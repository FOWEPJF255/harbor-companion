# Local demo walkthrough

1. Run `scripts/setup.ps1`, then `scripts/start.ps1`. Open http://127.0.0.1:8765.
2. Observe the mock banner. Confirm adult status and choose a mode.
3. Send `今天有点压力` to exercise a grounding tool, then inspect the observable trace.
4. Send `记住：我喜欢海边散步`. A pending memory appears; it is not approved yet.
5. Ask `你还记得我吗？` before approval; the mock recall tool returns no approved memory.
6. Approve the pending memory, ask again, and see the stored fact.
7. Create a new conversation with the explicit “share approved memory” checkbox. Ask again and inspect the recalled fact. A default isolated conversation does not see it.
8. Correct the approved memory using the Memory form; ask again, then delete the fact and verify recall no longer returns it. Corrections/deletions affect the shared space.
9. Open DataAgent in personal settings, ask `合成数据的情绪分布是什么？`, and expand the plan, results, source fingerprint, and execution trace. These are synthetic fixture counts, not actual product outcomes.
10. Switch the user interface to English, create an English conversation, and use `remember: I prefer quiet walks` / `what do you remember?`. User and management interface labels share the preference; authored character descriptions, historical chat and review text retain their original language.
11. Clear history and confirm approved memory persists. Delete sessions: dialogue is removed immediately, shared approved facts survive only in retained shared conversations; deleting the last one removes the memory space.
12. Run `scripts/evaluate.py` to view injected tool/provider failure, timeout, invalid-argument, and isolation scenarios. Failed runs return error traces and do not save half-turns. They are reproducible checks, not a UI switch for producing errors in a live service.

Deleting one memory does not remove text that already appeared in earlier messages. Use full session deletion for that scope of erasure.

Mock mode demonstrates the application's paths. It does not generate a convincing conversational relationship. After API integration, demonstrate the same flow with a real model and annotate the differences.

## v0.5 account-data demonstration

Use a newly provisioned authored-synthetic account on an isolated accounts-mode database. Do not erase the owner's account for a demonstration.

1. Create two linked conversations with a confirmed synthetic memory. Add dialogue and optionally grant/revoke reviewer permission.
2. Open My space → Export or delete my account. Re-enter the account password and download JSON. Confirm that both sessions and approved facts are present, with no credentials or system prompts.
3. Submit a wrong current password and observe an error while the current login remains available. Switch language and confirm the error is translated.
4. Read the deletion consequences, enter the correct password and exact `DELETE`, then explicitly confirm. Verify sign-out and failure of the old login token.
5. Log in as a different synthetic owner and confirm that owner's sessions remain. Use the synthetic race tests to demonstrate late-run protection; do not pretend it was a human visual walkthrough.
6. Run `scripts/backup-drill.ps1`. Show integrity, approved-memory preservation and restored-token invalidation in the safe metadata report. Explain that retained backups can contain deleted records and need separate retention/reconciliation.

These steps are a review script. Actual execution evidence is recorded separately in [evidence](evidence.md); an APK build is not a physical-phone walkthrough.

## v0.6 character demonstration

1. On the character list, open each profile before starting: inspect growth, work, skills, interests, flaws and boundaries. Switch language and verify the authored translations and fixed proper names.
2. Confirm adult status, start a **new** session, and use the current-character profile entry. Ask a profile question through the panel; an existing chat draft should remain intact. Older sessions intentionally keep their old snapshot.
3. Use the same ordinary daily event with three characters. Review actual replies rather than promising a score. Read the [recorded sample and limitations](persona-evaluation-v0.6.md).
4. In a disposable synthetic session, use the long-context fixture to inspect source IDs and omission counts. Explain that extraction is lossy and does not approve or share user facts.
5. In administration, edit one synthetic profile, inspect version history, restore a previous version explicitly, and confirm it creates a new revision while an old session is unchanged.
6. Grant review access from a synthetic user's session where accounts mode is active. Record six human scores with the exact supporting excerpt for each; leave unreviewed fields unfilled. Legacy scores stay in their own section.
7. Demonstrate the injected partial-output test offline; do not spend a real request merely to force truncation. Explain the visible incomplete notice and absence of automatic continuation or committed proposals.

These are review steps, not a claim that current mobile/browser UI was visually accepted. The v0.6 live-call ceiling has been reached; future live dialogue is not part of the recorded evaluation budget.
