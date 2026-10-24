---
name: para-new
description: Create one new project, area, idea, or contact in the vault, or a staged entity of a declared lifecycle such as a new deal or property, or promote an idea to a project. Runs the sorting test first (committed work is a project, a maintained responsibility an area, a concept an idea), asks only what each shape needs, then scaffolds and cross-links the files. Use when the user says "start a project", "new project for <x>", "new deal for <x>", "we've committed to <x>", "we're taking this on", "capture this idea", "add <person> as a contact", "this idea is real now", or types /para-new.
allowed-tools: Bash(python3 *), Bash(py *), Bash(pwd *), Glob, Grep, Read, Edit, Write, AskUserQuestion
argument-hint: '[project|area|idea|contact|promote] <name> [--test]'
---

# Para new

Creates **one entity**: a project, an area, an idea, or a contact. Nothing else, with a single exception - a project or idea that would otherwise have nothing pointing at it also gets its counterparty's contact file ([references/scaffold.md](references/scaffold.md)). It also runs the one promotion the lifecycle defines, `resources/ideas/<name>/` to `projects/<name>/`.

The first job is **classification, not scaffolding.** Most requests to "start a project" turn out to be an area, an idea, or a document that needs filing. The sorting test runs before any question about the work itself.

Do NOT invoke to file an inbound document (`/para-triage` does that), to add an action to an entity that already exists (append to its `actions.md` directly), or to create the skeleton's standing subfolders: `areas/business/` and `areas/network/` ship with the vault and are not areas anyone creates.

## The sorting test

This skill's contract, and the vault's own rule: *committed and dated → project. Maintained, no end date → area. Only thinking about it → idea. Over → archive.*

| What the user actually has | Shape |
|---|---|
| Someone is waiting on a named deliverable by a real date | **project** |
| Something live that they maintain, with no end date | **area** |
| A concept with no committed outcome yet | **idea** |
| A person | **contact** |
| A document or note that needs a home | not an entity: hand off to `/para-triage` |

**The deadline separates the first two.** A project needs a clear goal *and* a real-world date someone is actually waiting on; work that simply continues is an area. An invented date does not make an idea into a project, it makes a deliberation that will surface as falsely overdue.

**Put the test to the operator; do not announce its answer.** Where more than one shape is defensible - which is every project / area / idea call, and the great majority of runs - ask it as a single `AskUserQuestion` with the candidate shapes as options and the row of the table above as each option's description, per [para-shared/asking.md](../para-shared/asking.md). Its `header` is `Shape`, not a batch position. **Give each shape a `preview`** showing the scaffold it would produce - a project's `brief.md` plus `actions.md` with one next step, an idea's `brief.md` alone.

Ask only where the answer is not forced. "Add Alex Rivera as a contact" is a person and asking is noise; a declared shape that the test contradicts is exactly when to ask, with the declared shape offered second and the reason it fails in its description.

**A lifecycle noun does not replace the test.** Where the vault declares a lifecycle ([para-shared/lifecycles.md](../para-shared/lifecycles.md)), the test still decides whether this is that kind of entity at all, and a request that turns out to be committed work is created as the lifecycle's promoting stage rather than its first.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Ask what the user wants to create, then run the full flow. |
| `<name>` | Full flow: classify, interview, propose, scaffold. |
| `project` / `area` / `idea` / `contact` `<name>` | Same, with the shape declared. **The sorting test still runs** and still overrules a declared shape that is wrong. |
| `<noun> <name>` | The noun of a lifecycle the vault declares (`deal`, `property`): create a **staged entity** at that lifecycle's first non-row stage, with its Stage line and header. **[references/scaffold.md](references/scaffold.md).** |
| `promote <name>` | The idea-to-project path. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

Nothing is written before the proposal is approved, so there is no preview argument: every run is a preview until you say yes.

## Procedure

### Step 1 - Confirm context and check for a duplicate

1. **Resolve and verify the vault root** per [operating-discipline.md](../para-shared/operating-discipline.md#defer-to-the-vault).
2. **Fuzzy-match the name before anything else**, across `projects/`, `resources/ideas/`, `areas/`, `areas/network/`, and `archive/`. Report a near-match and confirm it is genuinely a different thing, offering to add to it instead: never a second folder for the same work. **An archived match never stops the run** - reusing a finished entity's name is allowed - but it is named, so the operator can choose a distinct slug if this is a successor rather than a repeat. **Where `${PARAOS_HOME:-~/.paraos}/vaults.json` lists other vaults, match their same folders too** and name a hit, with its vault, before scaffolding: the same entity in two vaults is the operator's call, never silently created.

### Steps 2 and 3 - Classify, then interview

Settle the shape against the sorting test above, then ask only what that shape needs: three questions for a project, two for an area, an idea, or a contact. **The interview is not an `AskUserQuestion`**: a name, a deadline and a goal are free text, asked in prose. The one exception is an answer the request already suggests without settling it, which [para-shared/asking.md](../para-shared/asking.md) (`## A question with a suggested answer`) puts to the operator as a recommended option. **Full procedure: [references/interview.md](references/interview.md).**

### Step 4 - Propose and scaffold

Show the exact files and their content, then write the folder, fill the brief from the vault's declared shape, seed at most one action, and cross-link. **Full procedure: [references/scaffold.md](references/scaffold.md).**

### Promotion

When the entity already exists as an idea, this is a move rather than a creation. **Full procedure: [references/promote.md](references/promote.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **An area absorbs before it multiplies.** Assets that gate each other are **one** area, not several: a domain, the site on it and the subscription paying for both belong together, because split apart the dependency between them stops being visible anywhere. Check whether an existing area should widen before creating a sibling.
- **One next action, not a plan.** A new project or area gets a single unblocked next step. Work that follows it is prose under `## Backlog` in the same file, promoted to a checkbox when its gate opens. Decomposing something new into a checklist is the action inflation the actionable-frontier rule exists to stop.
- **Never create an `actions.md` where the vault forbids one.** An idea gets a `brief.md` only, because `resources/` never holds a checkbox. A vault whose conventions drop action tracking gets prose next steps in the brief instead.
- **Write in the vault's language.** Structural filenames and headings follow the vault's convention (usually English, since the other skills parse them); the prose follows the vault's language rule and the operator's own words.

## Edge cases

- **It belongs inside an existing area.** Propose widening it rather than creating a sibling: adding the scope to its `actions.md`, or writing the `brief.md` it never had, whichever its shape calls for.
- **The vault has no `resources/ideas/` or `archive/projects/`**: create the bucket only with approval, saying it is new.
