"""Owner-only bounded account export and transactional erasure."""
from datetime import datetime, timezone
import json
import logging
import sqlite3
from threading import BoundedSemaphore
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .user_auth import NO_CACHE, USER_BEARER, authentication_error, request_input

MAX_EXPORT_BYTES = 16 * 1024 * 1024
EXPORT_LIMIT_ERROR = "Account export exceeds the 16 MiB limit; no partial file was returned."
EXPORT_ERROR = "Account export could not be completed; no partial file was returned."
DELETE_ERROR = "Account deletion could not be completed; no data was deleted."
logger = logging.getLogger(__name__)


class Reauthentication(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    password: str = Field(min_length=12, max_length=128, repr=False, json_schema_extra={"format": "password"})


class ErasureInput(Reauthentication):
    confirmation: str = Field(max_length=20)


class ExportBudget:
    """A byte budget checked before each incremental JSON chunk is retained."""
    def __init__(self):
        self.data = bytearray()

    @property
    def remaining(self):
        return MAX_EXPORT_BYTES - len(self.data)

    def append(self, data):
        value = data.encode("utf-8") if isinstance(data, str) else data
        if len(value) > self.remaining:
            raise authentication_error(413, EXPORT_LIMIT_ERROR)
        self.data.extend(value)

    def json(self, value, depth=0):
        if depth > 128:
            raise ValueError("Stored export data is too deeply nested")
        if isinstance(value, str):
            self.append('"')
            for start in range(0, len(value), 4096):
                self.append(json.dumps(value[start:start + 4096], ensure_ascii=False)[1:-1])
            self.append('"')
        elif isinstance(value, dict):
            self.append("{")
            for index, (key, item) in enumerate(value.items()):
                if index:
                    self.append(",")
                self.json(key, depth + 1)
                self.append(":")
                self.json(item, depth + 1)
            self.append("}")
        elif isinstance(value, list):
            self.append("[")
            for index, item in enumerate(value):
                if index:
                    self.append(",")
                self.json(item, depth + 1)
            self.append("]")
        else:
            self.append(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")))


def _require_current(db, owner, token_hash):
    row = db.execute("""SELECT u.id,u.username,u.created,u.adult_confirmed FROM users u JOIN user_tokens t ON t.user_id=u.id
        WHERE u.id=? AND u.active=1 AND t.token_hash=? AND t.revoked_at IS NULL AND t.expires_at>?""",
        (owner, token_hash, time.time())).fetchone()
    if not row:
        raise authentication_error(401, "User login required.")
    return {"id": row["id"], "username": row["username"], "created": row["created"], "adult_confirmed": bool(row["adult_confirmed"])}


def _rows(db, table, columns, where, parameters, budget, *, prefix="", transform=None):
    """Preflight one row's UTF-8 source size, then fetch and encode that row only."""
    selected = ",".join(columns)
    sizes = "+".join(f"COALESCE(length(CAST({column} AS BLOB)),0)" for column in columns)
    cursor = db.execute(f"{prefix} SELECT rowid AS export_rowid,({sizes}) AS export_bytes FROM {table} WHERE {where} ORDER BY rowid", parameters)
    first = True
    for position in cursor:
        # Oversized database values are rejected before Python materializes them.
        if position["export_bytes"] > budget.remaining:
            raise authentication_error(413, EXPORT_LIMIT_ERROR)
        row = dict(db.execute(f"SELECT {selected} FROM {table} WHERE rowid=?", (position["export_rowid"],)).fetchone())
        if not first:
            budget.append(",")
        budget.json(transform(row) if transform else row)
        first = False


_PRIVATE_KEYS = {
    "password", "password_hash", "salt", "token", "token_hash", "access_token", "refresh_token",
    "api_key", "authorization", "credentials", "system_prompt", "character_prompt", "prompt", "system",
    "pending_proposals", "proposals", "reasoning", "reasoning_content", "chain_of_thought",
}


def _safe_value(value):
    if isinstance(value, dict):
        return {key: _safe_value(item) for key, item in value.items() if key.lower() not in _PRIVATE_KEYS}
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    return value


def _safe_turn(row):
    raw = json.loads(row["response"])
    if not isinstance(raw, dict):
        raise ValueError("Invalid stored response")
    response = {key: _safe_value(raw[key]) for key in ("run_id", "reply", "emotion", "provider", "usage", "latency_ms") if key in raw}
    response["trace"] = []
    if not isinstance(raw.get("trace", []), list):
        raise ValueError("Invalid stored trace")
    for event in raw.get("trace", []):
        if not isinstance(event, dict):
            raise ValueError("Invalid stored trace")
        fields = ("type", "name", "status", "step", "finish_reason", "duration_ms")
        if event.get("name") != "propose_memory":
            fields += ("input", "observation")
        response["trace"].append({key: _safe_value(event[key]) for key in fields if key in event})
    return {**row, "response": response}


def _audit_scope():
    # Explicit provenance survives deletion of the source session. Actor history
    # also recovers attributable targets from older records before that migration.
    prefix = """WITH owned_targets(id) AS (
        SELECT :owner UNION SELECT id FROM sessions WHERE owner_user_id=:owner
        UNION SELECT id FROM memory_spaces WHERE owner_user_id=:owner
        UNION SELECT id FROM approved_memories WHERE space_id IN (SELECT id FROM memory_spaces WHERE owner_user_id=:owner)
        UNION SELECT id FROM turns WHERE session_id IN (SELECT id FROM sessions WHERE owner_user_id=:owner)
        UNION SELECT target_id FROM audit_events WHERE (actor_id IN (:owner,:actor) OR subject_user_id=:owner) AND target_id IS NOT NULL
        UNION SELECT json_extract(CASE WHEN json_valid(metadata) THEN metadata ELSE '{}' END,'$.run_id') FROM audit_events
            WHERE (actor_id IN (:owner,:actor) OR subject_user_id=:owner)
                AND json_type(CASE WHEN json_valid(metadata) THEN metadata ELSE '{}' END,'$.run_id')='text')"""
    predicate = """(subject_user_id=:owner OR actor_id IN (:owner,:actor) OR target_id IN (SELECT id FROM owned_targets)
        OR (CASE WHEN json_valid(metadata) THEN json_extract(metadata,'$.run_id') END) IN (SELECT id FROM owned_targets))"""
    return prefix, predicate


def _safe_audit(row, owner):
    actor = row["actor_id"]
    row["actor_id"] = "user" if actor in {owner, "user:" + owner} else "administrator" if actor and actor.startswith("admin:") else "other"
    raw = json.loads(row["metadata"])
    if not isinstance(raw, dict):
        raise ValueError("Invalid audit metadata")
    row["metadata"] = {key: _safe_value(raw[key]) for key in ("provider", "run_id", "reason", "duration_ms", "total_tokens", "allowed", "count") if key in raw}
    return row


def export_snapshot(store, owner, token_hash):
    budget = ExportBudget()
    with store.connect() as db:
        db.execute("BEGIN")
        user = _require_current(db, owner, token_hash)
        budget.append('{"format_version":"1.0","exported_at":')
        budget.json(datetime.now(timezone.utc).isoformat())
        budget.append(',"user":')
        budget.json(user)
        owned_session = "session_id IN (SELECT id FROM sessions WHERE owner_user_id=:owner)"
        sections = [
            ("sessions", "sessions", ("id", "mode", "created", "character_id", "character_revision", "character_name", "character_greeting", "memory_scope", "language", "review_access_allowed"), "owner_user_id=:owner", None),
            ("messages", "messages", ("id", "session_id", "role", "content", "emotion", "created"), owned_session, None),
            ("turns", "turns", ("id", "session_id", "request_id", "provider", "emotion", "latency_ms", "response", "created"), owned_session, _safe_turn),
            ("memory_spaces", "memory_spaces", ("id",), "owner_user_id=:owner", None),
            ("approved_memories", "approved_memories", ("id", "space_id", "content", "created", "updated", "revision"), "space_id IN (SELECT id FROM memory_spaces WHERE owner_user_id=:owner)", None),
            ("reviews", "reviews", ("id", "session_id", "run_id", "persona_score", "empathy_score", "memory_score", "note", "provider", "created"), owned_session, None),
        ]
        for name, table, columns, predicate, transform in sections:
            budget.append(',"' + name + '":[')
            _rows(db, table, columns, predicate, {"owner": owner}, budget, transform=transform)
            budget.append("]")
        prefix, predicate = _audit_scope()
        budget.append(',"audit":[')
        _rows(db, "audit_events", ("id", "actor_id", "action", "target_id", "metadata", "created"), predicate,
              {"owner": owner, "actor": "user:" + owner}, budget, prefix=prefix,
              transform=lambda row: _safe_audit(row, owner))
        budget.append("]}")
    return bytes(budget.data)


def erase_account(store, owner, token_hash):
    with store._pending_lock:
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            _require_current(db, owner, token_hash)
            sessions = [row["id"] for row in db.execute("SELECT id FROM sessions WHERE owner_user_id=?", (owner,))]
            prefix, predicate = _audit_scope()
            db.execute(f"{prefix} DELETE FROM audit_events WHERE {predicate}", {"owner": owner, "actor": "user:" + owner})
            db.execute("DELETE FROM sessions WHERE owner_user_id=?", (owner,))
            db.execute("DELETE FROM memory_spaces WHERE owner_user_id=?", (owner,))
            db.execute("DELETE FROM user_tokens WHERE user_id=?", (owner,))
            db.execute("DELETE FROM users WHERE id=?", (owner,))
        # Keep transient proposals intact when the SQL transaction rolls back.
        owned = set(sessions)
        for mid in list(store._pending):
            if store._pending[mid]["session_id"] in owned:
                store._pending.pop(mid, None)
    return sessions


def account_router(store, auth, on_erased=None):
    router = APIRouter(prefix="/api/account", tags=["account data"], dependencies=[Depends(USER_BEARER)])
    export_slots = BoundedSemaphore(2)

    def prepare_export(owner, token_hash):
        # Keep the permit in the worker itself: caller cancellation cannot free
        # a slot while the underlying database snapshot is still being built.
        if not export_slots.acquire(blocking=False):
            issue = authentication_error(429, "Account export is busy; try again later.")
            issue.headers = {**issue.headers, "Retry-After": "2"}
            raise issue
        try:
            return export_snapshot(store, owner, token_hash)
        finally:
            export_slots.release()

    def schema(model):
        return {"requestBody": {"required": True, "content": {"application/json": {"schema": model.model_json_schema()}}}}

    async def reauthenticate(request, model):
        if auth.settings.auth_mode != "accounts":
            raise authentication_error(403, "Account data controls require account mode.")
        user = await auth.require(request)
        auth.rate_limit(request)
        try:
            body = await request_input(request, model)
        except HTTPException as issue:
            if issue.status_code == 422:
                raise authentication_error(422, "Invalid account data input.") from None
            raise
        await auth.verify_password(user["id"], body.password)
        current = await auth.require(request)
        if current["id"] != user["id"]:
            raise authentication_error(401, "User login required.")
        return current, body

    @router.post("/export", openapi_extra=schema(Reauthentication))
    async def export(request: Request):
        user, _ = await reauthenticate(request, Reauthentication)
        try:
            content = await run_in_threadpool(prepare_export, user["id"], request.state.harbor_user_token_hash)
        except (sqlite3.Error, ValueError, TypeError, RecursionError):
            raise authentication_error(409, EXPORT_ERROR) from None
        await auth.require(request)
        return Response(content, media_type="application/json", headers={**NO_CACHE,
            "Content-Disposition": 'attachment; filename="harbor-account-export.json"', "X-Content-Type-Options": "nosniff"})

    @router.delete("/me", openapi_extra=schema(ErasureInput))
    async def erase(request: Request):
        user, body = await reauthenticate(request, ErasureInput)
        if body.confirmation != "DELETE":
            raise authentication_error(400, "Account deletion requires the exact confirmation DELETE.")
        try:
            sessions = erase_account(store, user["id"], request.state.harbor_user_token_hash)
        except sqlite3.Error:
            raise authentication_error(409, DELETE_ERROR) from None
        if on_erased:
            try:
                on_erased(sessions, user["id"])
            except Exception:
                # Account data is already erased; never report a false rollback.
                logger.error("Account erased; runtime registry cleanup failed.")
        return JSONResponse({"ok": True, "deleted": True}, headers=NO_CACHE)

    return router
