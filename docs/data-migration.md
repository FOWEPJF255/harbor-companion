# v0.6 identity and review migration

The Store applies the v0.6 changes within its explicit SQLite write transaction after creating the base tables. Tests use disposable databases. Back up an owner's database before upgrading; this document does not authorize deleting or resetting it.

## Additive identity schema

- `characters.profile`: nullable JSON text containing the validated bilingual fictional adult profile.
- `sessions.character_profile`: nullable JSON text frozen at session creation.
- `character_revisions(character_id, revision, snapshot, created)`: immutable full master-data snapshots keyed by character ID and revision.
- `session_summaries`: created through `ContextBuilder.ensure_schema`; history clearing removes only that session's summary, and session deletion cascades.

Existing character rows are recorded at their actual current revision with a missing profile explicitly represented as null. No earlier revisions are invented. On the first upgrade from a schema without `characters.profile`, the three built-in IDs receive a structured profile as a **new** revision. Only prompts and presentation fields that exactly match the old built-in defaults are replaced by the new defaults. Administrator-customized names, instructions and greetings are retained. Legacy sessions are not filled with the new biography or greeting.

Repeated startup does not add revisions. Restoring an old missing-profile snapshot remains a deliberate new legacy-profile version after restart; seed initialization does not silently replace it again.

## Honest missing review scores

The new review fields are `schema_version` (default 1), nullable `naturalness_score`, `continuity_score`, `credibility_score`, `boundary_score`, and nullable JSON `evidence`. Existing `persona_score`, `empathy_score`, `memory_score`, notes, IDs, providers, run links and timestamps are preserved.

The old `memory_score NOT NULL` constraint cannot express an unscored version 2 legacy dimension. SQLite cannot remove that constraint using `ADD COLUMN`. The targeted migration therefore creates `reviews_v06` with the known review schema and nullable memory score, copies every existing row and its known fields, replaces the old table, and renames the replacement **within the same transaction**. A later failure rolls back both the constraint change and identity additions. This migration supports the project's known schema; arbitrary unrecognized extension columns or external triggers/indexes are not a supported plugin migration contract.

Callers inserting review rows must name their columns explicitly. A positional nine-value insert is not compatible with the extended schema. All application writes now do so. Legacy records remain version 1 with newly added fields null; a version 2 review requires all six scores and evidence rather than fabricated defaults.

## Verification boundary

Synthetic checks cover fresh initialization, fixed bilingual schema, immutable session snapshots, monotonic restore/archive history, administrator authorization, missing legacy profiles, custom-field preservation, default-only upgrades, startup idempotence, exact legacy-score preservation, version 2 evidence validation and migration rollback. Passing these establishes storage and API behavior, not a semantic-quality score or real-device acceptance result.
