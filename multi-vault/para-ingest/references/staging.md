# Staging, ledger and run log (Step 5)

Three artefacts, in this order: the note into the vault, the ledger entry, the run log. **In preview mode only the run log is written**, and nothing else on this page happens.

## The staged note

One file per routed thread per vault, into `<vault>/triage/`. It follows the shape the sync-script integrations already write, so everything sitting in a `triage/` folder looks alike whatever put it there.

**Filename:** `YYYYMMDD <subject, filesystem-safe> <6 hex>.md`: the received date, the subject with the path-hostile characters `<>:"/\|?*` replaced by spaces and runs of whitespace collapsed, and **the first six characters of `sha1(threadId)`**.

That exact derivation, not merely *a* hash: it lets any later run **recompute a filename and look for it on disk**, the only check that survives a deleted ledger.

**A thread that resurfaces and stages again on the same day computes the same name.** Where the computed name already exists on disk, append ` 2`, then ` 3`, and look the stem up as a prefix glob in the places [the lookup on disk](#the-lookup-on-disk) names.

**Body:**

```markdown
# <subject>

- **Source:** <connector> (<mailbox>)
- **From:** <name> <<address>>
- **Received:** <ISO timestamp>
- **Routed:** <the reason from routing.md>
- **Content:** <what stands in for the message, and what was left out>
- **Link:** <permalink to the thread>

<snippet or body>
```

Two rules about the content:

- **Whatever stands in for the message is qualified in the note itself, on the `Content` line above the `Link` line.** A note holding a 200-character snippet must say so.
- **No proposed action, no classification, no urgency.** The note records what arrived and why it was routed here.

### A resurfaced thread stages a fresh note

A thread that grew past its watermark stages a **new note holding only the messages that arrived after it**, never an edit to the earlier note. Its `Routed` line names the earlier disposition, `resurfaced; previously <disposition> <date>, reason: <reason>`, and it is routed again from scratch.

## The ledger

One central ledger at `${PARAOS_HOME:-~/.paraos}/cache/ingest/ledger.json`, keyed by mailbox and then thread id:

```json
{
  "mailboxes": {
    "<mailbox>": {
      "<threadId>": {
        "routed": ["vault-a", "vault-b"],
        "reason": "contact: someone@example.com",
        "date": "YYYY-MM-DD",
        "subject": "...",
        "seen_through": "<dedup key of the newest message at disposition>",
        "seen_date": "<that message's received timestamp, ISO-8601 with offset>"
      }
    }
  },
  "by_message_id": {
    "<dedup key>": ["vault-a", "vault-b"]
  }
}
```

**`seen_date` is written and compared as an instant**, per [../../para-shared/connectors.md](../../para-shared/connectors.md) step 5, which also covers legacy entries. `date` is for a human reading the file and is never compared. The pair is required: where a provider yields no message identifier, `seen_through` takes the fallback key.

**Both `by_message_id` and `seen_through` key on the dedup key defined in step 6 of [../../para-shared/connectors.md](../../para-shared/connectors.md).** Keying `by_message_id` on the per-mailbox rung 3 turns off the cross-mailbox dedup it exists for, so report a run that fell to rung 3 as one whose cross-mailbox dedup was not working. **Never mix rungs for one message.**

### The two indexes

**Before staging a thread into a vault, check whether any message in it is already recorded against that vault in `by_message_id`, and skip that pair if it is.** Record every staged message's key there afterwards. It deduplicates per vault, not globally.

- **Every fetched thread gets an entry**, routed or not, except under the rule directly below.
- **A thread routed to a vault that could not be written gets no entry at all.** Not a partial entry, not an entry naming the vaults that did get it. If any vault in the routing decision was unreachable (its registry path not mounted, its `triage/` not writable), withhold the per-mailbox entry and let the thread be refetched next run. Record `by_message_id` for every message actually staged, always. Report these in the run log as **`undelivered`**.
- **Stage from the best-grouped copy of a conversation.** Where the dedup keys show two mailboxes carrying the same messages, stage from the copy with the most messages in it and let `by_message_id` suppress the rest. Name the suppressed threads in the run log.
- **Honour the pre-existing per-vault ledgers.** Before the first write run, read any legacy per-vault triage ledgers under `${PARAOS_HOME:-~/.paraos}/cache/` and treat a thread already dispositioned there as already handled for that vault.
- **Missing file or directory: create them.** It is a cache, not a system of record.
- **A ledgered thread resurfaces when it grows past its watermark**, and only then; step 5 of [../../para-shared/connectors.md](../../para-shared/connectors.md) does the comparison. Write the note first, ledger second.
- **Update the watermark on every disposition, including an unrouted one.** What advances is the watermark, never the `routed` list.

### Undelivered is re-checked, never carried

Every run collects the `undelivered` records from every run log since the last one whose `undelivered` was empty, treats them as **candidates, not facts**, and settles each against current state:

1. **The ledger.** A per-mailbox entry for the thread now exists. The entry is withheld until every routed vault was written, so its presence means delivered.
2. **`by_message_id`.** Every message of the thread is recorded against a vault the record said was owed: delivered to that vault.
3. **Disk.** The note is present in the owed vault, per the lookup below: delivered to that vault. **Absence proves nothing**: `/para-triage` may have filed the note already, and a note staged from another mailbox's better-grouped copy carries that thread's hash.

A candidate a check settles is reported once under **`resolved`** and dropped from every later run. One no check settles stays under `undelivered`, described from this run's checks, never from an older log's account. A thread still owed and now older than the write window is reported with the `--days N` that recovers it, as carry-over is.

**Recovery is never a ledger deletion.** A genuinely undelivered thread has no entry, and deleting one that exists re-stages a thread its vaults already hold.

### The lookup on disk

Recompute the note's stem and look for `<vault>/triage/<stem>*.md`, covering [collected copies](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery) on the read-only iPad delivery: `<vault>/triage/<stem>*.pdf` and `<vault>/resources/mds/triage__<stem>*.md`.

## The run log

One file per run at `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/YYYYMMDD-HHMMSS.json`, holding the mode, the source plan, every routing decision with its reason, every error, and the per-vault staged and unrouted counts.

It is written in **both** modes, and in preview it is the only thing written. Watch it for **the same thread routing to different vaults on different runs**: an ambiguous rule to tighten before write mode is switched on.

**Read these logs, and the ledger above, with `encoding="utf-8"`**, per [../../para-shared/connectors.md](../../para-shared/connectors.md).

### Fields the skill's reconciles read

Full records, never a count, each carrying mailbox, thread id, subject and routed vaults:

- A `mode: preview` log records **`outside_write_window`**: every thread it routed whose newest message is older than the write window.
- A `mode: write` log records **`carry_over`**: what the Step 3 reconcile found still unresolved, plus the `--days N` invocation that would recover it.
- Either mode records **`undelivered`**: every thread routed to a vault that could not be written, with the vaults that received it and the vaults still owed it.
- Either mode records **`resolved`**: every earlier `undelivered` candidate this run found delivered, with the vault and the check that settled it.

**Every routing decision goes in `decisions`, always under that name**, however much of the fleet the run covered; `source_plan` says what it covered.

## Idempotency

A second write run immediately after a first stages **zero**, provided no mail arrived in between: run it by hand once. A genuine reply landing between the two runs makes the second stage one, and that is the watermark working.

The sync scripts dedupe against their own ledgers and the fetch against this one, so nothing in this skill depends on being run at a particular time or exactly once.
