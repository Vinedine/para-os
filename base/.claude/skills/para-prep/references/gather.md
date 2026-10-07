# Gather (Steps 2 and 3)

`scripts/prep_scan.py` implements every rule below except who attends, which is read from the agenda first. Where the script cannot run, apply this file by hand and say so in one line.

## Who attends

The agenda is `/para-daily-brief`'s, read by [its Step 5c](../../para-daily-brief/references/signals.md#step-5c-build-the-agenda): the `## Agenda sources` connectors and the `meetings.md` fallback, merged.

- **A calendar event**: its attendee list, each passed as `Name <address>`, or the address alone. Leave out the calendar's own address (the source's `Endpoint`), rooms and other resources, and anyone who declined.
- **A `meetings.md` line**: a field naming people is the attendee list, and a title naming people ("Weekly status with Jan") names them too. Pass each name as written.
- **A `<person>`, or prose naming people**: those people, as written.

## What the scan returns

| Field | Holds |
|---|---|
| `vault`, `today`, `root` | The vault root, the date every age is measured against, and the root check (`root`, `missing`) |
| `lifecycles` | The headings of the lifecycles the vault declares; empty where it declares none |
| `cards_hold` | What a card may hold, from the checkbox table's `areas/network/` row: `yes`, `relationship only` or `never` |
| `people[]` | One per `--person`, in the order given: `query`, the `name` and `email` read from it, `status` (`matched`, `ambiguous`, `no_card`) and `matched_by` |
| `people[].candidates` | `ambiguous` only: the cards it could be |
| `people[].card` | `matched` only: `path`, `name`, `aliases`, `kind` (the `**Kind:**` line, or null), `header`, `emails`, and `items`, its open checkboxes. An item under `## Next actions` carries the card's title as its `section` |
| `people[].entities` | `matched` only: `{path, via}` per entity the card links (`card`), whose brief or README links the card (`entity`), or both |
| `people[].mentions` | Open items in any other action file or card naming the person, with `file`, `line`, the markers and `by` |
| `people[].records`, `records_total` | The five newest files in a live `sources/` or `archive/meetings/` naming the person, with `date`, `days_ago` and `by`; the total counts every match |
| `people[].unfiled` | Items in `triage/` naming the person, `{path, by}`, undated: an item waiting to be filed is usually the newest record, so its date is read from its content |
| `people[].rows` | Register rows of a declared row home naming the person: `register`, `line`, `name`, `closed`, `stage`, `cells`, `by` |
| `entities[]` | Once per entity any matched card ties to: `path`, `document`, `title`, `stage`, `header`, `unknown` (header fields reading `unknown`), `do_not_raise`, `actions` (`path`, `open`, `next`) and `newest_source` |
| `entities[].stage` | Null unless the Stage line names a declared stage: `lifecycle`, `name`, `qualifier`, `since`, `days_in_stage` (null without a `since`), `dated_facts` with `days_ahead`, `terminal`, and `columns`, the rest of that stage's row in the lifecycle table as written (its `Exit criterion` among them) |

**Null is not empty.** `mentions`, `records`, `unfiled` and `rows` are null for an `ambiguous` person and for one with no card whose name is a single word: nothing was searched. An empty list means searched and nothing found.

## How a person is matched

The first rung that finds any card decides; two cards at that rung are `ambiguous`, never chosen between.

1. **`email`**: an address the card carries anywhere outside a fence.
2. **`name`**, then **`alias`**: the whole name, ignoring word order, case and accents, against the card's title, its file name read as words (`peeters-ann.md` is Ann Peeters), and every name its `**Aliases:**` or `Also:` lines list. A title or file name outranks another card's alias.
3. **`partial`**: every word of the name sits in one of the card's names (`Jan` is Jan Claes where no other card carries a Jan).
4. **`email_name`**: an address whose part before the `@` spells a whole name (`jan.claes@...`). Say which address it was: it is the weakest rung.
5. Otherwise **`no_card`**.

A parenthetical is dropped from the name (`Ann Peeters (Acme)`), and `Last, First` reads as one name.

## What names a person

The `by` on a mention, a record or a row, first match wins:

- **`link`**: a link resolving to the card.
- **`email`**: an address the card carries, or the one given for a person with no card.
- **`name`** or **`alias`**: a whole name of two words or more, in any rotation of its words (`De Ryck, Pieter`), accents and case ignored.
- **`short name`**, in an open item only: the first or last word of the card's title, or a one-word alias, written as on the card, three letters or more, carried by no other card, and not followed by a number (`Jan 2027` is a month). It is how "Raise with Jan" is found, and the likeliest to be wrong: weigh it before quoting it.
- **`file name`**, for a record: a whole name in the file's name.

A person with no card is looked for by the whole name and address given, never by one word.

## Entities, records and rows

- **An entity** is the folder a link resolves into: `projects/<x>`, `areas/<x>` (never the network area) or `resources/ideas/<x>`. Its document is `README.md` where it has one, else `brief.md`. An archived entity is history, not something the meeting touches.
- **Its stage** is read per [para-shared/lifecycles.md](../../para-shared/lifecycles.md); a stage name two lifecycles declare is read against the one whose home holds the entity.
- **Its do-not-raise list** is the text after a bold-led `**Do not raise:**` label and the list directly under it, or everything under a heading of that name down to the next heading of its level.
- **Its open count and next item** come from its own `actions.md`; the next item is the earliest-dated open one.
- **Its newest source**, and every record's date, is the date its file name opens on (`YYYYMMDD` or `YYYY-MM-DD`); an undated file is never the newest source and sorts last among records.
- **A record** is a file under a live entity's `sources/` or under `archive/meetings/`, or, unfiled, under `triage/`. A text file (`.md`, `.txt`, `.eml`) names the person in its content; any other file only in its name.
- **A row** is one row of a register a lifecycle declares as a row home. A row under `## Closed` is `closed`.

## By hand

1. **Cards.** Glob `areas/network/**/*.md`, leaving out `README.md` and `actions.md`. Grep each address over them, then match each name against every card's `# ` title, `**Aliases:**` and `Also:` lines and file name, by the rungs above.
2. **Each matched card.** Read it: the header lines, every open `- [ ]`, and every link into `projects/`, `areas/` or `resources/ideas/`. Then Grep the card's file name over every entity's `README.md` and `brief.md` for the briefs linking it back.
3. **Each entity.** Read its document's Stage line and header lines, match the stage against the lifecycle tables in `CLAUDE.md`, and look for a do-not-raise label or heading. Count the open items in its `actions.md` and take the earliest dated one. Glob its `sources/` and take the newest by date prefix.
4. **Mentions.** Grep for `- [ ]` lines naming the person, by the rules above, over every `actions.md` outside `archive/` and `resources/`, and every card but the person's own. Skip what sits inside a fence.
5. **Records.** Glob `projects/**/sources/**`, `areas/**/sources/**`, `resources/ideas/**/sources/**` and `archive/meetings/**`; Grep the card's file name, the addresses and the whole names, and match file names; keep the five newest by date prefix. Grep `triage/` the same way for the unfiled ones.
6. **Rows.** Grep each declared row-home register for the person's whole names and addresses.
