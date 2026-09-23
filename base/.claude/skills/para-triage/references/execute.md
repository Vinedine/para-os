# Executing an approved batch (Steps 7 to 9)

Nothing here runs before every item has been put to the operator and approved - one question each, or one table approved as a unit on the paths that do not ask ([approval.md](approval.md)). Only approved items execute; a deferral is a no-op, not a delayed yes.

**A failure anywhere still stops the whole batch**, however the approvals were collected.

## Loose files

In a single batched operation where possible:

- **Read-only iPad delivery**: Steps 7 to 9 run inside [its cycle](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).
- **Create entity**: `/para-new` runs as a sub-step before the moves. Its questions settle the entity, not whether to create one. The item files into whatever entity it ends on (created, widened, or found to exist) under that entity's convention, which the approval covers, folder included, and the new brief cites that path. If it ends on no entity, the item stays in `triage/` and the batch carries on. **An entity with no folder** (a contact card, where the vault keeps contacts as single files) has nowhere to file the item: `/para-new` folds its content into the card as prose, and the triage file then gets its own **Delete (no lasting value)** question naming the card as the survivor.
- **Extract**: unpack into a temporary folder outside the vault, then move each member as the approval named it, with the collision check below per member. The archive itself stays until its own Delete question.
- **Split**: copy each document's pages into a new file with a tool that copies pages rather than re-rendering them (`pypdf`'s `PdfWriter.add_page`), named to the convention, into `triage/` or straight to the approved destinations. The original is untouched until its own Delete question, which is what keeps this inside the rule that a file's content is never modified.
- **Run vault script**: the script the vault's filing rules name, dry run first. **A script that acts on the whole folder acts on declined items too**, so before `--write`, move every item not approved for it out of the script's scope (or pass it an explicit file list, where it takes one) and put them back afterwards. The triage copy's delete runs only once the script reports the file handled, and on its own approval, after an MD5 match against the copy the script wrote, where it wrote one.
- **Move out of vault**: to the target the operator named, with the collision check below. Never into another vault: that is **Dismiss (other vault)**, which writes nothing there.
- **Re-check before each delete or move**, per [para-shared/scripts.md](../../para-shared/scripts.md).
- **Repoint inbound references in the same step** as the delete or move that breaks them, to the survivor or the new path the approval named, and resolve each rewritten link to a file that exists.
- **Moves with rename**: before each move, **check that the destination does not already exist** (`test -e "<dst>" && echo EXISTS`). If it exists, stop the whole batch, report the collision, and ask how to resolve. Never overwrite silently: `mv` clobbers by default and there is no undo. Once clear: `mv "<src>" "<dst>"`, absolute paths, quote spaces.
- **On any failure**: report which moves succeeded and which failed, and wait for direction.
- **Deletions are recoverable.** A file git tracks: `git rm "<path>"`, so history keeps it. An untracked one goes to the system trash: on Windows PowerShell `Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("<path>", 'OnlyErrorDialogs', 'SendToRecycleBin')`, on macOS `osascript -e 'tell application "Finder" to delete POSIX file "<absolute path>"'`, on Linux `gio trash "<path>"`. Where no trash is reachable, say the file is untracked and a delete is permanent, and ask before `rm`. Only delete a file whose own Delete disposition was approved - its own question, or its own Delete row on the table path. The summary says which way each file went.
- **Mkdir** only for destinations named in an approved disposition. Never silently create new folders.
- **Image rotation**: on Windows, PowerShell plus System.Drawing. **Preserve the source format**: `Save($dst)` with no format argument lets GDI+ pick the encoder from the destination extension. Write to a temp path first, because `FromFile` holds an open handle on `$src`:

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

After moves complete, re-list `triage/` and confirm only the expected residue remains (approved subdirectories, files explicitly left). A file that arrived during the run is not residue: leave it, and name it in the summary as arrived.

## Connector items

These apply to a connector thread and to a staged mail note alike ([approval.md](approval.md) gives the note this vocabulary).

- **Update existing**: edit the tracked item in place - annotate the existing `actions.md` line ("reply received `<date>`", "docs arrived `<date>`, now actionable") or the contact/project note. Keep the vault's Obsidian Tasks markers; do not tick an item complete unless the work is actually done. Never add a duplicate line.
- **Add action**: append the task line to the named `actions.md`, using that vault's markers. Never create a new `actions.md`; if the vault has none, this action was not offered.
- **On a staged mail note**, the write above comes first, then the note goes as its option said: deleted (the default, the thread surviving in the mailbox) or filed. **Dismiss (other vault)** on a note deletes it here and names the vault it belongs to in the summary; nothing is written to that vault. No seen-ledger entry for any of these: the note's thread was ledgered when it was staged.
- **Note to triage**: write a short `.md` into `triage/` - frontmatter (`source`, `thread_id`, `date`, `link`), body a 2-3 line summary of what needs attention. Do not file it further in this pass.
- **Ledger writes**: per the seen-ledger rules in [sources.md](sources.md#the-seen-ledger).

## Follow-ons (Step 8)

For each receiving entity whose main document - its `README.md`, or its `brief.md` where that is what the entity carries - was flagged in the proposal's follow-on edits:

- Add new rows to existing tables (Insurance, Mortgage, and so on) - preserve column order.
- Add new entries to the source-document lists, in the correct sub-section, in date order.
- If a new sub-section is appropriate ("Renovation 2013", "Tenant search"), create it in the natural ordering of existing sub-sections.
- **Do not** rewrite or reorganize the document beyond the new entries. Match the existing voice and bullet style - read 2-3 nearby bullets first and copy their structure.

For multi-paragraph headers (Background, Open items): only edit if the new file changes a stated fact ("X document not on file" becomes "X document on file as 20151012 ..."). Otherwise leave the prose alone.

## Re-render PDFs (Step 9)

Only if the vault has `render.ps1`: run it from the vault root, and on the read-only iPad delivery close [its cycle](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).
