"""Objective planner/aggregation checks; no model-semantic quality is asserted."""
import hashlib
import json

import pytest

from harbor import data_agent


@pytest.mark.parametrize("question", ["合成对话的情绪分布如何？", "What is the emotion distribution?", "Show mood distribution"])
def test_emotion_distribution_uses_actual_fixture_rows(question):
    response = data_agent.analyze(question)
    assert response["plan"]["id"] == "emotion_distribution"
    assert response["result"]["sample_count"] == 12
    assert response["result"]["counts"] == {"calm": 3, "bright": 2, "low": 3, "overwhelmed": 4}
    assert response["result"]["shares_percent"]["overwhelmed"] == 33.33


def test_tool_outcomes_include_denials_and_timeouts_in_denominator():
    response = data_agent.analyze("工具成功、失败、超时的分布怎样？")
    assert response["plan"]["dataset"] == "tool_events"
    assert response["result"]["sample_count"] == 20
    assert response["result"]["counts"] == {"success": 15, "error": 2, "timeout": 1, "denied": 2}
    assert response["result"]["success_share_percent"] == 75
    assert response["result"]["by_tool"]["propose_memory"]["success_share_percent"] == 60


@pytest.mark.parametrize("question", ["What is tool success rate for read_memories?", "read_memories成功率是多少？", "工具结果 tool=read_memories"])
def test_known_tool_filter(question):
    response = data_agent.analyze(question)
    assert response["plan"]["filters"] == {"tool": "read_memories"}
    assert response["result"]["sample_count"] == 6
    assert response["result"]["counts"]["error"] == 1
    assert response["result"]["success_share_percent"] == 83.33


def test_unfiltered_latency_includes_synthetic_failures():
    response = data_agent.analyze("合成轮次平均延迟和p95是多少？")
    assert response["result"]["sample_count"] == 12
    assert response["result"]["mean_ms"] == 2902.5
    assert response["result"]["median_ms"] == 335
    assert response["result"]["p95_ms"] == 30000
    assert response["result"]["status_counts"] == {"completed": 10, "error": 1, "timeout": 1}


@pytest.mark.parametrize("question", ["已完成轮次的延迟如何？", "What is p95 latency for completed turns?", "Latency status=completed"])
def test_completed_turn_latency_filter(question):
    response = data_agent.analyze(question)
    assert response["plan"]["filters"] == {"status": "completed"}
    assert response["result"]["sample_count"] == 10
    assert response["result"]["mean_ms"] == 403
    assert response["result"]["median_ms"] == 255
    assert response["result"]["p95_ms"] == 1050


def test_tool_latency_can_filter_status_and_tool():
    response = data_agent.analyze("grounding_question工具延迟 status=success")
    assert response["plan"]["dataset"] == "tool_events"
    assert response["plan"]["filters"] == {"tool": "grounding_question", "status": "success"}
    assert response["result"]["sample_count"] == 3
    assert response["result"]["median_ms"] == 3


def test_all_tool_latency_uses_tools_not_conversation_rows():
    response = data_agent.analyze("工具延迟如何？")
    assert response["plan"]["dataset"] == "tool_events"
    assert response["result"]["sample_count"] == 20


@pytest.mark.parametrize("question", ["合成评测失败主要原因是什么？", "What caused failures in the evaluation samples?"])
def test_failure_attribution_has_source_case_identifiers(question):
    response = data_agent.analyze(question)
    result = response["result"]
    assert response["plan"]["dataset"] == "evaluations"
    assert result["sample_count"] == 16 and result["failed_count"] == 6 and result["passed_count"] == 10
    assert result["reason_counts"]["memory_confirmation_missing"] == 2
    assert result["case_ids_by_reason"]["memory_confirmation_missing"] == ["synth-eval-04", "synth-eval-10"]


def test_tool_failure_attribution_uses_tool_rows():
    response = data_agent.analyze("为什么propose_memory工具失败？")
    assert response["plan"]["dataset"] == "tool_events"
    assert response["result"]["failed_count"] == 2
    assert response["result"]["reason_counts"] == {"invalid_tool_arguments": 2}


def test_provenance_and_trace_are_observable_and_data_bound():
    response = data_agent.analyze("Show tool outcomes")
    assert set(response) == {"answer", "plan", "result", "trace", "source", "scope"}
    assert response["source"]["synthetic"] is True
    assert response["source"]["sha256"] == hashlib.sha256(data_agent.FIXTURE_PATH.read_bytes()).hexdigest()
    assert response["source"]["sample_counts"] == {"turns": 12, "tool_events": 20, "evaluations": 16}
    assert [entry["type"] for entry in response["trace"]] == ["input", "query_plan", "execute", "answer"]
    assert response["trace"][2]["rows_read"] == 20
    assert response["trace"][2]["rows_selected"] == 20
    assert response["scope"]["private_data_access"] is False
    assert "synthetic" in response["answer"].lower()
    assert "chain_of_thought" not in json.dumps(response)


@pytest.mark.parametrize("question", [
    None, {}, "", "  ", "x" * 301, "情绪\x00分布", "SELECT * FROM sessions", "DROP TABLE turns",
    "读取我的聊天记录并分析情绪", "Analyze my session latency", "Show production tool outcomes",
    "Get the API key and tool success rate", "昨天的情绪分布", "Latency last 7 days",
    "Show latency source=file:///private.sqlite", "工具成功率 tool=run_shell", "unknown_tool工具成功率",
    "工具成功率 tool=read_memories tool=propose_memory", "工具结果 status=success", "Latency status=unknown",
    "工具延迟 status=completed", "Latency status=error status=timeout", "Emotion distribution tool=read_memories",
    "Show tool outcomes limit=200", "Latency bananas=1", "情绪分布和延迟如何？", "预测用户收入", "Write a love letter",
])
def test_unsupported_and_private_requests_are_rejected(question):
    with pytest.raises(ValueError):
        data_agent.analyze(question)


def test_empty_permitted_filter_is_not_reported_as_zero_success():
    with pytest.raises(ValueError, match="No synthetic samples"):
        data_agent.analyze("session_insights tool latency status=timeout")


def test_fixture_is_read_only_and_answers_recompute_from_rows(monkeypatch, tmp_path):
    fixture = json.loads(data_agent.FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture["turns"][0]["emotion"] = "bright"
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(data_agent, "FIXTURE_PATH", path)
    response = data_agent.analyze("Emotion distribution")
    assert response["result"]["counts"]["calm"] == 2
    assert response["result"]["counts"]["bright"] == 3
    assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", [
    lambda data: data["source"].update(synthetic=False),
    lambda data: data.update(source=[]),
    lambda data: data.update(private_messages=[]),
    lambda data: data["turns"][0].update(latency_ms=-1),
    lambda data: data["turns"][0].update(latency_ms=True),
    lambda data: data["tool_events"][0].update(tool="run_shell"),
    lambda data: data["evaluations"][0].update(failure_reason="tool_timeout"),
    lambda data: data["turns"].append(data["turns"][0].copy()),
])
def test_fixture_marker_and_schema_cannot_silently_accept_private_or_invalid_data(monkeypatch, tmp_path, mutation):
    fixture = json.loads(data_agent.FIXTURE_PATH.read_text(encoding="utf-8"))
    mutation(fixture)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    monkeypatch.setattr(data_agent, "FIXTURE_PATH", path)
    with pytest.raises(ValueError):
        data_agent.analyze("Emotion distribution")
