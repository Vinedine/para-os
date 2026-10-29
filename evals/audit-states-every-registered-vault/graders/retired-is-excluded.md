---
type: llm
---

The registry marks the vault `west` as `retired: true`, and its folder is still on disk. A retired vault is left out of the audit on purpose.

PASS if the reply says west was not audited because it is retired, in any wording.

FAIL if west is audited like the others, is reported as unreachable or broken, or is not mentioned at all.
