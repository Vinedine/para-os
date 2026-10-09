---
name: para-triage
description: Empty the current vault's triage/ folder - and any configured triage sources (mailboxes, sync scripts) - by classifying each item, proposing a destination or action, then executing after user confirmation. Use when user asks to "process triage", "clean up triage", "what's in triage", "empty the inbox", "check my email for anything to do", or types /para-triage.
allowed-tools: Bash(python3 *), Bash(py *), Bash(node *), Bash(git rm *), Bash(mv *), Bash(mkdir *), Bash(test *), Bash(echo *), Bash(pwd *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content, mcp__google-workspace__get_gmail_attachment_content, mcp__google-workspace__search_drive_files, mcp__google-workspace__list_drive_items, mcp__google-workspace__get_drive_file_content
argument-hint: '[preview|apply|convert|table] [--test]'
---

# Triage

Processes every loose file in the current vault's `triage/` folder, plus any items pulled from the vault's configured triage sources (mailboxes, sync scripts). **Nothing is moved, renamed, or deleted until its own disposition has been put to the operator and approved** - one question per item, or per linked group, with the whole batch listed as a manifest first.

The vault's `CLAUDE.md`, read at runtime, supplies the naming convention, the PARA layout and the optional `## Triage sources` block; without that block the run is folder-only. Files already filed outside `triage/` are not re-sorted.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow: scan, classify, print the manifest, ask item by item, execute. |
| `preview` | Print the manifest, then stop after the proposal table. Do not ask, do not execute. |
| `apply` | Skip the approval step. Only when the user already approved a previous preview in this conversation. |
| `table` | One markdown proposal table, one `go`: the explicit escape from item-by-item questions. |
| `convert` | **Unattended entry point.** Run sync sources, convert Google-native files to `.md` siblings, write the conversion ledger, report what arrived. Nothing is classified, moved or deleted. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

### Step 1: Confirm vault context

**Resolve the vault root** (the path the operator named, or `pwd` before anything moved the shell) and verify it with Step 2's scan, run now. `vault.root` false (exit 3): stop with `Not a vault root: <the path you checked>.`, adding `Registered vault <name> is at <path>.` where `hint` names one, and never run against that path until the operator names it. An empty `triage/` is no reason to stop: Step 2's pulls write into it.

Read the vault's `CLAUDE.md` and its [rule files](../para-shared/operating-discipline.md#a-vaults-rule-files), quoting the naming convention you apply verbatim in the proposal, and the root `README.md`'s `## Operating model` where present: it decides whether a connector item is this vault's business. **Where no source-document naming convention is stated**, propose destinations only and ask the operator to dictate one before any rename; never invent one or borrow another vault's.

### Step 2: Gather inputs

**Run the scan**, per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/triage_scan.py" --vault <root>
```

It keeps its output outside the vault at `saved_to`, which every later re-check reads; where that is null, `save_error` says why: redirect the output to a file outside the vault. Exit 0 answers, an empty `triage/` included; 3 is Step 1's stop. **Fields: [references/scan.md](references/scan.md).**

**Each `sources.rows[].plan` decides whether that source runs**, per [references/sources.md](references/sources.md); what it pulls flows on as loose files. **Re-run the scan** after anything writes into `triage/`, and with `--threads <file>` once a local mailbox pull has its candidate threads: that folds each into a note already staged for it and counts a sent message's working days unanswered.

**Then read `items.loose`** and `items.subdirectories`. Subdirectories are **listed, never asked**. `triage/` never holds a `README.md`: propose deleting one the scan flags (`readme: true`).

**Only now, check for emptiness.** `items.empty` true: respond `Nothing to triage in <the path you checked>.`, naming any declared source that could not be read, and stop. `items.only_subdirectories` true: list them and stop with `Only subdirectories in triage/; nothing to file at top level. Subdirectories listed for your review.`

### Steps 3 and 4: Inspect each file, then choose its destination

Read each loose file, weigh the scan's duplicates and inbound links, then find its entity and build the convention-conform name: [references/filing.md](references/filing.md). A meeting record filed for an entity whose shape declares `Last touch` also proposes that entity's updates and a follow-up draft ([filing.md](references/filing.md#a-meeting-record)).

### Steps 5 and 6: Propose, then approve item by item

Group the linked items, **then print the manifest** as [para-shared/asking.md](../para-shared/asking.md) sets out: the count line (`N items, N questions (N grouped), N rounds.`, worded exactly so on the table paths too, where each question is a row), one line per question, then `items.subdirectories_line` as the scan printed it. Then ask **one `AskUserQuestion` per item or linked group**, from [references/approval.md](references/approval.md)'s vocabulary.

**On `preview`, `apply`, `table`, or any run with no interactive operator, do not ask**: after the manifest, build the markdown proposal table - `| # | Source item | Action | Why | Destination |` - gated on a single "Reply **go** to execute, or tell me what to change." Its `Action` column holds only [the table path's actions](references/approval.md#the-table-path), never **Create entity**: that item is **Leave in triage**, its Why naming the entity to create. Follow-on edits and any draft go under the table in full, never "as listed above". `preview` stops at the table; `apply` skips the gate. **Do not proceed on silence, on "ok", or on tangential replies.**

### Steps 7 and 8: Execute, update READMEs

Moves, deletes, connector writes and follow-on edits: [references/execute.md](references/execute.md).

### Step 9: Summarize

One line per category: files moved (each linked to its new path), deleted (with the reason), follow-on edits (each file named), each declared source skipped or unreachable, and what is left in `triage/`. **Name the deferrals too**: every `Leave in triage` or `Note to triage`, and every amendment made through Other.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** Specific to this skill:

- **Every deletion is approved on its own** - its own question, or its own Delete row on the table path - never a verbal go-ahead alone.
- **Never invent a top-level PARA folder** without asking. Sub-folders inside an existing entity are fine where the convention supports them (`sources/photos/`).
- **Never search Drive without the `drive` row's drive id**: an unscoped query can answer "No files found" while the document sits in the folder. With no `drive` row, say the drive is undeclared; never infer an id.
- **Mail is read-only** ([connectors.md](../para-shared/connectors.md)); a draft follows [para-shared/drafting.md](../para-shared/drafting.md) and is shown, never sent or saved. A mailbox source writes only the `triage/` note, the `actions.md` line or register row, and the ledgers.
- **Connector items land in `triage/`, `actions.md` or a register row**, never straight into an entity folder or another vault: that is **Dismiss (other vault)** or **Stage in other vault**.
- **A staged note whose `Content` line says the operator's own messages were not fetched names no reply as owed** (no action to answer the sender, no draft) unless a re-read at its source shows they have not answered ([references/filing.md](references/filing.md)).
- **Fuzzy-match before creating.** Check existing contacts, projects, ideas, register rows and open `actions.md` items first; a thread bearing on tracked work is **Update existing**, not a duplicate.
- **One next step per thread**: at most one new checkbox.
