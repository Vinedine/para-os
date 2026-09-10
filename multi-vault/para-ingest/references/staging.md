# Staging, ledger and run log (Step 5)

Three artefacts, in this order: the note into the vault, the ledger entry, the run log. **In preview mode only the run log is written**, and nothing else on this page happens.

## The staged note

One file per routed thread per vault, into `<vault>/triage/`. It follows the shape the sync-script integrations already write, so everything sitting in a `triage/` folder looks alike whatever put it there.

**Filename:** `YYYYMMDD <subject, filesystem-safe> <6 hex>.md`: the received date, the subject with the path-hostile characters `<>:"/\|?*` replaced by spaces and runs of whitespace collapsed, and **the first six characters of `sha1(threadId)`**.

That exact derivation, not merely *a* hash. The hash keeps two threads with the same subject on the same day from colliding; pinning how it is computed is what additionally lets any later run **recompute a filename and look for it on disk**, which is the only check that survives a deleted ledger. Left as "some hash" it drifts silently and immediately: three notes staged inside one 24-hour period were found using `md5(threadId)`, `sha1(threadId)`, and a third derivation matching neither, which makes the six characters decoration rather than an identifier.

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

- **Whatever stands in for the message is qualified in the note itself, above the `Link` line.** A note holding a 200-character snippet must say so, because the ledger entry written straight after means no later run revisits this thread: the reader of this file is the last person who can act on it, and an unmarked snippet reads as the whole message. Above the link, because everything below it reads as the message. **The key is `Content`**, every time - as `Body:` in one note and `Content below:` in the next it stops being greppable across a fleet, which is the only way anyone checks whether the qualifier is being written at all.
- **No proposed action, no classification, no urgency.** The note records what arrived and why it was routed here. Anything more has made triage's decision for it.

### A resurfaced thread stages a fresh note

A thread that grew past its watermark stages a **new note holding only the messages that arrived after it** - not an edit to the earlier note, and not silence.

- **A fresh note, because the note is what carries the content.** Suppressing it on the grounds that this thread already reached this vault reproduces the defect the watermark closes: the vault would hold a record that the thread exists and never the thing that arrived on it.
- **Only the messages past the watermark**, which needs no new mechanism. `by_message_id` already refuses to stage a message into a vault it has reached before, so re-staging the whole thread would be caught message by message anyway. Cutting at the watermark reaches the same result more cheaply and produces a note someone can read, rather than one that is mostly duplicate.
- **Name the earlier disposition on the `Routed` line**: `resurfaced; previously <disposition> <date>, reason: <reason>`. This matters most in the case that goes wrong most - a thread dismissed on thin evidence, whose new messages are the ones that would say what it was, reads as an ordinary fresh arrival unless the note says otherwise.
- **Route it again from scratch.** The earlier reason is context for the reader and never an input: a thread that routed nowhere on a bare subject line may route somewhere on its third message, which is the whole reason for letting it back through. Re-deriving the answer is cheap; inheriting it would make the first judgment permanent by another route.

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
        "seen_through": "<RFC822 Message-ID of the newest message at disposition>",
        "seen_date": "<that message's received timestamp>"
      }
    }
  },
  "by_message_id": {
    "<RFC822 Message-ID>": ["vault-a", "vault-b"]
  }
}
```

### Why there are two indexes

The per-mailbox one answers "have I seen this thread here". It cannot answer **"is this the same message I already staged from a different mailbox"**, and that case is common rather than exotic: one message addressed to two of the registered mailboxes, or sent to a group both are in, arrives as two thread ids in two mailboxes with no shared key between them. Keyed only by mailbox and thread, the ledger stages it twice into the same vault and has no way to notice.

So keep a second index on the RFC822 `Message-ID` header, which is stable across mailboxes for one message and comes back with the metadata you already fetch. **Before staging a thread into a vault, check whether any message in it is already recorded against that vault in `by_message_id`, and skip that pair if it is.** Record every staged message's id there afterwards.

It deduplicates per vault, not globally: the same message genuinely routed to two vaults still stages in both, which is the multi-routing rule doing its job. What it stops is the same message reaching one vault twice because it came in through two front doors.

- **Every fetched thread gets an entry**, routed or not. An unrouted thread with no entry is refetched and re-judged on every run forever, which is the cost this layer was built to remove.
- **Honour the pre-existing per-vault ledgers.** Before the first write run, read any legacy per-vault triage ledgers under `${PARAOS_HOME:-~/.paraos}/cache/` and treat a thread already dispositioned there as already handled for that vault. Skipping this re-stages, into a shared folder, everything the operator already dealt with one vault at a time, which is the single worst first impression this layer can make.
- **Missing file or directory: create them.** It is a cache, not a system of record. Deleting it means threads resurface, not that anything is lost.
- **A ledgered thread resurfaces when it grows past its watermark**, and only then. The entry records `seen_through` and `seen_date` for the newest message it was dispositioned on, and step 5 of [../../para-shared/connectors.md](../../para-shared/connectors.md) does the comparison; this file's job is to write the pair. An entry is still written only once the note is actually on disk. Write the note first, ledger second: the reverse order loses an item silently if the write fails, while this order at worst stages one thing twice.
- **Update the watermark on every disposition, including an unrouted one.** A thread judged and not routed still advances `seen_through`, or the same messages are re-judged every run forever, which is the cost this layer was built to remove. What advances is the watermark, never the `routed` list.

## The run log

One file per run at `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/YYYYMMDD-HHMMSS.json`, holding the mode, the source plan, every routing decision with its reason, every error, and the per-vault staged and unrouted counts.

It is written in **both** modes, and in preview it is the only thing written. It exists to be read: the preview week is a week of reading these, and the thing to watch for is **the same thread routing to different vaults on different runs**, which means an ambiguous rule to tighten before write mode is ever switched on.

### Two fields the window reconcile needs

The carry-over reconcile in Step 3 of the skill reads these logs rather than a person, so the numbers it needs have to be **in them as data**:

- A `mode: preview` log records **`outside_write_window`**: every thread it routed whose newest message is older than the write window. Full records, not a count - mailbox, thread id, subject, routed vaults - because the next write run reads them to work out what it is missing.
- A `mode: write` log records **`carry_over`**: what the reconcile found still unresolved, in the same shape, plus the `--days N` invocation that would recover it.

A count alone is useless here: it tells the operator a number they can do nothing with, and tells the next run nothing at all. The whole point of writing the routing decision down is that a run which stages nothing has still produced something the next one can act on.

**Every routing decision goes in `decisions`, always under that name.** A run covering only part of the fleet still writes `decisions`; what it covered is `source_plan`'s job to say. Renaming the array after its scope - `decisions_fetch_script_mailboxes` and the like - hides it from the reconcile that reads these logs, which then finds nothing and reports a clean pass. A log is not a report to a person, it is an input to the next run, and an input whose field names vary is one nobody can read without knowing what wrote it.

## Idempotency

A second write run immediately after a first stages **zero**, provided no mail arrived in between. That is the check that proves the ledger works, and it is worth running by hand once rather than assuming. State the proviso when reporting the result: under the watermark rule a genuine reply landing between the two runs makes the second run stage one, and that is the fix working rather than the ledger failing.

Everything upstream is idempotent by the same means: the sync scripts dedupe against their own ledgers, the fetch dedupes against this one. Nothing in this skill depends on being run at a particular time or exactly once.
