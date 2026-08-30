# Signals

What to compute from the ledger, and what each number is allowed to mean. Loaded by Steps 2 and 3 of [SKILL.md](../SKILL.md).

## Parsing

Read every `resources/logs/sessions/*.jsonl` inside the window with a script, never by reading files into context. A month of a working team is tens of thousands of lines, and the whole point is to arrive at a page of findings without paying for the raw material.

Two rules the parser must follow:

- **A malformed line is skipped, not fatal.** The ledger is written by a fail-open hook, so a truncated final line is a normal artifact of a session ending mid-write. Count what was skipped and mention it only if it is more than a rounding error.
- **Group by `session` first.** Almost every useful signal is per session, not per event. Within a session, `prompt_id` groups the tool calls that one request caused, which is what makes "how much work did that ask turn into" computable.

Per session, derive: person (from the filename), start and end timestamps, duration, prompt count, tool count, whether anything was written, and the `SessionEnd` reason.

## A. Adoption - what gets used

**Enumerate first, then subtract.** List the vault's declared capabilities before looking at the log: the skills in its `.claude/skills/`, the ones its CLAUDE.md names, and the integrations in `resources/scripts/`. Then mark which the ledger never shows. Assembling this list from the log instead is the single easiest way to miss the biggest finding, because a thing nobody used leaves no trace to notice.

Detect an invocation from `UserPromptExpansion` events, and from prompts whose first token starts with `/`. Count per skill and per person.

The four shapes this produces, in descending order of how much they should change:

| Shape | Reading |
|---|---|
| Invoked by nobody, ever | The capability does not exist as far as its users are concerned. Fix discovery or delete the capability |
| Invoked once, early, never again | It was tried and abandoned. The friction signals usually say why; if they do not, this is the thing to go and ask about |
| Invoked by one person only | Not adoption but a private habit. Ask whether it is worth teaching or worth removing |
| Used steadily by several | Working. Say so in the report; a report that lists only failures gets read as a complaint |

## B. Reach - what gets touched

Map every `target` to its top-level folder and count sessions per bucket. Compare against the buckets that actually exist: a vault with an `archive/` nobody has opened in a month is either well-run or carrying dead weight, and which one it is depends on what else the ledger says.

Also worth one line each: files written by exactly one person (single points of knowledge), and files read repeatedly across sessions without ever being written (reference that is doing its job, or a question the structure never answers).

## C. Friction - where it fights back

- **Failures and denials.** Count `PostToolUseFailure` and `PermissionDenied` by tool and by target. A repeated failure on the same target is a defect with an address.
- **Sessions that produced nothing.** Prompts submitted, no `Write` or `Edit` all session. One is noise; a pattern is people asking for something the vault cannot do.
- **Turns per request.** Tool calls grouped by `prompt_id`. A request that expands into many turns is either real work or a badly-shaped task; read it against what was written at the end.
- **Rephrasing.** Consecutive prompts in one session that are near-repeats (compare lowercased, punctuation stripped, on token overlap). This is the strongest available signal that the vault did not understand a request. It is **not** evidence about the person's mood or ability, and the report must not say it is.
- **How sessions ended.** The `SessionEnd` reason separates finishing from abandoning.

## D. Rhythm

Sessions per person per week, median duration, and the gap between a person's first ever session and their most recent. A team whose usage stopped after week one has a different problem from one that never started, and only the dates distinguish them.

## E. Contradictions - usage against the vault's own rules

Read the reviewed vault's CLAUDE.md, then check only what that vault actually declares. Each of these is a rule the structure invites people to break:

- A checkbox in a bucket the vault forbids one in.
- `triage/` holding files while the vault's triage skill was never invoked in the window.
- An entity folder missing the files its conventions require (usually a brief).
- Actions carrying invented or absent dates where the vault has a dating rule.
- Entities created by hand - a write straight to `projects/<x>/brief.md` with no creation skill invoked - which says the skill is unknown, not that the person was wrong.
- Files landing at the vault root, or in a bucket whose purpose the filing rules put elsewhere.

**Every one of these is a finding about the vault, not the person.** A convention people work around is either badly designed, badly explained, or badly enforced, and the report's job is to say which.

## What none of this can support

- **Intent.** The ledger records what was asked, not what was meant. Never diagnose confusion or frustration from wording.
- **Productivity.** Session counts and durations measure activity, not value. Someone who thinks for an hour and writes one good line will look idle here.
- **Completeness.** Only Claude Code sessions are recorded. A file edited directly, a page read in a browser, and a question abandoned before it was typed are all invisible, and the last one is often the most important thing that happened.
- **Causation.** Two signals moving together is a hypothesis worth testing by asking someone, not a finding.
