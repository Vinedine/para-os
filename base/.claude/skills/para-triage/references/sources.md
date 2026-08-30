# Configured triage sources (Step 2)

Beyond the `triage/` folder, a vault may declare extra inputs in a `## Triage sources` block in its CLAUDE.md. This file is the protocol for pulling them. **If the vault has no such block, do nothing here** - the skill is folder-only.

Read the block. It is a table with columns `Source | Type | Endpoint | Relevant when` (wording varies; the first three are what you dispatch on). Three source types.

## sync-script sources

A script that writes new items into `triage/` (e.g. `granola.js`).

- **Real run:** run it with `--write` (resolve the path relative to the vault root; `node` for `.js`, `py`/`python` for `.py`). These scripts default to dry-run and dedup their own output, so running them is idempotent and safe.
- **Preview (`preview` arg):** run it **without** `--write` and list what it would add. `preview` must not touch disk - never `--write` a sync source in preview.
- After a real run, its files are ordinary loose files in `triage/` and flow through the remaining steps like anything else - nothing more to do here.
- If the script errors (auth expired, network), report it and continue with the other sources; do not abort the whole triage.

## connector sources

A live mailbox read over MCP. Read-only - never writes to a mailbox.

**Dispatch by the `Type` value:**

| Type in manifest | Search tool | Content tool | Granularity |
|---|---|---|---|
| `connector: claude_ai_Gmail` | `search_threads` | `get_thread` | threads (native) |
| `connector: google-workspace` | `search_gmail_messages` (pass the Endpoint as `user_google_email`) | `get_gmail_messages_content_batch` | messages - **must group by `threadId`** |

**Match on the tool suffix, not the full name.** The `<server>` half of `mcp__<server>__<tool>` is not stable across clients: the same connector may appear as `mcp__claude_ai_Gmail__*` or under an opaque UUID. If schemas are deferred, search for the suffix to load them. Only when that search comes back empty is the connector genuinely absent: skip the source, note it in the summary ("`<source>` declared but not connected - skipped"), and do not fail the run.

**Per connector source:**

1. **Build the query** from the `Relevant when` text plus a standard frame: `in:inbox -category:promotions -category:social -category:updates newer_than:30d`. Add the sender/subject operators the filter implies. **Exclude machine notifications** - widen these as the mailbox needs: `-from:noreply -from:no-reply -from:donotreply -from:notification -from:newsletter`, plus any app-notification domain it receives. A working mailbox can be mostly bot mail.
2. **Operators only pre-filter; the judgment is the real gate.** Sender exclusions never catch everything - a variant address (`donotreply@`, `notification@`) or a *human* reply on an automated thread will slip through. Treat the query as a cheap first cut, then in step 6 drop anything that is not genuinely a thread needing a reply or a decision.
3. **Search, then normalize to threads.** Gmail returns threads already. Workspace returns individual messages - group results by `threadId` so one conversation is one candidate, not N. Fetch metadata (subject, from, date) for the shortlist.
4. **Dedup against the seen-ledger** (below): drop any thread already dispositioned.
5. **Get the true message list before judging.** For every `claude_ai_Gmail` thread that survives dedup, call `get_thread` with `messageFormat: METADATA_ONLY` (cheap - IDs, senders, dates, labels, no bodies). Search results may be truncated, so a thread that looks short may not be. Workspace threads need no such call.
6. **Judge action-worthiness** against `Relevant when` plus the root README's `## Operating model` (read in SKILL.md Step 1): `Relevant when` scopes the query, the Operating model decides whether the thread is this vault's business at all - a real thread outside it is **Dismiss (other vault)**. Read snippets/bodies only for the shortlist. Keep the threads that genuinely need a reply or a decision. Two rules that kill common false positives: (a) **if the newest message in the thread is the mailbox owner's own (SENT), the ball is usually in the other party's court** - default to Dismiss unless the content clearly leaves an open task for the owner; (b) real correspondence about a *different* vault's business is **Dismiss (other vault)**, not action-worthy here. Apply (a) only to a message list from step 5; if that call could not run, surface the thread instead of dismissing it.
7. **Before proposing a new action, match the thread against what the vault already tracks** - contacts (`areas/network/`), projects, ideas, and open `actions.md` items - the same entity-matching [filing.md](filing.md) does for loose files. If the thread bears on an existing item (a reply on an open thread, promised docs arriving), route it to **Update existing**, not **Add action**; only a thread with no existing home becomes **Add action**. Each surviving thread then becomes a proposal row in SKILL.md Step 5.

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
5. **The stub itself gets a Delete row in the proposal table**, approved by a human like any other delete. Never auto-delete it - see the Strict rule.

**Pair the stub and its converted `.md` as one proposal row**, not two. They are one item arriving in two forms, and counting them twice inflates the loose-file count `/para-daily-brief` reads.

## The conversion ledger

Separate from the seen-ledger, because it answers a different question: *has this document already been converted, and has it changed since?*

- Path: `${PARAOS_HOME:-~/.paraos}/cache/triage-drive/<vault>.json`.
- Keyed on **Drive file id plus `modifiedTime`**. Both halves matter: the id alone would never re-convert a document that was edited after conversion, and the pair makes an edited document correctly re-convert while an untouched one never does.
- Shape: `{ "<fileId>": { "modifiedTime": "...", "converted_to": "<filename>.md", "date": "YYYY-MM-DD" } }`.
- Missing file or directory: create them. It is a cache, so deleting it only means documents re-convert.

## The seen-ledger

Connector dedup across runs lives outside the vault (a mailbox read must leak nothing into a synced folder):

- Path: `${PARAOS_HOME:-~/.paraos}/cache/triage-email/<vault>.json`, keyed by thread ID.
- Shape: `{ "<threadId>": { "disposition": "actioned|noted|dismissed", "date": "YYYY-MM-DD", "subject": "..." } }`.
- **Read** it during dedup (connector step 4 above) to skip dispositioned threads.
- **Write** it at execute time for settled dispositions - Update existing, Add action, Note to triage, and **Dismiss (noise)**. Do **not** ledger **Dismiss (other vault)**: that thread belongs to another vault, and a permanent dismissal here would hide it if it later became relevant - re-dismissing it next run is cheap.
- Missing file or directory: create them. It is a cache, not a system of record, so deleting it only means threads may resurface.
- **A ledgered Dismiss never resurfaces**, so write one only with the thread's true message list (step 5) in hand. To undo one, delete its entry.

## Edge cases

- **Google-native file, but the Drive API is not enabled** on the connector's Cloud project: the API returns an explicit "not enabled" error naming the project and an enable URL. Surface that error and the URL to the operator verbatim, leave the stub in `triage/`, and do **not** fall back to name-only inference. The document becomes readable the moment the operator clicks that link, and a filing inferred from the name meanwhile would be wrong in a way nobody would catch. This is a one-click operator action, not a skill failure.
- **Vault declares a `drive` row but no Drive connector is available** in the harness: skip the Google-native branch, leave the stubs in `triage/`, and note it in the summary the way an absent mail connector is noted (`drive` declared but not connected - Google-native files left unconverted). Never file or delete a stub you could not read.
