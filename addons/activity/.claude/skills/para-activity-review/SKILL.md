---
name: para-activity-review
description: Read a vault's activity ledger and report how the vault is actually being used - which skills get invoked and which never, where sessions stall or fail, which parts of the structure nobody touches, and where use contradicts the vault's own rules. Every finding names a change to make. Use when the user asks "how are they using the vault", "is anyone actually using this", "what should I fix about the vault", "review the usage log", "which skills does nobody use", or types /para-activity-review.
allowed-tools: Bash(python3 *), Bash(py *), Bash(git rm *), Bash(pwd *), Bash(gio trash *), Bash(osascript -e 'tell application "Finder" to delete POSIX file *), Glob, Grep, Read, Write, AskUserQuestion
argument-hint: '[<vault-path>] [days] [--test]'
---

# Activity review

Turns the **activity** module's session log into a short list of things to change. It reads that log, checks what it finds against the vault's own stated conventions, and writes a dated report.

## Arguments

`/para-activity-review [<vault-path>] [days]`

- No arguments: the current vault, last 30 days.
- A path: review that vault. This is the cross-vault case - a maintainer reviewing a vault somebody else uses.
- A number: the window in days.
- `--test`: test run, see [para-shared/test-run.md](../para-shared/test-run.md).

## Procedure

### Step 1 - Locate the ledger and frame the window

Resolve the vault and run the scan, per [para-shared/scripts.md](../para-shared/scripts.md):

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/review_scan.py" --vault <vault> [--days N] > <scan output path>
```

Exit 3 is no `resources/logs/sessions/`: the "No ledger installed" edge case. Otherwise report its `frame` first: how many sessions, how many anyone typed into, how many people, over how many days.

### Step 2 - Compute the signals

The scan's `adoption`, `reach`, `friction` and `rhythm` hold the counts. **What each may mean: [references/signals.md](references/signals.md).**

### Step 3 - Check usage against the vault's own rules

Read the reviewed vault's CLAUDE.md, then look for the specific contradictions it makes possible. **Full list: [references/signals.md](references/signals.md).**

### Step 4 - Write the report

One dated Markdown file, findings ranked by what they would change, each tied to a concrete edit to a skill, a template, a convention or the onboarding. Propose its path and write it only after a yes. **Full shape: [references/report.md](references/report.md).**

### Step 5 - Propose pruning, never perform it

Reported lines have done their work. This step deletes, so it is **one question per ledger file**, never one yes over a list, per [para-shared/asking.md](../para-shared/asking.md). Each question names the file, its size and the window it covers, and says what the report took from it. **Recommend the delete only where the report actually consumed the file**; a ledger the run skipped, or one whose window the report describes as blind, keeps `Keep it` as the recommended option. Every question carries `Keep it`.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **The report never goes in a vault that belongs to someone else**: write it where the review was invoked, and ask where that is ambiguous.
- **Findings name defects, never people**, in the report and the reply alike. Per-person counts tell "nobody uses this" from "one person uses this" and never appear as a ranking.
- **Absence is the primary signal.** Enumerate the vault's declared capabilities and folders **first**, then mark which the ledger never touched.
- **Every finding carries the change it implies**; an observation without one is cut.
- **Never infer intent from a prompt.** Quote it, without its author, as evidence of what was asked, never of what someone meant or felt.
- **Say what the ledger cannot see.** It records Claude Code sessions only: a file edited directly, a document read in a browser, and a question someone gave up on before typing are all invisible.
- **A small window is reported as small.** Under 7 days, or under 5 sessions, the output is a first look with its confidence stated, not a set of conclusions.

## Edge cases

- **No ledger installed.** Say so, point at the activity module, and stop: the reply ends there, with no observation about the vault's contents, its triage or any skill. Do not substitute git history: it answers a different question and dressing it up as usage data is worse than an empty report.
- **Ledger present but empty.** Usually the hook never fired rather than nobody working. Check the vault's `.claude/settings.json` for the hook block and the trust step before concluding anything about people.
- **One person, many sessions.** Perfectly reviewable; adoption and friction still hold. Drop the per-person split rather than reporting a table with one row.
- **A git mirror exists.** Use it to answer "what changed" alongside "what was attempted", and keep the two separate in the report. The mirror cannot attribute a change to a person, so never let it look as though it did.
- **Prompts switched off in the ledger config.** Structural signals all still work. Say in the report that the intent half is missing.

## Related skills

- [`/para-deep-clean`](../para-deep-clean/SKILL.md) repairs what this diagnoses inside one vault. This skill changes the tools instead.
- [`/para-daily-brief`](../para-daily-brief/SKILL.md) reports vault state for the person working in it. This reports vault *usage* for the person maintaining it.
