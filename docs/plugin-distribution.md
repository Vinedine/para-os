# Distributing the skills as a plugin

A prototype, not a shipped install path. Today `INSTALL.md` step 3 copies `base/.claude/skills/` into every vault and `/para-upgrade` re-syncs those copies on every revision. This page records what it takes to install the same skills as a Claude Code plugin from this repository instead, what was verified, what was not, and what would have to change before operators are pointed at it.

Everything below was measured with Claude Code 2.1.283 and the plugin pages of the official docs (plugins, plugin marketplaces, the plugins reference, the marketplace reference, the plugin loading reference and the plugin CLI reference).

## What was built

Two new files, and nothing under `base/` moved or changed. **Neither is in the repository**: a manifest at the root makes the repository installable as soon as it reaches `main`, and [Before shipping](#before-shipping) lists what has to come first. To try the prototype, create both at the repository root:

- **`.claude-plugin/marketplace.json`**: a marketplace named `para-os` with one entry, `para-os`, whose `source` is `./`, the repository root.
- **`.claude-plugin/plugin.json`**: the plugin manifest. `name` is `para-os`, `version` is the newest revision label, and `"skills": ["./base/.claude/skills/"]` points the plugin at the existing skills folder.

`.claude-plugin/marketplace.json`:

```json
{
  "name": "para-os",
  "description": "para-os as a plugin marketplace: the base /para-* skills for a PARA-style vault.",
  "owner": {
    "name": "Vinedine"
  },
  "plugins": [
    {
      "name": "para-os",
      "source": "./",
      "description": "The base /para-* skills: daily brief, triage, new, archive, deep clean, pipeline and upgrade."
    }
  ]
}
```

`.claude-plugin/plugin.json`:

```json
{
  "name": "para-os",
  "version": "2026.09.05",
  "description": "The para-os /para-* skills for a PARA-style vault, loaded from base/.claude/skills/. The vault itself (CLAUDE.md, rule files, folders) still comes from base/.",
  "author": {
    "name": "Vinedine"
  },
  "homepage": "https://github.com/Vinedine/para-os",
  "repository": "https://github.com/Vinedine/para-os",
  "license": "MIT",
  "keywords": ["para", "vault", "second-brain"],
  "skills": ["./base/.claude/skills/"]
}
```

The install id is `para-os@para-os`: plugin name, then marketplace name.

### Why the plugin root is the repository root

`plugin.json` can point at a custom skills directory: the `skills` key takes a path or a list of paths, and adds them to the default `skills/` scan rather than replacing it. The limits are what decide the layout:

- Every component path is relative to the plugin root and starts with `./`.
- A path containing `..` fails validation, and a path that resolves outside the plugin root does not load (`path escapes plugin directory`). A symlink leading outside the plugin is rejected the same way, and symlinks do not survive a default Windows checkout anyway.

So a manifest can reach `base/.claude/skills/` only from a plugin root that encloses it: the repository root, `base/`, or `base/.claude/`. A `plugin.json` under `base/` would be copied into every new vault by `INSTALL.md` step 3, and `/para-upgrade`'s skeleton sweep (everything in `base/` except the skills) would then propose it to every existing vault. That leaves the repository root, with the marketplace entry's `source` as `./`.

**The measured alternative** is a marketplace entry whose `source` is `./base/.claude` and no `plugin.json` at all: with no manifest, the entry is the manifest, and the plugin root's default `skills/` folder is exactly `base/.claude/skills/`. It validated with `--strict`, installed, and listed the same eight skills. It is one file instead of two and ships 59 files instead of the whole repository's 271, but it gives `--plugin-dir` and `claude plugin eval` nothing to load from the repository root, and it ships `rules/` and `settings.json`, which a plugin cannot use (a plugin's `settings.json` honours only `agent` and `subagentStatusLine`). The prototype uses the repository root for the `tools/eval.py` saving below; switching is a two-file edit either way.

### The version

`version` is `2026.09.05`, the newest `CHANGELOG.md` revision. Claude Code detects an update by comparing versions, and a manifest version wins over everything else, so:

- **Pinned** (the prototype): an installed copy moves only when the version string moves, which ties plugin updates to revisions, the same boundary the `<!-- para-os-template: -->` marker uses.
- **Unpinned**: the version becomes the commit SHA, and every commit to `main` reaches every operator, mid-revision work included. `claude plugin validate` also warns that no version is set.

Pinning adds a stamp that must move with every revision, and nothing checks it yet (see [Before shipping](#before-shipping)). The label is also not semver: `claude plugin validate --strict` accepts it, but `claude plugin tag` refuses it (`Version "2026.09.05" is not valid semver`) and plugin dependency ranges ignore it. Neither feature is used here; if one ever is, `2026.9.5` is the semver spelling of the same revision.

## What was verified

Every install ran in a throwaway configuration: `CLAUDE_CONFIG_DIR` and `CLAUDE_CODE_PLUGIN_CACHE_DIR` pointed at scratch directories. Overriding `HOME` was refused by the sandbox the prototype was built in, so the real configuration was checked instead: the checksum of `~/.claude.json` was unchanged afterwards, no `~/.claude/settings.json` was created, and nothing new appeared under `~/.claude/plugins/`.

| What | Command | Result |
|---|---|---|
| Marketplace manifest | `claude plugin validate --strict .` | `Validating marketplace manifest`, `Validation passed` |
| Plugin manifest | `claude plugin validate --strict .claude-plugin/plugin.json` | `Validation passed` |
| The skills folder, as `tools/check.py` runs it | `claude plugin validate base/.claude/skills` | still `Validating components in`, `Validation passed` |
| Add the marketplace | `claude plugin marketplace add <repo path>` | `Successfully added marketplace: para-os (declared in user settings)` |
| Install | `claude plugin install para-os@para-os` | `Successfully installed plugin: para-os@para-os (scope: user)` |
| Listed | `claude plugin list` | `para-os@para-os`, `Version: 2026.09.05`, `Scope: user`, enabled |
| Loaded skills | `claude plugin details para-os` | `Skills (8)`: the eight `para-*` skills; `para-shared` is correctly not a skill; about 1,339 tokens always-on |
| Session-only load | `claude --plugin-dir <repo path> plugin list` | `para-os@inline`, loaded, the same eight skills |
| Project scope | `marketplace add --scope project`, then `install --scope project`, from a scratch vault | both wrote to the vault's `.claude/settings.json`, beside `autoMemoryEnabled` (details under [User or project scope](#user-or-project-scope)) |
| Contract checks | `python3 tools/check.py --no-vendor`, then `python3 tools/check.py` | both pass; neither needed a change for the new files |

A marketplace run of `validate` does not open the plugin's skill files, so the manifests' passes say nothing about the skills themselves. `tools/check.py` already validates `base/.claude/skills/` as a components folder, and that check is unaffected by the manifests.

**A marketplace added from a local directory loads the plugin in place.** Install still writes a copy into the plugin cache (from a working checkout it copies untracked `__pycache__/` too), but after install a probe skill added to the source folder showed up in `claude plugin details` with no reinstall. A marketplace added from the operator's existing clone at `~/.paraos/para-os` would therefore follow `git pull` directly, with the version string playing no part.

### para-shared still resolves

`para-shared/` has no `SKILL.md`, so it is never listed as a skill, but it is copied with everything else under the plugin root, beside the skills, in the same layout a vault has today. Checked in the installed copy under the plugin cache:

- All 88 relative links from skill Markdown into `para-shared/` (`../para-shared/asking.md`, `../../para-shared/scripts.md` and the rest) resolve; none is missing.
- `brief_scan.py`, run from the installed copy against `examples/belfoot-vault`, exits 0, and its `paraos_vault` import resolves to the installed copy's own `para-shared/scripts/paraos_vault.py`.
- `upgrade_scan.py`, run from the installed copy against a scratch vault with no bundled skills, exits 0. Its `skills` block comes back empty (only the `para-shared` library row, with no copies), and its smoke test runs the plugin's own `brief_scan.py` through the fallback beside the scan.

It works because nothing assumes the skills live in the vault: `para-shared/scripts.md` anchors every path to "this skill's base directory", and every script finds the library from its own `__file__`. It would stop working for any layout that separates a skill from `para-shared/`, which is exactly the add-on case below.

## What is not verified

- **No model turn.** There was no API key, so nothing here saw the `/` menu, a skill invocation, or the model choosing a skill by its description. Whether `/para-daily-brief` also resolves by its short name, and whether the "base directory for this skill" a session reports points into the plugin cache, are taken from the docs, not observed.
- **A GitHub-hosted marketplace.** The manifests are not on GitHub, and nothing was pushed. `marketplace add` refuses a `file://` git URL (`Invalid marketplace source format`), and a git entry declared under `extraKnownMarketplaces` was not picked up by the non-interactive commands. The clone, the commit recorded at install, `claude plugin update` against a pinned version, and auto-update (off by default for a third-party marketplace) are all doc-based.
- **Windows, macOS, the desktop app's Code tab, Cowork and cloud sessions.** Only the Linux CLI was run.
- **`claude plugin eval .` from the repository root.** It costs a model run.
- **A vault holding bundled copies and the plugin at once.** The docs say both load, one as `/para-daily-brief` and one as `/para-os:para-daily-brief`.
- **Two vaults on one machine at different plugin versions.** `installed_plugins.json` keeps one row per scope, with a `projectPath` for project scope, which suggests it may be possible; nothing tested it.

## Skill namespacing

Every plugin skill is namespaced under the plugin's `name`: `/para-daily-brief` becomes `/para-os:para-daily-brief`. The skills keep their frontmatter names, so the prefix doubles up; naming the plugin `para` would give `/para:para-daily-brief`, and only renaming the skills themselves (to `daily-brief` and so on) would read cleanly, which breaks every bundled vault. Model invocation from a description is unaffected; typed commands and prose are not:

- 56 files in the repository, with 174 mentions, tell the operator or the model to run a `/para-*` command: both templates, `bootstrap-prompt.md`, `README.md`, `INSTALL.md`, the add-ons and the skills' own cross-references. In a plugin-only vault each one names a command that does not exist under that name.
- `Skill(...)` permission rules, where a vault or a user has written any, name the skill; whether an unprefixed rule still matches a plugin skill is not documented and was not tested.
- A vault's own `CLAUDE.md` names skills too, and `/para-upgrade` Phase 3 already sweeps skill names in prose; it would have to learn the prefix.

## What /para-upgrade would no longer need

For a vault whose skills come from the plugin:

- **Phase 3's installed skill copies**, bundled and user-level: the tree diff against the master, `missing` files, `names_missing_script`, `revisions_behind`, running each copied skill's suite beside the copy, `para-shared/scripts/` as the library dependency checked first, line-ending normalisation of those diffs, and deciding which of two copies shadows the other. In `upgrade_scan.py` that is the `skills` block and its helpers, about 275 of its 1,627 lines, plus the `SkillsBlockCase` and `UndeclaredAddonSkillCase` tests. The verdict and history machinery it uses is shared with the integrations and stays.
- **The Reaction line** most revisions carry, "re-sync every installed `para-*` skill copy and `para-shared/`", becomes "update the plugin".
- **Copy verification at install**: `INSTALL.md` step 3's check that `.claude/skills/para-daily-brief/SKILL.md` arrived.

That is a real saving, but a minority of the skill. **What must remain**, because none of it is a skill:

- **Phase 0**: the vault's `<!-- para-os-template: -->` marker against the template's, and the changelog entries between them as the scope. The marker becomes more important, not less: it is the only record of which revision a vault's rules are at, and a pinned plugin version is the only record of which revision its skills are at.
- **Phases 1 and 2**: `CLAUDE.md` template migrations and the skeleton files. A plugin has no component for either.
- **Rule files in `.claude/rules/`.** They load by their `paths:` globs from the vault's own `.claude/rules/`, a plugin has no rules component, and a vault extends its copies.
- **`.claude/settings.json`**: `autoMemoryEnabled: false` must stay in the vault; a plugin's settings file drops it.
- **The rest of Phase 3**: vault-local skills restating a changed rule, skill names in prose, the vault's `CLAUDE.md` claims about itself, and installed integration scripts under the four-condition gate.
- **Phases 4 and 5**: rule-driven content violations, then the stamp, the smoke test and the link check.
- **A para-os clone.** The scan reads every master with `git` at an explicit ref; the plugin cache is a copy with no `.git`. Adding the marketplace from that same clone keeps one checkout serving both.

It would also need new work: detect the plugin (the vault's or the user's `enabledPlugins`), report its version against the master's revision, and flag a vault that still has bundled `para-*` copies alongside it, since both would load.

## Trade-offs

### Self-containment and offline use

Today a vault folder is complete: copy, sync or clone it anywhere and the skills come with it. That includes cloud sessions and routines, which per the docs load skills committed to a repository's `.claude/skills/` but not plugins, whether declared in the repository's `.claude/settings.json` or enabled in user settings. With the plugin, every machine that runs the skills installs it first. Offline use is fine after install, since the plugin runs from its cache, and a marketplace added from a local clone needs no network at all. Cowork sessions, per the docs, load the skills enabled for the claude.ai account rather than `~/.claude/skills/`; neither install path was tried there.

### The vault's git history

Today every revision lands a skill diff in the vault's history: noise, but also an exact record of the skill code that ran against the vault at each commit. With the plugin the history holds only the migrations `/para-upgrade` makes, and which skills ran is known only through the marker and the installed plugin version, which agree only if the operator updates the plugin and runs the upgrade together.

### Operators running several vaults

At user scope one install serves every vault, which is what moving the skills to `~/.claude/skills/` does today. The consequence is the same too: a plugin update moves every vault's skills at once, while each vault's rules move only when `/para-upgrade` runs in it. Skills then run against vaults a revision behind, which today happens only to operators on a user-level install.

### User or project scope

- **User scope** enables the skills in every session on the machine, non-vault projects included, at about 1,339 tokens each.
- **Project scope** enables them per vault, through the vault's `.claude/settings.json`, which the vault already ships. Per the docs, a plugin enabled by a repository's settings loads only after that folder's workspace trust dialog is accepted. Each machine still runs the install once; committing the setting enables the plugin but does not download it.
- A project-scope marketplace added from a local path is written into `.claude/settings.json` as an absolute, machine-specific path. For a vault shared between machines, declare the GitHub source instead.

### Namespacing

See [Skill namespacing](#skill-namespacing). It is the change operators would notice first.

### How example vault copies are checked

`tools/check.py` fails when an untracked copy under `examples/*/.claude/skills/` differs from `base/.claude/skills/`, because the example runs from such a copy. With the plugin, a reader tries the example with the plugin enabled instead, or with `claude --plugin-dir <repo>`, and there is no copy to fall behind. The check stays useful for as long as copying remains a supported path.

### Add-ons and para-ingest

The add-on skills (`property-*`, `para-activity-review`, `para-brainstorm`) and `multi-vault/para-ingest` link `../para-shared/` and only work installed beside base's skills, as the real-estate README says. A second plugin rooted at an add-on would not contain `para-shared/`. Adding the add-on's skills folder to this plugin's `skills` list loads the skills, but their `../para-shared/` then resolves inside the add-on's own folder, where there is none. Add-ons are also chosen per vault, which fits project scope and not user scope. The prototype covers base only; add-ons need either one shared skills directory or their own copy of `para-shared/` before they can follow.

### Vault-relative paths that assume bundled skills

A plugin-only vault breaks these, each a small edit:

- `base/bootstrap-prompt.md` cites `.claude/skills/para-shared/asking.md` twice as a vault path, and tells the operator the skills are bundled in the vault.
- `INSTALL.md` step 3 checks for `.claude/skills/para-daily-brief/SKILL.md`, and "Uninstalling" deletes the bundled folders.
- `/para-activity-review` enumerates the skills a vault declares from its `.claude/skills/`, so it would miss every plugin skill.

## What tools/eval.py could drop

With `plugin.json` at the repository root, `claude plugin eval .` run from the repository root finds the plugin and its default `evals/` folder. `tools/eval.py` could drop `build_plugin`, the generated `MANIFEST`, the temporary directory, both `copytree` calls and `--keep`, and keep only what is policy: results under `$PARAOS_HOME/data/eval-runs/`, the `native` tag by default, and `--trust-plugin --scaffold --no-publish`. Two things to check first: `build_plugin` leaves out any `evals/results/` folder, which the harness would now see; and nothing here ran an eval against the repository root. Its docstring, and the vendor-validator paragraph in `tools/check.py`, both say the repository ships no manifest, which would no longer be true.

## Migration path for existing vaults

1. **A revision ships the manifests** with the prerequisites below. Bundled copies stay the default install; the plugin is opt-in.
2. **Once per machine**, add the marketplace. From the existing clone, `claude plugin marketplace add ~/.paraos/para-os`: loads in place, works offline, follows `git pull`. Or from GitHub, `claude plugin marketplace add Vinedine/para-os`: cached, updated with `claude plugin update para-os@para-os`.
3. **Per vault, upgrade first.** Run `/para-upgrade` to bring the vault to the revision that shipped the manifests, while its bundled skills still run it.
4. **Then install and remove the copies.** From the vault root, `claude plugin install para-os@para-os --scope project`, or once at user scope when every project on the machine is a para-os vault. Delete `.claude/skills/para-*/` and `.claude/skills/para-shared/`, and nothing else in `.claude/skills/`, since a vault's own skills live there too. Do the same for any `para-*` copies in `~/.claude/skills/`. Commit.
5. **Confirm** in a new session: `claude plugin details para-os` lists the eight skills, `/para-os:para-daily-brief week` runs, and the `/` menu shows no unprefixed `/para-daily-brief` left over.
6. **To roll back**, uninstall the plugin (`claude plugin uninstall para-os@para-os`) and copy `base/.claude/skills/` back into the vault.

Later revisions then carry "update the plugin" as their skill Reaction, and `/para-upgrade`'s copy audit becomes the legacy path for vaults that never switched. `base/.claude/skills/` stays where it is: it is the plugin's source.

## Before shipping

In order:

1. **Run it with a model**, in the desktop app's Code tab on Windows and macOS: the namespaced command, the short name, model invocation, and a script-backed skill (`/para-os:para-daily-brief`) reading `para-shared/`.
2. **Decide the naming**, then rewrite the `/para-*` mentions and the vault-relative paths listed above.
3. **Check the version in `tools/check.py`**: `plugin.json`'s `version` equal to the newest `CHANGELOG.md` revision, as the template markers already are, and `claude plugin validate --strict` over the repository root beside the skills-folder run. Until then a pinned version is a stamp that silently falls behind.
4. **Teach `/para-upgrade` the plugin**: detect it, compare its version, flag leftover copies.
5. **Settle add-ons and `para-shared/`** before offering add-ons this way.
