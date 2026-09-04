# BelFoot Vault Conventions

<!-- para-os-template: 2026.09.01 -->
**Type:** vault (default flavor: plain editable markdown)

The consulting vault for BelFoot Royal Sporting Club ("BelFoot FC", Belgian Pro League) and its multi-stream IT modernisation programme - an external consultant engagement, started Q1 2026, running through 2027. Per-vault guidance for Claude Code sessions.

Both lines above are machine-read (the comment by `/para-upgrade`, the type by your own tooling) and must survive every upgrade.

## Context

BelFoot internal data (financials, employee records, contracts) is confidential to this engagement. This vault is the consultant's working copy; outputs that leave it (decks, reports, emails) are reviewed before send. Never reference another client engagement here - cross-client context violates the engagement letter.

**This is a synthetic example vault with a frozen reference date of 2026-06-24** (see the top of `README.md`). Every date in it is internally consistent as of that day and anchored to real match days. Do not "refresh" dates to the current calendar, do not mark items overdue relative to today, and do not treat the gap as drift to clean up - judge the vault against 2026-06-24.

## PARA layout

The sorting test between buckets: **committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.**

- **triage/** - capture area for unprocessed artifacts before they get filed (call notes, screenshots, meeting transcripts, scanned docs, ad-hoc thoughts). Process via `/para-triage`. It never holds a `README.md`: every file here is by definition unprocessed, so a permanent one is indistinguishable from a real item and inflates the loose-file count forever. A `.gitkeep` keeps the empty folder in git.
- **projects/** - time-bound IT workstreams with a committed deliverable and deadline, one folder per workstream. Each holds a `brief.md` (what it is, who it's for, scope, stakeholders, deadline), an `actions.md` (task list with Obsidian Tasks markers, see below), and a `sources/` subfolder for raw material (RFP PDFs, vendor decks, scanned contracts). A workstream needs a committed deliverable **and** a date; a rolling improvement backlog on a system the club already runs is an area wearing a project name.
- **areas/** - ongoing responsibilities: anything live that gets maintained, with no end date. `stadium/` = the stadium modernisation programme as a standing responsibility: cross-cutting strategic actions not tied to a single workstream. `network/` = one file per BelFoot stakeholder. Systems that gate each other (the wallet, the ticketing platform it integrates with, the stadium network both depend on) stay **one** area.
- **resources/** - reusable reference (procurement templates, vendor evaluations, regulatory notes). `prompts/` = reusable specs and drafts. `ideas/` = concept-stage workstreams to pick future projects from: one folder per idea, `brief.md` only, holding its thinking as open questions plus at most one prose "revisit when X" trigger. `scripts/` = persistent tools the vault needs; their runtime state lives *outside* the vault (see "Integration scripts and their state" below).
- **archive/** - inactive artifacts. `meetings/` = conversation records spanning several entities. `projects/` = completed workstreams and `ideas/` = shelved concepts (both filled by `/para-archive`).

Root `README.md` is the master document, single source of truth for identity, operating model, and track record; derived outputs regenerate from it. Its first four `##` headings are exactly `Identity`, `Operating model`, `Track record`, `Vision`, in that order and in English whatever the body language, and Vision (the end state and its horizon) is never a stub. Vault-specific sections follow them, an optional `## Principles` (standing decisions not to relitigate) among them. It carries no hand-maintained **work** state - no checkbox, `📅` marker, project status list, deadline table, or Status column in a table listing workstreams or entities: live state belongs in `projects/` and `areas/` and surfaces through `/para-daily-brief`. A status *fact* about the club itself is not work state and stays - a registration table reading `| Status | Active |` alongside a VAT number is describing the entity, not tracking a task.

### Lifecycle

- `/para-new` **creates** an entity - a project, an area, an idea, or a contact - settling its shape against the sorting test above before scaffolding anything, and runs the idea-to-project promotion below.
- An idea **promotes** to `projects/` when someone is waiting on a deliverable by a date, money or a formal engagement is committed, or a go/no-go review is on the calendar - and it earns its `actions.md` at that moment, not before. Retiring an idea is always the operator's call, never automatic: an idea that never happened goes to `archive/ideas/`, a workstream where real work ran and then stopped goes to `archive/projects/`.
- The next big, dated push on a maintained system is a **project running alongside its area**; when that project archives, surviving work returns to the area.
- An entity **archives whole** - brief, actions, sources together, via `/para-archive` - with surviving open items routed out *first* (to `areas/stadium/actions.md`, a successor workstream, or the stakeholder's contact file).
- **Every move repoints inbound links in the same pass**, not just archiving. `/para-deep-clean` audits for dangling links.

### Archive hygiene

What a clean `archive/` looks like (applied on the way in, and audited by `/para-deep-clean`):

- **No live work in the archive.** An archived entity has zero open actions - every item done, or open items softened to an explicit "fully closed; minor gaps not material" note. A closed workstream must not keep surfacing in `/para-daily-brief`.
- **History archives; living references go to `resources/`.** Brief, actions, and one-time migration/handoff notes are history - they archive with the entity. Reusable material (procurement templates, vendor evaluations, anything other live work links to as a resource) is *not* buried in the archive; route it to `resources/<name>/`.
- **No loose files at the archive root.** Everything under `archive/` lives in a subfolder (`meetings/`, `projects/`, ...). A stray top-level file is misfiled.
- **Minimum record.** Each archived entity carries a status marker (why it's archived) and a `brief.md`/`README.md`, so it's self-explanatory years later.
- **Zero dangling links.** The general repoint-on-move rule above, audited at the archive boundary: no inbound reference may still point at the pre-archive path. A historical mention *inside* the archived folder itself is fine.

## Actions

### Where a checkbox may live

A checkbox is a commitment, so the bucket a file sits in decides whether it may hold one.

| Bucket | `actions.md` | State |
|---|---|---|
| `projects/`, `areas/` | yes | open + closed |
| `resources/` | **never** | a checkbox here is a filing error |
| `archive/` | yes | **all closed** - one open `- [ ]` means it was archived too early |

Everything genuinely actionable still has a home: a dated go/no-go is a strategic action in `areas/stadium/actions.md`, linking to the idea; a stakeholder follow-up lives in that person's contact file; scheduled multi-step work means the thing is a workstream, not an idea.

### The actionable frontier

A checkbox is a commitment you could act on now or on its marked date - not a plan. When work decomposes into phases, only the steps whose dependencies have cleared get checkboxes; everything downstream stays prose (a `## Backlog` section in the same file, or the brief) until its gate opens. The failure this prevents is **action inflation**: decompose the whole rollout into checkboxes up front and the speculative items soon outnumber the committed work until nobody believes the count. Two guardrails:

- **The WIP flag.** Before appending an action to a file already holding 12 or more open items, say so and propose grooming instead of silently adding. `/para-daily-brief` flags such files; `/para-deep-clean` grooms them.
- **One next step per inbound item.** Triage and working sessions add at most one next step per thread or document, never a decomposition. A vendor proposal landing in `triage/` yields "decide whether to shortlist", not a nine-step evaluation plan.

### The content frontier

The same rule applied to prose. Files only ever grow: a brief gets one more dated entry, a vendor's pricing gets restated in a second file "for context", a superseded decision is left in place because deleting it feels lossy. Content inflation is action inflation's quieter half - an over-grown action file announces itself with a count, while an over-grown brief just looks thorough.

- **Say it once.** Every fact has one owning file. Vendor pricing lives in the RFP response in `sources/`; the brief links to it rather than restating it. A copy is a second thing to keep true, and once the two disagree nobody can tell which is current.
- **A development log records decisions, not activity.** An entry earns its place by recording what a later reader would otherwise get wrong: a decision and why, a constraint discovered, an option rejected. "Continued vendor evaluation" is not an entry.
- **Superseded content leaves the live buckets** for `archive/` or git history. A shortlist that has been narrowed is history, not current state.

**Never delete to satisfy this.** Pruning is proposed and ruled on one item at a time; the default is *move* or *demote*, and outright deletion applies only to a genuine duplicate whose contents have been compared against the copy that survives. Source documents and anything in `triage/` are never pruned.

### Which file an action goes in

- Co-locate with the workstream or area it belongs to: `projects/<workstream>/actions.md`, `areas/stadium/actions.md`.
- Per-stakeholder actions live inside the contact file (`areas/network/<person>.md`, under `## Next actions`).
- Cross-cutting programme work not tied to one workstream or person goes in `areas/stadium/actions.md`.
- Never create a monolithic root `actions.md`.
- An `actions.md` archives *with its workstream*, fully closed - never on its own, and never carrying an open item.

### Task markers (Obsidian Tasks syntax)

Any `actions.md` file in this vault uses Obsidian Tasks plugin markers. The `/para-daily-brief` skill parses these with regex:

- `📅 YYYY-MM-DD` - due date (hard deadline)
- `🛫 YYYY-MM-DD` - start date (item not actionable until then)
- `⏳ YYYY-MM-DD` - scheduled (planned work date)
- `🔁 every <cadence>` - recurring (pair with `📅` for the next occurrence)
- `🔺 🔼 🔽 ⏬` - priority, highest to lowest. Medium = no marker. Use 🔺 sparingly.
- `✅ YYYY-MM-DD` - completion (auto-filled when ticked)

Rules when writing or editing tasks:

- Put markers at the end of the line: `- [ ] Review vendor scoring matrix 📅 2026-06-10`
- Replace free-text dates with markers (no "before Jun 10 📅 2026-06-10", just the marker)
- Convert fuzzy dates ("Q4", "summer") to concrete dates (usually end-of-quarter or end-of-season)
- A `📅` records a real-world deadline (a stakeholder expects it, a fixture is fixed, a contract renews), never an aspiration. For items gated on external events (a CFO decision, a vendor reply), leave undated.
- One flattened `## Recurring` section per file, not separate "quarterly" / "annually" headings.

## Filing and naming

- **Contacts**: one file per stakeholder at `areas/network/<firstname-lastname>.md` (kebab-case, no diacritics). Relationship context at the top, `## Next actions` appended at the bottom, carrying `_None currently._` when there are none.
- **Dated conversation records** (meeting notes, call transcripts, chat/email sequences): to the `sources/` of the workstream or area that owns them; `archive/meetings/YYYYMMDD Description.md` only when they span several entities.
- **Source documents**: `sources/YYYYMMDD <Who> <Description>.<ext>` - the date of the document itself (signing, issue, inspection), not the received date.
- **Shared workstreams across stakeholders**: track actions in the primary stakeholder's file; the others get a pointer line.
- **Project brief + relationship**: the contact file is the relationship summary; the project folder holds the brief and execution detail. Cross-link both ways.

## Authoritative sources

Name the owning surface *before* answering, not after.

- **Check `triage/` before searching by date.** An item waiting to be filed is usually the current one; a file found by "most recent" may be a stale copy.
- **Prefer source documents over hand-maintained summaries in briefs.** Vendor pricing and scope come from the RFP responses and the signed SOW in `sources/`, not from a comparison table typed into a brief. When they disagree, the source document wins and the brief gets corrected.

| Question | Authoritative source |
|---|---|
| What did we agree with NovaPay? | the signed SOW in `projects/cashless-stadium-rollout/sources/` |
| What does a ticketing vendor offer / charge? | that vendor's RFP response in `projects/ticketing-platform-replacement/sources/` |
| What was decided in a meeting? | the dated record, in the owning workstream's `sources/` or in `archive/meetings/` if it spans several |

## Language

Folders and structural files in English. Stakeholder notes, meeting records, and source documents may be in Dutch, French, or English, matching the source. Don't translate unless asked.

The operator's language is English. Explain, summarize, and answer in English regardless of the source document's language: a Dutch or French document gets explained back in English, not echoed in its own. Quote the original wording only where the exact phrasing is load-bearing (a contract clause, a term of art, a figure).

## Memory

This vault on disk IS the memory. Do not use the agent's built-in memory feature, and do not create a `memory/` folder or session-log files (`/AI/sessions/` and the like). The agent reads the vault fresh each session; the git history is the audit log. Durable facts belong in the file they describe: conventions in this `CLAUDE.md`, scope and stakeholders in `README.md`, and everything else in the relevant project or contact note. If you would otherwise save a memory, write the fact into the vault file it belongs to instead.

## File formats

The substrate is real, readable files. Markdown and plain text first (edited in place, diff cleanly in git), with `.csv`/`.docx`/`.xlsx` as the fallback for material received from others. Avoid cloud-native pointer formats (e.g. Google Docs/Sheets): they sync as stubs, so the bytes aren't local and the agent often can't read them at all. When one lands in the vault, convert it to a real file.

## Integration scripts and their state

A *persistent* tool the agent writes for this vault (a script pulling from a connected system, not a throwaway one-off) is code, so it lives in the vault at `resources/scripts/`. Its runtime state does not: credentials, caches, and bulk data go under `~/.paraos/`, because **a secret written inside the vault leaks the moment the vault syncs to a cloud drive or a git remote**.

`resources/scripts/README.md` carries the rest: the three state buckets, the `PARAOS_HOME` resolver, and the language preference.

## Do not add

- **Cross-client material** - never reference another engagement here; it violates the engagement letter. BelFoot-confidential data (financials, contracts, employee records) stays in this vault, and outputs are reviewed before they leave it.
- **Templates** - don't create per-stakeholder or per-project templates preemptively. Wait until a second instance proves the shape, then document it here.
- **Derived outputs as standalone files** - decks, reports, one-pager text regenerate from `README.md`. Don't let them drift into separate sources of truth.
- **Content rewrites during reorganization** - structure changes preserve copy verbatim. Fix wording in a later, dedicated pass.

## Skills wired to this vault

`/para-daily-brief` (bucketed action dashboard across every `actions.md`), `/para-triage` (empty the inbox by classifying then moving each item), `/para-new` (create a workstream, area, idea or contact, and promote an idea), `/para-deep-clean` (audit structural drift), `/para-archive` (close out one finished project or shelved idea).
