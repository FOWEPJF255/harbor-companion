"""Reproduce synthetic application contracts; never score companion semantics here."""
import argparse
import asyncio
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "server") not in sys.path:
    sys.path.insert(0, str(ROOT / "server"))

from fastapi.testclient import TestClient
from harbor.config import Settings
from harbor.main import create_app
from harbor.providers import Completion, ProviderError

CASES_PATH = ROOT / "eval" / "framework-cases.json"


def load_cases():
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


class ContextProvider:
    """Capture message assembly; the fixed reply makes no semantic understanding claim."""
    name = "synthetic_context"

    def __init__(self):
        self.inputs = []

    async def complete(self, messages, tools):
        self.inputs.append(copy.deepcopy(messages))
        return Completion(content="Synthetic context fixture reply; no language-quality score.")


class ControlledToolProvider:
    """Request one injected tool call and acknowledge its actual observation."""
    name = "synthetic_tool"

    def __init__(self, name, arguments=None):
        self.tool_name = name
        self.arguments = arguments or {}
        self.observations = []

    async def complete(self, messages, tools):
        if messages[-1]["role"] == "tool":
            observation = json.loads(messages[-1]["content"])
            self.observations.append(observation)
            if "error" in observation:
                return Completion(content=f"Synthetic tool error observed: {observation['error']}. No successful data result is claimed.")
            return Completion(content="Synthetic tool observation received; fixture execution only.")
        return Completion(calls=[{"id": "acceptance-tool-call", "name": self.tool_name, "arguments": self.arguments}])


class BrokenProvider:
    name = "synthetic_failure"

    def __init__(self):
        self.calls = 0

    async def complete(self, messages, tools):
        self.calls += 1
        raise ProviderError("Synthetic injected provider failure; not a real API request.")


class SlowProvider:
    name = "synthetic_timeout"

    async def complete(self, messages, tools):
        await asyncio.sleep(0.1)
        return Completion(content="This completion should time out before it is returned.")


class LoopProvider:
    name = "synthetic_loop"

    async def complete(self, messages, tools):
        return Completion(calls=[{"id": "acceptance-loop", "name": "read_memories", "arguments": {}}])


class BurstProvider:
    name = "synthetic_burst"

    async def complete(self, messages, tools):
        return Completion(calls=[{"id": f"acceptance-burst-{index}", "name": "read_memories", "arguments": {}} for index in range(5)])


class CaseContext:
    def __init__(self, case, directory):
        self.case = case
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        scenario = case["scenario"]
        self.provider = None
        options = {"db_path": str(self.directory / "acceptance.sqlite3")}
        if scenario in {"context_history", "context_window", "persona_snapshot", "history_isolation"}:
            self.provider = ContextProvider()
        elif scenario in {"tool_failure", "tool_timeout"}:
            self.provider = ControlledToolProvider("session_insights")
            if scenario == "tool_timeout":
                options["tool_timeout"] = 0.01
        elif scenario == "invalid_arguments":
            self.provider = ControlledToolProvider("propose_memory", {"content": "Synthetic preference", "unexpected": True})
        elif scenario == "unknown_tool":
            self.provider = ControlledToolProvider("run_shell", {"command": "not executed"})
        elif scenario == "timeout":
            self.provider = SlowProvider()
            options["timeout"] = 0.01
        elif scenario == "step_budget":
            self.provider = LoopProvider()
            options["max_steps"] = 2
        elif scenario == "burst_budget":
            self.provider = BurstProvider()
        elif scenario in {"provider_failure", "minor_boundary"}:
            self.provider = BrokenProvider()
        self.settings = Settings(**options)
        self.app = create_app(self.settings, self.provider)
        self.store = self.app.state.store
        self.client = TestClient(self.app)
        self.output = []
        self.checks = []
        self.counter = 0
        self.mode = self.provider.name if self.provider else "mock"

    def request(self, method, path, payload=None, expected_status=200):
        response = self.client.request(method, path, json=payload)
        body = response.json()
        self.output.append({"operation": f"{method} {path}", "input": payload, "status": response.status_code, "output": body})
        if expected_status is not None:
            self.check(response.status_code == expected_status,
                       f"Expected HTTP {expected_status} for {method} {path}; received {response.status_code}.")
        if isinstance(body, dict) and body.get("provider") == "policy":
            self.mode = "policy"
        return response.status_code, body

    def new(self, source=None, character="nova", language=None):
        body = {"adult_confirmed": True, "mode": "friend", "character_id": character,
                "language": language or self.case.get("language", "zh")}
        if source:
            body["memory_from_session_id"] = source
        return self.request("POST", "/api/sessions", body)[1]["id"]

    def chat(self, sid, text, expected_status=200, request_id=None):
        self.counter += 1
        body = {"message": text, "request_id": request_id or f"acceptance-request-{self.counter:04d}",
                "language": self.case.get("language", "zh")}
        return self.request("POST", f"/api/sessions/{sid}/chat", body, expected_status)[1]

    def read(self, sid):
        return self.request("GET", f"/api/sessions/{sid}")[1]

    def approve(self, sid, mid):
        return self.request("POST", f"/api/sessions/{sid}/memories/{mid}/approve")[1]

    def add(self, sid, text):
        return self.request("POST", f"/api/sessions/{sid}/memories", {"content": text})[1]["id"]

    def check(self, passed, statement):
        self.checks.append({"assertion": statement, "passed": bool(passed)})
        if not passed:
            raise AssertionError(statement)


def tool_entry(result, name):
    return next((entry for entry in result.get("trace", []) if entry.get("type") == "tool" and entry.get("name") == name), None)


def check_tool(context, result, name, expected_error=None):
    entry = tool_entry(result, name)
    context.check(entry is not None, f"A trace exists for tool {name}.")
    context.check("input" in entry and "observation" in entry, "Tool trace exposes its input and observation, without requesting private reasoning.")
    if expected_error:
        context.check(entry["observation"].get("error") == expected_error, f"The tool observation reports {expected_error}.")
        context.check(entry["status"] != "ok", "A failed or denied tool is not labeled successful.")
    else:
        context.check(entry["status"] == "ok", f"Tool {name} completed successfully.")
    return entry["observation"]


def memory_terms(language):
    if language == "en":
        return "I prefer tea", "Remember: I prefer tea", "What do you remember?"
    return "我喜欢海边散步", "记住：我喜欢海边散步", "你记得什么？"


def propose(context, sid):
    fact, request, _ = memory_terms(context.case.get("language", "zh"))
    result = context.chat(sid, request)
    check_tool(context, result, "propose_memory")
    memories = context.read(sid)["memories"]
    pending = next((item for item in memories if item["status"] == "pending" and item["content"] == fact), None)
    context.check(pending is not None, "The synthetic preference is available as a process-local pending proposal.")
    return pending["id"], fact


def check_no_half_turn(context, sid, result):
    context.check(bool(result.get("failure_reason")), "An explicit failure_reason accompanies the failed request.")
    context.check(bool(result.get("trace")), "The failed request includes an observable execution trace.")
    context.check(any(entry.get("type") == "failure" for entry in result["trace"]), "The execution trace records a failure event.")
    context.check(result.get("provider") != "mock", "No mock fallback replaces the injected failure.")
    context.check("reply" not in result, "The failed request does not return a successful reply field.")
    state = context.read(sid)
    context.check(state["messages"] == [], "A failed request saves no partial user/assistant pair.")
    context.check(state["insights"]["turn_count"] == 0, "A failed request saves no completed turn.")


def run_scenario(context):
    case, scenario = context.case, context.case["scenario"]
    language = case.get("language", "zh")
    if scenario == "adult_gate":
        context.request("POST", "/api/sessions", {"adult_confirmed": False}, 422)
        return
    if scenario.startswith("data_"):
        before = context.store.overview()
        expected = 422 if scenario == "data_reject" else 200
        _, result = context.request("POST", "/api/data-agent", {"question": case["input"]}, expected)
        context.mode = "offline deterministic DataAgent / synthetic data"
        context.check(context.store.overview() == before, "Data analysis does not mutate application telemetry, private memories, or conversations.")
        if scenario == "data_reject":
            context.check("result" not in result, "Rejected instructions yield no fabricated aggregate result.")
            return
        raw = (ROOT / "eval" / "synthetic-analytics.json").read_bytes()
        fixture = json.loads(raw)
        context.check(result["source"].get("synthetic") is True, "The answer identifies its source as synthetic.")
        context.check(result["source"]["sha256"] == hashlib.sha256(raw).hexdigest(), "The source digest matches the public fixture actually read.")
        context.check(result["scope"].get("private_data_access") is False, "The source contract denies private-data access.")
        context.check(result["scope"].get("access") == "read_only", "The declared access scope is read-only.")
        context.check(any(row.get("type") == "execute" and row.get("status") == "completed" for row in result["trace"]), "The trace includes an actual completed aggregate operation.")
        context.check(bool(result["answer"]), "A non-empty source-bound answer is returned.")
        actual = result["result"]
        if scenario == "data_distribution":
            counts = Counter(row["emotion"] for row in fixture["turns"])
            context.check(result["plan"]["id"] == "emotion_distribution", "The planner selects emotion_distribution.")
            context.check(actual["sample_count"] == len(fixture["turns"]), "The distribution denominator equals the public turn fixture size.")
            context.check(all(actual["counts"].get(name, 0) == count for name, count in counts.items()), "Every observed emotion count matches an independent fixture count.")
        elif scenario == "data_rate":
            rows = fixture["tool_events"]
            successes = sum(row["status"] == "success" for row in rows)
            context.check(result["plan"]["id"] == "tool_outcomes", "The planner selects tool_outcomes.")
            context.check(actual["sample_count"] == len(rows) and actual["counts"]["success"] == successes, "The numerator and denominator independently match synthetic tool events.")
            context.check(actual["success_share_percent"] == round(successes / len(rows) * 100, 2), "The share is computed from all selected synthetic attempts.")
        elif scenario == "data_latency":
            durations = sorted(row["latency_ms"] for row in fixture["turns"])
            context.check(result["plan"]["id"] == "latency_summary", "The planner selects latency_summary.")
            context.check(actual["unit"] == "ms", "Latency values report milliseconds.")
            context.check(actual["mean_ms"] == round(statistics.mean(durations), 2), "Mean latency matches independently computed fixture values.")
            context.check(actual["median_ms"] == round(statistics.median(durations), 2), "Median latency matches independently computed fixture values.")
            context.check(actual["p95_ms"] == durations[math.ceil(0.95 * len(durations)) - 1], "p95 follows the documented nearest-rank method.")
        return

    sid = context.new()
    if scenario == "identity":
        result = context.chat(sid, case["input"])
        context.check(result["provider"] == "mock", "The identity fixture is explicitly reported as mock.")
        context.check("AI" in result["reply"], "The fixture discloses AI identity.")
        terms = ["fixed", "mock", "demo"] if language == "en" else ["固定", "演示", "模拟"]
        context.check(any(term in result["reply"].lower() for term in terms), "The fixture discloses its deterministic demonstration mode.")
        if language == "en":
            context.check(not any('\u3400' <= char <= '\u9fff' for char in result["reply"]), "The English identity fixture does not accidentally use the Chinese fixed template.")
    elif scenario == "persona_snapshot":
        original = context.store.session(sid)
        character = context.store.character("nova")
        edited = {key: character[key] for key in ("name", "tagline", "description", "system_prompt", "greeting", "accent_color", "avatar_style", "enabled")}
        edited.update(name="Terra", system_prompt="Synthetic changed character instructions.")
        context.store.save_character(edited, "nova")
        context.chat(sid, "Inspect the original character context.")
        old_prompt = context.provider.inputs[-1][0]["content"]
        fresh = context.new()
        context.chat(fresh, "Inspect the updated character context.")
        new_prompt = context.provider.inputs[-1][0]["content"]
        context.output.append({"original_context": old_prompt, "new_context": new_prompt})
        context.check(f"Character name: {original['character_name']}" in old_prompt, "The old session keeps its original character name.")
        context.check(original["character_prompt"] in old_prompt, "The old session keeps its original character instructions.")
        context.check("Character name: Terra" in new_prompt and edited["system_prompt"] in new_prompt, "The new session uses the published character revision.")
        context.check(context.store.session(fresh)["character_revision"] > original["character_revision"], "The new session captures an incremented revision.")
    elif scenario == "context_history":
        for message in case["input"]:
            context.chat(sid, message)
        messages = context.provider.inputs[-1]
        context.output.append({"provider_context": messages})
        users = [row["content"] for row in messages if row["role"] == "user"]
        context.check(users == case["input"], "All three synthetic user messages, including the correction, reach the final provider call in order.")
        context.check(sum(row["role"] == "assistant" for row in messages) == 2, "The provider input includes the two preceding assistant turns.")
        context.check(f"Response language: {language}" in messages[0]["content"], "The selected response language reaches the system configuration.")
    elif scenario == "context_window":
        for index in range(8):
            context.chat(sid, f"synthetic-context-turn-{index:02d}")
        context.chat(sid, "Inspect the final bounded window.")
        messages = context.provider.inputs[-1]
        context.output.append({"provider_context": messages})
        context.check(len(messages) <= 14, "The model input uses at most 12 history messages plus system and current user messages.")
        context.check(not any(row["content"] == "synthetic-context-turn-00" for row in messages), "The oldest synthetic turn is outside the raw recent-message window.")
        context.check("synthetic-context-turn-00" in messages[0]["content"], "An attributed older excerpt remains available in the bounded session summary.")
        context.check(any(row["content"] == "synthetic-context-turn-07" for row in messages), "The latest previous user turn is retained.")
    elif scenario in {"pending_not_persisted", "pending_not_recalled", "approved_recall", "shared_approved", "shared_pending"}:
        mid, fact = propose(context, sid)
        if scenario == "pending_not_persisted":
            with context.store.connect() as db:
                durable = db.execute("SELECT COUNT(*) FROM approved_memories").fetchone()[0]
                legacy = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            context.output.append({"durable_approved_memory_count": durable, "legacy_memory_row_count": legacy})
            context.check(durable == 0 and legacy == 0, "Before consent, neither the durable approved table nor the legacy memory table contains a proposal.")
        if scenario in {"approved_recall", "shared_approved"}:
            context.approve(sid, mid)
        target = context.new(source=sid) if scenario in {"shared_approved", "shared_pending"} else sid
        result = context.chat(target, memory_terms(language)[2])
        observation = check_tool(context, result, "read_memories")
        facts = [item["content"] for item in observation["memories"]]
        approved_expected = scenario in {"approved_recall", "shared_approved"}
        context.check((fact in facts) == approved_expected, "Memory-tool output contains the synthetic fact only after explicit approval and allowed sharing.")
        if scenario == "shared_pending":
            context.check(context.read(target)["memories"] == [], "A's pending proposal does not appear in the explicitly linked B session.")
            context.check(any(item["id"] == mid for item in context.read(sid)["memories"]), "The pending proposal remains visible only in its source session.")
    elif scenario == "correct_approved":
        mid = context.add(sid, "我喜欢咖啡")
        context.request("PUT", f"/api/sessions/{sid}/memories/{mid}", {"content": "我喜欢茶"})
        result = context.chat(sid, "你记得什么？")
        facts = [item["content"] for item in check_tool(context, result, "read_memories")["memories"]]
        context.check("我喜欢茶" in facts and "我喜欢咖啡" not in facts, "The approved memory tool uses the corrected value instead of the old value.")
        record = context.read(sid)["memories"][0]
        context.check(record["revision"] == 2, "The approved correction increments the memory revision.")
    elif scenario == "delete_approved":
        mid = context.add(sid, "I prefer tea")
        context.request("POST", f"/api/sessions/{sid}/memories/{mid}/delete")
        result = context.chat(sid, "What do you remember?")
        context.check(check_tool(context, result, "read_memories")["memories"] == [], "The memory tool returns no fact after explicit deletion.")
    elif scenario == "restart_memory":
        context.add(sid, "已确认的合成偏好：茶")
        propose(context, sid)
        reopened = create_app(context.settings)
        with TestClient(reopened) as client:
            response = client.get(f"/api/sessions/{sid}")
            context.check(response.status_code == 200, "The session survives an app and Store restart.")
            state = response.json()
        context.output.append({"restarted_state": state})
        context.check([row["content"] for row in state["memories"]] == ["已确认的合成偏好：茶"], "Restart preserves confirmed memory and discards the process-only pending proposal.")
        context.check(all(row["status"] == "approved" for row in state["memories"]), "No pending proposal is restored from SQLite.")
    elif scenario == "shared_lifecycle":
        fact = "Synthetic shared preference: tea"
        context.add(sid, fact)
        linked = context.new(source=sid)
        context.request("DELETE", f"/api/sessions/{sid}")
        context.check(any(row["content"] == fact for row in context.read(linked)["memories"]), "Deleting one linked session preserves the approved pool for its other session.")
        context.request("DELETE", f"/api/sessions/{linked}")
        with context.store.connect() as db:
            remaining = db.execute("SELECT COUNT(*) FROM approved_memories").fetchone()[0]
            spaces = db.execute("SELECT COUNT(*) FROM memory_spaces").fetchone()[0]
        context.output.append({"approved_memory_count_after_last_delete": remaining, "memory_space_count_after_last_delete": spaces})
        context.check(remaining == 0 and spaces == 0, "Deleting the final linked session removes the orphan pool and its approved memory.")
    elif scenario == "emotion":
        result = context.chat(sid, case["input"])
        context.check(result["emotion"] == case["emotion"], f"The keyword hook returns {case['emotion']}.")
        context.check(bool(result["reply"].strip()), "A non-empty deterministic fixture response is returned.")
        if "tool" in case:
            check_tool(context, result, case["tool"])
    elif scenario in {"tool_failure", "tool_timeout"}:
        original = context.store.insights
        if scenario == "tool_failure":
            def injected(_sid):
                raise RuntimeError("synthetic-private-error-marker-993")
            expected_error = "tool_failed"
        else:
            def injected(_sid):
                time.sleep(0.04)
                return original(_sid)
            expected_error = "tool_timeout"
        context.store.insights = injected
        try:
            result = context.chat(sid, "Inspect synthetic session aggregates.")
        finally:
            context.store.insights = original
        check_tool(context, result, "session_insights", expected_error)
        context.check(context.provider.observations[-1]["error"] == expected_error, "The provider receives the actual failure observation.")
        context.check("synthetic-private-error-marker-993" not in json.dumps(result), "Raw exception details are not leaked in the reply or trace.")
        context.check(expected_error in result["reply"], "The controlled fixture reply explicitly acknowledges the tool failure instead of claiming data.")
    elif scenario in {"invalid_arguments", "unknown_tool"}:
        result = context.chat(sid, "Inspect the injected synthetic tool request.")
        name = "propose_memory" if scenario == "invalid_arguments" else "run_shell"
        error = "invalid_arguments" if scenario == "invalid_arguments" else "tool_not_allowed"
        check_tool(context, result, name, error)
        context.check(context.provider.observations[-1].get("error") == error, "The denied action reaches the controlled provider as an error observation.")
        context.check(context.read(sid)["memories"] == [], "The denied action does not create a memory.")
    elif scenario in {"timeout", "step_budget", "burst_budget", "provider_failure"}:
        result = context.chat(sid, "hello", expected_status=502)
        check_no_half_turn(context, sid, result)
        if scenario == "timeout":
            context.check(result["failure_reason"] == "run_timeout", "The timeout is classified as run_timeout.")
        if scenario == "step_budget":
            context.check(sum(entry.get("type") == "model" for entry in result["trace"]) == 2, "Exactly the configured two model steps execute before failure.")
        if scenario == "burst_budget":
            context.check(not any(entry.get("type") == "tool" for entry in result["trace"]), "The over-budget burst is rejected before any tool executes.")
    elif scenario == "cross_session_memory":
        mid = context.add(sid, "Synthetic unrelated preference: tea")
        other = context.new()
        context.request("POST", f"/api/sessions/{other}/memories/{mid}/approve", expected_status=404)
        context.request("PUT", f"/api/sessions/{other}/memories/{mid}", {"content": "Illegal replacement"}, 404)
        context.request("POST", f"/api/sessions/{other}/memories/{mid}/delete", expected_status=404)
        context.check(context.read(other)["memories"] == [], "The unrelated session has no approved or pending memory from A.")
        context.check(context.read(sid)["memories"][0]["content"] == "Synthetic unrelated preference: tea", "Forbidden operations do not alter A's approved value.")
    elif scenario == "history_isolation":
        context.chat(sid, "synthetic-private-coast-824")
        other = context.new()
        context.chat(other, "Inspect only this session's context.")
        messages = context.provider.inputs[-1]
        context.output.append({"isolated_provider_context": messages})
        context.check("synthetic-private-coast-824" not in json.dumps(messages), "A's unique synthetic history marker never reaches B's model input.")
    elif scenario in {"idempotency", "request_collision"}:
        first = context.chat(sid, "First synthetic message", request_id="acceptance-fixed")
        if scenario == "idempotency":
            second = context.chat(sid, "First synthetic message", request_id="acceptance-fixed")
            context.check(first["run_id"] == second["run_id"], "An identical request retry returns the same run ID.")
        else:
            context.chat(sid, "A different synthetic message", expected_status=409, request_id="acceptance-fixed")
        state = context.read(sid)
        context.check(len(state["messages"]) == 2 and state["insights"]["turn_count"] == 1, "Only the original completed message pair and turn are stored.")
    elif scenario == "minor_boundary":
        result = context.chat(sid, case["input"])
        context.check(result["provider"] == "policy" and context.provider.calls == 0, "The age policy runs without calling the unavailable synthetic provider.")
        context.check(any(entry.get("name") == "age_boundary" and entry.get("status") == "handled" for entry in result["trace"]), "The age-boundary handling is visible in the trace.")
    elif scenario == "legacy":
        if "memory" in case:
            context.add(sid, case["memory"])
        result = context.chat(sid, case["input"])
        if "contains" in case:
            context.check(case["contains"] in result["reply"], "The original deterministic fixture text marker is retained; this is not a semantic score.")
        if "tool" in case:
            check_tool(context, result, case["tool"])
        if "emotion" in case:
            context.check(result["emotion"] == case["emotion"], "The original keyword emotion-routing fixture is retained.")
        if "provider" in case:
            context.check(result["provider"] == case["provider"], "The original mock or policy provenance is retained.")
        if "proposal" in case:
            records = context.read(sid)["memories"]
            context.check(any(row["content"] == case["proposal"] and row["status"] == "pending" for row in records), "The original proposal is present in the transient pending queue.")
            context.check(context.store.memories(sid, "approved") == [], "The unconfirmed legacy fixture is not an approved memory.")
    else:
        raise AssertionError(f"Unsupported evaluator scenario: {scenario}")


def run_case(case, directory):
    started = time.perf_counter()
    context = None
    failure = None
    try:
        context = CaseContext(case, directory)
        with context.client:
            run_scenario(context)
    except Exception as issue:
        failure = {"type": type(issue).__name__, "reason": str(issue)[:1000]}
    return {
        "id": case["id"], "category": case["category"], "scenario": case["scenario"], "language": case.get("language", "zh"),
        "input": case["input"], "expected": case["expected"], "output": context.output if context else [],
        "execution_ms": round((time.perf_counter() - started) * 1000, 2), "mode": context.mode if context else "setup failed",
        "pass": failure is None, "passed": failure is None, "failure": failure,
        "checks": context.checks if context else [], "semantic_quality": "not evaluated",
    }


def build_report(cases=None):
    cases = load_cases() if cases is None else cases
    with tempfile.TemporaryDirectory(prefix="harbor-acceptance-") as directory:
        rows = [run_case(case, Path(directory) / case["id"]) for case in cases]
    category_counts = Counter(row["category"] for row in rows)
    return {"time": datetime.now(timezone.utc).isoformat(), "provider": "mock, policy, injected synthetic providers, offline DataAgent",
            "scope": "synthetic application contracts; no network model calls or private user conversations",
            "passed": sum(row["pass"] for row in rows), "total": len(rows), "category_counts": dict(sorted(category_counts.items())),
            "cases": rows, "semantic_quality": "pending real-model evaluation", "live_model_calls": 0}


def markdown_report(report):
    lines = ["# Synthetic framework acceptance report", "", f"Generated: {report['time']}", "",
             f"Result: **{report['passed']} / {report['total']} application-contract fixtures passed**.", "",
             "These are engineering-flow checks with deterministic/injected providers. They do not measure companionship, empathy, real model speed, or production reliability.", "",
             "| Case | Category | Mode | Execution ms | Result |", "|---|---|---|---:|---|"]
    for row in report["cases"]:
        lines.append(f"| {row['id']} | {row['category']} | {row['mode']} | {row['execution_ms']} | {'PASS' if row['pass'] else 'FAIL'} |")
    lines.extend(["", "## Case evidence", ""])
    for row in report["cases"]:
        lines.extend([f"### {row['id']}", "", f"Expected: {row['expected']}", "",
                      f"Result: {'PASS' if row['pass'] else 'FAIL'}; mode: {row['mode']}; execution: {row['execution_ms']} ms.", "",
                      "```json", json.dumps({key: row[key] for key in ("input", "output", "checks", "failure")}, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "framework-latest.json")
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown_report(report), encoding="utf-8")
    print(f"Synthetic application contracts: {report['passed']}/{report['total']} passed; live model calls: 0.")
    print(f"Detailed report: {args.output}")
    for row in report["cases"]:
        if not row["pass"]:
            print(f"FAIL {row['id']}: {row['failure']['type']}: {row['failure']['reason']}")
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
