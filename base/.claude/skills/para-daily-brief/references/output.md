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

**The lifecycle line follows Totals**, one per declared lifecycle, stages in the table's own order and omitted where the vault declares none.

**A triage item the scan's `triage_preview` marks `auth` is never listed**: it is counted on the codes line, which is omitted at zero ([connectors.md](../../para-shared/connectors.md#sign-in-and-security-codes)).

The 📊 Vault state rows (top 10 entities by open count, remainder aggregated to the `(+N more)` line) render inside their own fenced code block. Bar rows: width 10, the row's `bar` (10 x open / max open, rounded half-up) filled `█`, padded with `░`. Entity labels left-aligned to one width. In `all`, append the full bucket sections (🔴 🟠 🟡 🔵 ⚪ 🔁 ⏳ ❓, each a complete list in the Now line format) after Health flags.

**Line rules:** one line per task, no wraps; priority emoji at bullet start when present; date suffix in parens ("(22d ago)", "(in 5d)"); link text `<scope>:<line>`, or `<person>:<line>` from the scan's `person` field for a contact item; relative link targets from CWD. **A long task text is cut, never wrapped:** link syntax and emphasis reduced to their text, then to its bold lead where it has one, else to its first clause (up to the first `;`, ` - ` or [sentence end](signals.md#step-4d-ideas-lane) outside parentheses), and to 100 characters at a word boundary with `…` if still longer. **A heading's `(N)` counts the items rendered under it**: a recurring item overdue or due today counts under both its date bucket and `🔁 Recurring`, while `Totals:` counts it once, under Recurring.

**Percent-encode every link target** (spaces, commas, `#`, `&`, brackets), never the link text.

## The entity scope

A different layout, not the vault brief with rows removed: the buckets lead and nothing is capped.

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

- **Every open item renders**, in the same one-line format as Now.
- **Empty buckets are omitted.** The four low-urgency buckets share one heading line when each is small; give any of them its own section once it exceeds five items.
- **The header line replaces 📊 Vault state.**
- **`🔗 Mentioned elsewhere` is not this entity's work.** It is the second grep from task-scan.md. Its counts never join the header totals, and each line names the file that owns it.
- **Health flags are this entity's only**, as signals.md Step 4c scopes them.
- **The Next action still closes it**, chosen from this entity's own items only, never from `🔗 Mentioned elsewhere`.

**The Next action close.** Exactly one item: concrete, startable in roughly two minutes, chosen from the Now list (or, when Now is empty, the most Vision-advancing undated item). Prefer the item that unblocks others or advances the Vision. Phrase it as the *first physical step* ("Open X and check Y"), not the whole task, and link it. Never a question.

## Example fragment

```
## 🎯 Now (5 of 14)
1. 🔺 Score the two remaining ticketing vendor bids - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13) · 📅 2026-03-31 (22d ago)
2. Jan to send the legacy POS transaction export - [cashless-stadium-rollout:7](projects/cashless-stadium-rollout/actions.md#L7) · 📅 2026-04-02 (20d ago)
**Later:** 4 this week · 2 next 30 days · 1 recurring · 6 undated

---
**Next action:** Open the two vendor bid PDFs and re-read your scoring notes from March - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13)
```
