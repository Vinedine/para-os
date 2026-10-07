---
type: llm
---

The operator ran the para-os bootstrap for a household vault, every answer and approval given
up front. Two items waited in `triage/`: a letting agent's rent review letter (`scan0117.txt`)
and a plumber's mail registering a boiler warranty (`Boiler warranty registered.eml`). The
vault's naming convention for source documents is `YYYYMMDD <Who> <Description>.<ext>`. The
bootstrap's Finish runs `/para-triage` on the operator's real items before the brief.

PASS if the reply says both items were filed out of `triage/` into an entity's folder (a
`sources/` folder, or the entity folder itself), each under a name that starts with an
eight-digit date and names who sent it.

FAIL if the reply says either item was left in `triage/`, filed under its original name, or
not handled, or if it does not account for both.
