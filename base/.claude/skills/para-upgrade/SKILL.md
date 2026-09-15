---
name: para-upgrade
description: Bring a vault in line with a newer para-os template revision - reads the vault's template marker, diffs it against a para-os clone at an explicit ref, then applies the intervening changelog entries as a reviewed migration (structure, skeleton files, stale rule and integration-script copies, and rule-driven content violations). Use when the user asks to "upgrade the vault", "align this vault to para-os", "is this vault on the latest structure", "apply the new para-os structure", or types /para-upgrade.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write
arg-hint: '[--ref <git-ref>] [audit] [--test]'
---

# Para upgrade

Aligns one vault to a para-os template revision. This is the **migration** skill: it changes what the vault's rules *are*. `/para-deep-clean` is the **conformance** skill: it checks the vault against the rules it already has. Run this one first when both are due, or the deep clean audits against a stale contract.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow against the default ref |
| `--ref <git-ref>` | Read the master from this ref instead of the default (a branch, tag, or commit). Also accepted as a bare positional argument (`/para-upgrade feat/revision-x`) or with a leading qualifier word (`local feat/revision-x`) - either resolves to `<git-ref>` in the clone, same as `--ref`. |
| `audit` | Read-only. Reports the delta and what would change; never modifies a file |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Preconditions

1. **A local para-os clone.** Ask the user for its path if it isn't obvious; do not guess. Every master is read from it, per [references/delta.md](references/delta.md).
2. **An explicit ref, defaulting to `origin/main`.** Run `git fetch` first so `origin/main` is current.
3. **The ref should be committed.** If the user names a working branch, check `git status --short` in the clone. Uncommitted changes can't be diffed against later or reproduced on another machine. If the master is uncommitted, say so plainly, name the files, and ask whether to proceed anyway or commit first. Do not commit on the user's behalf.
4. **Vault has a `CLAUDE.md`.** If missing, this is a bootstrap, not an upgrade: point at `bootstrap-prompt.md` and stop.
5. **A clean-enough vault working tree, and a way to undo.** This skill produces a large diff. If the vault already has substantial uncommitted changes, tell the user, so the migration doesn't get tangled with unrelated edits. Git undoes only what it tracks: check `CLAUDE.md` and `.claude/` with `git ls-files` and `git check-ignore`, and name any file in scope that git does not track. Where neither git nor a drive's version history covers a file, say so plainly and get an explicit go-ahead before Phase 1.

## Phase 0 - Establish the delta

Read the vault's marker and the master's, then read `CHANGELOG.md` at the ref and collect every entry after the vault's marker, up to and including the master's. Reading and resolving the master, the Equal case and the smoke-test baseline: [references/delta.md](references/delta.md).

- **Vault's marker**: the first `<!-- para-os-template: YYYY.MM.NN -->` comment in its `CLAUDE.md` (line 3 in the shipped template).
- **Master's marker**: the same comment in the resolved `CLAUDE.md.template`. Read it from the template, not from `CHANGELOG.md`, which carries a lookalike inside a code fence.

- **Equal** - run the Equal-markers checks, and stop unless they find the vault short.
- **Vault ahead of master** - stop and ask. Either the ref is stale or someone hand-edited the marker. Never downgrade a vault.
- **No marker in the vault** - it predates the scheme. Treat as the oldest revision in the changelog and run everything.
- **Vault stamped `2026.08`** - the label the first revision shipped under before revisions carried a sequence. It means `2026.08.01`, so the vault is already migrated to it: read it as that, collect only the entries after it, and restamp in Phase 5. Never re-run the `2026.08.01` entry against it.

Present the collected entries, with their size in files and items, as the migration plan before touching anything. **That list is the scope.** Do not opportunistically fix things the changelog doesn't mention: unrelated drift is `/para-deep-clean`'s job.

## Phases 1 and 2 - CLAUDE.md structure, then skeleton files

Diff the vault's `CLAUDE.md` against the template at both the new ref and the vault's own marker, so a deliberate local rewrite is carried forward rather than flattened; then create only the skeleton files genuinely missing. **Full procedure: [references/rules-and-skeleton.md](references/rules-and-skeleton.md).**

## Phase 3 - Derived copies: rules and scripts

The phase that pays for the skill: vault-local skills restating changed rules, stale skill names, bundled and user-level skill copies, and installed integration scripts diffed by **content** rather than by their marker string. Read-only - drift is reported and the user merges it. **Full procedure: [references/derived-copies.md](references/derived-copies.md).**

## Phase 4 - Rule-driven content violations

The content that breaks the *new* rules, with checks derived from the changelog entries rather than a fixed list. Everything here is destructive or reclassifying, so approval is per item and reclassification is proposed, never applied. **Full procedure: [references/content-violations.md](references/content-violations.md).**

## Phase 5 - Stamp and verify

1. **Write the new revision marker** into the vault's `CLAUDE.md`, and write it *here* - Phase 1 holds the vault's existing marker even while it replaces the section around it. Only after the phases above actually applied: the next run skips whatever a marker claims.
2. **Run the vault's own skills as a smoke test.** At minimum `/para-daily-brief week`, which publishes nothing, against the Phase 0 baseline. A skill that errors or renders an obviously wrong count is a regression from this migration, fixed here.
3. **Re-run the link check** from `/para-deep-clean` Phase 1, Step 1.2 (its `phase1-structural.md`), as written there. Zero dangling relative links in live buckets.
4. **Close the [edit cycle](../para-shared/operating-discipline.md#the-read-only-ipad-delivery) only now**, after every check that resolves a path against disk (this link check, Phase 3's self-claims sweep, the skeleton-presence check): they read the spread state.
5. **Report.** What changed per phase, what was proposed and declined, what was routed where, and what you did **not** verify.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **The changelog is the scope.** Drift the changelog doesn't mention belongs to `/para-deep-clean`.
- **Never remove vault-local additions** - sections, rules, markers, or the `**Type:**`, `**Delivery:**` and `**Flavor:**` lines. The template is a floor.
- **Never create a redundant `.claude/settings.json`** when the user-level settings already set the same keys, and never create a `triage/README.md` at all.
- **Never invent content.** A missing brief is written from what's on disk, or left missing with the gap stated. A missing date stays missing.
- **Never write to an installed script without the four-condition gate** - anything carrying (or identified as needing) a `para-os-integration:` marker, wherever it sits: `resources/scripts/`, or the vault root where a delivery's render pipeline lives. The general rule is report drift and let the user merge it; the one permitted write is the marker line itself, plus the **one sanctioned overwrite** described in Phase 3 (user asked, mechanical equivalence proven, copy not ahead, verified after write).

## Edge cases

- **The vault predates the marker scheme and has diverged heavily.** Run Phase 0 and Phase 1 as an audit first, present the size of the delta, and let the user decide whether to do it in one pass or split it.
- **The vault was migrated by hand and only lacks the marker.** Run the full pass anyway; it is the only thing that actually verifies the hand migration landed. Expect Phases 1 to 3 to come back near-empty and Phase 4 to re-derive proposals the earlier migration already settled. Present those as re-proposals, not discoveries, and take a "we looked at this and decided otherwise" as final.
- **A changelog entry doesn't apply to this vault.** Say so and skip it. A vault with no `resources/ideas/` has nothing to migrate from a checkbox-placement rule.
- **A file is locked mid-pass.** A syncing drive's client can hold a file open so an edit fails or half-lands. Stop on the first write error, report which files landed, have the user pause syncing, and resume from the failed phase.
- **The user wants out.** There is no automatic rollback. Name the vault's undo path before Phase 1 (git, the drive's version history, or none, per Precondition 5). If a pass goes wrong mid-flight, stop, list every file touched so far, and hand the user that path. Never reconstruct original content from memory.

## Notes for Claude sessions

- Track the phases in the harness's task list. They are long and the user needs to see where the pass is.
- Phase 4 is where the session gets slow, because each item needs a routing decision. Batch the *presentation* (one table per rule) even though approval is per item.

## Related skills

- `/para-deep-clean` - the conformance skill to this one's migration. Its own Precondition 5 sends a vault here when it's behind.
