# v0.6: authored identities and observable continuity

## Scope and source corrections

The owner requested implementation of the WorkBuddy character-persona handoff. It is an input specification, not evidence that all of its source interpretations are correct.

1. The former history window contained 12 **messages**, usually six user/assistant pairs, not 12 complete rounds. It did not use the model's full context capacity.
2. A detailed input profile does not mechanically require a long answer or imply output truncation. The previous fixed 600-token budget was nevertheless too rigid. v0.6 uses a configurable 600–2000 output budget, default 1200, and explicitly marks safe partial text. Incomplete tool calls still fail.
3. The historical `en-boundary` record in the v0.4 synthetic live report was **model-generated**: provider `openai_compatible`, model trace, attempt 10, 973 prompt / 64 completion / 1037 total tokens. It was not the hardcoded policy sentence. No causal claim that prompting alone explains the quality difference is established by these two samples.
4. The old output filter matched specific assertions such as `我是一个真人`, not every occurrence of `真人`. v0.6 removes detected misleading assertion sentences and preserves unrelated safe sentences. Keeping an unsafe reply intact and merely appending a disclaimer was rejected as an inadequate correction.
5. No measured baseline establishes “zero” persona quality; no “85–90% human” target is recorded. Engineering checks and human dialogue review remain separate.
6. Current [official DeepSeek model documentation](https://api-docs.deepseek.com/quick_start/pricing/) lists a 1M context for its current models; the [completion protocol](https://api-docs.deepseek.com/api/create-chat-completion/) describes output budgets. The handoff's 64K-context assertion must not become a product constraint. This application deliberately uses a much smaller, bounded context independent of that advertised capacity.
7. A character flaw does not excuse ignoring “just listen,” refusal or safety. The authored tendency should be self-correcting when the user states a preference.

## Implemented design

- Three existing adult characters retain their IDs. Each has six authored sections in Chinese and English, age, fictional identity and schema version. Biographical stories are character design, never the owner's professional experience or a claim that an AI has a body.
- Profile/history/restore belong to authenticated administration. Restoring a previous revision publishes a new revision. Existing sessions keep the exact profile/name/prompt/greeting/revision snapshot; sessions predating profiles explicitly say their structured profile is unavailable.
- Public current-profile and owned session-profile APIs expose the authored profile, not administrator instructions or credentials. A read-only `read_own_profile` tool always resolves the current session snapshot.
- Prompt assembly separates global boundaries, character instructions, fictional profile, approved memory, attributed older excerpts, recent full message pairs and the current request. Data is not promoted to instructions. Styles are not forced into every message.
- Long conversation uses at most 12 recent messages within 18,000 UTF-8 bytes and an extractive summary within 9,000 bytes. The summary retains early explicit preferences/plans and recent corrections with source IDs/speakers. Selection and omission counts are visible in context traces. It makes zero extra model requests and does not claim perfect recall.
- Summary storage is **derived session history**, not approved long-term memory. It stays within one session, is exported for its owner, and is removed with clear-history/session/account deletion. Explicitly sharing approved memory does not share the summary.
- Summary update reads at most 512 older messages per build. Overflow is counted, not silently declared remembered. Long indivisible sentences that exceed the excerpt budget are omitted with a visible count. A 120,000-byte serialized-message ceiling fails visibly before an oversized model request. Bytes are a conservative resource bound, not tokenizer measurements or context-window utilization.
- `finish_reason=length` preserves nonempty plain text only when there is no incomplete tool call. The user sees an incomplete-response notice, no automatic continuation is sent, and memory proposals from that turn are discarded. Cached replay retains the status. Other provider failures still have no mock fallback or saved half-turn.
- Six-dimensional reviews require 1–5 scores and a quoted excerpt for each dimension: naturalness, persona, continuity, credibility, empathy and boundary handling. Legacy three-dimensional scores remain legacy; no new score is inferred or filled with zero.

## Evidence plan and truthful limits

`scripts/evaluate_persona.py` has 14 sampled scenarios across 12 categories, including the same daily event for all three characters. A durable SQLite ledger reserves a slot **before** every actual request and refuses a 19th attempt, including after restart. Re-running the complete upgrade sample with an existing ledger is refused. Failures consume the budget; there is no retry loop or API-failure-to-mock conversion.

Every live row identifies character, profile revision, language, input, output, provider/policy source, trace, timing and pending human scores. The long-context sample uses explicitly labeled synthetic fixture history; it does not demonstrate a full 45-turn real-model conversation. Memory proposal uses a real tool request when produced; approval/correction/deletion are scripted synthetic-user actions and are labeled separately. Not all 12 categories are sampled for every character.

The original 50 application fixtures remain. The raw-history-window assertion now additionally requires that the older short synthetic message exists in the attributed summary. This reflects the new continuity requirement rather than removing a regression check.

## Operational precautions

The verified owned v0.5 loopback server was stopped before the schema change. A private consistent SQLite copy was made at `data/backups/harbor-before-persona-20261009-232411.sqlite3`; integrity check returned `ok`. Do not publish this backup or use it as an evaluation fixture. Test imports use a separate ignored `HARBOR_DB` path.

Versioned schema behavior is described in [data migration](data-migration.md), profile content in [character identity](character-identity.md), and current results in [CURRENT](CURRENT.md). Browser automation was unavailable during this iteration; frontend compilation is not visual/mobile acceptance. APK compilation, physical-phone review and public service availability remain separate milestones.

## Remaining work

Human six-dimensional review of actual samples, evidence-driven follow-up of weak responses, accessible browser and physical-phone walkthrough, and the previously planned response-feedback/triage loop. Voice, dynamic avatars, autonomous messaging, production tenancy and commercial claims are outside this increment.

## Final observed results, 2026-10-10

Local full regression: 461 passed in 68.95s; one existing dependency warning. Separate application evaluator: 50/50, zero API calls. Frontend build passed. Cloud CI on source `1b20ef7`: 461 passed in 54.25s, same warning; 50/50 evaluator and web build passed. The first local full run had 4 failures/455 passes: three new mock-profile replies omitted the explicit mock marker, and the export test expected the old top-level inventory. The mock disclosure and inventory check were repaired; owner-summary export/erasure coverage was added. No failure was reclassified as a model-quality success.

The initial real sample used 15 requests and exposed unsupported user-event guessing, misleading chat-only approval wording, and verbose profile corrections. Prompt rules were adjusted; two targeted repeats consumed the remaining 3 requests. Both outputs are retained in [the review queue](persona-evaluation-v0.6.md). Total: 18 requests, 39,058 provider-reported tokens, no execution failures. Human scores remain pending; profile verbosity has not been rechecked after that prompt adjustment.

Local migration passed integrity/foreign-key checks and retained messages, turns, approved-memory and user rows unchanged. Local v0.6 status/health/homepage responded correctly. APK compilation, download/hash verification and actual-key absence checks passed; see [app delivery](app-delivery.md). The [GitHub study](persona-github-references-2026-10-10.md) records verified upstream mechanisms and clearly separates future suggestions from shipped behavior.
