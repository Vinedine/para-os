# Inspecting and filing a loose file (Steps 3 and 4)

How each loose file in `triage/` is read, checked against the vault, and given a destination and a convention-conform name. Threads fetched in this run are routed in [sources.md](sources.md) instead. **A staged mail note is a loose file**, read here like any other, then offered the wider vocabulary in [approval.md](approval.md).

## Inspect (Step 3)

- **Read the file** with `Read`, which renders PDFs and images. **Where it fails on a PDF** (no `pdftoppm`, or fonts that extract as nothing), render the first page with PyMuPDF (`fitz`) or `pypdfium2` and read that; only where no renderer runs, ask the operator before falling back to name-only inference.
- **A staged mail note whose `Content` line says it holds less than the message** (`note.content_incomplete`, with `note.content_evidence` naming the phrase; judge the line yourself where it is `null`) is re-read at its source before it is judged, unless the vault already holds a filed survivor of the same message: check for one first, by content, as below. Read-only, one call per note, by the note's `Message id` (`note.message_id`), never an id derived from `Link`: the mailbox's content tool (`get_thread`, `get_gmail_thread_content`), or for a fetch script `outlook.py` followed by that line as written. Only a note with no `Message id` falls back to the thread in its `Link`. Where the thread's only content is a small text attachment, such as an `.ics`, one attachment read (`get_gmail_attachment_content`) follows. A fact found only there goes into the Update existing annotation or a follow-on edit, never into the note, which stays as staged.
- **A Google-native file** (`.gdoc`, `.gsheet`, `.gslides`, `.gform`, `.gdraw`) is a stub no local read opens, but its content is readable through the Drive API, so never infer from its name: convert it per [sources.md](sources.md#google-native-files).
- **For PDFs and images, capture** the document's own date (signing, invoice, issue; never the file's modification date), the parties, reference numbers, and the document type. A PDF bundling several documents is noted in full, and its name reflects the bundle.

Then check for **duplicates and redundancies**, **content first, never filename first**:

- **`duplicates`** lists every other file in the vault with the same bytes. Non-empty: propose **Delete (duplicate)**, citing the surviving path and the MD5. `hash_skipped` or an empty list only means no byte match exists, not that the file is original.
- **`cross_vault`**, for a note routed to other vaults: a byte-identical file already in one of their `sources/`. Same treatment, that path as the survivor. A vault reported `unreadable` is named, never dropped.
- **Plausibly the same content with no byte match** (a rescan, a "copy 2"): open both and compare key fields, then ask it as its own question, never an automatic delete. Between a scan and its digital original, the scan is the **Delete (redundant scan)** candidate and the digital version its evidence.

Carry the item's `inbound` into its question or row ([approval.md](approval.md)) rather than re-grepping.

**Orientation**: judge an image (`.jpg`, `.jpeg`, `.png`, `.gif`) from the rendered preview, whatever its EXIF tag says: upside down (180) or sideways (90, 270) needs the pixels rotated. A wrong-way scanned PDF is flagged, and rotated only on the operator's say.

## Choose a destination and a new filename (Step 4)

- **First check existing entities**: list `areas/`, `projects/`, `resources/ideas/` and `archive/`, and read a candidate's `brief.md` or `README.md` for matching parties, dates and reference numbers. A file naming a contract number, address or person lands where that entity is documented, even when it pre-dates the entity's active window.
- **A vault without the entity-with-README pattern** (a flat `areas/`, a looser catch-all): ask the user where each file belongs rather than forcing the entity-folder model on it.
- **Where the owning entity's bucket has no `sources/`** under the vault's rules, the record files into the entity folder itself.
- **If no entity matches, ask whether the file has a concrete subject the vault would hold as an entity** - a prospect, a property, a person, a deal its lifecycle homes. If so, on the table path the item is **Leave in triage**, its Why naming the entity to create, and never **Create entity** ([approval.md](approval.md#the-table-path)); asking, offer **Create entity** (Recommended, naming the shape and folder the vault's structure gives it) and **Leave in triage**. Only a record with no identifiable subject goes by the vault's rule for ownerless records (dated conversation records to `archive/meetings/`, say). With neither, **Leave in triage** (Recommended, saying what is missing). Never hand-build the folder ([operating-discipline.md](../../para-shared/operating-discipline.md#entity-creation)).

Apply the vault's naming convention literally, judging each name against the whole of `.claude/rules/filing.md` and any topic rule file governing the document ([operating-discipline.md](../../para-shared/operating-discipline.md#a-vaults-rule-files)), or `CLAUDE.md` where there is no rule file. Drop legacy suffixes (`- FINAL.pdf`, `copy.pdf`, `(1).pdf`). **A machine-staged note's filename is not the document's name**, only a mail subject plus a hash, so its `<Description>` follows the receiving folder's language and established variant; the rule against translating a document's name does not reach it.

## Writing the row

The **Why** (or the option description) names the specific signals used (date, contract number, address, parties), never a generic "matches the entity". The **Destination** is the full relative path with the new filename, as `[<new name>](<relative-path>)`.

Illustrative fragment - the vault's `CLAUDE.md` gives the real convention and entity shape:

```
| # | Source item | Action | Why | Destination |
|---|---|---|---|---|
| 1 | `Invoice Lockwerk copy.pdf` | Delete (duplicate) | Byte-identical duplicate (MD5 10d9edcc...) of the filed copy. | (deleted) |
| 2 | `IMG_2011.JPG` | File it + rotate 180 | Northwind Bank loan statement dated 2011-12-31 (upside down), loan LN-40213. | [.../sources/20111231 Northwind Bank Loan statement LN-40213.jpg](path) |
| 3 | "RE: quote" - supplier, 14 Jul (email) | Update existing | Reply on an open thread; annotate the tracked action rather than duplicate it. | [projects/<x>/actions.md](path) |
```

## Edge cases

- **An encrypted or locked PDF**: propose a destination from the filename and modification date alone, and say so in the evidence: "(content not readable - name-only inference)".
- **A file that looks like another vault's or context's** (client work in a personal vault, personal records in an engagement vault): ask before filing.
