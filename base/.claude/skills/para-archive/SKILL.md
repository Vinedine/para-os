---
name: para-archive
description: Archive a finished project, a retired idea, or an area the vault names an archive destination for, end-to-end - reconcile its open actions, validate its brief/actions files, optionally version-suffix it (projects only), route living-reference files to resources/, move it to archive/ and repoint every inbound link in the vault, then propose its Track record line and route its lessons. Use when a project has shipped or an idea is being shelved and the user asks to "archive this", "close out <name>", "wrap up <name>", "shelve <idea>", or types /para-archive <name>.
allowed-tools: Bash(python3 *), Bash(py *), Bash(git mv *), Bash(git rm *), Bash(mv *), Bash(mkdir *), Bash(rmdir *), Bash(pwd *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Edit, Write, AskUserQuestion
argument-hint: '<name> [preview|table] [--test]'
---

# Para archive

Closes out **one finished project, retired idea, or ended area**, leaving no dangling links: a project moves from `projects/<name>/` to `archive/projects/<name>/`, an idea from `resources/ideas/<name>/` to `archive/ideas/<name>/`, and where the vault's `CLAUDE.md` names another archive destination for its kind, there instead. An area archives only where one is named for its kind.

Do NOT invoke for a contact, an area with no named destination, or an idea becoming a project: that is a promotion, `/para-new promote <name>`.

## Arguments

The entity name is the one to three words of the argument that could name a folder or a `projects/<name>` / `resources/ideas/<name>` path, a leading `project`, `idea` or `on` dropped; the rest is an instruction for this run ([operating-discipline.md](../para-shared/operating-discipline.md#arguments)). Ask only where it matches none or several.

| Arg | Behavior |
|---|---|
| `<name>` | Full flow, Steps 0 to 9, pausing at each decision. |
| `<name> preview` | The analysis (open actions, file validation, inbound links) and the plan: the manifest of questions a live run would ask and the proposal, Step 9's included. NO changes. |
| `<name> table` | One proposal table, one `go` that approves no deletion or bucket move. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

Each decision (an open action's disposition, the version suffix, each Step 9 part) is its own question, per [para-shared/asking.md](../para-shared/asking.md).

### Step 0 - Scan

Run the plan call per [para-shared/scripts.md](../para-shared/scripts.md); it answers Steps 1 to 6:

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/archive_scan.py" --vault . --entity <name> [--destination <path>] [--today YYYY-MM-DD] [--route <file>]... > <scan output path>
```

Exit 0: answered, an unresolved or ambiguous entity included; exit 3: `--vault` is not a vault root.

### Step 1 - Confirm context and locate the entity

1. **The vault root is the `vault` block.** Where `root` is false, stop, naming the path checked and, from `hint`, the registered vault that holds it.
2. From the vault's `CLAUDE.md`, take its archive subfolders, any destination it names per kind, its Archive hygiene conventions and its "do not add" rules.
3. **`entity.status`**: `resolved`; `ambiguous`, ask which of `candidates`; `elsewhere`, already archived at `already_archived`, so run Steps 6 to 8 only, repairing its links; `unresolved`, list `this_vault`'s folders and which of `other_vaults` holds the name, and ask, never running against another vault until the operator names it. For an area, `destination.needs_vault_rule: true` means read the vault's destination for its kind and re-run with `--destination`. A non-null `lifecycle` is a staged entity: it archives into a home from `lifecycle.terminal_stages`, and Step 3 gates the move. The **kind** sets the source, the destination and whether Step 5 runs.
4. **Confirm it is done**: a project's deliverable shipped, an idea genuinely shelved, never live work. Where `gate` disagrees (an `open_dated` action, a `future_dated_lines` entry), say so in one line and ask **proceed or stop**, nothing else: a question of fact, with no recommendation. `status_line` alone is never the evidence. **Never offer a blanket disposition** such as "drop what's left": each open item is Step 2's question, once the gate says proceed.

### Steps 2 to 5 - Reconcile, validate, route, version

Settle each open action, validate the closed record, route survivors and living-reference files, and decide a project's version suffix: [references/reconcile.md](references/reconcile.md).

### Steps 6 to 8 - Scan links, execute, verify

Classify every inbound reference, move with `git mv`, rewrite the links inside what moved, then run the verify call and resolve every count it reports: [references/move.md](references/move.md).

### Step 9 - Close out

Once the verify call is clean: the Track record line, at most three lessons routed, and for a won deal the client's words: [references/close-out.md](references/close-out.md).

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** Specific to this skill:

- **Zero dangling links, in both directions.** The references to the entity and the links inside what moved are two scans; either left broken fails the run.
- **Never write a Stage or reason line yourself.** A move into a terminal stage waits until the operator has written both.
- **Never invent a lesson or a client's words.** A lesson is one the operator states or the brief records; a client's words are quoted from a file on record, or not recorded.
