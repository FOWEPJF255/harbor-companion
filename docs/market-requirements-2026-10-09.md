# Market requirements and engineering priorities

Research date: **2026-10-09, Asia/Shanghai**. All external sources below were retrieved on that date.

Status: **research and proposed acceptance criteria**. This document does not establish that any proposed feature has been implemented, deployed, reviewed on a phone, or used by customers.

## Navigation

- [1. Decision and scope](#1-decision-and-scope)
- [2. Evidence method and current baseline](#2-evidence-method-and-current-baseline)
- [3. Primary-source register](#3-primary-source-register)
- [4. Product requirements mapped to Harbor](#4-product-requirements-mapped-to-harbor)
- [5. Five development priorities](#5-five-development-priorities)
- [6. Companion quality and actual APP acceptance](#6-companion-quality-and-actual-app-acceptance)
- [7. DataAgent scope and evaluation design](#7-dataagent-scope-and-evaluation-design)
- [8. Role signals and honest project positioning](#8-role-signals-and-honest-project-positioning)
- [9. Delivery sequence and evidence gates](#9-delivery-sequence-and-evidence-gates)
- [10. Scope controls and unresolved decisions](#10-scope-controls-and-unresolved-decisions)

## 1. Decision and scope

**Recommendation, derived from the sources:** develop HarborCompanion as an adult, disclosed AI companion APP with an accountable agent runtime and an authenticated operations console. The next increment should demonstrate ownership, bounded execution, privacy controls, quality feedback, and reproducible operation.

The purpose is to make a small deployment understandable and manageable. The product proposition remains a character that can maintain context, use explicitly approved memories, and respond appropriately in a conversation. Engineering features should help that product work and make failures diagnosable.

The research supports three connected requirements:

1. **Companion product:** recognizable character behavior, useful memory, user control, and a way to report an unsatisfactory response.
2. **Agent engineering:** explicit model/tool/context boundaries, observable execution, reproducible evaluation, and failure handling.
3. **Operational foundation:** an authorized owner for every private object, resource budgets, clear data lifecycle, and a reproducible APP/backend release.

These are a scoped project recommendation. They are not a representative survey of all employers or proof of demand for a commercial Harbor service. Job descriptions describe expectations for their own teams, sometimes at substantially higher experience or research levels.

### Priority definitions

| Priority | Meaning in this document |
| --- | --- |
| P0 | A requirement to complete before admitting multiple independent reviewers or making a remotely accessible demonstration available. It can be developed locally without a live model. |
| P1 | A requirement that improves product quality or diagnosis after the P0 access and lifecycle boundaries are clear. |
| Later | A possible expansion with a specific product need, evidence, and owner approval; it is not included merely because a reference product or JD mentions it. |
| External evidence gate | An action requiring a real provider configuration, physical device, deployment decision, or other input that software scaffolding alone cannot supply. |

No latency, availability, user-count, revenue, emotional-quality, or production-success metric is declared by this document.

## 2. Evidence method and current baseline

### 2.1 Inputs

Internal inputs read for this research:

- `AGENTS.md`: project boundaries and development rules.
- `docs/CURRENT.md`, dated 2026-10-09: recorded current capability and remaining acceptance boundaries.
- `docs/roadmap.md`: the staged companion MVP direction.
- The owner's `APP需求与验收基线.md`, dated 2026-10-09: transcription and interpretation of the original HR screenshots.

The HR input requests an actual emotional-companion/romance project result and an APP. It is a specific project direction, not a promise of employment. Its cited reference products and promotional registration figure are not Harbor project metrics. The screenshot JD remains a historical input; its recruiting status was not reverified here.

### 2.2 Source selection

Only first-party product support pages, official employer job pages, official engineering documentation, and official technical standards were used below. Search-result summaries from aggregators, community discussions, and marketing counts were excluded from the requirement evidence.

The Tencent job pages use a dynamic body. Direct page extraction returned an empty body during this research, while search retrieval returned substantial indexed text from the official `careers.tencent.com` URLs. Entries S05-S07 therefore record **official indexed JD text**, with the visible update date. They are useful requirement signals, but their current vacancy status and application availability were not verified. Other sources were read directly.

This is a small, purposefully selected source set. It does not support claims about market percentages, skill-frequency rankings, salary expectations, or the owner's eligibility for these specific roles.

### 2.3 Current-state snapshot

The table below summarizes `docs/CURRENT.md` as read during this research. It is a document snapshot, not an independent implementation audit. Code and delivery may advance after this snapshot; check CURRENT and evidence before identifying a proposed item as a remaining gap.

| Area | Recorded baseline | Boundary relevant to this research |
| --- | --- | --- |
| Character and context | Adult AI disclosure, managed character revisions, per-session snapshots, bounded recent history | Real-model persona consistency and genuine emotional response remain unmeasured. |
| Memory | Explicit approval, process-only pending proposals, optional explicit cross-session sharing, correction and deletion | Sharing uses demo capability handles; this is not a full account/device identity system. Historical dialogue and traces are separate stores. |
| Harness | Tool allowlist, validation, loop/run/step/tool limits, visible failures and retries | Worker termination and distributed execution are not claimed. |
| DataAgent | Four bounded plans aggregate a fixed synthetic dataset and disclose provenance | Deterministic planning; no arbitrary SQL, private conversation analysis, or real-business-data claim. |
| Operations console | Authenticated single-owner management and stable character snapshots | Multiple operator roles, tenant lifecycle, and privacy workflows require separate evidence if introduced. |
| APP delivery | Capacitor Android project; a prior APK compilation/download/hash check is recorded | A current-code APK, physical-phone review, public backend, and store publication are distinct evidence stages. |
| Model connection | A local server-side key has been supplied | Provider base URL and model name were absent in CURRENT. No credential destination should be guessed. |

Existing mock checks establish engineering behavior for their fixtures. They do not establish semantic quality, real-provider uptime, real user satisfaction, or a production deployment.

## 3. Primary-source register

Each source entry separates the source-supported fact from the project proposal. All entries were retrieved **2026-10-09**. A visible page date is listed only when observed; a crawl date is not a publication date.

### 3.1 Companion product and privacy sources

| ID | Source, type, and date visible on page | Source-supported requirement signal | Harbor mapping and priority |
| --- | --- | --- | --- |
| S01 | [Replika: How does memory work?](https://help.replika.com/hc/en-us/articles/37208679176077-How-does-Replika-s-memory-work), official product support. No update date visible in extracted body. | Replika describes visible memories, manually added memories, personalization, and feedback on correct recall. | P1: make Harbor memory understandable and correctable. Preserve Harbor's explicit approval model; the reference's automatic memory design is not a requirement to copy. |
| S02 | [Replika: Can I delete my conversations?](https://help.replika.com/hc/en-us/articles/4410750548493-Can-I-delete-my-conversations), official product support. No update date visible. | The page distinguishes conversation history/account deletion from editing individual memories, and presents deletion as an irreversible action. | P0: explicitly distinguish history, approved memory, feedback, and traces in Harbor's export/deletion UI. Do not adopt the reference's account-only history deletion limitation. |
| S03 | [Character.AI privacy FAQ](https://support.character.ai/hc/en-us/articles/39030432883099-Privacy-Policy), official product support. Updated 2025-10-29. | It explains data collection/use, service-provider sharing, and regional access/correction/deletion/portability rights. | P0: document Harbor's actual data inventory and provider disclosure; implement scoped export/deletion. This is a product signal, not a legal conclusion that Harbor meets any regional law. |
| S04 | [Character.AI: How to report](https://character.ai/safety/reporting), official product safety workflow. No publication/update date visible. | Web and mobile users can report content with a reason and optional details for review. | P1: add a response-specific quality/safety report and an authenticated review queue. Harbor does not need public user-generated-character moderation while it has a managed character catalog. |

### 3.2 Agent, Harness, DataAgent, and evaluation job sources

| ID | Source, type, and date visible in official indexed/page text | Source-supported requirement signal | Harbor mapping and priority |
| --- | --- | --- | --- |
| S05 | [Tencent: 混元Agent强化学习框架工程师（深圳/北京/上海）](https://careers.tencent.com/jobdesc.html?postId=2061654749727600640), official indexed JD. Updated 2026-09-30. | Model/tool/context/task/trace/evaluation components, repeatable experiments, concurrency/resource consistency, Python/async engineering, and container/Kubernetes familiarity. | P0: explicit runtime contracts and budgets; P1: versioned run/evaluation records and a reproducible deployment. RL training and Kubernetes experience remain separate gaps. |
| S06 | [Tencent: Agent可观测研发工程师](https://careers.tencent.com/jobdesc.html?postId=2029862287371825152), official indexed JD. Updated 2026-09-14. | Agent logs/traces/metrics collection, SDK conventions, GenAI/OTel integration, and cloud-scale observability. | P0: coherent redacted run metadata and failure attribution; P1: a versioned telemetry adapter. Harbor is not a cloud-scale logging platform and need not introduce Kafka. |
| S07 | [Tencent: 微信支付-数据科学](https://careers.tencent.com/jobdesc.html?postId=2090281754874265600), official indexed JD. Updated 2026-09-01. | DataAgent architecture/evaluation, NL2SQL, business insight, knowledge systems, and analytical/causal methods. | P1: governed data-source contracts and verifiable analysis of approved evaluation artifacts. NL2SQL, knowledge graphs, financial analysis, causal inference, Spark, and production data are not current Harbor capabilities. |
| S08 | [Anthropic: Research Engineer, Post-Training Model Evaluations](https://job-boards.greenhouse.io/anthropic/jobs/5198255008), employer's official job board. No publication/update date visible. | Reliable measurements, live eval monitoring, regression investigation, dashboards/reports, and strong Python/production-system judgment. | P1: separate contract regression from human-reviewed model quality, preserve failing examples, and compare versioned runs. This is a capability reference, not a direct job-match assertion. |

### 3.3 Operations, authorization, privacy, and APP quality sources

| ID | Source, type, and date visible on page | Source-supported requirement signal | Harbor mapping and priority |
| --- | --- | --- | --- |
| S09 | [OpenTelemetry: Inside the LLM Call](https://opentelemetry.io/blog/2026/genai-observability/), official engineering blog, published 2026-05-14. | Model/tool/retry latency, token metadata, and trace structure help diagnose agent behavior; sensitive content is not captured by default in the described workflow. | P0: operational metadata first; P1: local telemetry viewing/export when useful. No external telemetry account is required by this source. |
| S10 | [OTel GenAI span conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md), official evolving specification, status **Development** at retrieval. | Content and memory records can be sensitive; content capture should be opt-in. Separate content storage/access is described for production needs. | P0: prevent prompts, memory values, raw outputs, access handles, and credentials from entering ordinary operational telemetry. P1: pin the adapter/schema version; do not describe this as a stable compliance certificate. |
| S11 | [OWASP API1: Broken Object Level Authorization](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/), official API Security Top 10, 2023 edition. | Authorization must be checked for each action on a requested object; an opaque or random ID alone is insufficient. | P0: check tenant/user/role and object ownership for sessions, memory spaces, feedback, exports, deletions, and admin actions. |
| S12 | [OWASP API4: Unrestricted Resource Consumption](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/), official API Security Top 10, 2023 edition. | Execution, payload, operation, rate, result-size, and third-party spending limits address resource exhaustion. | P0: admission limits, concurrency bounds, request/response caps, bounded retries and provider budgets; reject safely before provider/tool invocation. |
| S13 | [Android: Core app quality guidelines](https://developer.android.com/docs/quality-guidelines/core-app-quality), official platform guideline. Updated 2026-09-21 UTC. | The guidelines cover state preservation, navigation, orientation/resizing, responsiveness/stability, minimum permissions, safe logging, and encrypted network traffic. | P0 external evidence gate: verify the actual APK on a phone, including back navigation, keyboard, state, reconnect, and HTTPS. Additional media permissions are unnecessary for a text-only companion. |
| S14 | [SQLite Online Backup API](https://sqlite.org/backup.html), official storage documentation. Updated 2025-11-13. | The backup API creates a consistent snapshot of a live database with defined locking/error behavior. | P1: provide a controlled backup/restore procedure and exercise it with disposable data. Backups are private operational data with retention rules, not public demo artifacts. |

## 4. Product requirements mapped to Harbor

The following requirements are **research-derived proposals**, not quotations from employers or a claim that competitors all implement the same design. A priority represents Harbor's exposure and project goal.

| Requirement | Why it matters and evidence | Current foundation | Proposed increment | Priority and completion evidence |
| --- | --- | --- | --- | --- |
| Recognizable character and conversational continuity | Memory/personalization is an explicit product feature; evaluation jobs value meaningful quality measurement. S01, S08. | Character snapshots and bounded context. | Human-reviewed persona/continuity scenarios with the actual configured model, prompt version, and failed examples. | P1 plus real-provider gate. Review notes and reproducible run records; no mock-based empathy score. |
| Visible and reversible structured memory | Product help exposes manual memory management; history and memory have different deletion semantics. S01-S02. | Approval/correction/delete and explicit sharing. | Explain exactly what is approved, what is only in dialogue, where sharing applies, and what deletion affects. | P0 lifecycle clarity; P1 recall feedback. UI walkthrough and isolated/shared-memory cases. |
| Owner-bound private objects | Client-supplied object IDs require authorization. S11. | Single-owner admin plane and demo session handles. | Separate authenticated reviewer/customer identity from administrator access; bind each session/memory/export/feedback to an authorized principal and tenant scope. | P0 before independent reviewers. Cross-owner read/write/share/export/delete denial evidence. |
| Bounded provider/tool service | Agent framework roles highlight resource consistency; API resource consumption includes API cost. S05, S12. | Existing loop/timeouts and tool validation. | Add request admission, global/per-owner concurrency and quotas, payload/result caps, explicit rejected/failed outcomes, and provider-spend accounting when actual usage exists. | P0. Rejection must occur before invoking the provider; error metadata must explain the class. |
| Useful operational diagnosis | Agent observability JD and engineering docs separate runtime causes. S06, S09-S10. | Visible actions and failure observations. | Redacted run/step/tool metadata; a console summary for provider/tool/validation/rate-limit/cancellation failures. | P0. Known injected failures yield the expected class and remain inspectable after restart within the configured retention period. |
| User feedback to a maintained quality backlog | Companion products expose reporting; eval roles investigate regressions. S04, S08. | Managed characters and evaluator fixtures. | In-app feedback with category, authorized turn reference, optional explicitly shared text, triage state, and regression-case linkage. | P1. Submit, review, resolve, and rerun one real issue; mock issues remain labeled synthetic. |
| Trustworthy analytical answers | DataAgent JD includes data/evaluation capability; product data can be sensitive. S07, S03. | Actual bounded fixture aggregation. | Versioned, schema-validated imports of approved synthetic or de-identified evaluation artifacts; trace dataset, filter, denominator, result, and limitation. | P1. Independent arithmetic and source attribution; no arbitrary private-data queries. |
| Documented data lifecycle | Privacy and product help distinguish data uses and user control. S02-S03, S10. | Local storage with approved-memory semantics. | Inventory, per-owner export, deletion scope, retention cleanup, telemetry minimization, and a stated backup/restore boundary. | P0 for serving independent reviewers; P1 restore drill. Verify stores and caches as well as UI success messages. |
| Actual APP behavior | Platform quality includes state, navigation, privacy, and stability. S13. | Responsive UI and Android packaging. | Current revision/package record and physical-phone acceptance using a deliberately configured HTTPS backend. | P0 external gate for an APP-result claim. Record device/OS/build/backend mode/date and actual observations. |
| Recoverable, repeatable operation | Framework/eval roles value repeatability; SQLite offers supported snapshot mechanisms. S05, S08, S14. | Local backend and migration/storage code. | Configuration validation, deployment/runbook, health/readiness states, schema version, safe backup and rollback demonstration. | P0 configuration/runbook; P1 recovery exercise. No uptime or RPO/RTO promise without measurement. |

## 5. Five development priorities

All five can begin using disposable local data. Live quality and physical-device validation remain separate gates. Complete the existing functions through coherent contracts instead of creating a second companion app or agent framework.

### 5.1 P0 — Principals, object ownership, and management permissions

**Reason:** Harbor's capability handles are useful demo boundaries, while a service for independent users needs an explicit answer to who may read, change, share, or delete each object. This follows from S11; it is a Harbor architecture inference.

Suggested minimal design:

- Define a principal with user ID and deployment/tenant scope. If supporting multiple organizations, define tenant membership explicitly; do not infer it from a client-provided tenant ID.
- Keep user/reviewer authentication separate from studio administration. A model API key cannot be a user credential.
- Define a small permission matrix: end user, reviewer/operator where justified, and administrator. Do not create roles that have no workflow.
- Authorize the requested action on the owned object in one shared service layer. Apply the rule to history, memory-space membership, feedback, exports, deletion, and management endpoints.
- Make explicit memory sharing remain an authorized opt-in action. Possession of an unrelated raw ID must not establish membership.
- Preserve existing-session character snapshots when an administrator publishes changes.

Acceptance proposal:

| Scenario | Required observed outcome |
| --- | --- |
| User A supplies user B's session or memory identifier | Read, update, deletion, sharing, feedback lookup, and export are denied without exposing B's content. |
| Ordinary user calls a management mutation | Denied even when the user knows the endpoint and character ID. |
| Expired/revoked credential is reused | Denied consistently; stored drafts do not silently submit with stale authorization. |
| Existing user approves a share to a new session they own | Approved structured memories are available according to the declared scope; unrelated histories remain private. |
| An administrator publishes a new character revision | Existing sessions retain their snapshot; new sessions use the published revision. |

Migration must define ownership for pre-existing demo sessions. Do not assign ambiguous legacy private data to every newly registered user. A local demo reset or an explicit owner-only migration is safer than implicit sharing.

### 5.2 P0 — Admission control, quotas, and bounded costs

**Reason:** a tool-step timeout does not prevent a client from starting many runs. S12 motivates the broader resource boundary; S05 supplies the agent-runtime requirement signal.

Suggested increment:

- Validate configured limits at startup: accepted text size, retained context size, maximum steps, tool-result size, provider timeout, retry allowance, active runs, and admission window.
- Enforce both deployment-wide concurrency and per-principal limits. Reject overload before invoking the provider or reserving an unbounded worker.
- Count failed and retried provider attempts in execution budgets. Deduplicate a replayed client submission where an idempotency contract is offered.
- Separate cancellation, timeout, provider failure, validation rejection, quota rejection, and explicit policy refusal. Return a stable user-facing status without raw upstream bodies or secrets.
- Track token counts only when actually returned by the provider. Any local token estimate needs an explicit estimate label and method.
- Define whether daily usage budgets are request-based, token-based, or money-based. A currency amount needs a versioned price source and actual usage; no guessed costs.

Acceptance proposal: submit a burst with disposable principals, observe bounded active work, inspect deterministic rejection metadata, verify rejected calls never reach a counting fake provider, and verify a failed retry consumes the stated attempt budget. A budget failure must not become a successful mock reply.

Threshold values are configuration decisions for the chosen deployment. This research does not prescribe a fake capacity or latency SLO.

### 5.3 P0 — Redacted run records and actionable operations views

**Reason:** S06 and S09 establish that agent operation needs diagnosable execution. S10 warns that operational and conversational content have different access needs.

Suggested run metadata contract:

| Field group | Suggested contents | Privacy boundary |
| --- | --- | --- |
| Correlation | Internal run ID, parent step ID, deployment/revision, non-secret principal scope | Never log a bearer token, raw capability handle, or credential as a correlation ID. |
| Execution | Mode, operation name, allowlisted tool name, step/retry count, outcome class | Avoid raw arguments and observations in default telemetry. |
| Provider | Provider label, configured/returned model where available, duration, usage when returned | Exclude API key, authorization headers, sensitive endpoint query strings, prompt text, and output content. |
| Versioning | Character revision, prompt/schema/evaluator version, dataset ID where relevant | Use public or internal non-secret references. |
| Timing | Server timestamps and durations with documented units | Report missing values explicitly rather than replacing them with zero. |

Proposed console panels: recent failures by class, running/queued/rejected counts, bounded tool outcomes, provider attempts/retries, and latency distribution with period/sample count. Label mock, injected-failure, and real-provider runs distinctly.

Do not advertise a percentile when its sample set is empty or too small for a meaningful comparison. Report the definition, denominator, period, and environment alongside any measurement. Any telemetry export adapter should record the chosen evolving GenAI convention version.

Acceptance proposal: an injected slow tool, malformed provider response, rejected tool action, and provider exception each produce a distinct redacted record. The records survive the documented restart path. An export scan finds no credentials or synthetic sentinel private text. A single recorded run can be explained without displaying hidden reasoning.

### 5.4 P1 — Feedback, evaluation maintenance, and governed DataAgent reporting

**Reason:** S04 supports reporting inside the product, S08 supports reliable regression analysis, and S07 supports traceable analytical engineering. The proposed integration is Harbor-specific.

Suggested workflow:

1. A user marks a reply as helpful/unhelpful or reports a specific category: incorrect memory, character drift, irrelevant response, unsafe response, tool failure, or other.
2. The service checks that the user owns the referenced turn and stores a minimal feedback record. Optional free text has a size limit and a disclosure explaining who can read it.
3. The console lists issue category, character/prompt revision, execution mode, status, and authorized operational metadata. Access to conversational text needs its own explicit permission; ordinary operators should not gain unrestricted chat browsing through feedback.
4. A maintainer links an issue to a new synthetic or explicitly consented evaluation case. Label provenance and remove personal identifiers before sharing artifacts.
5. Rerun the comparable case/version, record observations, and resolve or retain the issue. Do not close it solely because a mock regression passes.

The first DataAgent extension should consume an allowlisted **evaluation-run dataset**, with an explicit source ID, schema version, generation/collection date, and authorization scope. Preserve the existing synthetic demo endpoint and its clear labeling. Do not let importing a file enable arbitrary filesystem reads, arbitrary SQL, or analysis of private dialogues.

Useful initial analyses: outcomes by error class, tool success/failure/timeout, provider attempts/retries, and latency summaries. Every answer should expose its query plan, filters, actual result, denominator, source, and limits. Emotion labels on synthetic or manually annotated scenarios are dataset labels, not measured user emotions or diagnoses.

Acceptance proposal: one reported synthetic failure travels through submit → authorized triage → linked case → rerun → recorded disposition. Imported data fails closed on an unexpected schema, out-of-scope owner, oversized file, or unsupported query. An independently computed aggregation matches the returned answer.

### 5.5 P0/P1 — Privacy lifecycle, export/delete, and recoverable operation

**Reason:** S02-S03 show that users need understandable control of different data categories. S14 provides a supported storage snapshot mechanism; the proposed recovery/lifecycle policies are project choices.

Write an inventory before implementing a general “delete everything” action:

| Data class | Questions the implementation must answer |
| --- | --- |
| Dialogue history | Who owns it, where is it stored, what does export include, and how is it removed? |
| Pending memory proposals | Are they still process-only with expiry, and are they invalidated when their session/owner is deleted? |
| Approved memory and revision history | Which authorized sessions share the space, and what does correction/delete remove or retain? |
| Content-bearing traces/artifacts | Is capture enabled, for what purpose, for how long, and who can access/delete it? |
| Metadata and feedback | What remains after content deletion, and can remaining fields still identify the user or reveal a conversation? |
| Credentials | Where are they kept and revoked? They must never appear in user export, APK, logs, or ordinary backup evidence. |
| Client caches/preferences | What is retained in browser/device storage and what does logout/account deletion clear? |
| Backups | Who can restore them, when do they expire, and how will a restore avoid reintroducing deleted user data? |

Suggested increment:

- Provide a per-owner export manifest with schema/version/date and explicit included/excluded stores.
- Offer scoped deletion with a confirmation explaining shared memory, retained operational records, and backups. Use a transaction or resumable deletion job with a visible outcome; a success toast alone is not evidence.
- Add bounded retention cleanup with a dry-run summary and an auditable result. Defaults should be explicit; arbitrary retention durations are not market facts.
- Prevent exports and backups from being placed under public/static assets or checked into Git. Restrict download authorization and avoid secrets in filenames/URLs.
- Provide an operator runbook for a consistent backup and restore into an isolated destination. Exercise it using disposable data, inspect integrity/ownership/schema state, and document failure/recovery steps.
- Plan a deletion ledger or another justified mechanism if restoring backups can resurrect deleted identities/content. Do not claim immediate erasure of backups unless the implementation proves it.

Acceptance proposal: user A can export only A's declared data, an export excludes credential sentinels, deletion clears the declared live stores and invalidates handles/caches, retention removes expired disposable records, and restoring an isolated backup respects the documented deletion boundary.

Legal compliance, encryption guarantees, recovery objectives, and availability guarantees require separate review and evidence. This research neither certifies them nor selects a legal retention period.

## 6. Companion quality and actual APP acceptance

The operations increment does not substitute for the HR's requested companion result.

### 6.1 Real companion behavior

Use the existing scenario suite as a maintained baseline. Add cases for observed failures instead of inventing a new passing count. Suggested human review dimensions are:

- Character consistency across multiple turns and sessions.
- Understanding a user's expressed intent without pretending to read their mind.
- Remembering approved information accurately, admitting missing information, and honoring corrections.
- Responding to emotional context with appropriate wording and boundaries.
- Avoiding repetitive or manipulative relationship language.
- Clear AI identity, consent, and adult-product boundary.
- Natural Chinese/English behavior in the selected response language.
- Honest tool/provider failures and practical recovery.

These are proposed evaluation dimensions. Record actual provider/model, input provenance, character/prompt revision, date, mode, reviewer rubric, and failed examples. A numerical rubric is a human judgment instrument, not a clinical measure or proven business impact. A judge model, if later used, needs its own version and limitations.

The provider configuration gate remains unresolved in the baseline. Do not send the locally stored key to a guessed URL. The owner must supply the intended base URL and model, and then an authorized real run can produce semantic evidence.

### 6.2 Native phone evidence

S13 supports the general needs for state preservation, navigation, privacy, and stability. The following checklist is a Harbor-specific acceptance proposal using the internal APP baseline; it does not reproduce the complete Android guideline. Do not infer these outcomes from a desktop responsive preview:

| APP check | Evidence to capture |
| --- | --- |
| Installation/opening | Package version/hash, code revision, phone model, Android version, install/open result. |
| Back navigation | Dismiss keyboard/modal and return between app screens without discarding an unsent draft or unexpectedly exiting. |
| Keyboard and safe area | Chat composer/send controls remain reachable; last message is readable with keyboard, navigation bar, and display cutout. |
| Orientation/resizing | User-facing actions retain parity; draft/navigation state behaves as documented. |
| Background and resume | Returning from lock/app switch restores the permitted state and does not duplicate a send. |
| Disconnect/reconnect | Offline state is visible; no fake reply or queued private send is generated; reconnect requires valid authorization. |
| Privacy and network | No model key/admin credential is packaged; no private API cache or sensitive device log; intended backend uses HTTPS. |
| Startup and slow reply | Loading/progress/error controls remain responsive; record measured time and environment rather than claiming a universal response speed. |

A compiled debug APK is an engineering artifact. Phone installation/review, a release-signed package, distribution, iOS packaging, and app-store publication remain separate milestones. A PWA can supplement the web experience; it cannot be described as the requested native APP result.

## 7. DataAgent scope and evaluation design

S07 includes requirements well beyond the existing deterministic DataAgent. Harbor should demonstrate a narrow useful analytical flow with evidence, while preserving that boundary.

### Recommended next data contract

| Contract element | Proposed rule |
| --- | --- |
| Source kind | `synthetic_demo`, `synthetic_eval`, or explicitly authorized `deidentified_eval`; distinguish each in UI and responses. |
| Ownership | A private imported dataset belongs to the authenticated principal/tenant and is checked at query time. |
| Import | Admin/owner-allowed format only; bounded file/row sizes, schema validation, documented required columns, and no arbitrary path/URL fetch. |
| Planning | Allowlisted operations and validated filters; unsupported natural-language intent returns a clear unsupported outcome. |
| Execution | Perform actual aggregation over the selected source; do not generate plausible numbers from the question. |
| Output | Answer plus source/version/date, plan, filters, denominator, result, trace, and limits. |
| Interpretation | Correlation and recorded failure classes are descriptive evidence; neither causal attribution nor diagnosis is implied. |
| Privacy | Content-free operational columns by default; no private chat mining or cross-tenant joins. |

Useful first questions for approved eval records include “Which tool timed out?”, “Which version had more validation failures?”, and “What was the latency distribution for the selected mode?” Each question must be supported by available columns and an authorized source. Missing columns or data produce an explicit limitation.

Choose natural-language planner upgrades only after the deterministic execution and refusal contracts remain stable. A language-model planner must propose a validated bounded plan; it cannot grant itself data access or insert raw SQL. NL2SQL and RAG/knowledge-graph work are later, separately scoped capabilities if they serve an actual dataset/problem.

## 8. Role signals and honest project positioning

This is a mapping of project evidence to role themes, not a claim of matching every advertised requirement.

| Role theme | Evidence Harbor can strengthen | Accurate description after implementation/evidence | Description to avoid |
| --- | --- | --- | --- |
| Companion Agent application | Character/context/memory boundaries, real conversation reviews, APP behavior | An adult companion prototype with explicitly approved memory and recorded real-provider/phone reviews. | Proven emotional satisfaction, mature romance product, user retention or commercial adoption without evidence. |
| Agent Harness/runtime | Tool contracts, execution budgets, idempotency, failures, versioned run metadata | A bounded application harness with observable actions and reproducible error handling. | General-purpose autonomous framework, distributed durable execution, RL platform, or Kubernetes expertise based on this APP alone. |
| Agent observability | Redacted traces/metrics, failure taxonomy, diagnosis walkthrough | Runtime metadata and failure analysis for a controlled deployment. | Cloud-scale logs platform, high-concurrency production experience, or universal stable GenAI-standard compliance. |
| DataAgent/application analytics | Governed dataset import, validated plan, real aggregation, provenance | Bounded analysis of labeled synthetic or authorized evaluation data. | Production NL2SQL, enterprise knowledge graph, causal analysis, financial modeling, or private-user emotional analytics. |
| AI product/engineering quality | Feedback-to-case workflow, version comparisons, failed-case repair | Maintained engineering regression and human-reviewed quality evidence with limitations. | Mock pass rate as model intelligence, evaluator count as business success, or a universal quality guarantee. |
| Backend/operations | Ownership/auth, budget, export/delete, recovery/runbook | Operational foundations for an authenticated small deployment, with concrete check records. | Already production-grade, large-scale multi-tenant SaaS, regulatory compliance, or availability promises from feature presence alone. |

Eligibility boundaries remain separate from project scope. The retrieved jobs include experienced and research-heavy positions; for example, S07 specifies a master's degree and S06 emphasizes substantial backend/cloud experience. Improving Harbor does not change the owner's education, employment dates, title, years of experience, or demonstrated training/algorithm expertise.

Before applying, reopen the current complete JD and assess its seniority, degree requirements, city/work arrangement, actual duties, and recruiting status. This research document should feed a fact-bound resume, not create personal skills from market keywords.

## 9. Delivery sequence and evidence gates

### 9.1 Suggested work order

| Increment | Deliverable | Dependencies | Evidence gate |
| --- | --- | --- | --- |
| A: access contract | Principal/ownership model, role matrix, session/memory/feedback authorization, migration decision | Existing storage/admin/session contracts | Cross-owner and role-denial cases with disposable data. |
| B: controlled runtime | Admission limits, quotas/concurrency, stable error classes, redacted run metadata | A; existing bounded harness | Bounded fake-provider/tool evidence plus secret/content sentinel checks. |
| C: data lifecycle | Inventory, per-owner export/delete/retention, safe recovery runbook | A; versioned storage schema | Inspect actual stores, artifacts, client behavior, and isolated restore; document retained data. |
| D: quality loop | Response feedback/triage/case linkage and governed DataAgent eval reporting | A-C; existing evaluator and safe planner | Actual lifecycle demonstration and independent aggregation. |
| E: product result | Intended real provider, observed companion quality, current APK and physical phone walkthrough | Owner supplies API base/model; controlled HTTPS demo decision and physical device | Provider/model/date/revision and actual phone evidence. |

The order is a dependency proposal, not a schedule or hiring commitment. Keep code changes incremental and reuse current endpoints/components where appropriate. A single service with a well-defined storage boundary is sufficient for the initial controlled deployment.

### 9.2 Minimal operations evidence packet

For each completed increment, retain:

- Implementation revision and a short change summary.
- Endpoint/data/permission contract and configuration names; use example values without secrets.
- Exactly which local/synthetic/real/provider/device checks ran, their environment, outcomes, and remaining failures.
- Migration/deletion/rollback boundary and known limitations.
- One walkthrough that explains a successful user flow and one observed failure/recovery flow.

Health/readiness should distinguish process alive, storage usable, provider configured, and provider successfully observed. A readiness check must not silently make paid model calls or expose private configuration. Operational summaries should preserve missing/unknown states.

### 9.3 Evidence wording by stage

| Observed stage | Permitted statement |
| --- | --- |
| Design exists | Proposed or designed; implementation pending. |
| Code exists without a check record | Implemented locally; verification pending. |
| Synthetic check passes | Verified for stated synthetic scenarios/environment. |
| Real provider run recorded | Observed with that provider/model/configuration/date, including limitations. |
| APK compiled | Android package compiled at stated revision; phone behavior not yet established. |
| Phone walkthrough recorded | Installed/reviewed on the stated device/build/backend; do not generalize to all devices. |
| Controlled hosting works | Deployed to the stated environment and scope; no production-scale/uptime claim. |

## 10. Scope controls and unresolved decisions

### 10.1 Features requiring a concrete later need

| Feature | Reason to defer by default |
| --- | --- |
| Microservices/Kafka/Kubernetes | The selected jobs mention infrastructure at their own scale. Harbor first needs a measured operational bottleneck and deployment need. |
| Payments/subscriptions | No billing requirement exists in the original direction or current baseline; it introduces an unrelated product and sensitive workflow. |
| Voice, realtime calls, animated/3D avatars | Possible companion features, but each requires quality/device/cost/privacy work beyond the text companion result. |
| Engagement notifications/background outreach | Not needed to demonstrate thoughtful conversation; background engagement requires a separate consent/product design and conflicts with current project boundaries. |
| Public user-created characters/social network | Current catalog is managed. Public creation requires a separate content/permission/reporting scope. |
| RL training/fine-tuning | Market roles mention it; Harbor currently needs actual application-quality evidence, not an unmeasured training claim. |
| Arbitrary SQL/private-chat analytics | Violates the existing DataAgent and privacy boundary; a later analytics use case needs explicit data authorization and a constrained contract. |
| External messaging, account integration, automatic HR contact | Outside this companion APP scope and prohibited by current AGENTS. |

### 10.2 Decisions to settle during implementation

1. **Exposure:** single-owner local use, invited reviewers, or independent user accounts? Public registration is a distinct choice; it should not be enabled as an incidental UI feature.
2. **Identity and organization:** does a tenant mean one deployment, one organization, or a review workspace? Choose the smallest model needed; enforce it consistently.
3. **Privacy defaults:** what data categories are retained, for what period/purpose, and who may see content-bearing artifacts? The values must be explicit product decisions.
4. **Quality rubric:** who reviews companion responses, how are failures labeled, and how are results compared across versions?
5. **Live provider:** intended base URL and model name, then an authorized synthetic-dialogue verification. A local key alone is insufficient.
6. **APP evidence:** access to an actual Android phone and a deliberately configured HTTPS backend; iOS release work requires its own tooling and evidence.

### 10.3 Research maintenance

Recheck product help and specifications when implementing their related contracts. Recheck live complete job descriptions when tailoring a resume. Preserve source URL, retrieval date, visible update date, source type, and which conclusion is an inference.

Do not rewrite this dated research as proof of present recruiting availability. Do not turn a competitor's claims, a job's infrastructure scale, or a proposed acceptance criterion into Harbor metrics or the owner's experience.
