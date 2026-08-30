---
name: para-triage
description: Empty the current vault's triage/ folder - and any configured triage sources (mailboxes, sync scripts) - by classifying each item, proposing a destination or action, then executing after user confirmation. Use when user asks to "process triage", "clean up triage", "empty the inbox", "check my email for anything to do", or types /para-triage.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content, mcp__google-workspace__search_drive_files, mcp__google-workspace__list_drive_items, mcp__google-workspace__get_drive_file_content
arg-hint: '[preview|apply|convert]'
---

# Triage

Processes every loose file in the current vault's `triage/` folder, plus any items pulled from the vault's configured triage sources (mailboxes, sync scripts). **Nothing is moved, renamed, or deleted until the full proposal table has been shown and approved.**

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime for the naming convention, the PARA layout, any iPad-rendering toolchain (`flip.ps1` / `render.ps1`), and the optional `## Triage sources` block; vaults without that block are folder-only. No vault-specific paths or connectors are hardcoded.

Do NOT invoke for files outside `triage/`. Files already filed are stable; don't re-sort them.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow: scan, show proposal table, wait for approval, execute. |
| `preview` | Stop after the table. Do not prompt for approval, do not execute. |
| `apply` | Skip the confirmation step. Use only when the user has already approved a previous preview in this conversation. |
| `convert` | **Unattended entry point.** Normalise formats only: run sync sources, convert Google-native files to real `.md` siblings, write the conversion ledger, report what arrived. No classify, no move, no file, no delete. Filing is judgment and moving or deleting is structural, so an unattended run is a strictly narrower job than the interactive one - not the same job with the prompts turned off. Safe to run on a schedule indefinitely; deletes happen on the operator's next interactive run. `triage/` does not empty on such a run, which is correct: it exists to hold unprocessed items. |

## Procedure

### Step 1: Confirm vault context

Verify the cwd is a vault root by checking for `triage/` and at least one of `projects/` `areas/` `archive/`. If `triage/` is missing or empty, respond `Nothing to triage in <cwd>.` and stop.

Read the vault's `CLAUDE.md` and extract: the **filing rules** (the per-folder naming convention for source documents - quote it back verbatim when you build the table, so the user can sanity-check it), any **language** rules, any **do-not-add** rules, and whether the vault uses the **flip/render** workflow (`flip.ps1`, `render.ps1`, `render.mjs` in the vault root).

Also read the root `README.md`'s `## Operating model` section (Grep with `-A` context is enough). `CLAUDE.md` says how this vault files; the Operating model says what its business *is*, and it is the authority for the in/out call on connector items. If the README or the section is missing, skip silently.

**If `CLAUDE.md` exists but has no source-document naming convention** (action- or markdown-focused vaults that don't deal with PDFs at scale): stop and ask the user to dictate the convention before any renames execute. Do not invent one, and do not silently borrow one from another vault.

### Step 2: Gather inputs

**First, pull configured triage sources** if the vault's CLAUDE.md has a `## Triage sources` block. **Full protocol: [references/sources.md](references/sources.md)** - sync scripts, mailbox connectors, the Drive lookup and Google-native conversion, and both ledgers. Sync scripts write into `triage/` and their output then files like any loose file; connectors write nothing and yield their own proposal rows in Step 5. No block means skip this entirely.

**Then list loose files.** Glob `triage/*` for top-level entries. Also note subdirectories with Glob `triage/*/` - list them but **do not recurse**. They are intentional sub-batches and get flagged as "subdirectory - needs separate review" rather than blindly flattened.

`triage/` holds a `.gitkeep` so the empty folder survives in git; ignore it. It never holds a `README.md` - every file here is by definition unprocessed, so a permanent one is indistinguishable from a real item and would inflate the loose-file count on every future run. **Never create one**, whatever a folder-placeholder convention elsewhere in the vault suggests; if you find one left by an older skeleton, propose deleting it rather than filing it.

If `triage/` holds only subdirectories, list them and stop with `Only subdirectories in triage/; nothing to file at top level. Subdirectories listed for your review.`.

### Steps 3 and 4: Inspect each file, then choose its destination

Read each loose file, check it against the rest of the vault for duplicates and orientation problems, then find its entity and build the convention-conform filename. **Full procedure: [references/filing.md](references/filing.md).**

### Step 5: Build the proposal table

One markdown table, every item in it - loose files and connector threads alike:

| # | Source item | Action | Why | Destination |
|---|---|---|---|---|

Actions for **loose files**: **Move + rename** (most common) · **Move + rename + rotate Nx** · **Delete** (byte-identical duplicate; cite the existing path and the MD5 match) · **Delete (redundant scan)** (content overlap, not a hash match - always confirm) · **Subdirectory - needs separate review** · **Leave in triage** (no good destination; explain what's missing).

Actions for **connector threads** (the `Source item` cell holds subject, sender, date):

- **Update existing** - the thread bears on something the vault already tracks. Annotate the existing `actions.md` line or contact/project note; do NOT add a duplicate. **In an active vault this is the default** - check for an existing item before reaching for Add action.
- **Add action** - a genuinely new to-do with no tracked home. **At most one next step per thread**, the immediately actionable move, never a decomposition into several checkboxes (the actionable-frontier rule; later steps earn their checkbox when they become the frontier). If the destination file already holds 12 or more open items, say so in the Why cell (`file at N open - groom?`) instead of silently growing it. **Never in notes-only vaults.**
- **Note to triage** - worth keeping; filed on a later pass, never straight into `projects/`.
- **Dismiss (noise)** - never action-worthy in any vault (newsletter, notification, bot, promo); ledgered so it does not resurface. Destination "(ledger only)".
- **Dismiss (other vault)** - real correspondence belonging to a different vault; **not** ledgered. Destination "(belongs to \<vault\>)".

After the table, list any **follow-on edits** to README files (new rows, new source-list entries, new sub-sections), naming which README and where in it.

### Step 6: Wait for approval

If arg is `preview`: stop here, don't prompt.

Otherwise ask "Reply **go** to execute, or tell me what to change." **Do not proceed on silence, on "ok", or on tangential replies.** "Go", "yes execute", "do it", "apply" are clear; anything else gets clarified. On an amendment, apply it, re-show only the changed rows, and ask again.

### Steps 7 to 9: Execute, update READMEs, re-render

Moves, deletes, rotations, connector writes, README follow-ons, and the optional `render.ps1` pass. **Full procedure: [references/execute.md](references/execute.md).**

### Step 10: Summarize

One line per category: N files moved (each linked to its new path), N deleted with the reason, N READMEs updated, and whatever is left in `triage/`.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Every deletion is a Delete row in the approved table**, never a verbal go-ahead alone.
- **Never invent new top-level PARA folders** without asking. Sub-folders inside an existing entity are fine when the convention supports them (`sources/photos/`).
- **Don't touch `_*` prefixed subdirectories in triage** without explicit direction. Underscore-prefix means a handoff batch the maintainer is managing manually.
- **Never search Drive unscoped.** An exact-name query without a `drive_id` answers "No files found" while the document sits in the folder. That is a **false quiet**: on an unattended run the scanner reports triage clear while items accumulate, which is the exact failure a scanner exists to prevent. Always scope to the drive id declared in the vault's `drive` row; if no row is declared, say the drive is undeclared - never infer an id and never report "nothing found" from an unscoped query.
- **Never auto-delete a converted Google-native stub.** It gets a Delete row in the table like anything else. Idempotency comes from the conversion ledger, not from deleting.
- **Mail is read-only.** Never send, reply, archive, or apply a label. Surface and draft only; the operator acts. The only writes the whole skill makes for a mailbox source are the local `triage/` note, the `actions.md` line, and the ledger.
- **Connector items land in `triage/` or `actions.md`, never straight into `projects/` or an entity folder** (a mis-routed email must stay cheap to fix), **and never into a *different* vault** - a thread for elsewhere is **Dismiss (other vault)**, not a cross-vault write.
- **Fuzzy-match before creating.** Check existing contacts, projects, and open `actions.md` items before proposing a new action. If a thread bears on tracked work, **Update existing** rather than adding a duplicate - an active vault already tracks most of what its mail is about.
- **One next step per thread, and flag fat files.** A thread never yields more than one new checkbox, and appending to a file already at 12+ open items gets the WIP flag in the proposal, pointing at `/para-deep-clean` for grooming. Action inflation is the failure `/para-daily-brief`'s counts die of; triage is where most of it enters.

## Edge cases

- **Vault has no CLAUDE.md** (or no filing rules section): show the proposal table with file destinations only, and ask the user to dictate the naming convention before any renames execute.
- **Vault declares triage sources but none are reachable**: file the loose files, and name each skipped source in the summary rather than reporting a clean run.

Per-file edge cases (locked PDFs, date mismatches, EXIF orientation, cross-vault files) are in [references/filing.md](references/filing.md); Drive and connector ones in [references/sources.md](references/sources.md).

## Related skills

- `/para-new` - creates the project, area, idea or contact a triaged file turns out to need. Triage files into entities that exist; this one makes the entity.
- `/para-deep-clean` - run it **after** this skill has emptied the loose-files queue, never before.
