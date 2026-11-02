# Staging, ledger and run log (Step 5)

`scripts/stage.py` writes the notes into each routed vault's `triage/`, the central ledger, then the run log; in preview, the log alone.

## The ledger

`${PARAOS_HOME:-~/.paraos}/cache/ingest/ledger.json`. **Recovery is never a ledger deletion**: a genuinely undelivered thread has no entry, and deleting one that exists re-stages a thread its vaults already hold.

## Idempotency

A second write run straight after a first stages **zero**, provided no mail arrived in between; a reply that did arrive stages one, and that is the watermark working.
