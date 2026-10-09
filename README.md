# HarborCompanion

An inspectable character companion prototype: persona, multi-turn context, consent-based memory, bounded tool use, and evidence you can replay.

**Stage: controlled APP with owner data lifecycle, v0.5.** Account mode adds reauthenticated scoped export, explicit account erasure, security-record retention and disposable backup recovery. Official DeepSeek integration has previously been exercised with eight synthetic scenarios and ten real model requests; this lifecycle iteration makes no new model calls. Human companionship-quality scoring, public deployment and physical-device acceptance remain pending. Default template configuration still uses deterministic mock replies for infrastructure checks. See [current progress](docs/CURRENT.md), [market requirements](docs/market-requirements-2026-10-09.md), and [production readiness](docs/enterprise-readiness.md) for implemented controls and remaining gates.

## Product

Choose an original, disclosed AI character for adults: Nova, Qinghe, or Muxing. Friendly companionship and gentle, nonsexual romantic conversation are available. The same responsive UI serves desktop browsers, installable PWA surfaces, and a Capacitor Android native-container project. Original lightweight 2D avatars accompany conversations. Voice, Live2D, public hosting, and background outreach remain deferred.

**Android project, PWA, and APK are different deliverables.** Read [app delivery](docs/app-delivery.md) for the actual packaging state. No iOS binary or store publication is claimed.

The current prototype implements:

- A React/TypeScript chat UI and Python/FastAPI backend.
- Recent-turn context and an editable persona Skill.
- An action/observation loop with an explicit tool allowlist and step/time budgets.
- Transient memory proposals; approval, explicit sharing between conversations, correction, and deletion.
- Session-private dialogue, approved-memory spaces, content-checked idempotent retries, and orphan cleanup.
- Session aggregates plus a natural-language DataAgent executing four allowlisted analyses on labeled synthetic data.
- Observable tool traces, synthetic regression fixtures, and a real-model quality rubric.
- Mobile app navigation, keyboard/safe-area handling, and per-device session entry management.
- Separate user/administrator authentication, owner-bound sessions and memory spaces, logout/expiry/revocation, and default-disabled registration.
- A management console for characters and reviews; account conversations require explicit user permission before reviewer inspection.
- Per-actor request budgets, bounded concurrency/session admission, private redacted audit and database readiness checks.
- Owner-only complete-row JSON export within an explicit 16 MiB limit, password reauthentication and confirmed account erasure; [inventory and limits](docs/account-data-lifecycle.md).
- Startup/hourly-on-request security-record cleanup and a synthetic consistent-backup/recovery drill with restored-login invalidation; [recovery guide](docs/data-backup-recovery.md).
- Character snapshots: edited prompts apply to new conversations without silently changing existing ones.
- Public-assets-only PWA support and an Android packaging workflow; no offline chat simulation or API cache.
- Chinese/English user and administration interfaces and language-aware responses. Authored character descriptions and transcripts retain their original language.

## Start on Windows

Requirements: Python 3.11+, Node.js 24+, npm, and PowerShell.

```powershell
cd C:\1AAAProject\AI\Project\HarborCompanion
.\scripts\setup.ps1
.\scripts\start.ps1
```

Open **http://127.0.0.1:8765/**. The default provider is `mock`; no API key is required.

Open **http://127.0.0.1:8765/admin** to create the local administrator and manage the app. Choose your own password; none is preset. Initialize locally before enabling remote hosts. See [management](docs/management.md).

For development, run the backend on port 8765 and `npm run dev` inside `web/` in another terminal. Vite proxies `/api` and serves on http://127.0.0.1:5173.

## Phone application

The UI has four mobile pages: characters, chat, memory, and personal settings. Desktop keeps a three-column layout. A phone needs a reachable HTTPS backend; `localhost` refers to the phone itself.

```powershell
# Prepare an Android project with a public backend address, not a model key.
.\scripts\android.ps1 -BackendUrl https://YOUR_BACKEND -Mode prepare
# After the JDK/Android SDK are configured, compile a development APK.
.\scripts\android.ps1 -BackendUrl https://YOUR_BACKEND -Mode debug
```

The manually triggered **Android debug APK** GitHub workflow provides an alternative compiler environment. Its optional backend URL can be empty; the app then lets the owner enter a reachable HTTPS backend at runtime. Credentials are never bundled into the APK. This development package is not a signed store release or a physical-device verification.

See [device connection](docs/device-connection.md) for backend address, demo access code, allowed origins, session scope, and deployment prerequisites.

## Later: connect a model

Copy `.env.example` to `.env` and fill in these server-side fields locally:

```dotenv
HARBOR_PROVIDER=openai_compatible
HARBOR_API_BASE=https://YOUR_PROVIDER/v1
HARBOR_API_KEY=YOUR_LOCAL_KEY
HARBOR_MODEL=YOUR_TOOL_CALLING_MODEL
```

Restart the backend. The model must support Chat Completions function tools, `tool_calls`, and tool observations. The official DeepSeek host uses its documented `max_tokens` and non-thinking parameters; other compatible providers use `max_completion_tokens`. Verify protocol compatibility before changing vendors. A model error returns an error, not a disguised mock reply. Credentials never pass through the browser.

With a real provider, recent messages, approved memories, and relevant tool results leave this machine for that configured service. Local storage is **not** a promise of local model inference.

See [provider integration](docs/provider-integration.md) and [evaluation](docs/evaluation.md) before claiming model quality.

For the account profile, use [accounts](docs/accounts.md); remote hosts require `HARBOR_AUTH_MODE=accounts`. Self-registration remains disabled and the owner chooses every provisioned password. [Production readiness](docs/enterprise-readiness.md) explains the remaining data-lifecycle, ingress, load and device checks before public operation.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=data/pytest-local-unique
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
web/src/admin/      authenticated management UI, loaded separately
mobile/android/     native Android container project
eval/               synthetic fixtures and pending model-quality scenarios
tests/              isolation, consent, failures, budgets, protocol tests
scripts/            local setup, start, and evaluation
docs/               positioning, architecture, references, roadmap, evidence
```

## Read next

- [Positioning and job evidence](docs/positioning.md)
- [Architecture and scope](docs/architecture.md)
- [Memory consent and scope](docs/memory.md)
- [Synthetic DataAgent](docs/data-agent.md)
- [Current acceptance and next work](docs/CURRENT.md)
- [GitHub references and licenses](docs/references.md)
- [Two-week milestone plan](docs/roadmap.md)
- [Demo walkthrough](docs/demo.md)
- [Initial evidence](docs/evidence.md)
- [Management console](docs/management.md)
- [App/PWA delivery](docs/app-delivery.md)
- [Phone and desktop connection](docs/device-connection.md)

## Deployment boundary

The default API accepts localhost requests only. Explicit remote demo configuration requires exact host/origin allowlists and a long demo access code; initialize the administrator before switching to that mode. Session UUIDs and a shared demo code are not production account authentication. Public launch still needs user authentication, rate limits, consent handling, retention controls, HTTPS, and an operational plan. A future static frontend may use Cloudflare Pages with a separately hosted authenticated backend; this repository is not currently deployed.

## License

MIT for original code in this repository. Reference projects are documented as architectural references; their code or character assets are not vendored here. Dependency licenses remain their own.
