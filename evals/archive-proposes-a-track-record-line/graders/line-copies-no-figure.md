---
type: llm
---

The project's brief records a figure: average days to payment fell from 41 to 19, with its
own as-of date. The vault's figures rule is that a number is typed into the vault once, so a
Track record line links the brief that holds it rather than copying it, unless the copy carries
its own as-of date and states why it is copied.

Judge only the Track record line the reply proposes for `README.md`, not the rest of the reply.

PASS if that line carries neither the 41 nor the 19, or carries them together with an as-of
date and a stated reason for the copy. A reply that proposes no Track record line at all also
passes this check; another check covers that.

FAIL if the proposed line states the 41, the 19 or the drop between them without both an as-of
date and a reason for copying it.
