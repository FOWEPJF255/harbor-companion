# HarborCompanion

An inspectable character companion prototype: persona, multi-turn context, consent-based memory, bounded tool use, and evidence you can replay.

**Stage: framework prototype.** The default mock provider uses deterministic replies to exercise infrastructure. Real conversational empathy, context quality, and relationship consistency are **not evaluated yet**. A server-side OpenAI-compatible adapter is ready for later credentials; no live API call has been made during the initial build.

## Product

Nova is a disclosed AI character for adults. Choose friendly companionship or gentle, nonsexual romantic conversation. This is a local web prototype, not a messaging bot. An original lightweight 2D avatar accompanies the conversation. Voice, Live2D, public hosting, and background outreach are outside this first milestone.

The first milestone demonstrates:

- A React/TypeScript chat UI and Python/FastAPI backend.
- Recent-turn context and an editable persona Skill.
- An action/observation loop with an explicit tool allowlist and step/time budgets.
- Memory proposals that become usable only after explicit user approval.
- Session-scoped SQLite storage, idempotent retries, and full session deletion.
- A read-only session analytics tool, with clearly labeled heuristic mood data.
- Observable tool traces, synthetic regression fixtures, and a real-model quality rubric.

## Start on Windows

Requirements: Python 3.11+, Node.js 24+, npm, and PowerShell.

```powershell
cd C:\1AAAProject\AI\Project\HarborCompanion
.\scripts\setup.ps1
.\scripts\start.ps1
```

Open **http://127.0.0.1:8765/**. The default provider is `mock`; no API key is required.

For development, run the backend on port 8765 and `npm run dev` inside `web/` in another terminal. Vite proxies `/api` and serves on http://127.0.0.1:5173.

## Later: connect a model

Copy `.env.example` to `.env` and fill in these server-side fields locally:

```dotenv
HARBOR_PROVIDER=openai_compatible
HARBOR_API_BASE=https://YOUR_PROVIDER/v1
HARBOR_API_KEY=YOUR_LOCAL_KEY
HARBOR_MODEL=YOUR_TOOL_CALLING_MODEL
```

Restart the backend. The model must support Chat Completions function tools, `tool_calls`, and tool observations. The adapter currently sends `max_completion_tokens`; verify compatibility with the selected provider. A model error returns an error, not a disguised mock reply. Credentials never pass through the browser.

With a real provider, recent messages, approved memories, and relevant tool results leave this machine for that configured service. Local storage is **not** a promise of local model inference.

See [provider integration](docs/provider-integration.md) and [evaluation](docs/evaluation.md) before claiming model quality.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/evaluate.py
cd web
npm run build
```

Synthetic framework results do not measure model empathy, clinical accuracy, production throughput, or 24/7 reliability. Reports in `reports/` and runtime data in `data/` are ignored by Git.

## Repository map

```text
server/harbor/       API, storage, provider, tools, policies
server/harbor/skills/ persona instructions and conversational resources
web/                React UI with original SVG avatar
eval/               synthetic fixtures and pending model-quality scenarios
tests/              isolation, consent, failures, budgets, protocol tests
scripts/            local setup, start, and evaluation
docs/               positioning, architecture, references, roadmap, evidence
```

## Read next

- [Positioning and job evidence](docs/positioning.md)
- [Architecture and scope](docs/architecture.md)
- [GitHub references and licenses](docs/references.md)
- [Two-week milestone plan](docs/roadmap.md)
- [Demo walkthrough](docs/demo.md)
- [Initial evidence](docs/evidence.md)

## Deployment boundary

The initial API accepts localhost requests only. Session UUIDs are local capability handles, not production authentication. Do not expose this server publicly. Public hosting needs authentication, rate limits, consent handling, retention controls, HTTPS, and a deployment-specific security review. A future static frontend may use Cloudflare Pages, with a separately hosted authenticated backend; this repository is not currently deployed.

## License

MIT for original code in this repository. Reference projects are documented as architectural references; their code or character assets are not vendored here. Dependency licenses remain their own.
