# Gather (Steps 2 and 3)

## Who attends

The agenda is `/para-daily-brief`'s, read by [its Step 5c](../../para-daily-brief/references/signals.md#step-5c-build-the-agenda). Leave out the operator (the calendar's own address, or the vault's principal), rooms and other resources, and anyone who declined.

- **A calendar event**: its attendees, each passed as `Name <address>`, or the address alone.
- **A `meetings.md` line, or an event listing nobody**: the people a field or the title names ("Weekly status with Jan"), as written. Naming nobody, ask who is coming.

## What the scan returns

| Field | Holds |
|---|---|
| `vault`, `today`, `root` | The vault root, the date ages are measured against, and the root check (`root`, `missing`) |
| `lifecycles` | The declared lifecycle headings |
| `cards_hold` | `yes`, `relationship only` or `never`, from the checkbox table; at `never` a person's open items are all `mentions` |
| `people[]` | Per `--person`, in order: `query`, `name`, `email`, `status` (`matched`, `ambiguous`, `no_card`), `matched_by` |
| `people[].candidates` | `ambiguous` only: the possible cards |
| `people[].card` | `matched` only: `path`, `name`, `aliases`, `kind`, `header`, `emails`, `items` (its open checkboxes) |
| `people[].entities` | `matched` only: `{path, via}`, `via` being `card` (the card links it), `entity` (it links the card) or both |
| `people[].mentions` | Open items naming the person in any other file: `file`, `line`, the markers, `by` |
| `people[].records`, `records_total` | The five newest files naming the person in a live `sources/` or `archive/meetings/`, with `date`, `days_ago`, `by`; and the total |
| `people[].unfiled` | `{path, by}` per `triage/` item naming the person, undated: date it by its content |
| `people[].rows` | Register rows naming the person: `register`, `line`, `name`, `closed`, `stage`, `cells`, `by` |
| `entities[]` | Per entity a matched card ties to: `path`, `document`, `title`, `stage`, `header`, `unknown` (fields reading `unknown`), `do_not_raise`, `actions` (`path`, `open`, `next`), `newest_source` |
| `entities[].stage` | Null unless at a declared stage: `lifecycle`, `name`, `qualifier`, `since`, `days_in_stage`, `dated_facts` (`days_ahead`), `terminal`, and `columns`, the stage's lifecycle row as written (`Exit criterion` among them) |

**Null is not empty**: a null `mentions`, `records`, `unfiled` or `rows` was never searched (an `ambiguous` person, or a one-word name with no card).

## How much a match is worth

`matched_by` and `by` name how the person was found. Name the address a weak `email_name` match rests on, and weigh a `short name` (one word of the card's names that no other card carries) before quoting it.
