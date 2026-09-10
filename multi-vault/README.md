# multi-vault - the cross-vault ingest layer

An **optional module**, not part of the base skeleton. Most people run one vault and need none of this.

It is for the case where you run several vaults and they draw on the same inputs. Per vault the design works: each declares its own sources in its own `## Triage sources` block and `/para-triage` pulls them. Across vaults it stops working, because the inbox is not vault-shaped. One mailbox declared by six vaults is fetched six times, a thread belonging to the seventh is dismissed six times without being recorded anywhere, and the knowledge of which vault a given item belongs to lives nowhere except in your head.

This layer puts that knowledge in one place and reads each source once.

## What it does

`/para-ingest` reads every registered vault's declared sources, decides **only** which vault each item belongs to, stages a note in that vault's `triage/`, and stops.

That boundary is the whole design. It never classifies an item, drafts an action, files anything into a project, or touches a mailbox. Every judgment about what an item *means* stays with `/para-triage`, in the vault the item landed in, with you present. A wrong routing call costs one misfiled note in a folder that exists to hold unprocessed things; a wrong filing call costs an edit inside a vault.

**Only the index is central.** The registry knows that your vaults exist and one line about what each is for. It never holds their contents, and no vault ever learns another vault's contents, so whatever separation you keep between them survives.

## What it does not do

- It does not reduce the number of vaults you sit down with. It removes duplicated reading and the routing decision, which is a different saving, and it will make some `triage/` folders fuller than they were, because items that previously surfaced nowhere now land somewhere.
- It does not give you one view across your vaults. That is a separate thing and this module does not ship it.
- It does not run unattended out of the box. See the preview week below.

## Installing

1. **Create the registry.** Copy `vaults.json.template` to `${PARAOS_HOME:-~/.paraos}/vaults.json` and fill in one entry per vault. The `purpose` line is the field that does the work: it is what an item's subject is judged against when nothing else decides. `registry.md` in the skill's references explains the rest of the schema.
2. **Install the skill.** Copy `para-ingest/` next to your other `para-*` skills, wherever those live for you. It reads `para-shared/connectors.md` from beside itself, so `para-shared/` has to be installed too; if you run any other `para-*` skill it already is.
3. **Run it by hand, in preview, and read the run log.** Do this before anything else.

## The three kinds of source, and why it matters here

A vault's `## Triage sources` block declares three kinds of thing, and this layer treats them very differently. The distinction is not bookkeeping: it decides whether an item is judged before it lands or after.

| Kind | What it is | What this layer does with it |
|---|---|---|
| `connector: <name>` | a mailbox read over MCP | fetched **once per mailbox**, however many vaults declare it, then routed |
| `fetch-script` | a mailbox with no connector, read by a script that prints candidates and writes nothing | the same: **once per mailbox**, then routed. A mailbox, not a writer |
| `sync-script` | a script that writes into `triage/` itself | run per vault, and **not routed**, because the script already knows where its items go |

**The last row is the one to be careful about.** A sync script writes straight into `triage/`, so nothing this layer decides applies to what it puts there. That is right for a script with a routing rule of its own, like a meeting sync that files by title prefix. It is a hole for one that imports an inbox wholesale, because such a script has no gate at all and the layer cannot add one.

So there is a **volume gate**: every script is dry-run first, in both modes, and only a source whose dry run would add **20 items or fewer to one vault** is ever passed `--write`. Above that the count is reported and the import is left to a person. Someone running an importer by hand reads that count and decides; a scheduled run has nobody to read it, and this is the one place an unattended run has to be more cautious than a person.

If you are wiring up a mailbox that has no MCP connector, prefer a `fetch-script` over a `sync-script`. Reading costs the same either way, and only one of them lets you be wrong for free.

## How `/para-triage` reacts

It notices, and no vault needs editing for it to. When the registry lists a vault root as `active`, `/para-triage` in that vault skips its own source pull, because this layer has already staged those sources as loose files there. It reports when the layer last staged, so a layer that has stopped running shows up as a date rather than as a quiet `triage/` folder.

On a machine with no registry, or for a vault not in it, `/para-triage` pulls its own sources exactly as it always did. That fallback is automatic and is why the check is a registry lookup rather than a marker written into each vault.

## The preview week

**Run in preview for a week before switching to write mode.** This is not caution for its own sake. A mis-routed email costs a dismissal; a router quietly wrong for a month erodes your trust in every vault it has been writing to, and that is not recoverable by fixing the router.

Two things to look for in the run logs. The first is the same thread routing to **different vaults on different runs**, which means an ambiguous `Relevant when` rule to tighten before anything writes. A thread reappearing every run is expected, since preview ledgers nothing.

The second is **a vault whose routed count looks too good**. On the first real run of this layer one vault matched a hundred items and every single one was wrong: the router was matching the mailbox owner's own address, which sits in the contact files of every vault its owner works in, so it matched most of the mailbox at once. A rule keyed on who someone is will do this by default, and it does not look like a bug, it looks like a productive run. `/para-ingest` excludes the owner now; the general lesson is that a suspiciously strong result deserves the same look as an empty one.

Then run `write` by hand once, immediately run it again to confirm it stages zero the second time, and only then consider scheduling it.

**The switch itself drops things, and this is the moment to decide about them.** Preview reaches back thirty days; write reaches back two. Everything a preview routed that is older than two days therefore never gets staged and never gets ledgered either, because no write run will fetch it again - the preview log is the only record it existed. On a real fleet this was not a rounding error: the last preview before the switch routed 32 threads, the first write run staged 5, and 10 of the remainder were in no ledger of any kind and stayed invisible until someone went looking for one specific email a day later.

So a preview run tells you how many of its routed threads are about to fall off that cliff, and a write run reports what it finds still outstanding as **carry-over**, with the `--days N` command that would recover it. Neither ever stages the backfill for you: reaching past the write window stays a thing a person types, because that is the only limit on how much history can land in a `triage/` folder at once. Run it, or decide the mail is already dealt with - but decide, rather than finding out later.

## What it writes

| Path | What |
|---|---|
| `<vault>/triage/*.md` | The staged notes. New files only, in registered vaults only. |
| `${PARAOS_HOME:-~/.paraos}/cache/ingest/ledger.json` | What has been seen, so nothing is fetched or judged twice. |
| `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/*.json` | One log per run, in both modes. |

Nothing else, in any mode. It never edits an existing file anywhere, and it never moves or deletes anything in a `triage/` folder, including its own notes.

## Known limits

- **A script that writes still runs per vault copy.** A mailbox does not: both connector and `fetch-script` sources are read once however many vaults declare them, which is the saving this layer exists for. Consolidating the writers is a change to those scripts, not to this layer.
- **It runs while your client is open.** Reading a mailbox is one thing, judging what is in it is another, and the second needs a model. So this is a routine you run, not a daemon.
- **A mailbox with no server-side categories is noisier.** Gmail applies its promotions and social filters before you see anything; Graph has no equivalent, so a `fetch-script` mailbox arrives raw. What the script can cut mechanically it does, on the RFC 2369 `List-Unsubscribe` header and nothing else - a noreply-style sender name is the one exclusion the fetch protocol forbids by default, since the transactional mail a vault most wants comes from exactly there. Measured on a live personal inbox that is 3005 messages down to 619 over thirty days, and 177 down to 18 over two. This is why the window turns on the mode: preview reaches back thirty days because breadth is how you judge a router and nothing is written, while write mode reaches back two whatever the state of the ledger, because a wide first *write* would reach back furthest exactly where it can filter least.
