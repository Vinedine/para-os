# Scanning triage and its sources (Step 2)

Everything between "the vault has a `triage/` folder and a `## Triage sources` block" and "a
set of loose items, source rows and notes, each carrying what Steps 3 to 6 need to judge it".
Mechanical: no judgment lives here, per [sources.md](sources.md)'s ingest-recency rule,
[filing.md](filing.md)'s duplicate check, and [approval.md](approval.md)'s mail-note
vocabulary - this file is the specification those three already state, read as one scan.

`scripts/triage_scan.py` implements every rule below over `para-shared/scripts/paraos_vault.py`
(the registry, the run logs, a staged note's filename shape, a thread's dedup hash, a ledger's
watermark, a content hash, where a checkbox may live), and `scripts/test_triage_scan.py` pins
each rule to a case.

```bash
python3 "<this skill's base directory>/scripts/triage_scan.py" --vault <root> \
    [--now <ISO-8601>] [--paraos-home <dir>] [--threads <file.json>] [--indent N]
```

## The output

| Field | Holds |
|---|---|
| `vault` | `path`, `root`, `missing`, `hint`, `name`, `registered`, `active` - Step 1's whole check |
| `sources.declared`, `sources.rows` | The `## Triage sources` table, each row gaining `plan` (`pull`/`run`/`skip`/`lookup`/`unknown`) and `reason` |
| `ingest` | `registered`, `active`, `newest_write`, `newest_any`, `covered`, `reason`, `staged_here`, `count_for_vault`, `log_errors` - the coverage verdict every row's `plan` reads |
| `ingest_ledger` | `path`, `exists`, `load_error` for `/para-ingest`'s own central ledger - the read verdict only; `items.loose[].note.routed_vaults` is what actually reads its `mailboxes` map, per note |
| `items.loose` | One entry per top-level file (`.gitkeep` dropped, a PDF's `.md` twin folded on): `name`, `size`, `kind`, `readme`, `twin`, `note`, `duplicates`, `hash_skipped`, `cross_vault`, `inbound` |
| `items.loose[].twin` | **PDF-only**: the `.md` whose stem matches a `.pdf` beside it. A Google-native stub and its converted `.md` are never paired this way - they cannot be, since the conversion names the `.md` under the vault's own naming convention, not the stub's stem. `sources.md`'s "Pair the stub and its converted `.md` as one proposal row" stays the skill's own rule, done at execute time, right after the skill itself performed that conversion. |
| `items.loose[].note` | For a `.md` item: `shape` (`ingest`/`frontmatter`/null), `fields`, `mail_note`, `mailbox`, `mentioned_vaults`, `routed_vaults`, `routed_from`, `content_incomplete`, `content_evidence`, `thread_hash`, `thread_id` |
| `items.subdirectories` | `name`, `files`, `handoff` (`_`-prefixed) |
| `items.empty`, `items.only_subdirectories` | The two stop conditions Step 2 checks last |
| `items.same_thread` | `{hash: [names]}` for every thread hash two or more notes share |
| `seen_ledger` | `path`, `exists`, `entries`, `legacy`, `load_error` |
| `threads` | Only with `--threads`: per fetched thread, `thread_id`, `thread_hash`, `staged_notes`, `ledger`, `watermark` |
| `over_threshold` | `{file, open}` for every action file at `WIP_THRESHOLD` (12) or more open items |
| `snapshot` | Read back by `paraos_vault.py changed <scan output file>` before each delete or move ([execute.md](execute.md)) |

The rest of this file is the script's specification and the by-hand fallback. By hand, a
collected vault's loose items are the files in `triage/` read through their
`resources/mds/triage__*` copies, per
[operating-discipline.md](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).

## By hand, where each rule actually lives

- **`vault`**: the library's root rule (`projects/` plus `areas/` or `archive/`, plus
  `CLAUDE.md`) plus a `triage/` folder present. `hint` is the registry entry whose path
  holds the checked folder, else one whose name folds to it - `vaults.json`'s own shape,
  read by hand the way [operating-discipline.md](../../para-shared/operating-discipline.md)
  already says every skill's Step 1 does.
- **`sources` and `ingest`**: exactly the three coverage bullets in
  [sources.md](sources.md#configured-triage-sources-step-2). That section, not this one, is
  the specification of the `plan` verdict; this file only says where in the JSON to find it.
- **`items.loose[].duplicates`**: [filing.md](filing.md)'s "check for duplicates and
  redundancies" step, content first and never a filename or a size. Content overlap that is
  not a byte-for-byte match stays a judgment call, never automated: the scan reports only
  what hashes to the same digest. `.cross_vault`'s own rule is under `items.loose[].note`
  below, since it reads the note's `mentioned_vaults` and `routed_vaults`.
- **`items.loose[].inbound`**: every live line naming the file by its whole name (`notes.md`
  is not named by `meeting-notes.md`), a mention written as a path sitting under `triage/` - [approval.md](approval.md)'s "A delete or a move names what links to the
  file".
- **`items.loose[].note`**: the two staged-note shapes `/para-ingest`'s own
  `references/staging.md` ("The staged note") and [execute.md](execute.md#connector-items)
  write, and the mail-note vocabulary [approval.md](approval.md#the-action-vocabulary) offers
  once `mail_note` is true.
  - **`content_incomplete`**: `true` where the `Content` line contains, case-insensitively,
    any of `snippet`, `preview`, `opening lines`, `no readable body`, `cut mid`, `truncat`,
    `not read`, `not fetched`; `false` where it contains, with none of those present, any of
    `full body`, `plain-text body`, `complete`; `null` otherwise, meaning judge the line
    yourself. An incomplete phrase always wins over a complete one when both are present.
    **An unread attachment or linked document never makes the body incomplete** - "the
    linked Google Doc was not opened" names something *beside* the body, not the body
    itself, so it reads `false` when a "held" phrase is also there. Where the scan reports
    `null`, judge the line yourself the same way - [filing.md](filing.md)'s re-fetch bullet
    is what this field feeds.
  - **`mentioned_vaults`**: registry names other than this vault's, appearing in the
    `Routed` line as whole words - case-insensitive for a name of four or more characters,
    case-sensitive for a shorter one, since a short name such as `IT` or `OR` is also an
    ordinary word. **No negation parsing**: a "Not Beta: a different prospect" line still
    names Beta here, because this is a mention the line makes, not the routing decision - a
    scan reading negation would need to parse every phrasing a model could write for "not
    this one," and getting it wrong the other way (reading a real routing as a negation)
    is the worse failure.
  - **`routed_vaults`, `routed_from`**: the actual routing decision, read from
    `/para-ingest`'s own central ledger (`ingest_ledger`, above), never from the note's own
    prose. In the note's `mailbox`, find the ledger entry whose thread id hashes
    (`thread_hash`) to the note's own filename hash; its `routed` list, minus this vault, is
    `routed_vaults`, and `routed_from` is `"ledger"`. No match, or the mailbox is not in the
    ledger at all: both come back `null` - and the hash is searched only within that one
    mailbox, never across every mailbox in the ledger, since a six-character hash can
    collide between two unrelated ones.
  - **`cross_vault`** checks the **union** of `mentioned_vaults` and `routed_vaults`
    (`null` read as empty): a vault checked needlessly costs one size-filtered walk of its
    `sources/`, a vault missed is a silent duplicate a later run has to catch by hand.
- **`items.subdirectories`, `items.same_thread`**: [approval.md](approval.md)'s "A
  subdirectory is listed, never asked" and "What 'linked' means here".
- **`seen_ledger`, `threads`**: the ledger shape and the fold of a fetched thread into an
  already-staged note, both in [sources.md](sources.md#the-seen-ledger).
- **`over_threshold`**: [approval.md](approval.md)'s Add action option, `file at N open -
  groom?`.
