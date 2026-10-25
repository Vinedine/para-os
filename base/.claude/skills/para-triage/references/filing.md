# Inspecting and filing a loose file (Steps 3 and 4)

## Inspect (Step 3)

- **Read it**, rendering a PDF `Read` cannot (PyMuPDF, `pypdfium2`) and decoding a saved message with `paraos_mail.py eml <file>` ([shared library](../../para-shared/scripts.md)). An encrypted one is proposed from its name and date, saying "(content not readable - name-only inference)"; with no renderer, ask before inferring from a name.
- **A staged note whose `Content` line says the operator's own messages were not fetched** is re-read at its source first, read-only, unless a filed survivor of that message exists: by `note.message_id`, never an id derived from `Link`; without one, a Gmail thread by `note.thread_id`, any other by sender and subject; through the mail connector or the fetch-script command its Content line gives. Judge it as a fetched thread ([sources.md](sources.md#connector-sources)); a fact found only there goes into the annotation or a follow-on edit, never the note. One no re-read can reach is judged on what it holds, its row saying so.
- **A Google-native stub** is converted first ([sources.md](sources.md#google-native-files)).
- **Capture** the document's own date, never the file's, and **a deadline only the operator can meet**, for **File it + add action**: a reply-by date, an unpaid invoice's due date, a renewing agreement's last day to give notice ([dated so](../../para-shared/operating-discipline.md#dating-a-renewing-agreement)).
- **Duplicates**: the scan's `duplicates` and `cross_vault` are byte matches, here and in a routed vault's `sources/`. Without one, a rescan or "copy 2" is compared field by field, a scan beside its digital original being **Delete (redundant scan)**.
- **Orientation**: rotate an image that renders sideways or upside down, whatever its EXIF says. A wrong-way PDF is flagged, rotated only on the operator's say.

## Choose a destination and a name (Step 4)

- **Find the entity**, `archive/` included, whose brief or README documents the file's parties, contract number or address, even before that entity's active window. A record (contract, invoice, signed letter) lands in its `sources/`. An item worth only the facts it carries (another tool's export, a recap), or one for a contact card, gives them to the entities they concern as follow-on edits naming it as their source, then gets its own **Delete (no lasting value)** question.
- **No entity matches**: a concrete subject the vault would hold (a prospect, a person, a deal) is **Add register row** where its lifecycle opens at a register, else **Create entity** (Recommended, naming the shape and folder), never a hand-built folder. A record no entity owns is **Delete (no lasting value)** where [its outcome survives](approval.md#choosing), else filed in `.claude/rules/filing.md`'s cross-cutting area. A file that looks like another vault's or context's is asked about first.
- **Name it** to the convention, dropping legacy suffixes (`- FINAL`, `copy`, `(1)`). A staged note's filename is a mail subject plus a hash: its `<Description>` follows the receiving folder's language.
- **The Why** names the signals used, never "matches the entity"; the **Destination** is `[<new name>](<relative path>)`.

## A meeting record

A dated record of a conversation (call note, minutes, a recorder's summary or transcript) filed for an entity whose shape declares `Last touch` adds these follow-on edits, each only where the shape declares its field. Read first the card the entity links as its contact (a deal's `Champion`). Everything comes from the record's own date and what was said: a bare title, invite or empty summary proposes Last touch at most, and no draft.

1. **Last touch**: `<the record's date>, <one clause on what happened>`, shown as `<current> → <proposed>`, where the record is newer or the current one is `unknown`.
2. **Signer**: where the record names who commits the money and the current value does not, shown the same way, linked to their card.
3. **One next step**: our earliest commitment as one checkbox, on the contact's card under its next-actions heading as far as `contact_card_level` allows (`relationship only`: a reply, introduction, thanks or check-in), else the entity's own: a register row's next-step cell, the owning area's `actions.md` (linking the brief) for an entity under `resources/`, a project's `actions.md`. **Their earliest commitment** is one `Waiting on [<person>](<card>): <what> (since <the record's date>)` line, no `📅`, homed the same way. Every other commitment goes in the draft. An open item the record shows done is proposed ticked; nothing is added twice.
4. **A stage question**, never a stage edit, where the record meets the current stage's exit criterion: `Move <entity> on from <stage>? Its exit criterion, <criterion>, looks met: <evidence>.`, repeated in the summary ([lifecycles.md](../../para-shared/lifecycles.md#what-each-skill-does-with-one)).
5. **A follow-up draft** per [drafting.md](../../para-shared/drafting.md): the agreed steps, our promises with their dates, the next meeting.
