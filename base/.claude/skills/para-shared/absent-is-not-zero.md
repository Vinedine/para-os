# Absent is not zero

An empty, zero, truncated or failed answer reads as good news unless a skill is told otherwise. Every skill that reports from what it read holds to these:

- **A paged or capped call describes its slice**, never the whole: say what was read (`3 of 12 pages`) and read on where the answer depends on the rest.
- **A summary is not a source where the rows exist**: total the rows.
- **Zero, absent and undated are different facts.** A missing value is unknown, an implausible zero reads as unknown, and a record with no activity date is the worst case, not the best. A date later than today is corrupt: report it.
- **An empty result and a failed query look the same.** Cross-check before reporting nothing: the error output, a second query, the ledger.
- **Two counts of one thing that disagree are a finding.** Name both and where each came from.

## Reading a document

Read every page: past 10 pages in batches of up to 20 through the Read tool's `pages` parameter, or with `pypdf` where Read cannot open it and it is installed. A page with no usable text is named as a scan gap. A value the document does not hold is `not found in N pages read`, naming the pages, never "not on file".
