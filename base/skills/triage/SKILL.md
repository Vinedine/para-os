---
name: triage
description: Empty the current vault's triage/ folder by classifying each loose file, proposing a destination + rename per the vault's naming convention, then moving/deleting after user confirmation. Use when user asks to "process triage", "clean up triage", "empty the inbox", or types /triage.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write
arg-hint: '[preview|apply]'
---

# Triage

Processes every loose file in the current vault's `triage/` folder by:

1. Identifying what each file is (read content, infer date/source/scope)
2. Choosing a destination folder by matching content to existing vault entities
3. Applying the vault's source-file naming convention (read from CLAUDE.md)
4. Detecting byte-identical duplicates and obvious redundancies
5. Detecting orientation issues for scanned images
6. **Showing a full proposal table BEFORE doing anything**, then waiting for explicit user approval
7. On approval: moving + renaming, rotating images, deleting duplicates
8. Updating the relevant README(s) so new files are documented in context
9. Re-rendering PDF siblings if the vault is in spread state

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime to discover the naming convention, the PARA layout, and any iPad-rendering toolchain (`flip.ps1` / `render.ps1`). No vault-specific paths are hardcoded.

## When to invoke

- User types `/triage` (optionally with `preview` to skip the execution step)
- User asks "process the triage folder" / "clean up triage" / "empty the inbox" / "file everything in triage"
- User asks to file or sort specific loose files that happen to live in `triage/`

Do NOT invoke for files outside `triage/`. Files already filed are stable; don't re-sort them.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow: scan → show proposal table → wait for approval → execute. |
| `preview` | Stop after the table. Do not prompt for approval, do not execute. |
| `apply` | Skip the confirmation step. Use only when the user has already approved a previous preview in this conversation. |

## Procedure

### Step 1: Confirm vault context

Verify the current working directory is a vault root by checking for `triage/` and at least one of `projects/` `areas/` `archive/`. If `triage/` is missing or empty, respond `Nothing to triage in <cwd>.` and stop.

Read the vault's `CLAUDE.md` (project-level, in the vault root). Extract:

- The **filing rules** section - gives the per-folder naming convention for source documents. Most vaults have a structured `YYYYMMDD <Who> <Description>` style with vault-specific scope suffixes. Quote the convention back verbatim later when you build the table, so the user can sanity-check it.
- Any **language** rules (which languages are kept verbatim, which folders are English-only).
- Any **do-not-add** rules (e.g. "don't create per-contact templates", "don't add actions.md files").
- Whether the vault uses the **flip/render** workflow (look for `flip.ps1`, `render.ps1`, `render.mjs` in the vault root).

**If `CLAUDE.md` exists but has no source-document naming convention** (e.g. action/markdown-focused vaults that don't deal with PDFs at scale): stop and ask the user to dictate the convention before any renames execute. Do not invent one. Do not silently borrow a convention from another vault. Same applies if the filing-rules section exists but is silent on source-document naming.

### Step 2: List loose files in triage/

Use Glob `triage/*` to get top-level entries. Also note any subdirectories with Glob `triage/*/` - list them but **do not recurse into them** for the proposal. Subdirectories in `triage/` are intentional sub-batches (e.g. `triage/_some-handoff/`) and should be flagged for the user as "subdirectory - needs separate review" rather than blindly flattened.

If `triage/` contains only subdirectories and no loose files, list the subdirectories and stop with `Only subdirectories in triage/; nothing to file at top level. Subdirectories listed for your review.`.

### Step 3: Inspect each loose file

For each loose file, gather enough context to propose a destination:

- **Read the file.** PDFs render visually; images render visually; text/markdown reads as content. Use the `Read` tool - it handles all three.
- For PDFs and images, capture: dated content (signing date, invoice date, issue date), parties involved (counterparties, addressees), reference numbers, and the document type (invoice, contract, certificate, ad, statement, etc.).
- For multi-page PDFs that bundle several documents (e.g. two invoices in one PDF), note all of them - the rename should reflect the bundle, not just the first page.

Then check for **duplicates and redundancies** against the rest of the vault:

- Same filename elsewhere in the vault? Compare with `md5sum` on both paths.
- Different filename but plausibly the same content (e.g. scan of a digital PDF, or a "copy" / "copy 2" variant)? Open both and compare key fields. Don't auto-delete on a hunch - flag and ask in the proposal table.

Detect **orientation issues** for image files (`.jpg`/`.jpeg`/`.png`/`.gif`):

- When you Read the image, the rendered preview shows the orientation. If text is upside down (180°) or sideways (90° or 270°), note the required rotation. PDFs with scanned pages can also be wrong-way; PDF rotation is harder, so flag and ask before attempting.

### Step 4: Choose destination + new filename

For each file, walk the vault to find the best home:

- **First check** existing entities. List `areas/`, `archive/`, and `projects/` subdirectories. Read the candidate's `README.md` to see whether the file's parties, dates, and reference numbers match. A file referencing a specific contract number, address, or person should land where that entity is already documented.
- **If the vault doesn't use the entity-with-README pattern** (e.g. flat `areas/` with loose markdown files, or a Personal-style catch-all with looser shape): fall back to asking the user where each file belongs. Don't try to force the entity-folder model onto a vault that uses a different shape.
- **If the file pre-dates the entity's active window** (a document from before a property was bought, a client was signed, a case was opened), it usually still belongs in that entity's `sources/` - apply the vault's prefix convention for such files if `CLAUDE.md` documents one.
- **If no existing entity matches**, propose either (a) a new folder under the right PARA bucket with a sensible kebab-case slug, or (b) leaving the file in `triage/` and asking the user where it belongs. Default to (b) - don't invent new folders without confirmation.

Apply the vault's naming convention. For example: `YYYYMMDD <Who> <Description> [<scope>].<ext>`. Read the convention from the project CLAUDE.md and apply it literally. Use:

- The document's own date (signing, issue, invoice, inspection). Not the file's mod date unless that's the only signal.
- The most identifying party (per the CLAUDE.md guidance - typically tenant for leases, contractor for work, provider for utilities, insurer for policies).
- A short description ending with any reference number on the document.
- The scope suffix only when relevant (per-unit docs in a multi-unit property).

Drop legacy suffixes (`- FINAL.pdf`, `copy.pdf`, `(1).pdf`, etc.) on rename.

### Step 5: Build the proposal table

Render a markdown table with these columns:

| # | Source file | Action | Why | Destination |
|---|---|---|---|---|

Action values:
- **Move + rename** - most common
- **Move + rename + rotate Nx°** - image needs rotation first
- **Delete** - byte-identical duplicate (cite the existing path + the MD5 hash match)
- **Delete (redundant scan)** - flag for confirmation; this is not a hash match, just a content overlap
- **Subdirectory - needs separate review** - for `triage/<subdir>/`
- **Leave in triage** - when no good destination exists; explain what's missing

For **Why** cells, name the specific signals you used (date, contract number, address, parties). Don't write generic "matches Stationsstraat" - write "Contract 123.456.789 dated 12/10/2015, addressee A. Janssens @ Stationsstraat 12, AXA polis matches the AXA row in [Insurance table](path)".

For **Destination** cells, write the full relative path including the new filename. Use the link `[<new name>](<relative-path>)` so VS Code renders it clickable.

After the table, list any **follow-on edits** to README files (new rows in tables, new entries in source-document lists, new sub-sections). Be explicit about which README and where in it.

### Step 6: Wait for approval

If arg is `preview`: stop here. Don't prompt.

Otherwise: ask the user something like "Reply **go** to execute, or tell me what to change." Wait for an explicit approval. **Do not proceed on silence, on "ok", or on tangential replies.** "Go", "yes execute", "do it", "apply" - these are clear. Anything else: clarify.

The user may amend (e.g. "skip #4, change #7's name to X"). Apply the amendments and re-show only the changed rows, then ask again.

### Step 7: Execute

In a single batched operation where possible:

- **Moves with rename**: before each move, **check that the destination does not already exist** (`test -e "<dst>" && echo EXISTS` or equivalent). If it exists: stop the whole batch, report the collision, and ask the user how to resolve (rename one, delete one, merge). Never overwrite silently - `mv` on bash will clobber the target by default and there is no undo. Once the path is clear: `mv "<src>" "<dst>"`. Use absolute paths inside the vault. Quote spaces.
- **On move failure** (permission denied, path not found, target exists despite check, filesystem error): **stop the batch immediately**, report which moves succeeded and which failed, and wait for direction. Do not continue moving subsequent files - the proposal table was approved as a unit and partial execution leaves the vault in an unclear state.
- **Deletions**: `rm "<path>"`. Only delete files explicitly marked Delete in the approved table.
- **Image rotation**: on Windows, use PowerShell + System.Drawing:
  ```powershell
  Add-Type -AssemblyName System.Drawing
  $img = [System.Drawing.Image]::FromFile($src)
  $img.RotateFlip([System.Drawing.RotateFlipType]::Rotate180FlipNone)
  $img.Save($dst, [System.Drawing.Imaging.ImageFormat]::Jpeg)
  $img.Dispose()
  ```
  Rotation values: `Rotate90FlipNone`, `Rotate180FlipNone`, `Rotate270FlipNone`. After rotation, delete the source file (the rotated version is already at the destination).
- **Mkdir** only for destinations the user approved in Step 5. Never silently create new folders.

After moves complete, re-list `triage/` and confirm only the expected residue remains (approved subdirectories, files explicitly left).

### Step 8: Update README(s)

For each receiving folder whose README was flagged in Step 5's follow-on edits:

- Add new rows to existing tables (Insurance, Mortgage, etc.) - preserve column order.
- Add new entries to the source-document lists, in the correct sub-section, in date order.
- If a new sub-section is appropriate (e.g. "Renovation 2013", "Tenant search"), create it in the natural ordering of existing sub-sections.
- **Do not** rewrite or reorganize the README beyond the new entries. Match the existing voice and bullet style - read 2-3 nearby bullets first and copy their structure.

For multi-paragraph headers (Background, Open items): only edit if the new file changes a stated fact (e.g. "X document not on file" becomes "X document on file as 20151012 ..."). Otherwise leave the prose alone.

### Step 9: Re-render PDFs (if applicable)

If the vault has `render.ps1`:

- Check whether the vault is in **spread** state (README.md sits next to README.pdf in PARA folders) or **collected** state (README.md files all live under `resources/mds/`).
- If **spread**: run `& "<vault>\render.ps1"`. It will only re-render the MDs that are newer than their PDFs.
- If **collected**: do not run render. The MD edits in `resources/mds/` don't have a directly-rendered sibling; the maintainer will flip → edit → render → flip back on their own cycle. Tell the user "Vault is in collected state; PDF re-render skipped. Run `.\flip.ps1 spread; .\render.ps1; .\flip.ps1 collect` when ready."

### Step 10: Summarize

A short closing message:

- N files moved (link each to its new path)
- N files deleted (with the reason)
- N README(s) updated (link each)
- Anything left in `triage/` (subdirectories, files left for user, etc.)

Keep it tight - one line per category.

## Strict rules

- **Show the proposal table BEFORE doing anything destructive.** Even if the user says "just do it" in their first message, build the table first; it's the audit trail.
- **Never delete a file without an explicit Delete row in the approved table.** Duplicates that look identical-but-not-quite stay until the user confirms.
- **Never invent new top-level PARA folders** (e.g. a new `areas/<x>/`) without asking. Sub-folders inside an existing entity are fine when the convention supports them (e.g. `sources/photos/`).
- **Never modify file content** beyond rotation. Don't re-OCR, don't re-compress, don't strip metadata.
- **Never translate document names.** If the source convention is in Dutch/French and the file is Dutch, the rename stays Dutch.
- **Respect "do not add" rules** in the vault's CLAUDE.md (no template files, no actions.md if disabled, no derived outputs, etc.). If a triaged file looks like an action list, ask before adding it.
- **Don't touch the `_*` prefixed subdirectories in triage** without explicit user direction. Underscore-prefix is a convention for "handoff" / "in flight" batches that the maintainer is managing manually.

## Edge cases

- **Vault has no CLAUDE.md** (or no filing rules section): show the proposal table with file destinations only, and ask the user to dictate the naming convention before any renames execute.
- **File is encrypted/locked PDF**: skip content inspection, propose destination from filename + file mod date only, and flag in the Why column as "(content not readable - name-only inference)".
- **File modification date is wildly different from document date** (e.g. 2024 mod date on a 2013 invoice): use document date. Mention the discrepancy in the Why column.
- **Two triage files describe the same event** (e.g. a scanned + a digital version of the same letter): keep the digital, delete the scan. Show both in the table; mark the scan as Delete (redundant scan) with a Why pointing to the digital version's path.
- **Triage file references a person not yet in `areas/network/`**: propose creating the contact file with a one-line bio (parties, date first encountered, source-doc reference), but only execute after user approval. Don't auto-create.
- **Triage file references a property/project not yet in the vault**: propose either (a) leaving in triage with a note about what's needed, or (b) creating the new folder with a stub README. Default to (a).
- **Image with EXIF orientation tag**: still inspect visually after Reading. EXIF orientation is widely ignored by renderers, so a "correct" EXIF tag with rotated pixels still needs the pixels rotated.
- **PDF where one page is rotated and others aren't**: flag for the user; PDF page rotation is risky to attempt blindly.
- **File looks like it belongs to a different vault or context** (client work in a personal vault, personal records in an engagement vault): ask before filing. One-vault-per-context only works if triage respects the boundary.

## Example proposal table fragment

*The example below uses a real-estate vault's naming convention (`YYYYMMDD <Who> <Description> [<scope>].<ext>`) and entity-folder structure. Your vault's `CLAUDE.md` is authoritative - convention and entity shape vary by vault.*

```
| # | Source file | Action | Why | Destination |
|---|---|---|---|---|
| 1 | `Ads_1409695_3182960_NL-5.pdf` | Move + rename | Rental ad N°3182960 for an 85m², 3rd-floor, 2-bedroom apartment with the owner's phone/email. File date Nov 2013, right after the Stationsstraat move-in. Matches the Stationsstraat description (3rd floor, 2 bedrooms). | [archive/properties/stationsstraat/sources/20131114 Immoweb Te Huur advertentie 3182960.pdf](archive/properties/stationsstraat/sources/20131114%20Immoweb%20Te%20Huur%20advertentie%203182960.pdf) |
| 2 | `Factuur Lockwerk.pdf` | Delete | Byte-identical duplicate (MD5 10d9edcc...) of [archive/properties/stationsstraat/sources/20160306 Lockwerk Factuur herstelling deur 497_60.pdf](archive/properties/stationsstraat/sources/20160306%20Lockwerk%20Factuur%20herstelling%20deur%20497_60.pdf). | (deleted) |
| 3 | `Tax Bank Mortgage 2011.JPG` | Move + rename + rotate 180° | Bank's 2011 repayment certificate (upside down). Contract 726-1234567-89 = the Stationsstraat mortgage. Printed 31-03-2012. Fills the 2011 gap. | [archive/properties/stationsstraat/sources/20111231 Bank Betalingsattest hypothecaire lening 2011 726-1234567-89.jpg](archive/properties/stationsstraat/sources/20111231%20Bank%20Betalingsattest%20hypothecaire%20lening%202011%20726-1234567-89.jpg) |
```

Follow-on README edits to mention in the same response:

- `archive/properties/stationsstraat/README.md`: add a new "Repayment certificates (2011-2014)" sub-section under Mortgage, with a year-by-year repayment table; add an AXA 2015 row to the Insurance table.

## Related skills

Part of the para-os skill set. Sibling skills:

- `/deep-clean` - comprehensive cleanup pass: audits structural issues, normalises READMEs, closes open items from source PDFs. Run **after** `/triage` has emptied the loose-files queue.
