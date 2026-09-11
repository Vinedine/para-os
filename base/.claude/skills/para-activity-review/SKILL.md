---
name: para-activity-review
description: Read a vault's activity ledger and report how the vault is actually being used - which skills get invoked and which never, where sessions stall or fail, which parts of the structure nobody touches, and where use contradicts the vault's own rules. Every finding names a change to make. Use when the user asks "how are they using the vault", "is anyone actually using this", "what should I fix about the vault", "review the usage log", "which skills does nobody use", or types /para-activity-review.
allowed-tools: Bash, Glob, Grep, Read, Write, AskUserQuestion
arg-hint: '[<vault-path>] [days]'
---

# Activity review

Turns the **activity** integration's session log into a short list of things to change. It reads that log, checks what it finds against the vault's own stated conventions, and writes a dated report.

The question is **never "what did these people do"**. It is "which parts of this vault work, which are ignored, and which fight the person using them". A finding that names a person rather than a defect is a finding written wrong, and the report is worthless the day anyone reads it as a performance review.

**This skill is vault-agnostic.** It reads the reviewed vault's CLAUDE.md at runtime for the PARA layout, the action rules, the filing conventions and the declared skills, and judges usage against *those* rules rather than any built in here.

Requires the activity integration installed in the vault being reviewed. Without it there is no input, and the honest answer is to say so and stop.

## What it answers

| Question | Reads | The finding it produces |
|---|---|---|
| **Adoption** - what gets used | Skill invocations per person | The capabilities invoked zero times. Usually the most valuable line in the report |
| **Reach** - what gets touched | Tool targets by PARA bucket | The folders nobody opens, and the ones that only ever get written by one person |
| **Friction** - where it fights back | Failures, denials, prompts per session, rephrasings | The specific step where people stall, with the prompt that preceded it |
| **Contradiction** - use against the rules | Ledger plus the vault's own CLAUDE.md | A convention people work around, which is either a rule to fix or a rule to teach |

## Arguments

`/para-activity-review [<vault-path>] [days]`

- No arguments: the current vault, last 30 days.
- A path: review that vault. This is the cross-vault case - a maintainer reviewing a vault somebody else uses.
- A number: the window in days. Fewer than 7 days of ledger is a first look, not a review, and the report says so.

## Procedure

### Step 1 - Locate the ledger and frame the window

Resolve the vault, confirm `resources/logs/sessions/` exists, and count what is there before reading any of it: how many sessions, how many distinct people, over how many days. Report the frame first. A review of four sessions and a review of four hundred are different documents, and stating the frame stops the second being written from the first.

### Step 2 - Compute the signals

Parse the JSONL with a script rather than by reading lines, and never let a single malformed line stop the run. **Full procedure, including every signal and what it means: [references/signals.md](references/signals.md).**

### Step 3 - Check usage against the vault's own rules

Read the reviewed vault's CLAUDE.md, then look for the specific contradictions it makes possible: a checkbox where that vault forbids one, `triage/` growing while its triage skill is never invoked, entities created without the files the conventions require, actions minted against the vault's own dating rule. **Full list: [references/signals.md](references/signals.md).**

### Step 4 - Write the report

One dated Markdown file, findings ranked by what they would change, each tied to a concrete edit to a skill, a template, a convention or the onboarding. **Full shape: [references/report.md](references/report.md).**

### Step 5 - Propose pruning, never perform it

Reported lines have done their work, and a log that grows forever becomes the clutter this skill exists to find. But this step deletes, and the vault's own rule is that pruning is *"proposed and ruled on, one item at a time"* - so it is **one question per ledger file**, never one yes over a list, per [para-shared/asking.md](../para-shared/asking.md). Each question names the file, its size and the window it covers, and says what the report took from it. **Recommend the delete only where the report actually consumed the file**; a ledger the run skipped, or one whose window the report describes as blind, keeps `Keep it` as the recommended option, because a file nothing read is not a file that has done its work. Every question carries `Keep it`, so declining costs nothing.

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **The report never goes in the reviewed vault when that vault belongs to someone else.** It is a critique of how their tools failed them, written for whoever maintains those tools. Write it where the review was invoked, and if that is ambiguous, ask.
- **Never delete a ledger file on a batch approval.** One question each, and the delete is recommended only for a file the report demonstrably read. This skill's whole output is an argument that silent, confident wrongness is the failure mode to fear; deleting the evidence on a shrug would be it.
- **Findings name defects, never people.** Per-person counts exist to distinguish "nobody uses this" from "one person uses this", which are different problems with different fixes. They are a means, and they do not go in the report as a ranking.
- **Absence is the primary signal, so look for it deliberately.** A log shows what happened; the valuable finding is usually what never did. Enumerate the vault's declared capabilities and folders **first**, then mark which the ledger never touched. A report assembled only from what appears in the log will systematically miss the biggest problem.
- **Every finding carries the change it implies.** "People rarely run triage" is an observation. "Triage is never invoked and `triage/` holds 40 files, so the walkthrough should open with it rather than mention it at step 9" is a finding. Observations without a proposed change get cut.
- **Never infer intent from a prompt.** Prompts record what someone asked, not what they meant or how they felt. Quote them as evidence of what the vault was asked to do; do not diagnose confusion, frustration or skill from wording.
- **Say what the ledger cannot see.** It records Claude Code sessions only: a file edited directly, a document read in a browser, and a question someone gave up on before typing are all invisible. A report that does not state its blind spots reads as complete.
- **A small window is reported as small.** Under 7 days, or under 5 sessions, the output is a first look with its confidence stated, not a set of conclusions.

## Edge cases

- **No ledger installed.** Say so, point at the integration, and stop. Do not substitute git history: it answers a different question and dressing it up as usage data is worse than an empty report.
- **Ledger present but empty.** Usually the hook never fired rather than nobody working. Check the vault's `.claude/settings.json` for the hook block and the trust step before concluding anything about people.
- **One person, many sessions.** Perfectly reviewable; adoption and friction still hold. Drop the per-person split rather than reporting a table with one row.
- **A git mirror exists.** Use it to answer "what changed" alongside "what was attempted", and keep the two separate in the report. The mirror cannot attribute a change to a person, so never let it look as though it did.
- **Prompts switched off in the ledger config.** Structural signals all still work. Say in the report that the intent half is missing.

## Related skills

- [`/para-deep-clean`](../para-deep-clean/SKILL.md) repairs what this diagnoses inside one vault. This skill changes the tools instead.
- [`/para-daily-brief`](../para-daily-brief/SKILL.md) reports vault state for the person working in it. This reports vault *usage* for the person maintaining it.
