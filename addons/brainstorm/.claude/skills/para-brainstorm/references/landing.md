# Landing (Step 7)

Referenced from [SKILL.md](../SKILL.md). Nothing below is written before the operator has approved it.

## Putting the candidates

The shortlist's top two or three, at most three, per [para-shared/asking.md](../../para-shared/asking.md): one question each, `header` `Idea 1/3` and so on, the candidate and its one-line read in the question. Options: land it as an idea `(Recommended)` for the top of the ranking, leave it in the record. A candidate matching an existing idea offers adding it to that idea's brief instead; one matching a retired idea names why it was shelved. Record every answer.

## An approved idea

Each is one `/para-new idea <name>` run, handed what its brief needs, in the vault's language:

- **The problem statement** it answers, from Step 4.
- **Who it is for.**
- **The riskiest assumption**: the one belief that, if wrong, makes the idea worthless.
- **The smallest test** that would settle it, with its success signal. That signal is the idea's one "revisit when" trigger.

`/para-new` runs the sorting test and the duplicate check as it always does. A candidate someone is already waiting on by a date comes out a project; this skill accepts the shape `/para-new` settles.

**A test the operator commits to on a date** is a checkbox in the actions file of the area the vault's `CLAUDE.md` names for a dated go/no-go on an idea (the business area unless it names another), linking the idea's brief. Ask for the date as an open line; with no date given, or in a vault that keeps no actions files, the trigger stays prose in the brief. Never a checkbox under `resources/`.

## The session record

One dated Markdown file, named by the vault's filing rule (`YYYYMMDD <Who> <Description>.md` by default, the description starting `Brainstorm`), dated the day the session ended. Where it lives:

- **One idea landed**: that idea's `sources/`.
- **Several landed, or none**: `archive/meetings/`, the vault's home for a conversation record spanning several entities.

It holds, in this order:

```
# <date> - Brainstorm: <topic>

**Kind:** <offering or improvement> · **Time:** <per week> · **Budget:** <amount> · **No-go:** <or none>

## Problems
1. For <who>, <task> is painful because <reason>, leading to <cost>. (picked)
2. ...

## Ideas
### <problem 1, short>
- <the operator's idea>
- <an agent idea> (agent)

## Shortlist
1. <idea> - pain: ...; worth: ...; four weeks: ... → landed as [<idea>](<link>)
2. <idea> - ... → left in this record
```

Every idea from Step 5 is in it, picked or not: an idea that was not picked gets no folder, and this file is where it stays findable.

## A run that stops partway

Write the record so far to `triage/`, the description ending `(partial)`, with one line under the title naming the last step completed. Tell the operator `/para-brainstorm <that path>` resumes it. A resumed run moves the finished record to its home above and deletes nothing else.
