# Configured triage sources (Step 2)

**The scan's `plan` decides each `## Triage sources` row**: `pull` and `run` execute below; `sent` runs only [the sent pass](../../para-shared/connectors.md); `skip`, `lookup` and `unknown` pull nothing. The summary carries `ingest.reason` unless it reads `pulled as normal`. A row carrying `pulled by <name>`, a writer on the roster, is read only on that writer's runs; anyone else's says `<source>: pulled by <name> - skipped`. What a source pulls flows on as loose files.

## sync-script sources

A script writing items into `triage/` (`granola.js`), dry-run by default: run it from the vault root with `--write`, or on `preview` without it, listing what it would add. An error is reported and the other sources carry on.

## fetch-script sources

A mailbox read by a script that prints candidates: `<script> fetch`, with the row's `--days N`, and `--sent` where it declares the sent pass, then judged as a connector thread. **Never pass `--write` or any other writing flag**: that files mail unjudged.

## connector sources

A `recording` row is read per [connectors.md](../../para-shared/connectors.md#recording), each item judged as a staged note. A mailbox is fetched per [connectors.md](../../para-shared/connectors.md#mail), then judged thread by thread:

1. **Another vault's business**, by the root README's `## Operating model`, is **Dismiss (other vault)**.
2. **Read the operator's own messages** from the true message list (connectors.md step 6); where that call could not run, surface the thread instead. One next step, a promise before a wait:
   - **A dated promise**: any message the operator wrote committing to a date or weekday ("price to you Wednesday") that no later message shows kept, whoever wrote last. **Update existing** where a tracked item covers it, else **Add action** dated `📅` on that day, quoting the sentence and when it was sent. A weekday is the first after the message's own date: `paraos_vault.py weekday-after <date> <weekday>` ([shared library](../../para-shared/scripts.md)), the day in English.
   - **An unanswered message**: the newest is the operator's own and asks something of the other side. Once `threads[].unanswered.waiting`, it is **Add action** with `Waiting on [<person>](<card>): <what> (since <the sent date>)`, no `📅`, or **Update existing** where a tracked item covers it. Before that, a fetched thread is neither asked nor ledgered.
   - **Neither**: the operator wrote last and nothing is left for them to do: **Dismiss (noise)**, or, for a thread only the sent pass found, neither asked nor ledgered.

   The summary counts the sent pass: `sent mail: N threads, N proposed, N under 5 working days`.

## Google-native files

A `drive` row's `Endpoint` is the id of the Google Drive the vault syncs from; without one, `convert` and this conversion are skipped. A `google-native` stub has no content: **find it by name in the drive-scoped folder listing** (the row's drive id, `trashed = false`), **export it verbatim** to a `.md` sibling in `triage/` under the vault's naming, and **ledger it**. The `.md` flows on as a loose file; the stub gets its own Delete question. With no Drive connector, or the Drive API not enabled (its error quoted), the stub stays unfiled and the summary says why.

## The conversion ledger

`${PARAOS_HOME:-~/.paraos}/cache/triage-drive/<vault>.json`, `{ "<fileId>": { "modifiedTime": "...", "converted_to": "<filename>.md", "date": "YYYY-MM-DD" } }`, created where missing: an edited document re-converts.

## The seen-ledger

Mailbox dedup across runs, read and settled at steps 5 and 6 of [connectors.md](../../para-shared/connectors.md): `${PARAOS_HOME:-~/.paraos}/cache/triage-email/<vault>.json`, `{ "<threadId>": { "disposition": "actioned|noted|dismissed", "date": "YYYY-MM-DD", "subject": "...", "seen_through": "<the dedup key of the newest message>", "seen_date": "<its received timestamp>" } }`, created where missing; a `seen_ledger.load_error` is reported.

- **A fetched thread already staged as a note is that note.** After a local pull, write the candidates (`{"thread_id", "newest_date"?, "newest_key"?, "newest_own"?}` each) to a file and re-run the scan with `--threads <file>`: `threads` folds each against the staged notes, with its watermark (`new`/`seen`/`grown`/`carry`) and `unanswered`.
- **Write** an entry at execute time for every disposition but **Dismiss (other vault)**, which the thread may later concern; `seen_through` is the newest message on the true list.
- **A thread grown past its watermark is judged from scratch**, its earlier disposition named in the option, never standing as the recommendation.
