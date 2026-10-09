"""Disposable SQLite recovery checks; never open the owner's configured database."""
import asyncio
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from harbor import backup
from harbor.store import Store
from harbor.user_auth import UserAuth


def synthetic_source(tmp_path):
    source = tmp_path / "synthetic.sqlite3"
    store = Store(str(source))
    with store.connect() as db:
        db.execute("INSERT INTO users VALUES('owner','synthetic-owner','synthetic-hash','00',1,1,'2026-10-09')")
    sid = store.create("friend", owner_user_id="owner")["id"]
    store.memory_add(sid, "Synthetic approved fact: tea")
    auth = UserAuth(store, SimpleNamespace(user_token_minutes=60))
    token = auth.issue({"id": "owner", "username": "synthetic-owner"})["access_token"]
    return source, store, sid, token


def assert_no_temporary_files(directory):
    assert list(directory.glob(".harbor-snapshot-*")) == []


def test_snapshot_and_restore_preserve_data_and_revoke_credentials(tmp_path):
    source, store, sid, token = synthetic_source(tmp_path)
    source_hash = backup.file_sha256(source)
    snapshot, restored = tmp_path / "backup.sqlite3", tmp_path / "restored.sqlite3"
    saved = backup.backup_database(source, snapshot)
    snapshot_hash = backup.file_sha256(snapshot)
    recovered = backup.restore_database(snapshot, restored)
    assert saved["row_counts"]["user_tokens"] == 1
    assert recovered["row_counts"]["user_tokens"] == 0 and recovered["user_tokens_removed"] == 1
    assert recovered["integrity"] == "ok" and recovered["foreign_key_errors"] == 0
    assert recovered["schema_fingerprint"] == saved["schema_fingerprint"]
    auth_settings = SimpleNamespace(user_token_minutes=60)
    assert asyncio.run(backup._auth_accepts(UserAuth(store, auth_settings), token)) is True
    restored_store = Store(str(restored))
    assert asyncio.run(backup._auth_accepts(UserAuth(restored_store, auth_settings), token)) is False
    assert restored_store.session(sid)["owner_user_id"] == "owner"
    assert restored_store.memories(sid, "approved")[0]["content"] == "Synthetic approved fact: tea"
    assert backup.file_sha256(source) == source_hash and backup.file_sha256(snapshot) == snapshot_hash
    assert_no_temporary_files(tmp_path)


@pytest.mark.parametrize("operation", [backup.backup_database, backup.restore_database])
def test_existing_target_is_never_overwritten(tmp_path, operation):
    source, *_ = synthetic_source(tmp_path)
    destination = tmp_path / "owner-existing.sqlite3"
    destination.write_bytes(b"authored-existing-file-marker")
    before = backup.file_sha256(destination)
    with pytest.raises(backup.BackupError):
        operation(source, destination)
    assert backup.file_sha256(destination) == before
    assert_no_temporary_files(tmp_path)


def test_source_destination_equality_and_hardlink_alias_are_rejected(tmp_path):
    source, *_ = synthetic_source(tmp_path)
    original = backup.file_sha256(source)
    with pytest.raises(backup.BackupError):
        backup.backup_database(source, source)
    alias = tmp_path / "alias.sqlite3"
    backup.os.link(source, alias)
    with pytest.raises(backup.BackupError):
        backup.restore_database(source, alias)
    assert backup.file_sha256(source) == original


def test_concurrent_target_creation_wins_without_overwrite(tmp_path, monkeypatch):
    source, *_ = synthetic_source(tmp_path)
    target = tmp_path / "race.sqlite3"
    original_link = backup.os.link

    def race(temporary, destination):
        with Path(destination).open("xb") as handle:
            handle.write(b"other-owner-race-winner")
        original_link(temporary, destination)

    monkeypatch.setattr(backup.os, "link", race)
    with pytest.raises(backup.BackupError):
        backup.backup_database(source, target)
    assert target.read_bytes() == b"other-owner-race-winner"
    assert_no_temporary_files(tmp_path)


def test_failed_snapshot_validation_removes_only_new_temporary_file(tmp_path, monkeypatch):
    source, *_ = synthetic_source(tmp_path)
    original = backup.file_sha256(source)
    validate = backup.validate_database
    calls = 0

    def fail_copied_snapshot(connection):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise backup.BackupError("Injected synthetic validation failure")
        return validate(connection)

    monkeypatch.setattr(backup, "validate_database", fail_copied_snapshot)
    target = tmp_path / "failed.sqlite3"
    with pytest.raises(backup.BackupError):
        backup.backup_database(source, target)
    assert not target.exists() and backup.file_sha256(source) == original
    assert_no_temporary_files(tmp_path)


def test_corrupt_database_is_rejected_without_published_output(tmp_path):
    source = tmp_path / "corrupt.sqlite3"
    source.write_bytes(b"Synthetic invalid SQLite header")
    target = tmp_path / "rejected.sqlite3"
    with pytest.raises(backup.BackupError):
        backup.backup_database(source, target)
    assert not target.exists()


def test_foreign_key_failure_is_rejected(tmp_path):
    source, *_ = synthetic_source(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("INSERT INTO approved_memories VALUES('orphan','missing-scope','synthetic', 'date','date',1)")
    with pytest.raises(backup.BackupError):
        backup.backup_database(source, tmp_path / "rejected.sqlite3")


def test_incompatible_companion_schema_is_rejected(tmp_path):
    source, *_ = synthetic_source(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("DROP TABLE messages")
        db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY,unrelated TEXT)")
    with pytest.raises(backup.BackupError):
        backup.backup_database(source, tmp_path / "rejected.sqlite3")


def test_triggered_database_is_not_restored(tmp_path):
    source, *_ = synthetic_source(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("CREATE TRIGGER mutate_on_revoke AFTER DELETE ON user_tokens BEGIN DELETE FROM approved_memories; END")
    with pytest.raises(backup.BackupError):
        backup.restore_database(source, tmp_path / "rejected.sqlite3")


@pytest.mark.parametrize("name", [".env", ".env.sqlite3", "model.key", "private.pem"])
def test_environment_and_key_file_paths_are_refused_before_read(tmp_path, name):
    with pytest.raises(backup.BackupError):
        backup.backup_database(tmp_path / name, tmp_path / "rejected.sqlite3")


def test_preaccount_snapshot_is_preserved_without_migration(tmp_path):
    source = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(source) as db:
        db.executescript("""
        CREATE TABLE sessions(id TEXT PRIMARY KEY,mode TEXT,created TEXT);
        CREATE TABLE messages(id INTEGER PRIMARY KEY,session_id TEXT REFERENCES sessions(id),role TEXT,content TEXT,emotion TEXT,created TEXT);
        CREATE TABLE memories(id TEXT PRIMARY KEY,session_id TEXT REFERENCES sessions(id),content TEXT,status TEXT,created TEXT);
        CREATE TABLE turns(id TEXT PRIMARY KEY,session_id TEXT REFERENCES sessions(id),request_id TEXT,provider TEXT,response TEXT,created TEXT);
        INSERT INTO sessions VALUES('legacy','friend','2026-10-09');
        INSERT INTO memories VALUES('fact','legacy','Synthetic legacy approved fact','approved','2026-10-09');
        """)
    original = backup.file_sha256(source)
    result = backup.restore_database(source, tmp_path / "legacy-restored.sqlite3")
    assert result["schema_profile"] == "legacy_preaccounts" and result["user_tokens_removed"] == 0
    assert "users" not in result["row_counts"] and result["row_counts"]["memories"] == 1
    assert backup.file_sha256(source) == original
    with sqlite3.connect(tmp_path / "legacy-restored.sqlite3") as db:
        assert db.execute("SELECT content FROM memories").fetchone()[0] == "Synthetic legacy approved fact"


def test_online_backup_captures_committed_wal_data(tmp_path):
    source, store, sid, _token = synthetic_source(tmp_path)
    with sqlite3.connect(source) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE approved_memories SET content='Synthetic committed WAL fact' WHERE space_id=(SELECT memory_scope FROM sessions WHERE id=?)", (sid,))
        writer.commit()
        assert Path(str(source) + "-wal").exists()
        target = tmp_path / "wal-snapshot.sqlite3"
        backup.backup_database(source, target)
        with sqlite3.connect(target) as copied:
            assert copied.execute("SELECT content FROM approved_memories").fetchone()[0] == "Synthetic committed WAL fact"


def test_cli_cannot_restore_into_live_or_public_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "ROOT", tmp_path)
    monkeypatch.setattr(backup, "DATA_ROOT", tmp_path / "data")
    for destination in (tmp_path / "data" / "harbor.sqlite3", tmp_path / "web" / "public" / "snapshot.sqlite3", tmp_path.parent / "outside.sqlite3"):
        with pytest.raises(backup.BackupError):
            backup._private_cli_destination(destination)


def test_default_drill_is_synthetic_isolated_and_revokes_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "ROOT", tmp_path)
    monkeypatch.setattr(backup, "DATA_ROOT", tmp_path / "data")
    report = backup.run_drill()
    assert report["passed"] and all(report["checks"].values())
    assert report["live_api_calls"] == 0 and report["scope"] == "authored synthetic records only"
    assert not (tmp_path / "data" / "harbor.sqlite3").exists()
    directory = tmp_path / report["directory"]
    assert directory.is_relative_to(tmp_path / "data" / "backup-drills")
    assert {path.name for path in directory.iterdir()} == {"synthetic.sqlite3", "backup.sqlite3", "restored.sqlite3", "report.json"}
    text = json.dumps(report)
    assert "Authored-synthetic-password-971" not in text and "usr_" not in text
    assert report["backup"]["row_counts"]["user_tokens"] == 2
    assert report["restore"]["user_tokens_removed"] == 2
