# Scanning the vault and the clone (Phase 0, Phase 3, the mechanical half of Phase 2, the Phase 5 re-checks)

Mechanical: the
judgment lives in [delta.md](delta.md), [rules-and-skeleton.md](rules-and-skeleton.md) and
[derived-copies.md](derived-copies.md), whose rules `scripts/upgrade_scan.py` reads as one
scan over the shared library, `para-shared/scripts/paraos_vault.py`.

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/upgrade_scan.py" --vault <path> [--clone <path>] \
    [--ref origin/stable] [--worktree] [--today YYYY-MM-DD] [--user-skills DIR] \
    [--user-settings FILE] [--unchanged EARLIER_SCAN.json] [--indent N]
```

## Exit codes

| Code | Meaning | What prints |
|---|---|---|
| 0 | Answered | Every block below |
| 2 | The shared library is missing or fails to import | Nothing but a stderr line: stop, per [para-shared/scripts.md](../../para-shared/scripts.md) |
| 3 | `--vault` is not a vault root (`vault_root`: `projects/` plus `areas/` or `archive/`, plus `CLAUDE.md`) | `vault` and `clone` (the clone is still checked, so both reasons print at once) |
| 4 | `--clone` is not a git repository, `--ref` does not resolve, `--worktree` names a ref other than the checked-out branch or finds the clone's HEAD detached with no branch to read, or the ref carries no `CHANGELOG.md` or `base/CLAUDE.md.template` (not a para-os clone) | `vault` (full) and `clone` (with `error`) |
| 5 | Neither `--ref` nor `--worktree` was given and the clone has no `origin/stable` branch yet (`clone.stable_missing: true`) | As exit 4 |
| 6 | No `--clone`, and no folder at `$PARAOS_HOME/para-os` (`find_clone`) | `vault` and `clone` (`path` and `source` `null`, with `error`) |

## The output

| Block | Holds |
|---|---|
| `vault` | `path`, `root`, `missing`, `hint`; `declarations` (the library's, unchanged); `claude_md_lines` (`wc -l` semantics - newline count, not `splitlines()` length); `git.repo`, `git.dirty`, `git.untracked_in_scope`, `git.ignored_in_scope` (files under `CLAUDE.md` and `.claude/` git does not track or does ignore - Precondition 5) |
| `clone` | `path`, `source` (`explicit`\|`default`), `ref`, `ref_commit`, `worktree`, `checked_out` (`branch`, `commit`), `origin_stable`, `same_commit` (name groups sharing one commit), `dirty`, `dirty_masters` (the `dirty` paths a master is read from, Precondition 3), `ref_merged` (is the ref an ancestor of `origin/stable`; `null` with no `origin/stable`), `stable_missing`, `error` on exit 4, 5 or 6 |
| `masters` | `template` (the library's `master_template` result: `base/CLAUDE.md.template`), `addons` (one row per declared flavor and module: `name`, `kind`, `root` or `null` with `reported` or `carried_forward`) |
| `delta` | `vault_marker`, `vault_marker_raw`, `legacy`, `master_marker`, `verdict` (`equal`\|`behind`\|`ahead`\|`no-marker`\|`unverified`), `entries` (each `{revision, line, items, reactions}`: its bold-led paragraphs and its `Reaction:` lines), `current` (equal only) |
| | `unverified`: the master's own marker could not be read (`master_marker: null`: no `<!-- para-os-template: -->` comment in the resolved template, or the read failed). Report it as that, not as a vault-side problem. |
| `baseline` | `commit`, `source` (`ref-tip`\|`log-S`\|`null`), `template`, `reason` |
| `skeleton` | `rows`: one per file the resolved master ships (`vault_path`, `master`, `present`, `identical`, `folder_has_content`); `triage_readme` |
| `rules` | One row per `.claude/rules/*.md` the vault has: `file`, `master`, `paths`, `paths_retired` (globs opening on `resources/mds/`, the retired collected-state twins, taken out of `paths`), `master_paths`, `paths_missing`, `paths_extra` (both `null` with no `master`), `kind` (`shape`\|`convention`\|`mixed`), `anchors`, `pointer` |
| `sections` | One row per flavor or module whose `CLAUDE.md.sections` the ref carries, declared or not (`declared`; an undeclared one only where the vault states a paragraph of some version of it): `name`, `master`, and per `## ` heading `verdict` (`absent`\|`current`\|`behind`\|`differs`), `behind` (vault paragraphs matching only an earlier version along the ref: `paragraph`, `commit`, `revision`), `missing` (current paragraphs the vault lacks), `missing_new` (those the addon did not state under that heading at `baseline.commit`; `null` with no baseline), `local` (vault paragraphs no version states), `localised` (a `local` and a `missing` paragraph that are one paragraph the vault reworded, paired and taken out of both: `paragraph`, `shipped`). Paragraphs compare with whitespace collapsed, a `{{placeholder}}` matching what the vault filled in |
| `settings` | `master_keys`, `user_level` (`path`, `matching`), `vault_level` (`present`, `keys`), `missing_effective` |
| `checkboxes` | `missing` (each `bucket` and the master's `row` as written), `contact_card_level` |
| `skills` | `rows`: the `para-shared` library first (`copies`, one per installed location), then one row per bundled and user-level skill folder, each with `revisions_behind`: the count of changelog entries after the OLDEST revision any of its differing files matched, up to and including the master's own marker (`entries_between`) - `null` unless the row's own `verdict` is `behind` - see [derived-copies.md](derived-copies.md) and "The verdict" below; `ignored` (folders with no `SKILL.md`) |
| `integrations` | `rows`: one per `para-os-integration:` marker found in the vault, with the verdict, the diff, `overwrite` eligibility and the `suite` locator; `unmarked`: script files under `resources/scripts/` carrying no marker, each with `matches` (evidence, never a verdict) |
| | `unmarked[].matches` compares the script's bytes against `integrations/*` **at the ref's tip only**, not that folder's history nor the addon `pipeline/` folders. A script matching an older master, or a pipeline script, has to be recognised by eye. |
| `smoke` | `available`, `script`, `today`, `totals`, `entities`, `lanes` (`{lane: count}`), `flags`, `ideas` (length), `triage` (length); `reason` when `available` is false |
| `snapshot` | `{path: digest}` over `CLAUDE.md`, `README.md`, `.claude/settings.json`, `resources/scripts/README.md`, every `.claude/rules/*.md`, every marked integration file, every skeleton target path, and every vault file path a collected entry's Reaction names in backticks (a path into the clone's own folders excluded) - `null` where a path is absent |
| `since` | Only with `--unchanged`: `changed` (snapshot paths whose digest moved, deletions included) and `smoke` (`{count, before, after}` for every smoke count that moved) |

## The verdict (skill files and integration files alike)

The copy, line endings normalised, against the master at the ref, the master's versions along
the ref's history (the newest 200), and the clone's working tree and other branch tips. A
file's *revision* is an integration's own header marker at that commit, or - for a skill
file, which carries none - `base/CLAUDE.md.template`'s own marker at that commit.

- `identical`: the copy is the master.
- `behind`: the copy is an older version (`commit`, `revision`, `within_revision`: that
  commit's revision equals the master's own). An integration whose content is an older
  version's under a marker naming another revision adds `marker_edited: true`.
- `ahead`: the copy is the working tree's or another branch's (`source`), or matches nothing
  and is nearest the master (`source: null`).
- `both`: the copy matches nothing and is nearest an older version (`closest`).
- `marker-matches-content-differs`, integrations only: the copy carries the master's marker
  but not its content. `case: "hand-bumped"` where the content is an older version's;
  `case: null` where it matches none, unproven - the model decides from provenance.

Integration rows keep `revision` for the copy's own header marker and report the revision a
match found as `matched_revision` instead. They add `diff` (unified, capped at 200 lines,
`diff_truncated`), `diff_stat`, `overwrite` (`eligible`, `proof`:
`history-match`\|`ast`\|`whitespace`\|`null`, `proof_commit` - conditions 2 and 3 of the
sanctioned overwrite, never eligible when the verdict is `ahead`, `both` or
`marker-matches-content-differs`), and `suite` (`dir`, `files`, `runner`, `fixtures`,
`covers`, `uncovered`).

Skill rows add `missing` (master files the copy lacks), `extra` (copy files the master
lacks, `ahead` when one matches the working tree or another branch; tool caches, folder
metadata and an older install's `test_*.py` are left out on both sides) and
`names_missing_script`. A copy with no master at the ref is `ahead` where the working tree or
another branch has a folder of that name, else `unmatched`. A copy matching an addon's skill
the vault does not declare is `undeclared_addon: <name>`, skipped rather than diffed.
