import json
import sqlite3
import statistics
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


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
            """)

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

    def create(self, mode: str):
        sid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (sid, mode, now()))
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
            return [dict(r) for r in db.execute(sql + " ORDER BY created DESC LIMIT 30", args).fetchall()]

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
            db.execute("DELETE FROM messages WHERE session_id=?", (sid,))
            db.execute("DELETE FROM turns WHERE session_id=?", (sid,))
            db.execute("DELETE FROM memories WHERE session_id=? AND status='pending'", (sid,))

    def delete(self, sid):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE id=?", (sid,))
