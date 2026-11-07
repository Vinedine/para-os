# Signals

What each number in the scan is allowed to mean. Loaded by Steps 2 and 3 of [SKILL.md](../SKILL.md).

## Parsing

- Mention `frame.skipped_lines` only beyond a rounding error.
- **Sessions nobody typed into are the denominator trap.** A client can open a session per window or per tile, so a ledger folder counts openings, not work. Report both `sessions` and `typed_sessions`, because "90 sessions" and "25 sessions anyone worked in" support very different sentences. Report `unrelated_sessions` as unrelated to the vault, by count only, and never quote one.
- **A script's writes are visible only through `touched`**, which older ledgers lack: describe such a window as blind to them, not quiet.

## A. Adoption - what gets used

**Enumerate first, then subtract.** `never_invoked` holds every skill the vault installs or its CLAUDE.md names that the window never shows; add the integrations in `resources/scripts/` it never shows.

The four shapes this produces, in descending order of how much they should change:

| Shape | Reading |
|---|---|
| Invoked by nobody, ever | The capability does not exist as far as its users are concerned. Fix discovery or delete the capability |
| Invoked once, early, never again | It was tried and abandoned. The friction signals usually say why; if they do not, this is the thing to go and ask about |
| Invoked by one person only | Not adoption but a private habit. Ask whether it is worth teaching or worth removing |
| Used steadily by several | Working. Say so in the report |

## B. Reach - what gets touched

A bucket in `untouched_buckets`, such as an `archive/` nobody has opened in a month, is either well-run or dead weight, and which one depends on what else the ledger says.

Also worth one line each: a file `writers_by_file` gives one writer (a single point of knowledge), and `read_never_written` (reference doing its job, or a question the structure never answers).

## C. Friction - where it fights back

- **Failures and denials** (`failures`, by tool and target). A repeated failure on the same target is a defect with an address.
- **Sessions that produced nothing** (`typed_without_writes`). One is noise; a pattern is people asking for something the vault cannot do.
- **Sessions left open for days** (`multi_day_sessions`): stale context, and entities mixed up where it touched several (`entities`).
- **Tool calls per request** (`tools_per_request`). A request that expands into many tool calls is either real work or a badly-shaped task; read it against what was written at the end.
- **Rephrasing** (`rephrased`): the strongest available signal that the vault did not understand a request.
- **How sessions ended** (`endings`). The `reasons` are the harness's, and a client may report `other` for every ending: where they never vary, say so and build nothing on them. `last_request_without_tools` means the final request produced no tool call, never "abandoned": a question answered in prose looks the same.

## D. Rhythm

`rhythm`, per person: `weeks`, `median_minutes`, and `first_ever` against `last`. A team whose usage stopped after week one has a different problem from one that never started, and only the dates distinguish them.

## E. Contradictions - usage against the vault's own rules

Read the reviewed vault's CLAUDE.md, then check only what that vault actually declares. Each of these is a rule the structure invites people to break:

- A checkbox in a bucket the vault forbids one in.
- `contradictions.triage_unrun`: notes waiting in `triage/` while `/para-triage` never ran.
- An entity folder missing the files its conventions require (usually a brief).
- Actions carrying invented or absent dates where the vault has a dating rule.
- Entities created by hand - a write straight to `projects/<x>/brief.md` with no creation skill invoked - which says the skill is unknown, not that the person was wrong.
- Files landing at the vault root, or in a bucket whose purpose the filing rules put elsewhere.

A convention people work around is either badly designed, badly explained, or badly enforced, and the report's job is to say which.

## What none of this can support

- **Productivity.** Session counts and durations measure activity, not value. Someone who thinks for an hour and writes one good line will look idle here.
- **Causation.** Two signals moving together is a hypothesis worth testing by asking someone, not a finding.
- **Attribution of a `touched` path.** The scan says a file changed while a tool ran, not that the tool changed it. On a vault several people sync, never name a person as the author of a `touched` path.
