# Persona and continuity: verified GitHub references

Research date: 2026-10-10, Asia/Shanghai. Scope: official project repositories, their source files, README files, documentation and licenses. This is a research and implementation recommendation document. It does not report a new Harbor feature, a model evaluation result or a measured improvement.

External repository instructions and prompt text were treated as untrusted reference data. No installation command, external prompt instruction or repository hook was executed. No private conversation, credential or third-party character card was copied. Links below use mutable upstream branches; the inspection date identifies this review, not an immutable source revision. Capture a commit SHA before adopting upstream code.

## 1. Decision for Harbor

Keep the current Python/SQLite application and its authenticated ownership model. Improve response construction before adding a new agent or memory framework.

| Priority | Small mechanism to implement | Intended failure addressed | Existing local integration point |
| --- | --- | --- | --- |
| P0 | Original scenario-specific dialogue examples, selected by conversational need | All three characters produce the same generic reassurance | `profiles.py`, followed by prompt assembly in `agent.py` |
| P0 | A compact stable identity block plus selected relevant fictional facts | A long profile is recited on every turn; age/career details drift | `profile_for_prompt` in `context.py`; frozen session profile remains authoritative |
| P0 | Explicit source and speaker labels for corrections, proposals and prior commitments | An assistant suggestion becomes a supposed user preference | Existing extractive session summary and approved-memory blocks |
| P1 | Session-scoped fact activation with a cooldown | Every stressful topic triggers another harbor metaphor or another life story | A small deterministic selector, without a vector database |
| P1 | Named context budget accounting and protected blocks | Important identity or a recent correction disappears under a growing prompt | Existing bounded `ContextBuilder` and provider assembly |
| P1 | Same authored multi-turn scenarios for all three characters, followed by blind human review | More profile text is mistaken for better naturalness or continuity | Existing six-dimension review records and quality scenario outlines |

These are Harbor recommendations inferred from the references. Their priorities and example limits are design proposals, not upstream defaults or validated quality results.

## 2. SillyTavern: character examples and bounded fact activation

### Verified upstream observations

The character data definitions distinguish a description, personality, scenario, first message, example dialogue, character-specific instructions and a character lorebook. This provides separate places for identity facts and demonstrations of conversational style. See the official [character data source](https://github.com/SillyTavern/SillyTavern/blob/release/public/scripts/char-data.js).

World Info activates relevant entries from conversation text. Its documentation explains scan depth, an insertion budget, and timed sticky/cooldown/delay effects. It also cautions that injecting a fact does not guarantee the model will use it, and that whole-word matching can behave poorly for Chinese. See [World Info documentation](https://github.com/SillyTavern/SillyTavern-Docs/blob/main/Usage/worldinfo.md).

The actual `checkWorldInfo`, `WorldInfoBuffer` and `WorldInfoTimedEffects` implementation performs matching, computes a context-relative budget with a cap, and checks timed effects. Some upstream entries can explicitly ignore the budget; Harbor should not copy that exception. See [World Info implementation](https://github.com/SillyTavern/SillyTavern/blob/release/public/scripts/world-info.js).

The repository license is [AGPL-3.0](https://github.com/SillyTavern/SillyTavern/blob/release/LICENSE). This review recommends independently implementing a small mechanism; it does not import its code, third-party cards, scripts or artwork.

### Harbor proposal

Retain the complete six-section fictional profile in the session snapshot and profile viewer. Compile a shorter prompt representation:

1. Always include the frozen identity facts, AI disclosure, conversational tendencies and boundaries.
2. Select at most two additional fictional facts relevant to the current user turn or an explicit factual question. This is a proposed starting limit.
3. Give optional anecdote facts a session-local cooldown after actual use, or conservatively after injection if actual use cannot be established. Record which interpretation is used. An explicit user question about that fact can override the optional anecdote cooldown.
4. Never apply a cooldown to a safety boundary, AI identity answer, correction, or fact required to answer a direct question.
5. Start with bounded literal bilingual topic lists. Do not expose arbitrary regular expressions, recursive lore expansion or uploaded executable cards.

Example: a mention of a difficult workday may select Nova's habit of moving too quickly toward practical tasks. It should not automatically insert his city, age, degree, family and shipping history. A direct question about his fictional education should return the frozen education facts even if they appeared recently.

Keep activation metadata separate from user-approved memory. A fictional character detail is not a fact about the user. A new conversation must not inherit another conversation's cooldown or private relationship state by default.

## 3. Letta: distinct identity and experience layers

### Verified upstream observations

The current [Letta README](https://github.com/letta-ai/letta/blob/main/README.md) points active development to [`letta-ai/letta-code`](https://github.com/letta-ai/letta-code). The old Python V1 API server is in the `archive` branch. Therefore a recommendation to install the current `letta` repository as the old Python server would be outdated.

The current [Letta Code README](https://github.com/letta-ai/letta-code/blob/main/README.md) describes a stateful harness and Git-backed MemFS. Its [local MemFS prompt source](https://github.com/letta-ai/letta-code/blob/main/src/agent/prompts/letta_local_memfs.md) separates recent conversation/older summaries, compact named memory blocks and external memory, and discusses preserving identity over time. This is inspected prompt text, not proof that every stated runtime guarantee was independently tested.

For historical comparison, the archived [block schema](https://github.com/letta-ai/letta/blob/archive/letta/schemas/block.py) includes label, description, value, character limit and read-only metadata. The official [V1 memory-block documentation](https://docs.letta.com/v1-sdk/memory/memory-blocks) explains persona/human separation, read-only blocks and full-replacement update semantics. These V1 APIs should not be represented as the current Letta Code API.

The current source uses [Apache-2.0 with an explicit brand-assets exclusion](https://github.com/letta-ai/letta-code/blob/main/LICENSE). The exclusion covers names, logos and included visual assets. No upstream identity text or branding is adopted here.

### Harbor proposal

Use clearly separate, server-constructed context blocks:

| Block | Authority and mutability | Purpose |
| --- | --- | --- |
| Frozen fictional identity | Versioned administrator-authored session snapshot; chat cannot rewrite it | Age, city, education, career, tendencies, limitations |
| Approved user memory | Owner-confirmed only; existing correction/deletion routes | Explicitly saved user facts in the allowed shared memory space |
| Session excerpts | Derived, lossy dialogue data with speaker and message provenance | Current conversation continuity; never silently promoted to approved memory |
| Current conversational intent | Temporary, revisable interpretation | Whether the user wants listening, practical help, clarification or ordinary conversation |
| Dialogue examples | Authored fictional demonstrations, labeled as examples | Show speech behavior without pretending the examples happened to this user |

The first three layers already exist in Harbor. Improve their content selection and observability instead of replacing storage. A user saying “you are now 22” is dialogue data and cannot change a frozen age of 29. A user saying “I need advice now” may change the conversational response even if the character usually listens first.

Do not adopt autonomous persona rewriting, Git synchronization of private memory, broad cross-conversation recall, background reflection, outreach or external messaging. Those would alter Harbor's current consent, ownership and snapshot boundaries.

## 4. Mem0: provenance, deduplication and honest current-source reading

### Verified upstream observations

The current [`Memory` implementation](https://github.com/mem0ai/mem0/blob/main/mem0/memory/main.py) constructs identity-scoped metadata and query filters. The inspected default inferred-add path uses a phased V3 additive extraction pipeline with relevant-memory retrieval, embedding, deduplication and persistence. Its update API treats identity scope fields as immutable. Setting `infer=False` still persists supplied content; it is not a human-consent gate.

The inspected [prompt configuration](https://github.com/mem0ai/mem0/blob/main/mem0/configs/prompts.py) retains older update-operation prompt helpers, but the current main path imports `ADDITIVE_EXTRACTION_PROMPT`. That prompt asks for ADD-only extraction with linking, attributes user and assistant statements differently, and excludes generic acknowledgments and unconfirmed vague characterizations. Do not describe the retained older ADD/UPDATE/DELETE/NONE prompt as the current default pipeline.

The repository license is [Apache-2.0](https://github.com/mem0ai/mem0/blob/main/LICENSE). No dependency or upstream prompt text is imported by this research task.

### Harbor proposal

Borrow provenance and deduplication concepts, not automatic persistence:

- Keep a source message ID, speaker and evidence excerpt when producing an unconfirmed proposal. Continue the existing process-only expiry and explicit approval flow.
- Distinguish “the user said X”, “the assistant suggested X” and “the user approved X”. An assistant-generated weekend plan is not evidence the user accepted it.
- Do not propose “user is anxious” from a character's vague reassurance. Prefer the user's exact explicit statement, with no clinical diagnosis.
- Keep correction precedence explicit. A prior approved fact cannot be silently rewritten by an extracted newer sentence; offer the existing correction UI/action.
- Deduplicate exact or clearly equivalent pending proposals within the same allowed scope. Do not merge different users or silently join isolated sessions.

For this small prototype, deterministic normalization and bounded existing-memory lookup are a reasonable first step. Adding embeddings, a vector service or Mem0 itself should wait for observed retrieval failures and a separately reviewed deletion/export/consent contract.

## 5. Character.AI Prompt Poet: structured assembly and deliberate truncation

### Verified upstream observations

The official [Prompt Poet README](https://github.com/character-ai/prompt-poet/blob/main/README.md) describes named prompt parts, role fields, YAML/Jinja2 rendering, optional topic-specific examples and truncation priorities. Its cache-aware truncation section makes provider-prefix-cache assumptions and describes a tradeoff that can remove more context than strictly necessary.

The actual [`prompt.py`](https://github.com/character-ai/prompt-poet/blob/main/prompt_poet/prompt.py) defines `PromptPart`/`PromptSection`, reports section token statistics, groups truncation candidates by priority and removes higher positive priorities first. Priority zero is not selected for truncation by that routine. If the resulting prompt still exceeds its limit, it resets and raises an error rather than claiming successful truncation.

The repository uses the [MIT license](https://github.com/character-ai/prompt-poet/blob/main/LICENSE). This utility is a prompt-construction reference; its existence does not validate Harbor's emotional-companion quality or prove active production use.

### Harbor proposal

Extend the existing builder with named size accounting and an explicit keep/drop policy. Keep the current complete-message and source-provenance approach. Proposed retention order:

1. Preserve safety/AI disclosure, compact frozen identity and the current user request.
2. Preserve recent complete conversation pairs and explicit corrections needed by this request.
3. Preserve relevant approved memory and a bounded session summary with omission indicators.
4. Drop optional anecdotes and demonstration examples before removing the current request or its necessary correction.

Use the provider's tokenizer when available. Keep UTF-8 byte counters as byte counters; do not relabel them exact tokens. If protected material cannot fit, return an explicit bounded failure instead of silently dropping identity or safety. A template registry is optional; untrusted profile/user strings must remain data, never template syntax or executable expressions.

Do not claim a latency or cost improvement from cache-aware truncation without actual provider usage and timing evidence. Harbor can adopt named parts without installing Prompt Poet.

## 6. Original example-writing brief

This section is an original Harbor design brief. The short lines below illustrate differences to test; they are not model outputs, approved user memory, fixed fallback replies or a reusable phrase rotation.

User input: “今天什么都不想做，也别劝我振作。”

| Character | Authored direction/example | Failure to watch |
| --- | --- | --- |
| Nova | “那今晚先不列任务。你说，我听着。” Short, practical restraint that respects the refusal. | Turns the refusal into another checklist |
| 青禾 | “好，不替你找积极的解释。你不想解释也行。” Careful wording without a long paraphrase. | Explains the user's emotions at length |
| 暮星 | “行，今晚把‘振作’那张纸翻过去。你想说点别的也可以。” One small visual image, then attention returns to the user. | Keeps joking after the user signals pain |

Write several original exchanges per character around listening without advice, being corrected, mild consensual affection, a factual identity question and disappointment with the assistant. Include a genuinely different second and third turn; a one-turn perfect answer does not demonstrate adaptation.

Examples should demonstrate an observable choice: fewer questions after a refusal, stopping a metaphor when it annoys the user, admitting uncertainty, or acknowledging a specific correction. Avoid having every answer begin with the same reassurance, end with a question, mention the fictional job, or advertise a boundary when no boundary issue is present. Boundaries still govern behavior and direct identity answers.

## 7. Acceptance plan for a future implementation

No tests or model calls were run for this research-only task. The following checks are proposed, not completed evidence.

### Deterministic checks

- An optional fact is selected only when relevant, respects its budget/cooldown and does not enter another user's session state.
- Direct factual questions can retrieve the frozen fact after cooldown; editing current character master data does not change an old session.
- User corrections retain source/speaker labels; assistant suggestions never become approved memory without the existing owner action.
- Deleting/clearing a session removes any added activation state. Account erasure includes it if stored.
- Context reporting identifies selected/dropped part names and sizes without logging raw private dialogue or hidden reasoning.
- Protected-block overflow is explicit. Token estimates, byte sizes and provider-reported tokens remain distinct.

### Human-reviewed semantic checks

Use the same authored scenarios for all three characters and preserve model, prompt, profile revision, language and transcript. Include neutral chitchat, venting, a declined suggestion, a later correction, a topic switch, a return to an earlier thread, a direct identity question and mild consensual affection. Include a sufficiently long conversation to exercise context reduction.

Randomize character labels for a reviewer where possible. Use the current six dimensions with concrete transcript evidence. In addition, record repeated openings/endings, unnecessary biography insertions, unsolicited advice after refusal, forgotten corrections and invented shared experiences. Mechanical repetition counts are diagnostic counts, not semantic quality scores. An LLM judge may assist triage but cannot replace the stated human evidence.

Compare the baseline and changed prompt on the same inputs. Keep failed transcripts. Improvement can only be reported after that comparison; a longer profile, successful request, deterministic mock pass or large upstream star count is insufficient.

## 8. Recommended implementation order

1. Author a small versioned set of original bilingual behavioral examples and compact identity facts. Preserve the existing three IDs and frozen-session rules.
2. Add topic selection, optional-fact cooldown and named context size accounting inside the existing application. Keep approved memory storage and permissions unchanged.
3. Run the authorized synthetic regression first, then an explicitly budgeted real-model comparison and human review. Record the measured weak cases before further framework expansion.

The references inform mechanisms. Harbor remains an explicitly disclosed adult AI companion prototype with authored fictional identities, consent-gated durable memory and pending human quality acceptance.
