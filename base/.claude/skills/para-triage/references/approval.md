# Approval: the manifest and the questions (Steps 5 and 6)

**The mechanics are [../../para-shared/asking.md](../../para-shared/asking.md)**: the manifest, batching, the question shape, grouping, reading answers, and when not to ask. This file holds triage's own vocabulary, what "linked" means here, and which arguments take the table.

## The action vocabulary

What a question may offer, and what the `Action` column holds on the table path. Nothing else, except what the operator types into **Other**.

**Loose files:**

- **File it** (move + rename to the convention) · **File it + rotate Nx**.
- **Extract** (an archive): each member's destination and convention name listed in the option description; the archive then gets its own Delete question.
- **Split** (a PDF bundling several documents): one new file per document, pages copied without re-encoding, each filed like any loose file; the original stays until its own Delete question.
- **Run vault script**: the vault's filing rules hand this kind of file to a script. Its dry-run verdict is the evidence; the triage copy's delete is its own question once the script has run.
- **Delete (duplicate)**: byte-identical; cite the surviving path and the MD5 match.
- **Delete (redundant scan)**: content overlap, not a hash match. Always confirm: `Leave in triage` is the recommended option.
- **Delete (no lasting value)**: the outcome is already recorded elsewhere; cite where.
- **Create entity**: no entity fits; `/para-new` creates it and the file files into it ([execute.md](execute.md)). **Asked, never a table row**: `/para-new` asks its own questions, which no table path can answer, so there the item is **Leave in triage**, its Why naming the entity to create.
- **Move out of vault**: the vault's rules keep this kind of file out of every synced folder (a takeout archive, a bulk export); the operator names the target.
- **Leave in triage**: no good destination; say what is missing.

**A subdirectory is listed, never asked**: every option it could get changes nothing. It goes under the manifest (`Subdirectories, not asked: ...`) and in the summary.

**A staged mail note takes the connector-thread vocabulary too.** A loose `.md` staged from a mailbox (by `/para-ingest` or an earlier **Note to triage**; the scan's `note.mail_note`) stands in for its thread. Its question may add **Update existing**, **Add action** and **Dismiss (other vault)**, each also disposing of the note, and the option says how: `Update existing, note deleted` is the default shape, since the thread survives in the mailbox and the note's Link names it; file the note too only where it holds content the mailbox copy does not. **Dismiss (noise)** is **Delete (no lasting value)** here, and **Leave thread** is **Leave in triage**. Its thread was ledgered when staged, so triage writes no seen-ledger entry for it.

**Connector threads** (named by subject, sender and date):

- **Update existing** - bears on something the vault already tracks: annotate that `actions.md` line or contact/project note. **The default in an active vault.**
- **Add action** - a genuinely new to-do with no tracked home: **one next step**, the immediately actionable move, never several checkboxes. Where the destination file holds 12 or more open items, say so in the option description (`file at N open - groom?`). **Never in notes-only vaults.**
- **Note to triage** - worth keeping; filed on a later pass, never straight into `projects/`.
- **Dismiss (noise)** - never action-worthy in any vault (newsletter, notification, bot, promo); ledgered. Destination "(ledger only)".
- **Dismiss (other vault)** - real correspondence for a different vault; **not** ledgered. Destination "(belongs to \<vault\>)".
- **Leave thread** - nothing; it resurfaces next run.

**Filing is not the default.** An item is in `triage/` because something arrived, not because it earned a place. Scheduling chatter whose meeting already has a record, a notification whose fact now lives where it belongs, a staged note that is a snippet of a mail still in the mailbox: filing these is content inflation. Where the value is already captured, **Delete (no lasting value)** leads, naming the survivor as evidence: the filed document or tracked line holding the value, or, for a staged mail note, the thread its Link names. **Where no survivor can be named, Leave in triage leads**, since the loss would be irreversible on a judgment ([asking.md](../../para-shared/asking.md#grouping)).

**A delete or a move names what links to the file**: the scan's `inbound` references in the option description, each with its repoint (to the survivor on a delete, the new path on a move). A delete whose references have no survivor to point at is not recommended.

## What "linked" means here

Under the shared grouping limits:

- Pages of one document arriving as separate files.
- A Google-native stub and the `.md` it converted to.
- Several shots of one physical thing (a business card, a photographed letter).
- Files that arrived together from one sender or event and share a destination folder.
- A connector thread and an attachment of it a sync script dropped into `triage/`.
- **The notes staged from one thread** (`items.same_thread`, the same six-character hash in their names): one question saying what happens to each note. This group alone may carry deletes, its single survivor being the thread in the mailbox ([asking.md](../../para-shared/asking.md#grouping)).

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

After it, list the **follow-on edits** to each receiving entity's `README.md` or `brief.md` (new rows, source-list entries, sub-sections, a stated fact the filed item changes), naming the file and where. They are not separate questions: each applies only if its item is approved.

## The table path

The arguments that do not ask are `preview`, `apply`, `convert` and `table`, plus any run with no interactive operator ([SKILL.md](../SKILL.md) Steps 5 and 6).
