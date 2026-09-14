# Steps 5 and 6 - Analyst underwriting and report

## Step 5 - Analyst underwriting

1. **Load the persona as the analytical lens**: `adapters/claude-code.md`, the `*.core.md`, and every file under `knowledge/`. Adopt its priorities, its scenario rule (one realistic base, one conservative downside, unless the persona says otherwise) and its guardrails.
2. **Produce the underwriting:**
   - **Structure.** Which entity holds or buys it, and why, as the persona's `knowledge/` supports. Never a default.
   - **Economics, acquisition mode.** A flip: the all-in cost basis (price, the transfer tax and fees from the register's cost table, financing, renovation with contingency), an after-repair value from real comparables, the tax treatment of the margin per `knowledge/`, holding costs, and the after-tax margin. A hold: gross and net yield, cash-on-cash, debt service cover, rent against the market, and the persona's portfolio yield bar.
   - **Economics, hold review.** Start from **capital deployed as booked**, with its as-of date. Value the property on current rents and comparables, compare the yield on booked capital against the persona's bar, and set out each exit the persona allows (for example keep, refinance, divide and sell, sell whole) with what it returns against that capital.
   - **The booked cost is the floor, not an input.** For any property already owned, read its ledger account from the books the vault names first, take that figure with its as-of date as spent to date, and underwrite only what lies ahead: remaining works, holding costs, selling costs. When an estimate and the ledger disagree, the ledger wins and the gap is itself a finding.
   - **Keep the three kinds of number apart**: contracted, booked, projected, as `property-dossier.md` requires.
   - **Financing.** Anchor on the owner's actual facilities and capital, from the dossier and the books, not on generic rates. Show how the deal is funded.
   - **Two scenarios**, base and downside, with the sensitivity that actually threatens the deal.
   - **Verdict.** Go, pass, or conditional, with a bid zone and a walk-away level while Prospecting or Acquiring, or a keep / act recommendation for a hold review, falling out of the numbers.
3. **Write the analysis into the dossier**, and consolidate everything still unknown or assumed into its open items, phrased as what to confirm and with whom. `/property-dealsheet` prints exactly these.

Present the verdict and the key figures, and get the go-ahead.

## Step 6 - Report

Say which state the vault is left in. Report the verdict in one line, the dossier sections changed, the cards touched, the flagged assumptions, and the open items that still gate a bid. If the dossier is decision-ready, say "ready for /property-dealsheet".
