---
name: para-ingest
description: Read every vault's declared triage sources once from outside the vaults, decide only which vault each item belongs to, and stage it as a note in that vault's triage/ folder. Runs from anywhere and never judges what an item means. Use when the operator runs several vaults that declare the same mailboxes and asks to "pull everything in", "check all my vaults for new mail", "run the ingest", "route what came in", or types /para-ingest.
allowed-tools: Bash, Glob, Grep, Read, Write, ToolSearch, mcp__*__search_threads, mcp__*__get_thread, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__google-workspace__search_gmail_messages, mcp__google-workspace__get_gmail_messages_content_batch, mcp__google-workspace__get_gmail_thread_content
arg-hint: '[preview|write]'
---

# Cross-vault ingest

Reads every registered vault's declared triage sources **once**, decides **only** which vault each item belongs to, stages a note in that vault's `triage/`, and stops.

**It never decides what an item means.** No classifying, no drafting an action, no filing into an entity, no touching a mailbox. Every judgment about meaning stays with `/para-triage`, interactively, in the vault the item landed in.

- **It needs `para-shared/` beside it.** The two links below resolve once this folder is installed next to the other `para-*` skills, which is where the module README says to put it. In the repo they do not resolve.

**Run it from anywhere.** Unlike every other `para-*` skill this one is not scoped to the cwd: the registry outside the vaults is what tells it they exist. The substrate stays federated and only the index is central, so no vault ever learns another vault's content.

## Arguments

| Arg | Behavior |
|---|---|
| `preview` *(default)* | Read everything, route everything, write **nothing**. Sync scripts run without `--write`, no note is staged, no ledger entry made. One run log, `mode: preview`. |
| `write` | The same run, staging notes and ledgering what it staged. The only mode that touches a vault. |
| `--days N` | Override the window for this run only, in either mode. The one way to reach back past the write window, and it exists for two jobs: recovering the carry-over Step 3 reports, and a deliberate one-off backfill. Never scheduled, never a default, always typed by a person who has read what it would stage. |

Preview is the default deliberately: a router that is quietly wrong for a month erodes trust in every vault it writes to, so it earns write mode by being read first.

## Procedure

### Step 0: Read the registry

`${PARAOS_HOME:-~/.paraos}/vaults.json` is the single enumeration of vaults. **Schema, the `purpose` field, and what an unmounted path does to the run: [references/registry.md](references/registry.md).**

No registry means there is nothing to ingest for: say so, point at the template in the module README, and stop. Never infer the vault list by globbing a directory.

### Step 1: Build the source plan

For each **active** vault read its `CLAUDE.md` `## Triage sources` block and its root `README.md` `## Operating model` section. The block says what the vault pulls; the Operating model says what the vault *is*, and routing needs both.

Then invert it: group connector rows **by mailbox**, so each mailbox is fetched once however many vaults declare it, and keep writing script rows **per vault**, since such a script writes into the vault it belongs to. A `fetch-script` row is a mailbox rather than a writer, so it groups with the connectors. Report the plan before acting: N vaults, N mailboxes, N script runs. **[references/gather.md](references/gather.md)** has the grouping rules and what an unreadable vault does to the plan.

A vault with no `## Triage sources` block contributes no sources. It stays a routing *destination*: an item can be routed to a vault that pulls nothing of its own.

### Step 2: Run the sync scripts

Run each script row from its own vault root. **Dry-run every one first, in both modes**; the volume gate in [references/gather.md](references/gather.md) decides which sources get `--write`.

These scripts dedupe against their own central ledgers, so running them is idempotent. **An error is recorded and skipped, never fatal.** Their output is not routed by this skill.

### Step 3: Fetch each mailbox once

Follow **[../para-shared/connectors.md](../para-shared/connectors.md)**, the same fetch protocol `/para-triage` uses: dispatch, query frame, thread normalisation, dedup, message list. Two differences:

- **The query frame is the union of every declaring vault's `Relevant when`**, not one vault's. Fetch once, route after. A per-vault query would refetch the same mailbox N times, which is the cost this layer exists to remove.
- **A connector this file's `allowed-tools` does not name is a setup step, not an absent mailbox.** The names there are the stable-server case; a harness that exposes the same connector under an account UUID (`mcp__<uuid>__search_threads`) is found by the shared file's tool-suffix rule and then refused, which looks identical to "not connected" and silently unroutes every vault it feeds. **Report it and carry on; never edit this file mid-run to widen your own permissions, and never let a refusal be reported as an absence.** The frontmatter carries a wildcard in the tool-name position for this reason, and the operator is the one who changes it if their harness still refuses. Editing a skill to grant itself a tool is outside the writes this skill is allowed (see Strict rules), and a run that quietly does it has made a permission decision nobody reviewed.
- **Dedup against this skill's own ledger**, plus the per-vault legacy ledgers named in [references/staging.md](references/staging.md). Stop at the end of step 6 of the shared file: its judgment steps are triage's, not this skill's. A thread the shared file hands back **resurfaced** has grown since it was dispositioned; route it from scratch and stage only what arrived after the watermark.

Window: **30 days in preview, 2 days in write mode, including the first write run.** It turns on the mode, not on whether a ledger exists yet, and the reasoning is worth keeping: a wide sample is how you tell whether a router works, and preview stages nothing, so breadth costs only the judgment on a run you chose to make. Write mode has no such licence. **Backfilling a month of a mailbox nobody was ingesting is not this layer's job** - that mail has already been dealt with or already been ignored, by a person, and switching on write mode must not be able to drop a month of history into several `triage/` folders at once. A deliberate backfill is `--days N` by hand, once.

#### The carry-over between the two windows

**The gap those two numbers leave is real, and it has to be named rather than left to be discovered.** Preview reaches 30 days and stages nothing; write reaches 2 and is the only thing that stages. Every thread a preview routed that is older than the write window falls between them: no later run fetches it again, so no ledger entry is ever made, and the preview's run log is the only trace it existed. None of this shows at the moment it happens - the first write run reports a clean small number, and the preview's work is simply gone. The failure is invisible in exactly the way the volume gate and the owner rule are: the run looks productive.

Two things close it, and both are **reporting, not staging**:

- **A preview run counts its own cliff.** Report, as its own line, how many routed threads are older than the write window: *"N of M routed threads are older than the 2-day write window and will not be staged when write mode is switched on."* That is the number the operator needs while deciding to switch on write mode, which is the one moment it is cheap to act on.
- **A write run reconciles against every preview since the last write, not the most recent one.** A single preview often covers only part of the fleet - one run for the connector mailboxes, another for the fetch-script ones - so the latest log alone is a partial view whose gaps read as zero. Collect every `mode: preview` log written after the last write run and reconcile the union of their routings. Any thread absent from this skill's ledger, absent from every legacy ledger, and outside the current window is **carry-over**: name it in the report with its mailbox and routed vaults, and give the exact `--days N` invocation that would recover it.

**Count carry-over by distinct thread id, never by decision record.** A log written by a run that failed to group messages into threads holds one decision per *message*, so counting records reports a number several times the real one - and reports it as a fleet-sized problem when it is a modest one. The grouping rule is in the shared fetch protocol, but the reconcile reads logs it did not write, so it defends itself rather than trusting them.

**The reconcile reads logs it did not write**, so the field it reads is a contract `references/staging.md` states and this step depends on: routing decisions are always under `decisions`. Accept any `decisions*` key from a log written before that rule, and say in the report that you did.

**Never let the reconcile stage anything by itself.** The reason write mode has a short window is that a person decides what a backfill drops into their vaults; a reconcile that quietly stages has made that decision for them, and it would do it on a scheduled run with nobody reading. Report, and stop.

Carry-over stays reported until it is resolved - by a recovery run, or by the operator judging it dead - and a run carrying it says so at the top of its report, beside the errors.

### Step 4: Route

For each fetched thread decide which registered vaults it belongs to. **Zero to many, not exactly one:** a thread can belong to two vaults, and most belong to none. **Rules, in order, and what to do with an ambiguous one: [references/routing.md](references/routing.md).**

The whole decision is *which vault*. Not urgency, not a drafted action, not a destination folder inside the vault.

### Step 5: Stage, ledger, log, report

In write mode: one note per routed thread into that vault's `triage/`, one ledger entry per thread whether routed or not, one run log. The single exception is a thread routed to a vault that could not be written, which gets **no** entry so the next run can deliver it. In preview: the run log only. **Note shape, ledger shape, run log shape and the idempotency rule: [references/staging.md](references/staging.md).**

Report as a table of vault, staged count and unrouted count, then name every source that errored, every carry-over thread Step 3 left outstanding, and every thread that routed to a vault it could not be delivered to. A run that staged nothing says so, rather than reporting nothing.

**An undelivered item belongs at the top of the report, beside the errors**, with the vault that is owed it. It is the one outcome that looks like success from every angle: the thread was fetched, judged and routed correctly, and the only thing that did not happen is the part the operator cares about.

## Strict rules

**Everything in [../para-shared/operating-discipline.md](../para-shared/operating-discipline.md) applies.** The rules specific to *this* skill:

- **The only writes are new `.md` files in a registered vault's `triage/`, plus this skill's own cache paths.** Nothing else, in any mode.
- **Never edit an `actions.md`, a brief, a README, or any existing file in any vault.** Not even to append. This skill creates files; it does not change them.
- **Never move, rename or delete anything in `triage/`**, including a note an earlier run of this skill staged. Removing it is the operator's call on their next `/para-triage`.
- **Mail is read-only.** No send, no reply, no archive, no label.
- **Decide which vault, never what to do.** A staged note carrying a proposed action has already made the judgment this skill exists not to make.
- **One source failing never aborts the run.** Record it, skip it, continue, name it in the report.
- **Never stage into an unregistered path, an inactive vault, or a vault whose path is not mounted.** A one-way mirror or a backup copy is not a vault: staging into one writes an item the next sync destroys, and the item is then routed nowhere with nothing left to show it was lost.
- **Never ledger a thread you could not deliver.** A thread routed to a vault whose path was not mounted gets no ledger entry, so the next run picks it up again; `by_message_id` is what stops the vaults that did receive it from receiving it twice. Ledgering it marks it handled forever, the vault that was down never gets it, and the only trace is a run log nobody re-reads. Full rule in [references/staging.md](references/staging.md).
- **Preview writes nothing at all.** Not a note, not a ledger entry, not a `--write` on a sync script. The run log is the only artefact.
- **The Step 3 reconcile reports carry-over and never stages it.** Reaching past the write window is `--days N`, typed by a person who has read the count. A scheduled run that silently recovers its own gap has removed the only thing limiting how much history can land in a `triage/` folder at once.
- **Never `--write` a sync script whose dry run came back over the volume gate**, whatever mode the run is in and however routine the source looks. The gate is the only check standing between an unfiltered inbox importer and every `triage/` folder it feeds.

## Edge cases

- **A registry path is not mounted** (a network drive, an unsynced client library): record an error row, route nothing to it, keep going. Never read "not mounted" as "no items".
- **A mailbox is declared but its connector is absent from the harness:** skip it, name it in the report, do not fail the run. The fetch protocol's tool-suffix rule is what tells absent from merely renamed.
- **A thread routes to two vaults:** stage it in both. It is one thread and two operators' business, and collapsing it to one vault silently loses it from the other.
- **A thread routes nowhere:** ledger it as unrouted and stage nothing. Unrouted is a normal outcome rather than a failure, but a *rising* unrouted count means the `Relevant when` rules need widening, not the router rewriting.
- **A thread routes to a vault whose path is not mounted:** stage into the vaults that are mounted, write **no** ledger entry, and report it under `undelivered`. It comes back on the next run and lands the moment the path does. Do not soften this into "routed nowhere": the routing was right and only the delivery failed, and recording it as unrouted loses that distinction exactly when it matters.

## Related skills

- `/para-triage` - the interactive half. It empties the `triage/` folder this skill fills, and skips its own connector and fetch-script pull in any vault the registry lists as active *provided* this skill has run recently.
