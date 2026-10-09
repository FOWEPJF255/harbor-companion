# Two-week MVP milestone plan

This is a plan, not a promise to a recruiter or evidence of completed work. API availability and review feedback affect timing.

## Current checkpoint: 2026-10-09

The v0.4 checkpoint adds user accounts, object ownership, explicit reviewer permission, request/concurrency budgets, private redacted audit and initial real DeepSeek execution evidence. The v0.3 consent/bilingual/DataAgent foundation is preserved. Local checks and actual model runs are recorded in [evidence](evidence.md); human semantic-quality scoring and physical-phone operation remain pending. Continue from [CURRENT](CURRENT.md) rather than rebuilding milestone 0.

The owner's new enterprise-engineering direction is tracked in [production readiness](enterprise-readiness.md), derived from [official market sources](market-requirements-2026-10-09.md). Finish owner data lifecycle and quality feedback next. Organization tenancy, distributed infrastructure and a production launch are not completed by the account foundation.

Existing voice, dynamic-avatar and outreach deferrals remain in force. Streaming is optional only after an observed UX need, not a required new feature.

## Milestone 0: framework

- Character chat UI and adult confirmation.
- Fixed persona, friend/gentle-romance modes.
- SQLite session history and consent-based memory.
- Mock and compatible-provider interface.
- Bounded tools, local analytics, observable traces, and synthetic checks.
- GitHub repository, docs, and CI.

Acceptance: start locally without credentials, demonstrate approval/recall/deletion, show tool traces, pass objective checks, and clearly disclose mock status.

## Week 1: real conversation results

- Supply API configuration and verify genuine tool calls.
- Review persona and mode-specific responses with synthetic multi-turn data.
- Exercise correction, memory conflict, stressed-user listening, and relationship boundaries.
- Add streaming only if measured UX needs it.
- Record small-sample end-to-end latency and token usage without overstating results.

Acceptance: reproducible real-model transcripts with provider/model/date, visible failed cases, and human-reviewed quality evidence.

## Week 2: showcase and iteration

- Use session aggregates to identify recurring failures.
- Fix one measured weakness and rerun the same scenario set.
- Capture an original-character demo and a short architecture walkthrough.
- Prepare a demo deployment only after authentication, rate limits, retention, and consent controls are ready.
- Update portfolio/resume to match actual results, with a clear distinction between framework and model evidence.

## Deferred

Voice, Live2D/3D, payments, engagement notifications, messaging-platform integrations, autonomous outreach, distributed serving, and large-scale analytics. No user-count, relationship-quality, or commercial claims are implied.
