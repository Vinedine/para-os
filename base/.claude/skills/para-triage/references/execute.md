# Executing an approved table (Steps 7 to 9)

Nothing here runs before the proposal table has been shown and explicitly approved. The table was approved as a unit, so a failure anywhere stops the whole batch.

## Loose files

In a single batched operation where possible:

- **Moves with rename**: before each move, **check that the destination does not already exist** (`test -e "<dst>" && echo EXISTS`). If it exists, stop the whole batch, report the collision, and ask how to resolve. Never overwrite silently: `mv` clobbers by default and there is no undo. Once clear: `mv "<src>" "<dst>"`, absolute paths, quote spaces.
- **On any move failure**: **stop the batch immediately**, report which moves succeeded and which failed, and wait for direction.
- **Deletions**: `rm "<path>"`. Only delete files explicitly marked Delete in the approved table.
- **Mkdir** only for destinations approved in the table. Never silently create new folders.
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

After moves complete, re-list `triage/` and confirm only the expected residue remains (approved subdirectories, files explicitly left).

## Connector items

- **Update existing**: edit the tracked item in place - annotate the existing `actions.md` line ("reply received `<date>`", "docs arrived `<date>`, now actionable") or the contact/project note. Keep the vault's Obsidian Tasks markers; do not tick an item complete unless the work is actually done. Never add a duplicate line.
- **Add action**: append the task line to the named `actions.md`, using that vault's markers. Never create a new `actions.md`; if the vault has none, this action was not offered.
- **Note to triage**: write a short `.md` into `triage/` - frontmatter (`source`, `thread_id`, `date`, `link`), body a 2-3 line summary of what needs attention. Do not file it further in this pass.
- **Ledger writes**: per the seen-ledger rules in [sources.md](sources.md#the-seen-ledger).
- **Never** send, reply to, archive, or label a mailbox. The only writes are the `actions.md` edit, the `triage/` note, and the ledger.

## README follow-ons (Step 8)

For each receiving folder whose README was flagged in the proposal's follow-on edits:

- Add new rows to existing tables (Insurance, Mortgage, and so on) - preserve column order.
- Add new entries to the source-document lists, in the correct sub-section, in date order.
- If a new sub-section is appropriate ("Renovation 2013", "Tenant search"), create it in the natural ordering of existing sub-sections.
- **Do not** rewrite or reorganize the README beyond the new entries. Match the existing voice and bullet style - read 2-3 nearby bullets first and copy their structure.

For multi-paragraph headers (Background, Open items): only edit if the new file changes a stated fact ("X document not on file" becomes "X document on file as 20151012 ..."). Otherwise leave the prose alone.

## Re-render PDFs (Step 9)

Only if the vault has `render.ps1`:

- Check whether the vault is in **spread** state (README.md sits next to README.pdf in PARA folders) or **collected** state (README.md files all live under `resources/mds/`).
- **Spread**: run `& "<vault>\render.ps1"`. It re-renders only the MDs newer than their PDFs.
- **Collected**: do not run render. Tell the user "Vault is in collected state; PDF re-render skipped. Run `.\flip.ps1 spread; .\render.ps1; .\flip.ps1 collect` when ready."
