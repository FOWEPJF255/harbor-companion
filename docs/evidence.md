# Initial evidence

Date: 2026-10-09. Stage: local framework; model quality pending.

The initial boundary/fixture results below describe the original `4a4328c` framework milestone. They have not been rerun for the app/management extension. Current app packaging evidence is tracked separately in [app delivery](app-delivery.md).

## Local framework evidence

Environment: Windows, Python 3.14.3, Node.js 24.18.0. Recorded on 2026-10-09 in Asia/Shanghai.

| Check | Observed result | Scope |
|---|---|---|
| Backend boundary checks | 10 passed | Adult gate, memory confirmation and isolation, repeat request IDs, provider failure, loop budgets, tool allowlist, synthetic protocol round trip, and localhost guard |
| Framework evaluation | 12/12 synthetic cases passed | Deterministic mock + illustrative policy paths; semantic quality remains pending |
| Frontend build | TypeScript + Vite build completed | Production asset compilation; not throughput or user testing |
| Local browser walkthrough | Start, propose memory, approve, recall, and aggregate view opened | Synthetic preference only; no external account or private chat data |

Sources: [boundary checks](../tests/test_boundaries.py), [fixture set](../eval/framework-cases.json), [evaluation runner](../scripts/evaluate.py), and [recorded framework result](evidence/framework-2026-10-09.json).

Pytest used an isolated project-local base directory after the operating system denied access to an existing shared temporary directory. A Starlette TestClient deprecation warning remains; it did not fail the local run.

## Pending evidence

Do not claim live-model results or production behavior from these checks.

- API integration: synthetic transport only; no live API usage.
- Conversations and metrics: synthetic/local only.
- Public hosting: not deployed.
- Companion quality: pending real-model transcripts and human review.
