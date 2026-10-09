# Current progress and acceptance

Updated: 2026-10-10, Asia/Shanghai. Source baseline: the owner's `APP需求与验收基线.md` dated 2026-10-09. This file is the continuation entry point; read AGENTS, this file, roadmap, and evidence before the next iteration.

The latest user direction expands the MVP into market-informed operational engineering. Continue from [production readiness](enterprise-readiness.md) and the [market requirement register](market-requirements-2026-10-09.md), preserving the original adult companion/APP scope. The prior [bilingual management follow-up](iteration-2026-10-09-bilingual.md) is retained.

## v0.6 checkpoint — 2026-10-10

Three authored adult AI profiles now have six bilingual sections, immutable session snapshots, version history/restore, public and owned profile views, and a read-only profile tool. Conversation assembly adds attributed bounded session summaries; output budgets and partial-text notices are explicit. Six-dimensional human reviews require quoted evidence and preserve legacy scores. See [character identity](character-identity.md), [migration](data-migration.md), and [iteration decisions](iteration-2026-10-09-v0.6.md).

**Actual checks:** 461 Python tests passed in 68.95 seconds (one existing Starlette/httpx warning); the independent fixture runner passed 50/50 with zero model calls; TypeScript/Vite production build passed. Initial full regression had four failures (three missing mock-disclosure checks and an outdated export inventory expectation); the mock path and additive export contract were repaired, then the suite passed. A subsequent ten-test context/live-runner check passed after the targeted dialogue-rule adjustment.

**Actual model evidence:** 14 initial synthetic scenarios plus two targeted repeats, **18 requests total**, no execution failures, 39,058 provider-reported tokens. One scenario was policy-only. An invented user-work detail and misleading chat-only memory-approval wording were observed and targeted; both original and repeated outputs are retained. Human naturalness/persona/continuity/credibility/empathy/boundary scores remain **pending**. Coverage is sampled, not every scenario for every character; see [review queue and outputs](persona-evaluation-v0.6.md).

The v0.6 loopback server is running at http://127.0.0.1:8765/ with the existing real DeepSeek configuration in `local_demo`. Consistent pre-migration backup was retained; SQLite integrity and foreign keys passed, and messages/turns/approved memories/users were unchanged across migration. **Start a new session to use the new profile**; older sessions intentionally retain their old snapshot and can show a missing structured profile.

Frontend compilation does not establish current browser/360px or physical-phone acceptance: browser automation was unavailable. The APK status is tracked in [app delivery](app-delivery.md). No public deployment, HR message or store release occurred. Official GitHub mechanisms and licensing are recorded in [persona references](persona-github-references-2026-10-10.md); proposed examples/topic selection/cooldowns are future work, not claimed features.


Source `1b20ef7` passed [cloud CI](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37989539500) (461 tests, 54.25s) and [Android compilation](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37989553959). Downloaded `data/releases/Harbor-0.6.0-debug.apk` is 4,340,920 bytes; SHA-256 `90fe6e4872dfd72c809ec2c8a0e138df4a78b93f2807bcca29528298f12e30c0` matches the cloud checksum, and the local provider secret was absent from all ZIP entries.

### Next priorities for this checkpoint

1. Review the actual transcript excerpts with the six-dimensional form. In particular recheck overly long profile replies, defensive corrections and whether same-input character differences survive multi-turn conversation. The current 18-request budget is exhausted; no further live calls under it.
2. Complete a current browser and physical-phone walkthrough: profile tabs, draft preservation, language switching, history snapshots, admin restore and six-score evidence entry.
3. Use reviewed failures to prioritize original dialogue examples and selected relevant profile details from the GitHub reference study, then the existing response-feedback/triage loop. Do not expand into voice, dynamic avatars or automatic outreach.

## Historical v0.5 milestone

**v0.5 owner data lifecycle.** Account mode now provides current-password reauthentication, complete-row JSON export within an explicit 16 MiB limit, exact-confirmation account erasure, attributable-audit cleanup, late-run guards, startup/hourly-on-request security-record retention, and a consistent synthetic backup/recovery drill. See [lifecycle inventory](account-data-lifecycle.md), [recovery limits](data-backup-recovery.md), and the [v0.5 iteration record](iteration-2026-10-09-v0.5.md).

Final local regression: **321 passed**, one existing Starlette/httpx warning, **66.46 seconds**. Independent synthetic evaluator **50/50**, zero model calls; frontend production build passed. The actual synthetic recovery drill passed **10/10 checks**, including rejection of old restored user tokens. This iteration made no new model requests and did not erase an actual owner's account. Current browser/phone UI acceptance remains pending because browser automation was unavailable.

The v0.5 local backend is running at http://127.0.0.1:8765/ in the `local_demo` profile with the existing DeepSeek configuration; status, database readiness and HTTP 200 for the rebuilt frontend were checked. Account features require the owner's deliberately provisioned credentials and `accounts` profile. Packaging status is recorded separately in [app delivery](app-delivery.md); a newly compiled APK is not a physical-phone or public-service acceptance result.

Source `930fff8` passed [cloud framework CI](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37897562260) and [Android compilation](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37897573260). The downloaded `data/releases/Harbor-0.5.0-debug.apk` is 4,328,380 bytes; SHA-256 `4de651923c9b1e4a6322b6fc7451278e7cc655699857519fdf79b526a0937d58` matches the cloud checksum. The actual local provider key was absent from every APK ZIP entry.

### Historical v0.4 checkpoint

**v0.4 account/operations foundation and initial actual DeepSeek execution evidence.** The owner identified the API as official DeepSeek; its documented base URL and `deepseek-flash` are now configured locally. Eight authored synthetic scenarios made ten real requests, with no execution failures and 9,544 provider-reported total tokens. Human scores remain pending. There is no public deployment, HR message, physical-phone acceptance, store release, commercial result or customer-count claim.

### v0.4 implemented increment

- Optional user accounts, hashed opaque tokens, password hashing, expiry/revocation, default-disabled registration; user and administrator credentials are separate.
- Owner checks across sessions, messages, proposals, approved-memory sharing and deletion. Legacy anonymous records are not automatically assigned to users. Remote hosts require accounts mode.
- Server-owned session pagination and user-session restoration. The client clears private state/cancels requests on logout, user expiry or backend change.
- Explicit reviewer permission per owned session, default denied; withdrawal removes review notes and blocks further raw-data inspection.
- Request and concurrency admission, bounded session waits, redacted action audit with startup retention cleanup, readiness endpoint and authenticated operations API.
- DeepSeek-specific request parameters, failure metadata and an opt-in bounded synthetic live evaluator. Hidden reasoning and keys are not exposed.

Final full regression: **266 passed**, one existing Starlette/httpx deprecation warning, 37.33 seconds. Independent synthetic application evaluator: **50/50**, zero model calls. These are separate from the ten real calls. The full rebuild/check and repair history are recorded in [evidence](evidence.md) and the [v0.4 iteration](iteration-2026-10-09-v0.4.md).

User-account frontend compilation and ten grouped synthetic HTTP integration checks passed. Browser automation was unavailable after recovery attempts; current account UI interactions and the new 390px layout have not been visually accepted. Prior v0.3/bilingual walkthroughs are historical evidence only.

Code snapshot `9679f81` passed [cloud framework CI](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37875932171) and [Android compilation](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37875934424). The downloaded `data/releases/Harbor-0.4.0-debug.apk` matches its cloud SHA-256. [Packaging details](app-delivery.md) distinguish compilation from phone/public-release evidence. The local real-provider backend is running at http://127.0.0.1:8765/ in the loopback `local_demo` profile; account profile activation requires the owner's chosen user credentials.

### Earlier v0.3 baseline

| Acceptance area | Implemented evidence | Actual check | Remaining boundary |
| --- | --- | --- | --- |
| Adult disclosed AI characters | Seed personas, management revisions, per-session snapshots | Synthetic identity, snapshot, archive, adult-policy tests | Real-model persona and romance quality pending |
| Multi-turn context | Bounded recent history in provider request | Synthetic capture/provider assertions | Long-conversation continuity and genuine empathy pending |
| Memory consent | Process-only pending suggestions; explicit approved save | Disk/restart/expiry and approval tests | Ordinary dialogue can still contain the same fact |
| Cross-conversation recall | Explicit source-session selection; default isolated memory spaces | Shared recall, default isolation, restart and source-deletion tests; browser walkthrough | v0.3 used demo handles; v0.4 adds account ownership and server session listing |
| Correct/delete memory | User correction with revision; shared deletion; orphan-space cleanup | API/storage scenarios and corrected recall in browser | Historical messages/traces are not rewritten |
| Chinese/English and mobile | Shared language preference, bilingual user/studio UI, language-aware mock/policy, responsive navigation | Production build; prior mobile preview; studio login/draft/error switching walkthrough | Authored character/transcript content stays original; native phone review pending |
| Bounded ReAct-style execution | Allowlist, validation, run/step/tool timeouts, tool errors, content-checked retries | Injected provider/tool errors, timeout, late-result, denied-action, collision checks | No hidden reasoning displayed; Python workers are not forcibly killed |
| DataAgent | Natural-language selection of four safe plans; actual fixed-fixture aggregation | Independent arithmetic, rejection, provenance and API/tool scenarios; mobile query walkthrough | Deterministic planner, synthetic samples only; no private-data/LLM-quality claims |
| Reproducible evidence | 50 bilingual application-contract cases with detailed output/mode/time/errors | 50/50 fixtures; 140 Python tests; frontend build | These counts are engineering checks, not semantic scores |
| App and management | Capacitor Android project, authenticated single-owner console, local server | Management auth/logout/restart/snapshot/privacy checks; v0.3 APK compiled/downloaded/hash verified | Latest APK evidence tracked in app-delivery; hosting and phone installation pending |

Recorded commands/results and source links: [evidence](evidence.md), [evaluation](evaluation.md), [memory](memory.md), [DataAgent](data-agent.md), [user interface](user-app.md), [app delivery](app-delivery.md).

## Historical v0.5 next priorities (superseded by v0.6 above)

1. Add response feedback with authorized turn references, permissioned triage and regression linkage as the next bounded product loop. The v0.5 owner lifecycle is implemented; larger exports, password recovery, backup TTL and deletion-ledger replay remain explicit readiness gaps.
2. Human-review the actual DeepSeek transcripts and expand the existing quality outlines, including gentle-romance consistency, memory conflict and adversarial cases. Fix a measured weakness and rerun the versioned samples; do not convert execution completion into a quality score.
3. Recover UI verification and review the current Android build on a physical phone using a deliberately configured HTTPS account backend. Validate keyboard, rotation, safe areas, reconnect, access code and account switching. No deployment is authorized by this file.

The API input is now available; physical-device and human-quality evidence remain open. Follow the bounded readiness plan instead of rebuilding scaffolding or expanding into voice, dynamic avatars or autonomous outreach. The agreed 1–2 week direction is a goal, not a promised completion date or hiring outcome.
