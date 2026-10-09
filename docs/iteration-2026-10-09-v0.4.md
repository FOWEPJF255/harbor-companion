# v0.4 accounts, operations and actual-model iteration

Date: 2026-10-09, Asia/Shanghai. Starting code was the existing Harbor project and v0.3 acceptance checkpoint; no duplicate app was created.

## User direction

The owner supplied a server-side API key and requested continued upgrades based on real market requirements toward enterprise engineering. The owner then identified the provider as official DeepSeek. This authorized model integration and project development; it did not authorize public deployment, store release or contacting HR.

## Delivered changes

1. A [14-source market register](market-requirements-2026-10-09.md) separates official product/job/engineering signals from proposed features and current implementation. Dynamic official JD bodies were indexed, and vacancy status was not verified.
2. Account authentication, owner-bound sessions and approved-memory spaces, service-side pagination, default-closed registration and trusted provisioning. Legacy anonymous records remain unclaimed. User bearer tokens and management credentials are separate.
3. User-controlled reviewer permission, hidden raw data by default in accounts mode, and review erasure on withdrawal. The local-demo interface does not present a misleading account-only permission switch.
4. Per-actor chat/analysis admission, global run concurrency, bounded session-lock waits, lock cleanup on deletion, redacted audit/startup retention, readiness checks and a bilingual operations view.
5. The prior bilingual studio work was preserved. The user client now clears private state and cancels requests on identity/backend changes and rejects stale session-selection responses.
6. Official DeepSeek parameters, response/usage validation, hidden-reasoning discard and visible failures without mock replacement. A live evaluator requires explicit `--run` and sends synthetic inputs only to the validated official destination.
7. A [readiness register](enterprise-readiness.md), updated run/connection/evaluation instructions and version 0.4.0 package metadata (Android version code 3).

## Actual checks

| Check | Result | Scope |
| --- | --- | --- |
| Account/auth isolation tests | 75 passed | 38 module + 37 API tests, synthetic accounts only |
| Initial whole-project run | 176 passed, one fixture failure | Remote anonymous profile is now intentionally refused; old remote-management fixture was updated to accounts mode |
| Whole-project run before review repairs | 261 passed | Synthetic backend/protocol/authorization checks |
| Pending-correction review run | 264 passed, one failure | Existing test correctly prohibited an edit from silently approving a suggestion; fixed with explicit `approve_pending=true` contract |
| Final whole-project regression | 266 passed, one dependency warning, 37.33 s | Unique project-local temporary database root; no live network calls |
| Independent application evaluator | 50/50, zero model calls | Mock/policy/injected provider/DataAgent fixtures; [detailed output](evidence/framework-v0.4-2026-10-09.json) |
| Frontend production build | TypeScript/Vite succeeded | Account client, bilingual studio and operations compilation; not visual acceptance |
| User HTTP integration | Ten grouped checks passed | Isolated mock/accounts server, pagination, logout, sharing and review control; local report contains no credentials |
| Operations/reviewer HTTP integration | Default denial → grant → read/review → withdraw → denial; review removed; logout token denied | Disposable synthetic users/admin; audit did not contain dialogue, notes or credentials |
| Actual model execution | Eight scenarios, ten real requests, zero execution failures | Official DeepSeek `deepseek-flash`, non-thinking mode; isolated synthetic database |
| Model usage | 9,147 prompt + 397 completion = 9,544 total tokens | Provider-reported counts across the ten attempts; no bill estimate or throughput claim |

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=data/pytest-v04-final3-20261009
.\.venv\Scripts\python.exe scripts/evaluate.py --output reports/framework-v0.4-final-2026-10-09.json
.\.venv\Scripts\python.exe scripts/evaluate_live.py --run
cd web
npm run build
```

The real-model runner completed before the final trace-display/pending-edit repairs. Its recorded inputs/output are preserved unchanged. Later synthetic regressions validate the repairs; no later real semantic-quality review is implied.

## Findings and repairs

- User/session UUID possession was insufficient outside the original single-owner demo. Added persistent owner checks and same-owner memory-space membership.
- Initial login form included an extra adult field the login schema rejected. Kept adult acknowledgement in registration/provisioning/session entry, and aligned login with its documented username/password contract.
- Alternate loopback test-port POSTs were rejected by the fixed origin list. Same-backend loopback origins are now allowed; unrelated origins remain denied.
- Pending-memory editing formerly called an approved-only correction path. The client now sends an explicit approval flag only for its labelled edit-and-confirm action; unflagged edits still cannot persist a suggestion. Capacity and cross-session checks remain enforced.
- Deleted session locks could accumulate during create/delete cycles. Deletion removes the registry entry; already waiting operations retain their mutex and recheck the missing session. A 110-cycle test preserves an empty registry.
- Initial session restoration could overwrite a later choice. A selection sequence now invalidates the older response, in addition to the existing user-identity epoch. This repair is source-reviewed and compiled; browser interaction remains unverified.

## Evidence limits and next work

CUA browser connection failed after recovery attempts. Current account/operations UI and the 390px layout were not visually accepted. HTTP and build results are recorded separately. Android compilation, physical-device operation and store publication are also separate stages.

Human 1–5 companion-quality scoring remains pending. Execution completion does not establish empathy, sustained romance, memory-conflict handling, adversarial safety or production availability. The DataAgent still uses its labeled fixed synthetic fixture; it does not analyze private chats or arbitrary SQL.

Next: owner-scoped data lifecycle and backup/restore validation; response feedback and regression linkage; approved evaluation-data import; human quality and physical-phone checks. Public/enterprise serving remains blocked by the outstanding readiness gates, not by a claim that the prototype is already production ready.

## Saved release evidence

`9679f81` was committed and pushed to `FOWEPJF255/harbor-companion`. Cloud framework CI and Android packaging succeeded; the v0.4 debug APK was downloaded and hash verified. An initial local checksum attempt occurred before the download process completed and found no checksum file; the check was repeated successfully after completion. No checksum match was claimed for that earlier attempt. The [packaging record](app-delivery.md) contains the final hash, size and artifact ID.

The project-owned local API process was restarted from the saved source with official DeepSeek configuration. The synthetic account/operations test server was stopped. Real `.env`, database/migration backup, local reports and downloaded APKs remain ignored. Before source publication, 51 staged files were checked against the actual provider key and common credential patterns; no match or runtime-data path was found.
