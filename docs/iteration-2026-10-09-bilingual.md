# Bilingual management follow-up

Date: 2026-10-09 (Asia/Shanghai). Local follow-up to the v0.3 offline milestone; this is not a newly packaged or published mobile release.

## Delivered

- Chinese/English switching across the management login, navigation, overview, character editor, session summaries, reviews, provider status, labels, placeholders and notices.
- The companion app and studio use the same persisted language preference. Document language and title follow the selection.
- Switching language does not remount the studio, revoke its token, clear forms or rewrite character/user-authored content.
- API errors can be translated again when the interface changes. Bootstrap authorization checks use an error's stable original message rather than its translated display value.
- Mock provider status explicitly distinguishes an available mock workflow from complete real-provider configuration.
- The supplied model credential is stored in the project's ignored server `.env`. Its value is not included in this document, the recurring prompt or built web assets. Only presence is checked.

## Actual checks

- `npm run build --prefix web`: TypeScript and Vite production build passed after the final interface changes.
- `.venv/Scripts/python.exe -m pytest -q --basetemp <isolated workspace temporary directory> --tb=short`: **140 passed**, one upstream test-client deprecation warning. The first invocation failed to allocate the default Windows temporary directory; rerunning in a fresh workspace directory resolved the environment issue.
- Browser walkthrough used an isolated mock backend and an independent SQLite database, not the owner's sessions or administrator account. Login, switching both directions, refresh persistence, character draft retention, review labels, provider status, dynamic login-error translation and returning to the companion app were observed.
- Screenshots of the character studio were retained in the requesting chat's outputs directory. Character introductions remained in their original language; these are authored content, not interface strings.
- A scan of built web/native assets found no supplied model credential. The credential remains ignored by Git.

## Remaining work

The key alone does not establish the provider. `HARBOR_API_BASE` and `HARBOR_MODEL` are still empty; no live call was attempted and the runtime remains explicitly mock. Ask the owner for these two non-secret settings once, rather than guessing a destination or model. Once supplied, validate against the named provider's documentation, configure `HARBOR_PROVIDER=openai_compatible`, and run a bounded set of synthetic live scenarios before claiming connectivity or quality.

No new APK has been compiled, no Git commit/push was performed in this follow-up, and no public deployment or HR communication was made. The previously compiled v0.3 APK does not establish delivery of this management follow-up. Rebuild it after integrating this source change; physical-device review and live-model quality evaluation are still separate requirements.
