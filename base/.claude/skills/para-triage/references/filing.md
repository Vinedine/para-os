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
- Different filename but plausibly the same content (a scan of a digital PDF, a "copy" / "copy 2" variant)? Open both and compare key fields. Don't auto-delete on a hunch - flag and ask in the proposal table.

Detect **orientation issues** for image files (`.jpg` / `.jpeg` / `.png` / `.gif`): when you Read the image, the rendered preview shows the orientation. If text is upside down (180 degrees) or sideways (90 or 270), note the required rotation. PDFs with scanned pages can also be wrong-way; PDF rotation is harder, so flag and ask before attempting.

## Choose a destination and a new filename (Step 4)

Walk the vault to find the best home:

- **First check** existing entities. List `areas/`, `archive/`, and `projects/` subdirectories. Read the candidate's `README.md` to see whether the file's parties, dates, and reference numbers match. A file referencing a specific contract number, address, or person should land where that entity is already documented.
- **If the vault doesn't use the entity-with-README pattern** (a flat `areas/` with loose markdown files, or a catch-all with looser shape): fall back to asking the user where each file belongs. Don't force the entity-folder model onto a vault that uses a different shape.
- **If the file pre-dates the entity's active window** (a document from before a property was bought, a client was signed, a case was opened), it usually still belongs in that entity's `sources/` - apply the vault's prefix convention for such files if `CLAUDE.md` documents one.
- **If no existing entity matches**, propose either (a) a new folder under the right PARA bucket with a sensible kebab-case slug, or (b) leaving the file in `triage/` and asking the user where it belongs. Default to (b) - don't invent new folders without confirmation. When the file is the start of real work rather than a document needing a home, `/para-new` creates the entity properly (sorting test, brief, one action) instead of a stub folder.

Apply the vault's naming convention, read from its `CLAUDE.md` and applied literally. A common shape is `YYYYMMDD <Who> <Description> [<scope>].<ext>`. Use:

- The document's own date (signing, issue, invoice, inspection). Not the file's mod date unless that's the only signal.
- The most identifying party, per the CLAUDE.md guidance - typically tenant for leases, contractor for work, provider for utilities, insurer for policies.
- A short description ending with any reference number on the document.
- The scope suffix only when relevant (per-unit docs in a multi-unit property).

Drop legacy suffixes (`- FINAL.pdf`, `copy.pdf`, `(1).pdf`) on rename.

## Writing the row

The **Why** cell names the specific signals used (date, contract number, address, parties), never a generic "matches Stationsstraat". The **Destination** cell is the full relative path including the new filename, written as `[<new name>](<relative-path>)` so VS Code renders it clickable.

Illustrative fragment - the vault's `CLAUDE.md` gives the real naming convention and entity shape:

```
| # | Source item | Action | Why | Destination |
|---|---|---|---|---|
| 1 | `Factuur Lockwerk.pdf` | Delete | Byte-identical duplicate (MD5 10d9edcc...) of the filed copy. | (deleted) |
| 2 | `Tax Bank 2011.JPG` | Move + rename + rotate 180 | Bank 2011 repayment certificate (upside down), contract 726-1234567-89. | [.../sources/20111231 Bank Betalingsattest 726-1234567-89.jpg](path) |
| 3 | "RE: quote" - supplier, 14 Jul (email) | Update existing | Reply on an open thread; annotate the tracked action rather than duplicate it. | [projects/<x>/actions.md](path) |
```

## Edge cases

- **File is an encrypted or locked PDF**: skip content inspection, propose destination from filename plus file mod date only, and flag in the Why column as "(content not readable - name-only inference)".
- **File modification date is wildly different from the document date** (a 2024 mod date on a 2013 invoice): use the document date. Mention the discrepancy in the Why column.
- **Two triage files describe the same event** (a scanned and a digital version of the same letter): keep the digital, delete the scan. Show both in the table; mark the scan as Delete (redundant scan) with a Why pointing to the digital version's path.
- **File references a person not yet in `areas/network/`**: propose creating the contact file with a one-line bio (parties, date first encountered, source-doc reference), but only execute after approval. Don't auto-create.
- **File references a property or project not yet in the vault**: propose either (a) leaving it in triage with a note about what's needed, or (b) creating the new folder with a stub README. Default to (a).
- **Image with an EXIF orientation tag**: still inspect visually after Reading. EXIF orientation is widely ignored by renderers, so a "correct" EXIF tag with rotated pixels still needs the pixels rotated.
- **PDF where one page is rotated and others aren't**: flag for the user; PDF page rotation is risky to attempt blindly.
- **File looks like it belongs to a different vault or context** (client work in a personal vault, personal records in an engagement vault): ask before filing. One-vault-per-context only works if triage respects the boundary.
