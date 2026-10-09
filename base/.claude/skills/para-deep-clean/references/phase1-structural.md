# Phase 1 - Structural and housekeeping audit

`scripts/clean_scan.py --phase 1` implements every mechanical check below except five the agent makes itself: naming violations outside `archive/meetings/`, archive-versus-active misclassification, single-owner records in `archive/meetings/`, figures with no as-of date, and the root `README.md` shape.

Goal: identify and fix obvious structural issues before deeper work.

## Step 1.1 - Map the vault

The scan's `map` holds the top-level folders (PARA compliance), the entity count per bucket and the empty leaf directories (`resources/ideas/` and `resources/prompts/` often end up empty). Beside it:

- Root `README.md` shape, per the root-README rule in `CLAUDE.md`. Shape findings are fixed in Phase 2 Step 2.0; state findings move to the owning `brief.md` or `actions.md`.
- **Unfilled template placeholders** (`placeholders`): `{{...}}` slots the bootstrap never filled, in the files it wrote. **A placeholder in a file whose job is to hold one is not a finding.** Where one sits somewhere genuinely ambiguous, ask rather than filing it.

## Step 1.2 - Scan for housekeeping issues

**A file the vault declares generated** (its header says it is machine-written, or `CLAUDE.md` or a script README names it as a script's output) is never edited: report each finding in it against the source file it came from, fixed there and followed by a regenerate. Before regenerating or deleting a generated file, diff it against what its generator can still produce: content with no surviving source is a finding to route, not to discard.

- **Stale draft files** (`stale_drafts`): a `.doc` / `.docx` draft beside its signed `.pdf` final. Some vaults keep them as searchable text: check the README before proposing deletion.
- **Naming convention violations**: filenames not matching the vault's convention, judged per [A vault's rule files](../../para-shared/operating-discipline.md#a-vaults-rule-files) (legacy suffixes like ` - FINAL`, typos, wrong dates, wrong language).
- **Dangling links** (`dangling`): a relative link in a live-bucket file, a `.claude/rules/` file or under `archive/` whose target does not exist. Report each with its source file and the likely intended target, and report a verdict only where every `checker_verified` field is true. An absolute machine-local path in any form (a UNC share `\\host\...` among them) is not a dangling link, though worth mentioning once as a portability finding.
- **Link syntaxes the dangling check can't see** (`wikilinks`): a pocket of Obsidian `[[wikilinks]]` in a vault that otherwise uses markdown links, each with the note it `resolved` to. Propose converting them to the vault's normal form; a piped alias (`[[target|display text]]`) keeps its display text.
- **Uncited contacts** (`uncited_contacts`): a person who *has* a card, named in prose in a live-bucket file that never links to it, one entry per card with the files naming it. Contact details beside a mention (`inline_contact_details`: an email or a phone on a line naming a carded person) are a second finding. Propose linking the first mention per file and moving the details to the card. A card marked `principal` is the vault's own subject, linked from the root README's Identity section, and is listed only where the root README or its top-level area README fails to link it.

  **Exclusions the scan cannot make.** Drop **third-party verbatim files** - synced publications, transcripts, quoted correspondence, wherever they are filed, a `sources/` folder or the area's own folder in a vault that allows no `sources/` there - per [operating-discipline.md](../../para-shared/operating-discipline.md), and **analytical and ledger records that are evidence in all but folder name** (a session-usage review, an activity digest, a run log); `uncited_exempt` names the files a path proxy already dropped, for the operator to override. `names_on_line` lists every carded name sharing a detail's line: **never attribute an inline email or phone to its owner by same-line proximity**.
- **Archive vs active misclassification**: entities whose README marks them as no longer active (sold, closed, completed, rejected, superseded) but that still live in `areas/` or `projects/`.
- **Duplicate documents** (`duplicates.groups`): the same content under different filenames, by content hash. A group marked `cross_entity` spans two entities and is its own finding. What `duplicates.skipped` lists (a `photos/`, `plans/`, `styles/` or `public/` folder's files) is named in the report, never silently dropped.
- **The same number, two files, two values** (`figure_pairs`): a roll-up file (an index or portfolio README, the root README, a dashboard) stating a figure about an entity that the entity's own file does not. Two files disagreeing is a finding on its own, with no document needed to prove either wrong. Report the pair, name the file that should own the figure per the vault's say-it-once rule, and propose that every other mention become a link to it rather than a second copy. **Do not resolve the numbers here** - which value is right is Step 3.5's question and a source document's answer.
- **A figure with no as-of date, or a projection sitting among facts**: a cost, balance, margin or valuation stated without the date it was true, or an estimate in the same table as contracted and booked figures. Where the vault's `CLAUDE.md` prescribes a shape that keeps the two apart - a dated column, a separate projections table - flag the tables that mix them. A formatting finding, not an accuracy one.

## Step 1.2b - Archive-folder hygiene

Audit `archive/` against the vault's **Archive hygiene** conventions in CLAUDE.md:

- **Loose files at the archive root** (`archive.loose_root_files`). Propose moving, or deleting (individual approval) if thin and fully superseded.
- **Dated-naming violations in `archive/meetings/`** (`archive.meetings_naming`) - files not matching the vault's dated pattern: an eight-digit date prefix, unless the vault's naming convention sets another, passed as `--dated-pattern <regex>`. Flag.
- **Single-owner records in `archive/meetings/`** - a record whose own content names exactly one owning project or area (a `**Project:**` line, or every entity link in it resolving to the same folder) belongs in that entity's `sources/`, renamed to the source-document convention - or, where the vault's own filing rule allows that entity's bucket no `sources/` folder, the entity folder itself. Records naming several entities, or none, are the cross-cutting audit trail and stay. Propose the move **with its inbound links**: grep the vault for the old path first and repoint every hit in the same step.
- **Open checkboxes in an archived entity** (`archive.misplaced_checkboxes`, its `archive` list) - the vault's Archive hygiene rule reads one open `- [ ]` as archived too early. A checkbox in **third-party verbatim content** - a transcript's auto-extracted "next steps", quoted correspondence - records what a tool or a person said, and [operating-discipline.md](../../para-shared/operating-discipline.md) forbids ticking it. Propose the **frozen-record marker**, never the tick: a blockquote before the first checkbox, or a line in the record's first fifteen naming it "frozen record", "third-party verbatim" or "kept as generated", as an HTML comment where it must not render (`<!-- frozen record: sent to client -->`). Route any surviving work to the owning entity's `actions.md`.

- **Archived entities missing their minimum record** (`archive.missing_record`: no `brief.md` or `README.md`), or with no status marker. Flag.
- **Typos or wrong names in already-archived filenames** - the naming scan applies to archived files too. Propose a rename, preserving the source language.

**Checkboxes on contact cards where the vault's `areas/network/` checkbox row says `never`** (`archive.misplaced_checkboxes`, its `areas/network` list for open items and its `closed` list for ticked ones) are filing errors, repaired one item at a time: a ticked item becomes a plain bullet in the card's `## History` section, placed before `## Next actions` and created if missing, its checkbox and `✅` marker stripped and `_(closed YYYY-MM-DD)_` appended; an open item is routed to the project or area it serves, or dropped. `## Next actions` keeps the empty sentinel.

**Loose files at the resources root** (`resources_loose`): any file there but `README.md` and `.gitkeep`. Propose a destination for each: the area or project it serves when one owns it, else a kind folder, a new one if none fits. Repoint its inbound links in the same step.

## Step 1.3 - Present the issues table

One table, shown **before** applying anything:

| # | Issue | Where | Proposed fix |
|---|---|---|---|

Wait for explicit approval. **Batch approval is allowed only for non-destructive normalisations** (naming-convention fixes, link-style normalisations, casing fixes). **Deletions, moves between PARA buckets, and any destructive operation require individual approval**, per [operating-discipline.md](../../para-shared/operating-discipline.md).

## Step 1.4 - Apply

In priority order: non-destructive first (link style, naming consistency), destructive last. Apply the batched normalisations from the issues table, then the deletions **one at a time**, per [operating-discipline.md](../../para-shared/operating-discipline.md#deleting-a-file).

**Every approved move carries its links.** Run `move_plan` before moving a file or folder, apply its `inside` rewrites (links inside the moved content pointing out) and its `inbound` rewrites (links from the rest of the vault pointing in), per [operating-discipline.md](../../para-shared/operating-discipline.md) "Moving an entity folder". Re-run the dangling-link scan after any move in this step.

## Edge case

- **Entity README references files not in `sources/`**: flag as a content-vs-filesystem mismatch. Either find the file (often still in triage or another mailbox) or update the README to mark it missing.
