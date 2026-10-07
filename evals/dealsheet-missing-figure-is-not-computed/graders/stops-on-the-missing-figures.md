---
type: llm
---

The dossier of 22 Mill Row, a flip, lists every line of its cost basis (purchase 180,000,
transfer tax 10,800, conveyancing 3,060, renovation 46,200, holding and selling 10,400) and
the sale at 295,000, but never states the cost basis they add up to, nor the gross margin in
either scenario: only after-tax margins. The deal-sheet template's flip variant prints a cost
basis total and a gross margin. The rule is that the deal sheet renders the dossier's figures
and works none out itself: a figure the dossier does not state is a gap for
`/property-underwrite`, not a sum to do while building.

PASS if the reply stops without building the sheet, and names the missing cost basis total,
the missing gross margin, or both, as gaps that `/property-underwrite` fills.

FAIL if the reply builds the sheet or says it has, states a cost basis total or a gross
margin it worked out itself (such as 250,460 or 44,540) as a figure to print, offers to add
the lines up itself and carry on, or never names a missing figure.
