# Steps 5 and 6 - Analyst underwriting and report

## Step 5 - Analyst underwriting

1. **Load the persona as the analytical lens**: `adapters/claude-code.md`, the `*.core.md`, and every file under `knowledge/`. Adopt its priorities, its scenario rule (one realistic base, one conservative downside, unless the persona says otherwise) and its guardrails. Where its baseline facts contradict the dossier, the dossier wins and the report lists each contradiction as persona drift.
2. **Produce the underwriting.** Where the dossier already carries a dated underwriting and this run only added facts, write a dated addendum applying its method to them instead of re-deriving it.
   - **Structure.** Which entity holds or buys it, and why, as the persona's `knowledge/` supports. Never a default.
   - **Economics, acquisition mode.** A flip: the all-in cost basis (price, the transfer tax and fees from the register's cost table, financing, renovation with contingency), an after-repair value from real comparables, the tax treatment of the margin per `knowledge/`, holding costs, and the after-tax margin. A hold: gross and net yield, cash-on-cash, debt service cover, rent against the market, and the persona's portfolio yield bar.
   - **Economics, hold review.** Start from **capital deployed as booked**, with its as-of date. Value the property on current rents and comparables, compare the yield on booked capital against the persona's bar, and set out each exit the persona allows (for example keep, refinance, divide and sell, sell whole) with what it returns against that capital.
   - **The booked cost is the floor, not an input.** For any property already owned, read its ledger account from the books the vault names first, take that figure with its as-of date as spent to date, and underwrite only what lies ahead: remaining works, holding costs, selling costs. When an estimate and the ledger disagree, the ledger wins and the gap is itself a finding.
   - **Keep the three kinds of number apart**: contracted, booked, projected, as `property-dossier.md` requires.
   - **Cost lines.** Each states its tax basis (net or gross of VAT, and the rate); lines on different bases are never summed, and a projection that did is a finding. Every contractor or scope named in the dossier or mail is marked quoted or not, and an unquoted scope becomes a contingency line or an open item. Per-unit figures are written as amounts, not only as a rate per area.
   - **Financing.** Anchor on the owner's actual facilities and capital, from the dossier and the books, not on generic rates. Show how the deal is funded.
   - **Two scenarios**, base and downside, on the axis that dominates the deal: the permit outcome while a permit is undecided, otherwise cost and sale or rent stress. A scenario figure no document prices is a flagged assumption stating its derivation.
   - **Verdict.** Go, pass, or conditional, falling out of the numbers, with a bid zone and walk-away while the price is open, the cost ceiling and sale or rent floor that still clear the persona's bar once it is contracted, or keep / act for a hold review.
   - **A load-bearing number no source gives** (price, renovation cost, rent basis) gates only what depends on it: write the rest, flag or omit the dependent figures, and make the verdict conditional on it, first among the open items.
3. **Write the analysis into the dossier**, and consolidate everything still unknown or assumed into its open items, phrased as what to confirm and with whom. `/property-dealsheet` prints exactly these.

Present the verdict and the key figures, and get the go-ahead.

## Step 6 - Report

Say which state the vault is left in. Report the verdict in one line, the dossier sections changed, the cards touched, the flagged assumptions, and the open items that still gate the verdict. If the dossier is decision-ready, say "ready for /property-dealsheet". A run stopped before Step 5 reports what changed and that no verdict exists yet.
