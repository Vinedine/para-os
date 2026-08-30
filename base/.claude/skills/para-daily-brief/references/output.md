# Rendering the brief (Step 6)

Exact terminal layout, filtered to the argument's sections. Always start with the H1 title. Sections with no content are omitted - no empty placeholders.

````
# Daily Brief - <YYYY-MM-DD> - <vault name>

## 📊 Vault state
```
[P] ticketing-platform-replacement  ██████████ 14 open · 2 🔴 · 10 undated
[P] cashless-stadium-rollout        █████░░░░░  7 open ·         5 undated
[A] network (17 files)              ███░░░░░░░  4 open · 1 🔴 ·  2 undated
(+N more entities · M open)
```
**Totals:** N open · N 🔴 overdue · N dated · N% undated

## 🗓 Agenda
**Today**
- <time> · <title> · <where/attendees> ·(source when useful)
**This week**
- <Dow DD> · <time> · <title>
*(+N upcoming · recurring: <cadences>)*

## 🎯 Now (5 of N)
1. 🔺 <task text> - [<scope>:<line>](<relative/path>#L<line>) · 📅 <date> (<Nd> ago)
2. ...
**Later:** N this week · N next 30 days · N later · N recurring · N waiting · N undated

## 🚩 Health flags
- <flag lines>

## 💡 Ideas (N)
- <idea-name> - touched <YYYY-MM-DD> - <Stage line, when present>
- <idea-name> - touched <YYYY-MM-DD> - ⚠️ dormant 6+ months, retirement candidate

## 📥 Triage (N to process)
- [<filename>](triage/<filename>)

---
**Next action:** <exactly one concrete step - see below>
````

The 📊 Vault state rows (top 10 entities by open count, remainder aggregated to the `(+N more)` line) render inside their own fenced code block so the columns align. Bar rows: width 10, `round(10 x open / max_open)` filled `█`, padded with `░`. Entity labels left-aligned to one width. In `all`, append the full bucket sections (🔴 🟠 🟡 🔵 ⚪ 🔁 ⏳ ❓, each a complete list in the Now line format) after Health flags.

**Line rules:** one line per task, no wraps; priority emoji at bullet start when present; date suffix in parens ("(22d ago)", "(in 5d)"); link text `<scope>:<line>` so the entity is visible without opening the file; relative link targets from CWD.

**The Next action close.** Exactly one item: concrete, startable in roughly two minutes, chosen from the Now list (or, when Now is empty, the most Vision-advancing undated item). Prefer the item that unblocks others or advances the Vision. Phrase it as the *first physical step* ("Open X and check Y"), not the whole task, and link it. One - never a list, never a question.

## Example fragment

```
## 🎯 Now (5 of 14)
1. 🔺 Score the two remaining ticketing vendor bids - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13) · 📅 2026-03-31 (22d ago)
2. Jan to send the legacy POS transaction export - [cashless-stadium-rollout:7](projects/cashless-stadium-rollout/actions.md#L7) · 📅 2026-04-02 (20d ago)
**Later:** 4 this week · 2 next 30 days · 1 recurring · 6 undated

---
**Next action:** Open the two vendor bid PDFs and re-read your scoring notes from March - [ticketing-platform-replacement:13](projects/ticketing-platform-replacement/actions.md#L13)
```
