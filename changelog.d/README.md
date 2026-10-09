# Changelog fragments

A pull request that an existing vault must react to adds one file here, named for its issue
(`281.md`), instead of editing `CHANGELOG.md` or `RELEASES.md`. A new file per pull request
means branches open at the same time never conflict over the changelog. `/release` folds every
fragment into the revision it cuts and deletes it. A change to nothing a vault holds (an eval, a test, `tools/`, `docs/`) adds none.

```markdown
## Changelog

- <what the vault does>: <file or section>
Retired: `<vault path, folder or glob>`, ...

## What changes for you

One or two plain sentences for people.

## Do you need to do anything?

Only what `/para-upgrade` cannot do for them. Leave the section out when it does everything.
```

- **Changelog** lines go into `CHANGELOG.md`, which `/para-upgrade` executes: one line per
  change a vault makes to its own content, its condition first ("In a real-estate vault, ...").
  Re-copying a file the kit owns, or taking a template sentence, gets no line: the upgrade
  compares the first by hash and shows the second as a diff. A file the kit stops shipping goes
  on a `Retired:` line, and the upgrade proposes deleting it. With nothing else for a vault to
  do, leave the section out. The fold ends each `- ` line on the fragment's number.
- The other two sections are joined onto the revision's two paragraphs in `RELEASES.md`:
  plain words, no file path a non-programmer would not recognise.
- No calendar dates, and no em or en dashes. `tools/check.py` fails a fragment the fold
  cannot parse.

A hotfix cherry-picked onto `stable` edits `CHANGELOG.md` and `RELEASES.md` directly, since
`stable` never holds a fragment.
