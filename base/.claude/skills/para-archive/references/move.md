# Scan links, execute, verify (Steps 6 to 8)

`scripts/archive_scan.py` implements every mechanical rule below - the plan call's `inbound` for Step 6, the verify call for Step 8 - and `scripts/test_archive_scan.py` pins each one to a case. Read this file when a result looks wrong, or when running the scan by hand per Step 0.

Zero dangling links is the bar. **Links inside a fenced code block are neither scanned nor rewritten**, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md). The link scan runs **before** anything moves and again after, because the second run is the only proof.

## Step 6 - Scan inbound links (the part that breaks silently)

Before moving anything, grep the **entire vault** for the entity folder's name and the filename of each file routed out of it. A path grep misses a link written relative to a sibling (`../<name>/brief.md`), so read each hit and keep only real references to this entity. Git internals and installed skill copies are not vault content. **`inbound.references` and `.name_only` are this scan, already split**; the by-hand fallback:

```bash
# from vault root
grep -rn --include="*.md" "<name>" . | grep -v -e '^\./\.git/' -e '^\./\.claude/skills/'
```

**A routed file's own filename is a second name to search, not only the entity folder's.** Which files route to `resources/` is Step 4's decision, made only after Step 0's plan call already ran once - so a mention of a routed file may name only that file (a backtick citation, a bare filename in prose) and never the entity's folder at all, which the scan above cannot see. Once Step 4 has decided, re-run the plan call with one `--route <file>` per routed file and read `inbound.routed[<file>]` - the same search, scoped to that file's bare name, minus hits inside the entity folder. The by-hand fallback is the same grep, substituting the routed file's own name for `<name>`.

**A reference is anywhere the path is written, not only a `](...)` target.** That is why the scan searches for the name rather than for link syntax, and why every hit gets repointed: the target of a markdown link, the **display text** of one (a link written as `[projects/<name>/actions.md](../../projects/<name>/actions.md)` spells the path twice, and a target-only rewrite leaves half of it lying), a path quoted in backticks as a source citation, and a bare path in prose. Only the first of those 404s on a click, so the rest never look broken while still asserting a path that no longer exists, which is what `/para-deep-clean` audits for. **Each hit's `shape` field names which of the four it is** (`link_target`, `link_text`, `backtick`, `prose`), and `in_sources` marks a hit inside a `sources/` folder. The exception is **third-party verbatim content** (`operating-discipline.md`): a synced publication or a transcript is not repointed, though an annotation section the vault appended below one is.

**A hit that is only a substring of a longer name is not a reference at all** - `acme` inside `acme-website-v2` names a different entity, not this one - and lands in `inbound.name_only` instead, for the operator to read and never to count. A hit in `inbound.references` is one whose line carries a link that resolves under the entity folder, or that names the folder as a whole path segment (a boundary on both sides: the start or end of the text, or a character that is not a letter, digit, `-` or `_`).

Build an **inbound-link table**: every file and line pointing at the entity, its brief, its actions, or any file being routed to `resources/`. Classify each:

- Repoint to the **archive** path, Step 1's destination.
- Repoint to the **successor** (`resources/ideas/<name>-vNext/brief.md`) when it referenced live or forward work. A link to the old `actions.md` lands on the successor's brief; if it tracked a dated commitment, repoint to wherever that commitment went instead.
- Repoint to the **resources** home, for routed living-reference files.
- Repoint to a **live external source** (a shipped URL, a public repo) when that's the truer target than a dead vault path.
- Leave as-is.

Some of these links may **already be broken** from earlier moves - fix them in the same pass.

## Step 7 - Execute

**Re-check the plan call's snapshot first**, immediately before anything below writes, per [para-shared/scripts.md](../../para-shared/scripts.md).

In order, with `git mv` so history is preserved, except on the [read-only iPad delivery](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery), whose rules govern every move and delete. **`move_plan.inside` and `.inbound`** (from the plan call) name every link that sub-steps 6 and 7 below rewrite, each with the `new_href` it becomes.

**`git mv` on a folder fails whenever the index disagrees with the disk, and that is the ordinary state of a working vault.** A single uncommitted rename or deletion inside the entity aborts the entire move:

```
fatal: bad source, source=projects/<name>/sources/<a file git still holds under its old name>.md
```

Nothing moves when this happens. Unless the vault's `CLAUDE.md` allows a skill to commit, a vault accumulates exactly this state between the operator's own commits: treat it as expected rather than as a failure to diagnose. **Fall back to plain `mv`**, which costs no history, since git detects the rename from content when the operator commits. Same fallback where the vault is not a git repo at all. **Never retry `git mv` file by file** - a half-moved entity is worse than either outcome. Say in the report which of the two ran.

1. Move living-reference files to `resources/<name>/`.
2. Delete approved stale snapshots, per [operating-discipline.md](../../para-shared/operating-discipline.md#deleting-a-file).
3. Create the successor scaffold if chosen.
4. Retense and clean `brief.md` and `actions.md` to their archived form.
5. Move the entity to Step 1's destination. Create the destination parent if needed. **Check the destination does not already exist first** - `destination.exists` from the plan call already answers this (`test -e "<dst>" && echo EXISTS` by hand). If it exists, stop and resolve the collision with the user - never let `mv` merge into or clobber an occupied archive path.
6. **Rewrite the links *inside* the moved folder and each routed file** per [operating-discipline.md](../../para-shared/operating-discipline.md#moving-an-entity-folder): only a link whose target lies outside what moved changes.
7. Apply every approved link repoint from the Step 6 table.
8. **Windows note**: an empty source directory can linger ("device or resource busy") if the IDE or a terminal holds a handle - the files moved fine; `rm -rf` the empty shell and tell the user it was a stale handle, not a failure.

## Step 8 - Verify and report

Run the verify call:

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/archive_scan.py" --vault . --verify --moved-from <old> --moved-to <new> [--routed <file>]...
```

pass every file moved to `resources/<name>/` in Step 7.1 as its own `--routed`. Its fields are this step, already run:

- **`stale_links`**: every link anywhere in the vault (every bucket, archive included, plus root-level files) whose resolved target still lies under the old path. Assert **zero**. The by-hand fallback is re-running the Step 6 grep and reading every hit.
- **`stale_mentions`** (and **`stale_mentions_exempt`** for third-party content): every remaining occurrence of the old path written as text - link display text, a backtick path, bare prose - with a path boundary on both sides: not preceded by a letter, digit, `-`, `_` or `.`, nor by another named folder (`archive/projects/x` is never a mention of `projects/x`, nor is `archive/projects/x-v1`), though a `../` or `./` climb is; and not followed by a letter, digit, `-` or `_`. Assert zero outside the exempt list.
- **`inbound_resolved`**: `.resolved` counts and `.unresolved` lists every link from outside the new folder whose target resolves under it. By hand, resolve each rewritten target against the filesystem, percent-decoded, and report how many resolved rather than how many were rewritten.
- **`inside`**: `.resolved` and `.dangling` for every relative link inside the archived folder and each `--routed` file - the half the inbound grep cannot see. A still-live historical mention inside the archived folder itself (a migration plan, say) is acceptable; flag it explicitly rather than reading it from `dangling`. `.missing` lists each `--routed` path that names no file (a typo, or a file not yet moved): it was never read, so fix the path or the move and re-run.
- **`old_path`**: `.exists` and `.empty` - the Windows stale-handle case below.
- **`untracked`**: `git_untracked(vault, new)`, `null` when git cannot answer (no repo, no git on PATH) rather than an empty list, so the report never reads "could not check" as "nothing untracked".
- **`clean`**: true only when every one of the above is empty (mentions outside the exempt list). Treat it as the run's own pass/fail line, not a substitute for reading the lists.

Beyond the verify call:

- Confirm the archived folder contains only history (brief, actions, one-time plans) and that the successor, if any, holds the surviving work.
- Report: what was archived and its kind, the version decision (projects only), files routed to resources, snapshots deleted, the successor created, and the count of links repointed with the table - inbound and outbound counted separately, since they come from different scans. List `untracked`: a file never committed moves on disk under a successful `git mv` too, and appears there as untracked rather than renamed, which reads as unexplained unless the report says so.
- Say whether anything was committed: nothing is unless the vault's `CLAUDE.md` allows commits (`operating-discipline.md`), and name which of the two applied. Where a plain `mv` ran, say so here as well, because `git status` will show the move as a block of deletions plus untracked files until they stage it. If the skill itself or a public repo was touched, flag that those need their own review.

## Edge cases

- **Entity already partly archived** (someone moved the folder but left links broken): run Steps 6 to 8 only - reconcile the links and validate the archived files.
- **Suffix collision** (`<name>-v1` already exists in archive): ask whether this is a further version or a re-archive of the same; never silently overwrite. Projects only.
- **Name collision for an idea or area** (the destination already exists): ask whether this re-archives the same entity or is a distinct one needing a disambiguating name; never silently overwrite.
