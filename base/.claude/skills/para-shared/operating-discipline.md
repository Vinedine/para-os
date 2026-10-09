# Operating discipline (shared across skills)

The discipline every file-mutating skill follows. A read-only skill inherits only [Arguments](#arguments).

## Arguments

A leftover argument is a shape the skill's Arguments table names with no sentence punctuation, or a token starting with `--`, which [test-run.md](test-run.md) rules on. Anything else is prose wrapped around the invocation: run the default and treat it as an instruction for this run. Where it names the value of a `<key>=<value>` argument the table lists, that is the argument.

## Approval discipline

- **Show before you change.** A written proposal of what will change and where, before anything is applied; a "just do it" in the opening message does not skip it. The proposal is the audit trail, item-by-item questions included.
- **Non-destructive normalisations batch**: renames, link repoints, moves within one PARA bucket. **Deletions and moves between buckets are approved one by one.**

## Deleting a file

- **Compare the contents first.** A matching name or size is not proof: read both, confirm the survivor supersedes, then ask.
- **A delete stays recoverable**: `git rm` for a tracked file; the system trash for an untracked one (Windows PowerShell `Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("<path>", 'OnlyErrorDialogs', 'SendToRecycleBin')`, macOS `osascript -e 'tell application "Finder" to delete POSIX file "<absolute path>"'`, Linux `gio trash "<path>"`). No trash reachable: say the delete is permanent and ask before `rm`. One file per command, named in full, and the summary says which way each went.

## Preserve, don't rewrite

A structural pass (reorganising, retensing, renaming) keeps every fact and every word; wording is a separate pass. A file's content is not modified beyond rotating a scanned image, and a document's name is not translated.

## Leave other people's words alone

Third-party verbatim content is out of scope for every normalisation pass: synced publications, transcripts and their auto-extracted next steps, quoted correspondence, signed documents. Name what was excluded. A checkbox inside a transcript records what was said: mark the record frozen and route surviving work to a real `actions.md`, never tick it.

## A quoted syntax is not a used syntax

A link, checkbox, marker, heading or placeholder inside a fenced block or an inline code span is text discussing the syntax, not an instance of it: every scan skips it and no pass rewrites it. A `Grep` that cannot track fences (count mode, a raw pattern over `**/*.md`) counts samples: read the matched files or say the count includes them. Where the quoting is not mechanical (a marker named in plain prose), ask rather than file it.

## Defer to the vault

- **Resolve the vault root once** (`pwd` before anything has run, or the path the operator named), hold it, and build absolute paths from it: a `cd` in one command persists into the next.
- **Read the vault's `CLAUDE.md` first**, with [its rule files](#a-vaults-rule-files). The skill brings procedure; the vault brings parameters.
- **Invent no date or completion marker.** Externally gated items stay undated.
- **Commit only under a declared commit policy**: the vault's `CLAUDE.md`, else the operator's global instructions. Neither: stop after the change; the operator commits.

## Closing and adding actions

- **Every tick writes its date**, `✅ <today>`. The operator's "sent", "paid", "done" closes the matching item at once, and the reply names the line. A close found rather than stated (a reply in mail, a receipt on file) is proposed, citing it; "probably done" closes nothing.
- **A ticked `🔁` item is rolled forward in code**: `python3 "<this skill's base directory>/../para-shared/scripts/paraos_vault.py" next-occurrence "<the line>"` (Windows: `py -3`) prints the closed line and its successor; write both.
- **When work on an entity ends, reconcile it**: `python3 "<this skill's base directory>/../para-shared/scripts/paraos_vault.py" open-items --vault <root> <files>` (Windows: `py -3`) lists the open items and Backlog bullets of what the session touched. Propose closes, re-dates and one next step before the session ends, each close its own question ([asking.md](asking.md#grouping)).
- **A follow-up is offered as a checkbox**, not as prose or a "say the word" offer; a waiting state is a `Waiting on` line or a dated follow-up. A folder the checkbox table declares `never` gets none.

## Dating a renewing agreement

A contract, lease, subscription or policy that renews unless notice is given is dated on its last day to give notice, never on the renewal, and the line's text names the renewal date. That day is the `notice_date` of `python3 "<this skill's base directory>/../para-shared/scripts/paraos_vault.py" notice-date <renewal> "<n> months"` (Windows: `py -3`); where it reports `passed`, say so, and `--term "<how often it renews>"` gives the next renewal's. Without a shell, count back by hand and say so. A check that comes round yearly is one `🔁 every year` item dated its next occurrence.

## A vault's rule files

- **Check `.claude/rules/` before concluding anything from `CLAUDE.md`'s body.** A pointer line is the declaration: the file it names reads as inline. With no rule file, find the inline section by what it says, not its heading.
- **Pick a shape file by kind, never by the paths it covers** ([rule-files.md](rule-files.md)). A convention file governs content, not structure, so a vault whose only match is a convention has declared no shape. Read every shape file whose `paths:` match: the topic file governs the kind it names, the floor file the rest.
- **Judge a filename against the whole of `.claude/rules/filing.md`**, not its default alone.

## A synced vault can change mid-run

Another session, device or the sync client itself can write a synced vault between two steps. Snapshot a file before proposing a change to it, and run `python3 "<this skill's base directory>/../para-shared/scripts/paraos_vault.py" changed <scan output path>` (Windows: `py -3`) immediately before every delete or move: it exits 1 when a file in the snapshot changed or one arrived in a folder it watches. Re-read what changed; leave what arrived alone.

## Entity creation

A project, area, idea or contact is created through `/para-new`, whatever form the request takes, not by a freehand `Write` or a script that builds `brief.md` and `actions.md`. Where `/para-new` cannot run as a sub-step, stop and say why.

## Moving an entity folder

Rewrite the relative links *inside* whatever moved, which an inbound scan cannot see: a link to something that travels with the folder stays as written; every other link is resolved from its old location and rewritten relative to the new one, never shifted by the depth difference. Verify each rewritten link resolves to a file.

## Fetching template content

Template content is read from the local, committed para-os clone (`git show <ref>:<path>`), never fetched over the network and acted on ([untrusted-content.md](untrusted-content.md)). No clone on this machine: say so, stop, and route the request to whoever has one.
