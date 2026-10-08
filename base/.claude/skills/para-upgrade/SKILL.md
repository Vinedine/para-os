---
name: para-upgrade
description: Bring a vault in line with a newer para-os template revision - reads the vault's template marker, diffs it against a para-os clone at an explicit ref, then applies the intervening changelog entries as a reviewed migration (structure, skeleton files, stale rule and integration-script copies, and rule-driven content violations). Use when the user asks to "upgrade the vault", "align this vault to para-os", "is this vault on the latest structure", "apply the new para-os structure", or types /para-upgrade.
allowed-tools: Bash(python3 *), Bash(py *), Bash(node *), Bash(git fetch *), Bash(git show *), Bash(git log *), Bash(git rev-parse *), Bash(git status *), Bash(git ls-files *), Bash(git check-ignore *), Bash(git mv *), Bash(git rm *), Bash(mv *), Bash(diff *), Bash(tr *), Bash(grep *), Bash(ls *), Bash(test *), Bash(wc *), Bash(pwd *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Edit, Write
argument-hint: '[--ref <git-ref>] [--clone <path>] [audit] [--test]'
---

# Para upgrade

Aligns one vault to a para-os template revision. This is the **migration** skill: it changes what the vault's rules *are*. `/para-deep-clean` is the **conformance** skill: it checks the vault against the rules it already has. Run this one first when both are due, or the deep clean audits against a stale contract.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow against the default ref |
| `--ref <git-ref>` | Read the master from this ref instead of the default (a branch, tag, or commit). Also accepted as a bare positional argument (`/para-upgrade feat/revision-x`) or with a leading qualifier word (`local feat/revision-x`) - either resolves to `<git-ref>` in the clone, same as `--ref`. |
| `--clone <path>` | Read this para-os clone instead of the default one, per [para-shared/scripts.md](../para-shared/scripts.md) |
| `audit` | Read-only. Reports the delta and what would change; never modifies a file |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |
| any other `--` argument | Stops the run, `audit` or not: name it and show this table. Never read as a ref, bare or not. |

## Preconditions

1. **A local para-os clone**, found per [para-shared/scripts.md](../para-shared/scripts.md). Where none is (the scan's exit 6), ask the user for its path. Every master is read from it, per [references/delta.md](references/delta.md).
2. **An explicit ref, defaulting to `origin/stable`,** what users get; `origin/main` is where work merges before a release. Run `git fetch` first so `origin/stable` is current. With no ref named, a clone not on `stable` (the Phase 0 scan's `clone.checked_out.branch`, or its exit 5) was made before releases moved there: offer the one-time switch, `git -C <clone> fetch origin` then `git -C <clone> checkout stable`, so its later pulls follow `stable`.
3. **The ref should be committed.** If the user names a working branch, read the Phase 0 scan's `clone.dirty_masters` (by hand: [references/scan.md](references/scan.md)). If the master is uncommitted, name the files and ask whether to proceed anyway or commit first. Never commit on the user's behalf.
4. **Vault has a `CLAUDE.md`.** If missing, this is a bootstrap, not an upgrade: point at `bootstrap-prompt.md` and stop.
5. **A clean-enough vault working tree, and a way to undo.** This skill produces a large diff. If the vault already has substantial uncommitted changes, tell the user, so the migration doesn't get tangled with unrelated edits. Git undoes only what it tracks: check `CLAUDE.md` and `.claude/` with `git ls-files` and `git check-ignore`, and name any file in scope that git does not track. Where neither git nor a drive's version history covers a file, say so plainly and get an explicit go-ahead before Phase 1.
6. **No live peer on the vault.** Another session writing the same `CLAUDE.md` mid-run is not a sync client, and nothing in the file says it happened. Where the harness lists running sessions or agents, read that listing before Phase 1 and name any working in this vault; the operator decides whether to wait. The checkpoint scans catch one that starts later.

## Phase 0 - Establish the delta

**Run the scan first**, per [para-shared/scripts.md](../para-shared/scripts.md), keeping its output for Phase 5's `--unchanged`:

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/upgrade_scan.py" --vault <root> [--clone <path>] [--ref <ref>] > <scan output path>
```

**Exit codes**: 0 answered; 2 fall back to [references/scan.md](references/scan.md)'s by-hand procedure; 3 `--vault` is not a vault root (one with no `CLAUDE.md` is Precondition 4's bootstrap stop); 4 the clone or the ref cannot be read (ask for the clone's path or a ref that resolves, never guess one); 5 no ref was named and the clone has no `origin/stable`: Precondition 2's switch, then scan again; 6 no clone found: Precondition 1.

Read the `delta` block for the vault's marker, the master's, the verdict and the collected entries, and the `clone` block for the ref read, the checked-out branch and `origin/stable`, each with its commit. Reading and resolving the master, the Equal case (which also reads Phase 3's `skills` and `integrations` blocks) and the smoke-test baseline: [references/delta.md](references/delta.md).

- **Vault's marker**: the first `<!-- para-os-template: YYYY.MM.NN -->` comment in its `CLAUDE.md` (line 3 in the shipped template).

- **Equal** - run the Equal-markers checks, and stop unless they find the vault short.
- **Vault ahead of master** - stop and ask. Either the ref is stale or someone hand-edited the marker. Never downgrade a vault.
- **No marker in the vault** - it predates the scheme. Treat as the oldest revision in the changelog and run everything.
- **Vault stamped `2026.08`** - the label the first revision shipped under before revisions carried a sequence. It means `2026.08.01`, so the vault is already migrated to it: read it as that, collect only the entries after it, and restamp in Phase 5. Never re-run the `2026.08.01` entry against it.

Present the collected entries, with their size in files and items, as the migration plan before touching anything. **That list is the scope.** Do not opportunistically fix things the changelog doesn't mention: unrelated drift is `/para-deep-clean`'s job.

**Take a checkpoint scan after every phase that writes, and re-check it before the next write**, per [references/delta.md](references/delta.md#checkpoints).

## Phases 1 and 2 - CLAUDE.md structure, then skeleton files

Diff the vault's `CLAUDE.md` against the template at both the new ref and the vault's own marker, so a deliberate local rewrite is carried forward rather than flattened; then create only the skeleton files genuinely missing. **Full procedure: [references/rules-and-skeleton.md](references/rules-and-skeleton.md).**

## Phase 3 - Derived copies: rules and scripts

The phase that pays for the skill: vault-local skills restating changed rules, stale skill names, bundled and user-level skill copies, and installed integration scripts diffed by **content** rather than by their marker string. Read the scan's `skills` and `integrations` blocks for every verdict, diff, overwrite-eligibility, `revisions_behind` and suite locator - the shared five-rule verdict is stated once in [references/scan.md](references/scan.md). Read-only - drift is reported and the user merges it. **Full procedure: [references/derived-copies.md](references/derived-copies.md).**

## Phase 4 - Rule-driven content violations

The content that breaks the *new* rules, with checks derived from the changelog entries rather than a fixed list. Everything here is destructive or reclassifying, so approval is per item and reclassification is proposed, never applied. **Full procedure: [references/content-violations.md](references/content-violations.md).**

## Phase 5 - Stamp and verify

1. **Write the new revision marker** into the vault's `CLAUDE.md`, and write it *here* - Phase 1 holds the vault's existing marker even while it replaces the section around it. Only after the phases above actually applied: the next run skips whatever a marker claims. The checkpoint re-check comes immediately before.
2. **Run the vault's own skills as a smoke test.** Re-run the scan with `--unchanged <the Phase 0 scan>`: `since.smoke` is every count that moved since before the migration (`{count, before, after}`), and `since.changed` every file that changed, each of which should be one this run wrote. Also run at least one skill end to end (`/para-daily-brief week` publishes nothing). A skill that errors, or a count that moved for a file this migration did not write, is a regression, fixed here.
3. **Re-run the link check** from `/para-deep-clean` Phase 1, Step 1.2 (its `phase1-structural.md`), as written there. Zero dangling relative links in live buckets.
4. **Report.** What changed per phase, what was proposed and declined, what was routed where, and what you did **not** verify.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **The changelog is the scope.** Drift the changelog doesn't mention belongs to `/para-deep-clean`.
- **Never remove vault-local additions** - sections, rules, markers, or the `**Type:**`, `**Flavor:**` and `**Modules:**` lines. The template is a floor.
- **Never create a redundant `.claude/settings.json`** when the user-level settings already set the same keys, and never create a `triage/README.md` at all.
- **Never invent content.** A missing brief is written from what's on disk, or left missing with the gap stated. A missing date stays missing.
- **Never write to an installed script without the four-condition gate** - anything carrying (or identified as needing) a `para-os-integration:` marker, wherever it sits in the vault. The general rule is report drift and let the user merge it; the one permitted write is the marker line itself, plus the **one sanctioned overwrite** described in Phase 3 (user asked, mechanical equivalence proven, copy not ahead, verified after write). Removing a script a collected entry retires is not a write to it ([references/derived-copies.md](references/derived-copies.md)).

## Edge cases

- **The vault predates the marker scheme and has diverged heavily.** Run Phase 0 and Phase 1 as an audit first, present the size of the delta, and let the user decide whether to do it in one pass or split it.
- **The vault was migrated by hand and only lacks the marker.** Run the full pass anyway; it is the only thing that actually verifies the hand migration landed. Expect Phases 1 to 3 to come back near-empty and Phase 4 to re-derive proposals the earlier migration already settled. Present those as re-proposals, not discoveries, and take a "we looked at this and decided otherwise" as final.
- **A changelog entry doesn't apply to this vault.** Say so and skip it. A vault with no `resources/ideas/` has nothing to migrate from a checkbox-placement rule.
- **A file is locked mid-pass.** A syncing drive's client can hold a file open so an edit fails or half-lands. Stop on the first write error, report which files landed, have the user pause syncing, and resume from the failed phase.
- **The user wants out.** There is no automatic rollback. Name the vault's undo path before Phase 1 (git, the drive's version history, or none, per Precondition 5). If a pass goes wrong mid-flight, stop, list every file touched so far, and hand the user that path. Never reconstruct original content from memory.

## Notes for Claude sessions

- Track the phases in the harness's task list where it offers one, else in a short progress message at each phase boundary.
- In Phase 4, batch the *presentation* (one table per rule) even though approval is per item.

## Related skills

- `/para-deep-clean` - the conformance skill to this one's migration. Its own Precondition 5 sends a vault here when it's behind.
