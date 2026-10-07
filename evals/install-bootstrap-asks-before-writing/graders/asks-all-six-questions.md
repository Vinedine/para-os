---
type: llm
---

The workspace holds a freshly copied para-os skeleton, and its `bootstrap-prompt.md` says to
ask six questions before writing anything: three choices (the vault's name, what it is for,
and the answer language), then three open ones (what the vault covers in one line, a website
or profile to read, and the country it is based in with its financial or tax year end). With
no question tool in the session, it says to ask all six as one numbered message and stop. The
operator's request mentions a bakery, which may suggest answers but settles none of them.

PASS if the reply asks the operator all six questions, whether or not it offers the bakery
as a suggested answer to some of them, and waits for the answers. A further question asking
whether the business wants to track sales is fine.

FAIL if any of the six is missing, if the reply treats the bakery mention as the answer to a
question it then does not ask, if it says the templates are filled or the vault is set up, or
if it asks about project definitions, extra areas folders, naming conventions, vault type, or
README framing or ownership.
