# Management console

## Decision

Use a small management plane within the existing FastAPI/SQLite app. A separate CMS is unnecessary for this single-owner prototype: it would add another service, authentication setup, schema synchronization, and maintenance surface. The user app and management UI share a backend while having separate routes and access rules.

This is a prototype management system, not a multi-tenant business platform. Third-party CRM, messaging accounts, HR outreach, and model-key entry in the browser are not included.

## Interface language

Use the Chinese/English selector on the login card or in the studio sidebar. It shares the companion app's persisted preference and updates interface copy, error/status messages, accessible labels and date formatting without ending a login or clearing drafts. Existing character text, conversation content and review notes are not translated or rewritten. If browser storage is unavailable, switching still works within the current page, but persistence cannot be guaranteed.

## Open and initialize

1. Run `scripts/start.ps1` with the default local configuration.
2. Open http://127.0.0.1:8765/admin (the app also supports `?view=admin`).
3. Create one administrator using a username of 3–40 ASCII letters/numbers/`_.-` and a password of 12–128 characters.
4. The password is stored as a salted PBKDF2 hash in the ignored SQLite database. The plaintext password is not written to a file or returned by the API.
5. Sign in again after a browser reload, backend restart, logout, or token expiry. Management tokens remain in React state, not localStorage.

Initialize the administrator **before** enabling additional remote hosts. Remote configuration disables browser bootstrap, including requests forwarded by a reverse proxy. This avoids treating proxy-loopback requests as local ownership proof.

## Modules

| Module | Capability | Boundary |
|---|---|---|
| Overview | Session/turn/memory counts, provider distribution, server latency | Mock and real-provider data must be distinguished; counts do not establish relationship quality |
| Characters | Create/edit persona, greeting, avatar palette, publish or archive | Fixed core identity/boundary instructions remain in code; old sessions retain snapshots |
| Sessions | Summary list and explicitly opened details | Login required; raw content is not fetched in the overview/list; only recent messages/turns are returned |
| Human review | Persona, empathy, memory scores plus a concrete note | Stored as human annotations, tied to actual session/provider metadata; mock scores cannot prove LLM quality |
| Provider status | Provider, model, configured flag, whether a credential is present | The model key is neither returned nor editable in the browser |
| Operations | Active/concurrency/request limits and up to 100 redacted audit events | Single-process counters reset after restart; no raw dialogue or tool content |

Each character update increments its revision. New conversations use the latest enabled revision. Existing conversations keep the character name, prompt, and greeting snapshot from creation. Archiving removes a character from new-session choices without rewriting its prior conversations.

Pending proposals are per session. Approved memories belong to an explicitly shared memory space within the same user. An unapproved proposal is not included in long-term memory retrieval, while the original text can still exist in recent message context.

Clearing conversation history also clears its human reviews, since review notes can quote the source messages. Approved memories remain only when the user chooses the history-only action. Full session deletion cascades to messages, memories, turns, and reviews.

## Privacy and access

- In accounts mode, administrators cannot read conversations or annotate them until the session owner explicitly grants reviewer access. Withdrawal hides further raw reads and deletes existing review notes. Local-demo records remain the single owner's legacy demonstration surface and are not automatically assigned to accounts.
- The console first lists summaries. Opening details is an explicit action following the privacy notice.
- API responses have `Cache-Control: no-store`. The PWA service worker does not cache API calls, conversations, or tokens.
- There is no bulk private-data export or generic SQL/browser/shell tool.
- Logout revokes the current token in the running process. Restart invalidates all existing administrator tokens.
- Login is rate-limited per socket address. Behind a proxy this can group users together; it is a prototype limit, not a distributed authentication service.
- The built-in console has a single administrator, no recovery email, RBAC, MFA, or shared-team invitation workflow. Preserve the local DB privately; do not manually clear credentials just to bypass access.

## API map

`/api/admin/setup-status`, `/bootstrap`, `/login`, `/logout`, `/overview`, `/characters`, `/sessions`, `/reviews`, `/provider-status`, `/operations`, `/users` (trusted account provisioning; never returns a token or password).

All management data operations require a signed, short-lived Bearer token. Remote deployments additionally require the deployment's demo access code in `X-Harbor-Access` for protected APIs. Neither is the model API key.
