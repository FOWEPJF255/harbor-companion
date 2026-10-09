"""Offline output-budget and partial-completion protocol checks."""
import asyncio
from dataclasses import asdict
import json

import httpx
import pytest

from harbor.config import Settings
from harbor.providers import CompatibleProvider, ProviderError


def invoke(payload, **options):
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=payload)

    settings = Settings(provider="openai_compatible", api_base=options.pop("api_base", "https://api.deepseek.com/v1"),
                        api_key="synthetic-test-only", model="deepseek-flash", **options)
    result = asyncio.run(CompatibleProvider(settings, httpx.MockTransport(handle)).complete([], []))
    return result, seen


def response(content="Partial visible answer", **message):
    return {"choices": [{"finish_reason": "length", "message": {"content": content, **message}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 600, "total_tokens": 610}}


@pytest.mark.parametrize("base,key", [("https://api.deepseek.com/v1", "max_tokens"),
                                     ("https://fixture.test/v1", "max_completion_tokens")])
@pytest.mark.parametrize("budget,expected", [(1200, 1200), (600, 600), (1800, 1800), (2000, 2000), (20, 600), (9000, 2000)])
def test_output_budget_is_bounded_for_both_protocols(base, key, budget, expected):
    result, seen = invoke(response(), api_base=base, max_output_tokens=budget)
    assert len(seen) == 1 and seen[0][key] == expected
    assert result.metadata["truncated"] is True


@pytest.mark.parametrize("budget", [True, 1200.5, "1200", None])
def test_invalid_manual_budget_cannot_reach_transport(budget):
    with pytest.raises(ProviderError, match="integer"):
        invoke(response(), max_output_tokens=budget)


@pytest.mark.parametrize("raw,expected", [("1200", 1200), ("599", 600), ("2001", 2000), ("1600", 1600)])
def test_settings_environment_clamps_budget(monkeypatch, raw, expected):
    monkeypatch.setenv("HARBOR_MAX_OUTPUT_TOKENS", raw)
    assert Settings.from_env().max_output_tokens == expected


def test_default_budget_is_1200(monkeypatch):
    monkeypatch.delenv("HARBOR_MAX_OUTPUT_TOKENS", raising=False)
    assert Settings().max_output_tokens == Settings.from_env().max_output_tokens == 1200


def test_visible_partial_text_retains_safe_metadata_and_discards_reasoning():
    result, seen = invoke(response(reasoning_content="hidden-reasoning-fixture", tool_calls=[]))
    assert result.content == "Partial visible answer" and result.calls == []
    assert result.metadata["truncated"] is True and result.metadata["finish_reason"] == "length"
    assert result.usage["total_tokens"] == 610
    assert "hidden-reasoning-fixture" not in json.dumps(asdict(result))
    assert len(seen) == 1


@pytest.mark.parametrize("content", [None, "", " \n", 0, False, [], {"text": "partial"}])
def test_no_nonempty_plain_partial_reply_still_fails(content):
    with pytest.raises(ProviderError):
        invoke(response(content))


@pytest.mark.parametrize("calls", [None, {}, "partial", [{"id": "incomplete"}],
                                  [{"id": "valid", "type": "function", "function": {"name": "read_memories", "arguments": "{}"}}]])
def test_truncated_tools_never_become_completion_calls(calls):
    with pytest.raises(ProviderError):
        invoke(response(tool_calls=calls))


@pytest.mark.parametrize("legacy", [{}, {"name": "read_memories", "arguments": "{"}])
def test_truncated_legacy_function_call_is_rejected(legacy):
    with pytest.raises(ProviderError):
        invoke(response(function_call=legacy))


def test_partial_refusal_remains_failure_without_raw_content():
    with pytest.raises(ProviderError) as failure:
        invoke(response(refusal="synthetic-private-refusal"))
    assert failure.value.metadata["failure_class"] == "refusal"
    assert "synthetic-private-refusal" not in str(failure.value) + json.dumps(failure.value.metadata)
