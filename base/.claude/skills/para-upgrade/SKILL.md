---
name: para-upgrade
description: Bring a vault in line with a newer para-os template revision - compares every file the kit owns with a para-os clone at an explicit ref by hash and re-copies on approval, takes the operator through the template's change to CLAUDE.md hunk by hunk, proposes deleting the files the kit retired, applies the content changes the changelog asks for, and restamps the marker. Use when the user asks to "upgrade the vault", "align this vault to para-os", "is this vault on the latest structure", "apply the new para-os structure", or types /para-upgrade.
allowed-tools: Bash(python3 *), Bash(py *), Bash(git -C * fetch *), Bash(git -C * show *), Bash(git rm *), Bash(mkdir *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Edit, Write
argument-hint: '[--ref <git-ref>] [--clone <path>] [audit] [--test]'
---

# Para upgrade

Aligns one vault to a para-os template revision. This is the **migration** skill: it changes what the vault's rules *are*. `/para-deep-clean` checks the vault against the rules it already has; run this one first when both are due.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow against `origin/stable` |
| `--ref <git-ref>` | Read the kit at this branch, tag or commit instead. A bare positional ref (`/para-upgrade feat/x`), or one after a qualifier word (`local feat/x`), is the same. |
| `--clone <path>` | Read this para-os clone instead of the default one, per [para-shared/scripts.md](../para-shared/scripts.md) |
| `audit` | Read-only: report what an upgrade would change, and change nothing |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |
| any other `--` argument | Stops the run, `audit` or not: name it and show this table. Never read as a ref, bare or not. |

## Preconditions

1. **A local para-os clone**, per [para-shared/scripts.md](../para-shared/scripts.md); with none (the scan's exit 6), ask for its path. Run `git -C <clone> fetch origin` first, so `origin/stable` is current.
2. **A `CLAUDE.md` in the vault.** Without one this is a bootstrap, not an upgrade: point at `bootstrap-prompt.md` and stop.
3. **An undo path, named before the first write**: git where the vault is a repository, the drive's version history, or none, which needs the operator's explicit go-ahead. Name any uncommitted change already in the vault, so the upgrade's diff stays its own.

## Step 1 - Scan and plan

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/upgrade_scan.py" --vault <root> [--clone <path>] [--ref <ref>] > <scan output path>
```

**Exit codes**: 0 answered; 3 not a vault root (with no `CLAUDE.md`, Precondition 2); 4 the clone or the ref cannot be read: ask for a clone path or a ref that resolves, never guess one; 5 no ref named and the clone has no `origin/stable`: offer `git -C <clone> fetch origin` then `git -C <clone> checkout stable`, and scan again; 6 no clone: Precondition 1. Every field is in the script's docstring.

By `revision.verdict`:

- **behind** or **no-marker**: Steps 2 to 5.
- **equal**: a kit file drifts on its own, so `files` still counts. With nothing in it, say the vault is on revision X with nothing to do, and suggest `/para-deep-clean` for a cleanup.
- **ahead**: stop and ask. The ref is stale, or the marker was edited by hand. Never downgrade a vault.

**Present the plan before touching anything**: the `files` rows by state, the `contract` rows, and the Reactions in `revision.entries` that change the vault's own content. That is the scope: drift it does not name belongs to `/para-deep-clean`. With `audit`, report the plan and stop.

## Step 2 - Kit files

Every `files` row, by `state`:

- **untouched**: the vault's bytes are a version the kit shipped, so nothing local is lost. Re-copy them all on one approval.
- **missing**: copy in on one approval, except a `.claude/settings.json` whose every key `~/.claude/settings.json` already sets to the same value. A rule file copied in takes over what the vault already states of its rule, each line moved on its own yes.
- **edited**: bytes the kit never shipped: local work, a hand edit, or a copy taken from ahead of the ref. Show the row's `diff` and say what it shows; the operator decides each file: re-copy, keep, or carry the kit's change into the vault's wording.
- **retired**: the kit no longer ships it. Each deletion is its own question, per [operating-discipline.md](../para-shared/operating-discipline.md#deleting-a-file).
- **no-master**: an integration the ref ships nothing for. Report it and leave it, unless a collected Reaction retires it: then its deletion is its own question.

A `path` outside the vault is a user-level install, shared by every vault on the machine: say so when proposing it. Before each write run `paraos_vault.py changed <scan output path>`, per [operating-discipline.md](../para-shared/operating-discipline.md#a-synced-vault-can-change-mid-run), then copy with `git -C <clone> show <clone.commit>:<master> > <path>`, creating its folder first where it has none.

## Step 3 - The contract

`contract` is the template's own change since the vault's revision, one row per changed section of `base/CLAUDE.md.template` or a declared add-on's `CLAUDE.md.sections`. For each hunk, find where the vault states that rule and propose the edit in the vault's own wording and language; the operator rules on each hunk. With `revision.baseline` null there was no earlier template to diff against: each section comes whole, to compare with the vault's.

- **The template is a floor.** Never remove the vault's own sections, rules or declaration lines; where the template moves a section the vault extended, the vault's content moves with it.
- **A hunk the vault already states is skipped**, said in one line. A rule the vault deliberately departs from is the operator's call.
- **The marker line is Step 5's.** Hold the vault's existing marker until then.

## Step 4 - Content changes

A Reaction in `revision.entries` that asks the vault to change its own content (a sentence outside `CLAUDE.md`, a file to move, notes to delete) is its own item with its own approval. A Reaction that re-syncs or copies a kit file is Step 2's table, and one for an add-on the vault does not declare does not apply: say so in one line each. Reclassifying or retiring the vault's own entities is proposed, never applied, and every move repoints inbound links in the same pass.

## Step 5 - Stamp and verify

1. **Re-run the scan.** A row the operator approved is gone from `files`; one still there names what did not land.
2. **Write the master's marker** into the vault's `CLAUDE.md`, only once the steps above applied: the next run trusts it.
3. **Check the result**: `paraos_vault.py links dangling --vault <root>` finds no dangling link the run made, and one skill runs end to end (`/para-daily-brief week` publishes nothing). An error is a regression this run fixes.
4. **Report** what changed per step, what was proposed and declined, and what you did not verify.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** Specific to this skill:

- **The scan is the scope.** Never fix what it and the collected Reactions do not name.
- **Never overwrite an edited file, or a user-level install, without the operator's yes for that file.**
- **Never write the marker before the work it claims.** A marker written early hides the rest from every later run.

## Edge cases

- **A write fails mid-pass** (a sync client holding the file): stop, list what landed, have the operator pause syncing, and resume from the failed step. There is no automatic rollback: hand over Precondition 3's undo path.

## Related skills

- `/para-deep-clean` - the conformance skill to this one's migration. Its own Precondition 5 sends a vault here when it is behind.
- `/para-audit` - the same file table for every registered vault at once.
