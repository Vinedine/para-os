# Phase 1 - Structural and housekeeping audit

Every finding below is a field of the `--phase 1` scan except five the agent judges itself: naming outside `archive/meetings/`, archive-versus-active, single-owner records in `archive/meetings/`, figures with no as-of date, and the root `README.md` shape.

## Step 1.1 - Map the vault

`map` holds the top-level folders, the entity count per bucket and the empty leaf directories. Beside it:

- **Root `README.md` shape**, against the root-README rule in `CLAUDE.md`. Shape findings are fixed in Phase 2 Step 2.0; work state moves to the owning `brief.md` or `actions.md`.
- **Unfilled `{{...}}` placeholders** (`placeholders`) in files the bootstrap wrote. One in a file whose job is to hold it is not a finding; where that is unclear, ask.

## Step 1.2 - Housekeeping

**A file the vault declares generated** (its header, or `CLAUDE.md` or a script README naming it a script's output) is never edited: report the finding against its source, fixed there and regenerated. Before regenerating or deleting one, diff it against what its generator still produces: content with no surviving source is routed, not discarded.

- **Stale drafts** (`stale_drafts`): a `.doc`/`.docx` beside its signed `.pdf`. Check the README first: some vaults keep drafts as searchable text.
- **Naming violations**, archived files included, judged per [A vault's rule files](../../para-shared/operating-discipline.md#a-vaults-rule-files): legacy suffixes like ` - FINAL`, typos, wrong dates, wrong language.
- **Dangling links** (`dangling`), each with its likely intended target; give a verdict only where every `checker_verified` field is true. An absolute machine-local path is not dangling: mention it once as a portability finding. A README citing a file missing from `sources/` is the same finding: find the file, or mark it missing.
- **Wikilinks** (`wikilinks`), which the dangling check cannot see: propose the vault's normal link form to the note each `resolved` to, a piped alias keeping its display text.
- **Uncited contacts** (`uncited_contacts`): a carded person named in a live file that never links the card. Propose linking the first mention per file. Contact details beside a mention (`inline_contact_details`) move to the card; `names_on_line` lists every carded name on the line, so **never attribute an email or phone by same-line proximity**. Drop third-party verbatim files wherever they are filed, and records that are evidence in all but folder name (a usage review, a digest, a run log); `uncited_exempt` names those a path proxy already dropped, for the operator to override.
- **Archive vs active**: an entity in `areas/` or `projects/` whose README marks it sold, closed, completed, rejected or superseded. `/para-archive` closes it out.
- **Duplicates** (`duplicates.groups`), by content hash; a `cross_entity` group is its own finding. Name what `duplicates.skipped` lists.
- **One figure, two values** (`figure_pairs`): a roll-up file states a figure about an entity that its own file does not. Name the file that should own it and propose links in place of the copies. Which value is right is Step 3.5's question.
- **Figures with no as-of date, or projections among facts**: flag the tables that break the shape `CLAUDE.md` prescribes to keep them apart. A formatting finding, not an accuracy one.

## Step 1.2b - Filing hygiene

Against the vault's **Archive hygiene** rule and its checkbox table:

- **Loose files at the archive root** (`archive.loose_root_files`): move, or delete if thin and superseded.
- **Undated names in `archive/meetings/`** (`archive.meetings_naming`).
- **Single-owner records in `archive/meetings/`**: a record naming exactly one owning entity (a `**Project:**` line, or every entity link resolving to one folder) moves to that entity's `sources/`, renamed to the source-document convention, or to the entity folder where its bucket allows no `sources/`. Several entities or none: it stays.
- **Open checkboxes where the vault forbids them** (`archive.misplaced_checkboxes`, one list per bucket). In third-party verbatim content (a transcript's extracted next steps, quoted correspondence), propose the **frozen-record marker**, never the tick: a blockquote before the first checkbox, or a line in the first fifteen naming it "frozen record", "third-party verbatim" or "kept as generated", as an HTML comment where it must not render. The scan skips a file carrying one: name it as excluded. Route surviving work to the owning `actions.md`.
- **Checkboxes on a contact card under `never`** (the `areas/network` list, and `closed` for ticked ones), one item at a time: a ticked item becomes a plain bullet under `## History` (before `## Next actions`, created if missing), checkbox and `✅` stripped, `_(closed YYYY-MM-DD)_` appended; an open one goes to the entity it serves, or is dropped. `## Next actions` keeps its empty sentinel.
- **Archived entities missing their minimum record** (`archive.missing_record`) or a status marker.
- **Loose files at the resources root** (`resources_loose`): propose the area or project it serves, else a kind folder.

## Step 1.3 - Issues table

One table, shown before anything is applied:

| # | Issue | Where | Proposed fix |
|---|---|---|---|

## Step 1.4 - Apply

Lossless changes first, deletions last and one at a time, per [Deleting a file](../../para-shared/operating-discipline.md#deleting-a-file). Before any move, run the shared `paraos_vault.py move-plan <src> <dst>` and apply its `inside` and `inbound` rewrites; re-run the dangling check after the moves.
