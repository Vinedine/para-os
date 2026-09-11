# Asking item by item (shared across skills)

How a skill puts a batch of decisions to the operator through `AskUserQuestion` instead of one table and one `go`. Shared because five skills do it and the mechanics are identical; what differs per skill is only the **vocabulary** - the dispositions its questions may offer - which stays in that skill's own reference.

**Why per item rather than per batch.** `operating-discipline.md` requires individual approval for anything destructive: *"Deletions are approved one by one. No batching, no exceptions."* A table approved by a single word cannot deliver individual approval.

## Before the questions: the manifest

Print one line per question, numbered to match the order they will be asked, then the count and the number of rounds:

```
14 items, 11 questions (2 grouped), 3 rounds.

 1  <item>                        → <proposed action>  <destination or target>
 ...
```

One line, no pipes, no reasoning column: the reasoning belongs in the option description where the operator reads it at the moment of deciding. This is the overview, not the proposal. It exists so the batch shape and the number of rounds are visible before the first question, and so an abandoned run still leaves a readable trace.

**If the batch exceeds 20 items**, the first question asked is whether to go item by item or fall back to the written proposal. Six rounds is a chore, and a chore gets clicked through.

**The manifest is for a batch, and below four questions there is none.** Count the questions first: **four or more, print it; fewer, go straight to asking.** The threshold is per run, not per skill.

## The question

Batch up to **4 questions per call**, ordered so questions about the same entity or file land together.

- **`header`** - the position: `Item 3/11`, `Group 5/11`, `Action 8/11`. Twelve characters is not enough for a filename, and the operator needs to know where they are in the batch. **A skill that asks exactly one question spends that budget on a label instead**, because `1/1` tells the operator nothing the question does not: name the decision - `Shape`, `Disposition` - and let the calling skill say which word it wants.
- **`question`** - the item by name, and the proposed target in full. The target is the thing being approved; never abbreviate it to something the operator has to reconstruct.
- **`options`** - 2 to 4, from the calling skill's vocabulary. **The proposal goes first, labelled `(Recommended)`.** Each description carries the evidence for that disposition and the full target.

  **One question shape carries no recommendation: a question of fact about the operator's own situation.** Some decisions cannot be reached until a fact only the operator holds is settled - whether feedback arrived before or after a release, whether a document is the signed copy, whether a thread was already answered by phone. That question is legitimate and often has to be asked *first*, but the skill has no proposal to make: every option is a fact it does not know, and labelling one `(Recommended)` guesses at the operator's life and lends the guess the weight of a proposal. **Ask it with no option labelled, order the options by what the vault's own evidence suggests, and say in each description what that disposition would mean for the run.** The recommendation rule governs dispositions, which are the skill's to propose; it does not govern facts, which are not.
- **`multiSelect: false`**, always. A disposition is exclusive; splitting a group is an **Other** answer, not a multi-select.
- **`preview`** - optional per option, and worth it where the options differ in something the operator would rather see than read: the folder scaffold a shape would produce, a line before and after grooming, a brief's opening as it would be retensed. Skip it where the option label already says everything. **A preview shows the content as it will actually be written**, never a prettier rendering of it: the selected preview comes back as the approved content, so a line wrapped for readability against a file whose rule is one line per item is a mockup that misleads at the exact moment of approval. Where the real form is genuinely unreadable in a preview, say so in the description rather than reformatting it.

**Every question carries an escape that changes nothing** - leave it, skip it, decide later. A question that forces a disposition is a question that will get a wrong one.

## Grouping

Linked items get **one** question. Linked means one sentence can state the disposition for all of them **and** the question can name every member. Three hard limits, each closing a way a group hides a decision:

- **Never group a destructive item with anything.** A delete, a close, a drop: its own question, always, whatever it arrived beside.
- **Never group items whose targets differ.** A shared target is what makes one answer honest for all of them.
- **Never group more than five.** Past that the question stops naming its members and becomes a batch approval wearing a question's clothes, which is the defect this whole pattern exists to fix, reintroduced by its own fix.

**A destructive question states its evidence in the option description**: what survives it, and where. Where the evidence is a judgment rather than a fact (content overlap rather than a hash match, "probably done"), the recommended option is the one that changes nothing - **but only where the loss would be irreversible**, a deleted file or an unrecoverable record. Where the change is reversible and leaves its own trace - a closed checkbox that keeps its text and a stated reason, a demotion that preserves every word - recommend what the evidence actually supports. A recommendation that is systematically the safe one is uninformative.

## Reading the answers

- **Other is an amendment, not an answer.** If the free text names an unambiguous disposition, take it, echo the correction, and carry on. If it is ambiguous or asks something, answer it and re-ask that one question with the corrected proposal. Never execute an Other whose meaning you inferred.
- **A skipped question is a deferral, not an approval.** A question can come back unanswered, as `[No preference]`. Nothing about that item was decided, so it executes nothing - never read it as assent to the recommended option, which is the one reading that turns a shrug into a delete. Re-ask it once in the next round, saying it came back unanswered and naming what leaving it does; if it is skipped again, record it as a deferral and move on.

Record every answer, deferrals and amendments included, and carry them into the skill's final summary. The manifest records what was proposed; the summary is the record of what was decided, and a disposition appearing in neither leaves no trace at all.

## When not to ask

**Fail toward the written proposal.** A question nobody can answer stalls a run that would otherwise have produced something readable, so anywhere it is unclear whether an operator is present, build the table and stop. Never call `AskUserQuestion`:

- On any **argument that already bypasses approval** - a preview that stops at the proposal, an apply that runs on approval already given, an unattended entry point that makes no judgment calls to approve. Each calling skill names its own.
- On an explicit **escape argument** for an operator who would rather read a batch than click through it.
- When **no interactive operator is present**: a scheduled task, a subagent, a non-interactive run. The skip is a property of the entry point rather than a flag anyone has to remember.

On those paths the skill produces the markdown proposal it always did, gated on a single "reply **go**", or nothing at all.

**A preview prints the manifest first, then the table.** The manifest is the plan of the run it stands in for - how many questions, which items group, how many rounds - so a preview still shows the shape of what a live run would ask, and the table carries the reasoning a live run puts in the option descriptions.
