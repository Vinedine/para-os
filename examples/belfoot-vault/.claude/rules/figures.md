---
paths:
  - "areas/**/README.md"
  - "**/brief.md"
  - "resources/mds/areas__*__README.md"
  - "resources/mds/*__brief.md"
---

# Figures

Where a number lives, and how a document that needs it gets it. A convention, not a document shape: it governs every figure in a brief or an entity README, whatever that document's structure. The `resources/mds/` globs cover a read-only-iPad vault in collected state; anywhere else they match nothing.

## One number, one home

**A figure is typed into this vault once.** Everywhere else generates it, links to it, or does without it.

When a second copy would be convenient, resolve it in this order:

1. **Generate it.** If a registry the vault keeps (a YAML or CSV a script reads) already models the data, let that script write the figure into the document, between markers it owns.
2. **Link to it.** If no registry models it, link to the one place that holds it. A sentence saying where the number lives beats a copy of the number.
3. **Copy it, and say why in the same breath.** Only when the document cannot work as a link: a decision brief whose argument is built line by line on the figures. The copy carries its own as-of date, names what regenerates it, and states its reason beside it.

**Never generate what the registry does not model.** A generated block that invents a field the registry lacks (an entry price, a historical year-end, a contract number) is worse than the copy it replaced. Link or copy instead.

**A table carrying history the registry cannot hold stays hand-kept, guarded by a reconcile.** Exclude it from generation and let a check compare its totals against the registry, run after touching either side, so it cannot drift silently. The vault's own copy of this file names each such table and its check, so nobody "fixes" one back into a generated block.

## Freshness stamps

**A hand-maintained figure carries its own as-of date inline, next to the figure**, never in a header at the top of the file and never in a commit message.

- In a README or a brief: an `As of` column, or `_(as of YYYY-MM-DD)_` straight after the number.
- In a registry: a date field per row, whose age the script reading it reports.

A hand-maintained figure with no date is a defect: date it, or propose removing it.
