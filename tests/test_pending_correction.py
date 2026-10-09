"""Editing and explicitly confirming a transient suggestion must approve it safely."""
from fastapi.testclient import TestClient

from harbor.config import Settings
from harbor.main import create_app
from harbor.store import Store


def test_pending_edit_confirmation_persists_only_corrected_content(tmp_path):
    path = str(tmp_path / "correct.sqlite3")
    app = create_app(Settings(db_path=path))
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        turn = client.post(f"/api/sessions/{sid}/chat", json={"message": "记住：合成旧偏好", "request_id": "pending-correct"}).json()
        mid = turn["pending_proposals"][0]["id"]
        response = client.put(f"/api/sessions/{sid}/memories/{mid}", json={"content": "合成修正偏好", "approve_pending": True})
        assert response.status_code == 200 and response.json()["status"] == "approved"
        assert app.state.store.memories(sid, "pending") == []
        restarted = Store(path)
        assert restarted.memories(sid, "approved")[0]["content"] == "合成修正偏好"


def test_pending_cannot_be_corrected_from_another_linked_session(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "isolation.sqlite3")))
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        linked = client.post("/api/sessions", json={"adult_confirmed": True, "memory_from_session_id": sid}).json()["id"]
        mid = app.state.store.memory_add(sid, "Synthetic suggestion", "pending")
        assert client.put(f"/api/sessions/{linked}/memories/{mid}", json={"content": "Not permitted", "approve_pending": True}).status_code == 404
        assert app.state.store.memories(sid, "pending")[0]["content"] == "Synthetic suggestion"


def test_pending_edit_confirmation_respects_approved_memory_capacity(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "capacity.sqlite3")))
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        for count in range(100):
            app.state.store.memory_add(sid, f"Synthetic fact {count}")
        mid = app.state.store.memory_add(sid, "Synthetic suggestion", "pending")
        response = client.put(f"/api/sessions/{sid}/memories/{mid}", json={"content": "Synthetic correction", "approve_pending": True})
        assert response.status_code == 422
        assert len(app.state.store.memories(sid, "approved")) == 100
        assert app.state.store.memories(sid, "pending")[0]["id"] == mid


def test_pending_edit_without_explicit_approval_is_not_saved(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "no-approval.sqlite3")))
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        mid = app.state.store.memory_add(sid, "Synthetic pending", "pending")
        assert client.put(f"/api/sessions/{sid}/memories/{mid}", json={"content": "Synthetic correction"}).status_code == 404
        assert app.state.store.memories(sid, "approved") == []
