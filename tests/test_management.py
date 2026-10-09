"""Management-plane checks with synthetic credentials and disposable databases."""
import json

import pytest
from fastapi.testclient import TestClient

from harbor.config import Settings
from harbor.main import create_app

FIXTURE_LOGIN = {"username": "fixture-owner", "password": "synthetic-password-only"}


@pytest.fixture
def owner(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "admin.sqlite3")))) as client:
        response = client.post("/api/admin/bootstrap", json=FIXTURE_LOGIN)
        assert response.status_code == 200
        yield client, {"Authorization": "Bearer " + response.json()["token"]}


@pytest.mark.parametrize("path", ["overview", "characters", "sessions", "reviews", "provider-status"])
def test_admin_routes_require_owner(tmp_path, path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "no-owner.sqlite3")))) as client:
        assert client.get("/api/admin/" + path).status_code == 401


def test_admin_logout_and_restart_revoke_token(owner):
    client, headers = owner
    assert client.get("/api/admin/overview", headers=headers).status_code == 200
    restarted = TestClient(create_app(Settings(db_path=client.app.state.store.path)))
    assert restarted.get("/api/admin/overview", headers=headers).status_code == 401
    assert client.post("/api/admin/logout", headers=headers).status_code == 200
    assert client.get("/api/admin/overview", headers=headers).status_code == 401


def test_remote_configuration_cannot_bootstrap(tmp_path):
    access = "synthetic-demo-access-code-32-characters"
    settings = Settings(db_path=str(tmp_path / "remote.sqlite3"), allowed_hosts=("demo.example",), client_token=access,
                        auth_mode="accounts")
    with TestClient(create_app(settings)) as client:
        assert not client.get("/api/admin/setup-status").json()["can_initialize"]
        assert client.post("/api/admin/bootstrap", headers={"X-Harbor-Access": access}, json=FIXTURE_LOGIN).status_code == 403


def test_private_details_are_explicit_and_reviews_follow_erasure(owner):
    client, headers = owner
    sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
    turn = client.post(f"/api/sessions/{sid}/chat", json={"message": "synthetic private sentence", "request_id": "review-fixture"}).json()
    summary = client.get("/api/admin/sessions", headers=headers).json()
    assert "synthetic private sentence" not in json.dumps(summary)
    detail = client.get(f"/api/admin/sessions/{sid}", headers=headers).json()
    assert detail["messages"][0]["content"] == "synthetic private sentence"
    review = {"session_id": sid, "run_id": turn["run_id"], "persona_score": 3, "empathy_score": 2, "memory_score": 1,
              "note": "Synthetic annotation; not genuine model quality."}
    result = client.post("/api/admin/reviews", headers=headers, json=review)
    assert result.status_code == 200 and result.json()["provider"] == "mock"
    client.delete(f"/api/sessions/{sid}/history")
    assert client.get("/api/admin/reviews", headers=headers).json()["items"] == []


def test_character_snapshot_and_archive(owner):
    client, headers = owner
    original = client.post("/api/sessions", json={"adult_confirmed": True}).json()
    seed = next(c for c in client.get("/api/admin/characters", headers=headers).json()["items"] if c["id"] == "nova")
    seed.update(name="Revised fixture", system_prompt="A disclosed adult AI fixture.", greeting="Synthetic revised greeting")
    assert client.put("/api/admin/characters/nova", headers=headers, json=seed).status_code == 200
    older = client.get(f"/api/sessions/{original['id']}").json()
    assert older["character_name"] == original["character_name"]
    assert older["character_greeting"] == original["character_greeting"]
    assert client.post("/api/sessions", json={"adult_confirmed": True}).json()["character_name"] == "Revised fixture"
    seed["enabled"] = False
    client.put("/api/admin/characters/nova", headers=headers, json=seed)
    assert client.post("/api/sessions", json={"adult_confirmed": True}).status_code == 404
    assert client.get(f"/api/sessions/{original['id']}").status_code == 200


def test_model_credentials_are_not_returned(tmp_path):
    settings = Settings(db_path=str(tmp_path / "config.sqlite3"), provider="openai_compatible",
                        api_base="https://fixture-user:fixture-secret@example.test:8443/v1?secret=fixture-query",
                        api_key="fixture-provider-key", model="fixture-model")
    with TestClient(create_app(settings)) as client:
        token = client.post("/api/admin/bootstrap", json=FIXTURE_LOGIN).json()["token"]
        response = client.get("/api/admin/provider-status", headers={"Authorization": "Bearer " + token})
        assert response.json()["api_base"] == "https://example.test:8443/v1"
        for secret in ["fixture-user", "fixture-secret", "fixture-query", "fixture-provider-key", "password_hash"]:
            assert secret not in response.text
        assert "fixture-provider-key" not in client.get("/api/status").text
