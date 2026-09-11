# Configured triage sources (Step 2)

Beyond the `triage/` folder, a vault may declare extra inputs in a `## Triage sources` block in its CLAUDE.md. This file is the protocol for pulling them. **If the vault has no such block, do nothing here** - the skill is folder-only.

**Same when `${PARAOS_HOME:-~/.paraos}/vaults.json` lists this vault root as `active` *and the layer has actually run*.** On a machine running the cross-vault ingest layer, `/para-ingest` pulls these same sources once for every vault, stages what it routes here as notes in `triage/`, and keeps their ledger - so their output is already loose files by the time this skill runs, and pulling them again would double-fetch every mailbox and split the ledger in two.

**Both halves are required, and the second one is the load-bearing one.** Being listed in the registry says the layer is *supposed* to feed this vault; it does not say it has. Deferring to something that has not run is the false quiet named in the skill's Strict rules wearing a different hat: `triage/` looks clean because nothing filled it. So check the newest run log under `${PARAOS_HOME:-~/.paraos}/cache/ingest/runs/`:

- **A write log from the last 48 hours:** skip the `connector` and `fetch-script` sources below (since ingest already staged them), but still process `sync-script` and `drive` sources as normal. Put the log's date in the summary (`ingest last staged <date>`).
- **No write log, or the newest older than that (e.g. only preview logs):** pull all sources here as normal, and say why in the summary (`registry lists this vault, but ingest last staged <date or never> - pulled locally`). A double-fetch is a wasted API call; a skipped fetch is a missed item, and only one of those is recoverable by noticing later.

No registry, or this root not in it: pull as normal with nothing to report, which is also the right answer on a machine that has never run the layer.

Read the block. It is a table with columns `Source | Type | Endpoint | Relevant when` (wording varies; the first three are what you dispatch on). Four source types.

## sync-script sources

A script that writes new items into `triage/` (e.g. `granola.js`).

- **Real run:** run it with `--write` (resolve the path relative to the vault root; `node` for `.js`, `py`/`python` for `.py`). These scripts default to dry-run and dedup their own output, so running them is idempotent and safe.
- **Preview (`preview` arg):** run it **without** `--write` and list what it would add. `preview` must not touch disk - never `--write` a sync source in preview.
- After a real run, its files are ordinary loose files in `triage/` and flow through the remaining steps like anything else - nothing more to do here.
- If the script errors (auth expired, network), report it and continue with the other sources; do not abort the whole triage.

## fetch-script sources

A mailbox with no MCP connector, reached by a script that **prints candidates and writes nothing** (`<script> fetch --days N`, JSON on stdout, counts on stderr).

**Treat it as a mailbox, not as a sync source**, which means it runs the same protocol: it is a row in the dispatch table of [../../para-shared/connectors.md](../../para-shared/connectors.md), so follow that file exactly as a connector does - the script's `fetch` is the search step, and its records arrive already grouped by `thread_id`. Then judge the surviving threads exactly as the connector section below does.

**Never run such a script with `--write` or any other writing flag.** A fetch source reads and prints; if one also offers a write path, using it files mail unjudged, which is the thing fetching exists to avoid. A vault that genuinely wants wholesale import declares a `sync-script` row instead and takes what comes.

## connector sources

A live mailbox read over MCP, read-only. **The fetch protocol - dispatch, query frame, thread normalisation, dedup and the message-list call - is [../../para-shared/connectors.md](../../para-shared/connectors.md)**, shared with `/para-ingest`. It hands back a deduped candidate set and stops. What follows is triage's own, and is where the judgment lives.

**Per surviving thread:**

1. **Judge action-worthiness** against `Relevant when` plus the root README's `## Operating model` (read in SKILL.md Step 1): `Relevant when` scopes the query, the Operating model decides whether the thread is this vault's business at all - a real thread outside it is **Dismiss (other vault)**. Read snippets/bodies only for the shortlist. Keep the threads that genuinely need a reply or a decision. Two rules that kill common false positives: (a) **if the newest message in the thread is the mailbox owner's own (SENT), the ball is usually in the other party's court** - default to Dismiss unless the content clearly leaves an open task for the owner; (b) real correspondence about a *different* vault's business is **Dismiss (other vault)**, not action-worthy here. Apply (a) only to a message list from the shared file's step 6; if that call could not run, surface the thread instead of dismissing it.
2. **Before proposing a new action, match the thread against what the vault already tracks** - contacts (`areas/network/`), projects, ideas, and open `actions.md` items - the same entity-matching [filing.md](filing.md) does for loose files. If the thread bears on an existing item (a reply on an open thread, promised docs arriving), route it to **Update existing**, not **Add action**; only a thread with no existing home becomes **Add action**. Each surviving thread then gets its own disposition, per [approval.md](approval.md).

## drive sources

A `drive` row declares the Google Drive this vault syncs from, so Google-native stubs can be resolved. `Endpoint` is the **drive id**, declared rather than inferred - an unscoped Drive query is the false-quiet failure named in the skill's Strict rules. One row per vault; a vault that does not sync from Drive declares none, and everything below is skipped.

The row enables exactly two things: the Google-native conversion branch below, and the `convert` argument. It pulls no items of its own - a `drive` source is not an inbox, it is the lookup that makes a stub already sitting in `triage/` readable.

## Google-native files

Only relevant where Drive is the vault's sync layer, and only when the vault declares a `drive` row. Everywhere else, skip this section entirely.

A Google-native file syncs to disk as a **pointer stub**: the name and a file id, no content. It fails the vault's own file-format rule the moment it lands, so the job here is to normalise it into a real file, not to file the stub - even though `mv`/rename works on the stub itself (a same-volume move never reads the bytes). Never file it unconverted.

1. **Get the drive id from the `drive` row.** Never infer it, and never search without it - see the Strict rule on unscoped Drive search, which is the failure mode that makes this dangerous rather than merely annoying.
2. **Locate the document** by listing the drive-scoped folder and matching on the stub's name, passing the declared drive id. Scoping the call to the drive is the load-bearing part. Do **not** plan on reading the stub for its file id: on a streaming Drive mount it has no readable bytes at all. A mirroring mount does write real JSON, but no branch should depend on which mode the operator happens to run. **Exclude trashed items** (`trashed = false`): a Drive query returns trashed documents by default, so a name match will otherwise resurrect a document the operator deleted and convert it straight back into `triage/`.
3. **Export it** to text/Markdown and **write a real `.md` sibling into `triage/`**, under the vault's source-document naming. Keep the export verbatim: this is a format conversion, not a summarisation.
4. **Ledger the conversion** (below), then let the new `.md` flow through the remaining steps as an ordinary loose file.
5. **The stub itself gets its own delete disposition**, approved by a human like any other delete. Never auto-delete it - see the Strict rule.

**Pair the stub and its converted `.md` as one proposal row**, not two. They are one item arriving in two forms, and counting them twice inflates the loose-file count `/para-daily-brief` reads.

## The conversion ledger

Separate from the seen-ledger, because it answers a different question: *has this document already been converted, and has it changed since?*

- Path: `${PARAOS_HOME:-~/.paraos}/cache/triage-drive/<vault>.json`.
- Keyed on **Drive file id plus `modifiedTime`**. Both halves matter: the id alone would never re-convert a document that was edited after conversion, and the pair makes an edited document correctly re-convert while an untouched one never does.
- Shape: `{ "<fileId>": { "modifiedTime": "...", "converted_to": "<filename>.md", "date": "YYYY-MM-DD" } }`.
- Missing file or directory: create them. It is a cache, so deleting it only means documents re-convert.

## The seen-ledger

Mailbox dedup across runs - connector and fetch-script alike - lives outside the vault (a mailbox read must leak nothing into a synced folder):

- Path: `${PARAOS_HOME:-~/.paraos}/cache/triage-email/<vault>.json`, keyed by thread ID.
- Shape: `{ "<threadId>": { "disposition": "actioned|noted|dismissed", "date": "YYYY-MM-DD", "subject": "...", "seen_through": "<RFC822 Message-ID of the newest message at disposition>", "seen_date": "<that message's received timestamp>" } }`.
- **Read** it during dedup (step 5 of [../../para-shared/connectors.md](../../para-shared/connectors.md)) to skip threads dispositioned **through their newest message**. The `seen_through` / `seen_date` pair is what makes that comparison possible, so write it on every entry, and read an entry lacking it as watermarked at its `date`.
- **Write** it at execute time for settled dispositions - Update existing, Add action, Note to triage, and **Dismiss (noise)**. Do **not** ledger **Dismiss (other vault)**: that thread belongs to another vault, and a permanent dismissal here would hide it if it later became relevant - re-dismissing it next run is cheap.
- Missing file or directory: create them. It is a cache, not a system of record, so deleting it only means threads may resurface.
- **A ledgered thread resurfaces when it grows past its watermark**, and only then, so write the entry with the thread's true message list (step 6 of the shared file) in hand: the newest message on that list is what `seen_through` records. To drop a disposition altogether, delete its entry.
- **A resurfaced thread is judged from scratch and proposed like any other**, with its earlier disposition and date named in the option description. Never let the previous answer stand as the recommendation: it was given on a shorter thread, and treating it as a default reinstates the permanence this rule removes. Its new messages are the evidence, and a **Dismiss (noise)** that is right a second time costs one question.

## Edge cases

- **Google-native file, but the Drive API is not enabled** on the connector's Cloud project: the API returns an explicit "not enabled" error naming the project and an enable URL. Surface that error and the URL to the operator verbatim, leave the stub in `triage/`, and do **not** fall back to name-only inference. The document becomes readable the moment the operator clicks that link, and a filing inferred from the name meanwhile would be wrong in a way nobody would catch. This is a one-click operator action, not a skill failure.
- **Vault declares a `drive` row but no Drive connector is available** in the harness: skip the Google-native branch, leave the stubs in `triage/`, and note it in the summary the way an absent mail connector is noted (`drive` declared but not connected - Google-native files left unconverted). Never file or delete a stub you could not read.
