"""Run synthetic framework fixtures without network access or semantic quality claims."""
import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from harbor.agent import Agent
from harbor.config import Settings
from harbor.providers import MockProvider
from harbor.store import Store

ROOT = Path(__file__).resolve().parents[1]


async def main():
    rows = []
    with tempfile.TemporaryDirectory() as d:
        store = Store(str(Path(d) / "eval.sqlite3"))
        engine = Agent(store, MockProvider(), Settings())
        for case in json.loads((ROOT / "eval/framework-cases.json").read_text(encoding="utf-8")):
            sid = store.create("friend")["id"]
            if "memory" in case:
                store.memory_add(sid, case["memory"])
            result = await engine.run(sid, case["input"])
            checks = []
            if "contains" in case:
                checks.append(case["contains"] in result["reply"])
            if "tool" in case:
                checks.append(any(t["name"] == case["tool"] and t["status"] == "ok" for t in result["trace"]))
            if "emotion" in case:
                checks.append(result["emotion"] == case["emotion"])
            if "provider" in case:
                checks.append(result["provider"] == case["provider"])
            if "proposal" in case:
                checks.append(case["proposal"] in result["proposals"])
                checks.append(store.memories(sid, "approved") == [])
            rows.append({"id": case["id"], "passed": all(checks)})
    report = {"time": datetime.now(timezone.utc).isoformat(), "provider": "mock + policy", "scope": "synthetic infrastructure fixtures",
              "passed": sum(r["passed"] for r in rows), "total": len(rows), "cases": rows, "semantic_quality": "pending"}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/framework-latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
