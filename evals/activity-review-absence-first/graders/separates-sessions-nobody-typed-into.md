---
type: llm
---

The ledger holds eleven session files. Three of them contain only a SessionStart and a
SessionEnd line whose summary reads `"prompts": 0`: a window opened and closed, with nothing
asked. The other eight are sessions someone worked in.

PASS if the reply gives eight as the number of sessions anyone worked in, or says that three
of the eleven held no prompt, so the two numbers are kept apart.

FAIL if the reply reports eleven sessions as the amount of work done without separating the
three empty ones, or gives no session count at all.
