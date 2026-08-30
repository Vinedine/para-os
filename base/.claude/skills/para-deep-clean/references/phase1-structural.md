# Phase 1 - Structural and housekeeping audit

Goal: identify and fix obvious structural issues before deeper work. Ends with the issues table and its approvals; nothing is applied before that.

## Step 1.1 - Map the vault

A lightweight inventory:

- Top-level folders present (PARA compliance check)
- Entity count per area (properties / projects / clients)
- Empty PARA leaf directories (`resources/ideas/`, `resources/prompts/` often end up empty)
- Root `README.md` shape, per the root-README rule in `CLAUDE.md`. Shape findings are fixed in Phase 2 Step 2.0; state findings move to the owning `brief.md` or `actions.md`.
- **Unfilled template placeholders in `CLAUDE.md`** - `{{...}}` slots the bootstrap never filled. Grep for `{{` across the vault, not just the root README.

Triage emptiness is already enforced by the skill's preconditions - no need to re-check here.

## Step 1.2 - Scan for housekeeping issues

- **Stale draft files**: `.doc` / `.docx` drafts alongside signed `.pdf` finals. Often safe to delete once superseded, but some vaults keep them as searchable text - check the README before proposing deletion.
- **Naming convention violations**: filenames not matching the convention in CLAUDE.md (legacy suffixes like ` - FINAL`, typos, wrong dates, wrong language).
- **Cross-reference link style**: links should match the vault's mode. With collected/spread and `.pdf` siblings, links inside READMEs target `.md` so they work in both modes.
- **Dangling links**: every relative `](path)` in a live-bucket file must resolve to a file that exists. Report each with its source file and the likely intended target. External URLs and cross-drive absolute paths are out of scope.
- **Link syntaxes the audit can't see**: a vault that uses markdown links everywhere can still carry a pocket of Obsidian `[[wikilinks]]` from an older editing habit. They don't render in VS Code preview or on GitHub, and the dangling-link check above steps straight over them - so rot inside them can never surface. Grep for the syntaxes the vault doesn't otherwise use, resolve each target, and propose converting them to the vault's normal form. Piped aliases (`[[target|display text]]`) keep their display text.
- **Archive vs active misclassification**: entities whose README marks them as no longer active (sold, closed, completed, rejected, superseded) but that still live in `areas/` or `projects/`.
- **Duplicate documents**: same content under different filenames, often from migration passes.

## Step 1.2b - Archive-folder hygiene

Audit `archive/` against the vault's **Archive hygiene** conventions in CLAUDE.md:

- **Loose files at the archive root** - anything not in a documented subfolder (`meetings/`, `projects/`, ...). Propose moving, or deleting (individual approval) if thin and fully superseded.
- **Dated-naming violations in `archive/meetings/`** - files not matching the vault's dated pattern. Flag.
- **Single-owner records in `archive/meetings/`** - a record whose own content names exactly one owning project or area (a `**Project:**` line, or every entity link in it resolving to the same folder) belongs in that entity's `sources/`, renamed to the source-document convention. Records naming several entities, or none, are the cross-cutting audit trail and stay. Propose the move **with its inbound links**: grep the vault for the old path first and repoint every hit in the same step, or the move trades a filing error for a set of dangling links the Step 1.2 scan has already run past.
- **Archived entities missing their minimum record** - no `brief.md` / `README.md` or status marker. Flag.
- **Typos or wrong names in already-archived filenames** - the naming scan applies to archived files too. Propose a rename, preserving the source language.

## Step 1.3 - Present the issues table

One table, shown **before** applying anything:

| # | Issue | Where | Proposed fix |
|---|---|---|---|

Wait for explicit approval. **Batch approval is allowed only for non-destructive normalisations** (naming-convention fixes, link-style normalisations, casing fixes). **Deletions, moves between PARA buckets, and any destructive operation require individual approval** - no batching, no exceptions, per [operating-discipline.md](../../para-shared/operating-discipline.md).

## Step 1.4 - Apply

In priority order: non-destructive first (link style, naming consistency), destructive last (file deletions, batched with an explicit list). Never delete a file without an explicit row in the approved table.

## Edge case

- **Entity README references files not in `sources/`**: flag as a content-vs-filesystem mismatch. Either find the file (often still in triage or another mailbox) or update the README to mark it missing.
