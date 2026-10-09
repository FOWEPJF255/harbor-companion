"""Synthetic account authentication and ownership isolation checks."""
import asyncio
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from harbor.user_auth import UserAuth, user_router

PASSWORD = "synthetic-account-password-41"


class AuthDatabase:
    """Small isolated database adapter; no application .env or provider is imported."""
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()


@pytest.fixture
def auth_client(tmp_path):
    store = AuthDatabase(tmp_path / "auth.sqlite3")
    auth = UserAuth(store, SimpleNamespace(user_token_minutes=60, registration_enabled=True, auth_mode="accounts"))
    app = FastAPI()
    app.include_router(user_router(auth))
    with TestClient(app) as client:
        yield client, auth, store


def register(client, username="synthetic-alice", password=PASSWORD, **extra):
    response = client.post("/api/auth/register", json={"username": username, "password": password, "adult_confirmed": True, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def authorization(result):
    return {"Authorization": "Bearer " + result["access_token"]}


def test_registration_and_me_return_public_user_only(auth_client):
    client, _, _ = auth_client
    result = register(client)
    assert set(result) == {"access_token", "expires_in", "user"}
    assert set(result["user"]) == {"id", "username"}
    response = client.get("/api/auth/me", headers=authorization(result))
    assert response.status_code == 200
    assert response.json()["user"] == result["user"]
    assert 0 < response.json()["expires_in"] <= result["expires_in"]
    assert "password" not in response.text and "salt" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


def test_opaque_token_is_stored_as_hash_only(auth_client):
    client, _, store = auth_client
    result = register(client)
    with store.connect() as db:
        token = dict(db.execute("SELECT * FROM user_tokens").fetchone())
        user = dict(db.execute("SELECT * FROM users").fetchone())
    assert token["token_hash"] == hashlib.sha256(result["access_token"].encode()).hexdigest()
    assert result["access_token"] not in json.dumps(token)
    assert PASSWORD not in json.dumps(user)
    assert len(user["salt"]) == 32 and len(user["password_hash"]) == 64


def test_username_is_ascii_normalized(auth_client):
    client, _, _ = auth_client
    result = register(client, "  Synthetic.ALICE  ")
    assert result["user"]["username"] == "synthetic.alice"
    response = client.post("/api/auth/login", json={"username": "SYNTHETIC.ALICE", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["user"] == result["user"]


@pytest.mark.parametrize("username", ["用户", "Kelvin", "\u00a0alice\u00a0", "ab", "x" * 41, "with spaces", "<script>", "", 45])
def test_invalid_usernames_are_sanitized(auth_client, username):
    client, _, _ = auth_client
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD, "adult_confirmed": True})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid authentication input."}
    assert PASSWORD not in response.text


@pytest.mark.parametrize("password", ["short", "x" * 129, None, 45])
def test_invalid_passwords_are_not_echoed(auth_client, password):
    client, _, _ = auth_client
    response = client.post("/api/auth/login", json={"username": "synthetic-alice", "password": password})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid authentication input."}


def test_adult_consent_is_strict_and_required(auth_client):
    client, _, _ = auth_client
    for value in [False, "true", 1, None]:
        response = client.post("/api/auth/register", json={"username": "synthetic-alice", "password": PASSWORD, "adult_confirmed": value})
        assert response.status_code == 422
        assert PASSWORD not in response.text


def test_registration_is_disabled_by_default(auth_client):
    client, auth, store = auth_client
    auth.settings.registration_enabled = False
    response = client.post("/api/auth/register", json={"username": "synthetic-alice", "password": PASSWORD, "adult_confirmed": True})
    assert response.status_code == 403
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_registration_does_not_open_in_local_demo_mode(auth_client):
    client, auth, store = auth_client
    auth.settings.auth_mode = "local_demo"
    response = client.post("/api/auth/register", json={"username": "synthetic-alice", "password": PASSWORD, "adult_confirmed": True})
    assert response.status_code == 403
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_provision_returns_no_login_token(auth_client):
    _, auth, _ = auth_client
    user = asyncio.run(auth.provision("provisioned-user", PASSWORD))
    assert set(user) == {"id", "username"}
    assert user["username"] == "provisioned-user"


def test_duplicate_registration_uses_generic_error(auth_client):
    client, _, store = auth_client
    register(client)
    response = client.post("/api/auth/register", json={"username": "SYNTHETIC-ALICE", "password": PASSWORD, "adult_confirmed": True})
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to register using these details."}
    assert "UNIQUE" not in response.text
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_unknown_wrong_and_disabled_login_have_same_error(auth_client):
    client, _, store = auth_client
    result = register(client)
    unknown = client.post("/api/auth/login", json={"username": "unknown-user", "password": PASSWORD})
    wrong = client.post("/api/auth/login", json={"username": "synthetic-alice", "password": "wrong-password-long-enough"})
    with store.connect() as db:
        db.execute("UPDATE users SET active=0 WHERE id=?", (result["user"]["id"],))
    disabled = client.post("/api/auth/login", json={"username": "synthetic-alice", "password": PASSWORD})
    assert unknown.status_code == wrong.status_code == disabled.status_code == 401
    assert unknown.json() == wrong.json() == disabled.json() == {"detail": "Invalid user credentials."}
    assert PASSWORD not in unknown.text + wrong.text + disabled.text


def test_token_expiry_is_checked_in_database(auth_client):
    client, _, store = auth_client
    result = register(client)
    with store.connect() as db:
        db.execute("UPDATE user_tokens SET expires_at=0")
    assert client.get("/api/auth/me", headers=authorization(result)).status_code == 401


def test_logout_revokes_token_and_second_login_is_independent(auth_client):
    client, _, _ = auth_client
    first = register(client)
    second = client.post("/api/auth/login", json={"username": "synthetic-alice", "password": PASSWORD}).json()
    assert first["access_token"] != second["access_token"]
    assert client.post("/api/auth/logout", headers=authorization(first)).status_code == 200
    assert client.get("/api/auth/me", headers=authorization(first)).status_code == 401
    assert client.get("/api/auth/me", headers=authorization(second)).status_code == 200


def test_disabling_user_invalidates_existing_token(auth_client):
    client, _, store = auth_client
    result = register(client)
    with store.connect() as db:
        db.execute("UPDATE users SET active=0 WHERE id=?", (result["user"]["id"],))
    assert client.get("/api/auth/me", headers=authorization(result)).status_code == 401


def test_trusted_revoke_all_logins(auth_client):
    client, auth, _ = auth_client
    first = register(client)
    second = client.post("/api/auth/login", json={"username": "synthetic-alice", "password": PASSWORD}).json()
    auth.revoke_user(first["user"]["id"])
    assert client.get("/api/auth/me", headers=authorization(first)).status_code == 401
    assert client.get("/api/auth/me", headers=authorization(second)).status_code == 401


@pytest.mark.parametrize("header", [None, "", "Bearer bad-token", "Bearer usr_" + "a" * 43, "Basic example", "Bearer " + "x" * 4096, "Bearer malformed.admin.token"])
def test_missing_forged_and_admin_shaped_tokens_are_rejected(auth_client, header):
    client, _, _ = auth_client
    response = client.get("/api/auth/me", headers={"Authorization": header} if header is not None else {})
    assert response.status_code == 401
    assert response.json() == {"detail": "User login required."}
    assert response.headers["Cache-Control"] == "no-store"


def test_forwarded_headers_do_not_bypass_socket_rate_limit(auth_client):
    client, _, _ = auth_client
    for index in range(10):
        response = client.post("/api/auth/login", content="not-json", headers={"X-Forwarded-For": f"192.0.2.{index}"})
        assert response.status_code == 422
    limited = client.post("/api/auth/login", content="not-json", headers={"X-Forwarded-For": "198.51.100.12"})
    assert limited.status_code == 429
    assert limited.headers["Cache-Control"] == "no-store"


def test_bounded_json_and_extra_fields_are_sanitized(auth_client):
    client, _, _ = auth_client
    for payload in ["[]", "{", "x" * 5000, json.dumps({"username": "synthetic-alice", "password": PASSWORD, "owner_user_id": "forged-owner"})]:
        response = client.post("/api/auth/login", content=payload)
        assert response.status_code == 422
        assert response.json() == {"detail": "Invalid authentication input."}
        assert PASSWORD not in response.text


def test_restart_preserves_valid_login_and_revocation(auth_client):
    client, auth, store = auth_client
    result = register(client)
    replacement = UserAuth(store, auth.settings)
    app = FastAPI()
    app.include_router(user_router(replacement))
    with TestClient(app) as reopened:
        assert reopened.get("/api/auth/me", headers=authorization(result)).status_code == 200
        assert reopened.post("/api/auth/logout", headers=authorization(result)).status_code == 200
    assert client.get("/api/auth/me", headers=authorization(result)).status_code == 401


def test_two_users_have_distinct_public_ids_and_tokens(auth_client):
    client, _, _ = auth_client
    alice = register(client)
    bob = register(client, "synthetic-bob")
    assert alice["user"]["id"] != bob["user"]["id"]
    assert alice["access_token"] != bob["access_token"]
    assert client.get("/api/auth/me", headers=authorization(alice)).json()["user"] == alice["user"]
    assert client.get("/api/auth/me", headers=authorization(bob)).json()["user"] == bob["user"]


def test_openapi_documents_login_fields_and_user_bearer(auth_client):
    client, _, _ = auth_client
    schema = client.get("/openapi.json").json()
    fields = schema["paths"]["/api/auth/login"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert set(fields["required"]) == {"username", "password"}
    assert fields["properties"]["password"]["format"] == "password"
    assert schema["components"]["securitySchemes"]["UserBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/auth/me"]["get"]["security"] == [{"UserBearer": []}]
