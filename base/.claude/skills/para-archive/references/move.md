# Scan links, execute, verify (Steps 6 to 8)

Zero dangling links is the bar. **Links inside a fenced code block are neither scanned nor rewritten**, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md). The link scan runs **before** anything moves and again after, because the second run is the only proof.

## Step 6 - Scan inbound links (the part that breaks silently)

Before moving anything, grep the **entire vault** for the entity folder's name and the filename of each file routed out of it. A path grep misses a link written relative to a sibling (`../<name>/brief.md`), so read each hit and keep only real references to this entity. Git internals and installed skill copies are not vault content:

```bash
# from vault root
grep -rn --include="*.md" "<name>" . | grep -v -e '^\./\.git/' -e '^\./\.claude/skills/'
```

**A reference is anywhere the path is written, not only a `](...)` target.** That is why the scan searches for the name rather than for link syntax, and why every hit gets repointed: the target of a markdown link, the **display text** of one (a link written as `[projects/<name>/actions.md](../../projects/<name>/actions.md)` spells the path twice, and a target-only rewrite leaves half of it lying), a path quoted in backticks as a source citation, and a bare path in prose. Only the first of those 404s on a click, so the rest never look broken while still asserting a path that no longer exists, which is what `/para-deep-clean` audits for. The exception is **third-party verbatim content** (`operating-discipline.md`): a synced publication or a transcript is not repointed, though an annotation section the vault appended below one is.

Build an **inbound-link table**: every file and line pointing at the entity, its brief, its actions, or any file being routed to `resources/`. Classify each:

- Repoint to the **archive** path, Step 1's destination.
- Repoint to the **successor** (`resources/ideas/<name>-vNext/brief.md`) when it referenced live or forward work. A link to the old `actions.md` lands on the successor's brief; if it tracked a dated commitment, repoint to wherever that commitment went instead.
- Repoint to the **resources** home, for routed living-reference files.
- Repoint to a **live external source** (a shipped URL, a public repo) when that's the truer target than a dead vault path.
- Leave as-is.

Some of these links may **already be broken** from earlier moves - fix them in the same pass.

## Step 7 - Execute

In order, with `git mv` / `git rm` so history is preserved, except on the [read-only iPad delivery](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery), whose rules govern every move and delete.

**`git mv` on a folder fails whenever the index disagrees with the disk, and that is the ordinary state of a working vault.** A single uncommitted rename or deletion inside the entity aborts the entire move:

```
fatal: bad source, source=projects/<name>/sources/<a file git still holds under its old name>.md
```

Nothing moves when this happens. Unless the vault's `CLAUDE.md` allows a skill to commit, a vault accumulates exactly this state between the operator's own commits: treat it as expected rather than as a failure to diagnose. **Fall back to plain `mv` / `rm`**, which costs no history, since git detects the rename from content when the operator commits. Same fallback where the vault is not a git repo at all. **Never retry `git mv` file by file** - a half-moved entity is worse than either outcome. Say in the report which of the two ran.

1. Move living-reference files to `resources/<name>/`.
2. Delete approved stale snapshots.
3. Create the successor scaffold if chosen.
4. Retense and clean `brief.md` and `actions.md` to their archived form.
5. Move the entity to Step 1's destination. Create the destination parent if needed. **Check the destination does not already exist first** (`test -e "<dst>" && echo EXISTS`). If it exists, stop and resolve the collision with the user - never let `mv` merge into or clobber an occupied archive path.
6. **Rewrite the links *inside* the moved folder and each routed file** per [operating-discipline.md](../../para-shared/operating-discipline.md#moving-an-entity-folder): only a link whose target lies outside what moved changes.
7. Apply every approved link repoint from the Step 6 table.
8. **Windows note**: an empty source directory can linger ("device or resource busy") if the IDE or a terminal holds a handle - the files moved fine; `rm -rf` the empty shell and tell the user it was a stale handle, not a failure.

## Step 8 - Verify and report

- Re-run the Step 6 scan and read every hit. Assert **zero** still reference the old location, however the link is written.
- **Then resolve every repointed link to a file that exists.** The scan only proves the old path is gone; a repoint written at the wrong depth passes it and still dangles, which is the likeliest error in the whole run. Resolve each rewritten target against the filesystem, percent-decoding it first, and report how many resolved rather than how many were rewritten. An assertion that cannot fail is not a check.
- Resolve every relative link *inside* the archived folder and any file routed to `resources/` - the half the inbound grep cannot see. A still-live historical mention inside the archived folder itself (a migration plan, say) is acceptable; flag it explicitly.
- Confirm the archived folder contains only history (brief, actions, one-time plans) and that the successor, if any, holds the surviving work.
- Report: what was archived and its kind, the version decision (projects only), files routed to resources, snapshots deleted, the successor created, and the count of links repointed with the table - inbound and outbound counted separately, since they come from different scans.
- Say whether anything was committed: nothing is unless the vault's `CLAUDE.md` allows commits (`operating-discipline.md`), and name which of the two applied. Where a plain `mv` ran, say so here as well, because `git status` will show the move as a block of deletions plus untracked files until they stage it. If the skill itself or a public repo was touched, flag that those need their own review.

## Edge cases

- **Entity already partly archived** (someone moved the folder but left links broken): run Steps 6 to 8 only - reconcile the links and validate the archived files.
- **Suffix collision** (`<name>-v1` already exists in archive): ask whether this is a further version or a re-archive of the same; never silently overwrite. Projects only.
- **Name collision for an idea or area** (the destination already exists): ask whether this re-archives the same entity or is a distinct one needing a disambiguating name; never silently overwrite.
