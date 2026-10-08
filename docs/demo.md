# Local demo walkthrough

1. Run `scripts/setup.ps1`, then `scripts/start.ps1`. Open http://127.0.0.1:8765.
2. Observe the mock banner. Confirm adult status and choose a mode.
3. Send `今天有点压力` to exercise a grounding tool, then inspect the observable trace.
4. Send `记住：我喜欢海边散步`. A pending memory appears; it is not approved yet.
5. Ask `你还记得我吗？` before approval; the mock recall tool returns no approved memory.
6. Approve the pending memory, ask again, and see the stored fact.
7. Open session insights or ask `看看会话统计`; the tool returns local aggregates.
8. Clear history and confirm approved memory persists. Delete the entire session to erase all application rows for it.

Deleting one memory does not remove text that already appeared in earlier messages. Use full session deletion for that scope of erasure.

Mock mode demonstrates the application's paths. It does not generate a convincing conversational relationship. After API integration, demonstrate the same flow with a real model and annotate the differences.
