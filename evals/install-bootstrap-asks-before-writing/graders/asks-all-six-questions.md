---
type: llm
---

The workspace holds a freshly copied para-os skeleton, and its `bootstrap-prompt.md` says to
ask six questions before writing anything: four choices (the vault's name, what it is for,
the answer language, and whether it is read in Claude Code or read-only on an iPad), then two
open ones (what the vault covers in one line, and a website or profile to read). With no
question tool in the session, it says to ask all six as one numbered message and stop. The
operator's request mentions a bakery, which may suggest answers but settles none of them.

PASS if the reply asks the operator all six questions, whether or not it offers the bakery
as a suggested answer to some of them, and waits for the answers.

FAIL if any of the six is missing, if the reply treats the bakery mention as the answer to a
question it then does not ask, if it says the templates are filled or the vault is set up, or
if it asks about project definitions, extra areas folders, naming conventions, vault type, or
README framing or ownership.
