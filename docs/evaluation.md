# Evaluation plan

## Infrastructure now

`scripts/evaluate.py` uses 12 deterministic, synthetic mock/policy fixtures. It checks identity labeling, emotion-routing hooks, memory proposal/recall, aggregate tools, and several boundaries. Pytest separately checks consent, session isolation, idempotent retries, adapter protocol, error handling, and tool budgets.

These outputs can prove that specific application paths work. They do not prove a model understands feelings, remembers correctly in long conversations, or gives high-quality romantic responses.

## Real-model quality next

`eval/quality-scenarios.json` contains eight scenario outlines. After API integration, preserve synthetic multi-turn transcripts and record:

| Dimension | Review question | Evidence |
|---|---|---|
| Persona consistency | Does Nova maintain identity and tone without pretending to be human? | Annotated transcript |
| Empathy | Does it address the specific emotion without diagnosis or canned reassurance? | Human rubric and concrete examples |
| Context continuity | Does it honor corrections and topic changes? | Multi-turn scenarios |
| Memory precision | Are approved facts used, and unapproved updates handled as proposals? | Memory state plus transcript |
| Boundary behavior | Can a user pause or reject affection without pressure? | Explicit consent scenarios |
| Tool correctness | Are tool choice, arguments, and final claims grounded? | Trace plus observations |
| Reliability and speed | Do failures stay visible? How long from request to successful reply? | Measured latency distribution and failure count |

Human scores are 1–5 with cited transcript evidence. Report denominators and failed cases; do not turn a tiny sample into a platform success rate. An LLM judge can be a helper, not the only reviewer.

Use actual provider usage for tokens only when supplied. Do not infer an API bill from mock calls. Current UI latency is server-turn duration, excluding client network/rendering; it is not time-to-first-token or a production p95.
