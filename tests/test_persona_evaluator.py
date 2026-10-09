"""No network: verify the durable sample budget and synthetic evaluation wiring."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from harbor.config import Settings
from harbor.providers import Completion, ProviderError


def script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_persona.py"
    spec = importlib.util.spec_from_file_location("persona_evaluator_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Fixed:
    async def complete(self, messages, tools):
        return Completion(content="Synthetic fixture response.")


def test_budget_persists_across_instances_and_counts_failed_requests(tmp_path):
    module = script()
    class Failed:
        async def complete(self, messages, tools):
            raise ProviderError("Synthetic failure")
    path = tmp_path / "ledger.sqlite3"
    budget = module.DurableBudget(Failed(), path)
    with pytest.raises(ProviderError):
        asyncio.run(budget.complete([], []))
    resumed = module.DurableBudget(Fixed(), path)
    for _ in range(17):
        asyncio.run(resumed.complete([], []))
    with pytest.raises(ProviderError):
        asyncio.run(resumed.complete([], []))
    records = resumed.records()
    assert len(records) == 18 and records[0]["status"] == "failed"


def test_validation_does_not_run_or_create_files(tmp_path, monkeypatch, capsys):
    module = script()
    settings = Settings(provider="openai_compatible", api_base="https://api.deepseek.com", model="deepseek-flash", api_key="fixture-key")
    monkeypatch.setattr(module.Settings, "from_env", staticmethod(lambda: settings))
    monkeypatch.setattr(module, "evaluate", lambda *_: pytest.fail("Must not call provider"))
    monkeypatch.setattr(module.sys, "argv", ["evaluate_persona.py"])
    assert module.main() == 0 and "zero requests" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_full_sample_fixture_memory_and_coverage_are_honest(tmp_path, monkeypatch):
    module = script()
    class Fixtures:
        async def complete(self, messages, tools):
            last = messages[-1]
            if last["role"] == "user" and "propose_memory" in last["content"]:
                return Completion(calls=[{"id": "fixture", "name": "propose_memory", "arguments": {"content": "合成用户喜欢雨后骑车"}}])
            return Completion(content="Synthetic local fixture; not a real-model quality result.")
    monkeypatch.setattr(module, "CompatibleProvider", lambda _: Fixtures())
    settings = Settings(provider="openai_compatible", api_base="https://api.deepseek.com", model="deepseek-flash", api_key="fixture-key",
                        db_path=str(tmp_path / "must-not-open.sqlite3"))
    report = asyncio.run(module.evaluate(settings, tmp_path))
    assert report["failures"] == 0 and len(report["cases"]) == 14
    assert len({row["category"] for row in report["cases"]}) == 12
    assert report["model_calls"] <= 18 and not (tmp_path / "must-not-open.sqlite3").exists()
    assert report["human_scores"] == "pending" and report["semantic_quality"] == "not scored"
    memory = next(row for row in report["cases"] if row["id"] == "memory")["scripted_memory_checks"]
    assert memory["approved_before_confirmation"] == 0 and memory["remaining_after_delete"] == 0
    assert memory["corrected"][0]["content"] == "合成用户喜欢晴天骑车"
    assert "fixture-key" not in json.dumps(report)
    with pytest.raises(ValueError):
        asyncio.run(module.evaluate(settings, tmp_path))
    followup = asyncio.run(module.evaluate(settings, tmp_path, follow_up=True))
    assert followup["model_calls"] <= 18 and len(followup["cases"]) == 16
    assert sum(row["id"].startswith("followup-") for row in followup["cases"]) == 2
    with pytest.raises(ValueError):
        asyncio.run(module.evaluate(settings, tmp_path, follow_up=True))
