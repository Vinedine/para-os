---
name: para-deep-clean
description: Run a comprehensive cleanup pass on a vault - audits structural/housekeeping issues, normalizes README structure per a canonical template, closes documented open items by reading source PDFs, and ensures status tables make each entity's state visible at a glance. Use when user asks for a "deep clean", "deep cleanup", "vault review", "vault cleanup", "cleanup pass", or types /para-deep-clean.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write
arg-hint: '[phase1|phase2|phase3|phase4|audit]'
---

# Deep clean

A multi-phase cleanup workflow for vaults following the PARA + per-entity `sources/` convention (areas / projects / resources / archive / triage, with each entity having its own README.md + optional sources/ folder).

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime to discover the entity type (properties, clients, applications, etc.), naming conventions, language rules, "do not add" restrictions, and any iPad-rendering toolchain (`flip.ps1` / `render.ps1`). No vault-specific paths are hardcoded.

## When to invoke

- User types `/para-deep-clean` (optionally with a phase argument to skip to that phase)
- User asks for a "deep clean", "deep cleanup", "vault review", "cleanup pass", "review the repo", "clean up the vault"
- After a large content migration that left the vault inconsistent
- Periodically (every 3-6 months) to catch drift

Do NOT invoke for single-file edits or small tweaks. This is a multi-hour, multi-phase pass that touches most READMEs in the vault.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow starting from Phase 1 |
| `phase1` | Structural / housekeeping audit only |
| `phase2` | README structure consistency only (assumes Phase 1 done) |
| `phase3` | Open items audit only (assumes Phase 2 done) |
| `phase4` | Final audit only |
| `audit` | Read-only summary: runs Phase 1 (structural audit) + Phase 4 (final-audit checks) in observe-only mode. Skips destructive Phases 2-3. Never modifies files. |

## Preconditions

Confirm before starting:

1. Vault has a `CLAUDE.md` documenting structure, naming conventions, and "do not add" rules. If missing, stop and ask the user to create one (or use a similar vault's CLAUDE.md as a template).
2. Vault follows PARA layout (at least `areas/` + `projects/` + `archive/`; `triage/` and `resources/` optional but expected).
3. Entities (properties, projects, clients, etc.) each have a `README.md` + optional `sources/` folder.
4. **`triage/` must contain no loose files.** Use `Glob triage/*` to check - if any loose files (not subdirectories) are present, **stop and tell the user to run `/para-triage` first**. Subdirectories in `triage/` (especially underscore-prefixed handoff batches) are OK to leave. Rationale: deep-clean operates on routed-and-named state. Loose triage files are uncategorized data that haven't been routed to their entity `sources/` folders; running deep-clean over them would either miss them entirely or propose changes against a moving target.

If the vault uses the flip.ps1 collected/spread workflow (the para-os read-only flavor):
- If currently in **collected** state, ask the user to run `flip.ps1 spread` first so READMEs are editable in their natural locations.
- After all phases complete, remind the user to `flip.ps1 collect` (and to `render.ps1` first if PDFs need refreshing).

## Phased workflow

Each phase ends with a summary and waits for explicit user approval before proceeding to the next. The user can amend, skip, or stop at any phase. Never auto-advance without approval.

### Phase 1 - Structural / housekeeping audit

Goal: identify and fix obvious structural issues before deeper work.

**Step 1.1 - Map the vault.** Run a lightweight inventory:
- Top-level folders present (PARA compliance check)
- Entity count per area (number of properties / projects / clients)
- Empty PARA leaf directories (`resources/ideas/`, `resources/prompts/` often end up empty)
- Root `README.md` presence and completeness (look for `_To be filled in_` placeholders)

(Triage emptiness is already enforced by Precondition 4 - no need to re-check here.)

**Step 1.2 - Scan for housekeeping issues.** Look for:

- **Stale draft files**: `.doc` / `.docx` drafts alongside signed `.pdf` finals. Often safe to delete the draft if the signed PDF supersedes. Per the vault's CLAUDE.md, some drafts are kept intentionally as searchable text - check the README's source-document description before proposing deletion.
- **Naming convention violations**: filenames not matching the convention in CLAUDE.md (legacy suffixes like ` - FINAL`, typos, wrong dates, wrong language).
- **Cross-reference link style**: links should match the vault's mode. If vault uses collected/spread with `.pdf` siblings, links inside READMEs should target `.md` (so they work in both modes for the maintainer + collaborators).
- **Archive vs active misclassification**: entities whose README marks them as no longer active (terminology varies by vault - sold, closed, completed, rejected, terminated, superseded) but that still live in `areas/` or `projects/` should be moved to `archive/`.
- **Duplicate documents**: same content under different filenames (often from migration passes).

**Step 1.2b - Archive-folder hygiene.** Audit `archive/` against the vault's **Archive hygiene** conventions in CLAUDE.md (no live work in the archive, history-archives-but-living-references-go-to-resources, no loose files at the archive root, minimum record per archived entity). Concretely, scan for:

- **Loose files at the archive root** - anything not in a documented subfolder (`meetings/`, `projects/`, ...). Propose moving to the right subfolder, or deleting (individual approval) if thin and fully superseded.
- **Dated-naming violations in `archive/meetings/`** - files not matching the vault's dated pattern. Flag.
- **Archived entities missing their minimum record** - no `brief.md`/`README.md` or status marker. Flag.
- **Typos / wrong names in already-archived filenames** - the naming scan applies to archived files too; a misspelled name or wrong date defeats search. Propose a rename (preserve source language).

Approval discipline for all archive fixes follows [shared/operating-discipline.md](../shared/operating-discipline.md).

**Step 1.3 - Present issues table.** Build a single table:

| # | Issue | Where | Proposed fix |
|---|---|---|---|

Show this **before** applying anything. Wait for explicit user approval on the table. **Batch approval is allowed only for non-destructive normalisations** (naming-convention fixes, link-style normalisations, casing fixes). **Deletions, moves between PARA buckets, and any destructive operation require individual approval** - no batching, no exceptions.

**Step 1.4 - Apply fixes** in priority order:
- Non-destructive first (link style, naming consistency)
- Destructive last (file deletions, batched with explicit list)

Never delete a file without an explicit row in the approved table.

### Phase 2 - README structure consistency

Goal: every entity README follows a documented canonical structure for the vault.

**Step 2.1 - Check for canonical structure documentation.** Read `CLAUDE.md`. Does it specify a canonical README section order for the vault's main entity type (properties / projects / clients / etc.)? If not, draft one based on what the existing READMEs already share, and add a `### <Entity> README structure` subsection to CLAUDE.md.

The canonical structure should:
- List sections in a fixed order
- Specify that sections that don't apply get explicit `_n/a_` lines (not omission), so gaps stay visible
- Include domain-specific sections needed for the vault's purpose

**This skill does not bring a default section list.** The canonical structure for active entities and archived entities must come from each vault's CLAUDE.md - they are vault-specific. If you find yourself reaching for "what a good README looks like", that's a signal to read the vault's CLAUDE.md, not to invent or import a template.

**Step 2.2 - Archived / dead entities.** Check CLAUDE.md for a documented archived-entity template (often shorter than the active-entity one). If none is documented, **ask the user** what shape archived entries should take - do not apply a default. The travelling principle to surface in the conversation: archived entities don't need open-items or active-relationship sections, but should carry enough context (status marker, why they're archived, where source docs live) to be self-explanatory years later.

**Step 2.3 - Apply.** For each entity README:
- Do the **first one as a worked example** and pause for user approval before batching the rest
- Preserve all existing facts verbatim - only reorganize and add missing sections
- Promote inline bolded blocks (Ownership, Notary) to `##` sections for consistency
- Add `_n/a_` placeholders for sections that genuinely don't apply

### Phase 3 - Open items audit

Goal: every "Open items" section reflects real outstanding work, not historical record-keeping gaps.

**Phase 3 precondition:** verify Python + pypdf are installed before proceeding - `py -c "import pypdf"`. If the import fails: install with `pip install pypdf`, OR skip Step 3.1's PDF-based closure and proceed directly to Steps 3.2 and 3.3 (which don't need pypdf). Don't fail mid-flight on a missing dependency.

For each entity's Open items section:

**Step 3.1 - Read source PDFs to close items.** Many "missing data" open items are actually answerable by reading the source documents already on file. Use Python + pypdf to extract text from PDFs:

```bash
py -X utf8 -c "from pypdf import PdfReader; r = PdfReader(r'<path>'); print(r.pages[0].extract_text())"
```

Common items closable this way:
- "Purchase price not on file" → read the purchase contract PDF
- "Fees not itemised" → read the settlement statement or invoice
- "Date X unknown" → check PDF metadata or first page

Update the README with the closed facts; remove the item from Open items.

**Step 3.2 - Archived entities: aggressive close.** For sold/closed/archived entities, historical record-keeping gaps don't affect current operations. Soften Open items to `_None - <entity> fully closed; minor historical gaps acknowledged but not material._` or empty entirely.

For active entities: keep open items that represent real work to do; only remove ones that are actually resolved.

**Step 3.3 - Surface time-sensitive items.** Look for:
- Payments due in the next 30 days
- Indexation anniversaries
- Insurance renewals
- Inspection deadlines (boiler, electrical, asbestos)

Move these to the top of the Open items list with clear deadline labels.

### Phase 4 - Final audit

Read-only verification pass:

- All archived entities have zero open items (or explicit "fully closed" notes)
- All active entities have Open items reflecting real outstanding work only
- All READMEs follow canonical structure
- CLAUDE.md documents the canonical structures used
- Triage folder is empty
- No empty PARA leaf directories
- Archive folder is clean: no loose files at the archive root, `archive/meetings/` files follow the dated-naming convention, archived entities carry their minimum record (brief/README)
- Root README is complete (no `_To be filled in_` placeholders)
- Status tables ("where do we stand" per entity: cost basis, stage, key numbers) present and current, where the vault uses them

Report a clean state summary or list residual issues with proposed fixes.

**Flip workflow reminder:** if the vault uses the flip workflow and was spread for this cleanup, tell the user to run `render.ps1` (if any READMEs changed) then `flip.ps1 collect` to return the vault to its default state.

## Output

Final summary report covering:

- **What was fixed** (categorical list per phase)
- **Status snapshot** across all entities (one row each, key numbers visible)
- **Remaining open items** by entity (active only)
- **Suggestions for next-pass work** (e.g. domain-specific templates, contact-file consistency, etc.)

## Strict rules

- **Always preserve existing facts verbatim** during reorganization. Never lose information when restructuring a README; only reorganize and add missing sections.
- **Read every README and key source PDF** before proposing changes. Assumptions waste user time.
- **Pause for approval between phases**, and within Phase 2 do one worked example before batching the rest.
- **Vault conventions vary**: always read `CLAUDE.md` first for the specific vault's rules (naming, language, what to skip, "do not add" list).
- **Never delete a file without an explicit row in an approved deletion list.**
- **Never modify file content** beyond rotation of scanned images. Don't re-OCR, don't strip metadata, don't re-compress.
- **Never translate document names.** If the source convention is in Dutch/French and the file is Dutch/French, the rename stays in the source language.
- **Respect "do not add" rules** in CLAUDE.md. Common ones: no per-entity templates, no `actions.md`, no derived outputs that drift from a single source.
- **Match the vault's voice and style.** Read 2-3 nearby READMEs first and copy the structure / tone.
- **Cross-vault separation**: never link from a code repo to a private vault path, and never include other-vault paths in repo-checked content. Code repos push to shared remotes; vault paths leak personal context.

## Edge cases

- **Vault has no CLAUDE.md**: stop and ask the user to draft one (or copy from a similar vault). Don't proceed without conventions documented.
- **Vault is in collected state** (per flip.ps1 workflow): ask user to spread first. Editing .md files inside `resources/mds/` works but is error-prone - natural-location editing is safer.
- **Entity README references files not in sources/**: flag in Phase 1 as a content-vs-filesystem mismatch. Either find the file (often still in triage or another mailbox) or update the README to mark it missing.
- **Source PDF is scan-only with no text layer**: note the limitation; ask user to open the PDF directly and report the key value.
- **Open items list grows indefinitely** with low-priority items: in Phase 4, propose grouping into "Active" (real work) vs "Residual flags" (historical gaps, low priority). Keep both but make the priority hierarchy visible.
- **Multi-language vault** (e.g. mixed Dutch + English + French): match the document's source language for filenames and follow CLAUDE.md's per-section language guidance for prose.
- **Status / cost-basis table makes no sense for the entity type**: substitute a domain-appropriate "status at a glance" table. For jobs: Salary band + Stage + Last contact. For contacts: Role + Last interaction + Open asks. The principle is "one table near the top that answers 'where do we stand' in one look".

## Notes for Claude sessions

- This skill produces user-visible work on most READMEs in the vault. Make sure the user has time and bandwidth before kicking it off. A typical run takes 1-3 hours of conversation.
- Use TodoWrite for tracking - there are many discrete items per phase and progress visibility matters.
- When extracting data from PDFs, prefer Python + pypdf over Bash text grepping. PDF text layout is unreliable from grep.
- Resist the urge to rewrite content for clarity. The user knows their domain; your job is structural consistency + closing gaps, not editorial improvement.

## Related skills

Part of the para-os skill set. Sibling skills:

- `/para-triage` - empty the `triage/` folder and route loose files to their entity `sources/`. **Always run before** `/para-deep-clean` if triage has loose files (enforced by Precondition 4).
