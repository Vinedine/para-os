# Rendering the brief (Step 6)

Exact terminal layout, filtered to the argument's sections. Always start with the H1 title.

````
# Daily Brief - <YYYY-MM-DD> - <vault name>

## 📊 Vault state
```
[P] ticketing-platform-replacement  ██████████ 14 open · 2 🔴 · 10 undated
[P] cashless-stadium-rollout        █████░░░░░  7 open ·         5 undated
[A] network (3 with open items)     ███░░░░░░░  4 open · 1 🔴 ·  2 undated
(+N more entities · M open)
```
**Totals:** N open · N 🔴 overdue · N upcoming · N undated (N%)
**<Lifecycle>:** <Stage> N · <Stage> N · <Stage> N - `/para-pipeline` for the board

## 🗓 Agenda
**Today**
- <time> · <title> · <where/attendees> ·(source when useful)
**This week**
- <Dow DD> · <time> · <title>
*(+N upcoming · recurring: <cadences>)*

## 🎯 Now (5 of N)
1. 🔺 <task text> - [<scope>:<line>](<relative/path>#L<line>) · 📅 <date> (<Nd> ago)
2. ...
**Later:** N this week · N next 30 days · N later · N recurring · N waiting · N waiting on others (oldest N days) · N undated

## 🚩 Health flags
- <flag lines>

## 💡 Ideas (N)
- <idea-name> - touched <YYYY-MM-DD> - <Stage line, when present>
- <idea-name> - touched <YYYY-MM-DD> - ⚠️ dormant 6+ months, retirement candidate

## 📥 Triage (N to process)
- [<filename>](triage/<filename>)
- sign-in and security codes: N

---
**Next action:** <exactly one concrete step - see below>
````

**The Later line's `this week` counts every 🔴, 🟠 and 🟡 item not in Now**, so an overdue or due-today item the cap leaves out lands there. When Now is empty, the line renders alone, with no `🎯 Now` heading.

**The lifecycle line follows Totals**, one per lifecycle in the scan's `lifecycles`, stages in the table's order, zeros included; the board stays `/para-pipeline`'s.

**A triage item the scan's `triage_preview` marks `auth` is never listed**: it is counted on the codes line, which is omitted at zero ([connectors.md](../../para-shared/connectors.md#sign-in-and-security-codes)).

The 📊 Vault state rows (top 10 entities by open count, remainder aggregated to the `(+N more)` line) render inside their own fenced code block. Bar rows: width 10, the row's `bar` filled `█`, padded with `░`. Entity labels left-aligned to one width. In `all`, append the full bucket sections (🔴 🟠 🟡 🔵 ⚪ 🔁 ⏳ ❓, each a complete list in the Now line format) after Health flags.

**Line rules:** one line per task, no wraps; priority emoji at bullet start when present; date suffix in parens ("(22d ago)", "(in 5d)"); link text `<scope>:<line>`, or `<person>:<line>` from the scan's `person` field for a contact item; relative link targets from CWD. **A long task text is cut, never wrapped:** link syntax and emphasis reduced to their text, then to its bold lead where it has one, else to its first clause (up to the first `;`, ` - ` or [sentence end](signals.md#step-4d-ideas-lane) outside parentheses), and to 100 characters at a word boundary with `…` if still longer. **A heading's `(N)` counts the items rendered under it**: a recurring item overdue or due today counts under both its date bucket and `🔁 Recurring`, while `Totals:` counts it once, under Recurring.

**Percent-encode every link target** (spaces, commas, `#`, `&`, brackets), never the link text.

## The entity scope

A different layout, not the vault brief with rows removed: the buckets lead, and every open item renders in the Now line format.

````
# <entity> - <YYYY-MM-DD>

**[P] projects/<entity>** · N open · N 🔴 overdue · N upcoming · N undated · actions.md touched <YYYY-MM-DD>

The bucket letter and path are the resolved entity's, `[A] areas/<entity>` for an area. An entity whose open items live in several files (a contact area such as `areas/network/`) renders `N files, latest touched <YYYY-MM-DD>` in place of the `actions.md` clause.

## 🔴 Overdue (N)
1. 🔺 <task text> - [<entity>:<line>](<relative/path>#L<line>) · 📅 <date> (<Nd> ago)

## 🟠 Today (N)
## 🟡 This week (N)
## 🔵 Next 30 days (N) · ⚪ Later (N) · 🔁 Recurring (N) · ⏳ Waiting (N)
## ❓ Undated (N)

## 🔗 Mentioned elsewhere (N)
- <task text> - [<other-scope>:<line>](<relative/path>#L<line>) · *lives in <other entity>*

## 🚩 Health flags
- <flag lines, this entity only>

---
**Next action:** <exactly one concrete step>
````

Rules specific to this scope:

- **The four low-urgency buckets share one heading line** while each is small; any of them past five items gets its own section.
- **`🔗 Mentioned elsewhere` is not this entity's work.** It is the scan's `mentioned_elsewhere`, five lines then `(+N more)`. Its counts never join the header totals, and each line names the file that owns it.
- **The Next action still closes it**, chosen from this entity's own items only, never from `🔗 Mentioned elsewhere`.

**The Next action close.** Exactly one item: concrete, startable in roughly two minutes, chosen from the Now list (or, when Now is empty, the most Vision-advancing undated item). Prefer the item that unblocks others or advances the Vision. Phrase it as the *first physical step* ("Open X and check Y"), not the whole task, and link it. Never a question.

## The review scope

A look back over the window, every number from the scan's `review` block. The entity scope renders the same layout, titled `# Review - <entity> - <start> to <end>`.

````
# Review - <start> to <end> - <vault name>

**N done · N slipped · N moved · N decisions** over <the last 7 days | the last 30 days | since <start>>

## ✅ Done (N)
**[P] <entity>** (N)
- <task text> - [<scope>:<line>](<relative/path>#L<line>) · ✅ <date>
*N closed items carry no completion date, so no window counts them.*

## ⚠️ Slipped (N)
- <task text> - [<scope>:<line>](<relative/path>#L<line>) · 📅 <date> (<N>d late)

## 🔀 Moved
**<Lifecycle>:** N - <name> to <Stage> <date> · <name> to <Stage> <date>, closed

## 🧱 Stuck
- N overdue, the oldest: <task text> - [<scope>:<line>](<relative/path>#L<line>) · 📅 <date> (<N>d ago)
- No next step: <entity> · <entity>

## 🧭 Decisions (N)
- <date> · <entity>: <entry text> - [<scope>:<line>](<relative/path>#L<line>)

---
**Next action:** <exactly one concrete step>
````

- **Done groups by entity**, most closes first, each item in date order; an archived entity's row adds `(archived)`, and a contact's close is linked by `<person>:<line>` as in Now.
- **An undated close is never dated into the window.** The italic count line renders whenever `undated` is above zero, whatever the window holds.
- **Moved leads with its count**, one line per declared lifecycle and a quiet one included (`**<Lifecycle>:** nothing moved`); a terminal or closed move says so. The board stays `/para-pipeline`'s.
- **Stuck names the oldest overdue item only**, since Slipped already lists the recent ones, and at most three entities with no next step, plus a count.
- **Decisions render as written**, cut like a task.
- **An empty section is omitted**, Moved excepted; with nothing in the window at all, the count line alone says so.
- **The Next action** is the first step on the oldest slipped item, else on Stuck, by the rule above.

**For one entity, close by offering a status update** the operator can send: one line after the Next action, `Draft a status update for <entity>?`. On a yes, draft it in chat per [para-shared/drafting.md](../../para-shared/drafting.md), each recipient's address from their contact card: what was done (from Done, in plain words), what is next (the entity's soonest open items), and what we need from you (the open items waiting on the recipient's side, a paragraph omitted when none is). No links, counts, flags or undated closes.

## Example fragment

```
## 🎯 Now (5 of 14)
1. 🔺 Score the two remaining ticketing vendor bids - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13) · 📅 2026-03-31 (22d ago)
2. Jan to send the legacy POS transaction export - [cashless-stadium-rollout:7](projects/cashless-stadium-rollout/actions.md#L7) · 📅 2026-04-02 (20d ago)
**Later:** 4 this week · 2 next 30 days · 1 recurring · 6 undated

---
**Next action:** Open the two vendor bid PDFs and re-read your scoring notes from March - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13)
```
