---
paths:
  - "areas/**/README.md"
  - "**/brief.md"
---

# Figures

Where a number lives, how a document that needs it gets it, and how an amount is written and read. A convention, not a document shape: it governs every figure in a brief or an entity README, whatever that document's structure.

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

## Amounts

The vault's `CLAUDE.md` declares a currency, a number convention, a date order and a financial year on its `**Locale:**` line. An amount is written and read by them.

- **An amount carries its currency**: the declared currency's ISO 4217 code, or the symbol the line gives as this vault's own; an amount in any other currency carries its own code (`USD 1250`).
- **A new amount is written in the declared number convention.** One already written in another stays as written: read, never rewritten.
- **An amount whose separators are ambiguous on their own** (`1.666`, `1,666`) is read by the declared convention, or in a source document by the convention its other amounts show, and is confirmed against its source before use where a wrong reading would change a decision. A date whose order is ambiguous (`03/04`) is read the same way, by the declared date order.
- **A quarter or a year is the declared financial year's**: `Q1` of a year ending 30 June runs July to September. With no year end declared, it is the calendar's.
