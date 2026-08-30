# Report shape

The output of Step 4 of [SKILL.md](../SKILL.md). One Markdown file, written where the review was invoked.

## Filename and location

`<review-vault>/areas/<maintainer-area>/usage/YYYY-MM-DD-<reviewed-vault>.md`, or wherever the operator's own conventions put maintenance records. Propose the path and confirm it before writing. Never write it into a vault belonging to the people being reviewed.

## Shape

```markdown
# <Vault> usage review - YYYY-MM-DD

**Window:** N days, S sessions, P people. <one line on whether that is enough to conclude from>
**Ledger:** <first date> to <last date>. <anything missing, e.g. prompts not recorded>

## What nobody used

## Where it fights back

## Where usage contradicts the rules

## What is working

## Changes to make

## What this cannot see
```

Six sections, in that order, and the order is the argument: absence first because it is the finding people most reliably miss, changes last because they should read as consequences of what came before rather than opinions.

## Writing a finding

Three parts, always, and a finding missing the third gets cut:

1. **What was observed**, with the number and the window it came from.
2. **The evidence**, quoted or counted. A prompt verbatim, a file path, a count with its denominator.
3. **The change it implies** - a named edit to a skill, a template, a convention, an integration, or the onboarding walkthrough.

> **`/para-triage` was never invoked, in 34 sessions across 4 people, while `triage/` grew from 3 to 41 files.** Two people wrote files straight into `projects/` instead, which is the workaround the structure makes easiest. **Change:** the walkthrough opens with triage rather than mentioning it ninth, and `/para-daily-brief`'s triage line moves above the fold.

Rank by what the change would be worth, not by how large the number is. A capability nobody found outranks a tool that failed eleven times, because the second is a bug and the first is a product that is not being used.

Cap the list at what a maintainer will act on: five or six changes, with the rest as a short "also seen" line. A report proposing twenty changes gets none of them made, which is the same action-inflation failure the vault rules exist to prevent, moved up a level.

## Register

- **Findings name defects, never people.** Write "two of four people never opened `areas/`", never "X did not use areas". Per-person counts distinguish "nobody" from "one person"; that distinction goes in the reasoning, not on the page as a ranking.
- **Quote prompts as evidence of what was asked, and stop there.** No inference about what someone meant or felt.
- **State the blind spots in their own section**, not as a caveat buried in the intro. What the ledger cannot see is part of the result.
- **Include what works.** A report that only lists failures gets read as a complaint about its readers, and the thing that is working is usually the thing to build the next change on.

## Across reviews

Each report is dated and kept; the interesting signal is the second one. Adoption that has not moved between two reports is a stronger finding than anything in either report alone, and it is only available if the first was written down.
