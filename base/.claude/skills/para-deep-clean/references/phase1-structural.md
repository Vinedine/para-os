# Phase 1 - Structural and housekeeping audit

Goal: identify and fix obvious structural issues before deeper work. Ends with the issues table and its approvals; nothing is applied before that.

## Step 1.1 - Map the vault

A lightweight inventory:

- Top-level folders present (PARA compliance check)
- Entity count per area (properties / projects / clients)
- Empty PARA leaf directories (`resources/ideas/`, `resources/prompts/` often end up empty)
- Root `README.md` shape, per the root-README rule in `CLAUDE.md`. Shape findings are fixed in Phase 2 Step 2.0; state findings move to the owning `brief.md` or `actions.md`.
- **Unfilled template placeholders in `CLAUDE.md`** - `{{...}}` slots the bootstrap never filled. Grep for `{{` across the vault, not just the root README. **A placeholder in a file whose job is to hold one is not a finding**: a vault that keeps templates as content - an onboarding mail to fill in per client, a `CLAUDE.md` skeleton to hand an adopter - carries `{{...}}` there on purpose, and reporting them means this check fires on every run until nobody reads it. Scope the finding to files the bootstrap actually wrote (the root `README.md`, `CLAUDE.md`, entity briefs and action files) and treat `resources/prompts/` and any folder the vault's own `CLAUDE.md` describes as holding templates as out of scope. Where a placeholder sits somewhere genuinely ambiguous, ask rather than filing it.

Triage emptiness is already enforced by the skill's preconditions - no need to re-check here.

## Step 1.2 - Scan for housekeeping issues

- **Stale draft files**: `.doc` / `.docx` drafts alongside signed `.pdf` finals. Often safe to delete once superseded, but some vaults keep them as searchable text - check the README before proposing deletion.
- **Naming convention violations**: filenames not matching the convention in CLAUDE.md (legacy suffixes like ` - FINAL`, typos, wrong dates, wrong language).
- **Cross-reference link style**: links should match the vault's mode. With collected/spread and `.pdf` siblings, links inside READMEs target `.md` so they work in both modes.
- **Dangling links**: every relative `](path)` in a live-bucket file must resolve to a file that exists. Report each with its source file and the likely intended target. Out of scope: external URLs, and absolute paths in any form they take - a drive-letter path (`C:\...`), a UNC share (`\\host\...`), and a **`file:///` URI**, which is the one that looks relative enough to slip through a naive prefix test and get reported. An absolute machine-local path is worth mentioning once as a portability finding, since it resolves for nobody but the person who wrote it, but it is not a dangling link and does not belong in this count.

  **Percent-decode the href before resolving it, or this check reports the whole vault.** A filing convention built on `YYYYMMDD <Subject> - <Description>.<ext>` puts spaces in every filename, and a markdown link to one escapes each as `%20` - so comparing the raw href against disk fails on every correctly-written link in the vault. Decode with a real URL-decoder (`urllib.parse.unquote`); a shell substitution mangles `%20` into something that then genuinely does not exist, which turns a false alarm into a confident one. Strip any `#fragment` before resolving, and resolve relative to the **linking file's own folder**, not the vault root.

  **Strip code before matching - both kinds.** A fenced block hides links from the scan, which is a false clean; an *inline* span does the opposite and is the commoner of the two, because a rule file or a convention section quotes the link it wants written - `` `[portfolio overview](../README.md)` `` - and a naive matcher reports that quotation as a dangling link from the file that is only describing it. Remove fenced blocks and inline spans from the text before extracting hrefs.

  **Skip anything inside a fenced code block**, in this check and in every other scan in this phase, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md), which owns the rule and the evidence for it.

  **Validate the checker in three directions before reporting a verdict**, because it is wrong in three ways and only one of them is loud. Point it at a known-good link whose target has spaces and confirm it passes; point it at a link you have deliberately broken and confirm it fails; point it at a broken link **inside a fenced code block** and confirm it is skipped. A checker that cries wolf on every conforming link gets switched off, and it takes the real findings with it; one that silently resolves everything reports a clean vault it never read; and one that reads code fences reports the vault's own documentation as rot.
- **Link syntaxes the audit can't see**: a vault that uses markdown links everywhere can still carry a pocket of Obsidian `[[wikilinks]]` from an older editing habit. They don't render in VS Code preview or on GitHub, and the dangling-link check above steps straight over them - so rot inside them can never surface. Grep for the syntaxes the vault doesn't otherwise use, resolve each target, and propose converting them to the vault's normal form. Piped aliases (`[[target|display text]]`) keep their display text.
- **Uncited contacts**: the mirror of the dangling check, and invisible to it - a person who *has* a card, named in a live-bucket file that never links to it. For each `areas/network/` card, grep its person across the live buckets **and the root README**, skipping every `sources/` folder, since a source document is evidence and is never edited to carry a link. A mention with no link is one finding, and contact details sitting inline beside that mention (an email address, a phone number) are a second, since the card owns them. Propose linking the first mention per file and moving the details to the card. **Principals are the exception**: a person the root README **Identity section** links is the vault's own subject, named in nearly every file, and linking each first mention is noise rather than navigation - for them require only the root README and the top-level area README, and scope this to Identity so that linking an advisor or a counterparty elsewhere in the README does not silently exempt them everywhere, and count the rest as cited. A counterparty is met once and needs the link; a principal is reached from the documents that orient the reader.

  **Three exclusions, or this check returns a number nobody reads.** Run against one 42-card vault it produced 70 findings with no contact-hygiene problem behind them. Skip **third-party verbatim files** - synced publications, transcripts, quoted correspondence - which [operating-discipline.md](../../para-shared/operating-discipline.md) already places out of scope for every normalisation pass, and which is exactly where a frequently-named person co-occurs most. Skip **analytical and ledger records that are evidence in all but folder name** (a session-usage review, an activity digest, a run log): they name people as data, and linking each mention is noise rather than navigation. And **attribute an inline email or phone to its owner before reporting it** - matching on same-line proximity alone files a third party's address under whoever else is named in the sentence, which is a false finding pointing at a real one in the wrong place. The rule stated for the link checker above holds here too: a check that cries wolf gets switched off, and it takes the real findings with it.
- **Archive vs active misclassification**: entities whose README marks them as no longer active (sold, closed, completed, rejected, superseded) but that still live in `areas/` or `projects/`.
- **Duplicate documents**: same content under different filenames, often from migration passes.
- **The same number, two files, two values**: a headline figure an entity's own file states and a roll-up file (an index or portfolio README, the root README, a dashboard) restates about that entity must agree. Grep each entity's key figures (cost, price, margin, total, stage, date) across the live buckets and compare. Two files disagreeing is a finding on its own, with no document needed to prove either wrong: one of them is stale, and a reader has no way to tell which. Report the pair, name the file that should own the figure per the vault's say-it-once rule, and propose that every other mention become a link to it rather than a second copy. **Do not resolve the numbers here** - which value is right is Step 3.5's question and a source document's answer, and picking the more recent-looking one is exactly the guess that put the vault in this state.
- **A figure with no as-of date, or a projection sitting among facts**: a cost, balance, margin or valuation stated without the date it was true is unauditable and goes stale quietly, and an estimate in the same table as contracted and booked figures gets added to them by the next reader. Where the vault's `CLAUDE.md` prescribes a shape that keeps the two apart - a dated column, a separate projections table - flag the tables that mix them. This is a formatting finding and not an accuracy one: separating the two is in scope here, re-deriving the numbers is Phase 3.5's question and a source document's answer.

## Step 1.2b - Archive-folder hygiene

Audit `archive/` against the vault's **Archive hygiene** conventions in CLAUDE.md:

- **Loose files at the archive root** - anything not in a documented subfolder (`meetings/`, `projects/`, ...). Propose moving, or deleting (individual approval) if thin and fully superseded.
- **Dated-naming violations in `archive/meetings/`** - files not matching the vault's dated pattern. Flag.
- **Single-owner records in `archive/meetings/`** - a record whose own content names exactly one owning project or area (a `**Project:**` line, or every entity link in it resolving to the same folder) belongs in that entity's `sources/`, renamed to the source-document convention. Records naming several entities, or none, are the cross-cutting audit trail and stay. Propose the move **with its inbound links**: grep the vault for the old path first and repoint every hit in the same step, or the move trades a filing error for a set of dangling links the Step 1.2 scan has already run past.
- **Open checkboxes in an archived entity** - the vault's Archive hygiene rule reads one open `- [ ]` as archived too early, and two kinds of line satisfy that test without being work. A checkbox **inside a fenced code block** is a sample - a deck or a README showing what an `actions.md` looks like - and is not a checkbox at all, so exclude fence content before counting. A checkbox in **third-party verbatim content** - a transcript's auto-extracted "next steps", quoted correspondence - records what a tool or a person said, and [operating-discipline.md](../../para-shared/operating-discipline.md) forbids ticking it. Neither is live work and neither means the entity was archived early. The disposition for the second is the **frozen-record marker**: one line at the top of the record saying it is third-party verbatim, kept as generated, its boxes never ticked, with any surviving work routed to the owning entity's `actions.md`. Propose the marker, never the tick.

- **Archived entities missing their minimum record** - no `brief.md` / `README.md` or status marker. Flag.
- **Typos or wrong names in already-archived filenames** - the naming scan applies to archived files too. Propose a rename, preserving the source language.

## Step 1.3 - Present the issues table

One table, shown **before** applying anything:

| # | Issue | Where | Proposed fix |
|---|---|---|---|

Wait for explicit approval. **Batch approval is allowed only for non-destructive normalisations** (naming-convention fixes, link-style normalisations, casing fixes). **Deletions, moves between PARA buckets, and any destructive operation require individual approval** - no batching, no exceptions, per [operating-discipline.md](../../para-shared/operating-discipline.md).

## Step 1.4 - Apply

In priority order: non-destructive first (link style, naming consistency), destructive last. Apply the batched normalisations from the issues table, then the deletions **one at a time, each on its own approval** - never as a list approved together, per Step 1.3 above and the skill's Strict rules.

## Edge case

- **Entity README references files not in `sources/`**: flag as a content-vs-filesystem mismatch. Either find the file (often still in triage or another mailbox) or update the README to mark it missing.
