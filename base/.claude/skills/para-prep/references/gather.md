# Gather (Steps 2 and 3)

`scripts/prep_scan.py` matches each attendee to a card and gathers what the vault holds on them; who attends is read from the agenda first.

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

`matched_by` names the rung that decided, strongest first: `email` (an address the card carries), `name` or `alias` (the whole name), `partial` (every word of the name in one card's names), then `email_name` (an address whose part before the `@` spells a whole name). The last is the weakest rung: say which address it was.

## What names a person

The `by` on a mention, a record or a row: `link` (to the card), `email`, `name` or `alias` (a whole name), `file name` (a whole name in a record's file name), or, in an open item only, `short name`: one word of the card's names that no other card carries. It is how "Raise with Jan" is found, and the likeliest to be wrong: weigh it before quoting it.
