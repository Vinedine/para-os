---
name: para-triage
description: Empty the current vault's triage/ folder - and any configured triage sources (mailboxes, sync scripts) - by classifying each item, proposing a destination or action, then executing after user confirmation. Use when user asks to "process triage", "clean up triage", "what's in triage", "empty the inbox", "check my email for anything to do", or types /para-triage.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content, mcp__google-workspace__search_drive_files, mcp__google-workspace__list_drive_items, mcp__google-workspace__get_drive_file_content
arg-hint: '[preview|apply|convert|table] [--test]'
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
| `convert` | **Unattended entry point.** Normalise formats only: run sync sources, convert Google-native files to real `.md` siblings, write the conversion ledger, report what arrived. No classify, no move, no file, no delete. Safe to run on a schedule indefinitely; deletes happen on the operator's next interactive run. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

### Step 1: Confirm vault context

**Resolve the vault root, then verify it** - the path the operator named, or `pwd` read before anything else in the session has moved the shell, never the current directory taken on trust (`operating-discipline.md`). Step 2's scan answers this: run it now (the call is shown there) and read its `vault` block - the library's root rule plus a `triage/` folder present. Where `root` is false, stop: `Not a vault root: <the path you checked>.` and, where `hint` names one, `Registered vault <name> is at <path>.` - **never run against that path until the operator names it**. `missing` says what the check found absent; an empty `triage/` alone is not a reason to stop, since Step 2's pulls write into it.

Read the vault's `CLAUDE.md` and its [rule files](../para-shared/operating-discipline.md#a-vaults-rule-files), and extract: the **filing rules** (the naming convention for source documents - quote the one you apply back verbatim in the proposal, so the user can sanity-check it), any **language** rules, any **do-not-add** rules, and whether the vault is on the [read-only iPad delivery](../para-shared/operating-discipline.md#the-read-only-ipad-delivery).

Also read the root `README.md`'s `## Operating model` section (Grep with `-A` context is enough). `CLAUDE.md` says how this vault files; the Operating model says what its business *is*, and it is the authority for the in/out call on connector items. If the README or the section is missing, skip silently.

**Where neither `CLAUDE.md` nor its rule files state a source-document naming convention**: propose destinations only, and ask the user to dictate the convention before any rename executes. Do not invent one, and do not silently borrow one from another vault.

### Step 2: Gather inputs

**Run the scan**, per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
python3 "<this skill's base directory>/scripts/triage_scan.py" --vault <root> > <scan output path>
```

**Exit codes**: 0 answered, an empty `triage/` included; 2 fall back to [references/scan.md](references/scan.md)'s by-hand procedure, [references/sources.md](references/sources.md) and [references/filing.md](references/filing.md); 3 `--vault` is not a vault root (Step 1's stop).

**`sources.rows[].plan`, from `references/sources.md`'s conditions, decides which triage sources actually run**: a `pull` or `run` row still executes for real here (a connector search, a fetch-script call, a sync script's `--write`) and its output then flows through the remaining steps like any loose file; `skip` and `lookup` rows do nothing. **Re-run the scan** after any `--write` or Google-native conversion has written into `triage/`, and again with `--threads <file>` once a local connector pull has a candidate thread list, so `threads[]` folds a fetched thread into a note already staged for it and reads its seen-ledger watermark. **Full field table: [references/scan.md](references/scan.md).**

**Then read `items.loose`** for the top-level entries (with their [collected copies](../para-shared/operating-discipline.md#the-read-only-ipad-delivery)): kind, size, a PDF's `.md` twin already folded onto it, `readme`, `duplicates`, `cross_vault`, `inbound`, and a mail note's parsed header wherever `note` is not null. `items.subdirectories` are **listed, never asked** ([references/approval.md](references/approval.md)) - an `_`-prefixed one flagged `handoff`.

`triage/` holds a `.gitkeep`; the scan already excludes it. It never holds a `README.md`: **never create one**, whatever a folder-placeholder convention elsewhere suggests, and propose deleting one the scan flags (`readme: true`) rather than filing it.

**Only now, check for emptiness.** `items.empty` true - the pulls above yielded nothing and `triage/` holds nothing but `.gitkeep` - respond `Nothing to triage in <the path you checked>.` and stop. A source declared but unreachable is not nothing: name it per the edge case below rather than reporting a clean run. `items.only_subdirectories` true: list them and stop with `Only subdirectories in triage/; nothing to file at top level. Subdirectories listed for your review.`.

### Steps 3 and 4: Inspect each file, then choose its destination

Read each loose file, weigh its scan-reported duplicates, cross-vault hits and orientation problems, then find its entity and build the convention-conform filename. **Full procedure: [references/filing.md](references/filing.md).**

### Steps 5 and 6: Propose, then approve item by item

Group the linked items, **then print the manifest before anything else in Step 5** - the count line (`N items, N questions (N grouped), N rounds.`), one line per question, then the subdirectories listed apart. It comes first on **every** path, the table paths included, and is skipped only below four questions, per [para-shared/asking.md](../para-shared/asking.md). Then ask **one `AskUserQuestion` per item or linked group**. **Full procedure, the action vocabulary, and the grouping and delete rules: [references/approval.md](references/approval.md).**

**On `preview`, `apply`, `convert`, `table`, or any run with no interactive operator, do not ask.** After the manifest, build the markdown proposal table instead - `| # | Source item | Action | Why | Destination |` - and gate it on a single "Reply **go** to execute, or tell me what to change." Same vocabulary minus **Create entity**, same follow-on edits, one approval instead of N. `preview` stops at the table; `apply` skips the gate. **Do not proceed on silence, on "ok", or on tangential replies.**

### Steps 7 to 9: Execute, update READMEs, re-render

Moves, deletes, rotations, connector writes, README follow-ons, and the optional `render.ps1` pass. **Full procedure: [references/execute.md](references/execute.md).**

### Step 10: Summarize

One line per category: N files moved (each linked to its new path), N deleted with the reason, N follow-on edits made (each file named), and whatever is left in `triage/`. **Name the deferrals too** - every item answered `Leave in triage`, `Note to triage` or `Leave thread`, and every amendment made through Other, per [para-shared/asking.md](../para-shared/asking.md).

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Every deletion is approved on its own** - its own question, or its own Delete row on the table path - never a verbal go-ahead alone.
- **Never ask a question nobody is there to answer.** On the no-ask paths of Step 5, a scheduled task or a subagent, and wherever it is unclear whether an operator is present, **fail toward the table**.
- **Never invent new top-level PARA folders** without asking. Sub-folders inside an existing entity are fine when the convention supports them (`sources/photos/`).
- **Don't touch `_*` prefixed subdirectories in triage** without explicit direction. Underscore-prefix means a handoff batch the maintainer is managing manually.
- **Never search Drive unscoped.** An exact-name query without a `drive_id` answers "No files found" while the document sits in the folder. That is a **false quiet**: triage reported clear while items accumulate. Always scope to the drive id declared in the vault's `drive` row; if no row is declared, say the drive is undeclared - never infer an id and never report "nothing found" from an unscoped query.
- **Never auto-delete a converted Google-native stub.** It gets its own delete question, or a Delete row on the table path, like anything else. Idempotency comes from the conversion ledger, not from deleting.
- **Mail is read-only.** Never send, reply, archive, or apply a label. Surface and draft only; the operator acts. The only writes the whole skill makes for a mailbox source are the local `triage/` note, the `actions.md` line, and the ledger.
- **Connector items land in `triage/` or `actions.md`, never straight into `projects/` or an entity folder**, **and never into a *different* vault** - a thread for elsewhere is **Dismiss (other vault)**, not a cross-vault write.
- **Fuzzy-match before creating.** Check existing contacts, projects, and open `actions.md` items before proposing a new action. If a thread bears on tracked work, **Update existing** rather than adding a duplicate.
- **One next step per thread, and flag fat files.** A thread never yields more than one new checkbox, and appending to a file already at 12+ open items gets the WIP flag in the proposal, pointing at `/para-deep-clean` for grooming.

## Edge cases

- **Vault declares triage sources but none are reachable**: file the loose files, and name each skipped source in the summary rather than reporting a clean run.

Per-file edge cases (locked PDFs, date mismatches, EXIF orientation, cross-vault files) are in [references/filing.md](references/filing.md); Drive and connector ones in [references/sources.md](references/sources.md).

## Related skills

- `/para-new` - creates the project, area, idea or contact a triaged file turns out to need. Triage files into entities that exist; this one makes the entity.
- `/para-deep-clean` - run it **after** this skill has emptied the loose-files queue, never before.
