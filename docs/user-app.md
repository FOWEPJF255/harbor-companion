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
- The management console has a separate bilingual interface that follows the same selected language. Its login and data remain separate from ordinary user accounts.
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

Both backend connection and identity determine local session state. Capability-mode browser links use `getSessionKey`; account-mode active links additionally use the verified user ID via `getUserSessionKey`. Changing a backend does not transmit the previous backend's session handles to the new target. Anonymous links do not sync between devices automatically.

The app can reach My space even when a native app has no backend address yet. Native deployment needs a reachable HTTPS backend and the operator's demo access code where required. Model API keys remain on the server.

## Ordinary user accounts

`GET /api/status` declares either `local_demo` or `accounts` plus `registration_enabled`. The UI cannot infer account readiness from model configuration. The local demo retains the original anonymous capability workflow and states that it is not a deployed multi-user service. A remotely exposed backend must use accounts mode.

In accounts mode, My space provides ordinary-user login and, only when enabled by the server, self-registration. Self-registration is disabled by default; the operator provisions accounts through the separate management or CLI process. Usernames are 3–40 ASCII letters, digits, underscores, dots, or hyphens and are normalized by the server. Passwords are 12–128 characters. The UI asks for adult confirmation before login; registration and new-session requests additionally carry explicit server-side confirmation.

The login body contains only `username` and `password`. Registration sends those fields and `adult_confirmed: true`. Responses contain the public user identity, an opaque access token, and expiry; the browser does not request password hashes. Password inputs are never written to application storage and are cleared after attempts. Browser password-manager behavior is controlled by the browser.

An ordinary-user access token is kept in `sessionStorage`, scoped to the backend URL. Restoration calls `/api/auth/me` before loading private sessions. It is passed explicitly through `userApi` and never silently applied to `/api/admin/*`; administrator login and operator access codes are independent. The UI's backend connection input is not a place for model credentials.

Account-mode session lists come from the authenticated server rather than the anonymous device registry. They show 20 items per page and offer an explicit Load more control when `next_cursor` is returned. The last-used session is stored separately per backend and verified user. Existing anonymous sessions are not automatically claimed.

Sign-out clears local identity, chat, session lists, observable traces, retries, memory drafts, and analysis input immediately, then requests server token revocation. Failure to confirm server revocation is shown explicitly. Backend changes, expiry, and sign-out abort user requests and increment an identity epoch. Responses from an earlier identity cannot write a later user's state or session cache. Returning to a previously configured backend still verifies its stored token before restoration.

## Permission for human review

My space → Privacy and usage boundaries includes an unchecked-by-default consent control for the current session. Only an explicit action sends `POST /api/sessions/{sid}/review-access` with `allowed: true`. The explanatory copy names the messages, memories, and review material that an administrator may inspect for human quality assessment. Withdrawal sends `allowed: false`.

The backend owns permission and account-ownership enforcement; the browser checkbox is not an authorization boundary. In account mode, revoked or absent permission prevents administrator access to raw session/review material. Sharing approved memory is a different consent action and does not grant administrator review access.

## Verification scope

The v0.5 My space extension adds an authenticated account-data panel for password-reauthenticated export and explicit permanent deletion. It is absent in local-demo mode. Export contains complete owned rows within a 16 MiB budget; deletion requires the exact typed `DELETE`. Incorrect current passwords preserve login, while expired/revoked tokens clear identity. Successful deletion clears the current account's saved session handles, token and private UI and keeps a translated completion notice. See [full inventory and limits](account-data-lifecycle.md).

The v0.5 frontend rebuild passed. Lifecycle API and race checks use synthetic data; browser automation remained unavailable, so account-data interaction, translated layout and native download behavior have not been visually accepted.

`npm run build` completed on this iteration: TypeScript validation and the Vite production bundle succeeded. This is a build result, not physical-device operation or semantic conversation evaluation.

The isolated loopback service at `http://127.0.0.1:8766` used mock mode, two provisioned synthetic users, disabled registration, and disposable synthetic data. Ten HTTP assertion groups passed: public account-mode disclosure, no-token denial, disabled registration, both users' login and `me`, default-isolated versus explicit shared memory, cross-owner read/share/permission denial, grant/withdraw review permission, an English mock turn, 20-item pagination, and revoked-token denial after logout. The record is `reports/user-accounts-http-2026-10-09.json`; it contains no passwords or tokens. These requests verify the live API contract, not React interactions.

Browser automation was attempted with CUA, but all browser extension surfaces returned `nodeRepl.fetch request failed` and the in-app browser was unavailable. No 390-pixel screenshot or interactive browser acceptance is claimed in that report. Browser/phone acceptance still needs both languages through login, account switching, creation, explicit memory sharing, correction, deletion, analysis, request failure, and logout. In particular, cancellation of late UI responses and the absence of cross-user drafts require a browser-level walkthrough in addition to the identity guards implemented in code.
