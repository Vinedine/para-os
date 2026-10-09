# Changelog

What a vault does for each template revision beyond what `/para-upgrade` takes from the kit on its own: the kit's files, compared by hash, and the template's change to `CLAUDE.md`, shown as a diff. Why each change was made is in its pull request and in [RELEASES.md](RELEASES.md).

Each vault's `CLAUDE.md` carries the revision it was last aligned to, as an HTML comment on line 3:

```
<!-- para-os-template: 2026.08.01 -->
```

`/para-upgrade` collects every entry after the vault's marker, up to and including the kit's; a vault with no marker predates the scheme and collects them all. Each line is one change, `<what the vault does>: <file or section>`, its condition first where it has one and its pull request's number last where it cites one. A `Retired:` line names vault paths the kit no longer ships, and the upgrade proposes deleting each whatever the vault's marker.

Revisions are `YYYY.MM.NN`: the year and month a revision shipped, then its zero-padded number within that month, so a plain string compare orders them. A revision marks a template change an existing vault has to react to.

**One legacy label.** The first revision shipped as `2026.08` and was renumbered `2026.08.01`: a vault stamped `2026.08` is already on `2026.08.01`, collects only the entries after it, and is restamped.

## 2026.10.01

- In a vault on the read-only iPad delivery (a `**Delivery:** readonly-ipad` line, or `flip.ps1` at its root), run `flip.ps1 spread` before the retired scripts go, then compare each section with base's template whole, as for a vault with no marker: `CLAUDE.md`
- Propose removing the `**Delivery:**` line, whatever it names: `CLAUDE.md`
- Move the repo list under `## Code repos` verbatim into `.claude/rules/code-repos.md` as `bootstrap-prompt.md` describes it, its relative links prefixed with `../../`: `CLAUDE.md` `## Code repos`
- Propose a home for each loose file at the resources root, `README.md` aside, one approval each, inbound links repointed: `resources/`
- In a real-estate vault, rewrite the `_Stage:_` label as the four header lines `property-dossier.md` declares, `since`, `Opened` and `Source` from the dossier's Timeline and Background or `unknown`, never a guessed date: each property dossier
- In a real-estate vault, add `**Dropped reason:**` from its `## Reason for skipping`: each dropped dossier
- In a real-estate vault, list each prospect whose next step sits only under its own heading, for the operator to file as a dated checkbox in an area's `actions.md`: prospect dossiers
- Offer to delete, by count and in one question, the notes holding a one-time code, a sign-in or reset link, or a token: `triage/`
- Add the `areas/network/` row at `never` where the vault has `## Who writes this vault`, else at `yes`, never changing a level the vault already declares: `CLAUDE.md` `### Where a checkbox may live`
- In a vault at `never`, move each ticked card item to the card's `## History` as a plain bullet ending `_(closed YYYY-MM-DD)_`, and route each open one to the project or area it serves, or drop it, one approval each: `areas/network/`
- Propose a `never` row for each folder whose work the vault's own rules place in another system, such as a ticket tracker or a generated file: `CLAUDE.md` `### Where a checkbox may live`
- Offer to rewrite each open item that waits on someone else as a `Waiting on` line, `since` from the line's history (`git log -L`, else the file's date, said which) and never invented, in one batched question: action files
- Name `/para-prep` wherever the vault lists its skills: `CLAUDE.md`
- Fill the `**Locale:**` fields from what the vault already states (`README.md`'s Identity, the amounts and dates its files hold), asking one question per field only for the rest, and never rewrite an amount or a date: `CLAUDE.md` `## Language`
- Move each of the six locale fields that `README.md`'s Identity states on its own into the `**Locale:**` line, leaving a link, on one approval: `README.md` `## Identity`
Retired: `flip.ps1`, `render.ps1`, `render.mjs`

## 2026.09.07

- Correct each Stage line that `/para-pipeline`'s scan lists under `unknown_stage`: staged entities
- In a vault with `resources/scripts/activity.py`, add `**Modules:** activity` under the `**Type:**` line: `CLAUDE.md`
- In a vault with no `resources/scripts/activity.py`, delete the bundled skill: `.claude/skills/para-activity-review/`

## 2026.09.06

## 2026.09.05

- Rename each skill of the vault's own whose name starts `para-`: `.claude/skills/`
- Add `.pytest_cache/`: `.gitignore`

## 2026.09.04

- Where `/para-ingest` is installed, run it once with every vault mounted: its run log
- Add a row for each mailbox the vault received routed mail from on its registry `purpose` alone and should keep receiving: `CLAUDE.md` `## Triage sources`
- Remove an email opt-out written into the vault's registry `purpose` once its block declares no such mailbox: `vaults.json`
- Repoint each path naming `flavors/real-estate/` to `addons/real-estate/`: the vault's prose
- Delete `!.mcp.json` and add `.mcp.json` under the runtime-state line: `.gitignore`
- Where `git ls-files .mcp.json` lists it, untrack it with `git rm --cached .mcp.json` and tell the operator to rotate every credential it ever held: `.mcp.json`
Retired: `.vscode/settings.json`

## 2026.09.03

- Drop a qualifier an older bootstrap left, such as `vault (default flavor: ...)`: `CLAUDE.md` `**Type:**` line
- Move each inline shape section into its own shape file per `para-shared/rule-files.md`, pointed at from `## Entity structures`, a `## README structures` section renamed to it; where the shapes are already extracted, bring each file to that contract: `CLAUDE.md`
- State each archive destination the vault already uses besides `archive/projects/` and `archive/ideas/`: `CLAUDE.md` `### Lifecycle`
- In a vault already running the `property-*` skills, add `**Flavor:** real-estate` under the `**Type:**` line: `CLAUDE.md`
- In a vault already running the `property-*` skills, move every local fact the old copies hardcoded into the source register before they are re-copied (the unobtainable facts and the request that settles each, the parcel lookup and plan commands, the portals, the transaction costs, how to read a unit breakdown): `resources/property-evaluation/property-data-sources.md`
- In a vault already running the `property-*` skills, rename its property rule files to the flavor's four, a shape file for READMEs not about property becoming `readme-structure.md` and a `brief-structure.md` added: `.claude/rules/`
- In a vault already running the `property-*` skills, use the lifecycle table's stage names, `Permitting` among them: dossiers and deal-sheet badges
- In a vault already running the `property-*` skills, turn a project beside a held property's area that carries a second dossier into `projects/<property>-works/` with an ordinary brief linking the area's dossier: `projects/`
- Move each exclusion written into a `## Triage sources` row into `$PARAOS_HOME/triage-exclusions.json`, taking it out of the row only once `para-shared/` is re-copied: `CLAUDE.md` `## Triage sources`
- Where the operator wants the skills to commit and their own instructions do not already allow it, say so: `CLAUDE.md`
- Re-copy every `granola` copy on the machine in one pass, keeping `cache/granola/synced.json` until a re-copied one has run `--write`: `granola.js`

## 2026.09.02

- Change each `sync-script` row naming `outlook.py` to a `fetch-script` row calling `py resources/scripts/outlook.py fetch`: `CLAUDE.md` `## Triage sources`
- Remove the retired `keywords`, `match_all` and `match_body` keys: `outlook.config.json`
- Register `http://localhost` (Mobile and desktop applications platform, no port) as a redirect URI on every app the outlook script signs in through: the Entra app registration
- Add delegated `Mail.Read.Shared` only where an account reads a shared mailbox: the Entra app registration
- Move each open question written as prose (_to confirm_, _still to settle_) to the file that owns the fact, or resolve it: `README.md`

## 2026.09.01

- Tell the operator that every record `outlook.py` filed before this revision holds a 255-character preview of each message, a forward without what it forwarded, and that anything built on one wants the mail read again: records filed by `outlook.py`
- Change each route value naming this vault's own folder to `"."`: `granola.config.json`
- Point the seven activity hook commands at `py "$CLAUDE_PROJECT_DIR/resources/scripts/activity.py"`: `.claude/settings.json`

## 2026.08.03

- Run one grooming pass with `/para-deep-clean` Phase 3: action files
- Add `## Agenda sources` only where a connector reaches the vault's calendar: `CLAUDE.md`
- Take the secret guard from base's file: `.gitignore`
- Move the `ROUTE` map into `granola.config.json` beside the script as `{"route": {...}}`, then replace `granola-sync.js` with the kit's `granola.js`: `resources/scripts/`
- Rename `outlook_sync.py` to `outlook.py`, re-copied from the kit, and `outlook_sync.json` to `outlook.config.json`: `resources/scripts/`
- In a vault on a synced Google Drive, add a `drive` row with the drive id: `CLAUDE.md` `## Triage sources`
- In a vault several people write, add `## Who writes this vault` with its roster: `CLAUDE.md`
Retired: `.claude/skills/shared/operating-discipline.md`

## 2026.08.02

- Move each single-owner record into the owning entity's `sources/`, renamed to the source-document convention, inbound links repointed: `archive/meetings/`
- Bring the opening headings to `Identity`, `Operating model`, `Track record` and `Vision`, in that order and in English, numbered or renamed opening sections folded under them, Vision written for real, and any "Working in this vault" section cut to the one closing line: `README.md`
- Move project, deadline and status tables to the owning `brief.md` (status) or `actions.md` (deadlines as `📅` items): `README.md`
- Ask, per unmarked script, which shipped integration it copies, and stamp its marker at the revision it was installed from: `resources/scripts/`
- Take base's paragraph on integration markers: `resources/scripts/README.md`

## 2026.08.01

- Fold the open items of each `actions.md` under `resources/ideas/` into that idea's `brief.md`, then delete the file: `resources/ideas/*/actions.md`
- Rename `## Filing rules` to `## Filing and naming`: `CLAUDE.md`
Retired: `triage/README.md`
