"""Consistent private SQLite snapshots and disposable, non-overwriting recovery drills."""
import argparse
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data"
DATABASE_SUFFIXES = {".sqlite3", ".sqlite", ".db"}
CORE_SCHEMA = {
    "sessions": {"id", "mode", "created"},
    "messages": {"id", "session_id", "role", "content", "emotion", "created"},
    "memories": {"id", "session_id", "content", "status", "created"},
    "turns": {"id", "session_id", "request_id", "provider", "response", "created"},
}
ACCOUNT_SCHEMA = {
    "users": {"id", "username", "password_hash", "salt", "active", "adult_confirmed", "created"},
    "user_tokens": {"token_hash", "user_id", "expires_at", "created", "revoked_at"},
}
MEMORY_SCHEMA = {
    "memory_spaces": {"id"},
    "approved_memories": {"id", "space_id", "content", "created", "updated", "revision"},
}
OPTIONAL_SCHEMA = {
    "characters": {"id", "name", "system_prompt", "greeting", "enabled", "revision"},
    "administrators": {"id", "username", "password_hash", "salt", "created"},
    "reviews": {"id", "session_id", "run_id", "persona_score", "empathy_score", "memory_score", "provider", "created"},
    "audit_events": {"id", "actor_id", "action", "target_id", "metadata", "created"},
}
PRIMARY_KEYS = {"sessions": "id", "messages": "id", "memories": "id", "turns": "id",
                "users": "id", "user_tokens": "token_hash", "memory_spaces": "id", "approved_memories": "id",
                **{name: "id" for name in OPTIONAL_SCHEMA}}


class BackupError(ValueError):
    """Sanitized operator error; never includes a row, credential, or database content."""


def _database_path(value, *, must_exist):
    if "\x00" in str(value):
        raise BackupError("Database path contains an invalid character.")
    path = Path(value).expanduser()
    if path.suffix.lower() not in DATABASE_SUFFIXES or any(part.lower().startswith(".env") for part in path.parts):
        raise BackupError("Only explicitly named SQLite database files are allowed; environment/key files are prohibited.")
    if path.is_symlink():
        raise BackupError("Database symlink paths are prohibited.")
    try:
        resolved = path.resolve(strict=must_exist)
    except (OSError, ValueError):
        raise BackupError("The explicitly named database path is unavailable.") from None
    if must_exist and not resolved.is_file():
        raise BackupError("The source must be an existing regular database file.")
    return resolved


def _identity(path):
    current = path.stat(follow_symlinks=False)
    return current.st_dev, current.st_ino


def _remove_owned_file(path, identity):
    """Delete only the exact temporary file we created, never a replacement or a tree."""
    try:
        if _identity(path) == identity and not path.is_symlink():
            path.unlink()
    except FileNotFoundError:
        pass


def _connection(path, *, readonly=False):
    uri = path.as_uri() + ("?mode=ro" if readonly else "?mode=rw")
    connection = sqlite3.connect(uri, uri=True, timeout=2)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    if readonly:
        connection.execute("PRAGMA query_only=ON")
    return connection


def validate_database(connection):
    """Accept known companion schema shapes, including pre-account snapshots."""
    integrity = connection.execute("PRAGMA integrity_check(1)").fetchall()
    if integrity != [("ok",)]:
        raise BackupError("Database integrity validation failed.")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise BackupError("Database foreign-key validation failed.")
    objects = connection.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    tables = {name for kind, name, _sql in objects if kind == "table"}
    # A token-deletion trigger could mutate other restored data. Harbor does not require triggers.
    if any(kind == "trigger" for kind, _name, _sql in objects):
        raise BackupError("Database triggers require explicit compatibility review before recovery.")
    expected = dict(CORE_SCHEMA)
    has_accounts = bool(tables & set(ACCOUNT_SCHEMA))
    has_approved = bool(tables & set(MEMORY_SCHEMA))
    if has_accounts:
        expected.update(ACCOUNT_SCHEMA)
    if has_approved:
        expected.update(MEMORY_SCHEMA)
    expected.update({name: fields for name, fields in OPTIONAL_SCHEMA.items() if name in tables})
    for table, required in expected.items():
        if table not in tables:
            raise BackupError("Database is missing a required companion table.")
        info = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        columns = {row[1] for row in info}
        if not required <= columns or not any(row[1] == PRIMARY_KEYS[table] and row[5] for row in info):
            raise BackupError("Database table columns or primary key are incompatible.")
    counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in expected}
    fingerprint = hashlib.sha256(json.dumps(objects, ensure_ascii=False).encode()).hexdigest()
    return {"integrity": "ok", "foreign_key_errors": 0,
            "schema_profile": "accounts" if has_accounts else "legacy_preaccounts",
            "approved_memory_schema": has_approved, "schema_fingerprint": fingerprint,
            "sqlite_user_version": connection.execute("PRAGMA user_version").fetchone()[0], "row_counts": counts}


def _snapshot(source, destination, *, restore, timeout_seconds=30):
    """Publish only a validated newly created snapshot, atomically without overwrite."""
    source = _database_path(source, must_exist=True)
    destination = _database_path(destination, must_exist=False)
    if source == destination:
        raise BackupError("Source and destination must be different files.")
    if destination.exists():
        raise BackupError("Destination already exists; it will not be overwritten.")
    if not destination.parent.is_dir():
        raise BackupError("Create a private destination directory explicitly before copying.")
    if not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 300:
        raise BackupError("Backup timeout must be between zero and 300 seconds.")
    deadline = time.monotonic() + timeout_seconds

    def deadline_check(*_arguments):
        if time.monotonic() > deadline:
            raise BackupError("Backup validation or copy exceeded its deadline.")

    temporary = destination.parent / (".harbor-snapshot-" + uuid.uuid4().hex + ".sqlite3")
    identity = None
    try:
        with closing(_connection(source, readonly=True)) as original:
            original.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            validate_database(original)
            # O_EXCL reserves the unpredictable temporary file; os.link publishes without replacing a race winner.
            descriptor = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                identity = _identity(temporary)
            finally:
                os.close(descriptor)
            with closing(_connection(temporary)) as output:
                output.execute("PRAGMA journal_mode=DELETE")
                output.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                original.backup(output, pages=64, progress=deadline_check, sleep=0.01)
                before = validate_database(output)
                stripped = before["row_counts"].get("user_tokens", 0) if restore else 0
                if restore and "user_tokens" in before["row_counts"]:
                    with output:
                        output.execute("DELETE FROM user_tokens")
                after = validate_database(output)
            deadline_check()
            # Windows FlushFileBuffers needs a writable handle even after SQLite has closed it.
            with temporary.open("r+b") as handle:
                os.fsync(handle.fileno())
            snapshot_hash = file_sha256(temporary)
            try:
                os.link(temporary, destination)
            except FileExistsError:
                raise BackupError("Destination was created concurrently; it was not overwritten.") from None
            except OSError:
                raise BackupError("Atomic non-overwriting publication failed; use a private local filesystem with hard-link support.") from None
            return {"operation": "restore_disposable" if restore else "backup", **after,
                    "user_tokens_removed": stripped, "source_modified": False,
                    "sha256": snapshot_hash,
                    "privacy": "Private database snapshot; may contain dialogue and password/token hashes. Do not upload."}
    except (sqlite3.Error, OSError):
        raise BackupError("SQLite snapshot failed; source content and raw errors are suppressed.") from None
    finally:
        if identity is not None:
            _remove_owned_file(temporary, identity)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_database(source, destination, *, timeout_seconds=30):
    return _snapshot(source, destination, restore=False, timeout_seconds=timeout_seconds)


def restore_database(source, destination, *, timeout_seconds=30):
    # There is intentionally no option to revive login tokens from a snapshot.
    return _snapshot(source, destination, restore=True, timeout_seconds=timeout_seconds)


def _private_cli_destination(value):
    destination = _database_path(value, must_exist=False)
    root = DATA_ROOT.resolve()
    if not root.is_relative_to(ROOT.resolve()) or not destination.is_relative_to(root):
        raise BackupError("CLI output must stay inside this project's ignored data directory.")
    if destination == (root / "harbor.sqlite3").resolve():
        raise BackupError("The live default database is not a disposable recovery destination.")
    return destination


async def _auth_accepts(auth, token):
    from fastapi import HTTPException
    from starlette.requests import Request

    request = Request({"type": "http", "headers": [(b"authorization", ("Bearer " + token).encode())]})
    try:
        await auth.require(request)
    except HTTPException as issue:
        if issue.status_code == 401:
            return False
        raise
    return True


def run_drill():
    """Use authored synthetic records only; no config/env imports or provider calls."""
    from types import SimpleNamespace
    from .store import Store
    from .user_auth import UserAuth

    parent = DATA_ROOT / "backup-drills"
    if not parent.resolve().is_relative_to(ROOT.resolve() / "data"):
        raise BackupError("Drill output cannot leave the ignored project data directory.")
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = parent / (stamp + "-" + uuid.uuid4().hex[:12])
    directory.mkdir(mode=0o700, exist_ok=False)
    source, backup, restored = (directory / name for name in ("synthetic.sqlite3", "backup.sqlite3", "restored.sqlite3"))
    store = Store(str(source))
    auth_settings = SimpleNamespace(user_token_minutes=60)
    auth = UserAuth(store, auth_settings)
    issued = []

    async def populate():
        for index in range(2):
            user = await auth.provision(f"synthetic-owner-{index}", "Authored-synthetic-password-971", True)
            sid = store.create("friend", owner_user_id=user["id"])["id"]
            store.memory_add(sid, f"Synthetic approved preference {index}: tea")
            issued.append(auth.issue(user)["access_token"])
        legacy = store.create("friend")["id"]
        store.memory_add(legacy, "Synthetic legacy local memory: walking")
        store.memory_add(legacy, "Synthetic process-only proposal: not backed up", "pending")

    asyncio.run(populate())
    original_hash = file_sha256(source)
    backup_result = backup_database(source, backup)
    backup_hash = file_sha256(backup)
    restore_result = restore_database(backup, restored)
    recovered = Store(str(restored))
    recovered_auth = UserAuth(recovered, auth_settings)
    original_tokens_valid = all(asyncio.run(_auth_accepts(auth, token)) for token in issued)
    old_tokens_rejected = all(not asyncio.run(_auth_accepts(recovered_auth, token)) for token in issued)
    checks = {"source_unchanged": file_sha256(source) == original_hash,
              "backup_unchanged_by_restore": file_sha256(backup) == backup_hash,
              "owners_preserved": restore_result["row_counts"]["users"] == 2,
              "sessions_preserved": restore_result["row_counts"]["sessions"] == 3,
              "approved_memories_preserved": restore_result["row_counts"]["approved_memories"] == 3,
              "original_tokens_still_valid": original_tokens_valid, "restored_tokens_revoked": old_tokens_rejected,
              "restored_token_table_empty": restore_result["row_counts"]["user_tokens"] == 0,
              "pending_proposals_not_persisted": recovered._proposal_snapshot() == [],
              "integrity_and_foreign_keys": restore_result["integrity"] == "ok" and restore_result["foreign_key_errors"] == 0}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "scope": "authored synthetic records only",
              "live_api_calls": 0, "directory": str(directory.relative_to(ROOT)),
              "backup": backup_result, "restore": restore_result, "checks": checks,
              "passed": all(checks.values()), "erasure_limit": "Retained snapshots can restore deleted records; no physical/cryptographic erasure claim."}
    report_path = directory / "report.json"
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("drill", help="Create, back up and restore fresh synthetic data only (default).")
    for name in ("backup", "restore"):
        command = commands.add_parser(name, help="Explicitly read a private database and create a NEW private output.")
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in {None, "drill"}:
            result = run_drill()
        else:
            destination = _private_cli_destination(args.destination)
            operation = backup_database if args.command == "backup" else restore_database
            result = operation(args.source, destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("passed", True) else 1
    except (BackupError, OSError, RuntimeError):
        print("Backup/recovery failed validation or could not create a private new output. Existing files were not overwritten; raw errors are suppressed.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
