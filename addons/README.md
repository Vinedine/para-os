# Add-ons

Everything a vault declares under the `**Type:**` line of its `CLAUDE.md`, one folder per name. `base/` is the vault every adopter copies; an add-on is layered on it, and each folder's README opens on its kind and says how to install it.

## Two kinds

| Kind | What it is | Declared as | Per vault |
|---|---|---|---|
| Flavor | what a vault is about | `**Flavor:** <name>` | at most one |
| Module | a function beside whatever it is about | `**Modules:** <name>, <name>` | any number |

Both ship `CLAUDE.md.sections`, merged in beside the vault's own sections and never over one. The test between them: a flavor changes what every entity in the vault *is*; a module adds a kind of entity, or a function, beside them (a property developer carries the real-estate flavor for its properties and the sales module for its buyers).

## What a folder may ship

`README.md` (its first line naming the kind) and `CLAUDE.md.sections`; then, as needed, `.claude/rules/` for the shapes it governs, `.claude/skills/` installed beside base's, `skeleton/` for files copied into the vault, and `pipeline/` for scripts, each carrying a `para-os-integration` marker like an [integration](../integrations/).

`/para-upgrade` resolves every declared name to `addons/<name>/` and compares each file it ships as it compares base's; the declaration lines themselves are never removed. `tools/check.py` holds an add-on's skills to the same contract as base's.
