# Operating discipline (shared across skills)

Cross-skill rules for *how a skill behaves* when it changes files. This is not a vault convention (those live in each vault's `CLAUDE.md`) - it is the safety discipline **every file-mutating skill** follows, so the rules stay in one place. A read-only skill declares that contract instead and inherits nothing here.

## Approval discipline

- **Show before you change.** Build a proposal (a table of what will change and where) and surface it *before* applying anything. Wait for explicit user approval. A pre-emptive "just do it" in the opening message does not skip the proposal; the proposal is the audit trail.
- **Non-destructive normalizations may batch.** Renames, link repoints, casing/naming fixes, and moves between folders can be approved as a group.
- **Destructive operations require individual approval.** Deletions - and, per some vaults, moves between PARA buckets - are approved one by one. No batching, no exceptions.
- **Never delete a file without comparing its actual contents first.** Matching filenames, sizes, or "looks redundant" is not proof. Read both, confirm the survivor truly supersedes, then ask.

## Preserve, don't rewrite

- **Preserve facts verbatim** when reorganizing or retensing a file. Reorganize and add missing structure; never lose information.
- **Don't editorialize during a structural pass.** Fixing wording is a separate, dedicated pass - not something a cleanup/triage/archive run does silently.
- **Never modify a file's content beyond rotating a scanned image.** No re-OCR, no re-compression, no metadata stripping.
- **Never translate a document's name.** A Dutch or French source keeps its language when it is renamed to the convention.

## Leave other people's words alone

- **Third-party verbatim content is out of scope for every normalization pass.** Synced publications, meeting transcripts and their auto-extracted "next steps", quoted correspondence, signed documents. Rewriting those is rewriting someone else's record, not tidying yours. Exclude them explicitly and name which files you excluded, so the exclusion reads as a decision rather than an oversight.
- **A checkbox inside a transcript is not a task.** It records what was said in a room. Mark the record frozen and route any surviving work into a real `actions.md`; never tick it.

## Defer to the vault

- **Read the vault's `CLAUDE.md` first** for naming conventions, language rules, the action-marker syntax, the PARA/archive layout, and the "do not add" list. The skill brings *procedure*; the vault brings *parameters*.
- **Never invent dates or completion markers.** Use the vault's marker syntax; leave externally-gated items undated.
- **Never commit.** Stop after staging; the user commits manually.
