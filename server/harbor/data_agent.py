"""Bounded natural-language planning over public synthetic fixtures, without SQL or an LLM."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "eval" / "synthetic-analytics.json"
SOURCE_ID = "harbor-synthetic-analytics-v1"
MAX_QUESTION_LENGTH = 300
MAX_ROWS = 100
TOOLS = frozenset({"read_memories", "propose_memory", "grounding_question", "session_insights"})
EMOTIONS = ("calm", "bright", "low", "overwhelmed")
TOOL_STATUSES = ("success", "error", "timeout", "denied")
TURN_STATUSES = ("completed", "error", "timeout")
REASONS = frozenset({"storage_unavailable", "invalid_tool_arguments", "tool_timeout", "session_not_found",
                     "context_drift", "memory_confirmation_missing", "unsafe_dependency_reply"})
SCENARIOS = frozenset({"persona", "context", "memory", "emotion", "tools", "boundaries"})

QUERY_PLANS = {
    "emotion_distribution": {"dataset": "turns", "group_by": "emotion", "measure": "count_and_share"},
    "tool_outcomes": {"dataset": "tool_events", "group_by": ["tool", "status"], "measure": "count_and_success_share"},
    "latency_summary": {"dataset": "turns", "group_by": None, "measure": "elapsed_ms_summary"},
    "failure_attribution": {"dataset": "evaluations", "group_by": "failure_reason", "measure": "failed_case_count"},
}

MOOD_ZH = {"calm": "平静", "bright": "轻快", "low": "低落", "overwhelmed": "压力"}
REASON_ZH = {"context_drift": "上下文漂移", "memory_confirmation_missing": "记忆确认缺失",
             "tool_timeout": "工具超时", "invalid_tool_arguments": "非法工具参数", "unsafe_dependency_reply": "不安全的依赖式回复"}


def _reject_unsupported(question):
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= MAX_QUESTION_LENGTH:
        raise ValueError("Question must be a nonblank string of at most 300 characters.")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", question):
        raise ValueError("Control characters are not permitted.")
    normalized = " ".join(question.strip().split())
    lowered = normalized.lower()
    if re.search(r"\b(select\b.+\bfrom|insert\s+into|delete\s+from|drop\s+(table|database)|"
                 r"alter\s+table|update\b.+\bset|union\s+select|pragma|sqlite_master|attach\s+database)\b", lowered):
        raise ValueError("SQL and arbitrary database operations are not supported.")
    if any(term in lowered for term in (
        "sql", "数据库", ".sqlite", "api key", "api_key", "密钥", "password", "密码", "token",
        "私有", "私人", "真实用户", "真实聊天", "生产数据", "我的聊天", "我的会话", "聊天原文", "聊天记录",
        "private", "production", "real user", "raw conversation", "my chat", "my session", "customer",
    )):
        raise ValueError("Only the public synthetic fixture is available; private data and credentials are inaccessible.")
    if re.search(r"昨天|今天|上周|本周|过去\d|最近\d|\b(yesterday|today|last week|this week|last \d|past \d)\b", lowered):
        raise ValueError("The synthetic fixture has no calendar window; time-range questions are unsupported.")
    if re.search(r"https?://|file://|[a-z]:\\|\.\./", lowered):
        raise ValueError("Custom data sources and file paths are not supported.")
    return normalized


def _plan(question):
    lowered = question.lower()
    mentioned_tools = {tool for tool in TOOLS if re.search(r"(?<![a-z0-9_])" + re.escape(tool) + r"(?![a-z0-9_])", lowered)}
    tool_scope = bool(re.search(r"工具|\btools?\b", lowered) or mentioned_tools)
    evaluation_scope = bool(re.search(r"评测|评估|\beval\w*\b", lowered))
    latency = bool(re.search(r"延迟|耗时|响应时间|\blatency\b|\blatencies\b|\bp50\b|\bp95\b|\bmedian\b|\bpercentile\b", lowered))
    emotions = bool(re.search(r"情绪|情感分布|\bemotions?\b|\bmoods?\b", lowered))
    failures = bool(re.search(r"失败归因|失败原因|评测失败|失败评测|为什么.*失败|\bfailure (attribution|reasons?)\b|\bwhy\b.+\bfail|\beval\w*\b.+\bfail|\bfail\w*\b.+\beval", lowered))
    tool_outcomes = tool_scope and bool(re.search(r"成功|失败|超时|结果|分布|\bsuccess\b|\bfail\w*\b|\btimeouts?\b|\boutcomes?\b|\bdistribution\b", lowered)) and not latency and not failures
    choices = [name for name, selected in (("emotion_distribution", emotions), ("latency_summary", latency),
               ("failure_attribution", failures), ("tool_outcomes", tool_outcomes)) if selected]
    if len(choices) != 1:
        raise ValueError("Ask one supported question: emotion distribution, tool outcomes, latency, or evaluation failure reasons.")
    plan_id = choices[0]
    dataset = QUERY_PLANS[plan_id]["dataset"]
    if plan_id == "latency_summary" and tool_scope or plan_id == "failure_attribution" and tool_scope and not evaluation_scope:
        dataset = "tool_events"
    tools = mentioned_tools
    explicit = re.findall(r"\btool\s*[:=]\s*([a-z0-9_-]+)", lowered)
    if any(name not in TOOLS for name in explicit):
        raise ValueError("Unknown tool filter.")
    tools.update(explicit)
    if len(tools) > 1:
        raise ValueError("At most one tool filter is permitted.")
    filters = {}
    if tools:
        if dataset != "tool_events":
            raise ValueError("A tool filter is only valid for tool-event analysis.")
        filters["tool"] = next(iter(tools))
    status_values = re.findall(r"\bstatus\s*[:=]\s*([a-z_-]+)", lowered)
    if len(status_values) > 1:
        raise ValueError("At most one status filter is permitted.")
    status = status_values[0] if status_values else None
    if status:
        allowed = TOOL_STATUSES if dataset == "tool_events" else TURN_STATUSES
        if plan_id != "latency_summary" or status not in allowed:
            raise ValueError("A valid status filter is only available for the latency plan.")
        filters["status"] = status
    if re.search(r"已完成|成功轮次|\bcompleted\b|\bsuccessful turns\b", lowered):
        if plan_id != "latency_summary" or dataset != "turns" or (status and status != "completed"):
            raise ValueError("Completed-turn filtering only applies to turn latency.")
        filters["status"] = "completed"
    if re.search(r"\b(?:limit|dataset|source|table|path|where|group_by)\s*[:=]", lowered):
        raise ValueError("Custom query parameters are not supported.")
    if any(name not in {"tool", "status"} for name in re.findall(r"\b([a-z_][a-z0-9_]*)\s*=", lowered)):
        raise ValueError("Unknown query parameter.")
    underscored = set(re.findall(r"(?<![a-z0-9_])([a-z][a-z0-9]*_[a-z0-9_]+)(?![a-z0-9_])", lowered))
    if underscored - TOOLS:
        raise ValueError("Unknown named tool or query identifier.")
    plan = {"id": plan_id, **QUERY_PLANS[plan_id], "dataset": dataset, "filters": filters}
    return plan


def _load_fixture():
    try:
        raw = FIXTURE_PATH.read_bytes()
        if len(raw) > 128_000:
            raise ValueError("Synthetic fixture exceeds its size limit.")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("The packaged synthetic fixture is unavailable or invalid.") from exc
    if (not isinstance(data, dict) or set(data) != {"schema_version", "source", "turns", "tool_events", "evaluations"}
        or data.get("schema_version") != 1 or not isinstance(data.get("source"), dict)
        or data["source"].get("id") != SOURCE_ID or data["source"].get("synthetic") is not True):
        raise ValueError("Only the explicitly synthetic analytics fixture is allowed.")
    layouts = {
        "turns": {"id", "session_id", "emotion", "status", "latency_ms"},
        "tool_events": {"id", "tool", "status", "latency_ms", "failure_reason"},
        "evaluations": {"id", "scenario", "status", "failure_reason"},
    }
    prefixes = {"turns": "synth-turn-", "tool_events": "synth-tool-", "evaluations": "synth-eval-"}
    for dataset, fields in layouts.items():
        rows = data.get(dataset)
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
            raise ValueError("Synthetic datasets must contain between 1 and 100 rows.")
        seen = set()
        for row in rows:
            if (not isinstance(row, dict) or set(row) != fields or not isinstance(row.get("id"), str)
                    or not re.fullmatch(re.escape(prefixes[dataset]) + r"\d{2,3}", row["id"]) or row["id"] in seen):
                raise ValueError("Invalid synthetic row schema or identifier.")
            seen.add(row["id"])
            if not isinstance(row.get("status"), str) or ("failure_reason" in row and
                    row["failure_reason"] is not None and not isinstance(row["failure_reason"], str)):
                raise ValueError("Invalid synthetic status or failure reason.")
            if "latency_ms" in row:
                duration = row["latency_ms"]
                if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 <= duration <= 120_000:
                    raise ValueError("Latency must be a finite number between 0 and 120000 ms.")
            if dataset == "turns":
                if (not isinstance(row["emotion"], str) or row["emotion"] not in EMOTIONS or row["status"] not in TURN_STATUSES
                        or not isinstance(row["session_id"], str) or not re.fullmatch(r"synth-session-\d{2,3}", row["session_id"])):
                    raise ValueError("Invalid synthetic turn fields.")
            elif dataset == "tool_events":
                if not isinstance(row["tool"], str) or row["tool"] not in TOOLS or row["status"] not in TOOL_STATUSES:
                    raise ValueError("Invalid synthetic tool fields.")
                if (row["status"] == "success") != (row["failure_reason"] is None):
                    raise ValueError("Synthetic tool success and failure-reason fields disagree.")
                if row["failure_reason"] is not None and row["failure_reason"] not in REASONS:
                    raise ValueError("Unknown synthetic failure reason.")
            else:
                if not isinstance(row["scenario"], str) or row["scenario"] not in SCENARIOS or row["status"] not in {"pass", "fail"}:
                    raise ValueError("Invalid synthetic evaluation fields.")
                if (row["status"] == "pass") != (row["failure_reason"] is None):
                    raise ValueError("Synthetic evaluation status and failure-reason fields disagree.")
                if row["failure_reason"] is not None and row["failure_reason"] not in REASONS:
                    raise ValueError("Unknown synthetic failure reason.")
    return data, hashlib.sha256(raw).hexdigest()


def _execute(data, plan):
    rows = data[plan["dataset"]]
    selected = [row for row in rows if all(row.get(key) == value for key, value in plan["filters"].items())]
    if not selected:
        raise ValueError("No synthetic samples match the permitted filter.")
    count = len(selected)
    if plan["id"] == "emotion_distribution":
        counts = Counter(row["emotion"] for row in selected)
        result = {"sample_count": count, "counts": {name: counts[name] for name in EMOTIONS},
                  "shares_percent": {name: round(counts[name] / count * 100, 2) for name in EMOTIONS},
                  "label_method": "hand-assigned synthetic emotion tags; not emotion recognition or diagnosis"}
    elif plan["id"] == "tool_outcomes":
        counts = Counter(row["status"] for row in selected)
        by_tool = {}
        for name in sorted({row["tool"] for row in selected}):
            attempts = [row for row in selected if row["tool"] == name]
            outcomes = Counter(row["status"] for row in attempts)
            by_tool[name] = {"attempts": len(attempts), "counts": {status: outcomes[status] for status in TOOL_STATUSES},
                             "success_share_percent": round(outcomes["success"] / len(attempts) * 100, 2)}
        result = {"sample_count": count, "counts": {status: counts[status] for status in TOOL_STATUSES},
                  "success_share_percent": round(counts["success"] / count * 100, 2), "by_tool": by_tool,
                  "denominator": "all selected synthetic attempts, including denied calls and timeouts"}
    elif plan["id"] == "latency_summary":
        durations = sorted(row["latency_ms"] for row in selected)
        result = {"sample_count": count, "unit": "ms", "min_ms": min(durations), "max_ms": max(durations),
                  "mean_ms": round(statistics.mean(durations), 2), "median_ms": round(statistics.median(durations), 2),
                  "p95_ms": durations[math.ceil(0.95 * count) - 1], "p95_method": "nearest rank: ceil(0.95 * n), one-based",
                  "status_counts": dict(sorted(Counter(row["status"] for row in selected).items())),
                  "measurement": "hand-authored elapsed-time fixtures, not measured model or device speed"}
    else:
        success_state = "success" if plan["dataset"] == "tool_events" else "pass"
        failed = [row for row in selected if row["status"] != success_state]
        counts = Counter(row["failure_reason"] for row in failed)
        result = {"sample_count": count, "failed_count": len(failed), "passed_count": count - len(failed),
                  "reason_counts": dict(sorted(counts.items())),
                  "case_ids_by_reason": {reason: [row["id"] for row in failed if row["failure_reason"] == reason] for reason in sorted(counts)},
                  "attribution_method": "explicit injected labels in synthetic evaluation fixtures; not inferred root causes"}
    return result, len(rows), count


def _answer(question, plan, result):
    chinese = bool(re.search(r"[\u3400-\u9fff]", question))
    prefix = "仅分析公开合成样本，不代表真实用户、模型质量或线上指标。" if chinese else "Public synthetic fixtures only; these are not real-user data, model-quality results, or production metrics. "
    if plan["id"] == "emotion_distribution":
        details = "; ".join(f"{MOOD_ZH[name] if chinese else name} {count}" for name, count in result["counts"].items())
        text = f"{result['sample_count']} 个合成对话轮次：{details}。情绪标签由样本手工指定。" if chinese else f"Across {result['sample_count']} synthetic turns: {details}. Emotion labels were assigned by the fixture author."
    elif plan["id"] == "tool_outcomes":
        counts = result["counts"]
        selection = plan["filters"].get("tool", "all allowlisted tools")
        text = (f"{selection} 的 {result['sample_count']} 次合成工具尝试：成功 {counts['success']}、错误 {counts['error']}、超时 {counts['timeout']}、拒绝 {counts['denied']}；成功占比 {result['success_share_percent']}%。分母包含所有这些结果。" if chinese else
                f"For {selection}, {result['sample_count']} synthetic attempts contain {counts['success']} successes, {counts['error']} errors, {counts['timeout']} timeouts, and {counts['denied']} denials. Success share is {result['success_share_percent']}%, with all selected attempts in the denominator.")
    elif plan["id"] == "latency_summary":
        selection = json.dumps(plan["filters"], ensure_ascii=False) if plan["filters"] else "all statuses"
        text = (f"{plan['dataset']}，筛选 {selection}：{result['sample_count']} 条合成耗时，均值 {result['mean_ms']} ms、中位数 {result['median_ms']} ms、p95 {result['p95_ms']} ms。p95 使用最近秩法；未筛选时包含失败和超时样本。" if chinese else
                f"For {plan['dataset']} ({selection}), {result['sample_count']} synthetic elapsed-time samples have mean {result['mean_ms']} ms, median {result['median_ms']} ms, and nearest-rank p95 {result['p95_ms']} ms. Unfiltered samples include failures and timeouts.")
    else:
        details = "; ".join(f"{REASON_ZH.get(reason, reason) if chinese else reason} {count}" for reason, count in result["reason_counts"].items())
        noun = "工具事件" if plan["dataset"] == "tool_events" else "评测"
        noun_en = "tool-event" if plan["dataset"] == "tool_events" else "evaluation"
        text = (f"{result['sample_count']} 个合成{noun}样本中预设非成功结果 {result['failed_count']} 个：{details}。这些是注入样本的标签归类，不能作为实际评测通过率或自动根因诊断。" if chinese else
                f"Among {result['sample_count']} synthetic {noun_en} fixtures, {result['failed_count']} have injected non-success outcomes: {details}. This groups predefined labels; it is not a measured evaluation pass rate or an automatic root-cause diagnosis.")
    return prefix + text


def analyze(question: str) -> dict:
    """Select and execute one allowlisted query; raise ValueError for unsupported requests."""
    normalized = _reject_unsupported(question)
    plan = _plan(normalized)
    data, digest = _load_fixture()
    result, rows_read, rows_selected = _execute(data, plan)
    answer = _answer(normalized, plan, result)
    source = {"id": SOURCE_ID, "path": "eval/synthetic-analytics.json", "synthetic": True, "sha256": digest,
              "sample_counts": {name: len(data[name]) for name in ("turns", "tool_events", "evaluations")},
              "origin": "hand-authored fixtures; never application telemetry or real-model evidence"}
    trace = [
        {"type": "input", "question": normalized, "status": "validated", "scope": "synthetic_only"},
        {"type": "query_plan", "name": plan["id"], "dataset": plan["dataset"], "filters": plan["filters"], "status": "allowlisted"},
        {"type": "execute", "operation": "read_filter_aggregate", "rows_read": rows_read, "rows_selected": rows_selected,
         "source_sha256": digest, "status": "completed"},
        {"type": "answer", "status": "data_bound", "result_fields": sorted(result)},
    ]
    return {"answer": answer, "plan": plan, "result": result, "trace": trace, "source": source,
            "scope": {"kind": "synthetic_only", "access": "read_only", "planner": "offline deterministic bilingual router",
                      "private_data_access": False, "real_model_quality": "not_evaluated"}}
