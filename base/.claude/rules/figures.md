---
paths:
  - "areas/**/README.md"
  - "**/brief.md"
---

# Figures

Where a number lives and how an amount is written, in every brief and entity README.

## One number, one home

**A figure is typed into this vault once.** Everywhere else, in this order:

1. **Generate it** where a registry the vault keeps (a YAML or CSV a script reads) models the data: the script writes it between markers it owns.
2. **Link to it** where no registry models it.
3. **Copy it** only where the document cannot work as a link (a decision brief argued on its figures), with its as-of date, source and reason beside it.

**Never generate what the registry does not model**; link or copy instead. **A table holding history the registry cannot** stays hand-kept, excluded from generation, with a check comparing its totals to the registry; the vault's copy of this file names each such table and its check.

## Freshness stamps

**A hand-maintained figure carries its as-of date next to it**: an `As of` column or `_(as of YYYY-MM-DD)_` after the number, or a date field per row in a registry. An undated hand-maintained figure is a defect: date it, or propose removing it.

## Amounts

Written and read by the `**Locale:**` line in the vault's `CLAUDE.md`:

- **An amount carries its currency**: the declared ISO 4217 code or the vault's own symbol, and any other currency its own code (`USD 1250`).
- **A new amount follows the declared number convention**; one already written another way is read, never rewritten.
- **An ambiguous amount (`1.666`) or date (`03/04`)** is read by the declared convention, or by the one a source document's other figures show, and checked against its source where a misreading would change a decision.
- **A quarter or a year is the declared financial year's** (`Q1` of a year ending 30 June runs July to September); with none declared, the calendar's.
