---
name: para-deep-clean
description: Run a comprehensive cleanup pass on a vault - audits structural/housekeeping issues, normalizes README structure per a canonical template, closes documented open items by reading source PDFs, grooms over-grown action files back to the actionable frontier, and ensures status tables make each entity's state visible at a glance. Use when user asks for a "deep clean", "deep cleanup", "vault review", "vault cleanup", "cleanup pass", "groom my actions", "audit this vault", "check the vault without changing anything", or types /para-deep-clean.
allowed-tools: Bash(python3 *), Bash(py *), Bash(git show *), Bash(git mv *), Bash(git rm *), Bash(mv *), Bash(diff *), Bash(pwd *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Edit, Write, AskUserQuestion, ToolSearch, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content
argument-hint: '[phase1|phase2|phase3|phase4|audit] [--test]'
---

# Deep clean

A phased cleanup of a PARA vault with per-entity `sources/`, against the vault's own `CLAUDE.md`.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Every phase, from Phase 1 |
| `phase1`, `phase2`, `phase3`, `phase4` | That phase only |
| `audit` | Phase 1 and Phase 4, observe only: writes nothing |
| `ref=<git-ref>` | The committed para-os ref precondition 5 compares against instead of `origin/stable`, with any of the above. A working-tree path is refused. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Preconditions

1. The vault has a `CLAUDE.md` documenting its structure, naming and "do not add" rules. Missing: stop and ask for one.
2. It follows the PARA layout: at least `areas/`, `projects/` and `archive/`.
3. Each entity carries the main document its `CLAUDE.md` prescribes (`brief.md` by default).
4. **`triage/` holds no loose files** (`preconditions.triage_loose`). Any: stop and say to run `/para-triage` first; `audit` lists them as a finding instead. A `triage_readme` is flagged for deletion in Phase 1.
5. **The vault is on the newest shipped template revision**, per `preconditions.template_marker` at the `ref=` argument, else `origin/stable`. Detection only: acting on the master's content is `/para-upgrade`'s job.
   - **`behind`, or no vault marker:** stop and say to run `/para-upgrade` first.
   - **`ahead`:** name both markers in one line and carry on against the vault's own `CLAUDE.md`. Never send it to `/para-upgrade`.
   - **`no_clone`:** say the revision could not be verified, and carry on.
   - **`ref_missing` on the default ref** (a clone with no `stable` branch): ask the operator to switch the clone to `stable`, and check again; not done, carry on as with no clone.

## Step 0 - Scan

Phases 1, 3 and 4 each open with the scan, per [para-shared/scripts.md](../para-shared/scripts.md): preconditions 4 and 5 plus that phase's candidates. Phase 2 has none.

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/clean_scan.py" --vault . --phase <1|3|4> [--today <date the operator named>] [--ref <git-ref>] [--clone <path>] [--templates-dir <dir>]... [--generated-dir <dir>]... [--name-only-column <file>:<column>]... [--dated-pattern <regex>] [--next-steps-heading <heading>]... > <scan output path>
```

Pass a flag for each value the vault declares: a folder holding templates or a script's output, a register column of names rather than links, a dated-name pattern for `archive/meetings/` other than an eight-digit prefix, next-steps headings other than `Next steps` and `Open items`.

## Phases

Each phase ends with a summary and waits for approval; the operator can amend, skip or stop. **Never auto-advance.**

### Phase 1 - Structural audit

Housekeeping findings into one issues table, lossless fixes first: [references/phase1-structural.md](references/phase1-structural.md).

### Phase 2 - README structure

The root README's four headings, then entity READMEs against the vault's declared shape, one worked example first: [references/phase2-readmes.md](references/phase2-readmes.md).

### Phase 3 - Open items and grooming

Close items from documents on file, surface what is time-sensitive, groom action files to the actionable frontier and prose to the content frontier: [references/phase3-open-items.md](references/phase3-open-items.md).

### Phase 4 - Final audit

Read-only, and the second half of `audit`. A scan row with `pass: false` is a residual issue unless Phase 1's exclusions or an operator decision this run, recorded in the summary, accounts for it. A `pass: None` row is a count whose verdict is the agent's, `over_threshold_files` included where no file over is an `actions.md` (each may declare its own contract, Step 3.4). Then check by reading what no row covers:

- The root README passes the Step 1.1 shape check, every README follows the structure `CLAUDE.md` documents, and active entities' Open items hold only real work.
- Every contradiction between live files is corrected in the copies or carried as an open item on the owning entity.
- Status tables ("where do we stand": cost basis, stage, key numbers) are present and current, where the vault uses them.
- Content grooming was proposed and ruled on, each removal approved with its text shown, and the summary names the briefs Step 3.5 read and skipped.
- **`/para-daily-brief` runs** against the cleaned vault, terminal only, and its counts look right. Never simulate it with a grep.

Report a clean state, or the residual issues with proposed fixes.

## Output

A final summary: what was fixed, by phase; a status snapshot, one row per entity with its key numbers; the remaining open items of each active entity; suggestions for a next pass.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **Lossless changes batch** on the issues table: demotions, link repoints, renames, README normalisation. **Anything that closes, removes, strips a marker or deletes is one question per item**, per [para-shared/asking.md](../para-shared/asking.md), never a batch approval.
- **Read every README, and the source document a proposal rests on**, before proposing.
- **Respect the vault's "do not add" rules**: no per-entity templates, no derived outputs that drift from their source.
