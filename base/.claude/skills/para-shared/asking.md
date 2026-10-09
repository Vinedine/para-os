# Asking item by item (shared across skills)

How a skill puts a batch of decisions to the operator through `AskUserQuestion` instead of one table and one `go`. The vocabulary, the dispositions a question may offer, stays in each skill's own reference.

## Before the questions: the manifest

Four or more questions: print the count line, worded exactly `N items, N questions (N grouped), N rounds.`, then one line per question, numbered in the order they will be asked, ahead of the questions or, on a path that does not ask, ahead of the table. Fewer: skip it.

```
14 items, 11 questions (2 grouped), 3 rounds.

 1  <item>                        → <proposed action>  <destination or target>
```

One line each, no pipes, no reasoning: that belongs in the option description. Past 20 items, the first question is whether to go item by item or fall back to the written proposal.

## The question

Up to **4 questions per call**, questions about the same entity or file together.

- **`header`**: the position, `Item 3/11`, `Group 5/11`. A skill asking exactly one question names the decision instead: `Shape`, `Disposition`.
- **`question`**: the item by name and the proposed target in full, never abbreviated.
- **`options`**: 2 to 4 from the skill's vocabulary, the proposal first and labelled `(Recommended)`, each description carrying its evidence and the full target. **A question of fact about the operator's own situation carries no recommendation**: order its options by what the vault's evidence suggests and say in each what that answer does to the run.
- **One decision per question**, and `multiSelect: false`: a disposition is exclusive, and splitting a group is an **Other** answer.
- **`preview`**, where the options differ in something the operator would rather see than read, shows the content exactly as it will be written, never reformatted to fit; where it cannot fit, a fragment marked abbreviated.

Every question carries an escape that changes nothing: leave it, decide later.

## A question with a suggested answer

- **A closed choice** (purpose, language, a flavor, a shape) is always a question.
- **An open answer** (a name, a deadline, a URL) is a question only when the skill holds a concrete suggestion, first and `(Recommended)`, with **Other** for the correction; with nothing to suggest, a short numbered message in prose.
- **A discovery question** (what eats your week) asks which of several things hold, so it is the one shape asked with `multiSelect: true` and no recommendation.

## Grouping

Linked items get one question: one sentence states the disposition for all of them and the question names every member. Never group a destructive item (a delete, a close, a drop) with anything, never items whose targets differ, never more than five.

A destructive question states its evidence in the option description: what survives, and where. Where the evidence is a judgment and the loss would be irreversible, the recommended option is the one that changes nothing; where the change leaves its own trace (a closed checkbox keeping its text and reason, a demotion preserving every word), recommend what the evidence supports.

## Reading the answers

- **Other is an amendment.** An unambiguous disposition in the free text is taken and echoed; an ambiguous one is answered and that question re-asked. An Other whose meaning was inferred is not executed.
- **A skipped question is a deferral**, not assent to the recommended option. Re-ask it once, saying it came back unanswered and what leaving it does; skipped again, record the deferral.

Every answer, deferrals and amendments included, goes into the skill's final summary.

## When not to ask

Fail toward the written proposal: wherever it is unclear whether an operator is present, build the table and stop. `AskUserQuestion` is not called on an argument that already bypasses approval (a preview, an apply, an unattended entry point), on an explicit escape argument, or with no interactive operator (a scheduled task, a subagent). Those paths produce the markdown proposal gated on a single "reply **go**", or nothing.
