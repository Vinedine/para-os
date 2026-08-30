---
name: para-new
description: Create one new project, area, idea, or contact in the vault, or promote an existing idea to a project. Runs the sorting test first so committed work becomes a project, a maintained responsibility becomes an area, and a concept stays an idea, asks only the few questions each shape needs, then scaffolds the files and cross-links them. Use when the user says "start a project", "new project for <x>", "we've committed to <x>", "we're taking this on", "capture this idea", "add <person> as a contact", "this idea is real now", or types /para-new.
allowed-tools: Bash, PowerShell, Glob, Grep, Read, Edit, Write
arg-hint: '[project|area|idea|contact|promote] <name>'
---

# Para new

Creates **one entity** and nothing else: a project, an area, an idea, or a contact. It also runs the one promotion the lifecycle defines, `resources/ideas/<name>/` to `projects/<name>/`, because a promoted idea is a created project whose brief already exists.

The first job is **classification, not scaffolding.** Most requests to "start a project" turn out to be an area, an idea, or a document that needs filing, and a vault that lets all of them land in `projects/` stops being readable. The sorting test runs before any question about the work itself.

**This skill is vault-agnostic.** It reads the vault's CLAUDE.md at runtime for the PARA layout, the sorting test as that vault words it, what a project means there, any declared brief shape, the action-marker syntax, the naming and language conventions, and the "do not add" list. No vault-specific paths are hardcoded.

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

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Ask what the user wants to create, then run the full flow. |
| `<name>` | Full flow: classify, interview, propose, scaffold. |
| `project` / `area` / `idea` / `contact` `<name>` | Same, with the shape declared. **The sorting test still runs** and still overrules a declared shape that is wrong. |
| `promote <name>` | The idea-to-project path. |

Nothing is written before the proposal is approved, so there is no preview argument: every run is a preview until you say yes.

## Procedure

### Step 1 - Confirm context and check for a duplicate

1. Verify the cwd is a vault root (`projects/` plus at least one of `areas/` `archive/`, and a `CLAUDE.md`). If not, stop and say so.
2. Read the vault's `CLAUDE.md` for the parameters listed above.
3. **Fuzzy-match the name before anything else**, across `projects/`, `resources/ideas/`, `areas/`, and `areas/network/`. Report a near-match and confirm it is genuinely a different thing. In a vault several people write, the same work gets started twice under two names, and the duplicate is only noticed once both have history.

### Steps 2 and 3 - Classify, then interview

Settle the shape against the sorting test, then ask only what that shape needs: three questions for a project, two for an area, an idea, or a contact. **Full procedure: [references/interview.md](references/interview.md).**

### Step 4 - Propose and scaffold

Show the exact files and their content, then write the folder, fill the brief from the vault's declared shape, seed at most one action, and cross-link. **Full procedure: [references/scaffold.md](references/scaffold.md).**

### Promotion

When the entity already exists as an idea, this is a move rather than a creation: the brief is retensed in place, inbound links repoint in the same pass, and only the facts an idea brief cannot hold are asked for. **Full procedure: [references/promote.md](references/promote.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **A declared shape does not skip the sorting test.** `project <name>` states an intent, not a fact. If the work has no real deadline, say so and offer the shape that fits; creating it as a project anyway makes the skill a `mkdir` with extra steps.
- **An area absorbs before it multiplies.** Assets that gate each other are **one** area, not several: a domain, the site on it and the subscription paying for both belong together, because split apart the dependency between them stops being visible anywhere. Check whether an existing area should widen before creating a sibling.
- **Three questions, then stop.** The operator is starting something, not filling in a form. Everything not asked takes the vault's default or stays out of the file until it is real. A question whose answer changes no file is not asked.
- **One next action, not a plan.** A new project or area gets a single unblocked next step. Work that follows it is prose under `## Backlog` in the same file, promoted to a checkbox when its gate opens. Decomposing something new into a checklist is the action inflation the actionable-frontier rule exists to stop.
- **Never create an `actions.md` where the vault forbids one.** An idea gets a `brief.md` only, because `resources/` never holds a checkbox. A vault whose conventions drop action tracking gets prose next steps in the brief instead.
- **Write in the vault's language.** Structural filenames and headings follow the vault's convention (usually English, since the other skills parse them); the prose follows the vault's language rule and the operator's own words.

## Edge cases

- **It already exists.** Show what was found and ask whether to add to it instead. Never create a second folder for the same work.
- **It is really an area.** Say which test it failed (maintained, no end date), create the area, and offer to create the *dated push* as a project alongside it if there is one. The two coexist: the project archives when it ships, the area stays.
- **It is really a document.** Hand it to `/para-triage` rather than wrapping a single file in a project folder.
- **It belongs inside an existing area.** Say which one and why, and propose widening that area rather than creating a sibling. Creating it anyway is the commonest way an `areas/` tree becomes unreadable. An established area often carries only an `actions.md`, so widening may mean adding the scope to its actions file, or writing the `brief.md` it never had - propose whichever the area's own shape calls for rather than assuming a brief is there to edit.
- **A contact with nothing outstanding** carries the vault's empty-actions sentinel, so the file reads as a decision rather than an oversight.
- **The vault has no `resources/ideas/` or `archive/projects/`** because its `CLAUDE.md` never declared them: create the bucket only with approval, and say that it is a new bucket rather than an existing one.

## Related skills

- `/para-archive` - the other end of the same lifecycle. Its promotion edge case hands off here.
- `/para-triage` - files inbound artifacts into entities that exist. When triage finds a document with no home, this skill creates the home.
