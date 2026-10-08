import json
import sqlite3
import statistics
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .characters import SEEDS


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
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
            """)
            # Existing local sessions survive the additive migration and keep their original persona.
            columns = {row["name"] for row in db.execute("PRAGMA table_info(sessions)")}
            for column, definition in {
                "character_id": "TEXT NOT NULL DEFAULT 'nova'",
                "character_revision": "INTEGER NOT NULL DEFAULT 1",
                "character_name": "TEXT NOT NULL DEFAULT 'Nova'",
                "character_prompt": "TEXT NOT NULL DEFAULT ''",
                "character_greeting": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if column not in columns:
                    db.execute(f"ALTER TABLE sessions ADD COLUMN {column} {definition}")
            for character in SEEDS:
                self._insert_character(db, character)
            db.execute("UPDATE sessions SET character_prompt=?,character_greeting=? WHERE character_prompt='' AND character_id='nova'",
                       (SEEDS[0]["system_prompt"], SEEDS[0]["greeting"]))

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

    def create(self, mode: str, character_id="nova"):
        character = self.character(character_id)
        if not character or not character["enabled"]:
            raise ValueError("Character is not available")
        sid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO sessions(id,mode,created,character_id,character_revision,character_name,character_prompt,character_greeting) VALUES(?,?,?,?,?,?,?,?)",
                       (sid, mode, now(), character_id, character["revision"], character["name"], character["system_prompt"], character["greeting"]))
        return self.session(sid)

    def session(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            return dict(row) if row else None

    def history(self, sid, limit=24):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?", (sid, limit)).fetchall()
            return [dict(r) for r in reversed(rows)]

    def memories(self, sid, status=None):
        with self.connect() as db:
            sql = "SELECT * FROM memories WHERE session_id=?"
            args = [sid]
            if status:
                sql += " AND status=?"
                args.append(status)
            return [dict(r) for r in db.execute(sql + " ORDER BY created DESC", args).fetchall()]

    def memory_add(self, sid, content, status="approved"):
        mid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO memories VALUES(?,?,?,?,?)", (mid, sid, content, status, now()))
        return mid

    def memory_action(self, sid, mid, action):
        with self.connect() as db:
            if action == "approve":
                cur = db.execute("UPDATE memories SET status='approved' WHERE id=? AND session_id=? AND status='pending'", (mid, sid))
            else:
                cur = db.execute("DELETE FROM memories WHERE id=? AND session_id=?", (mid, sid))
            return cur.rowcount > 0

    def cached(self, sid, request_id):
        with self.connect() as db:
            row = db.execute("SELECT response FROM turns WHERE session_id=? AND request_id=?", (sid, request_id)).fetchone()
            return json.loads(row[0]) if row else None

    def commit_turn(self, sid, request_id, user, result):
        # A turn and its proposals are committed together; failed providers leave no half-turn.
        with self.connect() as db:
            for role, content in [("user", user), ("assistant", result["reply"])]:
                db.execute("INSERT INTO messages(session_id,role,content,emotion,created) VALUES(?,?,?,?,?)",
                           (sid, role, content, result["emotion"], now()))
            for content in result.pop("proposals", []):
                db.execute("INSERT INTO memories VALUES(?,?,?,?,?)", (str(uuid.uuid4()), sid, content, "pending", now()))
            db.execute("INSERT INTO turns VALUES(?,?,?,?,?,?,?,?)",
                       (result["run_id"], sid, request_id, result["provider"], result["emotion"], result["latency_ms"],
                        json.dumps(result, ensure_ascii=False), now()))
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
            db.execute("DELETE FROM memories WHERE session_id=? AND status='pending'", (sid,))

    def delete(self, sid):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE id=?", (sid,))

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
        sql = """SELECT s.id,s.character_id,s.character_name,s.character_revision,s.mode,s.created,
          (SELECT COUNT(*) FROM turns t WHERE t.session_id=s.id) AS turn_count,
          (SELECT COUNT(*) FROM memories m WHERE m.session_id=s.id) AS memory_count,
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
                "session_count": "sessions", "turn_count": "turns", "memory_count": "memories", "reviews_count": "reviews"}.items()}
            counts["pending_memory_count"] = db.execute("SELECT COUNT(*) FROM memories WHERE status='pending'").fetchone()[0]
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

    def reviews(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM reviews ORDER BY created DESC LIMIT 100")]
