"""Expanded synthetic API contracts; semantic quality requires separate model review."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("harbor_acceptance_runner", ROOT / "scripts" / "evaluate.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
CASES = RUNNER.load_cases()


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_synthetic_application_contract(case, tmp_path):
    result = RUNNER.run_case(case, tmp_path)
    assert result["pass"], json.dumps({"id": result["id"], "failure": result["failure"], "checks": result["checks"],
                                      "output": result["output"]}, ensure_ascii=False, indent=2)
    assert result["output"], "Every successful fixture must expose actual execution evidence."
    assert result["checks"], "Every successful fixture must have explicit assertions."
    assert result["semantic_quality"] == "not evaluated"
    assert result["execution_ms"] >= 0


def test_acceptance_manifest_covers_required_groups():
    counts = {}
    for case in CASES:
        counts[case["category"]] = counts.get(case["category"], 0) + 1
        assert {"id", "scenario", "input", "expected", "language", "category"} <= case.keys()
    assert len(CASES) >= 30
    assert len({case["id"] for case in CASES}) == len(CASES)
    assert {case["language"] for case in CASES} == {"zh", "en"}
    assert counts.get("persona_context", 0) >= 6
    assert counts.get("memory", 0) >= 8
    assert counts.get("emotion_routing", 0) >= 4
    assert counts.get("tool_exception", 0) >= 5
    assert counts.get("boundary_isolation", 0) >= 4
    assert counts.get("data_agent", 0) >= 3
    assert counts.get("legacy_regression", 0) == 12
