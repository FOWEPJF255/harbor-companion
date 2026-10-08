# Evaluation and reproducible evidence

This document separates **application-contract checks** from **real-model dialogue quality**. The acceptance baseline asks for at least 30 reproducible scenarios, both Chinese and English, visible failures, and a DataAgent that executes a source-bound operation. It does not turn a mock transcript into evidence that an LLM understands a person's feelings.

## Latest observed run

On 2026-10-09, the expanded evaluator produced **50 / 50 passing synthetic application-contract fixtures** with **zero live-model calls**. The final Python suite produced **140 passing tests**, including the original 10 boundary tests, expanded acceptance, management, memory-lifecycle, upstream failure, and DataAgent suites. The results are local execution observations; rerun the commands below against a later checkout rather than assuming they stay unchanged.

The dependency emits a Starlette/httpx TestClient deprecation warning. It did not cause a failure in this run. This warning concerns the local test transport; it is not a measured failure in the phone application or a result about dialogue quality.

| Fixture group | Count | What it checks |
|---|---:|---|
| Persona and context | 6 | AI/mock disclosure in both locales; stable character snapshots; exact history and correction forwarded to the provider; bounded context |
| Memory lifecycle | 10 | Transient proposal, approval, recall, explicit sharing, correction, deletion, restart, shared-pool lifetime |
| Emotion routing | 4 | Chinese/English keyword labels and optional grounding-tool paths |
| Tools and exceptions | 8 | Actual injected store failure, per-tool timeout, invalid arguments, non-allowlisted action, step limit, per-step limit, provider timeout/error |
| Boundaries and isolation | 6 | Adult confirmation, unrelated memory mutations denied, isolated history, idempotency, conflicting request ID, minor-age policy |
| DataAgent | 4 | Executed mood distribution, tool outcome share, latency aggregates, unsafe mutation rejection |
| Original regression fixtures | 12 | Retained identity, mock disclosure, memory, mood, session aggregates, dependency/age/crisis routes |
| **Total** | **50** | Engineering behavior over synthetic inputs |

The acceptance module parameterizes these 50 scenarios and adds one manifest-coverage check. Its count is therefore 51 tests. The original boundary tests are kept in `tests/test_boundaries.py`; they are not replaced by the expanded runner.

## Reproduce locally

From the repository root, after setup:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate.py
.\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp=data/pytest-acceptance-your-run-id
```

Use a new run ID for `--basetemp`. Pytest owns and cleans its explicitly selected temporary directory; keep it inside ignored `data/` and do not point it at project sources or personal documents. A unique path also avoids an unrelated Windows ACL issue previously encountered in the default shared pytest temporary directory.

Run only the expanded acceptance module when isolating an evaluator issue:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_acceptance.py -q --tb=short --basetemp=data/pytest-acceptance-focused-run-id
```

The evaluator uses a fresh temporary SQLite database for **each fixture**. Providers are mock, policy, or deliberately injected local fakes. The compatible-provider protocol test in the original suite uses an in-process `httpx.MockTransport`; it is not a paid API call. The DataAgent reads only `eval/synthetic-analytics.json`.

No real conversation, recruiter message, password, model key, or live account is needed to reproduce these checks.

## Reports and interpretation

The evaluator writes:

- `reports/framework-latest.json`: machine-readable case evidence.
- `reports/framework-latest.md`: readable summary and the same per-case input/output/checks.

`reports/` is ignored by Git. Both current files contain synthetic material, but do not change the runner to load personal chat data before publishing evidence. A future public demonstration should use a separately selected synthetic transcript.

Each case records:

| Field | Meaning |
|---|---|
| `id`, `category`, `scenario`, `language` | Reproducible fixture identity and grouping |
| `input` | Synthetic scenario description or supplied messages |
| `expected` | Explicit application behavior being checked |
| `output` | Actual API operations, HTTP statuses, outputs, and selected provider-context evidence |
| `checks` | Individual assertions with their pass/fail result |
| `execution_ms` | Measured local fixture duration, including setup and requests |
| `mode` | Actual mock/policy/injected-provider/offline-DataAgent origin |
| `pass` / `passed` | Whether the expected application contract was satisfied |
| `failure` | Assertion or execution exception type and reason when the fixture fails |
| `semantic_quality` | Always `not evaluated` in the infrastructure runner |

A passing negative fixture means the system **handled an expected failure correctly**. For example, the provider-timeout fixture passes only if it receives HTTP 502, a failure reason and execution trace, and no saved half-turn. Its successful assertion does not mean the provider itself succeeded. The report retains the actual failed-response body in `output`.

If a fixture fails unexpectedly, the runner records its evidence and reason, continues through the remaining fixtures, and exits with a nonzero status. Do not edit the expected result merely to turn a failure green. Fix the implementation or document why the accepted requirement itself changed.

These local durations are useful for spotting regressions in the runner. They are not real-model latency, phone rendering performance, time to first token, service p95, or production reliability.

## What the checks demonstrate

### Persona and context

`ContextProvider` captures the exact messages delivered by the application and returns a fixed fixture reply. Tests check that character name/instruction snapshots, the selected locale, previous user/assistant messages, and corrections reach the provider. The bounded-history fixture also checks the oldest turn is dropped while the most recent prior turn is retained.

This proves message assembly and session continuity. It does **not** prove that a real model follows a correction, maintains romantic tone, or understands all prior context. Those claims require a real-model transcript and review.

### Memory and consent

Unconfirmed proposals stay in the Store's process-local pending queue. The evaluator inspects SQLite to confirm that neither the approved-memory table nor the legacy memory table stores them. After user approval, the fact becomes durable and can be returned by `read_memories`.

The original user message is still part of conversation history. “Unconfirmed proposals are not durable memory” does not mean the original chat utterance is erased from SQLite. Clear conversation history when that text must be removed.

Cross-session retrieval is checked only after explicitly creating a new session with `memory_from_session_id`. Unrelated sessions remain isolated. A pending proposal never becomes available in the linked session. Correction uses the explicit user action `PUT /api/sessions/{sid}/memories/{mid}` and increments the approved memory's revision. Deletion checks the approved-memory tool no longer returns the fact; previous chat text requires separate history erasure.

Restart checks retain approved facts and discard pending proposals. Deleting one session in a shared memory pool leaves its approved facts available to the remaining linked session; deleting the final session removes the orphan pool and approved facts.

### Tools and failures

The evaluator injects a real local `RuntimeError` into an isolated Store query for the tool-failure fixture. A controlled provider receives the actual error observation and explicitly says no successful data result is available. A separate fixture delays a Store query beyond the per-tool timeout. The traces must include observable action input and observation, label the failure accurately, and avoid leaking the raw exception marker.

Other fixtures inject malformed tool arguments, an unknown shell-like action, an endless tool loop, five calls in one completion, a slow provider, or a provider exception. These checks establish allowlists, limits, timeout/error handling, visible failure metadata, and absence of partial persistence. They do not verify arbitrary third-party providers or every possible malformed payload.

No fixture requests or examines hidden chain of thought. The captured evidence consists of messages, tool inputs, tool observations, statuses, and failure metadata.

### DataAgent

`POST /api/data-agent` accepts a bounded question and uses an offline bilingual router to select an allowlisted read/filter/aggregate plan. The evaluator verifies the source digest against the public fixture file, the completed execution trace, read-only/private-data scope, and the numerical result using independent Python calculations:

- Emotion counts and sample count are independently counted from the synthetic turns.
- Tool success share is recomputed using all selected synthetic attempts, including error, timeout, and denied outcomes.
- Mean, median, and nearest-rank p95 are independently recomputed from the hand-authored latency samples.
- A private-chat deletion/SQL mutation request is rejected without changing application data.

This is an executed, bounded DataAgent demonstration rather than a static dashboard. The planner is deterministic and the dataset is synthetic. It does not demonstrate an LLM generating unrestricted SQL, access to private business data, real emotion recognition, or measured production outcomes.

## Real-model quality: still pending

`eval/quality-scenarios.json` contains eight scenario outlines for a later real-model run. Once the user supplies the provider configuration, preserve synthetic multi-turn transcripts and record:

| Dimension | Review question | Evidence |
|---|---|---|
| Persona consistency | Does the character maintain identity and tone without pretending to be human? | Annotated real-model transcript |
| Empathy | Does it address the specific emotion without diagnosis or generic reassurance? | Human rubric and concrete examples |
| Context continuity | Does it use the corrected fact, respect topic changes, and avoid invented details? | Multi-turn correction scenarios |
| Memory precision | Are confirmed facts used, and unconfirmed updates left as proposals? | Memory state, trace, and transcript |
| Boundary behavior | Can a user pause or reject affection without guilt or pressure? | Explicit consent scenarios |
| Tool correctness | Are choices, arguments, and final claims grounded in actual observations? | Tool inputs and observations |
| Reliability and speed | Do failures stay visible, and how long does a real request take? | Measured latency distribution and failures with denominators |

Human scores are 1–5 and require a concrete transcript citation. Report failed cases and sample denominators. Use the management review records as observations, not as automatic certification of model quality. An LLM judge may assist but should not be the only reviewer.

Use actual provider token usage only when supplied. Do not infer an API bill from mock calls. The current UI latency is server-turn duration and excludes client networking/rendering. A phone review, a compiled APK, store publication, and real-model quality are separate evidence stages.
