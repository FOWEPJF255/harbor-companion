# User accounts and ownership

This iteration adds a small account layer to the existing FastAPI/SQLite application. It does not replace the Agent runtime, character snapshots, memory confirmation flow, or administration plane. Account ownership is the basis for signed-in access; an anonymous session UUID or shared demo code is not a user identity.

## Two explicit operating modes

| Mode | Intended use | Session access |
|---|---|---|
| `local_demo` | The existing single-owner localhost demonstration and synthetic regression fixtures | Existing anonymous capability handles; only unowned local-demo sessions |
| `accounts` | An authenticated pilot with distinct users on phone and desktop | User Bearer authentication and a matching server-side `owner_user_id` |

`HARBOR_AUTH_MODE` selects the mode. Remote hosting requires account mode in the application integration. The shared demo access code may remain an additional deployment gate; possession of that code never establishes the user or grants access to another user's session.

Public registration is **disabled by default** (`HARBOR_REGISTRATION_ENABLED=false`). Provision initial pilot users from the trusted management operation or CLI. Enable registration deliberately only when the intended enrollment, abuse limits, and operational support are ready.

The default user-token lifetime is 60 minutes (`HARBOR_USER_TOKEN_MINUTES=60`). The account implementation bounds a supplied lifetime between one minute and one day. The server checks expiry and account status on every protected request. This first increment requires login again after the token expires; there is no refresh-token, password-reset, email-verification, or SSO workflow.

## Authentication API

All routes return `Cache-Control: no-store`. JSON errors are sanitized and do not echo the submitted password or internal validation inputs. The login/register OpenAPI request schemas describe the fields even though the implementation wraps validation itself to avoid FastAPI's default error input echo.

| API | Input | Result |
|---|---|---|
| `POST /api/auth/register` | `username`, `password`, `adult_confirmed: true` | `{access_token, expires_in, user}` when registration is enabled |
| `POST /api/auth/login` | `username`, `password` | `{access_token, expires_in, user}` |
| `GET /api/auth/me` | User Bearer header | `{user, expires_in}` |
| `POST /api/auth/logout` | User Bearer header | Revokes the current login, then returns `{ok: true}` |

`user` exposes only `id` and `username`. Password hashes, salts, token hashes, and raw credentials never appear in the public user payload. Usernames are normalized to lowercase and restricted to ASCII letters, digits, `_`, `.`, and `-`; normalized length is 3–40. Passwords are 12–128 characters and are not trimmed.

Unknown usernames, incorrect passwords, and disabled accounts receive the same HTTP 401 message. Each login attempt performs the same PBKDF2 hashing work, including for an unknown account. Invalid JSON/schema inputs receive a generic HTTP 422; duplicate registration receives a generic HTTP 400 without raw database details. Closed registration receives HTTP 403. IP-based attempts beyond the local limit receive HTTP 429.

The socket peer provides the rate-limit key. User-supplied `X-Forwarded-For` does not change that key. This is a process-local limiter, not a distributed edge defense; a trusted reverse-proxy deployment needs its own reviewed forwarding and rate-limit configuration.

If registration is publicly enabled, a successful enrollment versus a rejected enrollment can still reveal whether a username can be used. Generic errors remove explicit account-existence disclosure; they do not justify a claim that arbitrary public signup is fully resistant to account enumeration.

## Credential storage and lifecycle

`UserAuth.ensure_schema(db)` creates:

```text
users
  id                   primary key, stable internal account identifier
  username             unique normalized ASCII username
  password_hash        PBKDF2-HMAC-SHA256 result
  salt                 random 16-byte salt, encoded as hex
  active               account-enabled flag
  adult_confirmed      explicit enrollment assertion
  created              timestamp

user_tokens
  token_hash           primary key, SHA-256 of the full opaque token
  user_id              foreign key to users, cascade on account removal
  expires_at           Unix timestamp
  created              timestamp
  revoked_at           nullable Unix timestamp
```

Password derivation uses 600,000 PBKDF2-HMAC-SHA256 iterations with an independently generated salt. This matches the existing local administration approach; it is an implementation choice rather than a claim of an external security audit. The password-storage guidance supports salted adaptive hashing and documents this PBKDF2 work factor. [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

Each login receives a new opaque `usr_` token with 32 random bytes of secret material. SQLite stores only its SHA-256 verifier. Authentication looks up that verifier, joins the account, and checks `active`, `expires_at`, and `revoked_at` every time. A stolen database containing only token hashes does not directly contain reusable raw login tokens; this does not protect a stolen browser token or a fully compromised server. [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

User tokens persist across an application restart, including their expiry and revocation state. Logout revokes only the current login. `UserAuth.revoke_user(user_id)` is available to trusted account lifecycle operations to invalidate every existing login. Disabling an account prevents protected requests immediately after the next database check; this does not assert cancellation of a provider call already in flight.

User and administrator tokens use separate mechanisms and authority checks. A management token is not accepted as a normal user's identity, and a user token does not confer administration privileges.

## Provision a pilot account

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/provision-user.py --username pilot-user --adult-confirmed
```

The script prompts for a password twice using `getpass`. Do not put the password on the command line, in a shell transcript, or into `.env`. It creates the user but prints no login token. The default database is `data/harbor.sqlite3`; pass `--database` when the running backend uses a deliberately selected different file.

The `--adult-confirmed` flag records the intended user's explicit assertion; it does not perform identity or age verification. The companion flow retains its per-session adult confirmation and disclosed AI identity.

The provision script does not load `.env`, contact a provider, or configure API credentials. It imports the Store and account module only.

## Session and memory ownership integration

The Store's additive migration adds `owner_user_id` to `sessions` and `memory_spaces`. Existing rows remain unowned so the old local demo can continue. **No first login or public signup silently claims existing data.** Unowned rows must not become remotely visible merely because a caller knows their UUID.

In account mode:

- The API takes the owner from `UserAuth.require(request)`, never from a body/query field supplied by the client.
- A session lookup, chat, cached response, memory add/approve/correct/delete, history clear, and session delete require the same owner.
- A list request returns the signed-in user's sessions from the server. Client-side UUID storage is a convenience, not authorization.
- Explicit `memory_from_session_id` sharing accepts only a source session and approved-memory space owned by that same user.
- Pending proposals remain in process memory, scoped to their session, and never become available to another user or shared pool before confirmation.
- Approved memory can be shared across one user's explicitly linked sessions. It cannot become shared across two accounts by supplying another account's handle.

The relevant integration points are `main.py`'s principal/owned-session guard and session routes, and `store.py`'s owned lookup, session list, `create`, and memory-space checks. The authentication module does not itself select another user's conversations. Server-side per-object authorization is required on every operation, even when object IDs are random. [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)

The administration plane remains distinct. An authenticated administrator does not automatically obtain raw user conversations from the former single-owner console. In account mode, `POST /api/sessions/{sid}/review-access` accepts `{allowed: true}` only from that session's owner. Raw inspection and review require this grant, and reviewer reads are recorded in a content-free audit event. Changing the grant to `false` denies subsequent inspection/review and removes stored review notes for the session because they may quote dialogue. Revocation cannot erase a transcript that an operator has already seen.

The account session list uses server-side keyset pagination through `GET /api/sessions?cursor=...`. The cursor identifies an ordering position, not permission to read another user's records. Session creation rejects a caller-supplied `owner_user_id`; ownership comes only from the authenticated account. Unknown, foreign-owned, and legacy unowned resources receive the same session-not-found response in account mode.

## Client behavior

The phone/desktop client must:

1. Keep a user token in current runtime memory; avoid baking credentials into an APK or persisting them in ordinary localStorage.
2. Obtain the public identity from `/auth/me` and the current user's server-side session list after login.
3. Partition convenience cache keys by **backend plus user ID**; anonymous demo keys must remain separate.
4. Clear displayed messages, memories, traces, drafts, pending retries, and editing state on logout, account switch, token expiry, or backend change.
5. Reject late responses from a preceding account/backend using the same request-epoch technique already used for backend switching.
6. Revoke the current server token on logout and clear local state even if that request cannot reach the service.

This provides server-backed ownership and the basis for account access across devices. It does not by itself demonstrate physical-phone synchronization, secure native credential persistence, or a public deployment. Those require separate observed evidence.

## Verification and acceptance boundary

`tests/test_user_auth.py` first runs the account module and router over an isolated temporary SQLite adapter, without importing application provider configuration. It checks sanitized validation, lowercase/ASCII usernames, strict adult confirmation, disabled registration, provisioning without a token, generic login errors, salt/hash storage, token expiry/revocation, disabled-account rejection, malformed/admin-shaped token rejection, socket-IP rate limits, and restart persistence.

The observed combined run on 2026-10-09 completed **75 passed, one dependency deprecation warning, in 25.62 seconds**: 38 isolated account-module checks and 37 integrated API/ownership checks. This is the result of the command below; it is separate from the root agent's complete project regression run.

`tests/test_account_isolation.py` uses two genuinely distinct synthetic users and known session/memory handles. It verifies rejection for another user's session read, chat, cached retry, list IDs, shared-memory source, manual memory add, proposal approval, correction, deletion, history clear, and session deletion. Positive checks cover same-user explicitly shared approved memory, non-sharing of pending proposals, legacy local-demo compatibility, and account-owned keyset pagination without duplicates or foreign sessions. Management/user token separation, default-denied reviewer access, owner grant, revocation and note deletion, content-free audit records, and sanitized administrator provisioning are included.

Use synthetic accounts and dialogue only. No real provider call is required to establish ownership isolation. Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_user_auth.py tests/test_account_isolation.py -q --tb=short --basetemp=data/pytest-account-auth-unique-run-id
```

Passing those checks is evidence of the implemented account/authorization contracts. It is not a penetration-test report, a scale result, a privacy certification, a real-model dialogue score, or proof that the application is ready for unrestricted public registration. Single-host SQLite, process-local pending proposals and rate limits, no password recovery/SSO, and the unmeasured device/model behavior remain explicit boundaries.
