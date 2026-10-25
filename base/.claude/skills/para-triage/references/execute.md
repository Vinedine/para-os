# Executing an approved batch (Steps 7 and 8)

**A failure anywhere stops the batch**: report what succeeded and what failed, and wait.

## Loose files

- **Each move**: the `changed` re-check ([scripts.md](../../para-shared/scripts.md)), then `test -e "<dst>" && echo EXISTS`, a hit stopping the batch since `mv` clobbers. Create only folders an approval named, and repoint inbound references in the same step.
- **Delete** per [operating-discipline.md](../../para-shared/operating-discipline.md#deleting-a-file), after the same re-check and repoint.
- **Create entity**: `/para-new` runs first and settles the entity; the item then files or [folds](filing.md#choose-a-destination-and-a-name-step-4) into whatever entity it ends on, or stays.
- **Extract** outside the vault; **Split** by copying pages, never re-rendering them (`pypdf`'s `PdfWriter.add_page`).
- **Run vault script**: dry run first. A script acting on a whole folder acts on declined items too: move them out of its scope, or pass a file list, before `--write`. The triage copy's delete follows its own approval and an MD5 match against the script's copy.
- **Rotation** rewrites the pixels, keeping the format.

## Connector items

- **Update existing** writes as approved, in the vault's task markers ("reply received `<date>`"), ticking nothing unfinished. **Add action** and **Add register row** append what was shown, the row to the register's open table, its rule file's header replacing a `_None currently._` placeholder. Never create the file.
- **A staged note**: that write, then the note deleted or filed as its option said; **Stage in other vault** moves it, collision-checked. No seen-ledger entry for a note.
- **A re-read that reached a message newer than `note.ingest_seen.seen_date`**: after the disposition, add this vault's registry name to that message's `by_message_id` list in `ingest_ledger.path`, keyed as connectors.md step 6 keys it, leaving the watermark and `routed` alone.
- **Note to triage**: a short `.md` in `triage/`, frontmatter `source`, `thread_id`, `date`, `link`, then two or three lines on what needs attention.
- **The seen-ledger**: [sources.md](sources.md#the-seen-ledger).

## Follow-ons (Step 8)

Written as shown, in the order and voice of the entries beside them; nothing else in the file is rewritten. A meeting record's stage question and draft write nothing.
