"""Synthetic owner-data export, erasure, reauthentication, and rollback checks."""
import asyncio
import json
from threading import Event, Lock
from types import SimpleNamespace
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

import harbor.account_lifecycle as lifecycle
from harbor.account_lifecycle import account_router
from harbor.store import Store, now
from harbor.context import ContextBuilder
from harbor.user_auth import UserAuth, user_router

PASSWORD = "synthetic-lifecycle-password-12"
PRIVATE_PROMPT = "synthetic-hidden-system-prompt-182"
PRIVATE_PENDING = "synthetic-unapproved-proposal-183"
OTHER_MESSAGE = "synthetic-bob-only-message-184"
ADMIN_NAME = "synthetic-private-reviewer-185"


def headers(token):
    return {"Authorization": "Bearer " + token}


@pytest.fixture
def owner_data(tmp_path):
    store = Store(str(tmp_path / "lifecycle.sqlite3"))
    settings = SimpleNamespace(auth_mode="accounts", registration_enabled=False, user_token_minutes=60)
    auth = UserAuth(store, settings)
    users = {name: asyncio.run(auth.provision("synthetic-" + name, PASSWORD)) for name in ("alice", "bob")}
    tokens = {name: auth.issue(user)["access_token"] for name, user in users.items()}
    alice = store.create("friend", owner_user_id=users["alice"]["id"])
    linked = store.create("friend", memory_from_session_id=alice["id"], owner_user_id=users["alice"]["id"])
    bob = store.create("friend", owner_user_id=users["bob"]["id"])
    legacy = store.create("friend")
    approved = store.memory_add(alice["id"], "synthetic-alice-approved-memory")
    bob_memory = store.memory_add(bob["id"], "synthetic-bob-approved-memory")
    pending = store.memory_add(alice["id"], PRIVATE_PENDING, "pending")
    bob_pending = store.memory_add(bob["id"], "synthetic-bob-pending", "pending")
    with store.connect() as db:
        db.execute("UPDATE sessions SET character_prompt=? WHERE owner_user_id=?", (PRIVATE_PROMPT, users["alice"]["id"]))
        db.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)", (bob["id"], "user", OTHER_MESSAGE, "neutral", now()))
        db.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)", (legacy["id"], "user", "synthetic-legacy-only", "neutral", now()))
    store.create_administrator(ADMIN_NAME, "synthetic-admin-verifier", "synthetic-admin-salt")
    store.audit_event(users["alice"]["id"], "session_created", alice["id"])
    store.audit_event("admin:" + ADMIN_NAME, "reviewer_read", alice["id"])
    store.audit_event("admin:" + ADMIN_NAME, "user_provisioned", users["alice"]["id"])
    store.audit_event(users["bob"]["id"], "session_created", bob["id"])
    store.audit_event("admin:" + ADMIN_NAME, "reviewer_read", bob["id"])
    callbacks = []
    app = FastAPI()
    app.include_router(user_router(auth))
    app.include_router(account_router(store, auth, on_erased=lambda sids, uid: callbacks.append((sids, uid))))
    with TestClient(app) as client:
        yield {"store": store, "auth": auth, "users": users, "tokens": tokens, "settings": settings, "client": client,
               "a": alice, "linked": linked, "b": bob, "legacy": legacy, "approved": approved,
               "bob_memory": bob_memory, "pending": pending, "bob_pending": bob_pending, "callbacks": callbacks}


def request(data, path="/export", body=None, method="POST", user="alice"):
    return data["client"].request(method, "/api/account" + path, headers=headers(data["tokens"][user]),
                                  json=body if body is not None else {"password": PASSWORD})


def seed_owned_history(data, count=120):
    store, sid = data["store"], data["a"]["id"]
    turns, messages, reviews = [], [], []
    for index in range(count):
        run = str(uuid.uuid4())
        response = {"run_id": run, "reply": f"synthetic-owned-reply-{index}", "emotion": "neutral", "provider": "mock", "usage": None,
                    "latency_ms": 1, "system_prompt": PRIVATE_PROMPT, "api_key": "synthetic-provider-key",
                    "pending_proposals": [{"content": PRIVATE_PENDING}], "reasoning_content": "synthetic-hidden-reasoning",
                    "trace": [{"type": "tool", "name": "read_memories", "input": {}, "status": "ok",
                               "observation": {"memories": [{"content": "synthetic-alice-approved-memory"}], "system_prompt": PRIVATE_PROMPT}},
                              {"type": "tool", "name": "propose_memory", "input": {"content": PRIVATE_PENDING},
                               "observation": {"content": PRIVATE_PENDING}, "status": "ok"}]}
        turns.append((run, sid, f"lifecycle-{index}", "mock", "neutral", 1, json.dumps(response), now(), "synthetic-request-hash"))
        messages.extend([(sid, "user", f"synthetic-owned-input-{index}", "neutral", now()),
                         (sid, "assistant", response["reply"], "neutral", now())])
        reviews.append((str(uuid.uuid4()), sid, run, 3, 3, 3, f"synthetic-owned-review-{index}", "mock", now()))
    with store.connect() as db:
        db.executemany("INSERT INTO turns(id,session_id,request_id,provider,emotion,latency_ms,response,created,request_hash) VALUES(?,?,?,?,?,?,?,?,?)", turns)
        db.executemany("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)", messages)
        db.executemany("INSERT INTO reviews(id,session_id,run_id,persona_score,empathy_score,memory_score,note,provider,created) VALUES(?,?,?,?,?,?,?,?,?)", reviews)
    store.audit_event(data["users"]["alice"]["id"], "run_completed", sid, run_id=turns[0][0], provider="mock", duration_ms=1)
    return turns


def table_counts(store):
    names = ("users", "user_tokens", "sessions", "memory_spaces", "approved_memories", "messages", "session_summaries", "turns", "reviews", "audit_events", "administrators")
    with store.connect() as db:
        return {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in names}


def test_export_is_complete_owned_snapshot_beyond_ui_limits(owner_data):
    seed_owned_history(owner_data)
    response = request(owner_data)
    assert response.status_code == 200, response.text[:200]
    assert response.headers["Content-Disposition"] == 'attachment; filename="harbor-account-export.json"'
    assert response.headers["Cache-Control"] == "no-store" and response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Type"] == "application/json"
    payload = response.json()
    assert set(payload) == {"format_version", "exported_at", "user", "sessions", "messages", "session_summaries", "turns", "memory_spaces", "approved_memories", "reviews", "audit"}
    assert payload["format_version"] == "1.0"
    assert set(payload["user"]) == {"id", "username", "created", "adult_confirmed"}
    assert payload["user"]["adult_confirmed"] is True
    assert {row["id"] for row in payload["sessions"]} == {owner_data["a"]["id"], owner_data["linked"]["id"]}
    assert len(payload["messages"]) == 240 and len(payload["turns"]) == len(payload["reviews"]) == 120
    assert len(payload["memory_spaces"]) == len(payload["approved_memories"]) == 1
    assert payload["approved_memories"][0]["id"] == owner_data["approved"]
    assert payload["turns"][-1]["response"]["reply"] == "synthetic-owned-reply-119"
    assert payload["turns"][0]["response"]["trace"][0]["input"] == {}
    assert payload["turns"][0]["response"]["trace"][0]["observation"]["memories"][0]["content"] == "synthetic-alice-approved-memory"
    assert any(row["action"] == "user_provisioned" and row["actor_id"] == "administrator" for row in payload["audit"])


def test_summary_export_and_erasure_are_owner_scoped(owner_data):
    seed_owned_history(owner_data, 12)
    store = owner_data["store"]
    ContextBuilder(store).build(owner_data["a"]["id"])
    with store.connect() as db:
        db.execute("INSERT INTO session_summaries VALUES(?,?,?,?)",
                   (owner_data["b"]["id"], 1, json.dumps({"entries": [OTHER_MESSAGE]}), now()))
    response = request(owner_data)
    assert response.status_code == 200 and OTHER_MESSAGE not in response.text
    summaries = response.json()["session_summaries"]
    assert len(summaries) == 1 and summaries[0]["session_id"] == owner_data["a"]["id"]
    assert "synthetic-owned-input" in summaries[0]["content"]
    assert response.json()["sessions"][0]["character_profile"]
    removed = request(owner_data, "/me", {"password": PASSWORD, "confirmation": "DELETE"}, "DELETE")
    assert removed.status_code == 200
    with store.connect() as db:
        rows = db.execute("SELECT session_id FROM session_summaries").fetchall()
    assert [row["session_id"] for row in rows] == [owner_data["b"]["id"]]


def test_export_excludes_credentials_prompts_proposals_and_other_accounts(owner_data):
    seed_owned_history(owner_data, 1)
    with owner_data["store"].connect() as db:
        credentials = db.execute("SELECT password_hash,salt FROM users WHERE id=?", (owner_data["users"]["alice"]["id"],)).fetchone()
    response = request(owner_data)
    assert response.status_code == 200
    for secret in (PASSWORD, *credentials, *owner_data["tokens"].values(), PRIVATE_PROMPT, PRIVATE_PENDING,
                   OTHER_MESSAGE, "synthetic-provider-key", "synthetic-hidden-reasoning", "synthetic-request-hash", ADMIN_NAME,
                   owner_data["b"]["id"], owner_data["legacy"]["id"], owner_data["bob_memory"]):
        assert secret not in response.text
    for field in ('"password_hash"', '"salt"', '"token_hash"', '"pending_proposals"', '"system_prompt"', '"character_prompt"', '"owner_user_id"', '"subject_user_id"'):
        assert field not in response.text


@pytest.mark.parametrize("path,method", [("/export", "POST"), ("/me", "DELETE")])
def test_owner_lifecycle_requires_user_bearer(owner_data, path, method):
    response = owner_data["client"].request(method, "/api/account" + path, json={"password": PASSWORD, "confirmation": "DELETE"})
    assert response.status_code == 401
    assert PASSWORD not in response.text


@pytest.mark.parametrize("path,method", [("/export", "POST"), ("/me", "DELETE")])
def test_wrong_current_password_does_not_log_out(owner_data, path, method):
    body = {"password": "synthetic-incorrect-password"}
    if method == "DELETE":
        body["confirmation"] = "DELETE"
    before = table_counts(owner_data["store"])
    response = request(owner_data, path, body, method)
    assert response.status_code == 403 and response.json() == {"detail": "Current password is incorrect."}
    assert table_counts(owner_data["store"]) == before
    assert owner_data["client"].get("/api/auth/me", headers=headers(owner_data["tokens"]["alice"])).status_code == 200


@pytest.mark.parametrize("body", [{}, {"password": 123}, {"password": "short"}, {"password": PASSWORD, "owner_user_id": "foreign"}, {"password": PASSWORD, "unexpected": "sensitive"}])
def test_lifecycle_validation_is_strict_and_sanitized(owner_data, body):
    response = request(owner_data, body=body)
    assert response.status_code == 422 and response.json() == {"detail": "Invalid account data input."}
    assert PASSWORD not in response.text and "sensitive" not in response.text


def test_lifecycle_rejects_oversized_or_invalid_json(owner_data):
    for raw in (b"{", b"[]", b"x" * 5000):
        response = owner_data["client"].post("/api/account/export", content=raw, headers=headers(owner_data["tokens"]["alice"]))
        assert response.status_code == 422 and response.json() == {"detail": "Invalid account data input."}


@pytest.mark.parametrize("confirmation", ["delete", " DELETE", "DELETE ", "REMOVE", ""])
def test_deletion_requires_exact_confirmation(owner_data, confirmation):
    before = table_counts(owner_data["store"])
    response = request(owner_data, "/me", {"password": PASSWORD, "confirmation": confirmation}, "DELETE")
    assert response.status_code == 400
    assert table_counts(owner_data["store"]) == before and not owner_data["callbacks"]


def test_export_applies_real_16_mib_limit_before_oversized_row_materialization(owner_data):
    assert lifecycle.MAX_EXPORT_BYTES == 16 * 1024 * 1024
    with owner_data["store"].connect() as db:
        db.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)", (owner_data["a"]["id"], "user", "x" * (lifecycle.MAX_EXPORT_BYTES + 1), "neutral", now()))
    response = request(owner_data)
    assert response.status_code == 413 and response.json() == {"detail": lifecycle.EXPORT_LIMIT_ERROR}
    assert "Content-Disposition" not in response.headers and response.headers["Cache-Control"] == "no-store"


def test_incremental_json_budget_counts_escaping_and_never_returns_partial_file(owner_data, monkeypatch):
    with owner_data["store"].connect() as db:
        db.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)", (owner_data["a"]["id"], "user", "\x01" * 700, "neutral", now()))
    monkeypatch.setattr(lifecycle, "MAX_EXPORT_BYTES", 3000)
    response = request(owner_data)
    assert response.status_code == 413 and response.json() == {"detail": lifecycle.EXPORT_LIMIT_ERROR}
    assert "Content-Disposition" not in response.headers


def test_export_snapshot_is_consistent_during_concurrent_write(owner_data, monkeypatch):
    store = owner_data["store"]
    with store.connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
    original = lifecycle._rows
    injected = []
    def concurrent_write(db, table, *args, **kwargs):
        if table == "messages" and not injected:
            with store.connect() as writer:
                writer.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)", (owner_data["a"]["id"], "user", "synthetic-after-snapshot", "neutral", now()))
            injected.append(True)
        return original(db, table, *args, **kwargs)
    monkeypatch.setattr(lifecycle, "_rows", concurrent_write)
    response = request(owner_data)
    assert response.status_code == 200 and injected
    assert "synthetic-after-snapshot" not in response.text
    assert store.history(owner_data["a"]["id"])[0]["content"] == "synthetic-after-snapshot"


def test_verify_password_never_issues_a_new_token(owner_data):
    before = table_counts(owner_data["store"])["user_tokens"]
    result = asyncio.run(owner_data["auth"].verify_password(owner_data["users"]["alice"]["id"], PASSWORD))
    assert result == owner_data["users"]["alice"]
    assert table_counts(owner_data["store"])["user_tokens"] == before


@pytest.mark.parametrize("path,method", [("/export", "POST"), ("/me", "DELETE")])
def test_token_is_rechecked_after_password_await(owner_data, monkeypatch, path, method):
    auth = owner_data["auth"]
    original = auth.verify_password
    async def revoke_during_password(owner, password):
        result = await original(owner, password)
        auth.revoke_user(owner)
        return result
    monkeypatch.setattr(auth, "verify_password", revoke_during_password)
    body = {"password": PASSWORD, **({"confirmation": "DELETE"} if method == "DELETE" else {})}
    response = request(owner_data, path, body, method)
    assert response.status_code == 401
    assert owner_data["store"].session(owner_data["a"]["id"]) is not None
    assert not owner_data["callbacks"] and "Content-Disposition" not in response.headers


def test_export_rechecks_token_after_threadpool_snapshot(owner_data, monkeypatch):
    original = lifecycle.export_snapshot
    def revoke_after_snapshot(store, owner, token_hash):
        result = original(store, owner, token_hash)
        owner_data["auth"].revoke_user(owner)
        return result
    monkeypatch.setattr(lifecycle, "export_snapshot", revoke_after_snapshot)
    response = request(owner_data)
    assert response.status_code == 401 and "Content-Disposition" not in response.headers


def test_erasure_removes_shared_owned_data_all_tokens_pending_and_attributable_audit(owner_data):
    turns = seed_owned_history(owner_data, 2)
    uid, bob = owner_data["users"]["alice"]["id"], owner_data["users"]["bob"]["id"]
    second_token = owner_data["auth"].issue(owner_data["users"]["alice"])["access_token"]
    store = owner_data["store"]
    old = store.create("friend", owner_user_id=uid)
    store.audit_event("admin:" + ADMIN_NAME, "reviewer_read", old["id"])
    store.audit_event(uid, "session_deleted", old["id"])
    store.delete(old["id"])
    store.audit_event("admin:" + ADMIN_NAME, "run_inspected", turns[0][0])
    store.audit_event("admin:" + ADMIN_NAME, "memory_inspected", owner_data["approved"])
    response = request(owner_data, "/me", {"password": PASSWORD, "confirmation": "DELETE"}, "DELETE")
    assert response.status_code == 200 and response.json() == {"ok": True, "deleted": True}
    assert response.headers["Cache-Control"] == "no-store"
    assert set(owner_data["callbacks"][0][0]) == {owner_data["a"]["id"], owner_data["linked"]["id"]}
    assert owner_data["callbacks"][0][1] == uid
    with store.connect() as db:
        for table, column in (("users", "id"), ("user_tokens", "user_id"), ("sessions", "owner_user_id"), ("memory_spaces", "owner_user_id"), ("audit_events", "subject_user_id")):
            assert db.execute(f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (uid,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM users WHERE id=?", (bob,)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM approved_memories WHERE id=?", (owner_data["bob_memory"],)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM messages WHERE content=?", (OTHER_MESSAGE,)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM administrators").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM turns WHERE session_id=?", (owner_data["a"]["id"],)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM reviews WHERE session_id=?", (owner_data["a"]["id"],)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM audit_events WHERE target_id IN (?,?,?,?)", (old["id"], turns[0][0], owner_data["approved"], uid)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM audit_events WHERE subject_user_id=?", (bob,)).fetchone()[0] == 2
    assert owner_data["pending"] not in store._pending and owner_data["bob_pending"] in store._pending
    assert store.session(owner_data["b"]["id"]) and store.session(owner_data["legacy"]["id"])
    for token in (owner_data["tokens"]["alice"], second_token):
        assert owner_data["client"].get("/api/auth/me", headers=headers(token)).status_code == 401
    assert owner_data["client"].get("/api/auth/me", headers=headers(owner_data["tokens"]["bob"])).status_code == 200


def test_erasure_rolls_back_database_pending_and_callback_on_failure(owner_data):
    store, uid = owner_data["store"], owner_data["users"]["alice"]["id"]
    with store.connect() as db:
        db.execute(f"CREATE TRIGGER synthetic_rollback BEFORE DELETE ON users WHEN OLD.id='{uid}' BEGIN SELECT RAISE(ABORT,'synthetic rollback detail'); END")
    before, pending = table_counts(store), dict(store._pending)
    response = request(owner_data, "/me", {"password": PASSWORD, "confirmation": "DELETE"}, "DELETE")
    assert response.status_code == 409 and response.json() == {"detail": lifecycle.DELETE_ERROR}
    assert "synthetic rollback detail" not in response.text
    assert table_counts(store) == before and store._pending == pending and not owner_data["callbacks"]
    assert owner_data["client"].get("/api/auth/me", headers=headers(owner_data["tokens"]["alice"])).status_code == 200


def test_old_deleted_session_admin_audit_is_exported_without_admin_identity(owner_data):
    store, uid = owner_data["store"], owner_data["users"]["alice"]["id"]
    old = store.create("friend", owner_user_id=uid)
    store.audit_event("admin:" + ADMIN_NAME, "reviewer_read", old["id"])
    store.delete(old["id"])
    response = request(owner_data)
    assert response.status_code == 200
    assert any(row["target_id"] == old["id"] and row["actor_id"] == "administrator" for row in response.json()["audit"])
    assert ADMIN_NAME not in response.text


def test_lifecycle_rate_limit_reuses_socket_ip_window(owner_data):
    for index in range(10):
        response = owner_data["client"].post("/api/account/export", content="{", headers={**headers(owner_data["tokens"]["alice"]), "X-Forwarded-For": f"192.0.2.{index}"})
        assert response.status_code == 422
    response = request(owner_data)
    assert response.status_code == 429
    assert response.headers["Cache-Control"] == "no-store"


def test_lifecycle_is_unavailable_in_local_demo_mode(owner_data):
    owner_data["settings"].auth_mode = "local_demo"
    response = request(owner_data)
    assert response.status_code == 403 and response.json() == {"detail": "Account data controls require account mode."}


def test_corrupt_stored_response_fails_without_partial_export(owner_data):
    turns = seed_owned_history(owner_data, 1)
    with owner_data["store"].connect() as db:
        db.execute("UPDATE turns SET response=? WHERE id=?", ("invalid synthetic JSON", turns[0][0]))
    response = request(owner_data)
    assert response.status_code == 409 and response.json() == {"detail": lifecycle.EXPORT_ERROR}
    assert "Content-Disposition" not in response.headers


def test_lifecycle_openapi_describes_password_and_confirmation(owner_data):
    schema = owner_data["client"].get("/openapi.json").json()
    deletion = schema["paths"]["/api/account/me"]["delete"]
    assert deletion["security"] == [{"UserBearer": []}]
    fields = deletion["requestBody"]["content"]["application/json"]["schema"]
    assert set(fields["required"]) == {"password", "confirmation"}
    assert fields["properties"]["password"]["format"] == "password"


def test_export_admission_bounds_workers_and_keeps_cancelled_worker_slot(owner_data, monkeypatch):
    entered, completed = [Event(), Event()], [Event(), Event()]
    release, counter_lock, started = Event(), Lock(), []
    def controlled_snapshot(store, owner, token_hash):
        with counter_lock:
            index = len(started)
            started.append(owner)
        if index < 2:
            entered[index].set()
            try:
                if not release.wait(10):
                    raise ValueError("Synthetic worker release timed out")
            finally:
                completed[index].set()
        return b'{"synthetic_fixture":true}'
    monkeypatch.setattr(lifecycle, "export_snapshot", controlled_snapshot)
    async def scenario():
        transport = httpx.ASGITransport(app=owner_data["client"].app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async def export():
                return await client.post("/api/account/export", json={"password": PASSWORD}, headers=headers(owner_data["tokens"]["alice"]))
            first = asyncio.create_task(export())
            second = None
            try:
                assert await asyncio.wait_for(asyncio.to_thread(entered[0].wait, 5), 6)
                second = asyncio.create_task(export())
                assert await asyncio.wait_for(asyncio.to_thread(entered[1].wait, 5), 6)
                first.cancel()
                await asyncio.sleep(0.01)
                assert not completed[0].is_set() and not completed[1].is_set()
                rejected = await asyncio.wait_for(export(), 3)
                assert rejected.status_code == 429
                assert rejected.json() == {"detail": "Account export is busy; try again later."}
                assert rejected.headers["Retry-After"] == "2" and rejected.headers["Cache-Control"] == "no-store"
                assert len(started) == 2
            finally:
                release.set()
                await asyncio.gather(first, *([second] if second else []), return_exceptions=True)
                for event in completed:
                    await asyncio.wait_for(asyncio.to_thread(event.wait, 5), 6)
            recovered = await export()
            assert recovered.status_code == 200 and recovered.json() == {"synthetic_fixture": True}
            assert len(started) == 3
    asyncio.run(scenario())


def test_export_admission_permit_recovers_after_worker_failure(owner_data, monkeypatch):
    attempts = []
    def fail_then_succeed(store, owner, token_hash):
        attempts.append(owner)
        if len(attempts) <= 3:
            raise ValueError("Synthetic snapshot failure")
        return b'{"synthetic_fixture":true}'
    monkeypatch.setattr(lifecycle, "export_snapshot", fail_then_succeed)
    for _ in range(3):
        response = request(owner_data)
        assert response.status_code == 409 and response.json() == {"detail": lifecycle.EXPORT_ERROR}
    response = request(owner_data)
    assert response.status_code == 200 and response.json() == {"synthetic_fixture": True}
