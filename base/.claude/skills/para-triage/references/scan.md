# The scan's output (Step 2)

Flags beside `--vault`: `--threads <file.json>` ([sources.md](sources.md#the-seen-ledger)), `--now <ISO-8601>`, `--paraos-home <dir>`, `--indent N`.

| Field | Holds |
|---|---|
| `vault` | `path`, `root`, `missing`, `hint`, `name`, `registered`, `active`: Step 1's check |
| `sources.declared`, `sources.rows` | The `## Triage sources` rows, each with `plan` (`pull`/`run`/`skip`/`sent`/`lookup`/`unknown`), `reason`, and `sent` true where it declares the sent pass |
| `ingest` | `registered`, `active`, `newest_write`, `newest_any`, `covered`, `reason`, `staged_here`, `count_for_vault`, `log_errors`: the coverage verdict each `plan` reads |
| `ingest_ledger` | `path`, `exists`, `load_error` of `/para-ingest`'s ledger |
| `items.loose` | Per top-level file: `name`, `size`, `kind`, `readme`, `twin`, `note`, `duplicates`, `hash_skipped`, `cross_vault`, `inbound` |
| `items.loose[].twin` | A `.pdf`'s same-stem `.md`, folded onto it; never a Google-native stub's |
| `items.loose[].note` | For a `.md`: `shape`, `fields`, `mail_note`, `mailbox`, `mentioned_vaults` (named in its `Routed` line), `routed_vaults` and `routed_from` (the routing decision, from ingest's ledger), `content_incomplete`, `content_evidence`, `thread_hash`, `thread_id`, `message_id`, `conversation_id`, `ingest_seen`, `mailbox_readers` |
| `items.subdirectories` | `name`, `files`, `handoff` (`_`-prefixed) |
| `items.subdirectories_line` | The manifest's `Subdirectories, not asked: ...` line; null with none |
| `items.empty`, `items.only_subdirectories` | Step 2's two stops |
| `items.same_thread` | `{key: [names]}` for notes sharing a thread hash or `Conversation id` |
| `seen_ledger` | `path`, `exists`, `entries`, `legacy`, `load_error` |
| `threads` | With `--threads`, per thread: `thread_id`, `thread_hash`, `staged_notes`, `ledger`, `watermark`, `unanswered` (`since`, `working_days`, `waiting`; null unless `newest_own`) |
| `over_threshold` | `{file, open}` per action file at or past the cap of 8 open items |
| `contact_card_level` | `yes`, `relationship only` or `never`: what a contact card may hold ([filing.md](filing.md#a-meeting-record)) |
| `snapshot`, `snapshot_folders` | What the `changed` re-check reads |
| `saved_to`, `save_error` | The output's copy outside the vault, or null and why |
