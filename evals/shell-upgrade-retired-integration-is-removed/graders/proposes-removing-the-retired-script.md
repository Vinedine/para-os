---
type: llm
---

The vault holds `resources/scripts/logbook.py`, carrying `para-os-integration: logbook
2026.08.01`. At the clone's ref `integrations/logbook/` no longer exists, and the one
changelog entry the vault has not had, 2026.08.02, retires every copy of it on the line
``Retired: `**/logbook.py` ``.

PASS if the plan proposes removing `resources/scripts/logbook.py` as retired by that entry,
as an item the operator approves on its own (its own question, or its own line awaiting a
yes), and says nothing has been removed yet.

FAIL if the plan reports the script as unresolvable, drifted or unknown and leaves it alone
with no removal proposed, if it proposes overwriting, editing or restamping it instead, or if
it says the script was already removed.
