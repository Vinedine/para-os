# Step 2 - Extract, in parallel

Read the dossier first, so you know which claims exist.

1. **Group the source files by type**, by whatever clusters the folder actually has: certificates, leases, permits and legal, registry extracts, insurance, invoices.
2. **Spawn one `Agent` per group**, all in one message. Each reads its files and returns a compact fact list quoting the document: every number, date, reference, name (exact spelling), party, amount, label, area and parcel identifier. Tell each agent: facts only, no interpretation; write `not present` or `not visible in scan` for a missing field; name the pages of a partial scan. **A long scanned PDF (tens of pages) may need multi-call pagination** - the Read tool's embedded-text extraction can return a whole document in one call when a text layer exists, but a scan-only PDF of real length should be read in page batches (the `pages` parameter), with any page that returns no usable text named as a scan gap rather than silently skipped.
3. **Add one agent for the books** where the vault's `CLAUDE.md` names them. Point it at the most recent annual and interim accounts and any per-property ledger history, and have it return, for this property only: the asset or stock account balance and its as-of date, purchases and sales booked per period, any prepayment held before the deed, the credit drawn on the property, and a per-property bank account and its balance. Account numbers and labels verbatim, and a flag on any account **renamed between periods**.

The fact set the agents return is the only evidence in Step 3.
