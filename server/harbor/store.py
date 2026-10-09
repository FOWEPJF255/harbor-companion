import json
import hashlib
import sqlite3
import statistics
import re
import time
from threading import RLock
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .characters import SEEDS
from .user_auth import UserAuth


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str):
        self.path = path
        # Unapproved proposals are process-local, expire, and are never stored in SQLite.
        self._pending = {}
        self._pending_lock = RLock()
        self._maintenance_lock = RLock()
        self._last_maintenance = float("-inf")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            UserAuth.ensure_schema(db)
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, mode TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
              role TEXT, content TEXT, emotion TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
              content TEXT, status TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS turns(id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
              request_id TEXT, provider TEXT, emotion TEXT, latency_ms REAL, response TEXT, created TEXT,
              UNIQUE(session_id, request_id));
            CREATE TABLE IF NOT EXISTS characters(id TEXT PRIMARY KEY, name TEXT NOT NULL, tagline TEXT NOT NULL,
              description TEXT NOT NULL, system_prompt TEXT NOT NULL, greeting TEXT NOT NULL,
              accent_color TEXT NOT NULL, avatar_style TEXT NOT NULL, enabled INTEGER NOT NULL,
              revision INTEGER NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS administrators(id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL,
              password_hash TEXT NOT NULL, salt TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
              run_id TEXT, persona_score INTEGER NOT NULL, empathy_score INTEGER NOT NULL, memory_score INTEGER NOT NULL,
              note TEXT NOT NULL, provider TEXT NOT NULL, created TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id,id);
            CREATE INDEX IF NOT EXISTS memories_session ON memories(session_id,created);
            CREATE INDEX IF NOT EXISTS turns_session ON turns(session_id,created);
            CREATE TABLE IF NOT EXISTS memory_spaces(id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS approved_memories(id TEXT PRIMARY KEY,
              space_id TEXT NOT NULL REFERENCES memory_spaces(id) ON DELETE CASCADE,
              content TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS approved_memory_space ON approved_memories(space_id,created);
            CREATE TABLE IF NOT EXISTS audit_events(id TEXT PRIMARY KEY,actor_id TEXT,action TEXT NOT NULL,
              target_id TEXT,metadata TEXT NOT NULL,created TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS audit_created ON audit_events(created);
            """)
            # Existing local sessions survive the additive migration and keep their original persona.
            columns = {row["name"] for row in db.execute("PRAGMA table_info(sessions)")}
            for column, definition in {
                "character_id": "TEXT NOT NULL DEFAULT 'nova'",
                "character_revision": "INTEGER NOT NULL DEFAULT 1",
                "character_name": "TEXT NOT NULL DEFAULT 'Nova'",
                "character_prompt": "TEXT NOT NULL DEFAULT ''",
                "character_greeting": "TEXT NOT NULL DEFAULT ''",
                "memory_scope": "TEXT REFERENCES memory_spaces(id)",
                "language": "TEXT NOT NULL DEFAULT 'zh'",
                "owner_user_id": "TEXT REFERENCES users(id)",
                "review_access_allowed": "INTEGER NOT NULL DEFAULT 0",
            }.items():
                if column not in columns:
                    db.execute(f"ALTER TABLE sessions ADD COLUMN {column} {definition}")
            if "owner_user_id" not in {row["name"] for row in db.execute("PRAGMA table_info(memory_spaces)")}:
                db.execute("ALTER TABLE memory_spaces ADD COLUMN owner_user_id TEXT REFERENCES users(id)")
            for character in SEEDS:
                self._insert_character(db, character)
            db.execute("UPDATE sessions SET character_prompt=?,character_greeting=? WHERE character_prompt='' AND character_id='nova'",
                       (SEEDS[0]["system_prompt"], SEEDS[0]["greeting"]))
            # One-way additive migration: isolate each legacy session, preserve approved facts only.
            for row in db.execute("SELECT id FROM sessions WHERE memory_scope IS NULL").fetchall():
                scope = str(uuid.uuid4())
                db.execute("INSERT INTO memory_spaces(id) VALUES(?)", (scope,))
                db.execute("UPDATE sessions SET memory_scope=? WHERE id=?", (scope, row["id"]))
            db.execute("""INSERT OR IGNORE INTO approved_memories
                SELECT m.id,s.memory_scope,m.content,m.created,m.created,1
                FROM memories m JOIN sessions s ON s.id=m.session_id WHERE m.status='approved'""")
            db.execute("DELETE FROM memories")
            if "request_hash" not in {row["name"] for row in db.execute("PRAGMA table_info(turns)")}:
                db.execute("ALTER TABLE turns ADD COLUMN request_hash TEXT")
            if "subject_user_id" not in {row["name"] for row in db.execute("PRAGMA table_info(audit_events)")}:
                db.execute("ALTER TABLE audit_events ADD COLUMN subject_user_id TEXT REFERENCES users(id) ON DELETE CASCADE")
                # Attribute only existing, provably owned records; never guess orphaned legacy owners.
                db.execute("""UPDATE audit_events SET subject_user_id=COALESCE(
                    (SELECT u.id FROM users u WHERE u.id=audit_events.actor_id),
                    (SELECT u.id FROM users u WHERE u.id=audit_events.target_id),
                    (SELECT s.owner_user_id FROM sessions s WHERE s.id=audit_events.target_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS audit_subject ON audit_events(subject_user_id)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, mode: str, character_id="nova", memory_from_session_id=None, language="zh", owner_user_id=None):
        character = self.character(character_id)
        if not character or not character["enabled"]:
            raise ValueError("Character is not available")
        sid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if owner_user_id is not None and not db.execute("SELECT id FROM users WHERE id=? AND active=1", (owner_user_id,)).fetchone():
                raise ValueError("User account is not available")
            if memory_from_session_id:
                source = db.execute("""SELECT s.memory_scope,s.owner_user_id,p.owner_user_id AS space_owner
                    FROM sessions s JOIN memory_spaces p ON p.id=s.memory_scope WHERE s.id=?""", (memory_from_session_id,)).fetchone()
                if not source or source["owner_user_id"] != owner_user_id or source["space_owner"] != owner_user_id:
                    raise ValueError("Memory source session not found")
                scope = source["memory_scope"]
            else:
                scope = str(uuid.uuid4())
                db.execute("INSERT INTO memory_spaces(id,owner_user_id) VALUES(?,?)", (scope, owner_user_id))
            db.execute("INSERT INTO sessions(id,mode,created,character_id,character_revision,character_name,character_prompt,character_greeting,memory_scope,language,owner_user_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (sid, mode, now(), character_id, character["revision"], character["name"], character["system_prompt"], character["greeting"], scope, language, owner_user_id))
        return self.session(sid)

    def session(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            return dict(row) if row else None

    def history(self, sid, limit=24):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?", (sid, limit)).fetchall()
            return [dict(r) for r in reversed(rows)]

    def account_sessions(self, owner, cursor=None, limit=20):
        params = [owner]
        predicate = "owner_user_id=?"
        if cursor:
            created, separator, sid = cursor.partition("~")
            if not separator or len(created) > 50 or len(sid) != 36 or len(cursor) > 90:
                raise ValueError("Invalid session cursor")
            predicate += " AND (created < ? OR (created=? AND id<?))"
            params.extend([created, created, sid])
        with self.connect() as db:
            rows = db.execute(f"SELECT id,created FROM sessions WHERE {predicate} ORDER BY created DESC,id DESC LIMIT ?",
                              (*params, limit + 1)).fetchall()
        visible = rows[:limit]
        summaries = {row["id"]: row for row in self.list_sessions([r["id"] for r in visible], limit)}
        return {"items": [summaries[row["id"]] for row in visible], "limit": limit,
                "next_cursor": visible[-1]["created"] + "~" + visible[-1]["id"] if len(rows) > limit and visible else None}

    def session_count(self, owner=None):
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM sessions WHERE owner_user_id IS ?", (owner,)).fetchone()[0]

    def review_access(self, sid, allowed):
        with self.connect() as db:
            db.execute("UPDATE sessions SET review_access_allowed=? WHERE id=?", (int(allowed), sid))
            if not allowed:
                # Notes may quote dialogue; withdrawal removes them from the reviewer plane.
                db.execute("DELETE FROM reviews WHERE session_id=?", (sid,))

    def audit_event(self, actor, action, target=None, **metadata):
        allowed = {"provider", "run_id", "reason", "duration_ms", "total_tokens", "allowed", "count"}
        if set(metadata) - allowed:
            raise ValueError("Audit metadata must not include dialogue or credentials")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            actor_user = db.execute("SELECT id FROM users WHERE id=? AND active=1", (actor,)).fetchone()
            if re.fullmatch(r"[0-9a-f]{32}", actor or "") and not actor_user:
                # An asynchronous operation belonging to an erased account cannot recreate its audit.
                return
            subject = actor_user[0] if actor_user else None
            if subject is None and target:
                subject_row = db.execute("""SELECT id FROM users WHERE id=? UNION ALL
                    SELECT owner_user_id FROM sessions WHERE id=? UNION ALL
                    SELECT s.owner_user_id FROM turns t JOIN sessions s ON s.id=t.session_id WHERE t.id=? UNION ALL
                    SELECT p.owner_user_id FROM approved_memories m JOIN memory_spaces p ON p.id=m.space_id WHERE m.id=?
                    LIMIT 1""", (target, target, target, target)).fetchone()
                subject = subject_row[0] if subject_row else None
            db.execute("INSERT INTO audit_events(id,actor_id,action,target_id,metadata,created,subject_user_id) VALUES(?,?,?,?,?,?,?)",
                       (str(uuid.uuid4()), actor, action, target, json.dumps(metadata, ensure_ascii=False), now(), subject))

    def audit_events(self, limit=100):
        with self.connect() as db:
            return [{**dict(row), "metadata": json.loads(row["metadata"])} for row in db.execute(
                "SELECT * FROM audit_events ORDER BY created DESC LIMIT ?", (limit,))]

    def prune_audit(self, retention_days):
        from datetime import timedelta
        threshold = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self.connect() as db:
            return db.execute("DELETE FROM audit_events WHERE created < ?", (threshold,)).rowcount

    def maintenance(self, retention_days, *, force=False):
        """Startup and hourly-on-request cleanup; idle servers do not run a background sweeper."""
        from datetime import timedelta
        with self._maintenance_lock:
            stamp = time.monotonic()
            if not force and stamp - self._last_maintenance < 3600:
                return None
            threshold = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                tokens = db.execute("DELETE FROM user_tokens WHERE expires_at<=? OR revoked_at IS NOT NULL", (int(time.time()),)).rowcount
                audit = db.execute("DELETE FROM audit_events WHERE created<?", (threshold,)).rowcount
            self._last_maintenance = stamp
            self._expire_proposals()
            return {"expired_or_revoked_tokens": tokens, "expired_audit_events": audit}

    def memories(self, sid, status=None):
        self._expire_proposals()
        with self.connect() as db:
            rows = db.execute("""SELECT m.id,m.content,m.created,m.updated,m.revision,'approved' AS status
                FROM approved_memories m JOIN sessions s ON m.space_id=s.memory_scope
                WHERE s.id=? ORDER BY m.created DESC""", (sid,)).fetchall() if status != "pending" else []
        pending = [self._public_proposal(p) for p in self._proposal_snapshot() if p["session_id"] == sid] if status != "approved" else []
        return pending + [dict(row) for row in rows]

    def _expire_proposals(self):
        with self._pending_lock:
            stamp = time.monotonic()
            for mid in list(self._pending):
                if self._pending[mid]["expires_at"] <= stamp:
                    self._pending.pop(mid, None)

    def _proposal_snapshot(self):
        with self._pending_lock:
            self._expire_proposals()
            return [dict(p) for p in self._pending.values()]

    @staticmethod
    def _public_proposal(p):
        return {key: p[key] for key in ("id", "content", "status", "created")}

    def memory_add(self, sid, content, status="approved"):
        content = content.strip()
        if not 1 <= len(content) <= 300 or status not in {"approved", "pending"}:
            raise ValueError("Invalid memory")
        session = self.session(sid)
        if not session:
            raise ValueError("Session not found")
        mid = str(uuid.uuid4())
        if status == "pending":
            with self._pending_lock:
                if not self.session(sid):
                    raise ValueError("Session not found")
                self._pending[mid] = {"id": mid, "session_id": sid, "content": content, "status": "pending",
                                      "created": now(), "expires_at": time.monotonic() + 1800, "request_id": None}
            return mid
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM approved_memories WHERE space_id=?", (session["memory_scope"],)).fetchone()[0] >= 100:
                raise ValueError("Memory limit reached; remove older memories first.")
            stamp = now()
            db.execute("INSERT INTO approved_memories VALUES(?,?,?,?,?,1)", (mid, session["memory_scope"], content, stamp, stamp))
        return mid

    def memory_action(self, sid, mid, action):
        self._expire_proposals()
        with self._pending_lock:
            pending = self._pending.get(mid)
        if pending and pending["session_id"] == sid:
            if action == "approve":
                session = self.session(sid)
                with self.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if db.execute("SELECT COUNT(*) FROM approved_memories WHERE space_id=?", (session["memory_scope"],)).fetchone()[0] >= 100:
                        raise ValueError("Memory limit reached; remove older memories first.")
                    stamp = now()
                    db.execute("INSERT INTO approved_memories VALUES(?,?,?,?,?,1)",
                               (mid, session["memory_scope"], pending["content"], stamp, stamp))
            elif action != "delete":
                return False
            with self._pending_lock:
                self._pending.pop(mid, None)
            return True
        with self.connect() as db:
            if action != "delete":
                return False
            cur = db.execute("DELETE FROM approved_memories WHERE id=? AND space_id=(SELECT memory_scope FROM sessions WHERE id=?)", (mid, sid))
            return cur.rowcount > 0

    def memory_correct(self, sid, mid, content, *, approve_pending=False):
        content = content.strip()
        if not 1 <= len(content) <= 300:
            return False
        with self._pending_lock:
            self._expire_proposals()
            pending = self._pending.get(mid)
            if pending:
                if not approve_pending or pending["session_id"] != sid:
                    return False
                session = self.session(sid)
                if not session:
                    return False
                with self.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if db.execute("SELECT COUNT(*) FROM approved_memories WHERE space_id=?", (session["memory_scope"],)).fetchone()[0] >= 100:
                        raise ValueError("Memory limit reached; remove older memories first.")
                    stamp = now()
                    db.execute("INSERT INTO approved_memories VALUES(?,?,?,?,?,1)",
                               (mid, session["memory_scope"], content, stamp, stamp))
                self._pending.pop(mid, None)
                return True
        with self.connect() as db:
            cur = db.execute("UPDATE approved_memories SET content=?,updated=?,revision=revision+1 WHERE id=? AND space_id=(SELECT memory_scope FROM sessions WHERE id=?)",
                             (content, now(), mid, sid))
            return cur.rowcount > 0

    def cached(self, sid, request_id, user=None):
        with self.connect() as db:
            row = db.execute("SELECT response,request_hash FROM turns WHERE session_id=? AND request_id=?", (sid, request_id)).fetchone()
            if row and user is not None and row["request_hash"] != hashlib.sha256(user.strip().encode()).hexdigest():
                raise ValueError("Request ID was already used for a different message")
            result = json.loads(row[0]) if row else None
        self._expire_proposals()
        if result:
            result["pending_proposals"] = [self._public_proposal(p) for p in self._proposal_snapshot()
                                           if p["session_id"] == sid and p["request_id"] == request_id]
        return result

    def commit_turn(self, sid, request_id, user, result):
        proposals = result.pop("proposals", [])
        # Completed dialogue is history; dedicated proposals and their contents are not durable memory.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute("SELECT owner_user_id FROM sessions WHERE id=?", (sid,)).fetchone()
            if not session or (session[0] is not None and not db.execute("SELECT id FROM users WHERE id=? AND active=1", (session[0],)).fetchone()):
                raise ValueError("Session not found")
            for role, content in [("user", user), ("assistant", result["reply"])]:
                db.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)",
                           (sid, role, content, result["emotion"], now()))
            db.execute("INSERT INTO turns(id,session_id,request_id,provider,emotion,latency_ms,response,created,request_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                       (result["run_id"], sid, request_id, result["provider"], result["emotion"], result["latency_ms"],
                        json.dumps(result, ensure_ascii=False), now(), hashlib.sha256(user.strip().encode()).hexdigest()))
        pending = []
        for content in proposals:
            mid = self.memory_add(sid, content, "pending")
            self._pending[mid]["request_id"] = request_id
            pending.append(self._public_proposal(self._pending[mid]))
        result["pending_proposals"] = pending
        return result

    def insights(self, sid):
        with self.connect() as db:
            rows = db.execute("SELECT provider,emotion,latency_ms FROM turns WHERE session_id=?", (sid,)).fetchall()
        moods = {}
        providers = {}
        for r in rows:
            moods[r["emotion"]] = moods.get(r["emotion"], 0) + 1
            providers[r["provider"]] = providers.get(r["provider"], 0) + 1
        latencies = [r["latency_ms"] for r in rows]
        return {"turn_count": len(rows), "emotion_counts": moods, "provider_counts": providers,
                "median_latency_ms": round(statistics.median(latencies), 1) if latencies else None,
                "scope": "current local session", "emotion_method": "keyword heuristic; not a diagnosis",
                "latency_scope": "server turn only; mock values do not represent LLM speed"}

    def clear_history(self, sid):
        with self.connect() as db:
            # Human notes may quote private conversations; clear them with their source evidence.
            db.execute("DELETE FROM reviews WHERE session_id=?", (sid,))
            db.execute("DELETE FROM messages WHERE session_id=?", (sid,))
            db.execute("DELETE FROM turns WHERE session_id=?", (sid,))
        with self._pending_lock:
            self._pending = {mid: p for mid, p in self._pending.items() if p["session_id"] != sid}

    def delete(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT memory_scope FROM sessions WHERE id=?", (sid,)).fetchone()
            db.execute("DELETE FROM sessions WHERE id=?", (sid,))
            if row and not db.execute("SELECT id FROM sessions WHERE memory_scope=?", (row[0],)).fetchone():
                db.execute("DELETE FROM memory_spaces WHERE id=?", (row[0],))
        with self._pending_lock:
            self._pending = {mid: p for mid, p in self._pending.items() if p["session_id"] != sid}

    @staticmethod
    def _insert_character(db, character):
        stamp = now()
        db.execute("INSERT OR IGNORE INTO characters VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (character["id"], character["name"], character["tagline"], character["description"],
                    character["system_prompt"], character["greeting"], character["accent_color"], character["avatar_style"],
                    int(character["enabled"]), 1, stamp, stamp))

    def character(self, cid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM characters WHERE id=?", (cid,)).fetchone()
            return {**dict(row), "enabled": bool(row["enabled"])} if row else None

    def characters(self, public=False):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM characters" + (" WHERE enabled=1" if public else "") + " ORDER BY created,id").fetchall()
            return [{**dict(row), "enabled": bool(row["enabled"])} for row in rows]

    def save_character(self, data, cid=None):
        cid = cid or str(uuid.uuid4())
        with self.connect() as db:
            existing = db.execute("SELECT revision FROM characters WHERE id=?", (cid,)).fetchone()
            if existing:
                db.execute("UPDATE characters SET name=?,tagline=?,description=?,system_prompt=?,greeting=?,accent_color=?,avatar_style=?,enabled=?,revision=revision+1,updated=? WHERE id=?",
                           (data["name"], data["tagline"], data["description"], data["system_prompt"], data["greeting"],
                            data["accent_color"], data["avatar_style"], int(data["enabled"]), now(), cid))
            else:
                self._insert_character(db, {**data, "id": cid})
        return self.character(cid)

    def list_sessions(self, ids=None, limit=100):
        if ids is not None and not ids:
            return []
        sql = """SELECT s.id,s.character_id,s.character_name,s.character_revision,s.mode,s.created,s.review_access_allowed,
          (SELECT COUNT(*) FROM turns t WHERE t.session_id=s.id) AS turn_count,
          (SELECT COUNT(*) FROM approved_memories m WHERE m.space_id=s.memory_scope) AS memory_count,
          COALESCE((SELECT MAX(t.created) FROM turns t WHERE t.session_id=s.id),s.created) AS last_active FROM sessions s"""
        params = []
        if ids is not None:
            sql += " WHERE s.id IN (" + ",".join("?" for _ in ids) + ")"
            params.extend(ids)
        sql += " ORDER BY last_active DESC LIMIT ?"
        params.append(limit)
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def overview(self):
        with self.connect() as db:
            counts = {name: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for name, table in {
                "session_count": "sessions", "turn_count": "turns", "memory_count": "approved_memories", "reviews_count": "reviews"}.items()}
            self._expire_proposals()
            counts["pending_memory_count"] = len(self._proposal_snapshot())
            counts["active_character_count"] = db.execute("SELECT COUNT(*) FROM characters WHERE enabled=1").fetchone()[0]
            counts["average_latency_ms"] = db.execute("SELECT AVG(latency_ms) FROM turns").fetchone()[0]
            counts["provider_counts"] = {row[0]: row[1] for row in db.execute("SELECT provider,COUNT(*) FROM turns GROUP BY provider")}
            return counts

    def turn_metadata(self, sid):
        with self.connect() as db:
            rows = db.execute("SELECT id,provider,emotion,latency_ms,created,response FROM turns WHERE session_id=? ORDER BY created DESC LIMIT 100", (sid,)).fetchall()
        return [{**{k: row[k] for k in ("id", "provider", "emotion", "latency_ms", "created")},
                 "trace": json.loads(row["response"]).get("trace", []), "usage": json.loads(row["response"]).get("usage")} for row in rows]

    def administrator(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM administrators WHERE id=1").fetchone()
            return dict(row) if row else None

    def create_administrator(self, username, password_hash, salt):
        with self.connect() as db:
            db.execute("INSERT INTO administrators VALUES(1,?,?,?,?)", (username, password_hash, salt, now()))

    def save_review(self, data):
        sid, run_id = data["session_id"], data.get("run_id") or None
        with self.connect() as db:
            if not db.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone():
                raise ValueError("Session not found")
            if run_id:
                row = db.execute("SELECT provider FROM turns WHERE id=? AND session_id=?", (run_id, sid)).fetchone()
                if not row:
                    raise ValueError("Turn does not belong to this session")
                provider = row["provider"]
            else:
                providers = [row[0] for row in db.execute("SELECT DISTINCT provider FROM turns WHERE session_id=?", (sid,))]
                provider = providers[0] if len(providers) == 1 else "mixed" if providers else "no_completed_turn"
            rid = str(uuid.uuid4())
            db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)", (rid, sid, run_id, data["persona_score"],
                       data["empathy_score"], data["memory_score"], data["note"], provider, now()))
        return next(row for row in self.reviews() if row["id"] == rid)

    def reviews(self, permitted_only=False):
        with self.connect() as db:
            sql = "SELECT r.* FROM reviews r"
            if permitted_only:
                sql += " JOIN sessions s ON s.id=r.session_id WHERE s.owner_user_id IS NOT NULL AND s.review_access_allowed=1"
            return [dict(row) for row in db.execute(sql + " ORDER BY r.created DESC LIMIT 100")]
