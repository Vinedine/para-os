# The audit, by hand and in judgment

`scripts/audit_scan.py` runs every check below over the shared vault library and `/para-upgrade`'s scan, and its docstring states each rule. This file is the by-hand path for when the scan cannot run, and the judgment its output leaves to the skill.

## Which vaults

The registry's schema is `/para-ingest`'s [registry.md](../../para-ingest/references/registry.md). What the audit makes of each entry, in registry order:

| Entry | Reported as | Audited |
|---|---|---|
| `retired: true` | `RETIRED (excluded)` | No |
| No `name`, or no `path` | `INVALID` | No |
| `path` is not a folder: not mounted, or moved | `UNREACHABLE` | No |
| `path` holds no `CLAUDE.md` | `UNREACHABLE` | No |
| `active: false` | a row like any other | **Yes**: it only takes a vault out of `/para-ingest` |

**When every registered vault on one drive is unreachable, it is the drive**: a Windows drive letter or share, or a `/Volumes/<x>`, `/mnt/<x>` or `/media/<user>/<x>` mount, holding two or more of them or with its own root missing. Say so once.

## By hand

Say in one line that the audit ran by hand, and why. Read each master with `git -C <clone> show <ref>:<path>` and list one with `git -C <clone> ls-tree -r --name-only <ref> <folder>`, never from the clone's files on disk. **Without a shell git cannot run: checks 1, 4, 5 and 6 and the add-on names in 3 read `not judged`, with that reason,** and no closing line names a vault to upgrade. Checks 2, 7 and the rest of 3 still run with `Read` and `Grep`.

1. **Revision.** The vault's first `<!-- para-os-template: YYYY.MM.NN -->` against the one in `<ref>:base/CLAUDE.md.template`. Equal: `aligned`. Older: `behind N`, naming the `## YYYY.MM.NN` headings of `<ref>:CHANGELOG.md` newer than the vault's, oldest first. Newer: `ahead <rev>`, and checks 4 to 6 and the add-on names are `not judged`. None: `UNSTAMPED`, behind by every revision. A newer marker in the clone's working-tree template is mentioned once as in development and is never the bar.
2. **Type.** The `**Type:**` line against the entry's `kind`, ignoring case and reading spaces, dots and underscores as hyphens. A mismatch names both.
3. **Declarations.** The lines under the title run to the first line that is not a bold-led field, the marker comment skipped. In them: a `**Type:**` line; `**Type:**`, `**Flavor:**` and `**Modules:**` each written exactly `**Name:** value`; no `{{` placeholder; one flavor; and an `addons/<name>/` at the ref for each add-on named. Also a finding: a `para-os-template` comment that does not parse, one of the three lines found below those lines (nothing reads it there), and any other bold field among them, `**Delivery:**` included.
4. **Rules.** Every file under `base/.claude/rules/` and each declared add-on's `.claude/rules/` at the ref has a copy in the vault's `.claude/rules/`. A file there that no master ships and no other audited vault of the same `kind` carries is an observation; with no such vault, there is nothing to compare. A `voice-*.md` profile is one person's, never such a file.
5. **Integrations.** Each vault file carrying `para-os-integration: <name> <revision>` in its first 80 lines, `.claude/skills/` aside, against `integrations/<name>/<file>` at the ref, line endings normalised: identical, or which older revision its content is.
6. **Skills.** Each `.claude/skills/<name>/` copy named `para-*`, or one a master ships, file by file against its master at the ref, line endings normalised. A vault's own skill is not a copy.
7. **Size.** `CLAUDE.md`'s line count against 200.

## Reading the findings

- **`route: upgrade`** resolves with `/para-upgrade` run in that vault: say it once per vault, not once per finding.
- **A type mismatch is the operator's call.** The registry and the vault say different things and either may be the stale one; offer both corrections.
- **A vault ahead of the master** is on a draft revision, or the clone is stale: `git -C <clone> fetch`, or audit again with `ref=` naming the revision it is on.
- **A topic-file observation** may be a convention the vault grew on purpose. Report it, never as a defect.
- **Size** is about how reliably a session follows the file. The template's lever is extracting procedure to `.claude/rules/` with a one-line pointer left behind, never cutting the vault's own rules.
