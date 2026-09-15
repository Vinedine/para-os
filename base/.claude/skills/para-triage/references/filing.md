# Inspecting and filing a loose file (Steps 3 and 4)

How each loose file in `triage/` gets read, checked against what the vault already holds, and turned into a destination plus a convention-conform filename. Connector items skip this file entirely: they are routed in [sources.md](sources.md).

## Inspect (Step 3)

For each loose file, gather enough context to propose a destination:

- **Read the file.** PDFs render visually; images render visually; text and markdown read as content. Use the `Read` tool - it handles all three.
- **Google-native files are the one exception, and they are not readable locally at all.** A `.gdoc` / `.gsheet` / `.gslides` / `.gform` / `.gdraw` on a Drive-synced disk is a pointer stub, not a document: the bytes live on a server. Every local read path fails with an I/O error - `Read`, `cat`, `cp`, PowerShell `Get-Content`, `cmd type`, Python `open` - so do not fall back to inferring from the filename the way the locked-PDF edge case does. The content is fully available through the Drive API; name-only inference would throw away a document you can actually read. See [sources.md](sources.md#google-native-files) for the conversion branch. This applies only where Drive is the sync layer; a vault on any other substrate never sees one.
- For PDFs and images, capture: dated content (signing date, invoice date, issue date), parties involved (counterparties, addressees), reference numbers, and the document type (invoice, contract, certificate, ad, statement, etc.).
- For multi-page PDFs that bundle several documents (e.g. two invoices in one PDF), note all of them - the rename should reflect the bundle, not just the first page.

Then check for **duplicates and redundancies** against the rest of the vault:

- Same filename elsewhere in the vault? Compare with `md5sum` on both paths.
- Different filename but plausibly the same content (a scan of a digital PDF, a "copy" / "copy 2" variant)? Open both and compare key fields. Don't auto-delete on a hunch - flag it and put it to the operator as its own question.

Detect **orientation issues** for image files (`.jpg` / `.jpeg` / `.png` / `.gif`): when you Read the image, the rendered preview shows the orientation. If text is upside down (180 degrees) or sideways (90 or 270), note the required rotation. PDFs with scanned pages can also be wrong-way; PDF rotation is harder, so flag and ask before attempting.

## Choose a destination and a new filename (Step 4)

Walk the vault to find the best home:

- **First check** existing entities. List `areas/`, `projects/`, `resources/ideas/` and `archive/` subdirectories. Read the candidate's `brief.md` or `README.md` to see whether the file's parties, dates, and reference numbers match. A file referencing a specific contract number, address, or person should land where that entity is already documented.
- **If the vault doesn't use the entity-with-README pattern** (a flat `areas/` with loose markdown files, or a catch-all with looser shape): fall back to asking the user where each file belongs. Don't force the entity-folder model onto a vault that uses a different shape.
- **If the file pre-dates the entity's active window** (a document from before a property was bought, a client was signed, a case was opened), it usually still belongs in that entity's `sources/`.
- **If no existing entity matches**, the vault's rule for records with no owner decides where it has one (dated conversation records to `archive/meetings/`, say). Otherwise offer **Leave in triage** (Recommended, with what is missing) and **Create entity**, for a project, area or person the vault does not hold yet. Never hand-build the folder ([operating-discipline.md](../../para-shared/operating-discipline.md#entity-creation)).

Apply the vault's naming convention literally, judging each name against the whole of `.claude/rules/filing.md` and any topic rule file that governs the document ([operating-discipline.md](../../para-shared/operating-discipline.md#a-vaults-rule-files)), or against `CLAUDE.md` where the vault has no rule file. Drop legacy suffixes (`- FINAL.pdf`, `copy.pdf`, `(1).pdf`) on rename.

## Writing the row

The **Why** cell names the specific signals used (date, contract number, address, parties), never a generic "matches the entity". The **Destination** cell is the full relative path including the new filename, written as `[<new name>](<relative-path>)` so VS Code renders it clickable.

Illustrative fragment - the vault's `CLAUDE.md` gives the real naming convention and entity shape:

```
| # | Source item | Action | Why | Destination |
|---|---|---|---|---|
| 1 | `Invoice Lockwerk copy.pdf` | Delete (duplicate) | Byte-identical duplicate (MD5 10d9edcc...) of the filed copy. | (deleted) |
| 2 | `IMG_2011.JPG` | File it + rotate 180 | Northwind Bank loan statement dated 2011-12-31 (upside down), loan LN-40213. | [.../sources/20111231 Northwind Bank Loan statement LN-40213.jpg](path) |
| 3 | "RE: quote" - supplier, 14 Jul (email) | Update existing | Reply on an open thread; annotate the tracked action rather than duplicate it. | [projects/<x>/actions.md](path) |
```

## Edge cases

- **File is an encrypted or locked PDF**: skip content inspection, propose destination from filename plus file mod date only, and say so where the evidence goes - the option description, or the Why cell on the table path: "(content not readable - name-only inference)".
- **File modification date is wildly different from the document date** (a 2024 mod date on a 2013 invoice): use the document date, and name the discrepancy in the same place.
- **Two triage files describe the same event** (a scanned and a digital version of the same letter): keep the digital, delete the scan. Name both in the disposition; mark the scan as Delete (redundant scan), with the digital version's path as the evidence.
- **File references a person not yet in `areas/network/`**: offer **Create entity** for the contact file, with a one-line bio (parties, date first encountered, source-doc reference) to seed it.
- **Image with an EXIF orientation tag**: still inspect visually after Reading. EXIF orientation is widely ignored by renderers, so a "correct" EXIF tag with rotated pixels still needs the pixels rotated.
- **PDF where one page is rotated and others aren't**: flag for the user; PDF page rotation is risky to attempt blindly.
- **File looks like it belongs to a different vault or context** (client work in a personal vault, personal records in an engagement vault): ask before filing. One-vault-per-context only works if triage respects the boundary.
