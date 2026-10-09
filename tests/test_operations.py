"""Resource budgets and redacted audit checks use disposable synthetic data."""
import asyncio
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from harbor.config import Settings
from harbor.main import create_app
from harbor.operations import RunBudgets
from harbor.providers import ProviderError


def test_request_budget_is_per_identity_and_recovers(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("harbor.operations.time.monotonic", lambda: clock[0])
    budgets = RunBudgets(Settings(chat_requests_per_minute=2))
    budgets.accept("user-a")
    budgets.accept("user-a")
    with pytest.raises(HTTPException) as exc:
        budgets.accept("user-a")
    assert exc.value.status_code == 429 and exc.value.headers["Retry-After"] == "60"
    budgets.accept("user-b")
    clock[0] = 161.0
    budgets.accept("user-a")
    assert list(budgets.requests) == ["user-a"]


def test_concurrency_budget_releases_after_failures_and_cancellation():
    async def scenario():
        budgets = RunBudgets(Settings(max_concurrent_runs=1, run_queue_timeout=0.02))
        async with budgets.slot():
            assert budgets.active == 1
            with pytest.raises(HTTPException) as exc:
                async with budgets.slot():
                    pytest.fail("Busy slot must reject")
            assert exc.value.status_code == 429
        with pytest.raises(RuntimeError):
            async with budgets.slot():
                raise RuntimeError("Synthetic failure")
        entered = asyncio.Event()
        async def cancelled():
            async with budgets.slot():
                entered.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(cancelled())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with budgets.slot():
            assert budgets.active == 1
        assert budgets.active == 0 and budgets.rejected == 1
    asyncio.run(scenario())


def test_cached_retry_does_not_charge_budget_or_duplicate_audit(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "retry.sqlite3"), chat_requests_per_minute=1))
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        body = {"message": "Synthetic personal sentence", "request_id": "ops-retry"}
        first = client.post(f"/api/sessions/{sid}/chat", json=body)
        assert first.status_code == 200
        assert client.post(f"/api/sessions/{sid}/chat", json=body).json()["run_id"] == first.json()["run_id"]
        body["request_id"] = "ops-second"
        rejected = client.post(f"/api/sessions/{sid}/chat", json=body)
        assert rejected.status_code == 429 and rejected.headers["retry-after"] == "60"
        events = app.state.store.audit_events()
        assert sum(e["action"] == "run_completed" for e in events) == 1
        assert "Synthetic personal sentence" not in json.dumps(events)


def test_failed_runs_are_not_committed_and_do_not_leak_provider_errors(tmp_path):
    class FailingProvider:
        name = "openai_compatible"
        async def complete(self, messages, tools):
            raise ProviderError("Synthetic private credential must not appear")
    app = create_app(Settings(db_path=str(tmp_path / "failure.sqlite3")), FailingProvider())
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        response = client.post(f"/api/sessions/{sid}/chat", json={"message": "Synthetic dialogue", "request_id": "failed-ops"})
        assert response.status_code == 502
        assert "Synthetic private credential" not in response.text
        assert app.state.store.history(sid) == []
        events = app.state.store.audit_events()
        assert any(e["action"] == "run_failed" for e in events)
        assert "Synthetic dialogue" not in json.dumps(events)


def test_data_agent_shares_the_request_budget(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "data.sqlite3"), chat_requests_per_minute=1))) as client:
        assert client.post("/api/data-agent", json={"question": "合成工具成功率"}).status_code == 200
        assert client.post("/api/data-agent", json={"question": "合成工具成功率"}).status_code == 429


def test_audit_allowlist_and_retention(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "audit.sqlite3")))
    store = app.state.store
    with pytest.raises(ValueError):
        store.audit_event("fixture", "run", dialogue="private fixture")
    store.audit_event("fixture", "run", duration_ms=12.5, total_tokens=42)
    store.audit_event("fixture", "old")
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    with store.connect() as db:
        db.execute("UPDATE audit_events SET created=? WHERE action='old'", (old,))
    assert store.prune_audit(30) == 1
    assert store.audit_events()[0]["metadata"] == {"duration_ms": 12.5, "total_tokens": 42}


def test_health_does_not_probe_models_or_return_credentials(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "health.sqlite3"), provider="openai_compatible",
                              api_key="synthetic-never-send", api_base="https://fixture.invalid", model="fixture"))
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200 and response.json()["provider_probe"] == "not performed by this endpoint"
        assert "synthetic-never-send" not in response.text and "health.sqlite3" not in response.text


@pytest.mark.parametrize("mode", ["anonymous", "", "anything"])
def test_unknown_auth_mode_refuses_startup(tmp_path, mode):
    with pytest.raises(ValueError, match="HARBOR_AUTH_MODE"):
        create_app(Settings(db_path=str(tmp_path / "invalid.sqlite3"), auth_mode=mode))


def test_remote_anonymous_profile_refuses_startup(tmp_path):
    with pytest.raises(ValueError, match="AUTH_MODE=accounts"):
        create_app(Settings(db_path=str(tmp_path / "remote.sqlite3"), allowed_hosts=("demo.example",),
                            client_token="synthetic-access-code-32-characters"))


def test_admin_login_validation_never_echoes_password(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path / "invalid-login.sqlite3")))) as client:
        for endpoint in ("bootstrap", "login"):
            response = client.post("/api/admin/" + endpoint, json={"username": "bad", "password": "x-private"})
            assert response.status_code == 422 and "x-private" not in response.text


def test_same_origin_loopback_alternate_port_is_allowed(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "origin.sqlite3")))
    with TestClient(app, base_url="http://127.0.0.1:8766") as client:
        assert client.post("/api/sessions", json={"adult_confirmed": True},
                           headers={"Origin": "http://127.0.0.1:8766"}).status_code == 200
        assert client.post("/api/sessions", json={"adult_confirmed": True},
                           headers={"Origin": "https://untrusted.example"}).status_code == 403


def test_delete_releases_session_lock_registry(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "lock-cleanup.sqlite3")))
    with TestClient(app) as client:
        for count in range(110):
            sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
            assert client.delete(f"/api/sessions/{sid}").status_code == 200
            assert not app.state.session_locks
        assert app.state.store.session_count() == 0
