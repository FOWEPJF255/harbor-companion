# Private SQLite backup and disposable recovery

Updated: 2026-10-09, Asia/Shanghai.

## Purpose and boundary

`server/harbor/backup.py` provides consistent SQLite snapshots, validation, a restore into a **new file**, and an authored-synthetic recovery drill. It does not select the configured live database, replace a running database, delete an owner's files, deploy a server, or call a model API.

The default command creates fresh synthetic records under ignored `data/backup-drills/<unique>/`. It does not import the configuration loader or read `.env`. A private source is read only when an operator supplies its exact path to the explicit `backup` or `restore` command.

Backing up a database is an operator action over all its rows. It is different from a per-user export. A private snapshot may contain conversation content, approved memories, usernames, password hashes, token hashes, reviews, audit records, and legacy session handles. Keep it under the database's access protections; do not upload it to GitHub, a public website, an AI knowledge base, or an ordinary demo evidence package.

## Default synthetic drill

From the project root:

```powershell
.\scripts\backup-drill.ps1
```

The wrapper temporarily supplies the local Python package path, runs `python -m harbor.backup drill`, and restores the prior Python path. The module's no-subcommand behavior also runs the same synthetic drill.

Each drill creates a fresh, unique directory:

```text
data/backup-drills/<UTC timestamp>-<random suffix>/
├── synthetic.sqlite3
├── backup.sqlite3
├── restored.sqlite3
└── report.json
```

The fixture provisions two authored owners, their sessions and approved memories, plus one legacy ownerless local session. It issues temporary synthetic user credentials only in process memory; raw credentials and passwords are absent from `report.json`.

The drill checks:

- Two owners, three sessions, and three approved memories survive the restore.
- Source and backup file hashes remain unchanged by the copy/restore actions.
- The original synthetic login tokens still work against the source.
- The same old tokens are rejected with HTTP 401 by the restored authentication service.
- The restored `user_tokens` table is empty.
- Process-only pending memory proposals do not reappear after opening the restored store.
- Database integrity and foreign-key checks pass.

The report records counts, hashes, schema fingerprint, checks, and zero API calls. These demonstrate a local synthetic recovery flow, not production durability, availability, encryption, or recovery-time guarantees.

## Explicit private snapshot and disposable restore

The following commands read only the source explicitly supplied by the operator. Example names deliberately avoid the owner's live database. Create a private destination directory first; neither operation creates arbitrary directory trees or overwrites a target.

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'server'
.\.venv\Scripts\python.exe -m harbor.backup backup --source 'data\operator-selected.sqlite3' --destination 'data\private-recovery\snapshot-new.sqlite3'
.\.venv\Scripts\python.exe -m harbor.backup restore --source 'data\private-recovery\snapshot-new.sqlite3' --destination 'data\private-recovery\restored-new.sqlite3'
```

The two explicit commands require both `--source` and `--destination`. Use them only when authorized to read that source and when its output directory is private. Do not turn an untrusted web request into these filesystem arguments.

CLI destinations must resolve inside this project's ignored `data/` directory. The default live `data/harbor.sqlite3` is prohibited as a recovery destination. File suffixes are limited to `.sqlite3`, `.sqlite`, and `.db`; `.env` paths and key-file formats are refused. Direct file symlinks are refused. Source/destination equality and existing destinations are refused.

The Python functions `backup_database(source, destination)` and `restore_database(source, destination)` accept explicitly supplied paths for controlled tests/operator integrations. Unlike the CLI, the library does not choose or constrain an output to the project data directory. Its caller must supply a private directory; it retains all file-type, no-overwrite, source equality, schema, integrity, and token-revocation checks.

Do not automatically promote `restored-new.sqlite3` to the live service. Any actual replacement needs a separate, approved maintenance decision: stop writes, check schema/application compatibility, reconcile post-snapshot deletions, verify private permissions and configuration, then select the reviewed file through the normal deployment process. This tool intentionally does not perform that replacement.

## Copy and validation contract

1. Open the explicit source read-only, with SQLite query-only mode and trusted schema disabled.
2. Validate integrity, foreign keys, and supported companion table/primary-key/column shapes.
3. Reserve an unpredictable temporary file with exclusive creation.
4. Use the SQLite online backup API to copy a consistent committed snapshot, including committed WAL state. Do not copy only the live main file with a generic filesystem command.
5. Validate the copied snapshot. During restore, delete all rows from `user_tokens`, then validate again.
6. Flush the new snapshot and publish it using an atomic, non-overwriting hard link. A target created concurrently wins; its contents remain untouched.
7. Remove only the exact temporary file created by this operation, with an identity check. No recursive cleanup or deletion of source/other existing files occurs.

The default validation/copy deadline is 30 seconds; the library permits a bounded explicit value up to 300 seconds. A corrupt, foreign-key-inconsistent, incompatible, or timed-out database is rejected. SQLite errors are sanitized instead of printing rows or credentials.

Atomic publication requires a private local filesystem with hard-link support; it passed on this Windows project's filesystem. An unsupported filesystem fails closed. Protected directory permissions remain necessary: no path-based tool can provide complete isolation in an attacker-writable directory. POSIX creation modes are restrictive; Windows privacy depends on inherited and configured ACLs. Files are not encrypted by this module.

Known profiles include the core pre-account companion tables and the account-enabled schema. Optional approved-memory and known management/audit tables are validated when present. Additive unknown tables are preserved and SQLite foreign keys are checked; arbitrary application semantics of unknown tables are not certified. Triggers are refused because token deletion could otherwise mutate additional restored data. The tool does not run application migrations on a private backup.

Legacy pre-account snapshots therefore remain legacy snapshots. A later application migration is a distinct operation; it must not be hidden in a backup check. Current-store opening in the default drill is safe because that fixture was created with the current synthetic schema.

## Credentials after recovery

`restore_database` always empties `user_tokens`; there is no preserve-token switch. This invalidates the database-backed user logins that existed at snapshot time and requires a fresh login. The source snapshot is unchanged and still contains its original token hashes.

This does **not** rotate password hashes, administrator credentials, provider API keys, environment-held access codes, or legacy session capability handles. Model keys and `.env` files are not part of this backup workflow. Process-local administrator sessions are outside the SQLite snapshot. A service-recovery plan must separately review all remaining access mechanisms, especially before enabling legacy/local-demo access to restored private sessions.

Removing token rows is logical revocation. It is not a claim that old hash bytes have been physically overwritten on the storage device.

## Retention and account-erasure limits

The market research in `market-requirements-2026-10-09.md` §5.5 calls for a data inventory, scoped deletion, retention, safe snapshots, and a way to avoid restoring erased data. This increment supplies the consistent-snapshot and disposable-recovery parts.

| Requirement | Current backup-tool behavior | Remaining limitation |
| --- | --- | --- |
| Consistent backup | SQLite online backup plus integrity/FK/schema validation | No production replication or durability/RPO/RTO guarantee. |
| No destructive restore | New destination only, including concurrent target creation | Live service replacement is a separate maintenance operation. |
| Old login invalidation | Restored user-token rows removed and old credentials rejected | Password/admin/environment/legacy-handle access requires separate review. |
| Private artifacts | Ignored data path for CLI/drill; no transcript or credential dump in reports | Ignore rules do not provide encryption or ACL enforcement. |
| Snapshot expiry | Every output is explicit and uniquely named | No automated snapshot TTL, inventory, or scheduled purge is implemented. |
| Account erasure across snapshots | Limitation is explicit | No deletion ledger is replayed by this restore tool; retained snapshots can reintroduce accounts, history, memories, feedback, or audit records erased later. |
| Physical erasure | No claim is made | SQLite deletion, file deletion, and token-table clearing do not prove physical zeroization, SSD erasure, or cryptographic erasure. |

Before using private snapshots operationally, the owner must define a manual retention/purge policy with snapshot locations, authorized operators, retention dates, account-erasure handling, and restore approval. Inventory external copies, synchronized folders, off-machine backups, and cloud version history too. Do not claim that deleting current rows or an active account erased every retained copy.

If a deleted account's data must stay deleted after recovery, reconcile the snapshot against a protected post-snapshot deletion record before making the recovered service available. Until that mechanism is implemented and exercised, such restoration requires manual review and reapplication of deletions. This module does not silently invent a deletion ledger or automatically purge an owner's snapshots.

## Evidence recorded on 2026-10-09

- `tests/test_backup.py`: **18 offline checks passed**, using a fresh ignored test directory and no live database/API.
- Checks include source equality/hard-link alias, existing-target preservation, concurrent target race, failed-output cleanup, corruption, foreign-key violation, incompatible schema, trigger rejection, prohibited environment/key formats, pre-account preservation, committed WAL data, and old-login invalidation.
- Actual default wrapper drill: `data/backup-drills/20261009T065810069736Z-6dba1b3be580/report.json`.
- All ten recorded drill checks passed; two user-token rows were removed from the restored copy; integrity and foreign keys passed; API calls were **zero**.

These are local synthetic results. Private recovery, account-erasure reconciliation, multi-device state, deployment recovery, and physical erasure have not been established by this evidence.
