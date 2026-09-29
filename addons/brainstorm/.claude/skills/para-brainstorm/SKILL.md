---
name: para-brainstorm
description: Take the operator from what keeps going wrong to two or three ideas worth testing - frame the brainstorm, harvest their frustrations, turn them into problem statements, pick three, generate ideas with theirs first, shortlist, and land at most three through /para-new, keeping a dated session record of every idea. Runs any time, in one sitting or across several. Use when the user says "let's brainstorm", "help me come up with ideas", "what could I offer", "this keeps costing me time, what can I do about it", "brainstorm on <topic>", or types /para-brainstorm.
allowed-tools: Glob, Grep, Read, Write, Edit, Skill, AskUserQuestion
argument-hint: '[<topic>|<path>] [--test]'
---

# Para brainstorm

Takes one operator from frustrations to two or three ideas worth testing, and creates only what they approve. Onboarding's brainstorm inventories work that already exists; this one generates what does not exist yet, and it can be run again whenever something keeps costing time.

**This skill is vault-agnostic.** It reads the vault's `CLAUDE.md` at runtime for the PARA layout, where ideas and conversation records live, the filing and naming rule, which area owns a dated go/no-go on an idea, and the language.

Do NOT invoke to record an idea the operator has already formed (`/para-new idea` does that), or to plan work already committed.

## Two kinds of brainstorm, one flow

The frame's first question settles which: **a new offering** someone else would pay for, or **an improvement** to the operator's own work. Every step is the same. Only "what it is worth" reads differently: willingness to pay for an offering, what the problem costs today, in time or money, for an improvement.

## Arguments

| Arg | Behavior |
|---|---|
| *(none)* | Ask what to brainstorm on, then run the full flow. |
| `<topic>` | Full flow on that topic: a domain, a problem area, the business as a whole. |
| `<path>` | A record of a session already held or a run that stopped partway (notes, a transcript, a voice memo's text in `triage/`): read it, skip the rounds it answers, carry on from the first one it does not. |
| `--test` | Test run, see [para-shared/test-run.md](../para-shared/test-run.md). |

## Procedure

Every question follows [para-shared/asking.md](../para-shared/asking.md): a closed choice goes through `AskUserQuestion`, an open answer with nothing to suggest is a short numbered message. With no question tool, each round is one numbered message, and the run stops there until the operator answers.

### Step 1 - Read the vault first

1. **Resolve the vault root** per [operating-discipline.md](../para-shared/operating-discipline.md#defer-to-the-vault) and verify it: `projects/` plus at least one of `areas/` `archive/`, and a `CLAUDE.md`. Otherwise stop and say so.
2. Read `CLAUDE.md`, the root `README.md`, every brief under `resources/ideas/`, and the retired ideas under the archive. The frame asks only what these do not already say, and a candidate matching an existing or retired idea is named as such in Step 7.
3. With a `<path>`, read it and note which rounds it already answers.

### Steps 2 to 6 - The rounds

1. **Frame.** One call of closed questions: which kind of brainstorm, time available per week, budget, hard no's.
2. **Harvest.** One open round as a short numbered message: three things that went wrong or wasted time, what is still manual or full of back-and-forth, what people keep asking the operator for help with.
3. **Cluster and pick.** Rewrite the harvest as problem statements, confirmed by the operator, then pick three on three questions: painful, frequent, costly enough to act on.
4. **Ideate.** Per picked problem the operator goes first; the agent then adds its own under a fixed set of prompts, each marked as the agent's.
5. **Shortlist.** A one-line read per candidate on pain, what it is worth, and whether it can start within four weeks, ranked, and the ranking approved by the operator.

**The questions, the problem-statement form, the ideation prompts and the shortlist shape: [references/rounds.md](references/rounds.md).**

### Step 7 - Land

Two or three candidates, put to the operator item by item. Each approved one is one `/para-new` run, then the session record is written and every brief links it. **Where each output lands, the brief's four lines and the record's shape: [references/landing.md](references/landing.md).**

## Strict rules

**Everything in [para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **The operator's ideas come before the agent's**, in the harvest and in the ideation round. The agent suggests nothing until the operator has answered that round, and its own ideas stay marked as its own in the session record.
- **Generating and judging never share a round.** Nothing is scored, ranked or dismissed during the harvest or the ideation round.
- **Nothing is created before approval, and nothing for an idea that was not picked.** An unpicked idea lives in the session record only.
- **At most three ideas land per run.**
- **The skill writes no entity itself.** Every folder comes from a `/para-new` run, so the sorting test and the duplicate check apply unchanged: a candidate someone already waits on by a date becomes a project because the test says so, not because this skill does.
- **No number.** The shortlist is a ranking with a line of reasons per candidate; no score is summed or shown.
- **A checkbox never goes under `resources/`.** A test the operator commits to on a date is a checkbox in the owning area's actions file, linking the idea.

## Edge cases

- **The harvest is thin.** One frustration is enough to run on; say that fewer problems mean fewer ideas, and carry on rather than inventing more.
- **The operator stops partway.** Write the record so far to `triage/` ([references/landing.md](references/landing.md#a-run-that-stops-partway)), and say that `/para-brainstorm <path>` resumes it.
- **Nothing is worth landing.** The run still ends with its session record, and no folder.
- **A candidate matches an existing idea.** Offer to add it to that idea's brief instead of creating a second one; a match with a retired idea is named with the reason it was shelved.

## Related skills

- `/para-new` - creates each approved idea; this skill never scaffolds one itself.
- `/para-archive` - retires an idea whose test failed; its revisit trigger stays the one this skill wrote.
