---
name: para-triage
description: Empty the current vault's triage/ folder - and any configured triage sources (mailboxes, sync scripts) - by classifying each item, proposing a destination or action, then executing after user confirmation. Use when user asks to "process triage", "clean up triage", "empty the inbox", "check my email for anything to do", or types /para-triage.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content, mcp__google-workspace__search_drive_files, mcp__google-workspace__list_drive_items, mcp__google-workspace__get_drive_file_content
arg-hint: '[preview|apply|convert|table]'
---

# Triage

Processes every loose file in the current vault's `triage/` folder, plus any items pulled from the vault's configured triage sources (mailboxes, sync scripts). **Nothing is moved, renamed, or deleted until its own disposition has been put to the operator and approved** - one question per item, or per linked group, with the whole batch listed as a manifest first.

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime for the naming convention, the PARA layout, any iPad-rendering toolchain (`flip.ps1` / `render.ps1`), and the optional `## Triage sources` block; vaults without that block are folder-only. No vault-specific paths or connectors are hardcoded.

Do NOT invoke for files outside `triage/`. Files already filed are stable; don't re-sort them.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow: scan, classify, print the manifest, ask item by item, execute. |
| `preview` | Print the manifest, then stop after the proposal table. Do not ask, do not execute. |
| `apply` | Skip the approval step entirely. Use only when the user has already approved a previous preview in this conversation. |
| `table` | The batch proposal flow: one markdown proposal table, one `go`. The explicit escape from item-by-item questions, for a batch an operator would rather read than click through. |
| `convert` | **Unattended entry point.** Normalise formats only: run sync sources, convert Google-native files to real `.md` siblings, write the conversion ledger, report what arrived. No classify, no move, no file, no delete. Filing is judgment and moving or deleting is structural, so an unattended run is a strictly narrower job than the interactive one - not the same job with the prompts turned off. Safe to run on a schedule indefinitely; deletes happen on the operator's next interactive run. `triage/` does not empty on such a run, which is correct: it exists to hold unprocessed items. |

## Procedure

### Step 1: Confirm vault context

**Resolve the vault root, then verify it** - the path the operator named, or `pwd` read before anything else in the session has moved the shell, never the current directory taken on trust (`operating-discipline.md`) - by checking for `triage/` and at least one of `projects/` `areas/` `archive/`. If it is not one, respond `Not a vault root: <the path you checked>.` and stop. **That is this step's only job**; an empty `triage/` is not a reason to stop, since Step 2's sync sources write into it.

Read the vault's `CLAUDE.md` and extract: the **filing rules** (the per-folder naming convention for source documents - quote it back verbatim in the proposal, so the user can sanity-check it), any **language** rules, any **do-not-add** rules, and whether the vault uses the **flip/render** workflow (`flip.ps1`, `render.ps1`, `render.mjs` in the vault root).

Also read the root `README.md`'s `## Operating model` section (Grep with `-A` context is enough). `CLAUDE.md` says how this vault files; the Operating model says what its business *is*, and it is the authority for the in/out call on connector items. If the README or the section is missing, skip silently.

**If `CLAUDE.md` exists but has no source-document naming convention** (action- or markdown-focused vaults that don't deal with PDFs at scale): stop and ask the user to dictate the convention before any renames execute. Do not invent one, and do not silently borrow one from another vault.

### Step 2: Gather inputs

**First, pull configured triage sources** if the vault's CLAUDE.md has a `## Triage sources` block. **Full protocol: [references/sources.md](references/sources.md)** - sync scripts, mailbox connectors, the Drive lookup and Google-native conversion, and both ledgers. Sync scripts write into `triage/` and their output then files like any loose file; connectors write nothing and yield their own dispositions in Step 5. No block means skip this entirely.

**Then list loose files.** Glob `triage/*` for top-level entries. Also note subdirectories with Glob `triage/*/` - list them but **do not recurse**. They are intentional sub-batches and get flagged as "subdirectory - needs separate review" rather than blindly flattened.

`triage/` holds a `.gitkeep` so the empty folder survives in git; ignore it. It never holds a `README.md` - every file here is by definition unprocessed, so a permanent one is indistinguishable from a real item and would inflate the loose-file count on every future run. **Never create one**, whatever a folder-placeholder convention elsewhere in the vault suggests; if you find one left by an older skeleton, propose deleting it rather than filing it.

**Only now, check for emptiness.** If the source pull yielded nothing - or no sources are declared - and `triage/` holds nothing but `.gitkeep`, respond `Nothing to triage in <the path you checked>.` and stop. A source declared but unreachable is not nothing: name it per the edge case below rather than reporting a clean run.

If `triage/` holds only subdirectories, list them and stop with `Only subdirectories in triage/; nothing to file at top level. Subdirectories listed for your review.`.

### Steps 3 and 4: Inspect each file, then choose its destination

Read each loose file, check it against the rest of the vault for duplicates and orientation problems, then find its entity and build the convention-conform filename. **Full procedure: [references/filing.md](references/filing.md).**

### Steps 5 and 6: Propose, then approve item by item

Group the linked items, print the manifest, then ask **one `AskUserQuestion` per item or linked group**, per [para-shared/asking.md](../para-shared/asking.md). **Full procedure, the action vocabulary, and the grouping and delete rules: [references/approval.md](references/approval.md).**

**On `preview`, `apply`, `convert`, `table`, or any run with no interactive operator, do not ask.** Build the markdown proposal table instead - `| # | Source item | Action | Why | Destination |` - and gate it on a single "Reply **go** to execute, or tell me what to change." Same vocabulary, same follow-on edits, one approval instead of N. `preview` prints the manifest first and stops at the table; `apply` skips the gate. **Do not proceed on silence, on "ok", or on tangential replies.**

### Steps 7 to 9: Execute, update READMEs, re-render

Moves, deletes, rotations, connector writes, README follow-ons, and the optional `render.ps1` pass. **Full procedure: [references/execute.md](references/execute.md).**

### Step 10: Summarize

One line per category: N files moved (each linked to its new path), N deleted with the reason, N READMEs updated, and whatever is left in `triage/`. **Name the deferrals too** - every item answered `Leave in triage`, `Note to triage` or `Leave thread`, and every amendment made through Other, per [para-shared/asking.md](../para-shared/asking.md).

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Every deletion is approved on its own** - its own question, or its own Delete row on the table path - never a verbal go-ahead alone.
- **Never ask a question nobody is there to answer.** On the no-ask paths of Step 5, a scheduled task or a subagent, and wherever it is unclear whether an operator is present, **fail toward the table**.
- **Never invent new top-level PARA folders** without asking. Sub-folders inside an existing entity are fine when the convention supports them (`sources/photos/`).
- **Don't touch `_*` prefixed subdirectories in triage** without explicit direction. Underscore-prefix means a handoff batch the maintainer is managing manually.
- **Never search Drive unscoped.** An exact-name query without a `drive_id` answers "No files found" while the document sits in the folder. That is a **false quiet**: on an unattended run the scanner reports triage clear while items accumulate, which is the exact failure a scanner exists to prevent. Always scope to the drive id declared in the vault's `drive` row; if no row is declared, say the drive is undeclared - never infer an id and never report "nothing found" from an unscoped query.
- **Never auto-delete a converted Google-native stub.** It gets its own delete question, or a Delete row on the table path, like anything else. Idempotency comes from the conversion ledger, not from deleting.
- **Mail is read-only.** Never send, reply, archive, or apply a label. Surface and draft only; the operator acts. The only writes the whole skill makes for a mailbox source are the local `triage/` note, the `actions.md` line, and the ledger.
- **Connector items land in `triage/` or `actions.md`, never straight into `projects/` or an entity folder** (a mis-routed email must stay cheap to fix), **and never into a *different* vault** - a thread for elsewhere is **Dismiss (other vault)**, not a cross-vault write.
- **Fuzzy-match before creating.** Check existing contacts, projects, and open `actions.md` items before proposing a new action. If a thread bears on tracked work, **Update existing** rather than adding a duplicate - an active vault already tracks most of what its mail is about.
- **One next step per thread, and flag fat files.** A thread never yields more than one new checkbox, and appending to a file already at 12+ open items gets the WIP flag in the proposal, pointing at `/para-deep-clean` for grooming. Action inflation is the failure `/para-daily-brief`'s counts die of; triage is where most of it enters.

## Edge cases

- **Vault has no CLAUDE.md** (or no filing rules section): propose file destinations only, and ask the user to dictate the naming convention before any renames execute. A question cannot carry a filename the vault has no rule for.
- **Vault declares triage sources but none are reachable**: file the loose files, and name each skipped source in the summary rather than reporting a clean run.

Per-file edge cases (locked PDFs, date mismatches, EXIF orientation, cross-vault files) are in [references/filing.md](references/filing.md); Drive and connector ones in [references/sources.md](references/sources.md).

## Related skills

- `/para-new` - creates the project, area, idea or contact a triaged file turns out to need. Triage files into entities that exist; this one makes the entity.
- `/para-deep-clean` - run it **after** this skill has emptied the loose-files queue, never before.
