# Phase 1 - Structural and housekeeping audit

`scripts/clean_scan.py --phase 1` implements every mechanical check below except five, done by hand: naming violations outside `archive/meetings/`, archive-versus-active misclassification, single-owner records in `archive/meetings/`, figures with no as-of date, and the root `README.md` shape. Read this file when a result looks wrong, or when running the scan by hand per Step 0.

Goal: identify and fix obvious structural issues before deeper work.

## Step 1.1 - Map the vault

A lightweight inventory:

- Top-level folders present (PARA compliance check)
- Entity count per area (properties / projects / clients)
- Empty PARA leaf directories (`resources/ideas/`, `resources/prompts/` often end up empty)
- Root `README.md` shape, per the root-README rule in `CLAUDE.md`. Shape findings are fixed in Phase 2 Step 2.0; state findings move to the owning `brief.md` or `actions.md`.
- **Unfilled template placeholders in `CLAUDE.md`** - `{{...}}` slots the bootstrap never filled. Grep for `{{` across the vault, not just the root README. **A placeholder in a file whose job is to hold one is not a finding.** Scope the finding to files the bootstrap actually wrote (the root `README.md`, `CLAUDE.md`, entity briefs and action files) and treat `resources/prompts/` and any folder the vault's own `CLAUDE.md` describes as holding templates as out of scope. Where a placeholder sits somewhere genuinely ambiguous, ask rather than filing it.

## Step 1.2 - Scan for housekeeping issues

**A file the vault declares generated** (its header says it is machine-written, or `CLAUDE.md` or a script README names it as a script's output) is never edited: report each finding in it against the source file it came from, fixed there and followed by a regenerate. Before regenerating or deleting a generated file, diff it against what its generator can still produce: content with no surviving source is a finding to route, not to discard.

- **Stale draft files**: `.doc` / `.docx` drafts alongside signed `.pdf` finals. Some vaults keep them as searchable text: check the README before proposing deletion.
- **Naming convention violations**: filenames not matching the vault's convention, judged per [A vault's rule files](../../para-shared/operating-discipline.md#a-vaults-rule-files) (legacy suffixes like ` - FINAL`, typos, wrong dates, wrong language).
- **Dangling links**: every relative `](path)` in a live-bucket file, a `.claude/rules/` file or under `archive/` must resolve to a file that exists; a path an archived record names in prose is history, not a link. Report each with its source file and the likely intended target. Out of scope: external URLs, and absolute paths in any form they take - a drive-letter path (`C:\...`), a UNC share (`\\host\...`), and a **`file:///` URI**. An absolute machine-local path is worth mentioning once as a portability finding, but it is not a dangling link. Nor is a template placeholder: a bare `<placeholder>` target, or `<...>` inside a path. A whole target in angle brackets (`[x](<projects/my file.md>)`) is a real link, brackets stripped, and a trailing `"title"` is never part of a target.

  **Percent-decode the href before resolving it.** Decode with a real URL-decoder (`urllib.parse.unquote`), never a shell substitution. An href ends at the `)` that balances its opening `(`. Strip any `?query` or `#fragment` before resolving (a link that is nothing else names no file), and resolve relative to the **linking file's own folder**, not the vault root. Scanning by hand, apply the same rules `paraos_vault.dangling_links()` does.

  **Strip fenced blocks and inline code spans before extracting hrefs**, in this check and in every other scan in this phase, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md).

  **Validate the checker in three directions before reporting a verdict.** Point it at known-good links whose targets have spaces and parentheses and confirm they pass; point it at a link you have deliberately broken and confirm it fails; point it at a broken link **inside a fenced code block** and confirm it is skipped. `clean_scan.py --phase 1` reports this as `checker_verified`.
- **Link syntaxes the audit can't see**: a vault that uses markdown links everywhere can still carry a pocket of Obsidian `[[wikilinks]]`, which the dangling-link check above steps over. Grep for the syntaxes the vault doesn't otherwise use, resolve each target, and propose converting them to the vault's normal form. Piped aliases (`[[target|display text]]`) keep their display text.
- **Uncited contacts**: a person who *has* a card, named in a live-bucket file that never links to it. A card's name is its H1 heading plus every alias a `**Aliases:**` or `Also:` line lists; only a prose mention counts, never one inside backticks (per **A quoted syntax is not a used syntax**) or inside a link's text or target, while a link to the card anywhere in the file still cites it. For each `areas/network/` card, grep its person across the live buckets **and the root README**, skipping every `sources/` folder. A mention with no link is one finding, and contact details sitting inline beside that mention (an email address, a phone number) are a second. An email matches `name@domain.tld`; a phone matches a leading `+`, or at least eight digits separated only by spaces, dots or slashes, never a `YYYY-MM-DD` or `YYYYMMDD` date shape - read off the line with every link target stripped and percent-decoded first. Propose linking the first mention per file and moving the details to the card. **Principals are the exception**: a person the root README's **Identity section** links (a link elsewhere in the README exempts no one) is the vault's own subject: require a link only in the root README and the top-level area README (the README of the area folder the card sits under, else the root README), and count the rest as cited.

  **Exclusions.** Skip **third-party verbatim files** - synced publications, transcripts, quoted correspondence, wherever they are filed, a `sources/` folder or the area's own folder in a vault that allows no `sources/` there - per [operating-discipline.md](../../para-shared/operating-discipline.md). Skip **analytical and ledger records that are evidence in all but folder name** (a session-usage review, an activity digest, a run log). The mechanical proxy is any path segment or the filename carrying "log", "usage", "review", "digest", "ledger" or "transcript" as a whole word, case-insensitively; a file the proxy catches is dropped from the finding but still named, under `uncited_exempt`, for the operator to override. Skip **text meant for outside the vault**: `resources/prompts/`, each folder the vault's `CLAUDE.md` holds templates in (`--templates-dir`) or a script's output in (`--generated-dir`), and a **client-facing document** such as a sent proposal, marked by the Step 1.2b frozen-record marker in its first fifteen lines, as an HTML comment (`<!-- frozen record: sent to client -->`) where it must not render. Skip a register cell whose column the register's rule file declares a name, not a link (`--name-only-column <file>:<column>`). And **never attribute an inline email or phone to its owner by same-line proximity** - report every carded name sharing the line and leave the assignment unresolved for the skill to make.
- **Archive vs active misclassification**: entities whose README marks them as no longer active (sold, closed, completed, rejected, superseded) but that still live in `areas/` or `projects/`.
- **Duplicate documents**: same content under different filenames. Compared by content hash, never filename or size; a file under 200 bytes is excluded, and a `photos/` or `plans/` folder, or a build's own `styles/` or `public/` folder, is set aside from the comparison, its contents named separately rather than silently dropped. A pair spanning two different entities is its own finding: an entity is its live folder (`projects/<name>`, `areas/<name>`), or, under `archive/` or `resources/ideas/`, the folder two levels below that bucket (`archive/projects/<name>`, `resources/ideas/<name>`).
- **The same number, two files, two values**: a headline figure an entity's own file states and a roll-up file (an index or portfolio README, the root README, a dashboard) restates about that entity must agree. A figure is a currency-prefixed number, or a number followed by `%` or `k` (`€10,000`, `EUR19k`, `12%`). Grep each entity's key figures (cost, price, margin, total, stage, date) across the live buckets and compare, matching the entity's name on word boundaries against a line with every link target stripped and percent-decoded first. Two files disagreeing is a finding on its own, with no document needed to prove either wrong. Both sides must state a figure: an entity file stating none makes no pair. Report the pair, name the file that should own the figure per the vault's say-it-once rule, and propose that every other mention become a link to it rather than a second copy. **Do not resolve the numbers here** - which value is right is Step 3.5's question and a source document's answer.
- **A figure with no as-of date, or a projection sitting among facts**: a cost, balance, margin or valuation stated without the date it was true, or an estimate in the same table as contracted and booked figures. Where the vault's `CLAUDE.md` prescribes a shape that keeps the two apart - a dated column, a separate projections table - flag the tables that mix them. A formatting finding, not an accuracy one.

## Step 1.2b - Archive-folder hygiene

Audit `archive/` against the vault's **Archive hygiene** conventions in CLAUDE.md:

- **Loose files at the archive root** - anything not in a documented subfolder (`meetings/`, `projects/`, ...). Propose moving, or deleting (individual approval) if thin and fully superseded.
- **Dated-naming violations in `archive/meetings/`** - files not matching the vault's dated pattern: an eight-digit date prefix by default (`^\d{8} `, e.g. `20260101 Kickoff.md`), overridable per vault via `clean_scan.py --dated-pattern` where the naming convention differs. Flag.
- **Single-owner records in `archive/meetings/`** - a record whose own content names exactly one owning project or area (a `**Project:**` line, or every entity link in it resolving to the same folder) belongs in that entity's `sources/`, renamed to the source-document convention - or, where the vault's own filing rule allows that entity's bucket no `sources/` folder, the entity folder itself. Records naming several entities, or none, are the cross-cutting audit trail and stay. Propose the move **with its inbound links**: grep the vault for the old path first and repoint every hit in the same step.
- **Open checkboxes in an archived entity** - the vault's Archive hygiene rule reads one open `- [ ]` as archived too early, and two kinds of line satisfy that test without being work. A checkbox **inside a fenced code block** is a sample, not a checkbox, so exclude fence content before counting. A checkbox in **third-party verbatim content** - a transcript's auto-extracted "next steps", quoted correspondence - records what a tool or a person said, and [operating-discipline.md](../../para-shared/operating-discipline.md) forbids ticking it. The disposition for the second is the **frozen-record marker**: a blockquote before the first checkbox, or a plain-prose line in the record's first fifteen lines naming it "frozen record", "third-party verbatim" or "kept as generated" (case-insensitively) - either is enough on its own, no blockquote required for the words - with any surviving work routed to the owning entity's `actions.md`. Propose the marker, never the tick.

- **Archived entities missing their minimum record** - no `brief.md` / `README.md` or status marker. Flag.
- **Typos or wrong names in already-archived filenames** - the naming scan applies to archived files too. Propose a rename, preserving the source language.

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
