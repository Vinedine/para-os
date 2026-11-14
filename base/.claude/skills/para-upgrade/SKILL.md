---
name: para-upgrade
description: Bring a vault in line with a newer para-os revision - compares every file the kit owns with a para-os clone at an explicit ref and re-copies on approval, the fixed core among them, lists what the vault's own CLAUDE.md repeats from the kit, proposes deleting the files the kit retired, applies the content changes the changelog asks for, and adopts a named add-on. Use when the user wants the vault on a newer para-os revision or an add-on added ("upgrade the vault", "is this vault on the latest structure", "add the sales module"), or types /para-upgrade.
allowed-tools: Bash(python3 *), Bash(py *), Bash(git -C * fetch *), Bash(git rm *), Glob, Grep, Read, Edit, Write
argument-hint: '[--ref <git-ref>] [--clone <path>] [--add <name>] [audit] [--test]'
---
<!-- reviewed with: claude-opus-5-5 -->

# Para upgrade

Aligns one vault to a para-os revision: it changes the kit's files in the vault, where `/para-deep-clean` holds the vault to the rules it has. When both are due, run this one first.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow against `origin/stable` |
| `--ref <git-ref>` | Read the kit at this branch, tag or commit. A bare positional ref (`/para-upgrade feat/x`), or one after a qualifier word (`local feat/x`), is the same. |
| `--clone <path>` | Read this para-os clone instead of the default one, per [para-shared/scripts.md](../para-shared/scripts.md) |
| `--add <name>` | Also adopt `addons/<name>/`, or one named in words: before Step 5, run its README's Setup from the clone, each step on its own yes. |
| `audit` | Read-only: report the plan and change nothing |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |
| any other `--` argument | Stops the run, `audit` or not: name it and show this table. Never read as a ref, bare or not. |

## Preconditions

1. **A local para-os clone**, per [para-shared/scripts.md](../para-shared/scripts.md); with none (the scan's exit 6), ask for its path. Run `git -C <clone> fetch origin` first.
2. **An undo path, named before the first write**: git, the drive's version history, or none, which needs the operator's explicit go-ahead. Name any uncommitted change already in the vault, so the upgrade's diff stays its own.

## Step 1 - Scan and plan

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/upgrade_scan.py" --vault <root> [--clone <path>] [--ref <ref>] > <scan output path>
```

The script's docstring defines every field and exit code. On exit 3 with `CLAUDE.md` in `vault.missing`, this is a bootstrap: point at `bootstrap-prompt.md` and stop; on 4 or 5, ask for a clone path or a ref that resolves; on 6, see Precondition 1.

By `revision.verdict`:

- **behind** or **no-marker**: Steps 2 to 5.
- **equal**: a kit file changes on its own, so `files` and `own.repeats` still count. With nothing in either, say the vault is on revision X with nothing to do.
- **ahead**: stop and ask; the ref is stale or the core was edited by hand. Never downgrade a vault.

**Present the plan before touching anything**: the `files` rows by state, `own.repeats`, and the Reactions in `revision.entries`. With `audit`, report the plan and stop.

## Step 2 - Kit files

Every `files` row, by `state`:

- **untouched**: an older version the kit shipped: behind, with nothing local to lose. Re-copy them all on one approval.
- **missing**: copy in on one approval.
- **edited**: bytes the kit never shipped: local work, a hand edit, or a copy taken from ahead of the ref. Show the row's `diff` and say what it shows; the operator decides each file: re-copy, keep, or carry the kit's change into the vault's wording.
- **retired**: each deletion is its own question, per [operating-discipline.md](../para-shared/operating-discipline.md#deleting-a-file).
- **no-master**: report it and leave it.

A Reaction in `revision.entries` that names a row's file runs before that row is copied. A `core` row is a fixed file under `.claude/para-os/`: an edited one is re-copied, never kept or merged. `core.md` itself waits for Step 5, because it carries the revision.

A `path` outside the vault is a user-level install, shared by every vault on the machine: say so when proposing it. Copy each with `upgrade_scan.py copy --vault <root> --clone <clone> --commit <clone.commit> <master> <path>`; exit 4 changed nothing.

## Step 3 - The vault's own file

`CLAUDE.md` is the vault's, and this skill writes to it only what the operator approves line by line. Show each `own.repeats` row with the kit file that holds it and propose removing them all on one approval: the kit states that line, so the vault's copy says it twice. A `retired` row is asked apart: only the older template held it, the kit has dropped that rule, and the vault keeps it only as a rule of its own. Report `own.words` and `own.start_words`, what a session loads at its start.

## Step 4 - Content changes

Each Reaction in `revision.entries` is its own item with its own approval; one whose condition the vault does not meet does not apply, said in one line. Reclassifying or retiring the vault's own entities is proposed, never applied, and a move repoints inbound links in the same pass.

## Step 5 - Stamp and verify

1. **Re-run the scan.** A row the operator approved is gone from `files`; one still there names what did not land.
2. **Copy `.claude/para-os/core.md`** once everything the operator approved has landed; a `files` row left for the operator never holds it back.
3. **Check the result**: `paraos_vault.py links dangling --archive --vault <root>`, in `para-shared/scripts/`, finds no dangling link the run made, every `mentions` line a move returned is brought in line, and one skill runs end to end (`/para-daily-brief week` publishes nothing). An error is a regression this run fixes.
4. **Report** what changed per step, what was proposed and declined, and what you did not verify.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** Specific to this skill:

- **The plan is the scope.** What it does not name belongs to `/para-deep-clean`.
- **Never overwrite an edited file, or a user-level install, without the operator's yes for that file.**
- **Never copy the core before the work its revision claims.**
- **A write that fails mid-pass** (a sync client holding the file) stops the run: list what landed, have the operator pause syncing, and resume from the failed step. There is no automatic rollback beyond Precondition 2's undo path.
