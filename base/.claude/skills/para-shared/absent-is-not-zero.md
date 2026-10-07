# Absent is not zero

An empty, zero, truncated or failed answer reads as good news unless a skill is told otherwise, and the report built on it comes out confident and wrong in the direction that hides the problem. Every skill that reports from what it read holds to these:

- **A constrained or paged call describes its slice, never the whole.** Say what was read (`3 of 12 pages`, `stopped at 5 pages`), and read on where the answer depends on the rest.
- **A summary is not a source where the rows exist.** Total the rows; a stated total is a claim to check.
- **Zero and absent are different facts.** A missing value is unknown, never nought, and an implausible zero reads as unknown too.
- **Empty is not fresh.** A record with no activity date is the worst case, not the best.
- **A date later than today is corrupt.** Report it; never let it make a record look current.
- **An empty result and a failed query look the same.** Cross-check before reporting nothing: the error output, a second query, the ledger.
- **Two counts of the same thing that disagree are a finding**, not a rounding error. Name both and where each came from.

## Reading a document

Read every page. A PDF past 10 pages goes in page batches, the Read tool's `pages` parameter at up to 20 pages a call; where Read cannot open it, extract every page with `pypdf` where it is installed, never installing it unasked. Name each page that returns no usable text as a scan gap rather than skipping it. A value the document does not hold is `not found in N pages read`, naming those pages, never "not on file".
