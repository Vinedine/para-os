# Add-ons

Everything a vault declares under the `**Type:**` line of its `CLAUDE.md`, one folder per name. `base/` is the vault every adopter copies; an add-on is layered on it, and each folder's README opens on its kind and says how to install it.

## Two kinds

| Kind | What it is | Declared as | Per vault |
|---|---|---|---|
| Flavor | what a vault is about | `**Flavor:** <name>` | at most one |
| Module | a function beside whatever it is about | `**Modules:** <name>, <name>` | any number |

Both ship one fixed file, `para-os/<name>.md`, copied whole to the vault's `.claude/para-os/` and imported by its `CLAUDE.md` under the core's line; where the two differ, the vault's own file wins. The test between them: a flavor changes what every entity in the vault *is*; a module adds a kind of entity, or a function, beside them (a property developer carries the real-estate flavor for its properties and the sales module for its buyers).

## Available

- [`real-estate/`](real-estate/), a flavor for buying, renovating, selling and holding property.
- [`sales/`](sales/), a module for prospects, demos and deals.
- [`activity/`](activity/), a module that adds a usage review.
- [`brainstorm/`](brainstorm/), a module that adds a guided brainstorm.

## What a folder may ship

`README.md` (its first line naming the kind) and `para-os/<name>.md`; then, as needed, `.claude/rules/` for the shapes it governs, `.claude/skills/` installed beside base's, `skeleton/` for files copied into the vault, and `pipeline/` for scripts, each carrying a `para-os-integration` marker like an [integration](../integrations/).

`/para-upgrade` resolves every declared name to `addons/<name>/` and compares each file it ships as it compares base's; the declaration lines themselves are never removed. `/para-upgrade --add <name>` adopts one, running its README's Setup. `tools/check.py` holds an add-on's skills to the same contract as base's.
