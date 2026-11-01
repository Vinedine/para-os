# Staging, ledger and run log (Step 5)

`scripts/stage.py` writes the notes into each routed vault's `triage/`, the central ledger, then the run log; in preview, the log alone. Its output names the log, the counts per vault and mailbox, and every `undelivered` and `suppressed` thread, which is what the report is built from.

## The ledger

`${PARAOS_HOME:-~/.paraos}/cache/ingest/ledger.json`, written only by `stage.py`. A thread is ledgered once every vault it routed to was written, its watermark the newest message staged. **Recovery is never a ledger deletion**: a genuinely undelivered thread has no entry, and deleting one that exists re-stages a thread its vaults already hold.

## Undelivered is re-checked, never carried

Collect the `undelivered` records from every run log since the last one whose `undelivered` was empty, as **candidates, not facts**, and settle each against current state:

1. **The ledger** holds an entry for the thread: delivered, since the entry waits for every routed vault.
2. **`by_message_id`** records every one of the record's `keys` against an owed vault: delivered to that vault.
3. **Disk**: a note named for the thread's hash (`paraos_mail.thread_hash`) is in the owed vault's `triage/`. **Absence proves nothing**: `/para-triage` may have filed it already.

A candidate a check settles is reported once under **`resolved`** and dropped from later runs. One no check settles stays under `undelivered`, described from this run's checks; once older than the write window it is reported with the `--days N` that recovers it.

## Carry-over between the two windows

A thread a preview routed that is older than the write window is never fetched again by a write run, so nothing would ever stage it. Report it; never stage it.

- **A preview counts its own cliff** from `stage.py`'s `outside_write_window`: *"N of M routed threads are older than the 2-day write window and will not be staged when write mode is switched on."*
- **A write run reconciles every preview log since the last write**, not only the newest, since one preview often covers part of the fleet. A thread their `decisions` routed, absent from the ledger and outside the current window, is **carry-over**: name its mailbox and routed vaults, and give the `--days N` that recovers it. Count by distinct thread id, never by record; accept an older log's `decisions*` key and say so.

Carry-over stays reported, at the top, until a recovery run or the operator settles it. Write `carry_over` and `resolved` as full records into `run.json` before staging, so the log keeps them.

## The run log

One file per run under `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/`, in both modes. Watch it for **the same thread routing to different vaults on different runs**: an ambiguous rule to tighten. A vault's `/para-triage` reads the newest write log to see whether ingest already pulled its mailboxes and ran its sync scripts.

## Idempotency

A second write run straight after a first stages **zero**, provided no mail arrived in between; a reply that did arrive stages one, and that is the watermark working.
