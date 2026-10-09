"""Offline protocol and live-evaluation guard checks; no network or real credential."""
import asyncio
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import traceback

import httpx
import pytest

from harbor.config import Settings
from harbor.providers import CompatibleProvider, Completion, ProviderError

SENTINEL = "synthetic-never-print-credential-389"
HIDDEN = "synthetic-hidden-reasoning-772"


def settings(**options):
    return replace(Settings(provider="openai_compatible", api_base="https://api.deepseek.com/v1",
                            api_key=SENTINEL, model="deepseek-flash"), **options)


def completion(content="A synthetic final reply.", finish="stop", **message):
    return {"choices": [{"finish_reason": finish, "message": {"content": content, **message}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}}


def run(provider):
    return asyncio.run(provider.complete([{"role": "user", "content": "Synthetic input"}], []))


@pytest.mark.parametrize("base", ["https://api.deepseek.com", "https://api.deepseek.com/v1/", "https://API.DeepSeek.com/v1"])
def test_exact_official_host_uses_nonthinking_protocol(base):
    def handle(request):
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 1200
        assert payload["thinking"] == {"type": "disabled"}
        assert "max_completion_tokens" not in payload
        assert request.url.path in {"/chat/completions", "/v1/chat/completions"}
        assert request.headers["authorization"] == "Bearer " + SENTINEL
        return httpx.Response(200, json=completion(reasoning_content=HIDDEN))

    result = run(CompatibleProvider(settings(api_base=base), httpx.MockTransport(handle)))
    assert result.metadata["protocol"] == "deepseek_official"
    assert HIDDEN not in json.dumps(asdict(result))
    assert SENTINEL not in json.dumps(asdict(result))


@pytest.mark.parametrize("base", ["https://fixture.test/v1", "https://api.deepseek.com.attacker.test/v1"])
def test_other_hosts_keep_generic_compatibility(base):
    def handle(request):
        payload = json.loads(request.content)
        assert payload["max_completion_tokens"] == 1200
        assert "thinking" not in payload and "max_tokens" not in payload
        return httpx.Response(200, json={"choices": [{"message": {"content": "Legacy fixture"}}]})

    assert run(CompatibleProvider(settings(api_base=base), httpx.MockTransport(handle))).content == "Legacy fixture"


@pytest.mark.parametrize("finish", ["content_filter", "insufficient_system_resource", "aborted"])
def test_incomplete_generation_fails_with_safe_metadata(finish):
    payload = completion(content=SENTINEL, finish=finish, reasoning_content=HIDDEN)
    with pytest.raises(ProviderError) as failure:
        run(CompatibleProvider(settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=payload))))
    assert failure.value.metadata["finish_reason"] == finish
    assert failure.value.metadata["usage"]["total_tokens"] == 12
    assert SENTINEL not in str(failure.value) and HIDDEN not in str(failure.value.metadata)


def test_refusal_is_failure_even_with_stop():
    with pytest.raises(ProviderError) as failure:
        run(CompatibleProvider(settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=completion(refusal=SENTINEL)))))
    assert failure.value.metadata["failure_class"] == "refusal"
    assert SENTINEL not in str(failure.value.metadata) + str(failure.value)


@pytest.mark.parametrize("finish", [None, "unexpected-private-value", [], {"secret": SENTINEL}])
def test_official_finish_reason_is_required_and_validated(finish):
    with pytest.raises(ProviderError) as failure:
        run(CompatibleProvider(settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=completion(finish=finish)))))
    assert failure.value.metadata["finish_reason"] == "unknown"
    assert SENTINEL not in str(failure.value.metadata)


@pytest.mark.parametrize("choice", [None, [], "invalid"])
def test_malformed_choice_is_sanitized(choice):
    with pytest.raises(ProviderError):
        run(CompatibleProvider(settings(), httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [choice]}))))


def test_numeric_usage_whitelist_discards_untrusted_provider_text():
    payload = completion(reasoning_content=HIDDEN)
    payload["usage"].update(api_key=SENTINEL, hidden=HIDDEN, prompt_cache_hit_tokens=2,
                            prompt_tokens_details={"cached_tokens": 2, "secret": SENTINEL},
                            completion_tokens_details={"reasoning_tokens": 0, "reasoning_content": HIDDEN})
    result = run(CompatibleProvider(settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=payload))))
    assert result.usage["prompt_cache_hit_tokens"] == 2
    assert result.usage["completion_tokens_details"] == {"reasoning_tokens": 0}
    assert SENTINEL not in json.dumps(asdict(result)) and HIDDEN not in json.dumps(asdict(result))


@pytest.mark.parametrize("http_status", [400, 401, 429, 500])
def test_http_error_has_no_raw_body_or_credential_traceback(http_status):
    with pytest.raises(ProviderError) as failure:
        run(CompatibleProvider(settings(), httpx.MockTransport(lambda request: httpx.Response(http_status, text=SENTINEL + HIDDEN))))
    assert failure.value.metadata["http_status"] == http_status
    formatted = "".join(traceback.format_exception(failure.value))
    assert SENTINEL not in formatted and HIDDEN not in formatted
    assert failure.value.__cause__ is None


def test_transport_error_is_not_echoed():
    def handle(request):
        raise httpx.ConnectError(SENTINEL, request=request)

    with pytest.raises(ProviderError) as failure:
        run(CompatibleProvider(settings(), httpx.MockTransport(handle)))
    assert failure.value.metadata["failure_class"] == "transport"
    assert SENTINEL not in "".join(traceback.format_exception(failure.value))


def test_tool_call_is_parsed_without_reasoning():
    payload = completion(content=None, finish="tool_calls", reasoning_content=HIDDEN,
                         tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "read_memories", "arguments": "{}"}}])
    result = run(CompatibleProvider(settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=payload))))
    assert result.calls == [{"id": "call_1", "name": "read_memories", "arguments": {}}]
    assert HIDDEN not in json.dumps(asdict(result))


def load_live_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_live.py"
    spec = importlib.util.spec_from_file_location("harbor_live_evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("options", [{"provider": "mock"}, {"api_key": ""}, {"model": ""},
                                    {"api_base": "https://api.deepseek.com.attacker.test"},
                                    {"api_base": "http://api.deepseek.com"}, {"api_base": "https://api.deepseek.com/beta"}])
def test_live_validation_refuses_mock_missing_config_and_unapproved_destination(options):
    module = load_live_script()
    with pytest.raises(ValueError):
        module.validate_settings(settings(**options))


def test_validation_only_does_not_execute_or_create_artifacts(tmp_path, monkeypatch, capsys):
    module = load_live_script()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.Settings, "from_env", staticmethod(lambda: settings()))
    monkeypatch.setattr(module, "evaluate", lambda supplied: pytest.fail("Validation must not call evaluate"))
    monkeypatch.setattr(module.sys, "argv", ["evaluate_live.py"])
    assert module.main() == 0
    assert list(tmp_path.iterdir()) == []
    assert "0 model calls" in capsys.readouterr().out


def test_provider_budget_caps_all_attempts():
    module = load_live_script()

    class Fixed:
        async def complete(self, messages, tools):
            return Completion(content="synthetic")

    async def exercise():
        budget = module.BudgetProvider(Fixed())
        for _ in range(32):
            await budget.complete([], [])
        with pytest.raises(ProviderError):
            await budget.complete([], [])
        assert len(budget.requests) == 32

    asyncio.run(exercise())


def test_live_flow_is_isolated_synthetic_and_unscored(tmp_path, monkeypatch):
    module = load_live_script()
    monkeypatch.setattr(module, "ROOT", tmp_path)

    def handle(request):
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 600 and payload["thinking"]["type"] == "disabled"
        last = payload["messages"][-1]
        if last["role"] == "user" and "propose_memory" in last["content"]:
            response = completion(content=None, finish="tool_calls", tool_calls=[{
                "id": "synthetic_memory", "type": "function", "function": {
                    "name": "propose_memory", "arguments": json.dumps({"content": module.MEMORY_FACT})}}])
        elif last["role"] == "user" and "read_memories" in last["content"]:
            response = completion(content=None, finish="tool_calls", tool_calls=[{
                "id": "synthetic_read", "type": "function", "function": {"name": "read_memories", "arguments": "{}"}}])
        else:
            response = completion(reasoning_content=HIDDEN)
        return httpx.Response(200, json=response)

    monkeypatch.setattr(module, "CompatibleProvider", lambda supplied: CompatibleProvider(supplied, httpx.MockTransport(handle)))
    report = asyncio.run(module.evaluate(settings(db_path=str(tmp_path / "must-not-exist.sqlite3"), max_output_tokens=600)))
    assert not (tmp_path / "must-not-exist.sqlite3").exists()
    assert len(report["cases"]) == 8 and report["model_calls"] == 10
    assert report["actions"][0]["explicit_confirmation"] is True
    recall = next(row for row in report["cases"] if row["id"] == "memory-linked-recall")
    assert any(entry.get("name") == "read_memories" and entry["observation"]["memories"] for entry in recall["trace"])
    assert all(row["human_scores"] == "pending" for row in report["cases"])
    assert report["human_scores"] == "pending" and report["semantic_quality"].startswith("not scored")
    assert HIDDEN not in json.dumps(report) and SENTINEL not in json.dumps(report)
    path = module.write_report(report)
    assert path.parent == tmp_path / "reports" and path.with_suffix(".md").exists()
