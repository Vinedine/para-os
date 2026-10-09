# Changelog fragments

A pull request that an existing vault must react to adds one file here, named for its issue
(`281.md`), instead of editing `CHANGELOG.md` or `RELEASES.md`. A new file per pull request
means branches open at the same time never conflict over the changelog. `/release` folds every
fragment into the revision it cuts and deletes it. A change to nothing a vault holds (an eval, a test, `tools/`, `docs/`) adds none.

```markdown
## Changelog

**What changed, in one bold sentence.** What an agent needs to know. Reaction: what an existing vault does.

## What changes for you

One or two plain sentences for people.

## Do you need to do anything?

Only what `/para-upgrade` cannot do for them. Leave the section out when it does everything.
```

- **Changelog** is copied verbatim into `CHANGELOG.md`, which `/para-upgrade` executes, so it
  is an instruction to an agent, not a summary. One bold-led paragraph per change, each one
  unbroken line with its `Reaction:` (`none for an existing vault` when there is nothing to
  do). A reason earns a clause only where the migrating agent must judge a case the Reaction
  does not cover. An integration whose script moved gets an `**Integrations.**` paragraph.
- **A file the kit stops shipping** goes on a line of its own,
  ``Retired: `<vault path, folder or glob>`, ...``, and `/para-upgrade` proposes its deletion.
- The other two sections are joined onto the revision's two paragraphs in `RELEASES.md`:
  plain words, no file path a non-programmer would not recognise.
- No calendar dates, and no em or en dashes. `tools/check.py` fails a fragment the fold
  cannot parse.

A hotfix cherry-picked onto `stable` edits `CHANGELOG.md` and `RELEASES.md` directly, since
`stable` never holds a fragment.
