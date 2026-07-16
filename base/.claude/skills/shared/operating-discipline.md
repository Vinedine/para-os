# Operating discipline (shared across skills)

Cross-skill rules for *how a skill behaves* when it changes files. This is not a vault convention (those live in each vault's `CLAUDE.md`) - it's the safety discipline every file-mutating skill follows. `/para-triage`, `/para-deep-clean`, and `/para-archive` all defer here so the rules stay in one place.

## Approval discipline

- **Show before you change.** Build a proposal (a table of what will change and where) and surface it *before* applying anything. Wait for explicit user approval.
- **Non-destructive normalizations may batch.** Renames, link repoints, casing/naming fixes, and moves between folders can be approved as a group.
- **Destructive operations require individual approval.** Deletions - and, per some vaults, moves between PARA buckets - are approved one by one. No batching, no exceptions.
- **Never delete a file without comparing its actual contents first.** Matching filenames, sizes, or "looks redundant" is not proof. Read both, confirm the survivor truly supersedes, then ask.

## Preserve, don't rewrite

- **Preserve facts verbatim** when reorganizing or retensing a file. Reorganize and add missing structure; never lose information.
- **Don't editorialize during a structural pass.** Fixing wording is a separate, dedicated pass - not something a cleanup/triage/archive run does silently.

## Defer to the vault

- **Read the vault's `CLAUDE.md` first** for naming conventions, language rules, the action-marker syntax, the PARA/archive layout, and the "do not add" list. The skill brings *procedure*; the vault brings *parameters*.
- **Never invent dates or completion markers.** Use the vault's marker syntax; leave externally-gated items undated.
- **Never commit.** Stop after staging; the user commits manually.
