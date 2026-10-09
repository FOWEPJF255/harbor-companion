"""Bounded, extractive session context. No model calls or approved-memory writes."""
from datetime import datetime, timezone
import json
import re

RECENT_MESSAGES = 12
RECENT_BYTES = 18000
SUMMARY_BYTES = 9000
MAX_ENTRIES = 48
BATCH_MESSAGES = 512


def byte_size(value):
    return len(value.encode("utf-8"))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def category(text):
    lowered = text.lower()
    if any(x in lowered for x in ("更正", "改成", "不是", "actually", "correction", "instead")):
        return "correction_claim"
    if any(x in lowered for x in ("约定", "答应", "明天", "下周", "promise", "tomorrow", "next week")):
        return "plan_claim"
    if any(x in lowered for x in ("喜欢", "不喜欢", "只想", "不要建议", "prefer", "i like", "just listen")):
        return "preference_claim"
    return "dialogue_excerpt"


def excerpt(text, maximum=420):
    """Keep complete sentences only; disclose omissions instead of slicing claims."""
    sentences = re.split(r"(?<=[。！？!?\n])|(?<=\.)\s+", text)
    selected = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and len(" ".join([*selected, sentence])) <= maximum:
            selected.append(sentence)
    return " ".join(selected), len(" ".join(selected)) < len(text.strip())


class ContextBuilder:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def ensure_schema(db):
        db.execute("""CREATE TABLE IF NOT EXISTS session_summaries(
            session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
            through_message_id INTEGER NOT NULL, content TEXT NOT NULL, updated TEXT NOT NULL)""")

    def build(self, sid):
        # The transaction prevents concurrent erasure from leaving orphaned summaries.
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone():
                raise ValueError("Session not found")
            rows = [dict(row) for row in db.execute(
                "SELECT id,role,content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (sid, RECENT_MESSAGES))]
            recent, size = [], 0
            # Complete user/assistant pairs avoid truncating a sentence or dropping its speaker.
            for offset in range(0, len(rows), 2):
                pair = rows[offset:offset + 2]
                cost = sum(byte_size(item["content"]) for item in pair)
                if size + cost > RECENT_BYTES:
                    break
                recent.extend(pair)
                size += cost
            recent.reverse()
            cutoff = recent[0]["id"] if recent else (rows[0]["id"] + 1 if rows else 0)
            saved = db.execute("SELECT * FROM session_summaries WHERE session_id=?", (sid,)).fetchone()
            state = json.loads(saved["content"]) if saved else {
                "method": "extractive-v1", "scope": "this session only; derived dialogue, not approved long-term memory",
                "entries": [], "omitted_messages": 0, "omitted_entries": 0, "excerpt_omissions": 0}
            through = saved["through_message_id"] if saved else 0
            count = db.execute("SELECT COUNT(*) FROM messages WHERE session_id=? AND id>? AND id<?",
                               (sid, through, cutoff)).fetchone()[0]
            older = list(reversed(db.execute(
                "SELECT id,role,content FROM messages WHERE session_id=? AND id>? AND id<? ORDER BY id DESC LIMIT ?",
                (sid, through, cutoff, BATCH_MESSAGES)).fetchall()))
            state["omitted_messages"] += max(0, count - len(older))
            for row in older:
                quote, clipped = excerpt(row["content"])
                state["excerpt_omissions"] += int(clipped)
                if quote:
                    state["entries"].append({"source_message_id": row["id"], "speaker": row["role"],
                                             "kind": category(quote), "quote": quote})
                else:
                    state["omitted_entries"] += 1
            if older:
                through = older[-1]["id"]
            # Retain early explicit user anchors plus recent corrections, rather than only recency.
            candidates = state["entries"]
            anchors = [e for e in candidates if e["speaker"] == "user" and e["kind"] in
                       {"plan_claim", "preference_claim"}][:8]
            rank = anchors + sorted([e for e in candidates if e not in anchors],
                                    key=lambda e: (e["kind"] == "correction_claim", e["speaker"] == "user", e["source_message_id"]), reverse=True)
            kept = []
            for entry in rank:
                if len(kept) < MAX_ENTRIES and byte_size(encoded([*kept, entry])) <= SUMMARY_BYTES - 650:
                    kept.append(entry)
                else:
                    state["omitted_entries"] += 1
            state["entries"] = sorted(kept, key=lambda e: e["source_message_id"])
            state["lossy"] = bool(state["omitted_messages"] or state["omitted_entries"] or state["excerpt_omissions"])
            if count:
                db.execute("""INSERT INTO session_summaries VALUES(?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET
                    through_message_id=excluded.through_message_id,content=excluded.content,updated=excluded.updated""",
                    (sid, through, encoded(state), datetime.now(timezone.utc).isoformat()))
            metrics = {"recent_messages": len(recent), "recent_utf8_bytes": size,
                       "summary_entries": len(kept), "summary_utf8_bytes": byte_size(encoded(state)),
                       "omitted_messages": state["omitted_messages"], "omitted_entries": state["omitted_entries"],
                       "excerpt_omissions": state["excerpt_omissions"], "lossy": state["lossy"]}
            return state, [{"role": m["role"], "content": m["content"]} for m in recent], metrics


def profile_for_prompt(envelope, language):
    if envelope.get("legacy_profile") or not envelope.get("profile"):
        return {"legacy_profile": True, "instruction": "No authored life profile exists for this historical session. Do not invent it."}
    profile = envelope["profile"]
    return {"fictional": True, "age": profile["age"], "revision": envelope["revision"],
            "sections": {key: value[language] for key, value in profile["sections"].items()}}
