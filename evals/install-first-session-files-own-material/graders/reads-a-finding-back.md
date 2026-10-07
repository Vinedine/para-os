---
type: llm
---

The operator ran the para-os bootstrap for a household vault, every answer and approval given
up front. Two items waited in `triage/`: a letting agent's rent review letter (the monthly
rent rising from 1,150.00 to 1,210.00, a signed form due back by a reply-by date) and a
plumber's mail registering a boiler warranty that holds only if the first annual service is
done by a given date. The prompt also pasted a five-line to-do list, one line about renewing a
passport before it runs out at the end of next month. The bootstrap's Finish ends the session
on the daily brief, reading one finding back to the operator and asking whether it matches.

PASS if the reply restates at least one specific fact drawn from those items or that list (a
date, an amount, a name or a deadline) and asks the operator whether it is right or matches
what they have.

FAIL if the reply restates no such fact, restates one without asking the operator to confirm
it, or says that neither item was filed.
