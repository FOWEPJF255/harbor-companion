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
10. Switch the user interface to English, create an English conversation, and use `remember: I prefer quiet walks` / `what do you remember?`. Character descriptions and administration retain their original Chinese text.
11. Clear history and confirm approved memory persists. Delete sessions: dialogue is removed immediately, shared approved facts survive only in retained shared conversations; deleting the last one removes the memory space.
12. Run `scripts/evaluate.py` to view injected tool/provider failure, timeout, invalid-argument, and isolation scenarios. Failed runs return error traces and do not save half-turns. They are reproducible checks, not a UI switch for producing errors in a live service.

Deleting one memory does not remove text that already appeared in earlier messages. Use full session deletion for that scope of erasure.

Mock mode demonstrates the application's paths. It does not generate a convincing conversational relationship. After API integration, demonstrate the same flow with a real model and annotate the differences.
