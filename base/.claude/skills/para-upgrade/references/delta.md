# Phase 0 - Establish the delta

## Reading the master

The scan's `clone` block names the ref read, the clone's checked-out branch and `origin/main`, each with its commit, and `same_commit` where two are the same. Where Precondition 3 proceeds on an uncommitted master, pass `--worktree`: every master then comes from the clone's working tree, unstaged edits included, never the index, and the report says the master was uncommitted. Full field table: [scan.md](scan.md).

## Resolving the master

A vault declares a delivery, a flavor and its modules each on its own line under `**Type:**`. The scan's `masters` block resolves each to a root (`addons/<name>/`, or the older `delivery/`/`flavors/` split at a ref before that folder existed) - [scan.md](scan.md) states the walk. What the resolution *means*:

- **Delivery** (how the vault is read): its `skeleton/CLAUDE.md.template` is the master for the marker and Phase 1; Phase 2's master is `base/` with that skeleton's files overlaid. A vault with no `**Delivery:**` line that [the detection rule](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery) places on the read-only iPad delivery takes that delivery at every ref, and the missing line is a Phase 1 item.
- **Flavor** (what the vault is about): never supplies a `CLAUDE.md` master. Its addon adds sections, rule and skeleton files, and skill masters on top, each checked in the phase that checks its kind.
- **Modules** (what a vault does beside that): read exactly like a flavor, once per named module. A vault takes none, one or several, and they never replace a base, delivery or flavor section. A module the scan reports with no folder at the ref is skipped, never guessed at; one it reports `carried_forward` (the ref predates `addons/` entirely) is likewise left untouched.
- **An entry for a flavor or module the vault does not declare** is usually decidable without asking: read the entry's own applicability clause ("none for a vault whose own entities are not properties it buys...") against what the vault's `CLAUDE.md` says it is for, and name that reading in the plan. Ask only where the reading leaves real doubt.

## Equal markers

Read the scan's `skills` and `integrations` verdicts (`## Installed integration scripts` and the installed skill copies under `## Sweep for` in [derived-copies.md](derived-copies.md) state what each verdict means): both drift independently of the template marker. Then check the vault carries what the current revision's changelog entry tells a vault to do (its Reaction lines that change vault files). A miss means the marker overstates the vault: report it and offer that entry as the migration plan. Otherwise stop: report "vault is on revision X, nothing to do", plus any copy found behind, and suggest `/para-deep-clean` if the user wanted a cleanup.

## Smoke-test baseline

**This runs on every Phase 0, whatever the Equal-markers check above decided**, including the run that stops there: a migration that does nothing still has to prove it did nothing. The scan's own `smoke` block is this baseline - [scan.md](scan.md) states what it keeps and its fallback (`/para-daily-brief week`, agenda excluded, where Python is absent or `brief_scan.py` exits non-zero).

Phase 5 takes the same reading again with `--unchanged <this Phase 0 scan>`. Before calling a moved count a regression, check whether the files behind the change are ones this migration wrote.
