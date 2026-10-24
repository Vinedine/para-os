# Staging, ledger and run log (Step 5)

**`scripts/stage.py` writes all three**: the notes into each routed vault's `triage/`, the central ledger, then the run log. Write the run to one JSON file outside every vault, in the shape its docstring gives (`--help` prints it), and run `stage.py <run.json>` once ([launcher](../../para-shared/scripts.md)). In preview it writes the log alone. Exit 2 refuses the input before anything is written: fix what it names and run it again. Its output names the log, the counts per vault and mailbox, and every `undelivered` and `suppressed` thread, which is what the report is built from.

What only the run can supply:

- **Every fetched thread, routed or not**, each with its reason. A sign-in or security code is passed with only what keys it ([connectors.md](../../para-shared/connectors.md#sign-in-and-security-codes)).
- **What stands in for each message, said truthfully**: `text` is `preview` unless the source gave the whole body, and `own_messages` is false unless the operator's own messages were fetched. The note's `Content` line is built from them, and `/para-triage` re-reads at source on it.
- **A reason that says why the thread was routed here**, never what to do: no proposed action, classification or urgency.
- **What Steps 1 to 3 found**, copied into the log as given: `source_plan.declaring_vaults` (mailbox to the vault names declaring it); `sync_runs`, one `{"vault", "script", "written", "error"}` per script run, which that vault's triage does not re-run inside the window; `errors`, each naming its mailbox or script; and `carry_over` and `resolved` as full records, never counts, each with mailbox, thread id, subject and routed vaults, `carry_over` adding the `--days N` that recovers it and `resolved` the vault and the check that settled it.

## The ledger

`${PARAOS_HOME:-~/.paraos}/cache/ingest/ledger.json`, written only by the script and read as UTF-8. **Honour the pre-existing per-vault ledgers**: before the first write run, read any legacy per-vault triage ledgers under `${PARAOS_HOME:-~/.paraos}/cache/` and treat a thread already dispositioned there as already handled for that vault.

### Undelivered is re-checked, never carried

Every run collects the `undelivered` records from every run log since the last one whose `undelivered` was empty, treats them as **candidates, not facts**, and settles each against current state:

1. **The ledger.** A per-mailbox entry for the thread now exists. The entry is withheld until every routed vault was written, so its presence means delivered.
2. **`by_message_id`.** Every one of the record's `keys` is recorded against a vault it says was owed: delivered to that vault.
3. **Disk.** A note named for the thread's hash (`paraos_mail.thread_hash`) is in the owed vault's `triage/`: delivered to that vault. **Absence proves nothing**: `/para-triage` may have filed the note already, and a note staged from another mailbox's better-grouped copy carries that thread's hash.

A candidate a check settles is reported once under **`resolved`** and dropped from every later run. One no check settles stays under `undelivered`, described from this run's checks, never from an older log's account. A thread still owed and now older than the write window is reported with the `--days N` that recovers it, as carry-over is.

**Recovery is never a ledger deletion.** A genuinely undelivered thread has no entry, and deleting one that exists re-stages a thread its vaults already hold.

## The run log

One file per run under `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/`, in **both** modes, read as UTF-8. Watch it for **the same thread routing to different vaults on different runs**: an ambiguous rule to tighten before write mode is switched on. A vault's `/para-triage` decides from the newest write log whether ingest already pulled its mailboxes and ran its sync scripts.

## Idempotency

A second write run immediately after a first stages **zero**, provided no mail arrived in between: run it by hand once. A genuine reply landing between the two runs makes the second stage one, and that is the watermark working.
