# Production readiness and controlled service profile

Updated: 2026-10-09. This is an engineering acceptance register, not a claim that Harbor is production ready.

## Positioning and sources

Harbor is an adult, disclosed character companion APP with a bounded agent runtime and an authenticated management plane. Its next release should be useful to independent reviewers without treating session IDs as credentials. Product quality and operational controls are separate acceptance areas.

The [market research](market-requirements-2026-10-09.md) records 14 first-party sources, their retrieval dates, limitations, and proposed priorities. The most immediate engineering signals are [object authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/), [resource limits](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/), and [redacted GenAI observability](https://opentelemetry.io/blog/2026/genai-observability/). These guide this implementation; they do not certify it.

## Implemented v0.4 foundation

| Area | Actual implementation | Evidence and scope |
| --- | --- | --- |
| User identity | Optional `accounts` profile; opaque bearer tokens stored as hashes; password hashing; expiry, active-account checks and logout revocation | 38 authentication module tests, disposable synthetic accounts |
| Object ownership | Session and approved-memory-space owner columns; every user API action checks the authenticated owner | 37 account/API tests, including cross-user read/write/share denial |
| Safe legacy migration | Old anonymous sessions retain NULL ownership; no automatic account claim | Migration and legacy-boundary tests; private local database snapshot retained outside Git |
| Reviewer access | Accounts conversations are hidden from reviewers until the owner grants access; withdrawal removes review notes and denies subsequent reads | Default-denial, grant, review, withdrawal and denial tests |
| Request admission | Default 20 chat/analysis requests per actor per minute, 100 sessions per user, bounded session-lock waits | Resource tests and configured limits; completed cache retries do not invoke the provider or create another audit event |
| Concurrency | Default four active run slots, two-second admission timeout, guaranteed slot release on failure/cancellation | Synthetic concurrency/timeout checks; single Python process only |
| Provider budget | Step/run/tool deadlines; four tools maximum per model step; 600 output tokens per request | Protocol and failure-boundary tests; no automatic model-request retries |
| Audit | Allowlisted action metadata, IDs, duration, provider usage when supplied; no raw dialogue or tool content | Audit allowlist/retention tests; private database storage |
| Operations | Authenticated budget snapshot and up to 100 recent audit events | `/api/admin/operations`; process counters reset after restart |
| Readiness | `/api/health` checks database availability without exposing keys or probing a billable model | Synthetic endpoint tests; `provider_configured` is configuration presence, not provider uptime |
| Actual model integration | Official DeepSeek Chat Completions adapter, non-thinking mode, strict response parsing, no mock fallback | Eight synthetic scenarios, ten actual API calls; [model evidence](evidence/live-deepseek-2026-10-09.json) |

Account identity is not organization tenancy, multi-role RBAC, SSO, or a distributed authentication service. The reviewer role remains the single server administrator with explicit per-session permission.

## Run profiles

### Local demonstration

`HARBOR_AUTH_MODE=local_demo` remains the default so an owner can inspect the app on the backend machine without preconfigured passwords. Sessions use anonymous capability handles on this loopback-only surface. Account-owned data cannot be accessed from this profile.

### Account demonstration

1. Stop the backend and make a private consistent SQLite backup.
2. Set `HARBOR_AUTH_MODE=accounts` in the server's ignored `.env`.
3. Provision an adult account with `python scripts/provision-user.py`. The script prompts for a password without echoing it. No password is preset.
4. Initialize the separate administrator on localhost using the owner's chosen password.
5. Restart; confirm `/api/status` reports accounts mode and self-registration disabled.
6. Log in from the APP using the provisioned user account. Verify another synthetic user's IDs return 404.

Remote host configuration refuses to start with `local_demo`. Remote demonstrations additionally require explicit HTTPS origins/hosts and a 32-character or longer demo access code. These controls are necessary conditions; public deployment still requires the remaining checklist below. No deployment was performed for this release.

## Actual data inventory

| Store | Contents | Current lifecycle |
| --- | --- | --- |
| SQLite users/tokens | User ID, username, password hash/salt, adult flag, token hash and expiry/revocation | Tokens expire/revoke; account erasure/reset and automatic expired-token cleanup remain planned |
| SQLite sessions/messages/turns | Persona snapshot, dialogue, action/observation traces and completed-turn result | User clears history or deletes sessions; history removal also removes reviews. Historical dialogue/traces are separate from structured memory |
| Approved-memory spaces | Confirmed facts and correction revision | Shared only within one owner after explicit source selection; last-session deletion removes the orphaned space |
| Process memory | Unapproved proposals | Thirty-minute expiry, lost on restart; not persisted as structured facts |
| Audit events | Pseudonymous IDs, action, permitted numeric/status metadata | Default 30 days; configured 1–90 days; cleanup currently occurs at app startup |
| Local backups | Private consistent database snapshots | Kept outside Git; no automatic backup schedule or secure erasure promise |
| Model provider | Recent context, approved facts and relevant tool results sent with a model request | Governed by the chosen provider; server-local storage does not mean local model inference |
| Frontend | Session-scoped user token and backend connection; session entry handles per backend/user | Logout/expiry/backend switch clears private UI and cancels in-flight user requests; no private API/PWA caching |

The audit is redacted, not anonymous: persistent pseudonymous IDs can correlate activity within a server. Backups and prior exports require their own retention rules. Removing a structured memory does not rewrite dialogue in which it was previously mentioned.

## Remaining gates before public or enterprise operation

- Owner-scoped complete export and account erasure, explicit deletion inventory, automated retention and a disposable-data restore drill.
- Response feedback/reporting → permissioned review → triage → regression linkage. Existing admin annotations are not this complete workflow.
- A reviewed deployment profile with TLS termination, request-body limits at ingress, trusted proxy handling, encrypted backup storage and secret rotation procedure.
- An external or shared limiter, account/token lifecycle controls, and database migration/versioning appropriate for multiple workers. Current admission and locks are process-local.
- Measured load/concurrency tests, failure recovery, availability objectives and alerting. There is no production latency, p95, uptime, cost forecast, RPO/RTO or SLA claim.
- Human-reviewed real-model persona, empathy, romance, memory conflict and adversarial scenarios beyond the eight initial inputs. Automatic completion is not a quality grade.
- Physical Android installation and keyboard/back-navigation/rotation/reconnect/HTTPS checks for the current APK. Browser breakpoint checks do not replace this.

No public service, commercial customer, payment workflow, user volume, voice/avatar runtime, autonomous outreach, or certified compliance is claimed.

## Next bounded iteration

1. Complete the owner data lifecycle and response-feedback contracts on synthetic accounts.
2. Import approved synthetic/de-identified evaluation artifacts into a versioned DataAgent dataset; preserve denominator, query plan and independent arithmetic checks.
3. Review the actual model transcripts, repair one measured weakness, and rerun the same versioned scenarios; separately obtain physical-device evidence.
