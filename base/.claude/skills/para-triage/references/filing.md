# Inspecting and filing a loose file (Steps 3 and 4)

How each loose file in `triage/` gets read, checked against what the vault already holds, and turned into a destination plus a convention-conform filename. Connector threads fetched in this run skip this file: they are routed in [sources.md](sources.md). **A staged mail note is a loose file** and is read here like any other, then takes the wider vocabulary [approval.md](approval.md) gives it.

## Inspect (Step 3)

For each loose file, gather enough context to propose a destination:

- **Read the file.** PDFs render visually; images render visually; text and markdown read as content. Use the `Read` tool - it handles all three. **Where `Read` fails on a PDF** (no `pdftoppm` on the machine, or fonts that extract as nothing), render its first page to an image with PyMuPDF (`fitz`) or `pypdfium2` and read that; only where no renderer runs, ask the operator before falling back to name-only inference.
- **A staged mail note whose `Content` line says it holds less than the message** (a snippet, a preview, no readable body) is re-read at its source before it is judged, unless the vault already holds a filed survivor of the same message: check for one first, by content, as below. The scan's `note.content_incomplete` already flags this (`note.content_evidence` names the matched phrase); where it reads `null`, judge the `Content` line yourself. Read-only, one call per note: the mailbox's own content tool by the thread in the note's `Link` (`get_thread`, `get_gmail_thread_content`), or the fetch script's single-message read where it offers one (`outlook.py raw`). Where the thread's only content is a small text attachment, such as an `.ics`, one attachment read (`get_gmail_attachment_content`) follows that call. A fact found only in that body goes into the Update existing annotation or a follow-on edit, never into the note, which stays as it was staged.
- **Google-native files are the one exception, and they are not readable locally at all.** A `.gdoc` / `.gsheet` / `.gslides` / `.gform` / `.gdraw` on a Drive-synced disk is a pointer stub, not a document: the bytes live on a server. Every local read path fails with an I/O error - `Read`, `cat`, `cp`, PowerShell `Get-Content`, `cmd type`, Python `open` - yet the content is available through the Drive API, so never fall back to name-only inference. See [sources.md](sources.md#google-native-files) for the conversion branch.
- For PDFs and images, capture: dated content (signing date, invoice date, issue date), parties involved (counterparties, addressees), reference numbers, and the document type (invoice, contract, certificate, ad, statement, etc.).
- For multi-page PDFs that bundle several documents (e.g. two invoices in one PDF), note all of them - the rename should reflect the bundle, not just the first page.

Then check for **duplicates and redundancies** against the rest of the vault, **content first, never filename first** - a filename match is not evidence and a byte match is:

- The scan's `duplicates` field is every other file in the vault holding the same bytes, found by content hash, the item's own name never consulted. Non-empty: propose **Delete (duplicate)**, citing the surviving path and the MD5. `hash_skipped` (the file sits under the hashing floor) or an empty `duplicates` is not proof of originality - only that no byte match exists.
- **A note routed to other vaults** gets its `cross_vault` field too: a byte-identical file already sitting in one of those vaults' `sources/` folders, checked against the vaults the ingest ledger staged its thread into, and any other vault its `Routed` line mentions - same treatment, the other vault's path as the survivor. An entry naming a vault `unreadable` is reported, never dropped.
- **Different filename but plausibly the same content, with no byte match** (a rescanned PDF, a "copy" / "copy 2" variant a hash cannot catch): open both and compare key fields. Don't auto-delete on a hunch - flag it and put it to the operator as its own question.

The scan's `inbound` for the item - every live line naming it - is what [approval.md](approval.md)'s "A delete or a move names what links to the file" cites; carry it into the same row rather than re-greping for it.

Detect **orientation issues** for image files (`.jpg` / `.jpeg` / `.png` / `.gif`): when you Read the image, the rendered preview shows the orientation. If text is upside down (180 degrees) or sideways (90 or 270), note the required rotation. PDFs with scanned pages can also be wrong-way: flag and ask before rotating one.

## Choose a destination and a new filename (Step 4)

Walk the vault to find the best home:

- **First check** existing entities. List `areas/`, `projects/`, `resources/ideas/` and `archive/` subdirectories. Read the candidate's `brief.md` or `README.md` to see whether the file's parties, dates, and reference numbers match. A file referencing a specific contract number, address, or person should land where that entity is already documented.
- **If the vault doesn't use the entity-with-README pattern** (a flat `areas/` with loose markdown files, or a catch-all with looser shape): fall back to asking the user where each file belongs. Don't force the entity-folder model onto a vault that uses a different shape.
- **If the file pre-dates the entity's active window** (a document from before a property was bought, a client was signed, a case was opened), it usually still belongs in that entity's `sources/`.
- **Where the owning entity's bucket has no `sources/`** under the vault's own rules (some vaults give areas none), the record files into the entity folder itself.
- **If no existing entity matches, first ask whether the file has a concrete subject the vault would hold as an entity** - a prospect, a property, a person, a deal its lifecycle homes. If it does, offer **Create entity** (Recommended, naming the shape and folder the vault's structure gives it) and **Leave in triage**. Only a record with no identifiable subject goes by the vault's rule for records with no owner (dated conversation records to `archive/meetings/`, say). With neither, offer **Leave in triage** (Recommended, with what is missing). Never hand-build the folder ([operating-discipline.md](../../para-shared/operating-discipline.md#entity-creation)).

Apply the vault's naming convention literally, judging each name against the whole of `.claude/rules/filing.md` and any topic rule file that governs the document ([operating-discipline.md](../../para-shared/operating-discipline.md#a-vaults-rule-files)), or against `CLAUDE.md` where the vault has no rule file. Drop legacy suffixes (`- FINAL.pdf`, `copy.pdf`, `(1).pdf`) on rename. **A machine-staged note's filename is not the document's name**: it is a mail subject plus a hash, so the `<Description>` follows the receiving folder's language and established variant, and the rule against translating a document's name does not reach it.

## Writing the row

The **Why** cell names the specific signals used (date, contract number, address, parties), never a generic "matches the entity". The **Destination** cell is the full relative path including the new filename, written as `[<new name>](<relative-path>)` so it renders as a link.

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
- **File looks like it belongs to a different vault or context** (client work in a personal vault, personal records in an engagement vault): ask before filing.
