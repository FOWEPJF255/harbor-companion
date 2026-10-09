"""Synthetic continuity, snapshot tool, partial-output and profile-route contracts."""
import asyncio
import json

from fastapi.testclient import TestClient

from harbor.agent import Agent
from harbor.config import Settings
from harbor.context import ContextBuilder, SUMMARY_BYTES
from harbor.main import create_app
from harbor.providers import Completion
from harbor.store import Store


def add_pair(store, sid, user, reply="Synthetic acknowledgement."):
    with store.connect() as db:
        for role, content in (("user", user), ("assistant", reply)):
            db.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)",
                       (sid, role, content, "neutral", "2026-10-09T00:00:00Z"))


def test_long_dialogue_keeps_early_plan_and_latest_correction_without_approved_memory(tmp_path):
    store = Store(str(tmp_path / "context.sqlite3"))
    sid = store.create("friend")["id"]
    add_pair(store, sid, "我们约定下周二讨论我的自行车路线。")
    for n in range(75):
        add_pair(store, sid, f"合成聊天第{n}轮。")
        ContextBuilder(store).build(sid)
    add_pair(store, sid, "更正：路线讨论改成下周三，不是周二。")
    for n in range(8):
        add_pair(store, sid, f"后续普通闲聊{n}。")
    summary, recent, metrics = ContextBuilder(store).build(sid)
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "下周二" in serialized and "下周三" in serialized
    assert all(set(e) == {"source_message_id", "speaker", "kind", "quote"} for e in summary["entries"])
    assert len(recent) == 12 and metrics["summary_utf8_bytes"] <= SUMMARY_BYTES
    assert metrics["lossy"] and metrics["omitted_entries"] > 0
    assert store.memories(sid, "approved") == []
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM approved_memories").fetchone()[0] == 0


def test_summary_isolation_restart_and_clear_history(tmp_path):
    path = str(tmp_path / "isolated.sqlite3")
    store = Store(path)
    one = store.create("friend")["id"]
    add_pair(store, one, "我喜欢SYNTHETIC-ANCHOR。")
    for n in range(8):
        add_pair(store, one, f"Synthetic {n}.")
    ContextBuilder(store).build(one)
    store = Store(path)
    assert "SYNTHETIC-ANCHOR" in json.dumps(ContextBuilder(store).build(one)[0])
    two = store.create("friend", memory_from_session_id=one)["id"]
    assert "SYNTHETIC-ANCHOR" not in json.dumps(ContextBuilder(store).build(two))
    store.clear_history(one)
    assert "SYNTHETIC-ANCHOR" not in json.dumps(ContextBuilder(store).build(one))
    with store.connect() as db:
        assert not db.execute("SELECT * FROM session_summaries WHERE session_id=?", (one,)).fetchone()


def test_large_history_has_explicit_gaps_and_complete_excerpts(tmp_path):
    store = Store(str(tmp_path / "large.sqlite3"))
    sid = store.create("friend")["id"]
    for n in range(300):
        add_pair(store, sid, "x" * 1900, "y" * 3900)
    summary, recent, metrics = ContextBuilder(store).build(sid)
    assert metrics["omitted_messages"] > 0 and metrics["excerpt_omissions"] > 0
    assert metrics["recent_utf8_bytes"] <= 18000 and metrics["summary_utf8_bytes"] <= SUMMARY_BYTES
    assert all(row["content"] in {"x" * 1900, "y" * 3900} for row in recent)
    assert summary["entries"] == []  # No mid-sentence invented fragment.


def test_read_own_profile_is_readonly_and_snapshot_scoped(tmp_path):
    store = Store(str(tmp_path / "tool.sqlite3"))
    sid = store.create("friend", "ember")["id"]
    agent = Agent(store, None, Settings())
    proposals = []
    result = agent.execute(sid, "read_own_profile", {}, proposals)
    assert result["character_id"] == "ember" and result["profile"]["age"] == 26
    assert result["profile"]["fictional"] and not proposals
    assert agent.execute(sid, "read_own_profile", {"character_id": "nova"}, proposals) == {"error": "invalid_arguments"}
    assert store.history(sid) == [] and store.memories(sid) == []


class PartialAfterTool:
    name = "synthetic"

    async def complete(self, messages, tools):
        if messages[-1]["role"] != "tool":
            return Completion(calls=[{"id": "p", "name": "propose_memory", "arguments": {"content": "synthetic preference"}}])
        return Completion(content="This is an incomplete synthetic response", metadata={"truncated": True, "finish_reason": "length"})


def test_partial_reply_is_visible_idempotent_and_does_not_publish_proposals(tmp_path):
    settings = Settings(db_path=str(tmp_path / "partial.sqlite3"))
    with TestClient(create_app(settings, PartialAfterTool())) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True, "language": "en"}).json()["id"]
        payload = {"message": "Synthetic turn.", "request_id": "partial-fixture"}
        response = client.post(f"/api/sessions/{sid}/chat", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result["completion_status"] == "truncated" and "length limit" in result["reply"]
        assert result["pending_proposals"] == []
        assert client.post(f"/api/sessions/{sid}/chat", json=payload).json() == result
        assert client.get(f"/api/sessions/{sid}").json()["memories"] == []


def test_public_profile_route_has_no_prompt_and_session_snapshot_is_not_public(tmp_path):
    settings = Settings(db_path=str(tmp_path / "public.sqlite3"), client_token="synthetic-access-code")
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/characters/nova/profile")
        assert response.status_code == 200 and response.json()["profile"]["age"] == 29
        assert "system_prompt" not in response.text and "character_prompt" not in response.text
        assert client.get("/api/characters/missing/profile").status_code == 404
        headers = {"X-Harbor-Access": settings.client_token}
        session = client.post("/api/sessions", headers=headers, json={"adult_confirmed": True}).json()
        assert "character_profile" not in session
        sid = session["id"]
        assert client.get(f"/api/sessions/{sid}/profile").status_code == 403
        assert client.get(f"/api/sessions/{sid}/profile", headers=headers).json()["revision"] == session["character_revision"]


def test_prompt_keeps_sources_separate_and_respects_language(tmp_path):
    class Capture:
        name = "synthetic"
        async def complete(self, messages, tools):
            self.messages = messages
            return Completion(content="Synthetic response.")
    store = Store(str(tmp_path / "prompt.sqlite3"))
    sid = store.create("friend", "sage")["id"]
    provider = Capture()
    result = asyncio.run(Agent(store, provider, Settings()).run(sid, "讲讲你之前做过什么工作。", "en"))
    prompt = provider.messages[0]["content"]
    assert "FROZEN_FICTIONAL_CHARACTER_PROFILE" in prompt and "USER_APPROVED_MEMORY_DATA" in prompt
    assert "UNTRUSTED_SESSION_EXCERPTS" in prompt and "Response language: en" in prompt
    assert "journal" in prompt.lower() and "facts by invention" in prompt
    assert result["completion_status"] == "complete"
