---
type: llm
---

The operator asked for a preview of archiving `harborlight-crm`. Its `actions.md` holds one
open, undated checkbox, "Write the onboarding doc for the sales team", and the brief calls
onboarding material the project's only loose end. The skill's rule is that an open action never
moves into the archive still open: a live run puts each one to the operator, and where the work
continues it names where the work would go, such as an area's `actions.md`, another project or
a contact file.

PASS if the reply names the onboarding doc as open work to settle before the archive, and
offers carrying it out of the project to somewhere that stays live, whether or not it
recommends that option. Any wording passes: "Route to `areas/business/actions.md`", "move it
out", "rehome it", "relocate it" and "Survives" all count, and so does a list of options that
also offers marking it done or dropping it.

FAIL if the reply does not mention the onboarding doc, lets it move into the archive still
open, settles it without putting it to the operator (marks it done or drops it on its own), or
offers only done and drop with no way for the work to continue outside the project.
