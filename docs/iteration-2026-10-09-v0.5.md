# v0.5 owner-data lifecycle iteration

Date: 2026-10-09, Asia/Shanghai. Continued from the clean v0.4 checkout, existing requirements and market/readiness register. This increment closes the bounded current-server data lifecycle; it does not establish a production companion service.

## Implemented

1. Owner-only JSON export, current-password reauthentication, strict bounded/sanitized bodies, snapshot consistency and explicit 16 MiB limit with no partial attachment. Two active preparation workers maximum; cancellation retains a running worker's permit until completion.
2. Exact-confirmation account deletion, one SQL transaction, removal of shared owned memory spaces, every user token, owned conversations/reviews and attributable audit, then owned transient/runtime cleanup. Other accounts, administrator, characters and legacy anonymous records remain.
3. Current-token/session checks after model/analysis awaits; active-owner checks inside session creation and completed-turn transactions. Active and queued synthetic turns cannot recreate deleted replies, proposals or audit rows.
4. Server-derived audit subject provenance with cascading deletion and a conservative additive backfill. Legacy orphan ownership is not guessed.
5. Security-record cleanup at startup and hourly on API activity: expired/revoked user tokens and configured audit retention. Dialogue and approved facts are not silently put on a timed deletion policy.
6. Consistent SQLite backup, validation, non-overwriting new-file restore, forced restored-token removal and a synthetic recovery CLI/drill. No actual owner database was restored or account erased.
7. Bilingual accessible user-account panel, dynamic sanitized errors, reauthentication, JSON download and identity cleanup. Delayed Blob URL release avoids racing the requested browser download. Native download operation remains unverified.
8. Version 0.5.0 in Python/web/mobile metadata; Android version code 4. Updated lifecycle inventory, recovery procedure, architecture, demo, readiness and continuation records.

## Observed local checks

| Check | Actual result | Boundary |
| --- | --- | --- |
| Final Python suite | **321 passed**, one existing Starlette/httpx deprecation warning, **66.46 s** | Authored synthetic data/injected transports, no new live model calls |
| Lifecycle module | 33 passed, 22.37 s | Complete 240-message/120-turn/120-review export, byte/escaping limits, identity revocation, rollback, ownership, preparation admission/cancellation |
| Root race/operations focused run | 18 passed, 4.23 s | Active/queued success and failed runs, retention and durable audit provenance |
| Backup module | 18 passed | WAL consistency, corruption/schema/FK refusal, existing/racing target preservation, old-login invalidation |
| Independent application evaluator | **50/50**, zero live calls | [Detailed JSON](evidence/framework-v0.5-2026-10-09.json), [readable evidence](evidence/framework-v0.5-2026-10-09.md) |
| Actual synthetic backup/recovery wrapper | **10/10**, zero API calls | [Safe metadata report](evidence/backup-drill-v0.5-2026-10-09.json); two restored tokens removed |
| Frontend | TypeScript/Vite production build passed, 26 modules | Build only; no current visual acceptance |
| Running backend | v0.5 status, configured DeepSeek, DB ready, frontend HTTP 200 at localhost:8765 | Loopback local-demo profile; no model inference was triggered by readiness |
| Independent code review | No additional concrete ownership/erasure race defect identified | Review is supplementary, not a production-security certification |

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp=data/pytest-v05-20261009-final
.\.venv\Scripts\python.exe scripts/evaluate.py --output docs/evidence/framework-v0.5-2026-10-09.json
powershell -ExecutionPolicy Bypass -File scripts/backup-drill.ps1
cd web
npm run build
```

The backup wrapper was run twice on separately authored synthetic fixtures. The published report is from `data/backup-drills/20261009T065828631382Z-478aa766b8f6/report.json`. Its database contents/password hashes/tokens are not published.

## Repair and verification history

- Existing shared temporary-directory ACL trouble was avoided using a fresh ignored pytest base directory.
- The backup implementation initially attempted fsync through a read-only Windows handle; the operation now opens its newly created snapshot with a writable handle before flushing. Focused backup checks and the actual wrapper drill passed after repair.
- Reauthentication uses 403 for an incorrect current password, preserving login; current-token expiry/revocation remains 401. This avoids treating a password typo as logout.
- An independent lifecycle review found that export preparation also needed its own concurrency bound. The added worker-owned two-slot limit was checked under caller cancellation and repeated worker failure.
- The first broad run produced 288 passing tests before the newly authored lifecycle module/admission tests were included. It is not the final count. After source freeze, the full 321-test run above passed.
- Browser automation recovery still failed at its connection layer. No current browser screenshot or native download acceptance is asserted.
- The prior local server was stopped before the additive audit-schema migration, preventing its old positional audit INSERT from conflicting with the new column. A private consistent pre-lifecycle snapshot was validated at `data/backups/harbor-before-lifecycle-20261009-145413.sqlite3`. The updated server was restarted after the frontend build.

## Saved artifacts and limits

GitHub/Android build IDs, source snapshot, APK checksum and download are recorded in [app delivery](app-delivery.md) when those operations finish. This file's local-check table does not substitute for cloud or phone evidence. Runtime database, backups, downloads, reports and `.env` remain ignored; staged files/bundles are checked for common credential patterns and the actual locally configured provider secret without printing it.

The earlier eight-scenario/ten-request actual DeepSeek record remains the real-provider evidence. This iteration adds no human empathy/persona score, new API transcript, customer count, commercial deployment, HR outcome or SLA. Retained snapshots/downloads/provider copies need their own retention; logical deletion does not establish physical or cryptographic erasure.

## Next bounded work

1. Response feedback with owner-bound turn references, permissioned triage, explicit state transitions and regression-case linkage.
2. Versioned approved synthetic/deidentified evaluation imports for DataAgent; preserve denominator and independently checked arithmetic.
3. Human quality review of the existing real DeepSeek samples and physical-device review of the current APK. Backup TTL, deletion-ledger reconciliation, larger exports, password recovery and deployment/load controls remain visible readiness gaps.

No public deployment or HR message was sent.
