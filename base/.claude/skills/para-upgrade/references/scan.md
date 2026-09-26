# Scanning the vault and the clone (Phase 0, Phase 3, the mechanical half of Phase 2, the Phase 5 re-checks)

Everything between "a vault and a local para-os clone" and "a full account of where the vault
stands against the ref: the delta, the baseline, what skeleton files are missing, what every
rule file, skill copy and integration script says against its master, a smoke-test baseline,
and a snapshot to re-check before the marker is stamped". Mechanical: no judgment lives
here, per [delta.md](delta.md), [rules-and-skeleton.md](rules-and-skeleton.md) and
[derived-copies.md](derived-copies.md) - this file is the specification those three already
state, read as one scan.

`scripts/upgrade_scan.py` implements every rule below over `para-shared/scripts/paraos_vault.py`
(`declarations`, the clone readers `clone_ref`, `clone_read`, `clone_files`, `addon_root` and
`master_template`, the changelog and template-marker readers, `normalised`, `snapshot`), and
`scripts/test_upgrade_scan.py` pins each rule to a case.

```bash
py -3 "<this skill's base directory>/scripts/upgrade_scan.py" --vault <path> --clone <path> \
    [--ref origin/main] [--worktree] [--today YYYY-MM-DD] [--user-skills DIR] \
    [--user-settings FILE] [--unchanged EARLIER_SCAN.json] [--indent N]
```

## Exit codes

| Code | Meaning | What prints |
|---|---|---|
| 0 | Answered | Every block below |
| 2 | The shared library is missing or fails to import | Nothing but a stderr line: run the by-hand fallback |
| 3 | `--vault` is not a vault root (`vault_root`: `projects/` plus `areas/` or `archive/`, plus `CLAUDE.md`) | `vault` and `clone` (best-effort: clone is still checked, so a script that will fail on both prints both reasons at once) |
| 4 | `--clone` is not a git repository, `--ref` does not resolve, `--worktree` names a ref other than the checked-out branch or finds the clone's HEAD detached with no branch to read, or the ref carries no `CHANGELOG.md` or `base/CLAUDE.md.template` (not a para-os clone) | `vault` (full) and `clone` (with `error`) |

A collected vault is **never refused**: `CLAUDE.md` and `.claude/` are on `flip.ps1`'s
denylist and stay in place, so the scan reports `collected: true`, resolves skeleton
presence through the collected name, and the `smoke` block reports `brief_scan.py`'s own
refusal (exit 2) rather than refusing itself.

## The output

| Block | Holds |
|---|---|
| `vault` | `path`, `root`, `missing`, `hint`; `declarations` (the library's, unchanged); `collected`; `claude_md_lines` (`wc -l` semantics - newline count, not `splitlines()` length); `git.repo`, `git.dirty`, `git.untracked_in_scope`, `git.ignored_in_scope` (files under `CLAUDE.md` and `.claude/` git does not track or does ignore - Precondition 5) |
| `clone` | `path`, `ref`, `ref_commit`, `worktree`, `checked_out` (`branch`, `commit`), `origin_main`, `same_commit` (name groups sharing one commit), `dirty`, `ref_merged` (is the ref an ancestor of `origin/main`; `null` with no `origin/main`), `error` on exit 4 |
| `masters` | `template` (the library's `master_template` result), `skeleton_overlay`, `addons` (one row per declared delivery/flavor/module: `name`, `kind`, `root` or `null` with `reported` or `carried_forward`) |
| `delta` | `vault_marker`, `vault_marker_raw`, `legacy`, `master_marker`, `verdict` (`equal`\|`behind`\|`ahead`\|`no-marker`\|`unverified`), `entries` (each `{revision, line, items, reactions}`), `current` (equal only) |
| | `unverified` fires when the master's own marker cannot be read at all (`master_marker: null` - the resolved template carries no `<!-- para-os-template: -->` comment, or the read itself failed). Report it as "the master's own marker could not be read" rather than a vault-side problem. |
| `baseline` | `commit`, `source` (`ref-tip`\|`log-S`\|`null`), `template`, `reason` |
| `skeleton` | `rows`: one per file the resolved master ships (`vault_path`, `master`, `present`, `identical`, `collected_as`, `folder_has_content`); `triage_readme` |
| `rules` | One row per `.claude/rules/*.md` the vault has: `file`, `master`, `paths`, `master_paths`, `paths_missing`, `paths_extra`, `kind` (`shape`\|`convention`\|`mixed`), `anchors`, `doubled`, `pointer` |
| `settings` | `master_keys`, `user_level` (`path`, `matching`), `vault_level` (`present`, `keys`), `missing_effective` |
| `skills` | `rows`: the `para-shared` library first (`copies`, one per installed location), then one row per bundled and user-level skill folder, each with `revisions_behind`: the count of changelog entries after the OLDEST revision any of its differing files matched, up to and including the master's own marker (`entries_between`) - `null` unless the row's own `verdict` is `behind` - see [derived-copies.md](derived-copies.md) and "The verdict" below; `ignored` (folders with no `SKILL.md`) |
| `integrations` | `rows`: one per `para-os-integration:` marker found in the vault, with the verdict, the diff, `overwrite` eligibility and the `suite` locator; `unmarked`: script files under `resources/scripts/` (and a read-only-iPad vault's root pipeline files) carrying no marker, each with `matches` (evidence, never a verdict) |
| | `unmarked[].matches`'s actual reach is narrower than a full history search: it compares the unmarked script's bytes against `integrations/*` **at the ref's own tip only** - not that folder's history, and not the addon `pipeline/` folders a delivery's scripts ship from. A script that matches an older version of a master, or a pipeline script, is missed here and has to be recognised by eye. |
| | Master resolution for both `rules` and `skills`, where more than one declared addon could carry a file of the same name, tries base first (`base/.claude/rules/`, or for a skill `base/.claude/skills/` then `multi-vault/`), then the delivery, then the flavor, then each module in the order `**Modules:**` lists them; the first match wins. |
| `smoke` | `available`, `script`, `today`, `totals`, `entities`, `lanes` (`{lane: count}`), `flags`, `ideas` (length), `triage` (length); `reason` when `available` is false |
| `snapshot` | `{path: digest}` over `CLAUDE.md`, `README.md`, `.claude/settings.json`, `resources/scripts/README.md`, every `.claude/rules/*.md`, every marked integration file, and every skeleton target path - `null` where a path is absent |
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
lacks, `ahead` when one matches something in O; both sides leave out tool caches and folder metadata, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `*.pyc`, `desktop.ini`, `.DS_Store` and `Thumbs.db`, since a suite run in place or a sync client writes them and counted they read an identical copy as ahead), `names_missing_script`, and `suite` when the
copy ships its own `scripts/`. A copy with no master at the ref *and* a folder of that name
in O is `ahead`, never `unmatched`; only with neither is it `unmatched`. A copy matching an
addon's skill the vault does not declare is `undeclared_addon: <name>`, skipped rather than
diffed - searched under whichever addon layout the ref actually carries (`addons/`, or the
older `delivery/` + `flavors/` split), since a ref on the older layout has no `addons/`
folder to search at all.

**The rest of this file is that script's specification, and the fallback when it cannot run**
(no Python, a missing file, exit 2, any non-zero exit other than 3 and 4). Read this file
when a result looks wrong, when changing what the scan means, or when running the scan by
hand. A hand-run scan says so in the summary, in one line.

## By hand, where each rule actually lives, and the commands

Run every `diff` and `git log ... -S` below via bash (Git Bash or WSL), never PowerShell -
`<(...)` process substitution is bash-only, and PowerShell's `diff` alias neither accepts it
nor errors usefully. Where only PowerShell is available, write both normalised sides to temp
files first and diff those instead.

1. **`vault`** - the library's root rule, `declarations`, and `is_collected`, by hand. Precondition
   5's scope: `git ls-files -- CLAUDE.md .claude` (tracked), `git status --porcelain --
   CLAUDE.md .claude` (dirty and untracked), `git check-ignore -- CLAUDE.md .claude/**`
   (ignored).

2. **`clone`** - `git -C <clone> rev-parse --verify <ref>^{commit}`; `git -C <clone>
   symbolic-ref --short HEAD` for the checked-out branch; `git -C <clone> merge-base
   --is-ancestor <ref> origin/main` (exit 0 = ancestor, 1 = not, anything else = unknown);
   `git -C <clone> status --porcelain` for `dirty`. Not a para-os clone unless both
   `git show <ref>:CHANGELOG.md` and `git show <ref>:base/CLAUDE.md.template` succeed.

3. **`masters`** - [delta.md](delta.md)'s "Resolving the master": walk `addons/<name>/`,
   else `delivery/<name>/` and `flavors/<name>/` at a ref with no `addons/` folder, per
   declared delivery, flavor and module.

4. **`delta`** - the vault's marker: the first `<!-- para-os-template: -->` comment in
   `CLAUDE.md`, read literally (`raw`) and as the legacy-renumbered form (`2026.08` reads as
   `2026.08.01`). The master's marker: the same comment in the resolved template, never
   `CHANGELOG.md`. Collect every `## <revision>` entry from `CHANGELOG.md` at the ref whose
   revision is greater than the vault's marker and at most the master's, in order. Within an
   entry, each paragraph (blank-line or bullet-line separated) that opens on a bold sentence
   is an item; a paragraph carrying `Reaction:` or `Reactions:` contributes that sentence
   onward as a reaction.

5. **`baseline`** - `git show <ref>:<template>`; if its marker still matches the vault's,
   that is the baseline (`ref-tip`). Otherwise `git log <ref> -S"<!-- para-os-template:
   <raw marker> -->" -- <template> <its older-layout paths>`, take the newest commit listed,
   and its **parent** (`git rev-parse <that commit>^1`) is the baseline. **Walk the named
   ref, never HEAD**, and search the raw marker **with its comment
   delimiters** so a legacy `2026.08` never matches `2026.08.01` by substring.

6. **`skeleton`** - enumerate `base/` at the ref minus `base/.claude/skills/**`,
   `base/CLAUDE.md.template` (Phase 1's, not Phase 2's) and `base/bootstrap-prompt.md`
   (setup-only); overlay the delivery's `skeleton/` files (its own
   `CLAUDE.md.template` excluded the same way); add each declared flavor's and module's
   `.claude/rules/*` and `skeleton/**`. `README.md.template` maps to a vault `README.md`.
   For each, compare `git show <ref>:<master>` against the vault's own file, normalised - or,
   on a collected vault, against `resources/mds/<path with every "/" turned "__">`.

7. **`rules`** - for each `.claude/rules/*.md`: its `paths:` frontmatter list; its master
   (`base/.claude/rules/<name>`, else a declared addon's file of the same name) and that
   file's own `paths:`; `kind` from the three anchors (`**Order:**`, `## The shape`,
   `## Placeholders` as the last `##`) - all three present is `shape`, none is `convention`,
   anything else is `mixed`; on a collected delivery, every plain glob needs its doubled
   twin (interior `/` -> `__`, a leading `**/` -> `*__`, a trailing `/**` or `/*` -> `__*`,
   prefixed `resources/mds/`); the pointer sentence in `CLAUDE.md` naming the file.

8. **`settings`** - `base/.claude/settings.json` at the ref against `~/.claude/settings.json`
   and the vault's own `.claude/settings.json`, key by key.

9. **`skills`** and **`integrations`** - [derived-copies.md](derived-copies.md)'s "Sweep for"
   and "Installed integration scripts" sections state every rule above by hand: the master
   resolution order, the rename/ambiguous/unresolvable ladder, the sanctioned-overwrite
   conditions, and the suite locator. The verdict itself is stated once, above, since a skill
   file and an integration script are diffed by the same five rules.

10. **`smoke`** - `python3 "<skills folder>/para-daily-brief/scripts/brief_scan.py" --vault
    <vault> --indent 2`, per [delta.md](delta.md)'s "Smoke-test baseline". Non-zero exit
    (a collected vault included), or no Python: run `/para-daily-brief week` instead and
    keep the same counts, agenda excluded.

11. **`snapshot`**, **`since`** - `paraos_vault.py`'s own `snapshot`/`changed` functions, or
    by hand: a SHA-1 of each file's bytes, `null` where absent; a changed path is one whose
    digest no longer matches.
