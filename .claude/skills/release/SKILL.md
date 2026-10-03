---
name: release
description: Cut or extend a para-os template revision - pick the label, write the CHANGELOG entry, restamp every marker, bump changed integrations, reconcile delivery digests, run the full check, validate main on real vaults, and ship it to stable. Use when the maintainer says "release", "cut a revision", "stamp the revision", or types /release.
argument-hint: '[<revision>]'
disable-model-invocation: true
allowed-tools: Bash(python3 *), Bash(py *), Bash(git *), Bash(gh *), Read, Grep, Glob, Edit, Write, AskUserQuestion, Skill
---

# Release a revision

A revision marks a template change that an existing vault has to react to. The scheme is at
the top of `CHANGELOG.md`; read it first. `/para-upgrade` executes each entry, so an entry is
an instruction to an agent, not a summary for people. Work merges into `main`; a revision has
shipped once it is reachable from `origin/stable`, which users install and upgrade from.

## 1. Decide whether this needs a revision

List what changed since the last revision shipped:

```bash
git fetch origin
git diff --stat origin/stable...HEAD
git log --oneline origin/stable..HEAD
```

A change needs a revision when a vault must do something: re-sync a skill or `para-shared/`,
copy a rule file, edit its `CLAUDE.md`, update an installed integration. Wording that changes no
rule does not. When nothing qualifies, say so and stop.

## 2. Pick the label

Read the newest `## YYYY.MM.NN` heading in `CHANGELOG.md`, and check whether `origin/stable`
already has it (`git show origin/stable:CHANGELOG.md`).

- **Not shipped yet**: this change folds into that open revision. Keep the label and extend
  its entry.
- **Already shipped**: cut the next one. Same month, next sequence (`2026.09.05` is followed
  by `2026.09.06`); a new month restarts at `.01`. Take the month from the system clock.

An argument naming a revision overrides this; confirm it is newer than every heading.

## 3. Write the entry

Match the entries below it exactly: a bold one-line summary with its own `Reaction:`, then one
bold-led paragraph per change, each ending in `Reaction:` (what an existing vault does, or
`none for an existing vault`). Add an `**Integrations.**` line when a script moved. Newest
first, and no calendar dates or em/en dashes in the prose.

Then the same revision in `RELEASES.md`, for people rather than the agent: a
**What changes for you.** paragraph and a **Do you need to do anything?** paragraph that names
only what `/para-upgrade` cannot do for them. Plain words, no file paths a non-programmer
would not recognise. When folding into an open revision, update both files.

## 4. Restamp

- `<!-- para-os-template: <label> -->` in `base/CLAUDE.md.template`, every
  `addons/*/skeleton/CLAUDE.md.template`, and every `examples/*/CLAUDE.md`.
- For each integration whose script changed since its last stamp: the
  `para-os-integration: <name> <label>` marker in every script in its folder, and its row in
  the Available table in `integrations/README.md`. An unchanged integration keeps its label.
- If `base/CLAUDE.md.template`, `base/README.md.template` or `base/.gitignore` changed: review
  the matching `addons/readonly-ipad/skeleton/` file, apply what the delivery needs, then
  restamp its digest in `DELIVERY_TRACKING` in `tools/check.py` to the value the check reports.

## 5. Verify

```bash
python3 tools/check.py
```

Without `--no-vendor`: a release also passes `claude plugin validate`. If `~/.paraos/never-ship.txt`
is missing, the check skips the never-ship scan and says so; tell the maintainer rather than
treating it as a pass. Fix every failure; never edit a check to get green.

## 6. Hand over

Show the entry and the diff stat, and propose one commit, `Stamp revision <label>` or
`Fold <change> into revision <label>`. Commit only after approval. Never push or open a PR
unless asked.

Steps 7 and 8 run once every pull request in the revision's milestone has merged into `main`.

## 7. Validate `main` on real vaults

Record the commit under test, `<sha>`, as `git fetch origin && git rev-parse origin/main`
prints it. Start the evals on it with `gh workflow run evals.yml --ref main` and read the run's
summary page when it finishes: a case that dropped since the last weekly run is a finding like
those below. Beside them, run the `claude-api` skill's `prompt-audit` at `<sha>`, scoped to the
shipped files the revision changed (`git diff --name-only origin/stable...<sha> -- base addons
multi-vault`), or to every shipped skill when a Claude model has shipped since the last revision.
It applies nothing; each finding it would edit is a finding like those below, and a removal it
proposes is compared on the evals first. The maintainer syncs the installed skills from `<sha>`,
then upgrades two vaults of
different shapes with `/para-upgrade --ref <sha>`: one on the previous revision, one further
behind or on an add-on. In each, run every skill the revision changed with `--test`. Every
finding is fixed on `main` through its own issue and pull request, and the validation reruns
from a new `<sha>` until it is clean.

**Do not go on to step 8 until the maintainer has named both vaults and confirmed each ran
clean at `<sha>`.** Ask with `AskUserQuestion`; an answer that names fewer than two vaults is a
no.

## 8. Ship

Ship `<sha>`, the commit step 7 validated, never `main`'s head: a pull request merged since
then goes out in the next revision. Stop if `git show <sha>:base/CLAUDE.md.template` does not
carry `<!-- para-os-template: <label> -->`. Otherwise propose these commands, and run them only
on the maintainer's approval:

```bash
git tag <label> <sha>
git push origin <label>
git push origin <sha>:refs/heads/stable   # fast-forward only
gh release create <label> --verify-tag --title <label> --notes-file <notes>
```

`<notes>` is that revision's section of `RELEASES.md`, heading excluded, written to a scratch
file. Never force `stable`: a push it refuses means it holds a hotfix `<sha>` lacks. Merge
`stable` into `main` per [CLAUDE.md](../../../CLAUDE.md#branches), then validate again from
step 7.
