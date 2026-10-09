# Working on para-os

Instructions for anyone, person or agent, changing this repo. Keep private working notes in
`CLAUDE.local.md`, which Claude Code also loads and git ignores.

## The one principle

para-os is prose a capable model reads in someone else's vault, every session. **A rule exists
only for what the model would get wrong without it.** Everything else is cost: tokens per run,
a surface for the next contradiction, a bug nobody wants to read. So the default answer to any
finding is to delete or shorten something, and a new sentence is the exception that argues its
case. Before adding one, ask these in order and stop at the first yes:

1. Does the model already do this unprompted? Then no rule.
2. Does an existing rule cover it, read plainly? Then no second rule; at most a link to the first.
3. Would the finding disappear if the rule it hits were deleted? Then delete the rule.

Two consequences, and they hold for every pull request:

- **A change that adds no user-facing capability leaves every file it touches smaller.**
  Fixing, clarifying, hardening and explaining are not capabilities.
- **An issue an agent session filed is a claim, not a work item.** It gets a milestone only
  after the three questions above; one that reports ambiguity or friction in prose closes when
  the prose gets shorter, never longer. A fixed mistake does not earn a paragraph: correct the
  rule in place, and never append one narrating the incident.

## What ships

para-os is a kit, not an app. What a vault receives is `base/`, copied whole at install
(`INSTALL.md`). Everything else is optional or tooling:

| Path | What it is |
|---|---|
| `base/` | The vault skeleton: `CLAUDE.md.template`, `README.md.template`, `.claude/skills/para-*`, `.claude/rules/`, `bootstrap-prompt.md` |
| `addons/` | Flavors and modules an operator adopts by name later |
| `integrations/` | Sync and fetch scripts, each stamped `para-os-integration: <name> <revision>` |
| `multi-vault/` | `/para-ingest` and `/para-audit`, for operators running several vaults |
| `examples/belfoot-vault/` | The example vault: a working instance of everything base ships. Read it, never copy it |
| `evals/` | Behaviour cases for the skills, run by `tools/eval.py` |
| `docs/` | Design notes for maintainers; never copied into a vault |
| `tools/check.py`, `tools/tests/` | Contract checks, and the unit suite of every skill script |
| `tools/coverage_report.py` | The same suites under coverage, with a floor CI enforces |
| `CHANGELOG.md` | One entry per template revision; `/para-upgrade` executes each entry's Reaction |
| `RELEASES.md` | The same revisions for people: what changes, and whether to do anything |
| `changelog.d/` | One fragment per pull request, folded into both by `/release` |

## Before every commit

```bash
python3 tools/check.py --no-vendor   # what CI runs; `py -3` on Windows
python3 tools/check.py               # before a release: also runs `claude plugin validate`
```

Both must pass. CI runs the first on Ubuntu, macOS and Windows under Python 3.12, and on Ubuntu
under 3.9, on every push to `main`, `stable` or a `feat/` branch and on every pull request. A
second job fails when coverage drops below its floor, and a third runs `actionlint` over
`.github/workflows/`. `main` merges nothing until all six pass.

What the checks enforce, and why each is machinery rather than prose, is the docstring of
`tools/check.py`: dashes, dates, never-ship terms, line caps, the skill and rule-file contracts,
revision markers, fragments, test suites. A rule a check enforces is stated there and
nowhere else.

## Branches

- **`main` is where work merges**: one issue, one branch, one pull request that says `Fixes #N`,
  merged as a squash, so `main` reads one commit per issue. A squash leaves the branch's own
  commits unreachable, so an issue or pull request cites other work by its number, never by the
  hash of a commit that is not on `main`.
- **`stable` is what users get**: the Quickstart, `INSTALL.md` and `/para-upgrade` read it.
  `/release` moves it forward to a tagged revision on `main`; a hotfix is the one other change.
- **Fixes land on `main` first.** A hotfix to a released revision is fixed on `main` and
  cherry-picked onto `stable`, never the other way round. Then `stable` is merged into `main`
  through a pull request, as a merge commit, not a squash, so the next `/release` can
  fast-forward `stable` again.
- **Branch protection is versioned** in [`.github/rulesets/`](.github/rulesets/): `main.json`
  and `stable.json`. A ruleset changed on GitHub is re-exported in the same pull request
  (`gh api repos/Vinedine/para-os/rulesets/<id>`).

## Never ship

- **Private data, in any form.** No real people, clients, employers, mailbox addresses, or
  paths and folder trees from outside this repo. The example vault is synthetic and stays
  synthetic. The never-ship scan catches only the terms on its list; the rest is review.
- **Country-specific functionality.** No skill, rule, template or script assumes a country or
  anything that follows from one: registries, legal documents, taxes, portals, local-language
  terms. That is configuration the vault supplies, through its `CLAUDE.md` or a register
  template an addon ships. Synthetic example content may still be set in a country.
- Sections that announce their own emptiness, rationale paragraphs inside procedures, and
  personal machine configuration in a shipped `settings.json`.
- **Issue, pull request and commit text is as public as the files.** The same rules apply, and a
  finding from a real vault is restated with a synthetic example. `check.py` cannot scan it. The
  never-ship list is run against that text wherever private data can enter: an issue, comment or
  pull request written on a machine that holds the vaults. A session without the list, such as a
  cloud session working from this repository and its issues, has none of that data and skips the
  scan without flagging it.

## How changes are made

- **Read a folder's README in full before running or changing what is in it**: `evals/`,
  `integrations/`, `addons/`, `multi-vault/`. They hold the flags, limits and traps that are
  not visible from the code. Before saying something is missing, search the repo for it.
- **A change to base reaches every addon built on it and the example vault in the same pass**,
  or it has forked. Everything base ships has a working instance in `examples/belfoot-vault/`;
  base functionality with no instance there is unfinished.
- **Scripts do the mechanics, prose does the judgment.** Parsing, dating, bucketing, counting
  and every derived figure belong in a skill's `scripts/*_scan.py`, its suite in `tools/tests/`. A
  `SKILL.md` says what to do with the scan's output; the script and its suite are the
  specification, and no prose restates them. A scan emits only what a step of its skill reads.
- **Rules governing a script live in that script's README or docstring**, not in a `SKILL.md`.
- **A defect in a script becomes a test before it is fixed.** A defect in prose is first a
  question: delete the rule, or rewrite it shorter. It earns an eval case in `evals/` only when
  the shorter rule still fails. Before cutting a rule, compare its evals on the commit before and
  after ([`evals/README.md`](evals/README.md#checking-a-skill-change)).
- **Say it once.** Every rule has one canonical home; other files link to it.
- **Turning a convention into enforcement machinery is a feature.** Open an issue before
  building it.
- **A template change that an existing vault must react to adds a fragment** to
  `changelog.d/` ([format](changelog.d/README.md)), never an edit to `CHANGELOG.md` or
  `RELEASES.md`; `/release` folds the fragments into a revision. Wording that changes no rule
  adds none.
- **Line endings are LF** (`.gitattributes`), except `.ps1`, which is CRLF. An installed copy is
  compared to its master byte for byte.
- **Skill scripts use the Python standard library only.** An integration may need a package
  (`outlook` needs `requests`) and says so in its README. Every script must run on Windows
  (`py -3`) and macOS, under Python 3.9 or later.
- `examples/belfoot-vault/.claude/skills/` is an untracked copy of base's skills, made per
  `INSTALL.md`. If it exists, it must match base exactly, or the check fails.
