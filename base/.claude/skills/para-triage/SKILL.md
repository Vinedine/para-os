---
name: para-triage
description: Empty the current vault's triage/ folder - and any configured triage sources (mailboxes, sync scripts) - by classifying each item, proposing a destination or action, then executing after user confirmation. Use when user asks to "process triage", "clean up triage", "empty the inbox", "check my email for anything to do", or types /para-triage.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content
arg-hint: '[preview|apply]'
---

# Triage

Processes every loose file in the current vault's `triage/` folder - plus any items pulled from the vault's configured triage sources (mailboxes, sync scripts) - by:

1. Identifying what each file is (read content, infer date/source/scope)
2. Choosing a destination folder by matching content to existing vault entities
3. Applying the vault's source-file naming convention (read from CLAUDE.md)
4. Detecting byte-identical duplicates and obvious redundancies
5. Detecting orientation issues for scanned images
6. **Showing a full proposal table BEFORE doing anything**, then waiting for explicit user approval
7. On approval: moving + renaming, rotating images, deleting duplicates
8. Updating the relevant README(s) so new files are documented in context
9. Re-rendering PDF siblings if the vault is in spread state

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime to discover the naming convention, the PARA layout, and any iPad-rendering toolchain (`flip.ps1` / `render.ps1`). It also reads the optional `## Triage sources` block to discover extra inputs to pull (mailboxes, sync scripts) beyond the `triage/` folder. **Vaults without that block behave exactly as before - folder-only.** No vault-specific paths or connectors are hardcoded; the block names them.

## When to invoke

- User types `/para-triage` (optionally with `preview` to skip the execution step)
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

### Step 2: Gather inputs (sources, then loose files)

**First, pull configured triage sources.** If the vault's CLAUDE.md has a `## Triage sources` block, run the multi-source pull in the [Triage sources](#triage-sources) section below **before** listing files:

- **sync-script** sources write their new items into `triage/`. In a real run, run them with `--write` (they dedup their own output, so re-running is safe); **in `preview` mode, run them dry (no `--write`)** and list what they would add - preview must have no side effects. After a real run, their files are ordinary loose files and get filed in the same pass.
- **connector** sources (mailboxes) write nothing; they yield action-worthy items that become their own proposal rows in Step 5.

If there is no `## Triage sources` block, skip this entirely - folder-only behavior is unchanged.

**Then list loose files.** Use Glob `triage/*` to get top-level entries (this now includes anything a sync-script source just wrote). Also note any subdirectories with Glob `triage/*/` - list them but **do not recurse into them** for the proposal. Subdirectories in `triage/` are intentional sub-batches (e.g. `triage/_some-handoff/`) and should be flagged for the user as "subdirectory - needs separate review" rather than blindly flattened.

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

For **connector source** items (email threads), the same table carries these actions - the `Source file` cell holds the thread (subject + sender + date), the `Destination` cell the target:
- **Update existing** - the thread bears on something the vault already tracks (a reply on an open thread, promised docs arriving). Annotate the existing `actions.md` line or contact/project note; do NOT add a duplicate. **In an active vault this is the default - check for an existing item before reaching for Add action.** Destination is the existing item to annotate.
- **Add action** - a genuinely new to-do with no existing tracked home (a reply is owed); Destination is the `actions.md` line to append. **Never in notes-only vaults** (no `actions.md`).
- **Note to triage** - worth keeping; Destination is the `triage/` note path (filed on a later pass, never straight into `projects/`).
- **Dismiss (noise)** - never action-worthy in any vault (newsletter, notification, bot, promo); ledgered so it does not resurface. Destination "(ledger only)".
- **Dismiss (other vault)** - real correspondence that belongs to a different vault; **not** ledgered - it is that vault's triage to surface, and re-dismissing here next run is cheap. Destination "(belongs to \<vault\>)".

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
- **Image rotation**: on Windows, use PowerShell + System.Drawing. **Preserve the source format** - never re-encode a `.png` as JPEG. `Save($dst)` with no format argument lets GDI+ pick the encoder from the destination extension, so a `.png` stays PNG and a `.jpg` stays JPEG. Write to a temp path first, because `FromFile` holds an open handle on `$src` and you cannot `Save` back over it (this also covers a rotate-in-place where `$src == $dst`):
  ```powershell
  Add-Type -AssemblyName System.Drawing
  $tmp = "$dst.rotating"
  $img = [System.Drawing.Image]::FromFile($src)
  $img.RotateFlip([System.Drawing.RotateFlipType]::Rotate180FlipNone)
  $img.Save($tmp)                       # encoder inferred from $dst's extension
  $img.Dispose()                        # releases the handle on $src
  Move-Item -Force $tmp $dst
  ```
  Rotation values: `Rotate90FlipNone`, `Rotate180FlipNone`, `Rotate270FlipNone`. After `Dispose()` releases the handle, delete the source file if `$src` differs from `$dst` (the rotated version is already at the destination).
- **Mkdir** only for destinations the user approved in Step 5. Never silently create new folders.

For **connector source** items in the approved table:
- **Update existing**: edit the tracked item in place - annotate the existing `actions.md` line (e.g. "reply received `<date>`", "docs arrived `<date>`, now actionable") or the contact/project note. Keep the vault's Obsidian Tasks markers; do not tick an item complete unless the work is actually done. Never add a duplicate line.
- **Add action**: append the task line to the named `actions.md`, using that vault's Obsidian Tasks markers. Never create a new `actions.md`; if the vault has none, this action was not offered.
- **Note to triage**: write a short `.md` into `triage/` - frontmatter (`source`, `thread_id`, `date`, `link`), body a 2-3 line summary of what needs attention. Do not file it further in this pass.
- **Ledger writes:** record the thread ID in `${PARAOS_HOME:-~/.paraos}/cache/triage-email/<vault>.json` with its disposition for every **Update existing**, **Add action**, **Note to triage**, and **Dismiss (noise)** - these are settled for this vault. Do **not** ledger a **Dismiss (other vault)**: that thread is another vault's to surface, and a permanent dismissal here would wrongly hide it if it ever became relevant. Create the file/dir if missing.
- **Never** send, reply to, archive, or label a mailbox. The only writes are the `actions.md` edit, the `triage/` note, and the ledger.

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

## Triage sources

Beyond the `triage/` folder, a vault may declare extra inputs in a `## Triage sources` block in its CLAUDE.md. This section is the protocol for pulling them. **If the vault has no such block, do nothing here** - the skill is folder-only, exactly as before.

Read the block. It is a table with columns `Source | Type | Endpoint | Relevant when` (wording varies; the first three are what you dispatch on). Two source types.

### sync-script sources

A script that writes new items into `triage/` (e.g. `granola-sync.js`).

- **Real run:** run it with `--write` (resolve the path relative to the vault root; `node` for `.js`, `py`/`python` for `.py`). These scripts default to dry-run and dedup their own output, so running them is idempotent and safe.
- **Preview (`preview` arg):** run it **without** `--write` and list what it would add. `preview` must not touch disk - never `--write` a sync source in preview.
- After a real run, its files are ordinary loose files in `triage/` and flow through Steps 3-9 like anything else - nothing more to do here.
- If the script errors (auth expired, network), report it and continue with the other sources; do not abort the whole triage.

### connector sources

A live mailbox read over MCP. Read-only - never writes to a mailbox.

**Dispatch by the `Type` value:**

| Type in manifest | Search tool | Content tool | Granularity |
|---|---|---|---|
| `connector: claude_ai_Gmail` | `mcp__claude_ai_Gmail__search_threads` | `mcp__claude_ai_Gmail__get_thread` | threads (native) |
| `connector: google-workspace` | `mcp__google-workspace__search_gmail_messages` (pass the Endpoint as `user_google_email`) | `mcp__google-workspace__get_gmail_messages_content_batch` | messages - **must group by `threadId`** |

If the named tool is not available in the session (connector not connected), skip that source and note it in the summary ("`<source>` declared but not connected - skipped"). Do not fail the run.

**Per connector source:**

1. **Build the query** from the `Relevant when` text plus a standard frame: `in:inbox -category:promotions -category:social -category:updates newer_than:30d`. Add the sender/subject operators the filter implies. **Exclude machine notifications** - widen these as the mailbox needs: `-from:noreply -from:no-reply -from:donotreply -from:notification -from:newsletter`, plus any app-notification domain it receives (e.g. `-from:odoo.com`). A working mailbox can be mostly bot mail.
2. **Operators only pre-filter; the judgment is the real gate.** Sender exclusions never catch everything - a variant address (`donotreply@`, `notification@`) or a *human* reply on an automated thread (someone replying to a bot "to-do") will slip through. Treat the query as a cheap first cut, then in the judgment (step 5) drop anything that is not genuinely a thread needing a reply or a decision.
3. **Search, then normalize to threads.** Gmail returns threads already. Workspace returns individual messages - group results by `threadId` so one conversation is one candidate, not N. Fetch metadata (subject, from, date) for the shortlist.
4. **Dedup against the ledger** (below): drop any thread already dispositioned.
5. **Judge action-worthiness** against `Relevant when`, reading snippets/bodies only for the shortlist. Keep the threads that genuinely need a reply or a decision. Two rules that kill common false positives: (a) **if the newest message in the thread is the mailbox owner's own (SENT), the ball is usually in the other party's court** - default to Dismiss unless the content clearly leaves an open task for the owner; (b) real correspondence about a *different* vault's business is **Dismiss (other vault)**, not action-worthy here.
6. **Before proposing a new action, match the thread against what the vault already tracks** - contacts (`areas/network/`), projects, ideas, and open `actions.md` items - the same entity-matching Step 4 does for loose files. If the thread bears on an existing item (a reply on an open thread, promised docs arriving), route it to **Update existing**, not **Add action**; only a thread with no existing home becomes **Add action**. Each surviving thread then becomes a Step 5 proposal row (**Update existing / Add action / Note to triage / Dismiss**, defined in Step 5).

### The seen-ledger

Connector dedup across runs lives outside the vault (a mailbox read must leak nothing into a synced folder):

- Path: `${PARAOS_HOME:-~/.paraos}/cache/triage-email/<vault>.json`, keyed by thread ID.
- Shape: `{ "<threadId>": { "disposition": "actioned|noted|dismissed", "date": "YYYY-MM-DD", "subject": "..." } }`.
- **Read** it during dedup (step 4 above) to skip dispositioned threads.
- **Write** it at execute time (Step 7) for settled dispositions - Update existing, Add action, Note to triage, and **Dismiss (noise)**. Do **not** ledger **Dismiss (other vault)**: that thread belongs to another vault, and a permanent dismissal here would hide it if it later became relevant - re-dismissing it next run is cheap.
- Missing file/dir → create them. It is a cache, not a system of record: deleting it only means threads may resurface.

## Strict rules

- **Show the proposal table BEFORE doing anything destructive.** Even if the user says "just do it" in their first message, build the table first; it's the audit trail.
- **Never delete a file without an explicit Delete row in the approved table.** Duplicates that look identical-but-not-quite stay until the user confirms.
- **Never invent new top-level PARA folders** (e.g. a new `areas/<x>/`) without asking. Sub-folders inside an existing entity are fine when the convention supports them (e.g. `sources/photos/`).
- **Never modify file content** beyond rotation. Don't re-OCR, don't re-compress, don't strip metadata.
- **Never translate document names.** If the source convention is in Dutch/French and the file is Dutch, the rename stays Dutch.
- **Respect "do not add" rules** in the vault's CLAUDE.md (no template files, no actions.md if disabled, no derived outputs, etc.). If a triaged file looks like an action list, ask before adding it.
- **Don't touch the `_*` prefixed subdirectories in triage** without explicit user direction. Underscore-prefix is a convention for "handoff" / "in flight" batches that the maintainer is managing manually.
- **Mail is read-only.** For connector sources, never send, reply, archive, or apply a label. Surface and draft only; the operator acts. The only writes the whole skill makes to a mailbox source are the local `triage/` note, `actions.md` line, and ledger.
- **Connector items land in `triage/` or `actions.md`, never straight into `projects/` or an entity folder** (a mis-routed email must stay cheap to fix), **and never into a *different* vault** - a thread for elsewhere is **Dismiss (other vault)**, not a cross-vault write.
- **Fuzzy-match before creating.** For a connector thread, check existing contacts, projects, and open `actions.md` items before proposing a new action. If it bears on tracked work, **Update existing** rather than adding a duplicate - an active vault already tracks most of what its mail is about.

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

*Illustrative only - your vault's `CLAUDE.md` gives the real naming convention and entity shape. The `Why` cell names the concrete signals used (date, reference number, party); the `Destination` is a clickable relative link.*

```
| # | Source item | Action | Why | Destination |
|---|---|---|---|---|
| 1 | `Factuur Lockwerk.pdf` | Delete | Byte-identical duplicate (MD5 10d9edcc…) of the filed copy. | (deleted) |
| 2 | `Tax Bank 2011.JPG` | Move + rename + rotate 180° | Bank 2011 repayment certificate (upside down), contract 726-1234567-89. | [.../sources/20111231 Bank Betalingsattest 726-1234567-89.jpg](path) |
| 3 | "RE: quote" — supplier, 14 Jul (email) | Update existing | Reply on an open thread; annotate the tracked action rather than duplicate it. | [projects/<x>/actions.md](path) |
```

Then note any follow-on README edits (new table rows, source-list entries) in the same response.

## Related skills

Part of the para-os skill set. Sibling skills:

- `/para-deep-clean` - comprehensive cleanup pass: audits structural issues, normalises READMEs, closes open items from source PDFs. Run **after** `/para-triage` has emptied the loose-files queue.
