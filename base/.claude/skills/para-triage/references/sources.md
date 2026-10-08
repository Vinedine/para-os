# Configured triage sources (Step 2)

Beyond `triage/`, a vault may declare inputs in a `## Triage sources` block in its CLAUDE.md: a table `Source | Type | Endpoint | Relevant when` (wording varies; dispatch on the first three), with the four types below. **No such block: do nothing here.**

**Skip what `/para-ingest` already pulled.** On a machine running the cross-vault ingest layer, it pulls these sources for every vault and stages what it routes here as notes in `triage/`; pulling again would double-fetch every mailbox and split the ledger. The scan's `ingest` block and each row's `plan` and `reason` apply the rules below. By hand, read `${PARAOS_HOME:-~/.paraos}/vaults.json` and the newest **write** log under `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/`, by the fields `/para-ingest`'s `references/staging.md` names ("Fields `/para-triage` reads"):

- **Covered only when all hold**: the registry lists this root as `active`; the log's `mode` is `write` and `started_at` is within 48 hours; and it reached *this root*: a `files_written` entry lies under this vault's `triage/`, or `counts.per_vault` gives this vault's registry name an explicit `0`. **A positive count with no file under this root is not coverage**: the vault moved and the registry lagged, so ingest wrote elsewhere. Per row, a mailbox that `source_plan.declaring_vaults` (where present) does not list for this vault, or that an `errors` entry names, was not read for it.
- **Covered:** skip the covered `connector` and `fetch-script` rows, and put `ingest last staged <date>` in the summary. A row declaring the [sent pass](../../para-shared/connectors.md) (`plan` `sent`) runs that pass alone, keeping only threads that hold a message of the operator's own: ingest reads no sent mail. Skip a `sync-script` row only where the log's `sync_runs` records that script for this vault without an error; otherwise run it (it dedups, so this costs a round trip, never a duplicate). A `drive` row always stays.
- **Not covered** (no write log, older than 48 hours, preview logs only, or any condition above failing): pull every row here and name the failed condition in the summary (`registry lists this vault, but ingest last staged <date or never> - pulled locally`, `ingest staged N for <name> outside this root - pulled locally`).
- **No registry, or this root absent from it or inactive**: pull as normal, nothing to report.

## sync-script sources

A script that writes new items into `triage/` (e.g. `granola.js`). It defaults to dry-run and dedups its own output.

- **Real run:** `--write`, its path resolved against the vault root (`node` for `.js`; for `.py` the launcher [scripts.md](../../para-shared/scripts.md) names).
- **`preview`:** run it **without** `--write` and list what it would add. `preview` never touches disk.
- **On an error** (auth expired, network), report it and continue with the other sources.

## fetch-script sources

A mailbox with no MCP connector, reached by a script that **prints candidates and writes nothing** (`<script> fetch`, with the `--days N` its row passes and `--sent` where it declares the sent pass, JSON on stdout). **It is a mailbox, not a sync source**: follow [../../para-shared/connectors.md](../../para-shared/connectors.md) as for a connector (`fetch` is the search step; records arrive grouped by `thread_id`), then judge the surviving threads as below.

**Never run it with `--write` or any other writing flag**: that files mail unjudged. A vault that wants wholesale import declares a `sync-script` row instead.

**One judged attachment**, where the operator asks for it: fetch it with the script's own read-only single-item read where it offers one (`outlook.py raw <Graph path>`, under the environment its README names) and write it into `triage/` under the vault's naming, to file on this run. With no such read, the attachment stays in the mailbox and the summary says so.

## connector sources

A live mailbox read over MCP, read-only. **The fetch protocol (dispatch, query, threads, dedup, message list) is [../../para-shared/connectors.md](../../para-shared/connectors.md).** The judgment on each surviving thread is triage's own:

1. **Judge action-worthiness.** `Relevant when` scopes the query; the root README's `## Operating model` decides whether the thread is this vault's business at all, and a different vault's business is **Dismiss (other vault)**. Read bodies only for the shortlist; keep threads that genuinely need a reply or a decision.
2. **Read the operator's own messages**, on a fetched thread or a staged note's re-read ([filing.md](filing.md)), only on a true message list (the shared file's step 6); where that call could not run, surface the thread instead. Still one next step per thread, a promise before a wait:
   - **A dated promise.** Every message the operator wrote, not only the newest, is read for a commitment carrying a date or a weekday ("price to you Wednesday") that no later message shows kept. It is the thread's next step whoever wrote last: **Update existing** where a tracked item covers it, else **Add action** with `📅` on the promised date, a weekday being the first one after that message's own date, computed by the [shared library](../../para-shared/scripts.md)'s `paraos_vault.py weekday-after <date> <weekday>` with the day named in English, the option quoting the sentence and the date it was sent.
   - **An unanswered message.** Where the newest message is the operator's own and asks something of the other side (a proposal, a question, a reminder), the scan's `threads[].unanswered` counts its working days, Monday to Friday with public holidays counted as working days. From 5 (`waiting`) it is **Add action** with the line `Waiting on [<person>](<card>): <what> (since <the sent date>)` shown in full, or **Update existing** where a tracked item covers it. Before that a fetched thread is neither asked nor ledgered and comes back on the next run, and a staged note is **Leave in triage**.
   - **Neither**: a thread whose newest message is the operator's own is **Dismiss (noise)** unless its content leaves the operator an open task, and one only the sent pass found (for `outlook.py`, every message the operator's own) is neither asked nor ledgered.

   The summary counts the sent pass: `sent mail: N threads, N proposed, N under 5 working days`.
3. **Match before proposing a new action**, against contacts (`areas/network/`), projects, ideas, register rows and open `actions.md` items, as [filing.md](filing.md) does. A thread bearing on an existing item (a reply on an open thread, promised docs arriving) is **Update existing**; only one with no existing home becomes **Add action**, or **Add register row** where it opens a counterparty a register tracks. Each thread gets its own disposition ([approval.md](approval.md)).

## drive sources

A `drive` row's `Endpoint` is the **drive id** of the Google Drive this vault syncs from, declared rather than inferred (Strict rules: never search Drive unscoped). At most one per vault. It pulls no items: it enables the Google-native conversion below and the `convert` argument, and without it both are skipped.

## Google-native files

Only where the vault declares a `drive` row. A Google-native file syncs to disk as a **pointer stub**, a name and a file id with no content, so normalise it into a real file; never file the stub unconverted.

1. **Take the drive id from the `drive` row**; never infer it or search without it.
2. **Locate the document** by listing the drive-scoped folder for the stub's name. Do not rely on reading the stub for its file id: on a streaming mount it has no readable bytes. **Exclude trashed items** (`trashed = false`): a Drive query returns them by default, and a name match would resurrect a document the operator deleted.
3. **Export it verbatim** to text/Markdown as a real `.md` sibling in `triage/`, under the vault's source-document naming: a format conversion, not a summary.
4. **Ledger the conversion** (below); the `.md` then flows on as an ordinary loose file.
5. **The stub gets its own delete disposition** (Strict rules).

**The stub and its converted `.md` are one proposal row**, one item in two forms, so the loose-file count `/para-daily-brief` reads counts it once.

## The conversion ledger

Answers *has this document been converted, and has it changed since?*

- Path: `${PARAOS_HOME:-~/.paraos}/cache/triage-drive/<vault>.json`, keyed on **Drive file id plus `modifiedTime`**, so an edited document re-converts and an untouched one never does.
- Shape: `{ "<fileId>": { "modifiedTime": "...", "converted_to": "<filename>.md", "date": "YYYY-MM-DD" } }`.
- Missing: create it. It is a cache; deleting it only means documents re-convert.

## The seen-ledger

Mailbox dedup across runs, connector and fetch-script alike, kept outside the vault so a mailbox read leaks nothing into a synced folder.

- Path: `${PARAOS_HOME:-~/.paraos}/cache/triage-email/<vault>.json`, keyed by thread ID. Missing: create it; it is a cache, and deleting it only lets threads resurface. One that fails to parse is reported (the scan's `seen_ledger.load_error`), never silently dedupped against nothing.
- Shape: `{ "<threadId>": { "disposition": "actioned|noted|dismissed", "date": "YYYY-MM-DD", "subject": "...", "seen_through": "<the dedup key (connectors.md step 6) of the newest message at disposition>", "seen_date": "<that message's received timestamp>" } }`.
- **Read** it at step 5 of [../../para-shared/connectors.md](../../para-shared/connectors.md) and settle it at step 6, which hold the watermark rules.
- **A fetched thread already staged as a note is that note, not a second item.** After a local pull, write the candidates (`{"thread_id", "newest_date"?, "newest_key"?, "newest_own"?}` each) to a file and re-run the scan with `--threads <file>`: its `threads` block folds each against `items.loose` by the staged note's filename hash and carries the watermark verdict (`new`/`seen`/`grown`/`carry`), plus `unanswered` where `newest_own` says the newest message is the operator's own.
- **Write** it at execute time for Update existing, Add action, Add register row, Note to triage and **Dismiss (noise)**, with the true message list in hand: its newest message is `seen_through`, and every entry carries the `seen_through` / `seen_date` pair. **Never ledger Dismiss (other vault)**: a permanent dismissal would hide the thread if it later became relevant here. To drop a disposition, delete its entry.
- **A thread resurfaces only when it grows past its watermark, and is then judged from scratch**, its earlier disposition and date named in the option description. Never let the earlier answer stand as the recommendation: it was given on a shorter thread.

## Edge cases

- **Drive API not enabled** on the connector's Cloud project: the error names the project and an enable URL. Surface both to the operator verbatim, leave the stub in `triage/`, and **never fall back to name-only inference**: the document is readable once the API is enabled, and a filing guessed from the name would be wrong in a way nobody catches.
- **A `drive` row but no Drive connector**: skip the Google-native branch, leave the stubs, and note `drive declared but not connected - Google-native files left unconverted` in the summary. Never file or delete a stub you could not read.
