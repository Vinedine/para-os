---
name: para-triage
description: Empty the current vault's triage/ folder - and any configured triage sources (mailboxes, sync scripts) - by classifying each item, proposing a destination or action, then executing after user confirmation. Use when user asks to "process triage", "clean up triage", "what's in triage", "empty the inbox", "check my email for anything to do", or types /para-triage.
allowed-tools: Bash(python3 *), Bash(py *), Bash(node *), Bash(git rm *), Bash(mv *), Bash(mkdir *), Bash(test *), Bash(echo *), Bash(pwd *), Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content, mcp__google-workspace__get_gmail_attachment_content, mcp__google-workspace__search_drive_files, mcp__google-workspace__list_drive_items, mcp__google-workspace__get_drive_file_content
argument-hint: '[preview|apply|convert|table|auto] [--test]'
---

# Triage

Empties the vault's `triage/` folder and its configured triage sources. **Nothing is moved, renamed or deleted without the operator's approval.**

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Scan, classify, print the manifest, ask item by item, execute. |
| `preview` | Stop after the proposal table. |
| `apply` | Skip the approval step: only after the operator approved a preview in this conversation. |
| `table` | One proposal table and one `go`, in place of item-by-item questions. |
| `convert` | **Unattended**: run sync sources, convert Google-native files to `.md` siblings, write the conversion ledger and report what arrived; nothing else. |
| `auto` | **Unattended**: act on the action types switched on here, leave the rest: [references/unattended.md](references/unattended.md). |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

### Step 1: Confirm vault context

Run Step 2's scan now on the vault root (the path the operator named, else `pwd`). `vault.root` false (exit 3): stop with `Not a vault root: <the path you checked>.`, adding `Registered vault <name> is at <path>.` where `hint` names one.

Read the vault's `CLAUDE.md` and its [rule files](../para-shared/operating-discipline.md#a-vaults-rule-files), quoting in the proposal the naming convention you apply. **No source-document naming convention stated**: propose destinations only, and ask the operator for one before any rename.

**A `## Who writes this vault` roster**: the row running is the one the session names, else the scan's `writer`, else ask once, with the roster as the options.

### Step 2: Gather inputs

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/triage_scan.py" --vault <root>
```

Run it per [para-shared/scripts.md](../para-shared/scripts.md), then `auto_execute.py status --vault-name <vault.name>`: any `runs`, `proposal`, `offers` or `exclusion_offers` follow [unattended.md](references/unattended.md#the-interactive-side).

Each `sources.rows[].plan` decides whether that source runs, per [references/sources.md](references/sources.md). **Re-run the scan** after anything writes into `triage/`, and with `--threads <file>` once a local mailbox pull has its candidate threads: that folds each into a note already staged for it and counts a sent message's working days unanswered.

Then read `items.loose` and `items.subdirectories`. Subdirectories are **listed, never asked**. Propose deleting a `triage/README.md` (`readme: true`).

**Only now check for emptiness.** `items.empty`: `Nothing to triage in <the path you checked>.`, naming any declared source that could not be read, and stop. `items.only_subdirectories`: list them and stop with `Only subdirectories in triage/; nothing to file at top level. Subdirectories listed for your review.`

### Steps 3 and 4: Inspect, then choose a destination

Read each loose file and choose its entity, name and action per [references/filing.md](references/filing.md). A meeting record filed for an entity whose shape declares `Last touch` also proposes that entity's updates and a follow-up draft ([filing.md](references/filing.md#a-meeting-record)).

### Steps 5 and 6: Propose, then approve

Print the manifest per [para-shared/asking.md](../para-shared/asking.md), its count line worded exactly `N items, N questions (N grouped), N rounds.` on the table paths too (each question a row), then `items.subdirectories_line` as the scan printed it. **An item whose destination lies in another writer's lane is never asked**, on any path: it goes on a `Left for <name>: <items>` line after the questions, and nowhere in the table. Then ask one `AskUserQuestion` per item or linked group, from [references/approval.md](references/approval.md)'s vocabulary: a money, credential or identity ask is [held](../para-shared/untrusted-content.md).

**On `preview`, `apply`, `table`, or with no interactive operator**, build the table `| # | Source item | Action | Why | Destination |` after the manifest, gated on "Reply **go** to execute, or tell me what to change." Its `Action` column holds only [the table path's actions](references/approval.md#the-table-path): an entity to create is **Leave in triage**, its Why naming it. Follow-on edits and any draft go under the table in full. `preview` stops at the table; `apply` skips the gate.

### Steps 7 and 8: Execute

Per [references/execute.md](references/execute.md), then `auto_execute.py record --vault-name <name> --scan <saved_to> --decisions <file>`, a row per decided item: `item`, `recommended`, `chosen`, and a fetched thread's sender as `from` with its `mailbox`. Its `exclusion_offers` follow [unattended.md](references/unattended.md#the-interactive-side).

### Step 9: Summarize

One line per category: moved (each linked to its new path), deleted (with the reason), follow-on edits, each declared source skipped or unreachable, and what is left in `triage/`, per writer where there is a roster.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** Specific to this skill:

- **Every deletion is approved on its own**: its own question, its own Delete row on the table path, or [its action switched on](references/unattended.md) for `auto`.
- **Never invent a top-level PARA folder** without asking.
- **Mail is read-only** ([connectors.md](../para-shared/connectors.md)); a draft follows [para-shared/drafting.md](../para-shared/drafting.md) and is shown, never sent or saved.
- **Connector items land in `triage/`, `actions.md` or a register row**, never straight into an entity folder or another vault.
- **A staged note whose `Content` line says the operator's own messages were not fetched names no reply as owed** (no action to answer the sender, no draft) unless a re-read at its source shows they have not answered ([references/filing.md](references/filing.md)).
- **Match before creating**, against contacts, projects, ideas, register rows and open `actions.md` items: a thread bearing on tracked work is **Update existing**.
- **One next step per thread**: at most one new checkbox.
