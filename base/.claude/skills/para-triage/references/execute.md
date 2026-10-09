# Executing an approved batch (Steps 7 and 8)

Only approved items execute; a deferral is a no-op. **A failure anywhere stops the batch**: report what succeeded and what failed, and wait.

## Loose files

- **Each move**: the `changed` re-check ([scripts.md](../../para-shared/scripts.md)), then `test -e "<dst>" && echo EXISTS`, a hit stopping the batch since `mv` clobbers, then `mv "<src>" "<dst>"`, absolute and quoted. Create only folders an approval named, and repoint inbound references in the same step. A file the re-check reports `arrived` is left and named in the summary.
- **Delete** per [operating-discipline.md](../../para-shared/operating-discipline.md#deleting-a-file), after the same re-check and repoint.
- **Create entity**: `/para-new` runs first, settling the entity, not whether to create one; the item files into whatever entity it ends on, or stays on none. Into a single-file entity (a contact card) its content is folded, and the file gets its own Delete (no lasting value) question.
- **File it + add action**: the move, then the line, appended as **Add action** appends it.
- **Extract** outside the vault; **Split** by copying pages, never re-rendering them (`pypdf`'s `PdfWriter.add_page`). Originals wait for their own Delete question.
- **Run vault script**: dry run first. A script acting on a whole folder acts on declined items too: move them out of its scope, or pass a file list, before `--write`. The triage copy's delete follows its own approval and an MD5 match against the script's copy.
- **Rotation** rewrites the pixels, keeping the format.

Then re-list `triage/`: only the expected residue and arrivals remain.

## Connector items

- **Update existing** writes as approved, in the vault's task markers ("reply received `<date>`"), ticking nothing unfinished. **Add action** and **Add register row** append what was shown, the row to the register's open table, where its rule file's header replaces a `_None currently._` placeholder. Never create the file.
- **A staged note**: that write, then the note deleted or filed as its option said; **Stage in other vault** moves it, collision-checked, into that vault's `triage/`. The summary names any other vault. No seen-ledger entry for a note.
- **A re-read that reached a message newer than `note.ingest_seen.seen_date`**: after the disposition, add this vault's registry name to that message's `by_message_id` list in `ingest_ledger.path`, keyed as connectors.md step 6 keys it, leaving the watermark and `routed` alone.
- **Note to triage**: a short `.md` in `triage/`, frontmatter `source`, `thread_id`, `date`, `link`, then two or three lines on what needs attention.
- **The seen-ledger**: [sources.md](sources.md#the-seen-ledger).

## Follow-ons (Step 8)

A flagged `README.md` or `brief.md` gets its rows in column order, source entries in date order and a sub-section only where due, in the nearby entries' voice; prose changes only a fact the item changes, and nothing else is rewritten. A meeting record's header lines and cells are rewritten as shown, its next step and `Waiting on` line appended; its stage question and draft write nothing.
