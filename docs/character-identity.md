# Fictional character identities

The three existing character IDs remain `nova`, `sage`, and `ember`. All ages, locations, education, families and careers are **authored fictional adult AI settings**, not lived experiences, real employment or user biography. Interface AI disclosure and direct identity answers remain mandatory. This increment makes source material available; it does not establish genuine empathy or a percentage of human likeness. **Human quality review is pending.**

| Character | Fictional setting | Distinct conversational tendency | Testable limitation |
|---|---|---|---|
| Nova | 29, 青岛; maritime transport management associate diploma; shipping agency, five years of port dispatch, logistics itinerary coordination | Short, direct sentences with objects and times | Can turn venting into a task prematurely |
| 青禾 / `sage` | 34, 成都; Chinese-language bachelor's degree; four years of social-news reporting, editorial review | Longer precise sentences; checks the meaning and explains a question | Can over-paraphrase or sound like a lecture |
| 暮星 / `ember` | 26, 长沙; animation bachelor's degree; two years of outsourcing, independent storyboards and short illustrated books | Medium-length sentences and concrete visual analogies | Nervous humor can interrupt a serious topic |

`profiles.py` contains the validated seed material and distinct role instructions. The six fixed sections are `growth`, `work`, `skills`, `interests`, `flaws`, and `boundaries`. Each has separately authored `zh` and `en` text, bounded to 1–2000 characters per language; the fixed schema bounds the total to 24,000 text characters. `age` must be an integer from 18 through 120, `fictional` must be true, and `schema_version` must be integer 1. Missing locales, extra sections, blank strings and unexpected properties are rejected. Existing names and place names remain original; the interface selects a section's explicit language rather than automatically rewriting stored identity facts.

## Identity and ownership layers

1. The administrator edits character master data and its immutable revision history.
2. Creating a session freezes the name, revision, prompt, greeting and structured profile together. Editing or restoring a character affects future sessions.
3. Dialogue and explicit user-approved memories are separate. Character profiles are not automatically written to user memory. Transient stories or user statements cannot alter an identity revision.

`Store.character_profile(id, revision=None)` and `Store.session_profile(session_id)` return `{character_id, revision, name, profile, legacy_profile}` without a system prompt. A legacy snapshot with no known profile returns `profile: null` and `legacy_profile: true`; it is never reconstructed using today's biography. Authorization for session-profile access belongs to the existing owned-session route.

## Administration and review

`GET /api/admin/characters/{id}/revisions` lists public profile revision envelopes plus their recorded creation time, publication state, tagline, description and greeting. System prompts are excluded from that list. `POST /api/admin/characters/{id}/restore` accepts `{revision: <positive integer>}`. Restoration copies that immutable full snapshot into a **new** revision, including its prompt and publication state; it never decrements the current revision or rewrites a historical row. Omitting a profile during ordinary editing preserves the current profile.

Version 2 reviews require six independently supplied integer scores from 1 through 5: naturalness, persona recognition, continuity, credibility of details, empathy and boundary handling. Each needs a nonblank evidence quotation or concrete observation in the matching `evidence` key, at most 1000 characters. The observation is a human annotation, not an automatically measured quality result. No default scores are generated. The old `memory_score` may remain null for a version 2 review.

Version 1 reviews retain their original persona, empathy and memory scores. Added dimensions and evidence remain null; the system does not reinterpret an old memory score as continuity or credibility. Mock records remain workflow evidence and must not be reported as real-model quality.
