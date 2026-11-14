# A vault's rule files

What a `.claude/rules/<topic>.md` file is, read by whoever creates or edits one. Each opens on a `paths:` list of the globs it governs and loads when a matching file is read.

- **A kit file** (`filing.md`, `figures.md`, `writing-actions.md`, `brief-structure.md`, and any an add-on ships) is copied whole and replaced by an upgrade: never edit one. What a vault adds to its rule goes in a file of the vault's own.
- **A vault's own file** states what is true of this vault only: the shape of a kind of document that has one here, or a convention spanning documents. It takes a name no kit file has, and the vault's `CLAUDE.md` points at it in one line: "Read [.claude/rules/<file>.md](.claude/rules/<file>.md) before <doing what>."
- **A shape file** opens on an `**Order:**` line and `## The shape`, and closes on `## Placeholders`: the vault's convention for a section that does not apply.
