# Scan links, execute, verify (Steps 6 to 8)

**A link inside a fenced code block is never rewritten**, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md).

## Step 6 - Scan inbound links (the part that breaks silently)

**`inbound.references` is every line outside the entity naming it**: read each hit and keep only real references to this entity. **`inbound.name_only`** holds a name inside a longer one (`acme` inside `acme-website-v2`), for the operator to read and never to count.

**A routed file's own filename is a second name to search.** A mention of it need not name the entity's folder, so once Step 4 has decided, re-run the plan call with one `--route <file>` per routed file and read `inbound.routed[<file>]`.

**Every hit gets repointed, whatever its `shape`** (`link_target`, `link_text`, `backtick`, `prose`): a link written as `[projects/<name>/actions.md](../../projects/<name>/actions.md)` spells the path twice, and a target-only rewrite leaves half of it lying. `in_sources` marks a hit inside a `sources/` folder: **third-party verbatim content** (`operating-discipline.md`) such as a synced publication or a transcript is not repointed, though an annotation section the vault appended below one is.

Build an **inbound-link table**: every file and line pointing at the entity, its brief, its actions, or any file being routed to `resources/`. Classify each:

- Repoint to the **archive** path, Step 1's destination.
- Repoint to the **successor** (`resources/ideas/<name>-vNext/brief.md`) when it referenced live or forward work. A link to the old `actions.md` lands on the successor's brief; if it tracked a dated commitment, repoint to wherever that commitment went instead.
- Repoint to the **resources** home, for routed living-reference files.
- Repoint to a **live external source** (a shipped URL, a public repo) when that's the truer target than a dead vault path.
- Leave as-is.

Some of these links may **already be broken** from earlier moves - fix them in the same pass.

## Step 7 - Execute

**Re-check the plan call's snapshot first**, immediately before anything below writes, per [para-shared/scripts.md](../../para-shared/scripts.md).

In order, with `git mv` so history is preserved. **`move_plan.inside` and `.inbound`** (from the plan call) name every link that sub-steps 6 and 7 below rewrite, each with the `new_href` it becomes.

**`git mv` on a folder fails whenever the index disagrees with the disk, and that is the ordinary state of a working vault.** A single uncommitted rename or deletion inside the entity aborts the entire move:

```
fatal: bad source, source=projects/<name>/sources/<a file git still holds under its old name>.md
```

Nothing moves when this happens. Unless a skill may commit there ([the commit rule](../../para-shared/operating-discipline.md#defer-to-the-vault)), a vault accumulates exactly this state between the operator's own commits: treat it as expected rather than as a failure to diagnose. **Fall back to plain `mv`**, which costs no history, since git detects the rename from content when the operator commits. Same fallback where the vault is not a git repo at all. **Never retry `git mv` file by file** - a half-moved entity is worse than either outcome. Say in the report which of the two ran.

1. Move living-reference files to `resources/<name>/`.
2. Delete approved stale snapshots, per [operating-discipline.md](../../para-shared/operating-discipline.md#deleting-a-file).
3. Create the successor scaffold if chosen.
4. Retense and clean `brief.md` and `actions.md` to their archived form. **Then re-run the plan call**, with the same `--route` arguments, and take `move_plan` from it: a link the closing edits added is in no earlier plan, and would keep its old depth after the move.
5. Move the entity to Step 1's destination. Create the destination parent if needed. **Check the destination does not already exist first**: the plan call's `destination.exists`. If it exists, stop and resolve the collision with the user - never let `mv` merge into or clobber an occupied archive path.
6. **Rewrite the links *inside* the moved folder and each routed file** per [operating-discipline.md](../../para-shared/operating-discipline.md#moving-an-entity-folder): only a link whose target lies outside what moved changes.
7. Apply every approved link repoint from the Step 6 table. A link whose display text spells the old path gets the new path as its text too.
8. **Windows note**: an empty source directory can linger ("device or resource busy") if the IDE or a terminal holds a handle - the files moved fine; remove the shell with `rmdir` (PowerShell: `Remove-Item` without `-Recurse`), which fails on a folder that is not empty, and tell the user it was a stale handle, not a failure. A folder that is not empty is reported, never forced.

## Step 8 - Verify and report

Run the verify call:

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/archive_scan.py" --vault . --verify --moved-from <old> --moved-to <new> [--routed <file>]... [--keep <file>:<line>]...
```

pass every file moved to `resources/<name>/` in Step 7.1 as its own `--routed`, and every mention of the old path the operator approved leaving as written (a dated citation, say) as its own `--keep`, which `stale_mentions_kept` then lists apart. Its fields are this step, already run:

- **`stale_links`**: every link anywhere in the vault whose resolved target still lies under the old path. Assert **zero**.
- **`stale_mentions`** (and **`stale_mentions_exempt`** for third-party content): every remaining occurrence of the old path written as text - link display text, a backtick path, bare prose. Assert zero outside the exempt list.
- **`inbound_resolved`**: `.resolved` counts and `.unresolved` lists every link from outside the new folder whose target resolves under it. Report how many resolved, not how many were rewritten.
- **`inside`**: `.resolved` and `.dangling` for every relative link inside the archived folder and each `--routed` file. A still-live historical mention inside the archived folder itself (a migration plan, say) is acceptable; flag it explicitly rather than reading it from `dangling`. `.missing` lists each `--routed` path that names no file (a typo, or a file not yet moved): it was never read, so fix the path or the move and re-run.
- **`old_path`**: `.exists` and `.empty` - the stale-handle case in Step 7's Windows note.
- **`untracked`**: files at the new path git does not track, `null` when git cannot answer (no repo, no git on PATH) rather than an empty list, so the report never reads "could not check" as "nothing untracked".
- **`clean`**: true only when every one of the above is empty (mentions outside the exempt and kept lists). Treat it as the run's own pass/fail line, not a substitute for reading the lists.

Beyond the verify call:

- Confirm the archived folder contains only history (brief, actions, one-time plans) and that the successor, if any, holds the surviving work.
- Report, once [Step 9](close-out.md) has run: what was archived and its kind, the version decision (projects only), files routed to resources, snapshots deleted, the successor created, and the count of links repointed with the table - inbound and outbound counted separately. List `untracked`: a file never committed moves on disk under a successful `git mv` too, and shows as untracked rather than renamed.
- Say whether anything was committed, and which source of [the commit rule](../../para-shared/operating-discipline.md#defer-to-the-vault) allowed or withheld it. Where a plain `mv` ran, say so here as well: `git status` shows it as deletions plus untracked files until staged. If the skill itself or a public repo was touched, flag that those need their own review.

## Edge cases

- **Entity already partly archived** (someone moved the folder but left links broken): run Steps 6 to 8 only - reconcile the links and validate the archived files.
- **Suffix collision** (`<name>-v1` already exists in archive): ask whether this is a further version or a re-archive of the same; never silently overwrite. Projects only.
- **Name collision for an idea or area** (the destination already exists): ask whether this re-archives the same entity or is a distinct one needing a disambiguating name; never silently overwrite.
