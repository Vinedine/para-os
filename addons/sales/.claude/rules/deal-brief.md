---
paths:
  - "resources/ideas/*/brief.md"
  - "projects/*/brief.md"
  - "archive/ideas/*/brief.md"
  - "areas/*/leads.md"
---

# Deal brief

**Order:** fixed for the header block; free below it, where the vault's own brief shape governs.

One document per deal, from Qualified on. The header is the eight lines below, directly under the title, every one present except Won, which is written only once the deal reaches Goal. Everything under it is an ordinary brief of the vault's own shape: what the work would be, why now, the open questions, and the one prose "revisit when X" trigger. Its `sources/` folder holds the dated records (a demo recording, a sent proposal, a call note) as any entity's does.

These paths also match ideas and projects that are not deals, which follow the vault's own brief shape file: **this shape governs only the documents whose stage line names a stage of `## Deal lifecycle`**, and nothing else. The register glob covers the lead register, whose columns are in `## The register row`.

## The shape

```
# <Company>

**Stage:** Proposal (since YYYY-MM-DD; prices hold to YYYY-MM-DD)
**Opened:** YYYY-MM-DD
**Source:** referral from [<contact>](../../../areas/network/<contact>.md), network
**Champion:** [<contact>](../../../areas/network/<contact>.md)
**Signer:** unknown
**Value:** at most <amount> (proposal cap)
**Last touch:** YYYY-MM-DD, proposal sent
**Won:** YYYY-MM-DD
```

1. **Stage** - a stage name from `## Deal lifecycle`, then `(since <date>)` for the day it entered that stage, semicolon-separated from any dated fact that expires (a price validity, an option, a quoted lead time). `/para-pipeline` reads the first for days in stage and the second for its expiry flag, so a fact with a date belongs here rather than in the prose.
2. **Opened** - the day the deal entered the lifecycle, at whatever stage. It never changes, and the median time to a won deal is measured from it.
3. **Source** - one of `referral from <contact link>`, `inbound via <channel>` (the site, a post, an event) or `outreach`, then a comma and the channel word. The referrers table is computed from these lines, so no contact file carries a "referred us" line of its own.
4. **Champion** - a link to the contact file of the person carrying this inside the company.
5. **Signer** - who can commit the money, `unknown` until named. It is flagged from the second stage on, because the person who is excited is often not the person who signs.
6. **Value** - the internal number, with the basis in parentheses. It renders in a terminal and is never a public output.
7. **Last touch** - `<date>, <what happened>`, rewritten after every contact. It is the single field the staleness flag reads.
8. **Won** - the day the first paid phase was agreed, written by the promotion to Goal and kept unchanged when the delivery project later archives, so `/para-pipeline` can still count the deal as reached wherever it now sits.

**The next step is not a header line.** It lives where the vault's action rules already put it: the champion's contact file under its next-actions heading where the vault's `areas/network/` checkbox row allows it, an open item linking the deal brief, the project's `actions.md` once promoted, or the register row's own column. Written into the header as well it becomes the one field typed twice, and the copy is the one that goes stale.

**A lost deal carries one more line**, directly under `Stage`: `**Lost reason:** <reason>, <one free clause>`, the reason being one of **no decision**, **timing**, **budget**, **went elsewhere**, **not a fit**, **relationship only**. The free clause is what a later reader needs and the list cannot hold. `/para-archive` refuses the move to `archive/ideas/` without it.

## The proposal

- **The price comes from the vault's own deals.** Set it against two or three past deals' `**Value:**` lines, won and lost, shown to the operator with the arithmetic run in code. With no comparable, the price is a blank for the operator to fill, never a rate the draft invents.
- **The sent file is the client's.** It never carries the `**Value:**` line, the private read of the deal's risks, competitors, internal names or anything the brief lists as not to raise.

## The register row

The lead register named in `## Deal lifecycle` is one table under `## Open` and a second under `## Closed`, both with these columns in this order:

| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |
|---|---|---|---|---|---|---|---|

- **Company** is the row's name and the folder slug it would earn at Qualified. **Contact** is a name, not a link: a lead has no contact file yet.
- **Source**, **Opened**, **Stage** and **Last touch** carry exactly what the header lines of the same name carry.
- **Next step** is the step and its date, and it is the one place a next step lives outside an actions file, because a lead has neither an actions file nor a contact file to hold one.
- **Outcome** is empty while the row is open. A row moves to `## Closed` with its outcome filled in (no reply, not a fit, went quiet), or leaves the register entirely for a folder at Qualified, with a line in the closed table saying where it went.

## Placeholders

A header field not yet settled carries `unknown`, never a blank and never a dropped line: a missing line reads as an oversight and `unknown` reads as the next thing to find out. `**Value:**` before there is a number carries `unknown (not yet scoped)`. A deal with no dated fact keeps `(since <date>)` alone, with no semicolon. An empty register section carries `_None currently._` under its heading rather than an empty table. **Won** is the one field this does not apply to: before Goal the fact has simply not happened yet, so the line is omitted rather than carrying `unknown`.
