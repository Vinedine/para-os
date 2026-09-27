# Eval cases

Behaviour tests for the skills in `base/.claude/skills/`, run by the vendor's
`claude plugin eval` through [`tools/eval.py`](../tools/eval.py).

```bash
python3 tools/eval.py                                 # every case, three runs, two arms
python3 tools/eval.py --case daily-brief-*            # one group
python3 tools/eval.py -- --runs 1 --ablation none     # while iterating: one arm, one run
```

`py -3` on Windows. Anything after `--` goes to the vendor command unchanged.

`tools/eval.py` grants the gated tools (`Bash`, `Write`, `Edit`) that the selected cases list
in their `allowed_tools`, and says which on its first lines. Passing `--allow-tools` yourself
replaces that grant.

## Where this sits

Three layers test this repo, cheapest first, and each one catches what the layer below
cannot:

| Layer | Covers | Cost |
|---|---|---|
| `tools/check.py` | Structure: frontmatter, markers, revisions, line caps, shipped prose | Free |
| `base/.claude/skills/*/scripts/test_*.py` | The mechanical logic a skill hands to a script, and the shared library under `para-shared/scripts/` | Free |
| `evals/` (this folder) | Whether a skill triggers, and whether its answer is right | A model call per run |
| `--test` on a real vault | What nobody thought to test | A session |

A suite lives beside the code it covers, so the copy installed in a vault carries its own
tests and `/para-upgrade` can verify a synced script by running them. `tools/check.py`
runs every one of them, `tools/coverage_report.py` measures what they reach (CI
fails when that drops), and `tools/eval.py` runs this folder.

The loop that makes the suite grow: when a `--test` run finds a defect, it becomes a unit
test if it is mechanical and an eval case if it is judgment, and only then is it fixed.

## Who pays, and on which model

A run uses whatever Claude Code is logged in with. On a Claude subscription it counts against
the plan's usage limits; with `ANTHROPIC_API_KEY` set it is billed to that key instead. The
dollar figures in the report are list-price estimates either way, and `--max-cost-usd` caps
that estimate, not plan usage. The three triage cases, three runs each on two commits, came
to about four dollars of estimate and twenty minutes.

Runs use the harness's default model unless `--model` names another, and the `llm` graders
use Haiku unless `--judge-model` does. A cheaper model is fine while iterating on a case's
wording or its triggers. Decide on the model operators run: a skill's prose is a bet on what
that model does without being told, so a result on a different model answers a different
question. Say which model produced a result when you report it.

## Checking a skill change

A cut or a rewrite of a skill's prose is checked by running the same cases on the commit
before the change and on the change, three runs each, and comparing per grader. **One run
is not a verdict**: two single runs of `triage-preview-manifest` each missed a different
fixed phrase, on either side of the same change.

```bash
git worktree add --detach ../before <change>^
(cd ../before && python3 tools/eval.py --case 'triage-*' -- --runs 3 --ablation none --keep-temp)
python3 tools/eval.py --case 'triage-*' -- --runs 3 --ablation none --keep-temp
git worktree remove ../before
```

`--ablation none` drops the no-skill arm, which answers a different question. `--keep-temp`
keeps each run's `trace.jsonl`, which is the only way to see why a regex grader failed.

Read the failures on both sides before blaming the change. The `para-triage` prose cut
(9,088 to 6,410 words) scored the same or better on every case, and the failures it did show
were there before it:

| Case | Before | After | What the traces showed |
|---|---|---|---|
| `triage-preview-manifest` | 0.67 | 0.89 | Both paraphrase the fixed manifest wording now and then; both offer **Create entity** on the preview path, which the skill rules out (3 of 3 before, 2 of 3 after) |
| `triage-staged-note-updates-existing` | 0.44 | 0.44 | The answer is right on both sides; the graders want "delete the note" and "Update existing" on the same line as the file, and the model writes "Delete the triage note" and splits the line |
| `shell-triage-uses-the-script` | 0.53 | 0.67 | Neither side ever redirects the scan's output to a file |

Each of these was then fixed where it lives rather than re-run until it passed: the scan
prints the subdirectory line and keeps its own copy of its output, so neither depends on a
run's wording or memory; the skill states the Create entity exclusion where filing recommends
it, which cut that slip to one run in three rather than removing it; and the two staged-note
graders accept the wordings the model used, a table row included, tested against every kept
trace and against wrong answers.

## What a case is

One directory per case: `case.yaml` names it and points at the fixture script, `prompt.md`
holds what the operator types and the run's limits, and each file under `graders/` is one
check on the result. `_fixture/vault.sh` builds the vault every case runs against, with
its dates written relative to the day of the run, so a case scores the same whenever it
runs.

Runs start in an empty directory with none of your settings, skills, or connectors, and
the vault's own `CLAUDE.md` is not loaded for them: a skill that needs a convention has to
read the file, which is what the skills do anyway.

## Four limits worth knowing before writing a case

**A prompt typed as the slash command never shows a `Skill` call.** The harness expands
`/para-pipeline property` in place, so a `tool_used Skill` grader reports zero calls on
every run and the trigger is not tested. Write the prompt the way an operator would say
it, and keep the slash form for a case about argument parsing alone, with no trigger
grader.

**A shell grant needs a sandbox.** Granting `Bash` is refused on native Windows, so a case
that needs a shell has to run under WSL2 with a real distribution, or on a Linux runner.
Cases that stay inside `Read`, `Glob`, `Grep` and `Skill` run anywhere. Without a shell a
skill takes the date from the session rather than the system clock.

**No run can ask a question.** Every run is a non-interactive session, and the harness
removes the tools that need a person's answer, `AskUserQuestion` among them, even when a
case lists it in `allowed_tools`. A skill following `para-shared/asking.md` then prints
its questions as text, the path that file names for a run with no interactive operator.
Grade the printed question with a regex; a `tool_used AskUserQuestion` grader fails every
run, in both arms, whatever the skill does.

**A regex grader shows no evidence.** When one fails, the report gives the verdict and not
the text it judged. Re-run that case with `--keep-temp` and read `out/trace.jsonl` in the
directory it prints, or grade with a rubric, which does show what the judge saw.
A `tool_used` grader's `input_match` reads the tool's input as a JSON string, where the
quotes a model puts around a script's path arrive escaped (`\"`), so a clause like `[^"]*`
after the script name stops at that quote and reports the call as never made. Match across
it with `.*?`, and test a grader against a kept trace before paying for a pass.

**What a grader may read, and two traps in it.** `target:` on a regex grader (and `focus:`
on an `llm` one) takes `last_message`, the default, or `trace`, `files`, or
`{source: file, path}`; `tool_used` takes `min` and `max`, and a "never calls this tool"
check needs `min: 0`, `max: 0` **and** `arm: both`, since `arm` left off `tool: Skill` makes
it display-only under ablation. The traps: a `trace` target also reads every skill file the
run opened, so a pattern quoting the skill's own manifest example matches its documentation
rather than its behaviour; and a **proximity pattern over a proposal table is not a check on
one row**, because the neighbouring row's destination sits inside any window wide enough to
be useful.

**A `not_contains` grader on a keyword also catches the sentence that declines it.** Match
the affirmative forms (`(recommended)`, `Recommendation: proceed`, `I'd recommend`) rather
than the bare word, and read a kept trace before believing a steady one-in-three lapse.
The same holds for format: a pattern wanting `15 open` on one line misses the same fact
written as a table row (`| actions.md | 15 | over the threshold |`).

**Under WSL, read a kept run directory in place.** Copying `out/trace.jsonl` to `/mnt/c`
fails silently; open it from inside the distribution in the same session instead, and
in the same `wsl` call that ran the case: a later call can find the distribution restarted
and `/tmp` empty. Each `kept temp:` line prints *before* the result of the run it belongs
to, not after.

## What a grader should check

The baseline arm answers a sharper question than "did it work": it runs the same prompt
with no skills loaded at all. **A case whose score is the same in both arms is measuring
something the model already did on its own**, and a suite of those costs money to learn
nothing. Two cases here were exactly that before they were rewritten: a bare model already
reports an archived project as archived, and already resolves a name written with dots.

So a grader checks what the vault's conventions require and a bare model has no reason to
do: that at most five items are offered as the work to do now and the rest are counted,
that one next action closes the brief, that an item with no date marker is reported as
undated rather than given a deadline its prose hints at, and that an item living in
someone else's file is never counted as this entity's own work.

What is mechanical stays out of here. Name matching, bucketing and the hygiene sweeps are
pinned by the free unit suites beside the scripts, so paying a model to re-check them is
duplication, not coverage.

## The shell cases

Each `shell-*` case asserts that a skill runs its script (`brief_scan.py`,
`clean_scan.py`, `archive_scan.py`) rather than scanning by hand, which no `native` case can
see. They need `Bash`, so they need a sandbox backend and a Python on PATH: they run on a
Linux runner or under WSL2, and on native Windows the grant is refused outright when given
and the graders fail when it is not.

**Neither outcome is free**, which is why a case declares whether it can pass here: the
cases that can carry `native`, these carry `shell`, and `tools/eval.py` selects `native`
unless you pass `--shell`. Skipping them locally saves about two dollars a case. To run
them where they work:

```bash
python3 tools/eval.py --shell
```

It grants `Bash` itself. On native Windows, or on Linux without `bubblewrap` and `socat`, it
stops before the first model call and says what is missing, rather than paying for a run
the harness then refuses.

**Under WSL2**, four things differ from a Linux runner. Name the distribution on every call (`wsl -d Ubuntu -e bash -lc '...'`): with Docker Desktop installed the default can be `docker-desktop-data`, where a bare `wsl` fails with mount errors that read like a broken WSL. Run a Linux install of Claude Code
from inside the distribution: the Windows one is reachable through the shared PATH and
runs with no sandbox, so check `command -v claude` names a path under your Linux home.
Linux needs `bubblewrap` and `socat` for the sandbox. And a kept run directory lives in the
distribution's `/tmp`, which is sealed read-only by the harness and cleared when the
distribution stops, so copy `out/trace.jsonl` out in the same session that ran the case.

## The write cases

Some promises are about what a skill does not write: the bootstrap writes no file before
its questions are answered, `/para-new` writes nothing before its proposal is approved, and
`/para-activity-review` confirms a report's path before writing it. A case grading one lists
`Write` and `Edit` in `allowed_tools` and carries the tag `write`. The harness gates those
tools like `Bash`: without the grant it withholds them from the model, so a "never calls
`Write`" grader passes for want of anything to refuse, and only the text graders score.
`tools/eval.py` grants both whenever a selected case lists them, so the write graders bite in
an ordinary run. To run only these:

```bash
python3 tools/eval.py -- --tag write
```

A run with `--max-cost-usd 0` loads and checks every selected case, graders included, and
stops before the first model call, so a new case can be checked for shape at no cost.

## The install cases

The `install-*` cases read the kit as this checkout has it. `_fixture/kit/` holds symlinks
to the repo's `INSTALL.md` and `base/`, and `tools/eval.py`'s copy of this folder follows
them into real files, so a case tests the text under review rather than a copy of it that
drifts. A checkout made with symlinks off, Git for Windows' default, holds a one-line text
file there instead, and these cases stop at setup saying so: turn on git's `core.symlinks`
and check out again, or run them under WSL2. They carry no `native` tag for that reason.

No skill carries the bootstrap: both arms read the same `bootstrap-prompt.md` from the
fixture, so both score the same and the baseline arm buys nothing. Run them on one arm:

```bash
python3 tools/eval.py --case 'install-*' -- --ablation none
```
