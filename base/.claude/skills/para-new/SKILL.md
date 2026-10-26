---
name: para-new
description: Create one new project, area, idea, or contact in the vault, or a staged entity of a declared lifecycle such as a new deal or property, or promote an idea to a project. Runs the sorting test first (committed work is a project, a maintained responsibility an area, a concept an idea), asks only what each shape needs, then scaffolds and cross-links the files. Use when the user says "start a project", "new project for <x>", "new deal for <x>", "we've committed to <x>", "we're taking this on", "capture this idea", "add <person> as a contact", "this idea is real now", or types /para-new.
allowed-tools: Bash(python3 *), Bash(py *), Bash(pwd *), Glob, Grep, Read, Edit, Write, AskUserQuestion
argument-hint: '[project|area|idea|contact|promote] <name> [--test]'
---

# Para new

Creates **one entity**: a project, an area, an idea or a contact, plus the counterparty's contact file where nothing else would point at a new project or idea ([references/scaffold.md](references/scaffold.md)). It also runs the one promotion the lifecycle defines, `resources/ideas/<name>/` to `projects/<name>/`.

The first job is **classification, not scaffolding**: most requests to "start a project" turn out to be an area, an idea or a document to file. Not for filing an inbound document (`/para-triage`), adding an action to an existing entity (append to its `actions.md`), or the standing `areas/business/` and `areas/network/`.

## The sorting test

*Committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.*

| What the user actually has | Shape |
|---|---|
| Someone is waiting on a named deliverable by a real date | **project** |
| Something live that they maintain, with no end date | **area** |
| A concept with no committed outcome yet | **idea** |
| A person | **contact** |
| A document or note that needs a home | not an entity: hand off to `/para-triage` |

**The deadline separates the first two**: a project needs a goal *and* a real date someone is waiting on. An invented date makes an idea falsely overdue, not a project.

**Put the test to the operator; do not announce its answer.** Where more than one shape is defensible, ask one `AskUserQuestion` per [para-shared/asking.md](../para-shared/asking.md), the candidate shapes as options, each described by its row above, `header` `Shape`, and **a `preview` per shape** of the scaffold it would produce. Where the answer is forced ("add Alex Rivera as a contact"), do not ask; a declared shape the test contradicts is asked, the declared shape second with the reason it fails.

**A lifecycle noun does not replace the test** ([para-shared/lifecycles.md](../para-shared/lifecycles.md)): committed work is created as the lifecycle's promoting stage, not its first.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Ask what the user wants to create, then run the full flow. |
| `<name>` | Full flow: classify, interview, propose, scaffold. |
| `project` / `area` / `idea` / `contact` `<name>` | Same, with the shape declared; **the sorting test still runs** and overrules a wrong one. |
| `<noun> <name>` | The noun of a lifecycle the vault declares (`deal`, `property`): a **staged entity** ([references/scaffold.md](references/scaffold.md)). |
| `promote <name>` | The idea-to-project path. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

### Step 1 - Confirm context and check for a duplicate

1. **Resolve and verify the vault root** per [operating-discipline.md](../para-shared/operating-discipline.md#defer-to-the-vault).
2. **Fuzzy-match the name first**, across `projects/`, `resources/ideas/`, `areas/`, `areas/network/` and `archive/`, and in the same folders of every other vault `${PARAOS_HOME:-~/.paraos}/vaults.json` lists. A near-match is reported, offering to add to it instead: never a second folder for the same work, nor the same entity in a second vault unasked. **An archived match never stops the run**, but it is named, so a successor can take a distinct slug.

### Steps 2 and 3 - Classify, then interview

Settle the shape, then ask only what it needs: three questions for a project, two for an area, an idea or a contact, in prose, not an `AskUserQuestion`, except an answer the request suggests without settling it ([asking.md](../para-shared/asking.md#a-question-with-a-suggested-answer)). **[references/interview.md](references/interview.md).**

### Step 4 - Propose and scaffold

Show the exact files and their content, then write the folder, fill the brief from the vault's declared shape, seed at most one action, and cross-link: **[references/scaffold.md](references/scaffold.md).**

### Promotion

An existing idea is moved, not created: **[references/promote.md](references/promote.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** Specific to this skill:

- **An area absorbs before it multiplies.** Assets that gate each other (a domain, the site on it, the subscription paying for both) are **one** area; widen an existing area before creating a sibling, by its `actions.md` or the `brief.md` it never had.
- **One next action, not a plan.** A new project or area gets a single unblocked next step; what follows it is prose under `## Backlog` in the same file.
- **No `actions.md` where the vault forbids one**: an idea gets a `brief.md` only, and a vault without action tracking gets prose next steps in the brief.
- **Write in the vault's language**: structural filenames and headings follow the vault's convention, the prose its language rule and the operator's own words.
- **A missing `resources/ideas/` or `archive/projects/`** is created only with approval, saying it is new.
