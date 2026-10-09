---
name: para-deep-clean
description: Run a comprehensive cleanup pass on a vault - audits structural/housekeeping issues, normalizes README structure per a canonical template, closes documented open items by reading source PDFs, grooms over-grown action files back to the actionable frontier, and ensures status tables make each entity's state visible at a glance. Use when user asks for a "deep clean", "deep cleanup", "vault review", "vault cleanup", "cleanup pass", "groom my actions", "audit this vault", "check the vault without changing anything", or types /para-deep-clean.
allowed-tools: Bash(python3 *), Bash(py *), Bash(git show *), Bash(git mv *), Bash(git rm *), Bash(mv *), Bash(diff *), Bash(pwd *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content
argument-hint: '[phase1|phase2|phase3|phase4|audit] [--test]'
---

# Deep clean

A multi-phase cleanup workflow for vaults following the PARA plus per-entity `sources/` convention.

**This skill is vault-agnostic.** It reads the vault's `CLAUDE.md` for its parameters, per [Defer to the vault](../para-shared/operating-discipline.md#defer-to-the-vault), including the entity type.

Also invoke after a large content migration, or periodically (every 3-6 months) to catch drift. Do NOT invoke for single-file edits or small tweaks.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Full flow starting from Phase 1 |
| `phase1` | Structural / housekeeping audit only |
| `phase2` | README structure consistency only (assumes Phase 1 done) |
| `phase3` | Open items audit only (assumes Phase 2 done) |
| `phase4` | Final audit only |
| `audit` | Read-only summary: runs Phase 1 plus Phase 4 in observe-only mode. Skips destructive Phases 2 and 3. Never modifies files. |
| `ref=<git-ref>` | The committed para-os ref precondition 5 compares the vault's template marker against, instead of `origin/stable`, such as `origin/main` or a revision branch in flight. Combines with any of the above. A working-tree path is refused. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

A leftover argument follows [para-shared/operating-discipline.md](../para-shared/operating-discipline.md#arguments).

## Preconditions

Confirm before starting:

1. Vault has a `CLAUDE.md` documenting structure, naming conventions, and "do not add" rules. If missing, stop and ask the user to create one.
2. Vault follows PARA layout (at least `areas/` + `projects/` + `archive/`; `triage/` and `resources/` optional but expected).
3. Entities each carry the main document their `CLAUDE.md` prescribes (`brief.md` by default) plus optional `sources/`.
4. **`triage/` must contain no loose files.** The scan's `preconditions.triage_loose` lists them. If any are present, **stop and tell the user to run `/para-triage` first**; `audit`, which writes nothing, lists them as a finding instead. Subdirectories (especially underscore-prefixed handoff batches) are OK to leave, as is a `.gitkeep`. A `triage/README.md` is not: `triage/` never carries one, so flag it for deletion in Phase 1.
5. **The vault should be on the newest *shipped* para-os template revision.** Detection only - never read the master's *content* to act on it, that is `/para-upgrade`'s job.

   The scan's `preconditions.template_marker` compares the vault's `CLAUDE.md` marker with the master's at a committed ref: the `ref=` argument, else `origin/stable`. Then, in order:

   - **Vault behind the shipped marker, or carrying none:** stop and say to run `/para-upgrade` first.
   - **Vault ahead of the shipped marker:** it was aligned to a revision that has not shipped yet. Name the two markers in one line and carry on, auditing against the vault's own `CLAUDE.md`. **Never send this vault to `/para-upgrade`**, which refuses to downgrade.
   - **No clone found** (`verdict: no_clone`, per [para-shared/scripts.md](../para-shared/scripts.md)): skip the check, say no para-os clone was found so the vault's revision could not be verified, and carry on.
   - **A clone the scan reports `ref_missing` on the default ref:** it has no `stable` branch yet. Offer the one-time switch (`git -C <clone> fetch origin`, then `git -C <clone> checkout stable`) and check again; declined, carry on as with no clone.

## Step 0 - Scan

Phase 1, Phase 3 and Phase 4 each open with this call, per [para-shared/scripts.md](../para-shared/scripts.md); it returns preconditions 4 and 5 plus that phase's candidate findings. Phase 2 has no script.

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/clean_scan.py" --vault . --phase <1|3|4> [--today <date the operator named>] [--ref <git-ref>] [--clone <path>] [--templates-dir <dir>]... [--generated-dir <dir>]... [--name-only-column <file>:<column>]... > <scan output path>
```

Each exclusion flag repeats once per entry the vault declares: a folder its `CLAUDE.md` names as holding templates (`--templates-dir`) or a script's output (`--generated-dir`), and a register column its rule file declares a name, not a link (`--name-only-column`).

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

- **Read every README and key source PDF** before proposing changes.
- **Pause for approval between phases**, and within Phase 2 do one worked example before batching the rest.
- **Respect "do not add" rules** in CLAUDE.md. Common ones: no per-entity templates, and no derived outputs that drift from a single source.
- **Match the vault's voice and style.** Read 2-3 nearby READMEs first and copy the structure and tone.
- **Cross-vault separation**: never link from a code repo to a private vault path, and never include other-vault paths in repo-checked content.

## Edge cases

- **Multi-language vault**: match the document's source language for filenames and follow CLAUDE.md's per-section language guidance for prose.

## Notes for Claude sessions

- This skill produces user-visible work on most READMEs in the vault. Make sure the user has time and bandwidth before kicking it off. A typical run takes 1-3 hours of conversation.
- Track progress in the harness's task list where it offers one, else in a short progress message at each phase boundary.

## Related skills

- `/para-archive` - the thorough close-out for a single entity Phase 1 flags as misclassified.
