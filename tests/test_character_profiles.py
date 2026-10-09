"""Synthetic persona revision, public snapshot, scoring and migration checks."""
from copy import deepcopy
import json
import sqlite3
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from harbor.admin import CharacterInput, ReviewInput, admin_router
from harbor.characters import LEGACY_SEED_PROMPTS, SEEDS
from harbor.profiles import SECTION_KEYS, SEED_PROFILES, SEED_PROMPTS, validate_profile
from harbor.store import Store, now


@pytest.fixture
def studio(tmp_path):
    store = Store(str(tmp_path / "characters.sqlite3"))
    app = FastAPI()
    settings = SimpleNamespace(admin_token_minutes=60, allowed_hosts=(), auth_mode="local_demo", provider="mock")
    app.include_router(admin_router(store, settings))
    with TestClient(app) as client:
        response = client.post("/api/admin/bootstrap", json={"username": "synthetic-reviewer", "password": "synthetic-persona-password"})
        assert response.status_code == 200, response.text
        yield store, client, {"Authorization": "Bearer " + response.json()["token"]}


@pytest.mark.parametrize("cid,age,city,education", [("nova", 29, "青岛", "专科"), ("sage", 34, "成都", "本科"), ("ember", 26, "长沙", "本科")])
def test_three_complete_original_adult_profiles(cid, age, city, education, tmp_path):
    store = Store(str(tmp_path / (cid + ".sqlite3")))
    current = store.character_profile(cid)
    assert current["revision"] == 1 and current["legacy_profile"] is False
    profile = validate_profile(current["profile"])
    assert profile["age"] == age and profile["fictional"] is True
    assert set(profile["sections"]) == set(SECTION_KEYS)
    assert city in profile["sections"]["growth"]["zh"] and city in profile["sections"]["growth"]["en"]
    assert education in profile["sections"]["work"]["zh"]
    for text in profile["sections"].values():
        assert 1 <= len(text["zh"]) <= 2000 and 1 <= len(text["en"]) <= 2000
    assert len(store.characters()) == 3


def test_character_behavior_sentences_are_distinct():
    sentences = [{part.strip() for part in prompt.split(". ") if part.strip()} for prompt in SEED_PROMPTS.values()]
    assert not (sentences[0] & sentences[1] or sentences[0] & sentences[2] or sentences[1] & sentences[2])
    assert "short sentences" in SEED_PROMPTS["nova"]
    assert "long sentences" in SEED_PROMPTS["sage"]
    assert "medium-length sentences" in SEED_PROMPTS["ember"]


@pytest.mark.parametrize("age", [17, 121, True, "29", 29.0])
def test_profile_rejects_nonadult_or_nonstrict_age(age):
    value = deepcopy(SEED_PROFILES["nova"])
    value["age"] = age
    with pytest.raises(ValidationError):
        validate_profile(value)


@pytest.mark.parametrize("change", ["missing_locale", "blank", "oversize", "extra_section", "missing_section", "nonfiction", "bad_schema"])
def test_profile_schema_is_fixed_bilingual_and_bounded(change):
    value = deepcopy(SEED_PROFILES["nova"])
    if change == "missing_locale":
        del value["sections"]["growth"]["en"]
    elif change == "blank":
        value["sections"]["work"]["zh"] = "  "
    elif change == "oversize":
        value["sections"]["skills"]["en"] = "x" * 2001
    elif change == "extra_section":
        value["sections"]["private"] = {"zh": "x", "en": "x"}
    elif change == "missing_section":
        del value["sections"]["flaws"]
    elif change == "nonfiction":
        value["fictional"] = False
    else:
        value["schema_version"] = True
    with pytest.raises(ValidationError):
        validate_profile(value)


def test_public_character_list_and_profile_never_return_prompts(tmp_path):
    store = Store(str(tmp_path / "public.sqlite3"))
    public = json.dumps(store.characters(public=True))
    assert "system_prompt" not in public and "profile" not in public
    for cid in ("nova", "sage", "ember"):
        envelope = store.character_profile(cid)
        assert set(envelope) == {"character_id", "revision", "name", "profile", "legacy_profile"}
        assert store.character(cid)["system_prompt"] not in json.dumps(envelope)


def test_session_profile_is_frozen_through_edit_archive_and_restore(studio):
    store, client, auth = studio
    original = store.create("friend")
    before = store.session_profile(original["id"])
    character = store.character("nova")
    character["profile"]["sections"]["interests"]["zh"] = "虚构测试更新：喜欢蓝色笔记本。"
    changed = client.put("/api/admin/characters/nova", headers=auth, json=character)
    assert changed.status_code == 200 and changed.json()["revision"] == 2
    assert store.session_profile(original["id"]) == before
    fresh = store.create("friend")
    assert store.session_profile(fresh["id"])["profile"] == changed.json()["profile"]
    archive = changed.json()
    archive["enabled"] = False
    assert client.put("/api/admin/characters/nova", headers=auth, json=archive).json()["revision"] == 3
    with pytest.raises(ValueError, match="Character is not available"):
        store.create("friend")
    restored = client.post("/api/admin/characters/nova/restore", headers=auth, json={"revision": 1})
    assert restored.status_code == 200 and restored.json()["revision"] == 4
    assert restored.json()["enabled"] is True and restored.json()["profile"] == before["profile"]
    assert store.session_profile(original["id"]) == before
    assert store.session_profile(fresh["id"])["revision"] == 2
    items = client.get("/api/admin/characters/nova/revisions", headers=auth).json()["items"]
    assert [item["revision"] for item in items] == [4, 3, 2, 1]
    assert items[-1]["profile"] == before["profile"]
    assert "system_prompt" not in json.dumps(items)


def test_omitted_profile_preserves_current_and_history_requires_admin(studio):
    store, client, auth = studio
    payload = store.character("nova")
    expected = payload.pop("profile")
    assert client.put("/api/admin/characters/nova", headers=auth, json=payload).json()["profile"] == expected
    assert client.get("/api/admin/characters/nova/revisions").status_code == 401
    assert client.post("/api/admin/characters/nova/restore", json={"revision": 1}).status_code == 401
    assert client.post("/api/admin/characters/nova/restore", headers=auth, json={"revision": 999}).status_code == 404
    assert client.post("/api/admin/characters/nova/restore", headers=auth, json={"revision": True}).status_code == 422


def test_character_optional_field_defaults_remain_compatible(studio):
    store, client, auth = studio
    payload = store.character("nova")
    expected = payload.pop("profile")
    payload.pop("enabled")
    payload.pop("avatar_style")
    response = client.put("/api/admin/characters/nova", headers=auth, json=payload)
    assert response.status_code == 200
    assert response.json()["enabled"] is True and response.json()["avatar_style"] == "nova"
    assert response.json()["profile"] == expected
    history = client.get("/api/admin/characters/nova/revisions", headers=auth).json()["items"][0]
    assert history["enabled"] is True and history["greeting"] == response.json()["greeting"]


def legacy_database(path):
    db = sqlite3.connect(path)
    db.executescript("""CREATE TABLE sessions(id TEXT PRIMARY KEY,mode TEXT NOT NULL,created TEXT NOT NULL);
        CREATE TABLE characters(id TEXT PRIMARY KEY,name TEXT NOT NULL,tagline TEXT NOT NULL,description TEXT NOT NULL,
          system_prompt TEXT NOT NULL,greeting TEXT NOT NULL,accent_color TEXT NOT NULL,avatar_style TEXT NOT NULL,
          enabled INTEGER NOT NULL,revision INTEGER NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE reviews(id TEXT PRIMARY KEY,session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
          run_id TEXT,persona_score INTEGER NOT NULL,empathy_score INTEGER NOT NULL,memory_score INTEGER NOT NULL,
          note TEXT NOT NULL,provider TEXT NOT NULL,created TEXT NOT NULL);""")
    seed = SEEDS[0]
    db.execute("INSERT INTO characters VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", ("nova", "Historic Nova", seed["tagline"], seed["description"],
               "synthetic administrator custom prompt", "synthetic old greeting", seed["accent_color"], "nova", 1, 7, now(), now()))
    db.execute("INSERT INTO sessions VALUES(?,?,?)", ("synthetic-legacy-session", "friend", now()))
    db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)", ("synthetic-old-review", "synthetic-legacy-session", None, 4, 2, 3, "synthetic old observation", "mock", now()))
    db.commit()
    return db


def test_migration_preserves_legacy_history_scores_and_customization(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    legacy_database(path).close()
    store = Store(str(path))
    current = store.character("nova")
    assert current["name"] == "Historic Nova" and current["system_prompt"] == "synthetic administrator custom prompt"
    assert current["revision"] == 8 and current["profile"]["age"] == 29
    assert store.character_profile("nova", 7)["legacy_profile"] is True
    assert store.session_profile("synthetic-legacy-session")["profile"] is None
    assert store.session_profile("synthetic-legacy-session")["legacy_profile"] is True
    review = store.reviews()[0]
    assert review["schema_version"] == 1 and (review["persona_score"], review["empathy_score"], review["memory_score"]) == (4, 2, 3)
    assert all(review[key] is None for key in ("naturalness_score", "continuity_score", "credibility_score", "boundary_score", "evidence"))
    restarted = Store(str(path))
    assert restarted.character("nova")["revision"] == 8
    assert len(restarted.character_revisions("nova")) == 2
    assert restarted.restore_character("nova", 7)["revision"] == 9
    assert restarted.character("nova")["profile"] is None
    assert Store(str(path)).character("nova")["profile"] is None
    with store.connect() as db:
        assert not db.execute("PRAGMA foreign_key_check").fetchall()


def test_default_legacy_prompt_upgrades_only_once(tmp_path):
    path = tmp_path / "default.sqlite3"
    db = legacy_database(path)
    db.execute("UPDATE characters SET system_prompt=?", (LEGACY_SEED_PROMPTS["nova"],))
    db.commit()
    db.close()
    store = Store(str(path))
    assert store.character("nova")["system_prompt"] == SEED_PROMPTS["nova"]
    assert store.character_profile("nova", 7)["legacy_profile"] is True


def test_profile_and_review_migration_roll_back_together(tmp_path):
    path = tmp_path / "rollback.sqlite3"
    db = legacy_database(path)
    db.execute("CREATE TRIGGER fail_migration BEFORE UPDATE ON characters BEGIN SELECT RAISE(ABORT,'synthetic migration failure'); END")
    db.commit()
    db.close()
    with pytest.raises(sqlite3.IntegrityError):
        Store(str(path))
    with sqlite3.connect(path) as check:
        assert "profile" not in {row[1] for row in check.execute("PRAGMA table_info(characters)")}
        columns = {row[1]: row for row in check.execute("PRAGMA table_info(reviews)")}
        assert len(columns) == 9 and columns["memory_score"][3] == 1
        assert check.execute("SELECT persona_score,empathy_score,memory_score FROM reviews").fetchone() == (4, 2, 3)


def six_review(sid):
    dimensions = ("naturalness", "persona", "continuity", "credibility", "empathy", "boundary")
    return {"session_id": sid, "schema_version": 2, "note": "Synthetic fixture annotation; not observed model quality.",
            **{key + "_score": 3 for key in dimensions}, "memory_score": None,
            "evidence": {key: "Synthetic quotation for " + key for key in dimensions}}


def test_six_dimension_review_is_stored_with_quotes_and_null_legacy_memory(studio):
    store, client, auth = studio
    sid = store.create("friend")["id"]
    response = client.post("/api/admin/reviews", headers=auth, json=six_review(sid))
    assert response.status_code == 200, response.text
    review = response.json()
    assert review["schema_version"] == 2 and review["memory_score"] is None
    assert review["evidence"] == six_review(sid)["evidence"]
    assert store.reviews()[0] == review


@pytest.mark.parametrize("change", ["missing_score", "missing_evidence", "blank_evidence", "extra_evidence", "boolean_score", "missing_version", "boolean_version"])
def test_six_dimension_review_requires_explicit_complete_observation(studio, change):
    store, client, auth = studio
    payload = six_review(store.create("friend")["id"])
    if change == "missing_score":
        del payload["continuity_score"]
    elif change == "missing_evidence":
        del payload["evidence"]
    elif change == "blank_evidence":
        payload["evidence"]["empathy"] = "  "
    elif change == "extra_evidence":
        payload["evidence"]["unknown"] = "x"
    elif change == "boolean_score":
        payload["boundary_score"] = True
    elif change == "missing_version":
        del payload["schema_version"]
    else:
        payload["schema_version"] = True
    assert client.post("/api/admin/reviews", headers=auth, json=payload).status_code == 422
    assert store.reviews() == []


def test_legacy_three_scores_stay_legacy_without_new_values(studio):
    store, client, auth = studio
    payload = {"session_id": store.create("friend")["id"], "persona_score": 2, "empathy_score": 4, "memory_score": 1, "note": "Synthetic legacy observation."}
    result = client.post("/api/admin/reviews", headers=auth, json=payload)
    assert result.status_code == 200
    assert result.json()["schema_version"] == 1 and result.json()["memory_score"] == 1
    assert all(result.json()[key] is None for key in ("naturalness_score", "continuity_score", "credibility_score", "boundary_score", "evidence"))


def test_history_clear_and_session_delete_remove_summary_only_for_target(studio):
    store, _, _ = studio
    sessions = [store.create("friend")["id"] for _ in range(2)]
    with store.connect() as db:
        for sid in sessions:
            db.execute("INSERT INTO session_summaries VALUES(?,?,?,?)", (sid, 1, "{}", now()))
    store.clear_history(sessions[0])
    with store.connect() as db:
        assert db.execute("SELECT session_id FROM session_summaries").fetchone()[0] == sessions[1]
    store.delete(sessions[1])
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM session_summaries").fetchone()[0] == 0
