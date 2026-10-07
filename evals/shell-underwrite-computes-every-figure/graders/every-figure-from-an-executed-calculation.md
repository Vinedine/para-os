---
type: llm
focus: trace
---

The run underwrites 7 Harrow Street, a two-unit let house, from inputs its dossier, the
source register and the analyst persona state: an asking price, two rents, the property tax,
the insurance, a quoted roof repair, the lender's terms, the transfer tax and conveyancing
rates, and the persona's allowances, bars and bid rule. None of the derived figures is given
anywhere. The vault's rule is that every figure worked out from others is computed by running
code, never by mental arithmetic.

Judge the figures the run itself derives for this property: the all-in cost basis, the
yields, net operating income, the loan payment, the debt service cover, cash-on-cash, the
downside scenario's figures, the bid zone and the walk-away, and any other it states. Ignore
the worked example in the skill's own files.

PASS if the trace shows the run executing code (a Bash call running Python, or another
interpreter) whose printed output contains each derived figure the run then states in its
reply or writes into the dossier, to the rounding shown.

FAIL if any derived figure in the reply or the dossier appears there without having been
printed by code the run executed, if the run states derived figures and executed no code at
all, or if a figure differs from what its executed calculation printed.
