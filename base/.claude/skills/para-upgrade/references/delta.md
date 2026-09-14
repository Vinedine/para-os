# Phase 0 - Establish the delta

## Reading the master

Every master is read from the clone with `git show <ref>:<path>`. Where Precondition 3 proceeds on an uncommitted master, the ref is the checked-out branch and every master is read from the clone's working tree instead, unstaged edits included, never the index; every "at the ref" in this skill then means the working tree, and the report says the master was uncommitted.

The Phase 0 report names the ref read, the clone's checked-out branch and `origin/main`, each with its commit, and says when two are the same commit.

## Resolving the master

A vault declares a delivery and a flavor each on its own line under `**Type:**`.

- **Delivery** (how the vault is read): `**Delivery:** <name>` makes `delivery/<name>/skeleton/CLAUDE.md.template` the master for the marker and Phase 1. Phase 2's master is `base/` with that skeleton's files overlaid. A vault with no `**Delivery:**` line that [the detection rule](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery) places on the read-only iPad delivery takes that delivery at every ref, and the missing line is a Phase 1 item. At a ref with no `delivery/` folder, look under `flavors/` instead.
- **Flavor** (what the vault is about): `**Flavor:** <name>` never supplies a `CLAUDE.md` master. `flavors/<name>/` adds sections, rule and skeleton files, and skill masters on top, each checked in the phase that checks its kind.

## Equal markers

Run two checks from [derived-copies.md](derived-copies.md), `## Installed integration scripts` and the installed skill copies under `## Sweep for`: both drift independently of the template marker. Then check the vault carries what the current revision's changelog entry tells a vault to do (its Reaction lines that change vault files). A miss means the marker overstates the vault: report it and offer that entry as the migration plan. Otherwise stop: report "vault is on revision X, nothing to do", plus any copy found behind, and suggest `/para-deep-clean` if the user wanted a cleanup.

## Smoke-test baseline

Run `/para-daily-brief week` now and keep its counts. Phase 5 runs it again; before calling a changed count a regression, check whether the files behind the change are ones this migration wrote.
