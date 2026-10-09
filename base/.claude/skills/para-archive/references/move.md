# Scan links, execute, verify (Steps 6 to 8)

## Step 6 - Scan inbound links

`inbound.references` is every line outside the entity naming it: read each and keep the real references. `inbound.name_only` holds the name inside a longer one (`acme` in `acme-website-v2`), to read. Once Step 4 has routed files, re-run the plan call with one `--route <file>` each and read `inbound.routed[<file>]`: a mention of a routed file need not name the entity.

Every hit is repointed whatever its `shape`, except one marked `in_sources` (third-party content), though an annotation the vault appended below it is repointed. Propose one table of every file and line pointing at the entity or a routed file, each repointed to:

- the **archive** path;
- the **successor**, for a reference to live or forward work (a link to the old `actions.md` lands on its brief, or wherever a dated commitment went);
- the **resources** home, for a routed file;
- a **live external source** (a shipped URL, a public repo) where that is the truer target;
- or left as is.

A link already broken by an earlier move is fixed in the same pass.

## Step 7 - Execute

After re-checking the snapshot ([scripts.md](../../para-shared/scripts.md)), in order:

1. Move living-reference files to `resources/<name>/`.
2. Delete approved stale snapshots.
3. Create the successor scaffold, if chosen.
4. Retense `brief.md` and `actions.md` to their archived form, then **re-run the plan call** with the same `--route` arguments and take `move_plan` from it: a link the closing edits added is in no earlier plan.
5. Where `destination.exists`, stop and settle the collision with the operator (a further version, a re-archive, a distinct entity needing another name); never merge into or overwrite it. Otherwise create the parent and move the entity with `git mv`.
6. Rewrite the links inside the moved folder and each routed file, `move_plan.inside` giving each `new_href` ([moving an entity folder](../../para-shared/operating-discipline.md#moving-an-entity-folder)).
7. Apply the approved repoints, `move_plan.inbound` giving each `new_href`; display text spelling the old path gets the new one.
8. An empty source folder left behind ("device or resource busy" on Windows) is a stale handle: remove it with `rmdir` (PowerShell `Remove-Item` without `-Recurse`) and say so. A folder that is not empty is reported, never forced.

**`git mv` on a folder aborts whole whenever the index disagrees with the disk** (an uncommitted rename or deletion inside it), the ordinary state of a vault between commits. Then, or in a vault with no git, use plain `mv`: git detects the rename at commit. Never retry `git mv` file by file.

## Step 8 - Verify and report

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/archive_scan.py" --vault . --verify --moved-from <old> --moved-to <new> [--routed <file>]... [--keep <file>:<line>]...
```

One `--routed` per file Step 7.1 moved; one `--keep` per mention of the old path the operator approved leaving (a dated citation), listed apart in `stale_mentions_kept`.

| Field | Holds | Pass |
|---|---|---|
| `stale_links` | links anywhere whose target still lies under the old path | zero |
| `stale_mentions` | the old path as text: display text, backticks, prose; `stale_mentions_exempt` the third-party ones | zero outside exempt and kept |
| `inbound_resolved` | `.resolved`, a count, and `.unresolved`, a list, of links from outside resolving under the new folder | report the count resolved |
| `inside` | `.resolved` and `.dangling` relative links in the archived folder and each routed file; `.missing`, a `--routed` path naming no file | `.missing` fixed and re-run; a one-time plan's historical mention may stand, flagged |
| `old_path` | `.exists`, `.empty` | Step 7.8 |
| `untracked` | files at the new path git does not track; `null` when git cannot answer | listed |
| `clean` | true when the first four rows pass | the pass line, never instead of reading the lists |

Confirm the archived folder holds only history and any successor the surviving work. Report, after [Step 9](close-out.md): what was archived and its kind, the version decision, files routed, snapshots deleted, the successor, the links repointed in a table (inbound and inside counted separately), whether `git mv` or `mv` ran, Step 9's answers, and whether anything was committed under which commit rule. A touched skill or public repo is flagged for its own review.
