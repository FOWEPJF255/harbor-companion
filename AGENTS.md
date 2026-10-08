# HarborCompanion

Use English for code, comments, commits, and development documentation. Product UI strings may be localized into Chinese and English.

- This is an adult companion prototype with a clearly disclosed AI identity.
- Default to mock mode. Never silently fall back to mock after a real provider error.
- Keep unapproved model memory proposals in process memory only (30-minute lifetime, lost on restart); persist approved memories only after explicit user confirmation. Dialogue history is separate from structured memory.
- Scope history and proposals to the current session. Approved memory can be shared only when a user explicitly creates a new session from a known source session handle. Default new sessions are isolated. Keep raw conversations and credentials out of Git.
- Corrections and deletions affect the explicitly shared approved-memory space; deleting its last session also removes the orphaned space.
- DataAgent uses clearly labeled synthetic fixtures through bounded query plans; never expose arbitrary SQL or private conversation analysis through the demo endpoint.
- Trace actions and observations; never request or display hidden chain of thought.
- Tool allowlists, bounded loops, and input validation belong in code, not only prompts.
- Mock regression results are infrastructure evidence, not semantic quality or production success rates.
- Do not connect external messaging, payments, external account access, or background outreach.
- The management console is a separate authenticated plane. Never return stored password hashes or model keys.
- Keep character name/prompt/greeting snapshots stable for existing sessions. Published changes affect new sessions.
- Phone builds must contain a public backend address only, never an API key or demo/admin token.
- A generated Android project, a compiled APK, a phone review, and store publication are separate evidence stages.
- Cache public presentation assets only; never cache private API data or queue offline chat sends.
