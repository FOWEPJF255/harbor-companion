"""Regression checks for delayed tool mutation and malformed upstream payloads."""
import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from harbor.agent import Agent
from harbor.config import Settings
from harbor.main import create_app
from harbor.providers import CompatibleProvider, Completion


@pytest.mark.parametrize("message", [None, [], "not an object"])
def test_malformed_upstream_message_is_visible_failure(tmp_path, message):
    settings = Settings(provider="openai_compatible", api_base="https://fixture.test/v1", api_key="synthetic-key",
                        model="fixture-model", db_path=str(tmp_path / "malformed.sqlite3"))
    provider = CompatibleProvider(settings, httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": message}]})))
    with TestClient(create_app(settings, provider)) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        response = client.post(f"/api/sessions/{sid}/chat", json={"message": "hello", "request_id": "malformed-fixture"})
        assert response.status_code == 502
        assert response.json()["failure_reason"]
        assert response.json()["trace"][-1]["status"] == "failed"
        assert "synthetic-key" not in response.text
        assert client.get(f"/api/sessions/{sid}").json()["messages"] == []


class DelayedToolAgent(Agent):
    def execute(self, sid, name, args, proposals):
        time.sleep(0.03)
        return super().execute(sid, name, args, proposals)


class DelayedFinalProvider:
    name = "synthetic"

    async def complete(self, messages, tools):
        if messages[-1]["role"] == "tool":
            # Let the abandoned worker finish before the final turn commits.
            await asyncio.sleep(0.08)
            return Completion(content="The synthetic tool timed out; no memory was proposed.")
        return Completion(calls=[{"id": "delayed", "name": "propose_memory", "arguments": {"content": "must remain absent"}}])


def test_timed_out_worker_cannot_publish_late_proposal(tmp_path, monkeypatch):
    monkeypatch.setattr("harbor.main.Agent", DelayedToolAgent)
    settings = Settings(db_path=str(tmp_path / "late.sqlite3"), tool_timeout=0.005)
    with TestClient(create_app(settings, DelayedFinalProvider())) as client:
        sid = client.post("/api/sessions", json={"adult_confirmed": True}).json()["id"]
        response = client.post(f"/api/sessions/{sid}/chat", json={"message": "hello", "request_id": "delayed-fixture"})
        assert response.status_code == 200
        assert response.json()["pending_proposals"] == []
        assert any(t.get("observation", {}).get("error") == "tool_timeout" for t in response.json()["trace"])
        assert client.get(f"/api/sessions/{sid}").json()["memories"] == []
