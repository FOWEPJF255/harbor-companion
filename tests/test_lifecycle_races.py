"""Disposable account-erasure races and request-driven retention regression."""
import asyncio
from datetime import datetime, timedelta, timezone
import time

import httpx
import pytest

from harbor.agent import AgentFailure
from harbor.config import Settings
from harbor.main import create_app
from harbor.store import Store

PASSWORD = "synthetic-lifecycle-password-51"


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_erasure_blocks_inflight_and_queued_turns(tmp_path, outcome):
    async def scenario():
        app = create_app(Settings(auth_mode="accounts", registration_enabled=True,
                                  db_path=str(tmp_path / "race.sqlite3"), run_queue_timeout=5))
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed_run(sid, message, language):
            entered.set()
            await release.wait()
            if outcome == "failure":
                raise AgentFailure("synthetic_failure", [], "mock", 1)
            return {"run_id": "synthetic-erased-run", "reply": "Late synthetic reply", "emotion": "neutral",
                    "latency_ms": 1, "provider": "mock", "trace": [], "proposals": ["Never resurrect this fact"]}

        app.state.agent.run = delayed_run
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            result = (await client.post("/api/auth/register", json={"username": "synthetic-owner", "password": PASSWORD,
                                                                   "adult_confirmed": True})).json()
            headers = {"Authorization": "Bearer " + result["access_token"]}
            uid = result["user"]["id"]
            sid = (await client.post("/api/sessions", headers=headers, json={"adult_confirmed": True})).json()["id"]
            active = asyncio.create_task(client.post(f"/api/sessions/{sid}/chat", headers=headers,
                                        json={"message": "Synthetic first input", "request_id": "race-active"}))
            await asyncio.wait_for(entered.wait(), 3)
            queued = asyncio.create_task(client.post(f"/api/sessions/{sid}/chat", headers=headers,
                                        json={"message": "Synthetic second input", "request_id": "race-queued"}))
            await asyncio.sleep(0.02)
            erased = await client.request("DELETE", "/api/account/me", headers=headers,
                                         json={"password": PASSWORD, "confirmation": "DELETE"})
            assert erased.status_code == 200, erased.text
            release.set()
            responses = await asyncio.wait_for(asyncio.gather(active, queued), 3)
            assert all(r.status_code in {401, 404} for r in responses)
            assert all("Late synthetic reply" not in r.text for r in responses)
            assert app.state.store.session(sid) is None
            assert app.state.store.history(sid) == []
            assert app.state.store._proposal_snapshot() == []
            assert app.state.store.audit_events() == []
            assert not app.state.session_locks
            assert uid not in app.state.budgets.requests
            assert app.state.budgets.active == 0
            with app.state.store.connect() as db:
                assert db.execute("PRAGMA foreign_key_check").fetchall() == []
                assert db.execute("SELECT COUNT(*) FROM user_tokens").fetchone()[0] == 0
    asyncio.run(scenario())


def test_retention_removes_only_expired_security_records(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "retention.sqlite3"))
    app = create_app(Settings(db_path=store.path, auth_mode="accounts"))
    user = asyncio.run(app.state.user_auth.provision("synthetic-owner", PASSWORD))
    sid = store.create("friend", owner_user_id=user["id"])["id"]
    store.memory_add(sid, "Approved synthetic preference")
    stamp = datetime.now(timezone.utc).isoformat()
    store.audit_event(user["id"], "recent", sid)
    store.audit_event(user["id"], "old", sid)
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    with store.connect() as db:
        db.execute("UPDATE audit_events SET created=? WHERE action='old'", (old,))
        for name, expiry, revoked in [("expired", int(time.time())-1, None), ("revoked", int(time.time())+100, 1),
                                      ("active", int(time.time())+100, None)]:
            db.execute("INSERT INTO user_tokens VALUES(?,?,?,?,?)", (name, user["id"], expiry, stamp, revoked))
    clock = [100.0]
    monkeypatch.setattr("harbor.store.time.monotonic", lambda: clock[0])
    assert store.maintenance(30, force=True) == {"expired_or_revoked_tokens": 2, "expired_audit_events": 1}
    assert store.maintenance(30) is None
    clock[0] += 3601
    assert store.maintenance(30) == {"expired_or_revoked_tokens": 0, "expired_audit_events": 0}
    assert store.session(sid) and store.memories(sid)[0]["status"] == "approved"
    with store.connect() as db:
        assert [r[0] for r in db.execute("SELECT token_hash FROM user_tokens")] == ["active"]


def test_audit_provenance_survives_session_deletion(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "provenance.sqlite3")))
    store = app.state.store
    user = asyncio.run(app.state.user_auth.provision("synthetic-owner", PASSWORD))
    sid = store.create("friend", owner_user_id=user["id"])["id"]
    store.audit_event("admin:synthetic-operator", "reviewer_read", sid)
    store.delete(sid)
    assert store.audit_events()[0]["subject_user_id"] == user["id"]
    with store.connect() as db:
        db.execute("DELETE FROM users WHERE id=?", (user["id"],))
    store.audit_event(user["id"], "late_failure", sid)
    assert store.audit_events() == []
    with pytest.raises(ValueError, match="User account is not available"):
        store.create("friend", owner_user_id=user["id"])
