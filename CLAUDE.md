# Working on para-os

Instructions for anyone, person or agent, changing this repo. Keep private working notes in
`CLAUDE.local.md`, which Claude Code also loads and git ignores.

## What ships

para-os is a kit, not an app. What a vault receives is `base/`, copied whole at install
(`INSTALL.md`). Everything else is optional or tooling:

| Path | What it is |
|---|---|
| `base/` | The vault skeleton: `CLAUDE.md.template`, `README.md.template`, `.claude/skills/para-*`, `.claude/rules/`, `bootstrap-prompt.md` |
| `addons/` | Delivery skeletons and flavors an operator adopts by name later |
| `integrations/` | Sync and fetch scripts, each stamped `para-os-integration: <name> <revision>` |
| `multi-vault/` | `/para-ingest`, for operators running several vaults |
| `examples/belfoot-vault/` | A finished example vault, frozen at a date; read it, never copy it |
| `evals/` | Behaviour cases for the skills, run by `tools/eval.py` |
| `docs/` | Design notes for maintainers; never copied into a vault |
| `tools/check.py` | Contract checks plus every unit test suite |
| `tools/coverage_report.py` | The same suites under coverage, with a floor CI enforces |
| `CHANGELOG.md` | One entry per template revision; `/para-upgrade` executes each entry's Reaction |
| `RELEASES.md` | The same revisions for people: what changes, and whether to do anything |

## Before every commit

```bash
python3 tools/check.py --no-vendor   # what CI runs; `py -3` on Windows
python3 tools/check.py               # before a release: also runs `claude plugin validate`
```

Both must pass. CI runs the first on Ubuntu, macOS and Windows under Python 3.12, and on Ubuntu
under 3.9, on every push to `main` or a `feat/` branch and on every pull request. A second job
fails when coverage drops below its floor.

## Rules check.py enforces

- **No em or en dashes** in shipped prose. Use a plain hyphen, a colon, or two sentences.
- **No calendar dates** in shipped prose (an ISO date, a month with its year, a quarter). A rule
  states what is true, not when someone learned it. Revision labels (`2026.09.05`) are fine.
- **Line caps.** A `SKILL.md` stays under 130 lines: procedure moves to `references/`. A
  `CLAUDE.md.template` stays at or under 120 lines, and base is at the cap already.
- **Skill contract.** Frontmatter `name` matches the folder, plus `description`, `allowed-tools`,
  and an `argument-hint` offering `--test`; a `## Strict rules` block; every reference linked
  both ways.
- **Revision markers agree.** Every template and the example vault carry the newest
  `CHANGELOG.md` revision, and `RELEASES.md` lists the same revisions in the same order; each integration's scripts agree with its row in
  `integrations/README.md`.
- **Delivery tracking.** Editing `base/CLAUDE.md.template`, `base/README.md.template` or
  `base/.gitignore` fails the check until the matching `addons/readonly-ipad/skeleton/` file is
  reviewed and its digest in `DELIVERY_TRACKING` is restamped.

## How changes are made

- **Scripts do the mechanics, prose does the judgment.** Parsing, dating, bucketing and
  counting belong in a skill's `scripts/*_scan.py`, with tests beside it. A `SKILL.md` says what
  to do with the scan's output and keeps a by-hand fallback for when the script cannot run.
- **A defect becomes a test before it is fixed**: a unit test when it is mechanical, an eval
  case in `evals/` when it is judgment.
- **Before adding a rule to a skill, check it is still needed.** Prose that a current model
  follows without being told costs every run and dilutes the rules that matter.
- **A template change that an existing vault must react to gets a revision.** Wording that
  changes no rule does not. Use `/release` to cut one.
- **Line endings are LF** (`.gitattributes`), except `.ps1`, which is CRLF. An installed copy is
  compared to its master byte for byte.
- **Skill scripts use the Python standard library only.** An integration may need a package
  (`outlook` needs `requests`) and says so in its README. Every script must run on Windows
  (`py -3`) and macOS, under Python 3.9 or later.
- `examples/belfoot-vault/.claude/skills/` is an untracked copy of base's skills. If it exists,
  it must match base exactly, or the check fails.
