# Owner data lifecycle

Implemented increment: v0.5, 2026-10-09. These controls apply to the `accounts` profile and to the authenticated owner. They are not an organization compliance certification or a physical-erasure guarantee. The default loopback `local_demo` profile still provides session/history controls rather than an account to erase.

## User flow

Open **My space → Export or delete my account** after signing in. The same labels, consequences, errors and status messages are available in Chinese and English. Language switching does not log the user out. Passwords are password inputs, are cleared after an attempt/unmount, and are not written to application storage.

1. **Export:** re-enter the current password, request a JSON download, and check the browser's download list. The downloaded file is private. A browser/OS password manager or download directory is outside application storage control.
2. **Delete:** read the consequences, re-enter the current password and type the exact string `DELETE`. Submit the explicit deletion button. There is no model tool or automatic workflow that can delete the account.
3. A successful deletion invalidates every login for that account, clears the app identity and private interface, and leaves a translated success notice. Another user's data and the separate administrator account remain intact.

Browser compilation and HTTP contract checks do not prove the current UI or Android WebView download has been visually accepted. If a native container cannot save the download, the UI directs the user to sign in to the same backend in a supported browser. A native file-sharing integration has not been implemented.

## HTTP contracts

| Endpoint | Explicit input | Permission and result |
| --- | --- | --- |
| `POST /api/account/export` | `{"password":"<current password>"}` | Current user bearer token and password; fixed-name JSON attachment, `Cache-Control: no-store` |
| `DELETE /api/account/me` | `{"password":"<current password>","confirmation":"DELETE"}` | Same reauthentication plus exact confirmation; successful result contains `ok: true` |

Bodies are parsed within the authentication parser's 4 KiB limit, reject unknown fields, and never echo invalid input. The server derives the owner from the bearer token; there is no client-supplied target user ID. The socket-peer authentication admission limit also covers reauthentication attempts. Password checking uses the existing off-thread password hash and does not issue another token. The current token is checked again after that await and after asynchronous export preparation.

Incorrect current passwords return 403 and preserve the current login. An expired, revoked or erased user's token returns 401. Invalid input returns sanitized 422; incorrect confirmation returns 400. Database conflicts return sanitized 409. No password, raw exception or database path is returned.

## Export inventory and limits

The JSON uses `format_version: "1.0"`, an export timestamp, the public user profile, and flat arrays. The snapshot contains all owned rows within the stated byte limit, independent of the chat UI's 100-message read window or session-list pagination.

| Section | Included | Excluded |
| --- | --- | --- |
| `user` | ID, username, creation time, recorded adult-confirmation flag | Password hash, salt, token hashes and bearer tokens |
| `sessions` | IDs, mode, timestamps, character name/revision/greeting/profile snapshot, memory-space reference, language, reviewer permission | System/persona prompt, other owners and anonymous legacy sessions |
| `session_summaries` | Attributed bounded excerpts of owned session history, serialized as JSON text | Other sessions and approved-memory promotion |
| `messages` | All owned dialogue messages | Other users' messages |
| `turns` | Owned completed turns, public result, provider/usage/latency and permitted action/observation fields | Hidden reasoning, credentials, prompts, unapproved proposal content |
| `memory_spaces`, `approved_memories` | Owned spaces and confirmed facts with revisions | Process-only pending proposals |
| `reviews` | Notes/scores linked to owned sessions | Other owners' reviews |
| `audit` | Available attributable redacted events; administrator identity represented by a role label | Raw administrator credentials/identity, unrelated events |

This is a filtered personal-data export, not a database backup. Ordinary dialogue can contain facts that were also proposed as memories; excluding structured proposals does not remove those dialogue messages. Audit retention may already have removed older events.

SQLite `BEGIN` provides one read snapshot. Rows are read incrementally and checked against a **16 MiB UTF-8 JSON budget**. Oversized rows are rejected before Python materializes their full content. If the export does not fit, HTTP 413 returns a clear error and **no partial attachment**. Nothing is silently truncated or persisted as an export file on the server. Larger export jobs/chunking are a future capability; do not describe the limit as unlimited export.

Each application router admits at most two active snapshot workers. A third receives 429 with a retry hint. The worker releases its permit in `finally`; cancelling the HTTP caller does not release a still-running worker's permit early. This is a single-process preparation limit, not a distributed limiter or measured network/backpressure guarantee.

## Deletion inventory and concurrency

Within one write transaction the server removes the owner's sessions and cascading messages/summaries/turns/reviews, owned approved-memory spaces/facts, all user tokens, attributable audit events and the user row. Shared memory remains within one owner, so deletion removes that owner's linked sessions together. A failure rolls back database changes and preserves the process-only proposals.

After commit it clears only the erased sessions' pending proposals, drops their session-lock registry entries and removes the user's in-memory admission key. IP-based security-attempt windows do not contain the user ID and remain until their short expiry. Other users, anonymous legacy sessions, seed characters and the management account remain.

New session creation and completed-turn persistence check the owner/session in a write transaction. Chat success and failure paths recheck the current token/session after the model await; synthetic analysis rechecks the token before publishing its result. Already queued work rechecks the session after acquiring its mutex. An erased account therefore cannot receive a newly committed turn, proposal, or recreated user audit from a late model result. A model request already sent to a provider cannot be unsent by local deletion.

New audit rows include a server-derived `subject_user_id` with cascading account deletion. This attribution survives earlier deletion of the source session. The additive migration backfills only ownership that existing rows prove; older actor/target relationships are also used by export/deletion. An imported orphan administrator log with no surviving ownership evidence cannot safely be assigned to a person and is left to the audit-retention policy. No guess is used to erase another person's records.

## Retention actually implemented

| Data | Policy |
| --- | --- |
| Unapproved proposals | Process RAM only; 30-minute lifetime; lost on restart; expiry checked during access/maintenance |
| User tokens | Expired or revoked rows removed at startup and at most hourly on API activity |
| Audit events | `HARBOR_AUDIT_RETENTION_DAYS`, default 30, bounded 1–90 via environment loading; same startup/hourly-on-request cleanup |
| Dialogue and approved memories | Retained until explicit history/session/memory/account deletion; no undisclosed timed chat deletion |
| Backups and downloaded exports | Separate private copies; operator/user retention and purge required |

There is no background sweeper on an idle server. Single-process request activity triggers hourly cleanup, rather than a guaranteed deletion exactly at an idle wall-clock deadline.

## Recovery and remaining limits

See [backup/recovery](data-backup-recovery.md) for the authored-synthetic drill, exclusive new destinations, integrity/schema checks and forced removal of restored login tokens. Retained snapshots may contain deleted records and password hashes. Restoring one can resurrect those records even though old bearer tokens are removed. An erasure ledger, snapshot-purge automation, encrypted backup service and recovery orchestration are not implemented.

SQLite row deletion is logical deletion. It does not guarantee secure overwriting of database free pages, journals, filesystem snapshots, provider copies or user downloads. The app makes no cryptographic/physical erasure or regulatory compliance claim. Production use additionally needs the remaining [readiness gates](enterprise-readiness.md).

## Reproduce engineering checks

Run the lifecycle, race and backup test modules against a fresh ignored temporary directory, followed by the full suite and frontend build. Only authored synthetic accounts are erased in these checks. The recorded commands, results and any repairs live in [evidence](evidence.md). Real companionship quality, browser visual acceptance and physical-phone acceptance are separate evidence stages.
