# Test runs (shared across skills)

`--test` makes a skill report its own defects. It is removed from the arguments before anything reads them and combines with every other argument; any other `--flag` the skill's Arguments table does not list stops the run with the table printed.

The run does not change: the same steps, approvals and writes, against a copy of a vault, or a real vault with the skill's read-only argument, or stopping at the proposal where there is none. A skill is not fixed during a test run, neither the master nor the installed copy.

A finding is a defect in the skill, with the file and line of the instruction: a step that cannot be followed as written, two instructions that contradict each other (an installed copy differing from its master included), a wrong result the run caught, or a script failure with its exit code. A problem with the vault that the skill correctly reported is the skill working: list it under `Vault observations`. A step that merely had to be guessed at, or cost a round trip, is not a finding but a rule to shorten.

Report after the skill's own output:

```
## Test findings
/<skill> <arguments> on <vault>, <YYYY-MM-DD HH:MM> · skill copy: <folder loaded from> · steps exercised: <which ran, which were skipped>
1. [high|medium|low] <path>:<line> - <what happened>; expected <what>; fix: <one sentence>
## Vault observations
- <one line each, or omit the section>
```

`high` is a wrong result written or reported, `medium` one caught before acting, `low` the rest; `No findings.` is written, never implied. Save a copy to `${PARAOS_HOME:-~/.paraos}/data/test-runs/<YYYYMMDD-HHMM> <skill> <vault>.md`, never inside a vault, and say where. An issue is opened only for a `high` that reproduces on `main` and can be written as a failing test or eval case.
