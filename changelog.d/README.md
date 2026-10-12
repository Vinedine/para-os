# Changelog fragments

A pull request that an existing vault must react to adds one file here, named for its issue
(`281.md`), instead of editing `CHANGELOG.md` or `RELEASES.md`. A new file per pull request
means branches open at the same time never conflict over the changelog. `/release` folds every
fragment into the revision it cuts and deletes it. A change to nothing a vault holds (an eval, a test, `tools/`, `docs/`) adds none, and nor does one nobody would notice that leaves a vault nothing to do: the upgrade re-copies changed files by hash.

```markdown
## Changelog

- <what the vault does>: <file or section>
Retired: `<vault path, folder or glob>`, ...

## Fixes

- **What changed, in a few words.** One or two plain sentences for people.

## What to do

- Before you upgrade: <a step the upgrade needs done first>
- <a step only a person can do, after the upgrade>
```

- **Changelog** lines go into `CHANGELOG.md`, which `/para-upgrade` executes: one line per
  change a vault makes to its own content, its condition first ("In a real-estate vault, ...").
  Re-copying a file the kit owns, or taking a template sentence, gets no line: the upgrade
  compares the first by hash and shows the second as a diff. A file the kit stops shipping goes
  on a `Retired:` line, and the upgrade proposes deleting it. With nothing else for a vault to
  do, leave the section out. The fold ends each `- ` line on the fragment's number.
- **One release-notes section**, `## Safer by default`, `## Also new`, `## Fixes` or
  `## Removed`, holds one bullet with a bold lead, which the fold appends under that heading of
  the revision in `RELEASES.md`. `/release` picks the highlights from them.
- **What to do** lists only what `/para-upgrade` cannot do; leave it out when it does
  everything. The fold numbers the steps around the upgrade's own, a `Before you upgrade` step
  above it. Plain words in both, no file path a non-programmer would not recognise.
- No calendar dates, and no em or en dashes. `tools/check.py` fails a fragment the fold
  cannot parse.

A hotfix cherry-picked onto `stable` edits `CHANGELOG.md` and `RELEASES.md` directly, since
`stable` never holds a fragment.
