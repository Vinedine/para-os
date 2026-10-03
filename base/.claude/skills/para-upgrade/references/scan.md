# Scanning the vault and the clone (Phase 0, Phase 3, the mechanical half of Phase 2, the Phase 5 re-checks)

Mechanical: the
judgment lives in [delta.md](delta.md), [rules-and-skeleton.md](rules-and-skeleton.md) and
[derived-copies.md](derived-copies.md), whose rules this file reads as one scan.

`scripts/upgrade_scan.py` implements every rule below over the shared library,
`para-shared/scripts/paraos_vault.py`.

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
| 2 | The shared library is missing or fails to import | Nothing but a stderr line: run the by-hand fallback |
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
| `delta` | `vault_marker`, `vault_marker_raw`, `legacy`, `master_marker`, `verdict` (`equal`\|`behind`\|`ahead`\|`no-marker`\|`unverified`), `entries` (each `{revision, line, items, reactions}`), `current` (equal only) |
| | `unverified`: the master's own marker could not be read (`master_marker: null`: no `<!-- para-os-template: -->` comment in the resolved template, or the read failed). Report it as that, not as a vault-side problem. |
| `baseline` | `commit`, `source` (`ref-tip`\|`log-S`\|`null`), `template`, `reason` |
| `skeleton` | `rows`: one per file the resolved master ships (`vault_path`, `master`, `present`, `identical`, `folder_has_content`); `triage_readme` |
| `rules` | One row per `.claude/rules/*.md` the vault has: `file`, `master`, `paths`, `paths_retired` (globs no master carries any more, taken out of `paths`), `master_paths`, `paths_missing`, `paths_extra` (both `null` with no `master`), `kind` (`shape`\|`convention`\|`mixed`), `anchors`, `pointer` |
| `sections` | One row per flavor or module whose `CLAUDE.md.sections` the ref carries, declared or not (`declared`; an undeclared one only where the vault states a paragraph of some version of it): `name`, `master`, and per `## ` heading `verdict` (`absent`\|`current`\|`behind`\|`differs`), `behind` (vault paragraphs matching only an earlier version along the ref: `paragraph`, `commit`, `revision`), `missing` (current paragraphs the vault lacks), `missing_new` (those the addon did not state under that heading at `baseline.commit`; `null` with no baseline), `local` (vault paragraphs no version states), `localised` (a `local` and a `missing` paragraph that are one paragraph the vault reworded, paired and taken out of both: `paragraph`, `shipped`). Paragraphs compare with whitespace collapsed, a `{{placeholder}}` matching what the vault filled in |
| `settings` | `master_keys`, `user_level` (`path`, `matching`), `vault_level` (`present`, `keys`), `missing_effective` |
| `skills` | `rows`: the `para-shared` library first (`copies`, one per installed location), then one row per bundled and user-level skill folder, each with `revisions_behind`: the count of changelog entries after the OLDEST revision any of its differing files matched, up to and including the master's own marker (`entries_between`) - `null` unless the row's own `verdict` is `behind` - see [derived-copies.md](derived-copies.md) and "The verdict" below; `ignored` (folders with no `SKILL.md`) |
| `integrations` | `rows`: one per `para-os-integration:` marker found in the vault, with the verdict, the diff, `overwrite` eligibility and the `suite` locator; `unmarked`: script files under `resources/scripts/` carrying no marker, each with `matches` (evidence, never a verdict) |
| | `unmarked[].matches` compares the script's bytes against `integrations/*` **at the ref's tip only**, not that folder's history nor the addon `pipeline/` folders. A script matching an older master, or a pipeline script, has to be recognised by eye. |
| | Master resolution for both `rules` and `skills`, where more than one declared addon could carry a file of the same name, tries base first (`base/.claude/rules/`, or for a skill `base/.claude/skills/` then `multi-vault/`), then the flavor, then each module in the order `**Modules:**` lists them; the first match wins. |
| `smoke` | `available`, `script`, `today`, `totals`, `entities`, `lanes` (`{lane: count}`), `flags`, `ideas` (length), `triage` (length); `reason` when `available` is false |
| `snapshot` | `{path: digest}` over `CLAUDE.md`, `README.md`, `.claude/settings.json`, `resources/scripts/README.md`, every `.claude/rules/*.md`, every marked integration file, every skeleton target path, and every vault file path a collected entry's Reaction names in backticks (a path into the clone's own folders excluded) - `null` where a path is absent |
| `since` | Only with `--unchanged`: `changed` (snapshot paths whose digest moved, deletions included) and `smoke` (`{count, before, after}` for every smoke count that moved) |

## The verdict (skill files and integration files alike)

C = `normalised(copy)`, M = `normalised(master)`, H = the versions of the master path along
the ref's history, the newest 200 of them (an older match is not searched; newest first, H[0] normally M itself), O = the clone's working tree
plus every other local and remote-tracking branch tip. `strip(x)` replaces an integration's
own marker with a fixed token before comparing (integrations only). A file's *revision* is
an integration's own header marker at that commit, or - for a skill file, which carries none
- `base/CLAUDE.md.template`'s own marker at that commit.

1. `C == M` -> `identical`.
2. `C == H[i]`, `i > 0` -> `behind` (`commit`, `revision` - `matched_revision` on an integration row -, `within_revision`: that commit's
   revision equals the master's own).
3. `C` matches some source in O -> `ahead` (`source`: which one).
4. Integrations only: `strip(C) == strip(H[i])` and `H[i]`'s revision differs from `C`'s own
   -> `marker-matches-content-differs` (`case: "hand-bumped"`) when `C`'s marker equals the
   master's, else `behind` with `marker_edited: true`.
5. No exact match: `closest` = the version among `{M} + H` with the smallest difference from
   `C`. Integrations with `C`'s marker equal to the master's -> `marker-matches-content-differs`
   (`case: null`, unproven - the model decides from provenance). Otherwise `closest == M` ->
   `ahead` (`source: null`); `closest` older -> `both`.

Integration rows keep `revision` for the copy's own header marker and report the revision a
rule 2 or rule 4 match found as `matched_revision` instead. Integration rows add `diff` (unified, capped at 200 lines, `diff_truncated`), `diff_stat`,
`overwrite` (`eligible`, `proof`: `history-match`\|`ast`\|`whitespace`\|`null`,
`proof_commit` - conditions 2 and 3 of the sanctioned overwrite, never eligible when the
verdict is `ahead`, `both` or `marker-matches-content-differs`), and `suite` (`dir`, `files`,
`runner`, `fixtures`, `covers`, `uncovered`).

Skill rows add `missing` (master files the copy lacks), `extra` (copy files the master
lacks, `ahead` when one matches something in O; both sides leave out tool caches and folder metadata, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `*.pyc`, `desktop.ini`, `.DS_Store` and `Thumbs.db`), `names_missing_script`, and `suite` when the
copy ships its own `scripts/`. A copy with no master at the ref *and* a folder of that name
in O is `ahead`, never `unmatched`; only with neither is it `unmatched`. A copy matching an
addon's skill the vault does not declare is `undeclared_addon: <name>`, skipped rather than
diffed - searched under whichever addon layout the ref actually carries (`addons/`, or the
older `flavors/`).

**The rest of this file is that script's specification, and the fallback when it cannot run**
(no Python, a missing file, exit 2, any non-zero exit other than 3, 4 and 5). Read this file
when a result looks wrong or when running the scan by hand. A hand-run scan says so in the summary, in one line.

## By hand, where each rule actually lives, and the commands

Run every `diff` and `git log ... -S` below via bash (Git Bash or WSL): `<(...)` is
bash-only. Where only PowerShell is available, write both normalised sides to temp files and
diff those.

1. **`vault`** - the library's root rule and `declarations`, by hand. Precondition
   5's scope: `git ls-files -- CLAUDE.md .claude` (tracked), `git status --porcelain --
   CLAUDE.md .claude` (dirty and untracked), `git check-ignore -- CLAUDE.md .claude/**`
   (ignored).

2. **`clone`** - `git -C <clone> rev-parse --verify <ref>^{commit}`; `git -C <clone>
   symbolic-ref --short HEAD` for the checked-out branch; `git -C <clone> merge-base
   --is-ancestor <ref> origin/stable` (exit 0 = ancestor, 1 = not, anything else = unknown);
   `git -C <clone> status --porcelain` for `dirty`, and of those, `CHANGELOG.md` and the
   paths under `base/`, `integrations/`, `multi-vault/` or a declared addon's folder in any
   addon layout, a collapsed untracked folder holding one of those included, for
   `dirty_masters`. Not a para-os clone unless both `git show <ref>:CHANGELOG.md` and
   `git show <ref>:base/CLAUDE.md.template` succeed.

3. **`masters`** - [delta.md](delta.md)'s "Resolving the master": walk `addons/<name>/`,
   else `flavors/<name>/` at a ref with no `addons/` folder, per declared flavor and
   module.

4. **`delta`** - the vault's marker: the first `<!-- para-os-template: -->` comment in
   `CLAUDE.md`, read literally (`raw`) and as the legacy-renumbered form (`2026.08` reads as
   `2026.08.01`). The master's marker: the same comment in the resolved template, never
   `CHANGELOG.md`. Collect every `## <revision>` entry from `CHANGELOG.md` at the ref whose
   revision is greater than the vault's marker and at most the master's, in order. Within an
   entry, each paragraph (blank-line or bullet-line separated) that opens on a bold sentence
   is an item; a paragraph carrying `Reaction:` or `Reactions:` contributes its last one
   onward as a reaction.

5. **`baseline`** - `git show <ref>:<template>`; if its marker still matches the vault's,
   that is the baseline (`ref-tip`). Otherwise `git log <ref> -S"<!-- para-os-template:
   <raw marker> -->" -- <template>`, take the newest commit listed,
   and its **parent** (`git rev-parse <that commit>^1`) is the baseline. **Walk the named
   ref, never HEAD**, and search the raw marker **with its comment delimiters**.

6. **`skeleton`** - enumerate `base/` at the ref minus `base/.claude/skills/**`,
   `base/CLAUDE.md.template` (Phase 1's, not Phase 2's) and `base/bootstrap-prompt.md`
   (setup-only); add each declared flavor's and module's `.claude/rules/*` and
   `skeleton/**`. `README.md.template` maps to a vault `README.md`. For each, compare
   `git show <ref>:<master>` against the vault's own file, normalised.

7. **`rules`** - for each `.claude/rules/*.md`: its `paths:` frontmatter list; its master
   (`base/.claude/rules/<name>`, else a declared addon's file of the same name) and that
   file's own `paths:`; `kind` from the three anchors (`**Order:**`, `## The shape`,
   `## Placeholders` as the last `##`) - all three present is `shape`, none is `convention`,
   anything else is `mixed`; `paths_missing` and `paths_extra` against the master's list,
   `null` with no master, leaving out a glob opening on `resources/mds/` (the retired
   delivery's collected-state twin), which is `paths_retired`; the pointer sentence in
   `CLAUDE.md` naming the file. **`sections`**: split each addon's
   `CLAUDE.md.sections` and the vault's `CLAUDE.md` at `## ` headings, then look up each
   vault paragraph under a shared heading in `git show <ref>:<sections file>` and in every
   version `git log <ref> -- <sections file>` lists; a `missing` paragraph is `missing_new`
   unless `git show <baseline>:<sections file>` states it under the same heading.

8. **`settings`** - `base/.claude/settings.json` at the ref against `~/.claude/settings.json`
   and the vault's own `.claude/settings.json`, key by key.

9. **`skills`** and **`integrations`** - [derived-copies.md](derived-copies.md)'s "Sweep for"
   and "Installed integration scripts" sections state every rule above by hand: the master
   resolution order, the rename/ambiguous/unresolvable ladder, the sanctioned-overwrite
   conditions, and the suite locator. The verdict is stated once, above.

10. **`smoke`** - `python3 "<skills folder>/para-daily-brief/scripts/brief_scan.py" --vault <vault> --indent 2` (Windows: `py -3`),
    per [delta.md](delta.md)'s "Smoke-test baseline". Non-zero exit
    or no Python: run `/para-daily-brief week` instead and
    keep the same counts, agenda excluded.

11. **`snapshot`**, **`since`** - `paraos_vault.py`'s own `snapshot`/`changed` functions, or
    by hand over the paths the `snapshot` row lists: a SHA-1 of each file's bytes, `null`
    where absent; a changed path is one whose digest no longer matches.
