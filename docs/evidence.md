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

## App/management iteration, 2026-10-09

- Shared client and separate lazy-loaded management UI: TypeScript/Vite production build completed.
- Python modules: syntax compilation completed. The existing automated tests/fixtures were not rerun for this iteration, and no new tests were added.
- Source review: client/backend contracts, old-session snapshots, access boundaries, review cleanup, and timeout behavior were reviewed. This is review evidence, not a test result.
- Browser preview: desktop layout, 390 × 844 mobile chat/navigation, settings, and administrator initialization were opened. No owner's administrator password was chosen on their behalf.
- Android: [manual cloud packaging](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37818826647) succeeded for commit `8576f10`; downloaded APK checksum matched the build output.
- Model API, remote backend hosting, real-model quality, physical-phone operation, iOS packaging, and store publication remain pending.

See [app delivery](app-delivery.md) for the artifact size, hash, download location, and precise scope.

## Offline acceptance iteration, v0.3, 2026-10-09

| Check | Observed result | Scope/source |
| --- | --- | --- |
| Final Python regression | 140 passed, 1 deprecation warning, 6.54 s | Original boundary tests plus acceptance, management, memory, upstream failure and DataAgent tests |
| Expanded independent evaluator | 50/50 passed; live model calls 0 | [50 synthetic cases](../eval/framework-cases.json), [recorded detailed report](evidence/framework-v0.3-2026-10-09.json) |
| Frontend compilation | TypeScript/Vite build succeeded | Chinese/English user UI, consent/correction, trace panels and synthetic analysis |
| Local browser walkthrough | Approval → explicitly shared new chat → recall → correction → changed recall | Synthetic preference only; no semantic-quality assertion |
| Mobile browser | 390 × 844 chat and data analysis opened; actual query/row-count trace visible | Browser breakpoint review, not physical Android evidence |

Reproduction and failure examples: [evaluation](evaluation.md). Review findings/repairs: [iteration record](iteration-2026-10-09-v0.3.md). Current limits/next work: [CURRENT](CURRENT.md).

The DataAgent fixture's hand-authored success/failure and latency values are separate from these actual test counts; do not report fixture numbers as observed application performance. The complete MVP remains in development until live-model conversation quality and device evidence are recorded.

Code snapshot: `398bfb0`. [GitHub framework checks](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37843051697) completed successfully for that commit (backend tests/evaluator and frontend build). This is separate from Android compilation and real-model/device evidence.

Android v0.3: [cloud build 37843054056](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37843054056) completed successfully for `398bfb0`. Downloaded `data/releases/Harbor-0.3.0-debug.apk` is 4,307,956 bytes; SHA-256 matches the build checksum. See [packaging record](app-delivery.md) for the hash and limits. This does not verify installation or a physical phone.
