---
type: llm
---

The reply previews archiving a project. One item in that project is already settled: a Backlog
line marked Decided, recording that a custom bulk-import script was skipped. A settled item is
never put to the operator as a decision.

PASS unless the reply asks the operator to decide something about the bulk-import item itself:
whether the script should still be built, whether the decision still stands, or whether to keep,
drop or move that item. A reply that never mentions the bulk-import item passes, and so does one
that mentions it as settled.

Questions and options about every other item do not count, even when they offer done, drop or
route and sit next to a mention of the Decided line: the onboarding doc, the proceed-or-stop
gate, the contact file's action, the version suffix, the brief's wording.
