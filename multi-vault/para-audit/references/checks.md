# The audit, in judgment

`scripts/audit_scan.py` runs every check over the shared vault library and `/para-upgrade`'s scan, and its docstring states each rule. This file is the judgment its output leaves to the skill.

## Which vaults

The registry's schema is `/para-ingest`'s [registry.md](../../para-ingest/references/registry.md). What the audit makes of each entry, in registry order:

| Entry | Reported as | Audited |
|---|---|---|
| `retired: true` | `RETIRED (excluded)` | No |
| No `name`, or no `path` | `INVALID` | No |
| `path` is not a folder: not mounted, or moved | `UNREACHABLE` | No |
| `path` holds no `CLAUDE.md` | `UNREACHABLE` | No |
| `active: false` | a row like any other | **Yes**: it only takes a vault out of `/para-ingest` |

**When every registered vault on one drive is unreachable, it is the drive** (`drives`). Say so once.

## Reading the findings

- **`route: upgrade`** resolves with `/para-upgrade` run in that vault: say it once per vault, not once per finding.
- **A type mismatch is the operator's call.** The registry and the vault say different things and either may be the stale one; offer both corrections.
- **A vault ahead of the master** is on a draft revision, or the clone is stale: `git -C <clone> fetch`, or audit again with `ref=` naming the revision it is on.
- **A topic-file observation** may be a convention the vault grew on purpose. Report it, never as a defect.
- **Size** is about how reliably a session follows the file. The template's lever is extracting procedure to `.claude/rules/` with a one-line pointer left behind, never cutting the vault's own rules.
