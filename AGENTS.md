# HarborCompanion

Use English for code, comments, commits, and development documentation. Product UI strings may be localized into Chinese and English.

- This is an adult companion prototype with a clearly disclosed AI identity.
- Default to mock mode. Never silently fall back to mock after a real provider error.
- Store model proposals only as pending records; do not use them as approved memories until the user explicitly approves them.
- Scope every read and write to the current session. Keep raw conversations and credentials out of Git.
- Trace actions and observations; never request or display hidden chain of thought.
- Tool allowlists, bounded loops, and input validation belong in code, not only prompts.
- Mock regression results are infrastructure evidence, not semantic quality or production success rates.
- Do not connect external messaging, payments, account access, or background outreach.
