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

After re-checking the snapshot ([scripts.md](../../para-shared/scripts.md)), in order, each move per [moving an entity folder](../../para-shared/operating-discipline.md#moving-an-entity-folder):

1. Move living-reference files to `resources/<name>/`.
2. Delete approved stale snapshots.
3. Create the successor scaffold, if chosen.
4. Retense `brief.md` and `actions.md` to their archived form.
5. Apply the approved repoints that lead anywhere but the archive path; display text spelling the old path gets the new one.
6. Where `destination.exists`, stop and settle the collision with the operator (a further version, a re-archive, a distinct entity needing another name); never merge into or overwrite it. Otherwise move the entity, which repoints the links left.

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
| `old_path` | `.exists`, `.empty` | `.exists` false |
| `untracked` | files at the new path git does not track; `null` when git cannot answer | listed |
| `clean` | true when the first four rows pass | the pass line, never instead of reading the lists |

Confirm the archived folder holds only history and any successor the surviving work. Report, after [Step 9](close-out.md): what was archived, the version decision, files routed, snapshots deleted, the successor, the repoints in a table (inbound and inside apart), Step 9's answers and any commit. A touched skill or public repo is flagged for its own review.
