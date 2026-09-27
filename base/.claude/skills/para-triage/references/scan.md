# Scanning triage and its sources (Step 2)

The mechanical half of Steps 2 and 3, with no judgment in it. `scripts/triage_scan.py`
implements every rule below over `para-shared/scripts/paraos_vault.py`, and
`scripts/test_triage_scan.py` pins each rule to a case.

```bash
# Windows: py -3
python3 "<this skill's base directory>/scripts/triage_scan.py" --vault <root> \
    [--now <ISO-8601>] [--paraos-home <dir>] [--threads <file.json>] [--indent N]
```

## The output

| Field | Holds |
|---|---|
| `vault` | `path`, `root`, `missing`, `hint`, `name`, `registered`, `active` - Step 1's whole check |
| `sources.declared`, `sources.rows` | The `## Triage sources` table, each row gaining `plan` (`pull`/`run`/`skip`/`lookup`/`unknown`) and `reason` |
| `ingest` | `registered`, `active`, `newest_write`, `newest_any`, `covered`, `reason`, `staged_here`, `count_for_vault`, `log_errors` - the coverage verdict every row's `plan` reads |
| `ingest_ledger` | `path`, `exists`, `load_error` for `/para-ingest`'s central ledger; `items.loose[].note.routed_vaults` is what reads its `mailboxes` map, per note |
| `items.loose` | One entry per top-level file (`.gitkeep` dropped, a PDF's `.md` twin folded on): `name`, `size`, `kind`, `readme`, `twin`, `note`, `duplicates`, `hash_skipped`, `cross_vault`, `inbound` |
| `items.loose[].twin` | **PDF-only**: the `.md` whose stem matches a `.pdf` beside it. A Google-native stub and its converted `.md` are never paired here; the skill pairs them itself at conversion ([sources.md](sources.md#google-native-files)). |
| `items.loose[].note` | For a `.md` item: `shape` (`ingest`/`frontmatter`/null), `fields`, `mail_note`, `mailbox`, `mentioned_vaults`, `routed_vaults`, `routed_from`, `content_incomplete`, `content_evidence`, `thread_hash`, `thread_id` |
| `items.subdirectories` | `name`, `files`, `handoff` (`_`-prefixed) |
| `items.subdirectories_line` | The manifest's `Subdirectories, not asked: ...` line, printed as it stands; null with no subdirectories |
| `items.empty`, `items.only_subdirectories` | The two stop conditions Step 2 checks last |
| `items.same_thread` | `{hash: [names]}` for every thread hash two or more notes share |
| `seen_ledger` | `path`, `exists`, `entries`, `legacy`, `load_error` |
| `threads` | Only with `--threads`: per fetched thread, `thread_id`, `thread_hash`, `staged_notes`, `ledger`, `watermark` |
| `over_threshold` | `{file, open}` for every action file at `WIP_THRESHOLD` (12) or more open items |
| `snapshot` | Read back by `paraos_vault.py changed <saved_to>` before each delete or move ([execute.md](execute.md)) |
| `saved_to`, `save_error` | Where the scan kept its own copy of this output, under `$PARAOS_HOME/data/scans/` and never inside the vault (copies older than a week are pruned); or null, and why |

The rest of this file is the script's specification and the by-hand fallback. By hand, a
collected vault's loose items are the files in `triage/` read through their
`resources/mds/triage__*` copies, per
[operating-discipline.md](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).

## By hand, where each rule actually lives

- **`vault`**: the library's root rule (`projects/` plus `areas/` or `archive/`, plus
  `CLAUDE.md`) plus a `triage/` folder. `hint` is the registry entry whose path holds the
  checked folder, else one whose name folds to it.
- **`sources` and `ingest`**: the coverage bullets in
  [sources.md](sources.md#configured-triage-sources-step-2), which are the specification of
  the `plan` verdict.
- **`items.loose[].duplicates`**: every other file in the vault with the same content hash,
  never matched by filename or size. Content overlap short of a byte match stays a judgment
  ([filing.md](filing.md)), never automated.
- **`items.loose[].inbound`**: every live line naming the file by its whole name
  (`notes.md` is not named by `meeting-notes.md`), link text and backticked paths included;
  a mention written as a path must sit under `triage/` (`projects/p/README.md` does not
  name `triage/README.md`).
- **`items.loose[].note`**: the two staged-note shapes, `/para-ingest`'s bullet header
  (its `references/staging.md`, "The staged note") and the frontmatter
  [execute.md](execute.md#connector-items)'s Note to triage writes. `mail_note` is true for
  a bullet header carrying `Source` and `Link`, or frontmatter carrying a `thread_id`.
  - **`content_incomplete`**: `true` where the `Content` line contains, case-insensitively,
    any of `snippet`, `preview`, `opening lines`, `no readable body`, `cut mid`, `truncat`,
    `not read`, `not fetched`, `incomplete`; else `false` where it contains any of `full body`,
    `plain-text body`, `complete`; else `null`, meaning judge the line yourself. **An
    unread attachment or linked document never makes the body incomplete**: it names
    something beside the body.
  - **`mentioned_vaults`**: registry names other than this vault's appearing in the
    `Routed` line as whole words, case-insensitive for a name of four or more characters,
    case-sensitive for a shorter one (`IT`, `OR` are also ordinary words). **No negation
    parsing**: "Not Beta: a different prospect" still names Beta, because this is a
    mention, not the routing decision, and misreading a real routing as a negation is the
    worse failure.
  - **`routed_vaults`, `routed_from`**: the routing decision, from `/para-ingest`'s central
    ledger, never from the note's prose. In the note's `mailbox`, find the entry whose
    thread id hashes (`thread_hash`) to the note's filename hash: its `routed` list minus
    this vault is `routed_vaults`, and `routed_from` is `"ledger"`. No match, or the mailbox
    absent from the ledger: both `null`. Search only that one mailbox, never across
    mailboxes, since a six-character hash can collide.
  - **`cross_vault`**: a byte-identical file in another vault's `sources/`, checked across
    the **union** of `mentioned_vaults` and `routed_vaults` (`null` read as empty): a vault
    checked needlessly costs one walk, a vault missed is a silent duplicate.
- **`items.subdirectories`, `items.same_thread`**: [approval.md](approval.md)'s
  subdirectory rule and "What 'linked' means here".
- **`seen_ledger`, `threads`**: [sources.md](sources.md#the-seen-ledger).
- **`over_threshold`**: [approval.md](approval.md)'s Add action flag, `file at N open -
  groom?`.
