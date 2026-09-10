# Building the source plan (Steps 1 and 2)

Every active vault declares what it pulls in a `## Triage sources` block in its `CLAUDE.md`: a table with columns `Source | Type | Endpoint | Relevant when`. Per-vault, that block is a list of things to fetch. Read across all the vaults at once it is something else: **an index of which vaults care about which mailbox**, which is exactly what the router needs. Inverting it is Step 1's whole job.

## Reading each vault

For each active registry entry, read two things:

1. `CLAUDE.md`, for the `## Triage sources` block.
2. The root `README.md`, for its `## Operating model` section. Grep with context is enough. The block says what a vault *pulls*; the Operating model says what it *is*, and routing wants both. Missing section: skip it silently and route on `purpose` alone.

**A vault that cannot be read is an error row, not an absence.** No `CLAUDE.md`, unreadable file, malformed block: record it, do not pull for it, and keep it as a routing destination only if `purpose` is present. Report it in the summary. A vault silently dropped from the plan looks identical to a vault with nothing to say.

**A vault with no `## Triage sources` block contributes no sources and stays a destination.** This is normal and common: notes-only vaults and vaults nobody has wired a mailbox to still receive routed items.

## Inverting it

Four row types appear in the block. Handle them differently:

| `Type` | Grouping |
|---|---|
| `connector: <name>` | **By `Endpoint`.** One mailbox, however many vaults declare it, fetched once. Carry each declaring vault's `Relevant when` text with the group: that set is the router's candidate list for every thread the mailbox yields. |
| `fetch-script` | **By `Endpoint` mailbox, like a connector.** The script reads a mailbox that has no MCP connector and prints candidates without writing anything, so it belongs to the fetch in Step 3 rather than to the script runs here. Run it once per mailbox, not once per declaring vault. |
| `sync-script` | **Per vault.** The script writes into the vault it belongs to and is run from that vault's root. |
| `drive` | **Skipped.** A `drive` row is not an inbox; it is the lookup that lets `/para-triage` resolve a Google-native stub already sitting in `triage/`. It pulls nothing, so it contributes nothing here. |

Then say the plan out loud before acting on it: **N vaults, N mailboxes, N script runs**, with the error rows named. On a healthy fleet those three numbers barely move between runs, so a number that jumps is the cheapest possible signal that a vault changed its sources.

## Running the sync scripts

- Run each from **its own vault root**, resolving the path in the `Endpoint` cell relative to that root. `node` for `.js`, `py` or `python` for `.py`.
- **Always dry-run first, in both modes.** These scripts default to dry-run and report what they would add. That report is the input to the next rule, so there is no path where a script writes before its count has been read.
- They dedupe against their own ledgers outside the vault, so running one twice is harmless and running one after a manual invocation is harmless too.
- **An error is recorded and skipped.** An expired auth on one script must never cost the rest of the run, and the report names it rather than letting the run read clean.

**A `fetch-script` row is not subject to the volume gate below**, because the gate exists for scripts that write and this one cannot. Its candidates go through the router like connector mail, so volume costs judgment rather than files, and 800 unwanted messages become 800 unrouted decisions instead of 800 notes in someone's `triage/`.

### The volume gate: a script writes only if its dry run is small

**Script output bypasses the router entirely.** A sync script writes into `triage/` itself, so nothing this skill decides applies to what it puts there. That is correct for a script with a routing rule of its own, like a meeting sync that files by title prefix and reports the rest as unrouted. It is a hole for a script that imports an inbox wholesale, because such a script has no gate at all and this skill cannot add one.

The two kinds are indistinguishable from the manifest, and asking each vault to declare which it is would be a new configuration field that goes stale. Use the dry-run count instead, which measures the thing that actually matters:

> **In write mode, pass `--write` only to a source whose dry run would add 20 items or fewer to one vault. Above that, do not write. Report the count, name the source, and leave the import to a person.**

Twenty is not a tuned number. It is roughly where a count stops being something a person would scroll past and starts being something they would want to look at first, and the gate exists so that a human sees any such number before it lands rather than after.

**This is the one place an unattended run must be more cautious than a person.** Someone running a wholesale importer by hand reads the dry-run count and decides; a scheduled run has nobody to read it. The failure this prevents is not hypothetical: an inbox importer configured to match everything will report four figures on a busy mailbox, and filing that into a shared `triage/` costs more to undo than the whole layer saves.

- **Their output is not routed by this skill.** A sync script already knows where its items go, which is the whole reason it exists. Its files land as loose files in that vault's `triage/` and are the operator's on their next `/para-triage`.

**A script that fans out to sibling vaults** (some accept a flag to write every vault its own config routes to, not only its own) writes into those vaults directly. That is the script's business and not the router's. Where such a script exists, running the one copy that fans out is cheaper than running each vault's copy in turn, and the shared dedupe ledger makes it safe to do either.
