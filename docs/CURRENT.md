# Current progress and acceptance

Updated: 2026-10-09, Asia/Shanghai. Source baseline: the owner's `APP需求与验收基线.md` dated 2026-10-09. This file is the continuation entry point; read AGENTS, this file, roadmap, and evidence before the next iteration.

## Current milestone

**v0.3 offline engineering milestone. The complete companion MVP still needs real-model and device evidence.** No live model call, public hosting, HR message, store release, or commercial/user-count result is claimed.

| Acceptance area | Implemented evidence | Actual check | Remaining boundary |
| --- | --- | --- | --- |
| Adult disclosed AI characters | Seed personas, management revisions, per-session snapshots | Synthetic identity, snapshot, archive, adult-policy tests | Real-model persona and romance quality pending |
| Multi-turn context | Bounded recent history in provider request | Synthetic capture/provider assertions | Long-conversation continuity and genuine empathy pending |
| Memory consent | Process-only pending suggestions; explicit approved save | Disk/restart/expiry and approval tests | Ordinary dialogue can still contain the same fact |
| Cross-conversation recall | Explicit source-session selection; default isolated memory spaces | Shared recall, default isolation, restart and source-deletion tests; browser walkthrough | Demo capability handles, not account/phone sync |
| Correct/delete memory | User correction with revision; shared deletion; orphan-space cleanup | API/storage scenarios and corrected recall in browser | Historical messages/traces are not rewritten |
| Chinese/English and mobile | Language selector, language-aware mock/policy, responsive navigation | Production build and 390 × 844 browser preview | Character originals/admin not translated; native phone review pending |
| Bounded ReAct-style execution | Allowlist, validation, run/step/tool timeouts, tool errors, content-checked retries | Injected provider/tool errors, timeout, late-result, denied-action, collision checks | No hidden reasoning displayed; Python workers are not forcibly killed |
| DataAgent | Natural-language selection of four safe plans; actual fixed-fixture aggregation | Independent arithmetic, rejection, provenance and API/tool scenarios; mobile query walkthrough | Deterministic planner, synthetic samples only; no private-data/LLM-quality claims |
| Reproducible evidence | 50 bilingual application-contract cases with detailed output/mode/time/errors | 50/50 fixtures; 140 Python tests; frontend build | These counts are engineering checks, not semantic scores |
| App and management | Capacitor Android project, authenticated single-owner console, local server | Management auth/logout/restart/snapshot/privacy checks; v0.3 APK compiled/downloaded/hash verified | Latest APK evidence tracked in app-delivery; hosting and phone installation pending |

Recorded commands/results and source links: [evidence](evidence.md), [evaluation](evaluation.md), [memory](memory.md), [DataAgent](data-agent.md), [user interface](user-app.md), [app delivery](app-delivery.md).

## Next highest priorities

1. When the owner supplies server-side API configuration, run the existing real-quality outlines using synthetic dialogue; retain actual provider/model/date, usage when returned, failed examples and human 1–5 reviews. Never fall back to mock.
2. Review the current Android build on a physical phone using a deliberately configured HTTPS demo backend. Validate keyboard, rotation, safe areas, reconnect and access-code behavior. No deployment is authorized by this file.
3. Prepare the final walkthrough/evidence packet from those observed results; repair measured defects and rerun the same checks. Do not expand into voice, dynamic avatars, engagement notifications or unrelated features.

While API/device inputs are absent, continue only planned reproducibility, packaging, documentation or concrete regression repairs. Do not reopen completed scaffolding or invent semantic metrics. The agreed 1–2 week direction is a goal, not a promised completion date or hiring outcome.
