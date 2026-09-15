# Steps 3 and 4 - Reconcile, apply, report

## Step 3a - Against the documents

Walk the dossier's factual claims against the extracted facts and classify each as exactly one of:

- **Verified** - matches a source.
- **Corrected** - a source contradicts it. Record the claim, the old value, the source value and the file. Follow the **cascade**: a corrected rent changes the rent roll and the yields, a corrected assessed value changes whatever is computed from it.
- **Conflict** - sources disagree, the only evidence is a non-authoritative quote, or a primary document contradicts a listing or email figure and which is current is unclear. Never resolve it by choosing: it becomes an open item, with both values and their provenance.
- **Unobtainable** - the register lists the fact under facts no free source settles, and it is handled as the register says.
- **Misattributed** - the claim is presented under a specific source's heading or citation, but that source's own text does not contain it, and nothing else in `sources/` confirms or contradicts it either. This is not a Conflict (no second source disagrees) and not Unobtainable (the register doesn't say the fact is unreachable) - it is a citation error. Correct it by removing the attribution to the source that doesn't support it; keep the claim itself, flagged as unsourced pending a document that actually states it.

## Step 3b - Against the books

Where the vault names its books, run this as its own pass:

- **Stage.** Does the dossier's stage match the books? Stock on the property's account plus a drawn acquisition credit means it is owned, whatever the dossier says.
- **Cost basis.** Does the dossier's cost match the ledger at the ledger's latest as-of date, rather than an older interim one? A cost basis with no as-of date is itself a defect.
- **Realised margin.** Is a margin called realised stated against a booked sale and a booked cost, or against an estimate?
- **Portfolio file.** Does the dossier agree with the portfolio-level file that quotes the same figure? Two files disagreeing is drift even when neither can be checked against a document.
- **Derived figures.** Where a booked figure has to be derived (cost released against units sold), reconcile it two independent ways, write both down, and say in the dossier that it is derived and what would settle it.

Money follows the same four classes, plus one case: a figure the books cannot carry yet because the deed has not passed is not drift. It sits under prepayments, and the dossier says so.

## Step 4 - Apply and report

1. **Present** the reconciliation table (Corrected | Was | Now | Source), the conflicts, and a one-line verified summary; get the go-ahead.
2. **Apply** each correction with its cascade, citing the filename and the value found inline. Write every conflict into the dossier's open items as what to confirm and with whom.
3. **Report** the counts (corrected, flagged, verified), the conflicts now open, the state the vault is left in, and one verdict: safe to underwrite or build the sheet on these numbers, or which conflicts gate it.
