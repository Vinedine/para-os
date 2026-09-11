# Signals

What to compute from the ledger, and what each number is allowed to mean. Loaded by Steps 2 and 3 of [SKILL.md](../SKILL.md).

## Parsing

Read every `resources/logs/sessions/*.jsonl` inside the window with a script, never by reading files into context. A month of a working team is tens of thousands of lines, and the whole point is to arrive at a page of findings without paying for the raw material.

Two rules the parser must follow:

- **A malformed line is skipped, not fatal.** The ledger is written by a fail-open hook, so a truncated final line is a normal artifact of a session ending mid-write. Count what was skipped and mention it only if it is more than a rounding error.
- **Group by `session` first.** Almost every useful signal is per session, not per event. Within a session, `prompt_id` groups the tool calls that one request caused, which is what makes "how much work did that ask turn into" computable.

Per session, derive: person (from the filename), start and end timestamps, duration, prompt count, tool count, whether anything was written, and the `SessionEnd` reason.

**Sessions nobody typed into are the denominator trap.** A client can open a session per window or per tile, so a ledger folder counts openings, not work, and most files can hold a `SessionStart` and a `SessionEnd` and nothing else. Split them out before computing anything per session - `summary.prompts` of 0 states it outright, and on an older ledger it is the absence of any `UserPromptSubmit` line - and report both numbers, because "90 sessions" and "25 sessions anyone worked in" support very different sentences.

**Files changed come from two fields, not one.** `target` names the file for a `Write` or `Edit`. `touched` - a list, with `touched_total` alongside it when the list was capped - names the files a tool changed *without* naming them itself, and it is the only way work done by a script run through Bash is visible at all. A parser that reads only `target` reports work that plainly happened as never having happened. Two caveats to carry into the report. Ledgers lacking a `touched` field have no indirect write tracking, so an older window must be described as blind here rather than as quiet. And `touched` is **inferred**: its window is the tool's own duration, so on a synced library a file another person's sync client landed inside that window is indistinguishable from one this call wrote. It is evidence of what changed, never proof of who changed it.

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

Map every `target` **and every `touched` entry** to its top-level folder and count sessions per bucket. Compare against the buckets that actually exist: a vault with an `archive/` nobody has opened in a month is either well-run or carrying dead weight, and which one it is depends on what else the ledger says.

Also worth one line each: files written by exactly one person (single points of knowledge), and files read repeatedly across sessions without ever being written (reference that is doing its job, or a question the structure never answers).

## C. Friction - where it fights back

- **Failures and denials.** Count `PostToolUseFailure` and `PermissionDenied` by tool and by target. A repeated failure on the same target is a defect with an address.
- **Sessions that produced nothing.** Prompts submitted, nothing written all session (`summary.writes` of 0, or no `Write`/`Edit`/`touched` on an older ledger). One is noise; a pattern is people asking for something the vault cannot do.
- **Turns per request.** Tool calls grouped by `prompt_id`. A request that expands into many turns is either real work or a badly-shaped task; read it against what was written at the end.
- **Rephrasing.** Consecutive prompts in one session that are near-repeats (compare lowercased, punctuation stripped, on token overlap). This is the strongest available signal that the vault did not understand a request. It is **not** evidence about the person's mood or ability, and the report must not say it is.
- **How sessions ended.** `reason` belongs to the harness, not to the ledger, and a client may report `other` for every ending - one does. Check whether it varies at all before building anything on it, and say plainly in the report when it does not. The usable answer is the `summary` object on the `SessionEnd` line (when present): `prompts`, `tools`, `writes`, `failures`, `denials`, `duration_s`, `last_prompt_tools`. Read `last_prompt_tools: 0` as "the final request produced no tool call", never as "abandoned" - a question answered in prose looks the same.

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
- **Attribution of a `touched` path.** The scan says a file changed while a tool ran, not that the tool changed it. On a vault several people sync, never name a person as the author of a `touched` path.
