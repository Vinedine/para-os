---
name: para-deep-clean
description: Run a comprehensive cleanup pass on a vault - audits structural/housekeeping issues, normalizes README structure per a canonical template, closes documented open items by reading source PDFs, grooms over-grown action files back to the actionable frontier, and ensures status tables make each entity's state visible at a glance. Use when user asks for a "deep clean", "deep cleanup", "vault review", "vault cleanup", "cleanup pass", "groom my actions", or types /para-deep-clean.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__*__search_threads, mcp__*__get_thread, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content
arg-hint: '[phase1|phase2|phase3|phase4|audit] [--test]'
---

# Deep clean

A multi-phase cleanup workflow for vaults following the PARA plus per-entity `sources/` convention.

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime for the entity type, naming conventions, language rules, "do not add" restrictions, and any iPad-rendering toolchain (`flip.ps1` / `render.ps1`). No vault-specific paths are hardcoded.

Also invoke after a large content migration, or periodically (every 3-6 months) to catch drift. Do NOT invoke for single-file edits or small tweaks: this is a multi-hour pass that touches most READMEs in the vault.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow starting from Phase 1 |
| `phase1` | Structural / housekeeping audit only |
| `phase2` | README structure consistency only (assumes Phase 1 done) |
| `phase3` | Open items audit only (assumes Phase 2 done) |
| `phase4` | Final audit only |
| `audit` | Read-only summary: runs Phase 1 plus Phase 4 in observe-only mode. Skips destructive Phases 2 and 3. Never modifies files. |
| `ref=<git-ref>` | The committed para-os ref precondition 5 compares the vault's template marker against, instead of `origin/main`, such as a revision branch in flight. Combines with any of the above. A working-tree path is refused. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Preconditions

Confirm before starting:

1. Vault has a `CLAUDE.md` documenting structure, naming conventions, and "do not add" rules. If missing, stop and ask the user to create one.
2. Vault follows PARA layout (at least `areas/` + `projects/` + `archive/`; `triage/` and `resources/` optional but expected).
3. Entities each carry the main document their `CLAUDE.md` prescribes (`brief.md` by default) plus optional `sources/`.
4. **`triage/` must contain no loose files.** Use `Glob triage/*` to check, covering [collected copies](../para-shared/operating-discipline.md#the-read-only-ipad-delivery) - if any loose files (not subdirectories) are present, **stop and tell the user to run `/para-triage` first**. Subdirectories (especially underscore-prefixed handoff batches) are OK to leave, as is a `.gitkeep`. A `triage/README.md` is not: `triage/` never carries one, so flag it for deletion in Phase 1 rather than treating it as a loose item to file.
5. **The vault should be on the newest *shipped* para-os template revision.** This skill audits the vault against the rules its own `CLAUDE.md` states, so if that contract is a revision behind, a clean bill of health here only means the vault is faithful to a stale spec. Detection only - never read the master's *content* to act on it, that is `/para-upgrade`'s job.

   Read the first `<!-- para-os-template: YYYY.MM.NN -->` comment in the vault's `CLAUDE.md`, and the master's the way `/para-upgrade` reads it: **`git show <ref>:base/CLAUDE.md.template` at a committed ref - the one the operator named via the `ref=` argument, else `origin/main`** (the delivery's skeleton template for a vault on one). **Never read the clone's working tree:** a revision in flight lives there uncommitted and would report every vault on the machine as behind. The only marker a vault can be aligned to is one that has shipped.

   Then, in order:

   - **Vault behind the shipped marker, or carrying none:** stop and say to run `/para-upgrade` first.
   - **Vault ahead of the shipped marker:** it was aligned to a revision that has not shipped yet, as a test upgrade against an in-flight branch leaves it. Name the two markers in one line and carry on, auditing against the vault's own `CLAUDE.md`. **Never send this vault to `/para-upgrade`**, which refuses to downgrade.
   - **No para-os clone on this machine:** skip the check, say the vault's revision could not be verified, and carry on.

If the vault is on the read-only iPad delivery and **collected**, offer to run [its edit cycle](../para-shared/operating-discipline.md#the-read-only-ipad-delivery) around the phases that write.

## Phased workflow

Each phase ends with a summary and waits for explicit user approval before proceeding to the next. The user can amend, skip, or stop at any phase. **Never auto-advance without approval.**

### Phase 1 - Structural / housekeeping audit

Map the vault, scan for housekeeping issues (stale drafts, naming violations, dangling links and the link syntaxes the dangling check can't see, archive-vs-active misclassification, duplicates), audit archive-folder hygiene, then present one issues table and apply in priority order. **Full procedure: [references/phase1-structural.md](references/phase1-structural.md).**

### Phase 2 - README structure consistency

The root README's fixed four-heading shape first, then the vault's own canonical structure for entity READMEs, applied one worked example at a time. **Full procedure: [references/phase2-readmes.md](references/phase2-readmes.md).**

### Phase 3 - Open items, action grooming, content grooming

Close documented open items by reading the source PDFs, surface time-sensitive ones, groom over-grown action files back to the actionable frontier, and prune prose against the content frontier. This is where most of the destructive work is. **Full procedure: [references/phase3-open-items.md](references/phase3-open-items.md).**

### Phase 4 - Final audit

Read-only verification, ending on an actual `/para-daily-brief` run against the cleaned vault. **Full checklist: [references/phase4-audit.md](references/phase4-audit.md).**

## Output

Final summary report covering:

- **What was fixed** (categorical list per phase)
- **Status snapshot** across all entities (one row each, key numbers visible)
- **Remaining open items** by entity (active only)
- **Suggestions for next-pass work** (domain-specific templates, contact-file consistency, and so on)

## Approvals

Findings are presented two ways, and which one a finding gets is decided by whether approving it can lose something. **Lossless changes batch** onto the issues table each phase already builds: demotions, link repoints, renames, README normalisation. **Anything that closes, removes, strips a marker or deletes is one question per item** through `AskUserQuestion`. Mechanics, the manifest threshold and the 20-item gate: [para-shared/asking.md](../para-shared/asking.md).

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Never close, strip or delete on a batch approval.** The issues table is for changes that lose nothing; everything else is asked one at a time.

- **Read every README and key source PDF** before proposing changes. Assumptions waste user time.
- **Pause for approval between phases**, and within Phase 2 do one worked example before batching the rest.
- **Respect "do not add" rules** in CLAUDE.md. Common ones: no per-entity templates, no `actions.md`, no derived outputs that drift from a single source.
- **Match the vault's voice and style.** Read 2-3 nearby READMEs first and copy the structure and tone.
- **Cross-vault separation**: never link from a code repo to a private vault path, and never include other-vault paths in repo-checked content. Code repos push to shared remotes; vault paths leak personal context.

## Edge cases

- **Vault has no CLAUDE.md**: stop and ask the user to draft one. Don't proceed without conventions documented.
- **Multi-language vault**: match the document's source language for filenames and follow CLAUDE.md's per-section language guidance for prose.

Phase-specific edge cases live with their phase.

## Notes for Claude sessions

- This skill produces user-visible work on most READMEs in the vault. Make sure the user has time and bandwidth before kicking it off. A typical run takes 1-3 hours of conversation.
- Track progress in the harness's task list - there are many discrete items per phase and progress visibility matters.
- When extracting data from PDFs, prefer Python plus pypdf over Bash text grepping. PDF text layout is unreliable from grep.
- Resist the urge to rewrite content for clarity. The user knows their domain; your job is structural consistency and closing gaps, not editorial improvement.

## Related skills

- `/para-archive` - the thorough close-out for a single entity Phase 1 flags as misclassified. Preconditions 4 and 5 name the two skills that run before this one.
