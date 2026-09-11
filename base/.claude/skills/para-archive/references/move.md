# Scan links, execute, verify (Steps 6 to 8)

Zero dangling links is the bar. **Links inside a fenced code block are neither scanned nor rewritten**, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md) - re-depthing a sample link corrupts a code block that was correct, and in a diff that corruption is indistinguishable from the fix beside it. The link scan runs **before** anything moves and again after, because the second run is the only proof.

## Step 6 - Scan inbound links (the part that breaks silently)

Before moving anything, grep the **entire vault** for references to the entity's current path and to files moving out of it. Use the source bucket from Step 1 (`projects/<name>/` for a project, `resources/ideas/<name>/` for an idea):

```bash
# from vault root - find every inbound reference (project example)
grep -rn "projects/<name>/" --include="*.md" .
grep -rn "<name>" --include="*.md" . | grep -E "\]\(|\.md"   # catch relative links by filename
```

```bash
# idea example
grep -rn "resources/ideas/<name>/" --include="*.md" .
```

**A reference is anywhere the path is written, not only a `](...)` target.** That is why the greps above search for the path rather than for link syntax, and why every hit gets repointed: the target of a markdown link, the **display text** of one (a link written as `[projects/<name>/actions.md](../../projects/<name>/actions.md)` spells the path twice, and a target-only rewrite leaves half of it lying), a path quoted in backticks as a source citation, and a bare path in prose. Only the first of those 404s on a click, so the rest never look broken while still asserting a path that no longer exists, which is what `/para-deep-clean` audits for. The exception is **third-party verbatim content** (`operating-discipline.md`): a synced publication or a transcript is not repointed, though an annotation section the vault appended below one is.

Build an **inbound-link table**: every file and line pointing at the entity, its brief, its actions, or any file being routed to `resources/`. Classify each:

- Repoint to the **archive** path (`archive/projects/<name>[-v1]/...` for a project, `archive/ideas/<name>/...` for an idea).
- Repoint to the **successor** (`resources/ideas/<name>-vNext/brief.md`) when it referenced live or forward work. A link to the old `actions.md` lands on the successor's brief; if it tracked a dated commitment, repoint to wherever that commitment went instead.
- Repoint to the **resources** home, for routed living-reference files.
- Repoint to a **live external source** (a shipped URL, a public repo) when that's the truer target than a dead vault path.
- Leave as-is.

Some of these links may **already be broken** from earlier moves - fix them in the same pass.

## Step 7 - Execute

In order, with `git mv` / `git rm` so history is preserved.

**`git mv` on a folder fails whenever the index disagrees with the disk, and that is the ordinary state of a working vault.** A single uncommitted rename or deletion inside the entity aborts the entire move:

```
fatal: bad source, source=projects/<name>/sources/<a file git still holds under its old name>.md
```

Nothing moves when this happens. No skill here ever commits, so a vault accumulates exactly this state between the operator's own commits: treat it as expected rather than as a failure to diagnose. **Fall back to plain `mv` / `rm`**, which costs no history, since git detects the rename from content when the operator commits. Same fallback where the vault is not a git repo at all. **Never retry `git mv` file by file** - a half-moved entity is worse than either outcome. Say in the report which of the two ran.

1. Move living-reference files to `resources/<name>/`.
2. Delete approved stale snapshots.
3. Create the successor scaffold if chosen.
4. Retense and clean `brief.md` and `actions.md` to their archived form.
5. Move the entity to its archive bucket: `projects/<name>/` to `archive/projects/<name>[-v1]/`, or `resources/ideas/<name>/` to `archive/ideas/<name>/`. Create the destination parent if needed. **Check the destination does not already exist first** (`test -e "<dst>" && echo EXISTS`). If it exists, stop and resolve the collision with the user - never let `mv` merge into or clobber an occupied archive path.
6. **Re-depth the links *inside* the moved folder** ([operating-discipline.md](../../para-shared/operating-discipline.md#moving-an-entity-folder)). Two of the four moves above change depth, in opposite directions:

   | Move | Depth | Each outbound link |
   |---|---|---|
   | `projects/<name>/` to `archive/projects/<name>[-v1]/` | 2 to 3 | gains one `../` |
   | `resources/ideas/<name>/` to `archive/ideas/<name>/` | 3 to 3 | unchanged |
   | routed file, `projects/<name>/` to `resources/<name>/` | 2 to 2 | unchanged |
   | routed file, `resources/ideas/<name>/` to `resources/<name>/` | 3 to 2 | loses one `../` |

   Depths are the entity folder's own; a file in a `sources/` subfolder starts one deeper and shifts by the same amount.
7. Apply every approved link repoint from the Step 6 table.
8. **Windows note**: an empty source directory can linger ("device or resource busy") if the IDE or a terminal holds a handle - the files moved fine; `rm -rf` the empty shell and tell the user it was a stale handle, not a failure.

## Step 8 - Verify and report

- Re-run the inbound-link grep. Assert **zero** stale references remain to the old source path.
- **Then resolve every repointed link to a file that exists.** The grep only proves the old path is gone; a repoint written at the wrong depth passes it and still dangles, which is the likeliest error in the whole run. Resolve each rewritten target against the filesystem, percent-decoding it first, and report how many resolved rather than how many were rewritten. An assertion that cannot fail is not a check.
- Resolve every relative link *inside* the archived folder and any file routed to `resources/` - the half the inbound grep cannot see. A still-live historical mention inside the archived folder itself (a migration plan, say) is acceptable; flag it explicitly.
- Confirm the archived folder contains only history (brief, actions, one-time plans) and that the successor, if any, holds the surviving work.
- Report: what was archived (project or idea), the version decision (projects only), files routed to resources, snapshots deleted, the successor created, and the count of links repointed with the table - inbound and outbound counted separately, since they come from different scans.
- Remind the user that nothing is committed, attributing that to this skill's own discipline (`operating-discipline.md`: stop after staging) and **not** to a vault rule. Several vaults commit freely, and citing a convention a vault does not have sends the operator looking for it. Where a plain `mv` ran, say so here as well, because `git status` will show the move as a block of deletions plus untracked files until they stage it. If the skill itself or a public repo was touched, flag that those need their own review.

## Edge cases

- **Entity already partly archived** (someone moved the folder but left links broken): run Steps 6 to 8 only - reconcile the links and validate the archived files.
- **Suffix collision** (`<name>-v1` already exists in archive): ask whether this is a further version or a re-archive of the same; never silently overwrite. Projects only.
- **Idea name collision** (`archive/ideas/<name>/` already exists): ask whether this re-archives the same idea or is a distinct one needing a disambiguating name; never silently overwrite.
