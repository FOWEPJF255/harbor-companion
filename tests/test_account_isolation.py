"""Synthetic two-user API authorization, legacy migration, and review-consent checks."""
import asyncio

from fastapi.testclient import TestClient
import pytest

from harbor.config import Settings
from harbor.main import create_app

PASSWORD = "synthetic-account-password-41"
ALICE_FACT = "synthetic-alice-preference-824"
ALICE_PENDING = "synthetic-alice-pending-993"


def login_headers(result):
    return {"Authorization": "Bearer " + result["access_token"]}


def create_session(client, headers, **extra):
    response = client.post("/api/sessions", headers=headers, json={"adult_confirmed": True, **extra})
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.fixture
def accounts(tmp_path):
    settings = Settings(auth_mode="accounts", registration_enabled=True, db_path=str(tmp_path / "accounts.sqlite3"))
    with TestClient(create_app(settings)) as client:
        users = {}
        for name in ("alice", "bob"):
            result = client.post("/api/auth/register", json={"username": f"synthetic-{name}", "password": PASSWORD, "adult_confirmed": True})
            assert result.status_code == 200, result.text
            users[name] = result.json()
        a_headers, b_headers = login_headers(users["alice"]), login_headers(users["bob"])
        a, b = create_session(client, a_headers), create_session(client, b_headers)
        approved = client.post(f"/api/sessions/{a}/memories", headers=a_headers, json={"content": ALICE_FACT})
        assert approved.status_code == 200
        pending = client.app.state.store.memory_add(a, ALICE_PENDING, "pending")
        yield {"client": client, "store": client.app.state.store, "settings": settings, "users": users,
               "a_headers": a_headers, "b_headers": b_headers, "a": a, "b": b,
               "mid": approved.json()["id"], "pending_id": pending}


def bootstrap_admin(accounts):
    response = accounts["client"].post("/api/admin/bootstrap", json={"username": "synthetic-admin", "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/sessions", None),
    ("GET", "/api/sessions/{a}", None),
    ("POST", "/api/sessions", {"adult_confirmed": True}),
    ("POST", "/api/sessions/{a}/chat", {"message": "hello", "request_id": "synthetic-noauth"}),
    ("POST", "/api/sessions/{a}/memories", {"content": "Unapproved access"}),
    ("POST", "/api/data-agent", {"question": "emotion distribution"}),
])
def test_account_resources_require_user_authentication(accounts, method, path, body):
    response = accounts["client"].request(method, path.format(**accounts), json=body)
    assert response.status_code == 401
    assert ALICE_FACT not in response.text and ALICE_PENDING not in response.text


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/sessions/{a}", None),
    ("POST", "/api/sessions/{a}/chat", {"message": "hello", "request_id": "synthetic-cross-user"}),
    ("POST", "/api/sessions/{a}/memories", {"content": "Illegal new memory"}),
    ("PUT", "/api/sessions/{a}/memories/{mid}", {"content": "Illegal correction"}),
    ("POST", "/api/sessions/{a}/memories/{pending_id}/approve", None),
    ("POST", "/api/sessions/{a}/memories/{mid}/delete", None),
    ("DELETE", "/api/sessions/{a}/history", None),
    ("DELETE", "/api/sessions/{a}", None),
    ("POST", "/api/sessions/{a}/review-access", {"allowed": True}),
])
def test_another_users_session_handle_does_not_authorize_any_route(accounts, method, path, body):
    response = accounts["client"].request(method, path.format(**accounts), headers=accounts["b_headers"], json=body)
    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found"}
    assert ALICE_FACT not in response.text and ALICE_PENDING not in response.text
    state = accounts["client"].get(f"/api/sessions/{accounts['a']}", headers=accounts["a_headers"]).json()
    assert {memory["content"] for memory in state["memories"]} == {ALICE_FACT, ALICE_PENDING}
    assert state["review_access_allowed"] is False


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/sessions/{b}/memories/{pending_id}/approve", None),
    ("POST", "/api/sessions/{b}/memories/{mid}/delete", None),
    ("PUT", "/api/sessions/{b}/memories/{mid}", {"content": "Illegal replacement"}),
])
def test_foreign_memory_id_is_denied_even_with_an_owned_session(accounts, method, path, body):
    response = accounts["client"].request(method, path.format(**accounts), headers=accounts["b_headers"], json=body)
    assert response.status_code == 404
    assert accounts["client"].get(f"/api/sessions/{accounts['b']}", headers=accounts["b_headers"]).json()["memories"] == []
    assert any(memory["content"] == ALICE_FACT for memory in accounts["store"].memories(accounts["a"], "approved"))


def test_server_session_lists_are_owned_without_client_handles(accounts):
    client = accounts["client"]
    alice = client.get("/api/sessions", headers=accounts["a_headers"]).json()
    bob = client.get("/api/sessions", headers=accounts["b_headers"]).json()
    assert {session["id"] for session in alice["items"]} == {accounts["a"]}
    assert {session["id"] for session in bob["items"]} == {accounts["b"]}
    guessed = client.get(f"/api/sessions?ids={accounts['a']}", headers=accounts["b_headers"]).json()
    assert {session["id"] for session in guessed["items"]} == {accounts["b"]}
    assert ALICE_FACT not in str(guessed)


def test_owner_cannot_be_forged_in_new_session_body(accounts):
    response = accounts["client"].post("/api/sessions", headers=accounts["b_headers"], json={
        "adult_confirmed": True, "owner_user_id": accounts["users"]["alice"]["user"]["id"],
    })
    assert response.status_code == 422
    assert accounts["store"].session_count(accounts["users"]["bob"]["user"]["id"]) == 1


def test_cross_user_memory_source_is_rejected_without_creating_session(accounts):
    response = accounts["client"].post("/api/sessions", headers=accounts["b_headers"], json={
        "adult_confirmed": True, "memory_from_session_id": accounts["a"],
    })
    assert response.status_code == 404
    assert accounts["store"].session_count(accounts["users"]["bob"]["user"]["id"]) == 1


def test_store_rejects_cross_owner_memory_source(accounts):
    owner = accounts["users"]["bob"]["user"]["id"]
    with pytest.raises(ValueError, match="Memory source session not found"):
        accounts["store"].create("friend", memory_from_session_id=accounts["a"], owner_user_id=owner)
    assert accounts["store"].session_count(owner) == 1


def test_same_user_explicit_sharing_retains_only_approved_memory(accounts):
    linked = create_session(accounts["client"], accounts["a_headers"], memory_from_session_id=accounts["a"])
    state = accounts["client"].get(f"/api/sessions/{linked}", headers=accounts["a_headers"]).json()
    assert [row["content"] for row in state["memories"]] == [ALICE_FACT]
    assert state["memories"][0]["status"] == "approved"
    assert accounts["store"].session(linked)["memory_scope"] == accounts["store"].session(accounts["a"])["memory_scope"]
    assert accounts["store"].session(linked)["owner_user_id"] == accounts["users"]["alice"]["user"]["id"]
    assert accounts["client"].get(f"/api/sessions/{linked}", headers=accounts["b_headers"]).status_code == 404


def test_owned_resource_payloads_do_not_expose_internal_auth_data(accounts):
    response = accounts["client"].get(f"/api/sessions/{accounts['a']}", headers=accounts["a_headers"])
    assert response.status_code == 200
    assert not {"owner_user_id", "memory_scope", "character_prompt", "password_hash", "salt", "access_token"}.intersection(response.json())


def test_cached_reply_cannot_bypass_owner_guard(accounts):
    client = accounts["client"]
    path = f"/api/sessions/{accounts['a']}/chat"
    payload = {"message": "Hello synthetic account", "request_id": "synthetic-cache-owner"}
    first = client.post(path, headers=accounts["a_headers"], json=payload)
    assert first.status_code == 200, first.text
    other = client.post(path, headers=accounts["b_headers"], json=payload)
    assert other.status_code == 404
    repeated = client.post(path, headers=accounts["a_headers"], json=payload)
    assert repeated.status_code == 200
    assert repeated.json()["run_id"] == first.json()["run_id"]
    assert len(client.get(f"/api/sessions/{accounts['a']}", headers=accounts["a_headers"]).json()["messages"]) == 2


def test_legacy_unowned_sessions_are_not_automatically_claimed(accounts):
    legacy = accounts["store"].create("friend")["id"]
    accounts["store"].memory_add(legacy, "synthetic-legacy-private-886")
    client = accounts["client"]
    assert client.get(f"/api/sessions/{legacy}", headers=accounts["a_headers"]).status_code == 404
    assert client.get(f"/api/sessions/{legacy}", headers=accounts["b_headers"]).status_code == 404
    assert legacy not in {row["id"] for row in client.get("/api/sessions", headers=accounts["a_headers"]).json()["items"]}
    assert accounts["store"].session(legacy)["owner_user_id"] is None


def test_local_demo_can_restore_legacy_but_cannot_read_owned_sessions(accounts):
    legacy = accounts["store"].create("friend")["id"]
    with TestClient(create_app(Settings(db_path=accounts["store"].path))) as local:
        assert local.get(f"/api/sessions/{legacy}").status_code == 200
        assert local.get(f"/api/sessions/{accounts['a']}").status_code == 404
        listed = local.get(f"/api/sessions?ids={legacy},{accounts['a']}").json()["items"]
    assert [row["id"] for row in listed] == [legacy]


def test_account_pagination_returns_each_owned_session_once(accounts):
    expected = {accounts["a"]}
    for _ in range(24):
        expected.add(create_session(accounts["client"], accounts["a_headers"]))
    found = []
    cursor = None
    for page_index in range(3):
        params = {"cursor": cursor} if cursor else {}
        response = accounts["client"].get("/api/sessions", headers=accounts["a_headers"], params=params)
        assert response.status_code == 200
        result = response.json()
        assert len(result["items"]) <= 20
        found.extend(item["id"] for item in result["items"])
        cursor = result["next_cursor"]
        if not cursor:
            break
    assert cursor is None
    assert len(found) == len(set(found)) == 25
    assert set(found) == expected
    assert accounts["b"] not in found


def test_invalid_owned_session_cursor_is_rejected(accounts):
    response = accounts["client"].get("/api/sessions", headers=accounts["a_headers"], params={"cursor": "not-a-session-cursor"})
    assert response.status_code == 422


def test_user_token_cannot_access_management_plane(accounts):
    response = accounts["client"].get("/api/admin/overview", headers=accounts["a_headers"])
    assert response.status_code == 401


def test_administrator_token_is_not_a_user_identity(accounts):
    admin = bootstrap_admin(accounts)
    response = accounts["client"].get("/api/sessions", headers=admin)
    assert response.status_code == 401


def test_reviewer_requires_owner_grant_and_revocation_removes_notes(accounts):
    client = accounts["client"]
    admin = bootstrap_admin(accounts)
    sid = accounts["a"]
    review = {"session_id": sid, "persona_score": 3, "empathy_score": 3, "memory_score": 3, "note": "Synthetic observation for an explicitly permitted pilot case."}
    assert client.get(f"/api/admin/sessions/{sid}", headers=admin).status_code == 403
    assert client.post("/api/admin/reviews", headers=admin, json=review).status_code == 403
    granted = client.post(f"/api/sessions/{sid}/review-access", headers=accounts["a_headers"], json={"allowed": True})
    assert granted.status_code == 200
    assert client.get(f"/api/admin/sessions/{sid}", headers=admin).status_code == 200
    assert client.post("/api/admin/reviews", headers=admin, json=review).status_code == 200
    assert len(client.get("/api/admin/reviews", headers=admin).json()["items"]) == 1
    revoked = client.post(f"/api/sessions/{sid}/review-access", headers=accounts["a_headers"], json={"allowed": False})
    assert revoked.status_code == 200
    assert client.get(f"/api/admin/sessions/{sid}", headers=admin).status_code == 403
    assert client.post("/api/admin/reviews", headers=admin, json=review).status_code == 403
    assert client.get("/api/admin/reviews", headers=admin).json()["items"] == []
    events = accounts["store"].audit_events()
    assert any(event["action"] == "reviewer_read" and event["target_id"] == sid for event in events)
    assert all(ALICE_FACT not in str(event) and PASSWORD not in str(event) for event in events)


def test_granting_one_users_session_does_not_open_anothers(accounts):
    client = accounts["client"]
    admin = bootstrap_admin(accounts)
    assert client.post(f"/api/sessions/{accounts['b']}/review-access", headers=accounts["b_headers"], json={"allowed": True}).status_code == 200
    assert client.get(f"/api/admin/sessions/{accounts['b']}", headers=admin).status_code == 200
    assert client.get(f"/api/admin/sessions/{accounts['a']}", headers=admin).status_code == 403


def test_admin_provisioning_does_not_return_a_user_token(accounts):
    admin = bootstrap_admin(accounts)
    response = accounts["client"].post("/api/admin/users", headers=admin, json={
        "username": "synthetic-provisioned", "password": PASSWORD, "adult_confirmed": True,
    })
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"user"}
    assert set(response.json()["user"]) == {"id", "username"}
    assert PASSWORD not in response.text and "access_token" not in response.text


def test_admin_duplicate_provisioning_has_sanitized_validation_error(accounts):
    admin = bootstrap_admin(accounts)
    response = accounts["client"].post("/api/admin/users", headers=admin, json={
        "username": "synthetic-alice", "password": PASSWORD, "adult_confirmed": True,
    })
    assert response.status_code == 422
    assert PASSWORD not in response.text and "already" not in response.text.lower()
    assert "access_token" not in response.text and "password_hash" not in response.text


def test_remote_profile_requires_accounts_even_with_shared_code(tmp_path):
    with pytest.raises(ValueError, match="AUTH_MODE=accounts"):
        create_app(Settings(db_path=str(tmp_path / "invalid-remote.sqlite3"), allowed_hosts=("pilot.example",), client_token="x" * 32))


def test_shared_deployment_code_is_not_user_authentication(tmp_path):
    settings = Settings(auth_mode="accounts", allowed_hosts=("pilot.example",), client_token="synthetic-shared-code-for-pilot-32", db_path=str(tmp_path / "shared-code.sqlite3"))
    with TestClient(create_app(settings)) as client:
        auth = client.app.state.user_auth
        asyncio.run(auth.provision("synthetic-pilot", PASSWORD))
        headers = {"Host": "pilot.example", "X-Harbor-Access": settings.client_token}
        assert client.post("/api/sessions", headers=headers, json={"adult_confirmed": True}).status_code == 401
        logged_in = client.post("/api/auth/login", headers=headers, json={"username": "synthetic-pilot", "password": PASSWORD})
        assert logged_in.status_code == 200, logged_in.text
        authorized = {**headers, **login_headers(logged_in.json())}
        assert client.post("/api/sessions", headers=authorized, json={"adult_confirmed": True}).status_code == 200
