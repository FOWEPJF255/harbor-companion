"""Synthetic persistence and capability-scope regression checks."""
import json
import sqlite3
import time

import pytest

from fastapi.testclient import TestClient

from harbor.config import Settings
from harbor.main import create_app
from harbor.store import Store


def test_proposal_restart_and_disk_boundary(tmp_path):
    path = str(tmp_path / "memory.sqlite3")
    store = Store(path)
    sid = store.create("friend")["id"]
    mid = store.memory_add(sid, "synthetic unapproved preference", "pending")
    assert store.memories(sid)[0]["id"] == mid
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM approved_memories").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0
    reloaded = Store(path)
    assert reloaded.memories(sid) == []
    assert not reloaded.memory_action(sid, mid, "approve")


def test_proposal_expiry(tmp_path):
    store = Store(str(tmp_path / "expiry.sqlite3"))
    sid = store.create("friend")["id"]
    mid = store.memory_add(sid, "synthetic", "pending")
    store._pending[mid]["expires_at"] = time.monotonic() - 1
    assert store.memories(sid) == []
    assert not store.memory_action(sid, mid, "approve")


def test_shared_memory_survives_source_deletion_and_restart(tmp_path):
    path = str(tmp_path / "shared.sqlite3")
    store = Store(path)
    a = store.create("friend")["id"]
    mid = store.memory_add(a, "approved synthetic")
    b = store.create("friend", memory_from_session_id=a)["id"]
    store.delete(a)
    reloaded = Store(path)
    assert reloaded.memories(b, "approved")[0]["id"] == mid
    reloaded.delete(b)
    with reloaded.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM approved_memories").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM memory_spaces").fetchone()[0] == 0


def test_legacy_approved_only_migration(tmp_path):
    path = str(tmp_path / "legacy.sqlite3")
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE sessions(id TEXT PRIMARY KEY,mode TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE memories(id TEXT PRIMARY KEY,session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
              content TEXT,status TEXT,created TEXT);
            INSERT INTO sessions VALUES('old','friend','2026-10-09');
            INSERT INTO memories VALUES('a','old','approved fixture','approved','2026-10-09');
            INSERT INTO memories VALUES('p','old','pending fixture','pending','2026-10-09');
        """)
    store = Store(path)
    assert [m["id"] for m in store.memories("old")] == ["a"]
    assert [m["id"] for m in Store(path).memories("old")] == ["a"]


def test_pending_correction_not_an_approval(tmp_path):
    store = Store(str(tmp_path / "pending.sqlite3"))
    sid = store.create("friend")["id"]
    mid = store.memory_add(sid, "pending", "pending")
    assert not store.memory_correct(sid, mid, "replacement")
    assert store.memories(sid, "approved") == []


def test_idempotency_collision_does_not_change_history(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "retry.sqlite3")))) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        route = f"/api/sessions/{sid}/chat"
        first = client.post(route, json={"message": "hello", "request_id": "same-request"})
        assert first.status_code == 200
        assert client.post(route, json={"message": "changed", "request_id": "same-request"}).status_code == 409
        assert len(client.get(f"/api/sessions/{sid}").json()["messages"]) == 2


def test_legacy_cache_without_hash_is_not_blindly_replayed(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "legacy-cache.sqlite3")))) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        route = f"/api/sessions/{sid}/chat"
        client.post(route, json={"message": "original fixture", "request_id": "old-request"})
        with client.app.state.store.connect() as db:
            db.execute("UPDATE turns SET request_hash=NULL")
        assert client.post(route, json={"message": "changed fixture", "request_id": "old-request"}).status_code == 409
        assert len(client.get(f"/api/sessions/{sid}").json()["messages"]) == 2


def test_proposal_trace_does_not_persist_dedicated_content(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "trace.sqlite3")))) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        response = client.post(f"/api/sessions/{sid}/chat", json={"message": "记住：合成偏好", "request_id": "memory-request"}).json()
        assert len(response["pending_proposals"]) == 1
        with client.app.state.store.connect() as db:
            stored = json.loads(db.execute("SELECT response FROM turns WHERE session_id=?", (sid,)).fetchone()[0])
        assert "合成偏好" not in json.dumps(stored, ensure_ascii=False)
        assert "pending_proposals" not in stored
        assert "proposals" not in stored
        trace = next(t for t in stored["trace"] if t["type"] == "tool")
        assert trace["observation"]["needs_confirmation"] is True


def test_shared_correction_and_delete_are_scoped(tmp_path):
    store = Store(str(tmp_path / "correction.sqlite3"))
    a = store.create("friend")["id"]
    b = store.create("friend", memory_from_session_id=a)["id"]
    unrelated = store.create("friend")["id"]
    mid = store.memory_add(a, "old synthetic preference")
    assert not store.memory_correct(unrelated, mid, "cross-scope replacement")
    assert store.memory_correct(b, mid, "corrected synthetic preference")
    assert store.memories(a)[0]["revision"] == 2
    assert store.memories(a)[0]["content"] == "corrected synthetic preference"
    assert store.memory_action(b, mid, "delete")
    assert store.memories(a) == []


def test_shared_space_limit_is_rechecked_at_approval(tmp_path):
    store = Store(str(tmp_path / "limit.sqlite3"))
    a = store.create("friend")["id"]
    b = store.create("friend", memory_from_session_id=a)["id"]
    pending = store.memory_add(a, "pending synthetic", "pending")
    for index in range(100):
        store.memory_add(b, f"approved synthetic {index}")
    with pytest.raises(ValueError, match="Memory limit"):
        store.memory_action(a, pending, "approve")
    with pytest.raises(ValueError, match="Memory limit"):
        store.memory_add(b, "overflow")
    assert len(store.memories(a, "approved")) == 100
    assert store.memories(a, "pending")[0]["id"] == pending
