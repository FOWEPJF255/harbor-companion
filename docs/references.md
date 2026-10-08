# GitHub references

Reviewed on 2026-10-09. These are design references, not dependencies or copied implementations. No third-party character assets are included. Stars and marketing claims are deliberately not used as personal project metrics.

| Reference | What to study | Decision for HarborCompanion |
|---|---|---|
| [moeru-ai/airi](https://github.com/moeru-ai/airi) · MIT | Character interfaces, interactive companion surfaces | Start with an original lightweight 2D avatar; defer realtime voice/3D |
| [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern) · AGPL-3.0 | Character and conversation configuration UX | Learn interaction patterns; do not copy or vendor its source |
| [letta-ai/letta](https://github.com/letta-ai/letta) · Apache-2.0 | Stateful agent and memory concepts | Use explicit local consent-based memory first; the README currently points active source to [letta-code](https://github.com/letta-ai/letta-code) |
| [mem0ai/mem0](https://github.com/mem0ai/mem0) · Apache-2.0 | Memory lifecycle and retrieval tradeoffs | Keep SQLite memory transparent and inspectable before adding embeddings |

The comparison products described in the recruiting conversation are market inspiration only. They are not proof of this project's user scale, relationship quality, or commercial success.

The provider tool-message contract was checked against [official OpenAI function-calling documentation](https://developers.openai.com/api/docs/guides/function-calling). The adapter preserves assistant tool calls and matches each tool observation to its call ID. Compatibility with any particular third-party provider remains to be verified after credentials are supplied.

Licenses above reflect the referenced repository pages at review time. Any future source or asset reuse requires a fresh license and provenance check.
