# Scan links, execute, verify (Steps 6 to 8)

Zero dangling links is the bar. The link scan runs **before** anything moves and again after, because the second run is the only proof.

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

Build an **inbound-link table**: every file and line pointing at the entity, its brief, its actions, or any file being routed to `resources/`. Classify each:

- Repoint to the **archive** path (`archive/projects/<name>[-v1]/...` for a project, `archive/ideas/<name>/...` for an idea).
- Repoint to the **successor** (`resources/ideas/<name>-vNext/brief.md`) when it referenced live or forward work. A link to the old `actions.md` lands on the successor's brief; if it tracked a dated commitment, repoint to wherever that commitment went instead.
- Repoint to the **resources** home, for routed living-reference files.
- Repoint to a **live external source** (a shipped URL, a public repo) when that's the truer target than a dead vault path.
- Leave as-is.

Some of these links may **already be broken** from earlier moves - fix them in the same pass.

## Step 7 - Execute

In order, with `git mv` / `git rm` so history is preserved (fall back to plain `mv` / `rm` if not a git repo):

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
- Resolve every relative link *inside* the archived folder and any file routed to `resources/` - the half the inbound grep cannot see. A still-live historical mention inside the archived folder itself (a migration plan, say) is acceptable; flag it explicitly.
- Confirm the archived folder contains only history (brief, actions, one-time plans) and that the successor, if any, holds the surviving work.
- Report: what was archived (project or idea), the version decision (projects only), files routed to resources, snapshots deleted, the successor created, and the count of links repointed with the table - inbound and outbound counted separately, since they come from different scans.
- Remind the user that nothing is committed (per the no-commit convention) and, if the skill itself or a public repo was touched, that those need their own review.

## Edge cases

- **Entity already partly archived** (someone moved the folder but left links broken): run Steps 6 to 8 only - reconcile the links and validate the archived files.
- **Suffix collision** (`<name>-v1` already exists in archive): ask whether this is a further version or a re-archive of the same; never silently overwrite. Projects only.
- **Idea name collision** (`archive/ideas/<name>/` already exists): ask whether this re-archives the same idea or is a distinct one needing a disambiguating name; never silently overwrite.
