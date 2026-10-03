# Executing an approved batch (Steps 7 to 9)

Only approved items execute, whether approved by their own question or by a table approved as a unit ([approval.md](approval.md)). A deferral is a no-op, not a delayed yes. **A failure anywhere stops the whole batch.**

## Loose files

- **Read-only iPad delivery**: Steps 7 to 9 run inside [its cycle](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).
- **Create entity**: `/para-new` runs as a sub-step before the moves; its questions settle the entity, not whether to create one. The item files into whatever entity it ends on (created, widened, or found to exist) under that entity's convention, folder included, which the approval covers, and the new brief cites that path. Ending on no entity, the item stays in `triage/` and the batch carries on. **An entity with no folder** (a contact kept as a single file): `/para-new` folds the item's content into the card as prose, and the triage file then gets its own **Delete (no lasting value)** question naming the card as the survivor.
- **Extract**: unpack into a temporary folder outside the vault, then move each member as approved, each collision-checked. The archive stays until its own Delete question.
- **Split**: copy each document's pages into a new file with a tool that copies rather than re-renders them (`pypdf`'s `PdfWriter.add_page`), named to the convention, into `triage/` or the approved destinations. The original stays untouched until its own Delete question.
- **Run vault script**: dry run first. **A script acting on the whole folder acts on declined items too**: before `--write`, move every item not approved for it out of its scope (or pass an explicit file list, where it takes one), and put them back after. The triage copy's delete runs only once the script reports the file handled, on its own approval, after an MD5 match against any copy the script wrote.
- **Move out of vault**: to the target the operator named, collision-checked. Never into another vault: that is **Dismiss (other vault)**, which writes nothing there.
- **Re-check before each delete or move**, per [para-shared/scripts.md](../../para-shared/scripts.md). A file it reports as `arrived` came in after the scan: leave it, and name it in the summary as arrived.
- **Repoint inbound references in the same step** as the delete or move that breaks them, to the survivor or new path the approval named, resolving each rewritten link to a file that exists.
- **Collision check before every move**: `test -e "<dst>" && echo EXISTS`. If it exists, stop the whole batch, report it, and ask how to resolve it; `mv` clobbers silently and has no undo. Once clear: `mv "<src>" "<dst>"`, absolute paths, quoted.
- **On any failure**: report which moves succeeded and which failed, and wait for direction.
- **Delete only a file whose own Delete disposition was approved**, per [operating-discipline.md](../../para-shared/operating-discipline.md#deleting-a-file).
- **Mkdir** only for destinations named in an approved disposition.
- **Image rotation** (Windows, System.Drawing): `Save` with no format argument keeps the source format, and the temp path is needed because `FromFile` holds a handle on `$src`:

  ```powershell
  Add-Type -AssemblyName System.Drawing
  $tmp = "$dst.rotating"
  $img = [System.Drawing.Image]::FromFile($src)
  $img.RotateFlip([System.Drawing.RotateFlipType]::Rotate180FlipNone)
  $img.Save($tmp)                       # encoder inferred from $dst's extension
  $img.Dispose()                        # releases the handle on $src
  Move-Item -Force $tmp $dst
  ```

  Rotation values: `Rotate90FlipNone`, `Rotate180FlipNone`, `Rotate270FlipNone`. Then delete the source if `$src` differs from `$dst`.

After the moves, re-list `triage/` and confirm only the expected residue and the arrivals remain.

## Connector items

For a connector thread and a staged mail note alike:

- **Update existing**: annotate the tracked item in place, the `actions.md` line ("reply received `<date>`", "docs arrived `<date>`, now actionable") or the contact/project note, in the vault's Obsidian Tasks markers; a register row gets its last-touch and next-step cells rewritten. Never tick an item unless the work is done, and never add a duplicate line.
- **Add action**: append the task line to the named `actions.md`, in the vault's markers. Never create an `actions.md`.
- **Add register row**: append the approved row, as shown, to the register's open table (under `## Open` where it splits open from closed), whose `_None currently._` placeholder gives way to the header its rule file declares. Never create the register.
- **On a staged mail note**, that write comes first, then the note goes as its option said: deleted (the default) or filed. **Dismiss (other vault)** deletes the note and names its vault in the summary, writing nothing there. No seen-ledger entry for any of these.
- **A re-read that reached past the note's ingest seen point** (a message newer than `note.ingest_seen.seen_date`), once the note's disposition has executed: add this vault's registry name to each such message's `by_message_id` list in `/para-ingest`'s ledger (`ingest_ledger.path`), keyed as [connectors.md](../../para-shared/connectors.md) step 6 keys it, so the next ingest does not stage it here again. The watermark and `routed` stay: another routed vault may still be owed the message.
- **Note to triage**: write a short `.md` into `triage/` with frontmatter (`source`, `thread_id`, `date`, `link`) and a 2-3 line summary of what needs attention. Do not file it further this pass.
- **Ledger writes**: per [sources.md](sources.md#the-seen-ledger).

## Follow-ons (Step 8)

For each receiving entity whose `README.md` or `brief.md` was flagged with follow-on edits: add table rows in the existing column order, source-list entries in the right sub-section in date order, and a new sub-section only where one is due, in the existing order. Match the nearby entries' voice and structure, and **rewrite nothing else**; in prose sections (Background, Open items) change only a stated fact the new file changes ("X document not on file" becomes "X document on file as ...").

## Re-render PDFs (Step 9)

Only if the vault has `render.ps1`: run it from the vault root, and on the read-only iPad delivery close [its cycle](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).
