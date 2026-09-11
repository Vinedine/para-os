# Staging, ledger and run log (Step 5)

Three artefacts, in this order: the note into the vault, the ledger entry, the run log. **In preview mode only the run log is written**, and nothing else on this page happens.

## The staged note

One file per routed thread per vault, into `<vault>/triage/`. It follows the shape the sync-script integrations already write, so everything sitting in a `triage/` folder looks alike whatever put it there.

**Filename:** `YYYYMMDD <subject, filesystem-safe> <6 hex>.md`: the received date, the subject with the path-hostile characters `<>:"/\|?*` replaced by spaces and runs of whitespace collapsed, and **the first six characters of `sha1(threadId)`**.

That exact derivation, not merely *a* hash. The hash keeps two threads with the same subject on the same day from colliding; pinning how it is computed is what additionally lets any later run **recompute a filename and look for it on disk**, which is the only check that survives a deleted ledger. Left as "some hash" it drifts, and the six characters become decoration rather than an identifier.

**What it does not separate is two notes from one thread, and under the watermark rule below a thread can stage twice.** `sha1(threadId)` is constant per thread, so a thread that resurfaces and stages again on the same day computes the same name and the second note overwrites the first. Where the computed name already exists on disk, append ` 2`, then ` 3`. A fix that silently loses a note would be the same class of defect as the one it closes. Recomputation survives it: look for the stem as a prefix glob, `YYYYMMDD <subject> <6 hex>*.md`, rather than as an exact name.

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

- **Whatever stands in for the message is qualified in the note itself, above the `Link` line.** A note holding a 200-character snippet must say so. Above the link, because everything below it reads as the message. **The key is `Content`**, every time.
- **No proposed action, no classification, no urgency.** The note records what arrived and why it was routed here.

### A resurfaced thread stages a fresh note

A thread that grew past its watermark stages a **new note holding only the messages that arrived after it** - not an edit to the earlier note, and not silence.

- **A fresh note.**
- **Only the messages past the watermark.** `by_message_id` already refuses to stage a message into a vault it has reached before, so re-staging the whole thread would be caught message by message anyway.
- **Name the earlier disposition on the `Routed` line**: `resurfaced; previously <disposition> <date>, reason: <reason>`.
- **Route it again from scratch.**

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

### `seen_date` is an instant, and `date` is only for a human reading the file

**`seen_date` is written and compared as an instant**, per [../../para-shared/connectors.md](../../para-shared/connectors.md) step 5, which also covers legacy entries. `date` is a display convenience derived from it and is never compared.

Where a provider genuinely yields no message identifier, `seen_through` takes the fallback key below rather than being omitted; the pair is required (same file).

### The dedup key is the shared one

Both `by_message_id` and `seen_through` key on the **dedup key defined in step 6 of [../../para-shared/connectors.md](../../para-shared/connectors.md)**; the ladder is not restated here.

What matters for *this* index is the consequence of the last rung. `by_message_id` exists to catch one message arriving in two mailboxes, so keying it on a per-mailbox provider id turns it off for exactly the case it was built for, without shrinking it or raising anything. Prefer rung 1, take rung 2 wherever rung 1 is missing, and treat a run that fell to rung 3 as a run whose cross-mailbox dedup was not working.

**Never mix rungs for one message.** An identifier computed two ways identifies nothing, and the failure is invisible because both halves look like valid keys.

### The two indexes

Keep a second index on the RFC822 `Message-ID` header. **Before staging a thread into a vault, check whether any message in it is already recorded against that vault in `by_message_id`, and skip that pair if it is.** Record every staged message's id there afterwards.

It deduplicates per vault, not globally.

- **Every fetched thread gets an entry**, routed or not, *unless* delivery to one of its routed vaults was blocked. An unrouted thread with no entry is refetched and re-judged on every run forever. The one exception is the rule directly below.
- **A thread routed to a vault that could not be written gets no entry at all.** Not a partial entry, not an entry naming the vaults that did get it. If any vault in the routing decision was unreachable (its registry path not mounted, its `triage/` not writable), withhold the per-mailbox entry entirely and let the thread be refetched next run. Record `by_message_id` for every message actually staged, always. Report these in the run log as **`undelivered`**, in the same shape as `carry_over`: mailbox, thread id, subject, the vaults that received it, and the vaults still owed it. A run carrying `undelivered` says so at the top of its report, beside the errors.
- **Stage from the best-grouped copy of a conversation.** Where the dedup keys show two mailboxes carrying the same messages, stage from the copy with the most messages in it and let `by_message_id` suppress the rest. Name the suppressed threads in the run log.
- **Honour the pre-existing per-vault ledgers.** Before the first write run, read any legacy per-vault triage ledgers under `${PARAOS_HOME:-~/.paraos}/cache/` and treat a thread already dispositioned there as already handled for that vault.
- **Missing file or directory: create them.** It is a cache, not a system of record.
- **A ledgered thread resurfaces when it grows past its watermark**, and only then. The entry records `seen_through` and `seen_date` for the newest message it was dispositioned on, and step 5 of [../../para-shared/connectors.md](../../para-shared/connectors.md) does the comparison; this file's job is to write the pair. An entry is still written only once the note is actually on disk. Write the note first, ledger second.
- **Update the watermark on every disposition, including an unrouted one.** What advances is the watermark, never the `routed` list.

## The run log

One file per run at `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/YYYYMMDD-HHMMSS.json`, holding the mode, the source plan, every routing decision with its reason, every error, and the per-vault staged and unrouted counts.

It is written in **both** modes, and in preview it is the only thing written. It exists to be read: the preview week is a week of reading these, and the thing to watch for is **the same thread routing to different vaults on different runs**, which means an ambiguous rule to tighten before write mode is ever switched on.

**Read these logs, and the ledger above, with `encoding="utf-8"`**, per [../../para-shared/connectors.md](../../para-shared/connectors.md).

### Two fields the window reconcile needs

The carry-over reconcile in Step 3 of the skill reads these logs rather than a person, so the numbers it needs have to be **in them as data**:

- A `mode: preview` log records **`outside_write_window`**: every thread it routed whose newest message is older than the write window. Full records, not a count - mailbox, thread id, subject, routed vaults.
- A `mode: write` log records **`carry_over`**: what the reconcile found still unresolved, in the same shape, plus the `--days N` invocation that would recover it.
- Either mode records **`undelivered`**: every thread routed to a vault that could not be written, in the same shape again, with the vaults that received it and the vaults still owed it.

A count alone is useless here.

**Every routing decision goes in `decisions`, always under that name.** A run covering only part of the fleet still writes `decisions`; what it covered is `source_plan`'s job to say. Renaming the array after its scope - `decisions_fetch_script_mailboxes` and the like - hides it from the reconcile that reads these logs.

## Idempotency

A second write run immediately after a first stages **zero**, provided no mail arrived in between. That is the check that proves the ledger works, and it is worth running by hand once rather than assuming. State the proviso when reporting the result: under the watermark rule a genuine reply landing between the two runs makes the second run stage one, and that is the fix working rather than the ledger failing.

Everything upstream is idempotent by the same means: the sync scripts dedupe against their own ledgers, the fetch dedupes against this one. Nothing in this skill depends on being run at a particular time or exactly once.
