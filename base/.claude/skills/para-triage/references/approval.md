# Approval: the manifest and the questions (Steps 5 and 6)

**The mechanics are [../../para-shared/asking.md](../../para-shared/asking.md)** - the manifest, the four-questions-a-call batching, the question shape, grouping and its three limits, how to read an Other or a skipped answer, and when not to ask at all. This file holds what is triage's own: the vocabulary its questions offer, what "linked" means for a triage batch, and which arguments fall back to the table.

The classification itself is [filing.md](filing.md) for loose files and [sources.md](sources.md) for connector threads; nothing here re-decides what an item is, only how its disposition gets approved.

## The action vocabulary

What a question may offer as an option, and what the `Action` column holds on the table path. Nothing outside this list, except what the operator types into **Other**.

**Loose files:** **File it** (move + rename to the convention) · **File it + rotate Nx** · **Extract** (an archive: each member gets its own destination and convention name, listed in the option description; the archive itself then gets its own Delete question) · **Split** (a PDF bundling several documents: one new file per document, pages copied without re-encoding, each filed like any loose file; the original stays until its own Delete question) · **Run vault script** (the vault's filing rules hand this kind of file to a script of its own: the script's dry-run verdict for the file is the evidence, and the triage copy's delete is its own question once the script has run) · **Delete (duplicate)** (byte-identical; cite the surviving path and the MD5 match) · **Delete (redundant scan)** (content overlap, not a hash match - always confirm, so the recommended option here is `Leave in triage`, not the delete) · **Delete (no lasting value)** (nothing a later reader would need, because the outcome is already recorded elsewhere - cite where) · **Create entity** (no entity fits; `/para-new` creates it and the file is filed into it, per [execute.md](execute.md)) · **Move out of vault** (the vault's own rules keep this kind of file out of every synced folder - a takeout archive, a bulk export: the operator names the target, and the move is collision-checked like any other) · **Leave in triage** (no good destination; say what is missing).

**A subdirectory is listed, never asked.** It is an intentional sub-batch, and the only options a question could offer it both change nothing, so it goes in a list under the manifest (`Subdirectories, not asked: ...`) and in the summary.

**A staged mail note takes the connector-thread vocabulary too.** A loose `.md` staged from a mailbox - by `/para-ingest`, or by an earlier run's **Note to triage** - stands in for the thread it came from: its header carries `Source`, `Received` and `Link` lines, or a `thread_id` in its frontmatter. Its question may offer everything above plus **Update existing**, **Add action** and **Dismiss (other vault)** from the list below, each of which also disposes of the note, and the option says how: `Update existing, note deleted` is the default shape, because the thread survives in the mailbox and the note's Link names it; filing the note as well is for a note that holds content the mailbox copy does not. **Dismiss (noise)** is **Delete (no lasting value)** here, and **Leave thread** is **Leave in triage**. The note's thread was ledgered when it was staged, so triage writes no seen-ledger entry for it.

**Connector threads** (the item is named by subject, sender and date):

- **Update existing** - the thread bears on something the vault already tracks. Annotate the existing `actions.md` line or contact/project note; do NOT add a duplicate. **In an active vault this is the default** - check for an existing item before reaching for Add action.
- **Add action** - a genuinely new to-do with no tracked home. **At most one next step per thread**, the immediately actionable move, never a decomposition into several checkboxes (the actionable-frontier rule; later steps earn their checkbox when they become the frontier). If the destination file already holds 12 or more open items, say so in the option description (`file at N open - groom?`) instead of silently growing it. **Never in notes-only vaults.**
- **Note to triage** - worth keeping; filed on a later pass, never straight into `projects/`.
- **Dismiss (noise)** - never action-worthy in any vault (newsletter, notification, bot, promo); ledgered so it does not resurface. Destination "(ledger only)".
- **Dismiss (other vault)** - real correspondence belonging to a different vault; **not** ledgered. Destination "(belongs to \<vault\>)".
- **Leave thread** - do nothing; it stays un-dispositioned and will resurface on the next run.

**Filing is not the default.** An item is in `triage/` because something arrived, not because it earned a place in the vault. Scheduling chatter whose meeting already has a record, a notification whose fact now lives in the file it belongs to, a staged note that is a truncated snippet of a mail still sitting in the mailbox: filing these is content inflation. Where the value is already captured somewhere, **Delete (no lasting value)** is the honest recommendation and goes first, with the surviving record named as its evidence. **It leads only where that survivor can be named**: the path of the filed document or tracked line that already holds the value, or, for a staged mail note, the thread its own Link names, which stays in the mailbox and needs no re-read to be cited. Where no survivor can be named, the loss is irreversible on a judgment, so **Leave in triage** leads, per [asking.md](../../para-shared/asking.md#grouping). **An empty `triage/` reached by filing everything is not a clean vault**, and the count going to zero will not tell you which one you did.

**A delete or a move names what links to the file.** The scan's inbound references for the file go in the option description, with the repoint each needs (to the survivor on a delete, to the new path on a move); a delete whose references have no survivor to point at is not recommended.

## What "linked" means here

Under the shared grouping limits - no destructive item grouped with anything, no differing destinations, never more than five:

- Pages of one document arriving as separate files.
- A Google-native stub and the `.md` it converted to.
- Several shots of one physical thing (a business card, a multi-page letter photographed).
- Files that arrived together from one sender or event and share a destination folder.
- A connector thread and an attachment of it that a sync script dropped into `triage/`.
- **The notes staged from one thread**, which carry the same six-character hash in their names (a resurfaced thread stages a fresh note beside the first). They get one question whose options say what happens to every note, and this is the one group that may carry deletes: the survivor is one named record, the thread in the mailbox, so a single fact settles them all. [asking.md](../../para-shared/asking.md#grouping) names this exception.

## The manifest

Per the shared format, one line per question:

```
14 items, 11 questions (2 grouped), 3 rounds.

 1  20260709 Acme - Invoice.pdf                → File    projects/acme-rollout/sources/
 2  IMG_4471.jpg + IMG_4472.jpg                → File    areas/network/ (business card)
 3  scan0031.pdf                               → Delete  duplicate of archive/meetings/20260612 ...
 4  "Re: Q3 pricing" - ops@example.com, 09-08  → Update  projects/acme-rollout/actions.md
 5  20260910 Re Q3 pricing 4f9c2a.md (staged)   → Update  projects/acme-rollout/actions.md, note deleted
...

Subdirectories, not asked: triage/_handover-scans/ (12 files)
```

After it, list any **follow-on edits** to the receiving entity's main document, its `README.md` or its `brief.md` (new rows, new source-list entries, new sub-sections, a stated fact the filed item changes), naming which file and where in it. They are **not** separate questions: a follow-on is a consequence of its item being filed, so it applies only for items actually approved and is skipped for the rest.

## The table path

Triage's own list of arguments that do not ask, per the shared rule: **`preview`** (prints the manifest, then stops at the proposal), **`apply`** (runs on an approval already given), the unattended **`convert`** (no judgment calls to approve), and **`table`**, the explicit escape. On those paths the step builds the markdown table it always did - `| # | Source item | Action | Why | Destination |` - gated on a single "reply **go**", or nothing at all.
