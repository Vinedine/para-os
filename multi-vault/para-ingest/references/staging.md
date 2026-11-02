# Staging, ledger and run log (Step 5)

`scripts/stage.py` writes the notes into each routed vault's `triage/`, the central ledger, then the run log; in preview, the log alone. Its output names the log, the counts per vault and mailbox, and every `undelivered`, `resolved`, `carry_over` and `suppressed` thread, which is what the report is built from.

## The ledger

`${PARAOS_HOME:-~/.paraos}/cache/ingest/ledger.json`, written only by `stage.py`. A thread is ledgered once every vault it routed to was written, its watermark the newest message staged. **Recovery is never a ledger deletion**: a genuinely undelivered thread has no entry, and deleting one that exists re-stages a thread its vaults already hold.

## The run log

One file per run under `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/`, in both modes. Watch it for **the same thread routing to different vaults on different runs**: an ambiguous rule to tighten. A vault's `/para-triage` reads the newest write log to see whether ingest already pulled its mailboxes and ran its sync scripts, and the next write run reads it for where each mailbox's window starts.

## Idempotency

A second write run straight after a first stages **zero**, provided no mail arrived in between; a reply that did arrive stages one, and that is the watermark working.
