# Test runs (shared across skills)

What `--test` does. Every para-os skill accepts it, a flavor's skills included: the skill runs against a real vault and reports its own defects.

## Parsing

**`--test` is removed from the arguments before anything else reads them**, wherever it appears. It is never part of an entity name, a scope word, a property name or a ref, and it combines with every other argument: `/para-triage preview --test`, `/para-upgrade --ref feat/x --test`.

## What changes, and what does not

**The run does not change.** Same steps, same approvals, same writes. An operator who wants no writes combines `--test` with the skill's own read-only argument (`preview`, `audit`) where it has one.

Three things are added, and only these:

1. **Keep a findings list while running**, noting each one when it happens, with the file and line of the instruction involved. One that cannot name them does not go in the list.
2. **Report it at the end** of the run, after the skill's own final output.
3. **Save a copy** of the report outside the vault.

**Never fix a skill during a test run**, not the master, not the installed copy, however obvious the fix. Record it and carry on, or stop where the skill's own rules say to stop.

## What counts as a finding

A defect in the **skill**, in one of six classes:

1. **Not followable as written.** A step names a path, heading, argument, tool or script that is not there, or assumes a state the vault is not in (a spread path in a vault resting in collected state).
2. **Contradiction.** Between two steps of the skill, between the skill and another skill or `para-shared/` file, between the skill and the vault contract it claims to read, or between the skill and the CHANGELOG. An installed copy that differs from its master is this class, naming both paths.
3. **Ambiguity that forced a guess.** Say what was guessed, and what the other reading would have done.
4. **A silent wrong result, caught.** A check that passed or returned nothing where it should have found something; a claim the skill was about to report that turned out false.
5. **A tool or script failure.** The command, the exit code, the error text.
6. **Friction.** A step that worked but cost a round trip the skill could have avoided, such as a question it could have answered from the vault.

**A problem with the vault is not a skill finding.** Drift, a missing file or a broken link that the skill correctly reported is the skill working. List those separately under `Vault observations`, one line each, with no fix proposed.

## The report

```
## Test findings

/<skill> <arguments> on <vault>, <YYYY-MM-DD HH:MM>
Skill copy: <the folder this SKILL.md was loaded from>
Steps exercised: <which ran, which were skipped and why>

1. [high] <skill>/<path>:<line> - <class>: <what happened>
   Expected: <what the instruction should have produced>
   Suggested fix: <one or two sentences>

## Vault observations

- <one line each, or omit the section>
```

- **Severity.** `high`: a wrong result was written, reported, or about to be. `medium`: the skill had to guess or be worked around. `low`: friction.
- **Cite the copy that ran.** `<path>:<line>` points into the installed copy the run actually read; where it differs from its master, that is a class 2 finding.
- **A run that stops early still reports**, at a precondition or an edge case alike, with the stop as the last step exercised.
- **No findings is stated, never implied.** Write `No findings.` under the heading, and keep the `Steps exercised` line.

## Saving it

Write the report to `${PARAOS_HOME:-~/.paraos}/data/test-runs/<YYYYMMDD-HHMM> <skill> <vault>.md`, creating the folder when it is missing, and say where it went. **Never inside a vault.** If the folder cannot be written, say so and leave the report in the conversation only.
