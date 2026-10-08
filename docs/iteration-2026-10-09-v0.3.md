# v0.3 offline iteration record

Date: 2026-10-09, Asia/Shanghai.

## Starting gaps

The v0.2 app had session-only memory and persisted unapproved pending rows. Its analytics were fixed current-session aggregates; the framework evaluator had 12 fixtures and incomplete per-case output. The user interface had no English switch. Those were source-observed gaps against the new acceptance baseline, not failed real-model measurements.

## Changes

- Migrated legacy approved facts into default-isolated memory spaces; logically removed legacy pending rows. Added explicitly shared new conversations, correction/revision, shared deletion and last-session orphan cleanup.
- Kept unapproved suggestions in expiring process memory and out of durable memory/turn payloads. Preserved the separate ordinary-dialogue boundary.
- Added validated tool inputs, actual observations/durations, sanitized failed-run traces, per-tool timeout handling and request-content collision checks.
- Implemented offline bilingual DataAgent plan selection and actual synthetic aggregation with source fingerprint, filter/row-count traces and safety rejection.
- Added user-app English/Chinese switching, correction forms, sharing consent, observable trace panels and mobile data analysis.
- Retained the original 12 cases and added 38 application scenarios. Added separate memory persistence, management, data arithmetic, and upstream failure regressions.

## Review findings and repairs

These defects were identified by source review during the iteration; no pre-fix pass/fail rate is asserted.

| Finding | Repair | Regression evidence |
| --- | --- | --- |
| Timed-out synchronous proposal worker could append to the run's list after timeout | Use a per-call copy and merge only a successfully completed, non-error observation | `test_timed_out_worker_cannot_publish_late_proposal` waits for the abandoned worker before commit |
| Non-object upstream message could escape as AttributeError/HTTP 500 | Validate message object before parsing completion fields | Null/list/string upstream fixtures return visible 502 without a half-turn |
| Shared pending approval could exceed the space's approved-memory cap | Recheck count in an immediate SQLite transaction for every approved insert | Shared-space limit case preserves the pending suggestion and rejects overflow |
| Legacy cache with no content hash could replay an unrelated message | Reject unverifiable old-ID replay and require a new request ID | Legacy null-hash fixture returns 409 without changing history |

## Actual verification

- Final local Python suite: **140 passed, one Starlette TestClient deprecation warning, 6.54 s**.
- Independent application-contract evaluator: **50/50 passed, live model calls 0**, detailed inputs/expectations/outputs/modes/times/failures recorded.
- TypeScript/Vite production build succeeded. Main JS: 282.39 kB, gzip 89.81 kB; compilation size is not page-load or backend latency.
- Browser: English switch; propose/approve; explicitly share a new conversation; recall; correct and recall changed content; 390 × 844 chat navigation; synthetic DataAgent answer and row-count/source execution trace opened.
- Screenshots are local ignored artifacts under `reports/`: mobile-chat-v0.3.jpg, mobile-data-v0.3.jpg, mobile-data-trace-v0.3.jpg.
- Automated deletion/isolation/timeout/provider-error tests used disposable synthetic databases. No owner's administrator password was chosen, and no real chat or credential entered the Git evidence.

Remaining: [CURRENT](CURRENT.md). Android compiler/artifact status is separately recorded in [app delivery](app-delivery.md). Real empathy, persona stability, romantic quality, actual phone behavior and hosting remain unverified.
