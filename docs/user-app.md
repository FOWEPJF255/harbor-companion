# User app: language, consent, and observable analysis

## Interface layout

The phone UI has four main tabs: Characters, Chat, Memory, and My space. Data analysis opens as a separate page from My space. Its Back control returns to My space; it does not replace or change the companion session. Desktop users keep the character/chat/details layout, with the center column temporarily showing data analysis when selected.

The app uses the visual viewport, safe-area insets, an independently scrolling message list, and a composer that avoids sending during IME composition. A failed chat keeps its input and original request identifier for explicit retry. Offline messages are not queued.

## Chinese and English

The top-bar language selector provides `zh` and `en`. The preference is stored under the browser key `harbor-language`, with Chinese as the initial default. The document language is updated to `zh-CN` or `en`.

User-facing navigation, consent, chat controls, memory editing, session management, privacy copy, connection settings, basic installation instructions, mock disclosure, and the data-analysis view are localized. Both session creation and chat requests carry `language`.

Boundaries:

- Character names, introductions, and stored greeting snapshots stay in their original language. The English view states this explicitly.
- Existing messages and memory contents are not automatically translated.
- Tool names, status codes, fixture fields, and observable JSON stay faithful to the backend records.
- The management console remains Chinese in this iteration and its entry says so.
- English browser installation currently uses browser-menu instructions. The existing dedicated install-prompt component remains available in the Chinese view. Native apps do not show browser installation instructions.
- Real-model response language and semantic quality still require provider integration and separate evaluation. A translated interface is not evidence of international deployment or growth.

## Memory consent and sharing

New sessions use an isolated memory space by default. When an existing session is open, the character page provides an unchecked **Reuse approved memories** control. Only an explicit selection sends `memory_from_session_id` with the known source session handle.

The copy explains that this shares approved structured memory only, not dialogue history or pending suggestions. Correcting or removing a shared memory affects linked sessions.

Pending proposals are labeled separately. They belong to the current session's process-local pending queue, expire after at most 30 minutes, and disappear after a server restart. An approval click, an explicitly submitted correction, or the manual-memory form is required to turn a proposal into approved memory.

The correction form submits `PUT /api/sessions/{sid}/memories/{mid}` with a trimmed `content` field. It does not edit silently and requires an explicit confirmation action.

Deletion language follows the backend lifecycle:

- Clearing chat history retains approved memories and removes pending suggestions and related reviews.
- Removing a session retains approved memories only in other retained sessions that share the same space.
- Removing the last session also removes its orphaned memory space.
- A user can delete a memory directly before deleting a session when they want linked sessions to stop retrieving that fact.
- Previous dialogue may still contain facts mentioned earlier; deleting a structured memory does not rewrite message history.

## Observable traces

Latest successful or failed chat attempts can show backend-provided traces. Each expandable step exposes its tool input, observation, name, and status when available. The UI never requests or displays hidden chain of thought.

Failure traces are labeled as failed attempts and do not create a successful reply or a fabricated persisted turn. Traces reset when changing the active companion session or backend connection.

## Data analysis

The page sends `POST /api/data-agent` with a natural-language `question` of at most 300 characters. Suggested Chinese and English questions match the currently allowlisted plans:

- Tool success, error, timeout, and denial counts.
- Synthetic emotion-label distribution.
- Synthetic elapsed-time summaries.
- Injected evaluation-failure reasons.

The result displays the answer, actual execution plan, query result, source, scope, and expandable observable trace. Object, array, and string values are rendered as text/JSON without executing HTML or SQL.

The page explicitly states that these are public synthetic fixtures, processed by a rule-based bounded workflow. Fixture statistics are not measured model quality, private user analysis, production metrics, or medical emotion classification. Unsupported questions should produce an error rather than an invented answer.

## Backend connections

Browser session links use `getSessionKey` so different backend URLs have different link registries. Changing a backend does not transmit the previous backend's session handles to the new target. Known links do not sync between devices automatically.

The app can reach My space even when a native app has no backend address yet. Native deployment needs a reachable HTTPS backend and the operator's demo access code where required. Model API keys remain on the server.

## Verification scope

`npm run build` completed on this iteration: TypeScript validation and the Vite production bundle succeeded. This is a build result, not physical-device operation or semantic conversation evaluation. Browser/phone acceptance should still walk both languages through creation, explicit memory sharing, correction, deletion, safe analysis, and failed-request recovery.
