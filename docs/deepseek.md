# Official DeepSeek integration and bounded live evaluation

Updated: 2026-10-09, Asia/Shanghai.

This documents the provider adapter and an opt-in evaluation workflow. A successful offline adapter check does not establish an actual DeepSeek connection or companion response quality.

## 1. Verified protocol

The [official Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion/) retrieved on 2026-10-09 lists `deepseek-flash` and `deepseek-v4-pro`, a `max_tokens` output limit, and a `thinking.type` switch. The documented default enables thinking. Harbor explicitly disables it for this short-response integration; no low-latency result is claimed without an observed run.

The same reference distinguishes normal completion/tool calls from truncation, content filtering, resource interruption, and aborted generation. These unsuccessful finishes are failures in Harbor. See the [official model page](https://api-docs.deepseek.com/quick_start/pricing/) for current model information; this document does not estimate cost.

`server/harbor/providers.py` applies the special request fields **only** when the parsed hostname is exactly `api.deepseek.com`:

```json
{
  "max_tokens": 600,
  "thinking": {"type": "disabled"}
}
```

Other compatible hosts keep the existing `max_completion_tokens: 600` field. A suffix such as `api.deepseek.com.example.test` does not receive the official DeepSeek protocol. Existing URL checks reject credentials embedded in URLs, query strings/fragments, and unauthorized non-HTTPS destinations.

### Response handling

- Official responses require a recognized `finish_reason` of `stop` or `tool_calls` for success.
- `length`, `content_filter`, `insufficient_system_resource`, `aborted`, or a non-empty refusal field produce `ProviderError`.
- Contradictory finish/tool fields and malformed messages or tool arguments fail validation. The application still validates allowlisted tool names and arguments before executing them.
- `reasoning_content` and raw provider bodies are discarded. No hidden reasoning is returned, replayed, or persisted by the adapter.
- `Completion.metadata` and `ProviderError.metadata` retain a protocol label, HTTP status when available, a validated finish reason, failure class, and allowlisted nonnegative numeric usage. Numeric reasoning-token counts are usage metadata, not reasoning text.
- Raw response errors, transport messages, authorization headers, and exception causes are not echoed. Provider failure never substitutes a mock reply.
- Generic-host fixtures may omit `finish_reason` for backward compatibility; the official DeepSeek path is strict.

The current Agent may classify a provider error as a general execution failure. The live evaluation wrapper separately records the provider's safe metadata, preserving the reason without depending on an HTTP/UI exception serializer.

## 2. Server configuration

Configure the owner-approved destination on the server, through the project's normal settings mechanism. Keep the actual key out of Git, report output, client bundles, APKs, and public screenshots.

| Setting | Intended value |
| --- | --- |
| `HARBOR_PROVIDER` | `openai_compatible` |
| `HARBOR_API_BASE` | `https://api.deepseek.com` or `https://api.deepseek.com/v1` |
| `HARBOR_MODEL` | `deepseek-flash` or `deepseek-v4-pro`, chosen explicitly |
| `HARBOR_API_KEY` | Owner-supplied server-side secret; never print it to validate configuration |

The evaluation reads `Settings.from_env()` through the existing configuration loader. It refuses mock mode, missing configuration, a non-official destination, and an unsupported model name. It does not guess a provider or attempt to obtain a key.

## 3. Commands and explicit call authorization

From the project root:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_live.py
```

This is **validation only**. It makes zero model calls and creates neither an evaluation database nor a report. Validation confirms local configuration shape and presence, not key validity, account balance, network access, or provider availability.

To explicitly authorize the bounded, potentially billable synthetic run:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_live.py --run
```

The `--run` flag is the execution confirmation. The script does not perform a hidden connectivity probe, retry a failed evaluation automatically, call a second provider, send private conversations, contact HR, or deploy a backend.

### Enforced bounds

| Limit | Value and interpretation |
| --- | --- |
| Authored scenarios | At most 8 Agent turns/scenarios |
| Model steps per turn | At most 4 |
| Actual HTTP attempts | At most 32 across the whole run, including failed attempts |
| Deadline | 20 seconds per Agent turn and per provider request; the enclosing run deadline limits a multi-step turn |
| Generated output | At most 600 tokens per request, requested through the official field |
| Tool deadline | Existing tool deadline, capped at 3 seconds for this workflow |
| Concurrency | Sequential scenarios; no parallel provider batch |

These are evaluation limits, not promises of response speed, semantic quality, input-token cost, or provider billing. Actual prompt usage and failed-request charges depend on the provider. Usage is reported only when returned; absent usage is explicitly counted and never estimated.

## 4. Synthetic scenarios and memory consent

The script creates a new `data/live-eval-<UTC timestamp>/synthetic.sqlite3`. It overrides the configured production database path and never opens existing user conversation storage.

| Scenario | Purpose |
| --- | --- |
| `zh-persona` | Chinese identity and AI disclosure with Nova |
| `zh-context` | A synthetic daily event and natural response |
| `zh-continuity` | Recall that event within the recent conversation |
| `en-persona` | English identity/persona with Qinghe |
| `memory-proposal` | Ask the real model to call `propose_memory` for a fixed synthetic preference |
| Scripted approval | Explicitly approve a matching proposal as a synthetic user action; not a model-generated consent decision |
| `memory-linked-recall` | Create a new session explicitly sharing that approved space, then ask for `read_memories` |
| `en-emotion` | Listen to a synthetic presentation-related stress scenario |
| `en-boundary` | Request a false human identity and exclusion of real friends; preserve the actual observed response for review |

If the model does not produce the expected pending proposal, the script marks the linked-recall scenario `blocked_dependency`. It does not inject an approved memory to manufacture a successful demonstration. The approval action, source, success flag, and approved-memory count are included in the report.

The scenarios are authored test inputs. They are not real user emotions, private WeChat history, or evidence of therapeutic effectiveness. Boundary wording and companion quality need human assessment even when the transport succeeds.

## 5. Reports and interpretation

Each explicit run writes a timestamped JSON report and a readable Markdown report under ignored `reports/`. Records include:

- Configured model, official provider label, UTC execution date, mode, bounds, and isolated synthetic storage path.
- Authored question, actual final response when completed, elapsed time, observable tool inputs/results, and failures.
- Per-attempt safe metadata, finish reason, timing, and provider-returned numeric token usage.
- Scripted approval evidence and blocked memory dependencies.
- `human_scores: pending` and `semantic_quality: not scored; human review required`.

Exit status `0` means the scenarios completed mechanically; it does not mean their answers are good. Status `1` means at least one scenario failed or was blocked. Status `2` means validation/setup failed. Failure messages are sanitized rather than printing raw exceptions.

Review the actual responses for persona, continuity, approved-memory use, emotional wording, language, and boundaries. Preserve poor examples, repair a demonstrated problem, and rerun comparable cases. Do not convert a transport completion count into an empathy score or production success rate.

Reports and the synthetic database remain local and ignored. Review every artifact before sharing; the document does not authorize upload, public deployment, or publication.

## 6. Offline evidence from this implementation

On 2026-10-09, `tests/test_deepseek.py`, existing `tests/test_boundaries.py`, and `tests/test_run_failures.py` completed **47 offline checks**. `httpx.MockTransport` or injected providers handled requests; no actual provider network call was made. Test execution disabled automatic dotenv loading and used a fresh test directory inside ignored `data/`.

Coverage includes exact-host protocol selection, truncation/refusal/malformed response failures, hidden-reasoning exclusion, sanitized HTTP/transport errors, generic adapter compatibility, default validation with no side effects, the 32-attempt budget, and synthetic proposal → scripted approval → linked recall.

This is protocol and workflow evidence only. A real connection and companion quality are pending until an authorized run is actually observed and reviewed.
