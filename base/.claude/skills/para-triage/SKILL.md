---
name: para-triage
description: Empty the current vault's triage/ folder - and any configured triage sources (mailboxes, sync scripts) - by classifying each item, proposing a destination or action, then executing after user confirmation. Use when user asks to "process triage", "clean up triage", "what's in triage", "empty the inbox", "check my email for anything to do", or types /para-triage.
allowed-tools: Bash(python3 *), Bash(py *), Bash(node *), Bash(git rm *), Bash(mv *), Bash(mkdir *), Bash(test *), Bash(echo *), Bash(pwd *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content, mcp__google-workspace__get_gmail_attachment_content, mcp__google-workspace__search_drive_files, mcp__google-workspace__list_drive_items, mcp__google-workspace__get_drive_file_content
argument-hint: '[preview|apply|convert|table] [--test]'
---

# Triage

Processes every loose file in the current vault's `triage/` folder, plus any items pulled from the vault's configured triage sources (mailboxes, sync scripts). **Nothing is moved, renamed, or deleted until its own disposition has been put to the operator and approved** - one question per item, or per linked group, with the whole batch listed as a manifest first.

**This skill is vault-agnostic.** The vault's `CLAUDE.md`, read at runtime, supplies the naming convention, the PARA layout, and the optional `## Triage sources` block; a vault without that block is folder-only.

Do NOT invoke for files outside `triage/`. Files already filed are stable; don't re-sort them.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow: scan, classify, print the manifest, ask item by item, execute. |
| `preview` | Print the manifest, then stop after the proposal table. Do not ask, do not execute. |
| `apply` | Skip the approval step. Only when the user already approved a previous preview in this conversation. |
| `table` | One markdown proposal table, one `go`: the explicit escape from item-by-item questions. |
| `convert` | **Unattended entry point.** Normalise formats only: run sync sources, convert Google-native files to real `.md` siblings, write the conversion ledger, report what arrived. No classify, move, file or delete, so it is safe on a schedule; deletes wait for the next interactive run. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

### Step 1: Confirm vault context

**Resolve the vault root** (the path the operator named, or `pwd` before anything moved the shell, per `operating-discipline.md`) and verify it with Step 2's scan, run now. `vault.root` false (exit 3): stop with `Not a vault root: <the path you checked>.`, adding `Registered vault <name> is at <path>.` where `hint` names one, and **never run against that path until the operator names it**. An empty `triage/` is no reason to stop: Step 2's pulls write into it.

Read the vault's `CLAUDE.md` and its [rule files](../para-shared/operating-discipline.md#a-vaults-rule-files) (filing, language and do-not-add rules; quote the naming convention you apply back verbatim in the proposal). Also read the root `README.md`'s `## Operating model` section, skipping silently if absent: it says what the business *is*, and decides the in/out call on connector items.

**Where no source-document naming convention is stated**, propose destinations only and ask the user to dictate the convention before any rename executes. Never invent one or borrow another vault's.

### Step 2: Gather inputs

**Run the scan**, per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/triage_scan.py" --vault <root>
```

The scan keeps its own copy outside the vault and names it in `saved_to`: that path is the scan output every later re-check reads. Where `saved_to` is null, `save_error` says why; redirect the output to a file outside the vault instead.

**Exit codes**: 0 answered, an empty `triage/` included; 2 fall back to [references/scan.md](references/scan.md)'s by-hand procedure, [references/sources.md](references/sources.md) and [references/filing.md](references/filing.md); 3 not a vault root (Step 1's stop). **Field table: [references/scan.md](references/scan.md).**

**Each `sources.rows[].plan` decides whether that source runs**: a `pull` or `run` row executes here per [references/sources.md](references/sources.md), its output then flowing on like any loose file, and a `sent` row runs its sent-mail pass alone; `skip` and `lookup` rows pull nothing. **Re-run the scan** after anything writes into `triage/`, and with `--threads <file>` once a local connector pull has its candidate threads, so each folds into a note already staged for it and carries its seen-ledger watermark and, where the operator wrote last, its working days without a reply.

**Then read `items.loose`** and `items.subdirectories`. Subdirectories are **listed, never asked** ([references/approval.md](references/approval.md)). `triage/` never holds a `README.md`: **never create one**, and propose deleting one the scan flags (`readme: true`) rather than filing it.

**Only now, check for emptiness.** `items.empty` true: respond `Nothing to triage in <the path you checked>.` and stop. A source declared but unreachable is not nothing: name it (Edge cases, below). `items.only_subdirectories` true: list them and stop with `Only subdirectories in triage/; nothing to file at top level. Subdirectories listed for your review.`

### Steps 3 and 4: Inspect each file, then choose its destination

Read each loose file, weigh the scan's duplicates, cross-vault hits and orientation problems, then find its entity and build the convention-conform filename. **Full procedure: [references/filing.md](references/filing.md).** A meeting record filed for an entity whose shape declares `Last touch` also proposes that entity's updates and a follow-up draft: [references/after-a-meeting.md](references/after-a-meeting.md).

### Steps 5 and 6: Propose, then approve item by item

Group the linked items, **then print the manifest**, when and where [para-shared/asking.md](../para-shared/asking.md) says: the count line (`N items, N questions (N grouped), N rounds.`, worded exactly so on the table paths too, where each question is a row), one line per question, then `items.subdirectories_line` as the scan printed it. Then ask **one `AskUserQuestion` per item or linked group**. **Vocabulary, grouping and delete rules: [references/approval.md](references/approval.md).**

**On `preview`, `apply`, `convert`, `table`, or any run with no interactive operator, do not ask.** `convert` builds no table: it reports what arrived and stops. On the others, after the manifest, build the markdown proposal table - `| # | Source item | Action | Why | Destination |` - gated on a single "Reply **go** to execute, or tell me what to change." Its `Action` column holds only [the table path's actions](references/approval.md#the-table-path), never **Create entity**: that item is **Leave in triage**, its Why naming the entity to create. The follow-on edits and any draft go under the table in full, in the same message, never "as listed above". `preview` stops at the table; `apply` skips the gate. **Do not proceed on silence, on "ok", or on tangential replies.**

### Steps 7 and 8: Execute, update READMEs

Moves, deletes, rotations, connector writes, and README follow-ons. **Full procedure: [references/execute.md](references/execute.md).**

### Step 9: Summarize

One line per category: N files moved (each linked to its new path), N deleted with the reason, N follow-on edits (each file named), and what is left in `triage/`. **Name the deferrals too**: every `Leave in triage` or `Note to triage`, and every amendment made through Other, per [para-shared/asking.md](../para-shared/asking.md).

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** Specific to this skill:

- **Every deletion is approved on its own** - its own question, or its own Delete row on the table path - never a verbal go-ahead alone.
- **Never ask a question nobody is there to answer.** On the no-ask paths, a scheduled task or a subagent, and wherever it is unclear whether an operator is present, **fail toward the table**.
- **Never invent new top-level PARA folders** without asking. Sub-folders inside an existing entity are fine where the convention supports them (`sources/photos/`).
- **Don't touch `_*` prefixed subdirectories in triage** without explicit direction: they are handoff batches the maintainer manages by hand.
- **Never search Drive unscoped.** A query without the `drive_id` from the vault's `drive` row can answer "No files found" while the document sits in the folder: a **false quiet**. With no `drive` row, say the drive is undeclared. Never infer an id, and never report "nothing found" from an unscoped query.
- **Never auto-delete a converted Google-native stub.** It gets its own delete question, or Delete row, like anything else. Idempotency comes from the conversion ledger.
- **Mail is read-only.** Never send, reply, archive, or apply a label; surface and draft only, any draft per [para-shared/drafting.md](../para-shared/drafting.md). The only writes for a mailbox source are the local `triage/` note, the `actions.md` line or register row, and the ledger.
- **Connector items land in `triage/`, `actions.md` or a register row, never straight into `projects/` or an entity folder, and never into a *different* vault**: a thread for elsewhere is **Dismiss (other vault)**, or for a staged note whose vault does not read its mailbox, **Stage in other vault** ([approval.md](references/approval.md)).
- **A staged note whose `Content` line says the operator's own messages were not fetched names no reply as owed** (no action to answer the sender, no draft) unless a re-read at its source shows they have not answered ([references/filing.md](references/filing.md)).
- **Fuzzy-match before creating.** Check existing contacts, projects, register rows and open `actions.md` items first; a thread bearing on tracked work is **Update existing**, not a duplicate.
- **One next step per thread.** A thread yields at most one new checkbox, and a file at the cap (`over_threshold`) gets [approval.md](references/approval.md)'s flag.

## Edge cases

- **Vault declares triage sources but none are reachable**: file the loose files, and name each skipped source in the summary rather than reporting a clean run.

Per-file edge cases are in [references/filing.md](references/filing.md); Drive and connector ones in [references/sources.md](references/sources.md).

## Related skills

- `/para-new` - creates the project, area, idea or contact a triaged file turns out to need.
- `/para-deep-clean` - run it **after** this skill has emptied the loose-files queue, never before.
