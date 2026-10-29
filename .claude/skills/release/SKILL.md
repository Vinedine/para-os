---
name: release
description: Cut or extend a para-os template revision - pick the label, fold the changelog fragments, restamp every marker, bump changed integrations, run the full check, validate main on real vaults, and ship it to stable. Use when the maintainer says "release", "cut a revision", "stamp the revision", or types /release.
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
rule does not. Each such change left a fragment in `changelog.d/`; write one now for any that
did not. When nothing qualifies, say so and stop.

## 2. Pick the label

Read the newest `## YYYY.MM.NN` heading in `CHANGELOG.md`, and check whether `origin/stable`
already has it (`git show origin/stable:CHANGELOG.md`).

- **Not shipped yet**: this change folds into that open revision. Keep the label and extend
  its entry.
- **Already shipped**: cut the next one. Same month, next sequence (`2026.09.05` is followed
  by `2026.09.06`); a new month restarts at `.01`. Take the month from the system clock.

An argument naming a revision overrides this; confirm it is newer than every heading.

## 3. Fold the fragments

```bash
# Windows: py -3
python3 .claude/skills/release/scripts/fold_changelog.py <label>
```

It appends every fragment to the `<label>` revision in `CHANGELOG.md` and `RELEASES.md`, in
the order they merged, and deletes it; it writes nothing when it refuses. Then open the
revision in `RELEASES.md` on `### Highlights`: the few bullets most users will notice, moved up
from the sections below, which keep the rest or lose what nobody would miss. What each part
holds is in [changelog.d/README.md](../../../changelog.d/README.md).

## 4. Restamp

- `<!-- para-os-template: <label> -->` in `base/CLAUDE.md.template` and every
  `examples/*/CLAUDE.md`.
- For each integration whose script changed since its last stamp: the
  `para-os-integration: <name> <label>` marker in every script in its folder, and its row in
  the Available table in `integrations/README.md`. An unchanged integration keeps its label.
- `<!-- reviewed with: <your own model id> -->` on the line after the frontmatter of every
  shipped `SKILL.md` the step 7 prompt audit reads, replacing the one there.

## 5. Verify

```bash
python3 tools/check.py
```

Without `--no-vendor`: a release also passes `claude plugin validate`. If `~/.paraos/never-ship.txt`
is missing, the check skips the never-ship scan and says so; tell the maintainer rather than
treating it as a pass. Fix every failure; never edit a check to get green.

## 6. Hand over

Show the entry and the diff stat, and propose one commit, `Stamp revision <label>` or
`Fold changelog.d into revision <label>`. Commit only after approval. Never push or open a PR
unless asked.

Steps 7 and 8 run once every pull request in the revision's milestone has merged into `main`.

## 7. Validate `main` on real vaults

Record the commit under test, `<sha>`, that `git fetch origin && git rev-parse origin/main`
prints. If `git ls-tree --name-only <sha> changelog.d/` lists more than its `README.md`,
fold it first (steps 2-6). Start the evals with `gh workflow run evals.yml --ref main`; a case
that dropped since the last weekly run is a finding only if the drop holds over
[three runs on both commits](../../../evals/README.md#checking-a-skill-change). Run the
`claude-api` skill's `prompt-audit` at `<sha>` on the shipped files the revision changed
(`git diff --name-only origin/stable...<sha> -- base addons multi-vault`) and each shipped
`SKILL.md` with no `reviewed with` line, or on every shipped skill when a Claude model has
shipped since the last revision. Its proposed edits are findings.
On a new model, a case whose delta fell to about zero or below since the previous model's last
run proposes removing its rule; a removal is checked like a drop, and takes its case with it.
The maintainer syncs installed skills from `<sha>`, then upgrades two vaults of different shapes
with `/para-upgrade --ref <sha>`: one on the previous revision, one further behind or on an
add-on. In each, run every skill the revision changed with `--test`. Each finding gets its own
issue and pull request, and validation reruns from a new `<sha>` until clean.

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
