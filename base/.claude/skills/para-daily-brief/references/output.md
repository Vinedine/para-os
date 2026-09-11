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
**Totals:** N open · N 🔴 overdue · N upcoming · N undated (N%)

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

**Line rules:** one line per task, no wraps; priority emoji at bullet start when present; date suffix in parens ("(22d ago)", "(in 5d)"); link text `<scope>:<line>` so the entity is visible without opening the file; relative link targets from CWD. **A heading's `(N)` count must match the number of items rendered under it**, which means an overdue recurring item increments both the `🔴 Overdue` heading count and the `🔁 Recurring` heading count, even though the `Totals:` line counts it strictly once under Recurring.

**Percent-encode every link target.** Vault filenames carry spaces, commas, `#`, `&` and brackets - `triage/` worst of all, since its names come from mail subjects - and a raw one produces a link that looks right and resolves nowhere. Encode the path, never the link text: `triage/20260909 Nieuw e-Box bericht.md` is written `[20260909 Nieuw e-Box bericht.md](triage/20260909%20Nieuw%20e-Box%20bericht.md)`. A `#` in a filename must be encoded as `%23` or it truncates the target at the fragment.

## The Type B vault

Same layout, minus the sections the task scan feeds (SKILL.md Step 1b). Keep the H1, then 🗓 Agenda, 🚩 Health flags (the over-grown-brief flag only, when it fires), 💡 Ideas, 📥 Triage and the **Next action** close, in that order. One italic line under the H1 says why the task sections are absent - action tracking is absent by design, not missing - and that line is the only place it is mentioned; do not repeat it per section.

The triage heading keeps its canonical form, `## 📥 Triage (N to process)`. It is not retitled for this vault type, and it does not carry "run /para-triage": the Next action close says what to do, which is its job in every scope.

## The entity scope

A different layout, not the vault brief with rows removed. The question is "where does this one thing stand", so the buckets lead and nothing is capped.

````
# <entity> - <YYYY-MM-DD>

**[P] projects/<entity>** · N open · N 🔴 overdue · N upcoming · N undated · actions.md touched <YYYY-MM-DD>

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

- **Every open item renders**, in the same one-line format as Now. The five-item cap is a vault-wide device and does not apply.
- **Empty buckets are omitted**, like everywhere else. The four low-urgency buckets share one heading line when each is small; give any of them its own section once it exceeds five items.
- **The header line replaces 📊 Vault state.** One entity does not need a bar chart of itself.
- **`🔗 Mentioned elsewhere` is not this entity's work.** It is the second grep from task-scan.md, rendered so an item filed on a contact or in `areas/business/` is visible from here. Its counts never join the header totals, and each line names the file that owns it.
- **Health flags are filtered to this entity** (over-threshold, stale, falsely-overdue, stale recurrence, over-grown brief). The vault-wide ones - misplaced checkboxes, undated majority - are not computed.
- **The Next action still closes it**, chosen from this entity's own items only, never from `🔗 Mentioned elsewhere`.

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
