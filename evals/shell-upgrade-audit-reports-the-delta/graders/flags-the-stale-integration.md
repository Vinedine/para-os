---
type: llm
---

The vault's CLAUDE.md marker matches the clone's current revision exactly (both 2026.08.03), but `resources/scripts/logbook.py`'s header claims 2026.08.03 while its actual code is the 2026.08.01 version - it never gained the dedupe-ledger logic the 2026.08.03 changelog entry added.

PASS if the reply states that logbook.py is behind, outdated, or that its content does not match its header or the current revision.

FAIL if the reply never says that logbook.py is behind or that its content does not match its header. A reply that says the vault's marker is current, or that no changelog entry is pending, still PASSES when it also flags logbook.py; it FAILS only when it leaves logbook.py reported as current or unmentioned.
