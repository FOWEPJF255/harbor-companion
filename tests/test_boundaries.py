import json

import httpx
import pytest
from fastapi.testclient import TestClient

from harbor.config import Settings
from harbor.main import create_app
from harbor.providers import CompatibleProvider, Completion, ProviderError


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "test.sqlite3")))) as c:
        yield c


def new(client, mode="friend"):
    r = client.post("/api/sessions", json={"adult_confirmed": True, "mode": mode})
    assert r.status_code == 200
    return r.json()["id"]


def chat(client, sid, text, key="request-0001"):
    return client.post(f"/api/sessions/{sid}/chat", json={"message": text, "request_id": key})


def test_adult_gate(client):
    assert client.post("/api/sessions", json={"adult_confirmed": False}).status_code == 422


def test_memory_consent_recall_and_erasure(client):
    sid = new(client)
    assert chat(client, sid, "记住：我喜欢海边散步").status_code == 200
    s = client.get(f"/api/sessions/{sid}").json()
    memory = s["memories"][0]
    assert memory["status"] == "pending"
    assert "海边散步" not in chat(client, sid, "你还记得我吗？", "request-0002").json()["reply"]
    assert client.post(f"/api/sessions/{sid}/memories/{memory['id']}/approve").status_code == 200
    assert "海边散步" in chat(client, sid, "你还记得我吗？", "request-0003").json()["reply"]
    client.delete(f"/api/sessions/{sid}/history")
    assert client.get(f"/api/sessions/{sid}").json()["messages"] == []
    assert client.get(f"/api/sessions/{sid}").json()["memories"][0]["status"] == "approved"
    client.delete(f"/api/sessions/{sid}")
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_cross_session_isolation(client):
    a, b = new(client), new(client)
    mid = client.post(f"/api/sessions/{a}/memories", json={"content": "private preference"}).json()["id"]
    assert client.get(f"/api/sessions/{b}").json()["memories"] == []
    assert client.post(f"/api/sessions/{b}/memories/{mid}/delete").status_code == 404
    assert "private preference" not in chat(client, b, "memory").json()["reply"]


def test_retry_idempotency(client):
    sid = new(client)
    a = chat(client, sid, "你好").json()
    b = chat(client, sid, "你好").json()
    assert a["run_id"] == b["run_id"]
    s = client.get(f"/api/sessions/{sid}").json()
    assert len(s["messages"]) == 2
    assert s["insights"]["turn_count"] == 1


class BrokenProvider:
    name = "openai_compatible"

    async def complete(self, messages, tools):
        raise ProviderError("Synthetic failure")


def test_provider_failure_is_not_a_fake_success(tmp_path):
    c = TestClient(create_app(Settings(db_path=str(tmp_path / "broken.sqlite3")), BrokenProvider()))
    sid = new(c)
    assert chat(c, sid, "hello").status_code == 502
    assert c.get(f"/api/sessions/{sid}").json()["messages"] == []
    assert c.get(f"/api/sessions/{sid}").json()["insights"]["turn_count"] == 0


class LoopProvider:
    name = "synthetic"

    async def complete(self, messages, tools):
        return Completion(calls=[{"id": "loop", "name": "read_memories", "arguments": {}}])


def test_tool_loop_is_bounded(tmp_path):
    c = TestClient(create_app(Settings(db_path=str(tmp_path / "loop.sqlite3"), max_steps=2), LoopProvider()))
    sid = new(c)
    assert chat(c, sid, "hello").status_code == 502
    assert c.get(f"/api/sessions/{sid}").json()["messages"] == []


class BadToolProvider:
    name = "synthetic"

    async def complete(self, messages, tools):
        if messages[-1]["role"] == "tool":
            assert json.loads(messages[-1]["content"])["error"] == "tool_not_allowed"
            return Completion(content="That action is unavailable.")
        return Completion(calls=[{"id": "bad", "name": "run_shell", "arguments": {"command": "not executable"}}])


def test_unregistered_tools_are_not_executed(tmp_path):
    c = TestClient(create_app(Settings(db_path=str(tmp_path / "tool.sqlite3")), BadToolProvider()))
    result = chat(c, new(c), "run a command").json()
    assert any(t["name"] == "run_shell" and t["status"] == "denied" for t in result["trace"])


def test_compatible_adapter_round_trip(tmp_path):
    calls = []

    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.path == "/v1/chat/completions"
        if len(calls) == 1:
            message = {"content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {
                "name": "read_memories", "arguments": "{}"}}]}
        else:
            assert payload["messages"][-2]["role"] == "assistant"
            assert payload["messages"][-1]["tool_call_id"] == "call_1"
            message = {"content": "There are no approved memories yet."}
        return httpx.Response(200, json={"choices": [{"message": message}], "usage": {"total_tokens": 10}})

    settings = Settings(provider="openai_compatible", api_base="https://example.test/v1", api_key="synthetic-test-key",
                        model="test-model", db_path=str(tmp_path / "adapter.sqlite3"))
    c = TestClient(create_app(settings, CompatibleProvider(settings, httpx.MockTransport(handle))))
    result = chat(c, new(c), "memory").json()
    assert result["provider"] == "openai_compatible"
    assert result["usage"]["total_tokens"] == 20
    assert len(calls) == 2
    assert "synthetic-test-key" not in json.dumps(result)
    assert "api_key" not in c.get("/api/status").json()


def test_boundary_skips_unavailable_provider(tmp_path):
    c = TestClient(create_app(Settings(db_path=str(tmp_path / "policy.sqlite3")), BrokenProvider()))
    result = chat(c, new(c, "gentle_romance"), "我15岁").json()
    assert result["provider"] == "policy"
    assert "成年人" in result["reply"]


def test_reject_unrelated_browser_origin(client):
    assert client.post("/api/sessions", headers={"Origin": "https://unrelated.test"},
                       json={"adult_confirmed": True}).status_code == 403
    assert client.get("/api/status", headers={"Host": "unrelated.test"}).status_code == 403
