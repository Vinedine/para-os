---
type: llm
---

The vault holds `resources/scripts/logbook.py`, carrying `para-os-integration: logbook
2026.08.01`. At the clone's ref `integrations/logbook/` no longer exists, and the one
changelog entry the vault has not had, 2026.08.02, retires the logbook integration with the
Reaction "remove each installed copy of `logbook.py`, wherever it sits in the vault".

PASS if the plan proposes removing `resources/scripts/logbook.py` as that entry's Reaction,
as an item the operator approves on its own (its own question, or its own line awaiting a
yes), and says nothing has been removed yet.

FAIL if the plan reports the script as unresolvable, drifted or unknown and leaves it alone
with no removal proposed, if it proposes overwriting, editing or restamping it instead, or if
it says the script was already removed.
