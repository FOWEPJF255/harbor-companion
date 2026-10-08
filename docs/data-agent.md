# Offline synthetic DataAgent

## What it does

`harbor.data_agent.analyze(question)` is a bounded natural-language analysis pipeline. It selects an allowlisted plan, reads a local synthetic fixture, applies validated filters, executes aggregation in Python, and produces an answer bound to the computed result. It needs no model key, SQL engine, session store, account data, or network connection.

This is an executable DataAgent demonstration, not a static dashboard or a claim of general natural-language understanding. Routing is deterministic and limited to the documented Chinese/English question families. Real LLM tool-selection quality is a separate provider-integration evaluation.

## Integration contract

```python
from harbor.data_agent import analyze

observation = analyze("合成评测失败主要原因是什么？")
```

The public function accepts one nonblank string of at most 300 characters. It returns a JSON-serializable dictionary:

| Key | Meaning |
| --- | --- |
| `answer` | Chinese or English answer with an explicit synthetic-data disclaimer |
| `plan` | Allowlisted plan ID, dataset, grouping/measurement, validated filters |
| `result` | Actual aggregates calculated from the selected fixture rows |
| `trace` | Validated input, selected plan, executed row counts, and data-bound answer stage |
| `source` | Fixture path, synthetic marker, SHA-256, and actual sample counts |
| `scope` | Read-only synthetic scope, deterministic planner, no private-data access, no real-model quality claim |

`ValueError` is the public rejection/error contract for invalid, ambiguous, unsupported, private-data, SQL, unavailable-fixture, or empty-filter requests. The caller should expose the rejection as a denied tool observation or an appropriate API client error; it must not invent an analysis result or silently query private sessions instead.

Recommended tool schema: `analyze_demo_data` with exactly one required `question: string` field (`minLength: 1`, `maxLength: 300`, `additionalProperties: false`). Registration in the agent loop, API endpoints, and UI belongs to the application integration. This module never imports `Store`, opens a live SQLite database, or calls a provider.

## Allowed plans and questions

| Plan | Executed query | Example |
| --- | --- | --- |
| `emotion_distribution` | Count synthetic turn tags and divide by all selected turns | `合成对话的情绪分布如何？` / `What is the emotion distribution?` |
| `tool_outcomes` | Group synthetic attempts by tool/status; calculate success share | `工具成功、失败、超时的分布怎样？` / `What is tool success rate for read_memories?` |
| `latency_summary` | Count, minimum/maximum, mean, median, nearest-rank p95 | `已完成轮次的延迟如何？` / `What is p95 latency for completed turns?` |
| `failure_attribution` | Group explicitly labeled non-success examples; return supporting sample IDs | `合成评测失败主要原因是什么？` / `What caused failures in the evaluation samples?` |

Tool questions use the synthetic `tool_events` dataset; turn-emotion questions use `turns`; evaluation failure questions use `evaluations`. `工具延迟如何？` selects all synthetic tool events. `为什么 propose_memory 工具失败？` groups the selected tool's non-success reason labels. Explicit evaluation wording keeps failure analysis on evaluation rows.

One allowed tool filter may be specified using an exact name in the question or `tool=read_memories`. Allowed names are `read_memories`, `propose_memory`, `grounding_question`, and `session_insights`.

Latency alone supports one `status=` filter: turn statuses `completed`, `error`, `timeout`; tool statuses `success`, `error`, `timeout`, `denied`. The phrase `已完成` / `completed turns` selects completed turn latency. Tool filter and status can combine, for example `grounding_question 工具延迟 status=success`.

There is no date-window, arbitrary-dataset, custom-path, SQL, provider/model, arbitrary-limit, or multi-question execution. Requests outside these bounds are rejected rather than answered with unrelated sample metrics. The router is intentionally small; unsupported paraphrases can require a clearer supported question.

## Synthetic source and denominators

Source: `eval/synthetic-analytics.json`, ID `harbor-synthetic-analytics-v1`. The rows are hand-authored examples with synthetic identifiers; they contain no conversation text, personal identifiers, model keys, or production telemetry.

- 12 synthetic turn rows, across 6 synthetic session identifiers.
- 20 synthetic tool attempts.
- 16 synthetic evaluation fixtures, including injected failures.

These are fixture counts, not user count, completed regression count, or quality evidence. Evaluation labels were authored to exercise aggregation; they are not real evaluation outcomes.

Known computed examples from this fixture:

- Emotion counts: calm 3, bright 2, low 3, overwhelmed 4. Labels are manually assigned fixture tags, not measured emotion recognition.
- Tool outcomes: success 15, error 2, timeout 1, denied 2. Success share is 15 / 20 = 75%; every selected attempt, including refusal and timeout, is in the denominator. This is synthetic arithmetic, not the application's actual tool success rate.
- All-turn latency mean 2902.5 ms, median 335 ms, p95 30000 ms. The long timeout fixture is included. Completed turns alone have mean 403 ms, median 255 ms, p95 1050 ms. These are authored values, not measured LLM, server, phone, or network speed.
- Evaluation examples contain 6 injected failures: memory confirmation missing 2; context drift, tool timeout, invalid arguments, unsafe dependency reply 1 each. Supporting synthetic case IDs are returned. This groups explicit labels; it does not diagnose unknown causes or establish an actual evaluation pass rate.

`p95` uses the nearest-rank convention: sort the selected values and take the one-based rank `ceil(0.95 * n)`. Median uses the standard midpoint average for even sample sizes. No interpolation or unstated completed-only filtering is used.

## Boundaries

- Question length, type, control characters, recognized parameters, tool names, status values, and single-plan selection are checked before execution.
- SQL-like operations, private-data/credential requests, custom paths/URLs, date windows, unknown tools, and ambiguous multiple analyses are rejected.
- Data is read from one packaged file only. Dataset sizes, marker, schema, identifiers, enum values, nonnegative finite latency, and failure-label consistency are validated.
- No more than 100 rows per fixed dataset are accepted; the fixture file is bounded at 128 KB. There are no writes or caller-selected query targets.
- The trace reports observable execution stages, not hidden chain of thought.
- A source SHA-256 makes the exact arithmetic input identifiable. Changing the fixture changes the digest and calculated answer.

The synthetic marker and strict schema are not a privacy classifier for arbitrary files. Do not replace the fixture with private telemetry. Future real-data analysis needs its own de-identification, ownership/consent, authorization, schema, and evidence design; it is outside this module.

## Objective tests

`tests/test_data_agent.py` checks bilingual routing, exact aggregates, filtered denominators, quantile convention, tool-versus-turn scope, failure evidence IDs, source hashing, read-only behavior, malformed-fixture rejection, and unsupported/private/SQL requests. Mutated fixtures are isolated temporary test files. No live model calls or model-quality scores are involved.

Example local command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_data_agent.py -q --basetemp=data/data-agent-check-unique
```

Choose a fresh project-local base directory for each run. Passing these tests proves deterministic planning and arithmetic for the tested fixtures and rejection paths; it does not establish general semantic analysis quality.

Local verification for this module: **55 tests passed in 0.09 seconds**, using the project's virtual environment and a newly generated project-local temporary directory. Only `tests/test_data_agent.py` was run. This count includes parameterized arithmetic and rejection checks; it is not a count of completed companion-conversation scenarios or measured semantic outcomes.
