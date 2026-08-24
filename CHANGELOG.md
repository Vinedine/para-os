# Changelog

Template revisions. Each vault's `CLAUDE.md` carries the revision it was last aligned to, as an HTML comment on line 3:

```
<!-- para-os-template: 2026.08.01 -->
```

`/para-upgrade` reads that marker, compares it against the master's, and applies the entries below that fall between the two. A vault with **no marker** predates the scheme: treat it as pre-2026.08.01 and run the full 2026.08.01 entry against it.

Revisions are dated `YYYY.MM.NN`, not semver: the year and month it shipped, then a zero-padded sequence for the nth revision of that month. The sequence counts, it doesn't grade - `2026.08.02` is not a patch on `2026.08.01`, only the one after it. A revision marks "the template changed in a way an existing vault has to react to"; wording tweaks that change no rule don't get one. Every comparison in the scheme is a plain string compare, which is what the padding is for.

**One legacy label.** The first revision shipped as `2026.08`, before the sequence existed, and was renumbered to `2026.08.01` in `2026.08.02`. A vault still stamped `2026.08` is already on `2026.08.01`: read it as that label, collect the entries after it, and restamp it. Never re-run the `2026.08.01` entry against it.

Installed [integration](integrations/) scripts share the scheme. Each shipped script carries its own marker in its header, stamped with the revision that script last changed in:

```
para-os-integration: granola 2026.08.02
```

An entry's **Integrations** line says which ones moved and why. That marker is read per script, independently of the vault's template marker, so a vault already on the current revision can still be told its installed copy is behind.

---

## 2026.08.02

Four changes.

**Revisions carry a sequence, so a month can hold more than one.** `YYYY.MM` could only ever label one revision per month; the second one in a month had to choose between lying about its date and burning the next month's label. Revisions are now `YYYY.MM.NN`, zero-padded so a plain string compare still orders them (`2026.08.01` < `2026.08.02` < `2026.09.01`), and the sequence carries no severity - it says which one came next, not how big it was. The first revision was renumbered from `2026.08` to `2026.08.01`; this one is `2026.08.02`. Reaction: none by hand. A vault stamped `2026.08` is read as `2026.08.01`, already migrated, and restamped in Phase 5 like any other upgrade.

**Conversation records route by ownership.** A dated conversation record (meeting notes, call transcript, chat or email sequence) owned by a single project or area is a source like any other: it files in that entity's `sources/`, under the vault's source-document naming. `archive/meetings/` narrows to records that span several entities or have no owning entity - the cross-cutting audit trail. The old rule read literally sent every conversational artifact to `archive/meetings/`; this writes down the boundary as practiced. Reaction: move single-owner records out of `archive/meetings/` into the owning entity's `sources/`, renaming to the source-document convention and repointing inbound links in the same pass.

**The root README has one fixed shape and holds no hand-maintained state.** The seed named the opening sections only loosely ("or the vault's equivalent"), so vaults drifted into renamed or translated headings, hand-maintained dashboards duplicating what `projects/*/brief.md` and `actions.md` already hold (stale but still reading as current), and stub Visions. The rule now names the first four `##` headings exactly (`Identity`, `Operating model`, `Track record`, `Vision`), in that order and in English whatever the body language; Vision is the end state and its horizon, never a stub; vault-specific sections follow, with `## Principles` (standing decisions not to relitigate) the one optional section with a fixed name; and the README carries no project status list, deadline table, open-action list, or live status narrative (no checkbox, `📅` marker, or status column), because `/para-daily-brief` is the dashboard. `README.md.template` carries a definition per heading, the bootstrap drafts all four sections and the braindump is not done until Vision is real, and `/para-deep-clean` Phase 1 audits the shape, fixing it in Phase 2 ahead of the entity READMEs. Reaction: rename or translate the headings to the four, fold numbered or renamed opening sections under them (an inventory or brand list becomes a `###` under Track record), write a real Vision, reduce any "Working in this vault" section to the one closing line, and move project, deadline and status tables out of the root README into the owning `brief.md` (status) or `actions.md` (deadlines become `📅` items).

**Integration scripts carry their own revision, and `/para-upgrade` reports drift.** An installed integration is a *copy*: the script lands in `resources/scripts/` on install day and nothing ever told the vault when the master moved. `/para-upgrade` didn't look either - the changelog is its scope, and the changelog never mentioned integrations - so a fixed script stayed broken in any vault that already had it. Every shipped script now carries `para-os-integration: <name> <revision>` in its header, stamped with the revision that script's *code* last changed in, so a README rewording moves nothing, and each entry here notes what moved under an **Integrations** line. `/para-upgrade` Phase 3 compares the marker in each installed copy against the master's at the ref and **reports** the gap; it never overwrites, because these copies are meant to be edited, so a resync is a hand-merge the operator makes with the entry in front of them. The check keys off the script's own marker rather than the vault's template marker, so it runs even on a vault that is already on the current revision. Reaction: one pass over the scripts already installed. Nothing installed before this revision carries a marker, so the first run after it asks, per unmarked script, which shipped integration it is and stamps it at the revision it was installed from; a script that is the vault's own stays unmarked and is named as skipped. From then on the check reports which copies are behind. The one edit is to the vault's own `resources/scripts/README.md`, which gains a paragraph saying what the marker is and that a resync is a hand-merge - it ships in the skeleton, so a vault that already has the file gets the paragraph added to its copy.

**Integrations.** New: `outlook/` - personal Outlook / Hotmail into `triage/` over Graph device-code OAuth, read-only, Python 3.9+, any platform. Updated: `granola` to 2026.08.02 - a character a filename can't hold now becomes a space instead of vanishing, so a meeting titled `Q3/Q4 plan` files as `Q3 Q4 plan` rather than `Q3Q4 plan`, and a meeting with no title files as `untitled` rather than `null`. Reaction: none for meetings already synced, since the dedup ledger keys on the meeting id, not the filename. A meeting whose ledger entry was lost but whose note is still on disk re-files under the new name; delete whichever copy you don't want.

## 2026.08.01

Six changes.

**Where a checkbox may live.** New `## Actions` section carrying the bucket table: `projects/` and `areas/` hold open and closed items, `archive/` holds closed ones only, and **`resources/` may never hold a checkbox** - one there is always a filing error. `/para-daily-brief` now discards `resources/` paths outright. Vaults that kept `actions.md` files under `resources/ideas/` must fold those items into each `brief.md` before the work goes invisible.

**An `actions.md` archives with its entity.** Replaces the old "never archive an `actions.md`" rule, which contradicted what `/para-archive` actually does. It archives fully closed; one open `- [ ]` means the entity was archived too early.

**The PARA sorting test, and `### Lifecycle`.** *Committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.* A rolling improvement backlog on something you own is an area wearing a project name. Expect existing `projects/` folders to fail this test: a brief whose own status line reads "Active" or "Ongoing maintenance" is describing an area.

**`📅` means a real-world deadline, never an aspiration.** A decision with an invented date is still a deliberation, and the fake date only makes it surface as falsely overdue.

**Skeleton files an older vault may lack.** `resources/scripts/README.md` (the `PARAOS_HOME` resolver snippet plus a table of installed scripts) and `.claude/settings.json` (`autoMemoryEnabled: false`). The settings file is for adopters with no user-level Claude settings; a vault whose user-level settings already set the same keys should not carry a redundant copy.

**Section renames and de-bloat.** `## Filing rules` → `## Filing and naming`, with task markers folded in under `## Actions`. Memory and File formats condensed. `## Integration scripts and their state` shrinks to a pointer: its state buckets, `PARAOS_HOME` resolver, and language preference now live in `resources/scripts/README.md` (above), read when a script is touched rather than every session. Only the secret-never-inside-the-vault rule stays in `CLAUDE.md`.

Also in this revision, both housekeeping rather than migration work:

- **`triage/` never holds a `README.md`.** Every file there is by definition unprocessed, so a permanent one is indistinguishable from a real item and inflates the loose-file count forever. The skeleton ships `.gitkeep` instead. Delete any `triage/README.md` an earlier skeleton left behind.
- **Two machine-read markers at the top of `CLAUDE.md`**: the `<!-- para-os-template: -->` comment above, and a `**Type:**` line for your own tooling to key off. Both must survive every upgrade.
