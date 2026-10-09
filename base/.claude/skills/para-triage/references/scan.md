# Scanning triage and its sources (Step 2)

The mechanical half of Steps 2 and 3, with no judgment in it.

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/triage_scan.py" --vault <root> \
    [--now <ISO-8601>] [--paraos-home <dir>] [--threads <file.json>] [--indent N]
```

## The output

| Field | Holds |
|---|---|
| `vault` | `path`, `root`, `missing`, `hint`, `name`, `registered`, `active` - Step 1's whole check |
| `sources.declared`, `sources.rows` | The `## Triage sources` table, each row gaining `plan` (`pull`/`run`/`skip`/`sent`/`lookup`/`unknown`) and `reason`; `sent` is true for a row declaring the sent pass |
| `ingest` | `registered`, `active`, `newest_write`, `newest_any`, `covered`, `reason`, `staged_here`, `count_for_vault`, `log_errors` - the coverage verdict every row's `plan` reads |
| `ingest_ledger` | `path`, `exists`, `load_error` for `/para-ingest`'s central ledger; `items.loose[].note.routed_vaults` is what reads its `mailboxes` map, per note |
| `items.loose` | One entry per top-level file (`.gitkeep` dropped, a PDF's `.md` twin folded on): `name`, `size`, `kind`, `readme`, `twin`, `note`, `duplicates`, `hash_skipped`, `cross_vault`, `inbound` |
| `items.loose[].twin` | **PDF-only**: the `.md` whose stem matches a `.pdf` beside it. A Google-native stub and its converted `.md` are never paired here; the skill pairs them itself at conversion ([sources.md](sources.md#google-native-files)). |
| `items.loose[].note` | For a `.md` item: `shape` (`ingest`/`frontmatter`/null), `fields`, `mail_note`, `mailbox`, `mentioned_vaults` (named in its `Routed` line: a mention, not the routing decision), `routed_vaults`, `routed_from` (the routing decision, from `/para-ingest`'s ledger), `content_incomplete`, `content_evidence`, `thread_hash`, `thread_id`, `message_id`, `conversation_id`, `ingest_seen`, `mailbox_readers` |
| `items.subdirectories` | `name`, `files`, `handoff` (`_`-prefixed) |
| `items.subdirectories_line` | The manifest's `Subdirectories, not asked: ...` line, printed as it stands; null with no subdirectories |
| `items.empty`, `items.only_subdirectories` | The two stop conditions Step 2 checks last |
| `items.same_thread` | `{key: [names]}` for every thread hash or `Conversation id` two or more notes share, keyed by the conversation id where one joins them |
| `seen_ledger` | `path`, `exists`, `entries`, `legacy`, `load_error` |
| `threads` | Only with `--threads`: per fetched thread, `thread_id`, `thread_hash`, `staged_notes`, `ledger`, `watermark`, and `unanswered` (`since`, `working_days`, `waiting`; null unless `newest_own`) |
| `over_threshold` | `{file, open}` for every action file at the cap, `OPEN_ITEM_CAP` (8), or past it |
| `contact_card_level` | `yes`, `relationship only` or `never`: what a contact card may hold, which places a meeting record's next step ([after-a-meeting.md](after-a-meeting.md)) |
| `snapshot`, `snapshot_folders` | Every file in `triage/` and the folder itself, read back by `paraos_vault.py changed <saved_to>` before each delete or move ([execute.md](execute.md)) |
| `saved_to`, `save_error` | Where the scan kept its own copy of this output, under `$PARAOS_HOME/data/scans/` and never inside the vault (copies older than a week are pruned); or null, and why |
