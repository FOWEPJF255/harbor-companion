# Product positioning

## Goal

Build a focused companion-agent MVP that demonstrates a real character conversation experience **and** the engineering behind it. The target job family includes companion/digital-character apps, prompt engineering, Skills, tool use, Harness work, and data-backed improvement.

The project is a portfolio experiment, not an offer guarantee or a claim to have shipped a large companion platform. Prior task-control experience is transferable, but it does not substitute for live companion conversation results.

## User and experience

- Adult users who want short, supportive, character-based conversations.
- A disclosed AI character named Nova with stable values and tone.
- Friendly and gentle-romance modes; affection remains optional and nonsexual.
- User-owned memory: inspect, approve, reject, and delete.
- No pressure to keep chatting, exclusive dependence, or paid engagement manipulation.

The chat is the primary product surface. Engineering traces are optional and kept out of normal conversation. The original 2D avatar provides a low-cost digital-character surface; it does not imply voice synthesis or a full digital-human system.

## Evidence mapping

| Requirement | Initial implementation | Remaining proof |
|---|---|---|
| Companion/romance result | Character UI, modes, persona instructions | Live-model transcripts, reviewed interaction quality |
| Multi-turn context | Recent messages in the provider request | Correction and topic-continuity tests on a real model |
| Memory | Pending proposals, approval, recall, deletion | Long-conversation conflict/update evaluation |
| ReAct/Harness | Bounded model-action-tool-observation loop | Live tool-call behavior and failure transcripts |
| Skills | Editable persona and grounding resource | Skill selection/versioning as future needs justify |
| DataAgent work | Natural-language whitelist-plan selection and actual synthetic aggregation, visible query/result trace | Real-model planning evaluation, approved datasets, measured quality changes |
| Engineering deployment | Localhost server, locked frontend deps, CI | Authenticated remote demo and runtime monitoring |

The DataAgent executes bounded analyses on a fixed labeled synthetic fixture. Its planner is deterministic and its arithmetic is real; it does not establish LLM planning quality, production data mining, or arbitrary SQL-agent deployment. Mock fixtures are infrastructure checks, not companion-quality scores.

## Interview narrative after this milestone

“I have built the companion-agent framework: a character chat interface, consent-based persistent memory, bounded tool calls, session analytics, and replayable checks. The current demo is mock-backed. Next I will connect a real model and publish reviewed examples and measurements of context continuity, persona consistency, and emotional responses.”

Only upgrade this narrative after live API integration and evidence are actually recorded.
