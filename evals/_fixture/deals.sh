#!/usr/bin/env bash
# Appends a sales-module deal lifecycle onto the vault vault.sh already built. Sourced
# after vault.sh (which defines `day()`), never standalone. Dates are written relative to
# the day of the run, same rule as vault.sh.
#
# The shape is deliberate. One deal (northwind-quoting) sits at Proposal with a price
# hold expiring inside the 14-day window and a champion whose contact file carries the
# next dated step, so the expiry flag and the closing next action both have somewhere to
# land. A second deal (harbor-freight-labs) sits at Qualified, untouched for 30 days, with
# no actions.md, no mention in any other actions file, and a champion file whose next
# actions are empty: every source in the next-step search comes up empty, so the no-next-
# step flag fires without a step being invented for it. A third (old-mill-bakery) is
# already Lost, feeding the terminal metrics. The register carries one lead with a next
# step still ahead and one gone quiet on last touch with an undated next step.
set -e

cat >> CLAUDE.md <<'EOF'

## Deal lifecycle

A deal's PARA home follows its stage, and the stages are the phases the prospect hears in the room. A deal is **won** when a first paid phase is agreed, which is the base promotion rule wearing this module's vocabulary.

| Stage | Exit criterion | PARA home |
|---|---|---|
| Lead | A first conversation has been held | `areas/business/leads.md` (row) |
| Qualified | Fits a target profile in `README.md`, and the signer is named | `resources/ideas/<company>/` |
| Taste | Demo held, and recorded | `resources/ideas/<company>/` |
| Proposal | The signer has seen it, and the next meeting is dated | `resources/ideas/<company>/` |
| Goal | First paid phase agreed: promote | `projects/<company>/` |
| Nurture | A dated revisit action exists in the business area | `resources/ideas/<company>/` |
| Lost | Reason recorded, revisit trigger written | `archive/ideas/<company>/` |

## Entity structures

- **Deal brief** - a deal's brief and its register row carry the same seven header fields, in one order, `unknown` where a field is not yet settled. The full shape is in [.claude/rules/deal-brief.md](.claude/rules/deal-brief.md), which loads on its own when a deal brief or the lead register is read; read it explicitly before creating one.
EOF

mkdir -p .claude/rules
cat > .claude/rules/deal-brief.md <<'EOF'
---
paths:
  - "resources/ideas/*/brief.md"
  - "projects/*/brief.md"
  - "archive/ideas/*/brief.md"
  - "areas/*/leads.md"
  - "resources/mds/resources__ideas__*__brief.md"
  - "resources/mds/projects__*__brief.md"
  - "resources/mds/archive__ideas__*__brief.md"
  - "resources/mds/areas__*__leads.md"
---

# Deal brief

**Order:** fixed for the header block; free below it, where the vault's own brief shape governs.

One document per deal, from Qualified on. The header is the seven lines below, directly under the title, every one present. Everything under it is an ordinary brief of the vault's own shape: what the work would be, why now, the open questions, and the one prose "revisit when X" trigger. Its `sources/` folder holds the dated records (a demo recording, a sent proposal, a call note) as any entity's does.

These paths also match ideas and projects that are not deals, which follow the vault's own brief shape file: **this shape governs only the documents whose stage line names a stage of `## Deal lifecycle`**, and nothing else. The `resources/mds/` globs cover a read-only-iPad vault in collected state; anywhere else they match nothing. The one register glob covers the lead register, whose rows carry the same fields as columns.

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
```

1. **Stage** - a stage name from `## Deal lifecycle`, then `(since <date>)` for the day it entered that stage, semicolon-separated from any dated fact that expires (a price validity, an option, a quoted lead time). `/para-pipeline` reads the first for days in stage and the second for its expiry flag, so a fact with a date belongs here rather than in the prose.
2. **Opened** - the day the deal entered the lifecycle, at whatever stage. It never changes, and the median time to a won deal is measured from it.
3. **Source** - one of `referral from <contact link>`, `inbound via <channel>` (the site, a post, an event) or `outreach`, then a comma and the channel word. The referrers table is computed from these lines, so no contact file carries a "referred us" line of its own.
4. **Champion** - a link to the contact file of the person carrying this inside the company. The deal's next step is the earliest dated open item in that file, which is where `/para-pipeline` looks, so a deal without a champion file has nowhere to keep one.
5. **Signer** - who can commit the money, `unknown` until named. It is flagged from the second stage on, because the person who is excited is often not the person who signs.
6. **Value** - the internal number, with the basis in parentheses. It renders in a terminal and is never a public output.
7. **Last touch** - `<date>, <what happened>`, rewritten by hand after every contact. It is the single field the staleness flag reads.

**The next step is not a header line.** It lives where the vault's action rules already put it: the champion's contact file under its next-actions heading, the project's `actions.md` once promoted, or the register row's own column. Written into the header as well it becomes the one field typed twice, and the copy is the one that goes stale.

**A lost deal carries one more line**, directly under `Stage`: `**Lost reason:** <reason>, <one free clause>`, the reason being one of **no decision**, **timing**, **budget**, **went elsewhere**, **not a fit**, **relationship only**. The free clause is what a later reader needs and the list cannot hold. `/para-archive` refuses the move to `archive/ideas/` without it.

## The register row

The lead register named in `## Deal lifecycle` is one table under `## Open` and a second under `## Closed`, both with these columns in this order:

| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |
|---|---|---|---|---|---|---|---|

- **Company** is the row's name and the folder slug it would earn at Qualified. **Contact** is a name, not a link: a lead has no contact file yet.
- **Source**, **Opened**, **Stage** and **Last touch** carry exactly what the header lines of the same name carry.
- **Next step** is the step and its date, and it is the one place a next step lives outside an actions file, because a lead has neither an actions file nor a contact file to hold one.
- **Outcome** is empty while the row is open. A row moves to `## Closed` with its outcome filled in (no reply, not a fit, went quiet), or leaves the register entirely for a folder at Qualified, with a line in the closed table saying where it went.

## Placeholders

A header field not yet settled carries `unknown`, never a blank and never a dropped line: a missing line reads as an oversight and `unknown` reads as the next thing to find out. `**Value:**` before there is a number carries `unknown (not yet scoped)`. A deal with no dated fact keeps `(since <date>)` alone, with no semicolon. An empty register section carries `_None currently._` under its heading rather than an empty table.
EOF

mkdir -p areas/business resources/ideas/northwind-quoting resources/ideas/harbor-freight-labs \
  archive/ideas/old-mill-bakery areas/network

cat > areas/business/leads.md <<EOF
# Leads

## Open

| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |
|---|---|---|---|---|---|---|---|
| meridian-facilities | Owen Park | inbound via website | $(day -12) | Lead | Send the scoping questionnaire 📅 $(day 5) | $(day -2) | |
| bramblewood-retail | Dana Voss | outreach | $(day -25) | Lead | Follow up on the proposal call | $(day -20) | |

## Closed

_None currently._
EOF

cat > resources/ideas/northwind-quoting/brief.md <<EOF
# northwind-quoting

**Stage:** Proposal (since $(day -3); prices hold to $(day 10))
**Opened:** $(day -20)
**Source:** inbound via website, contact form
**Champion:** [Pia Vermeer](../../../areas/network/pia-vermeer.md)
**Signer:** unknown
**Value:** at most €18,000 (proposal cap)
**Last touch:** $(day -3), proposal sent

## Why now

Their quoting process is still spreadsheet-based and the team wants a faster turnaround before the busy season.

## Open questions

- Which of the two product lines to price first.

## Revisit trigger

Revisit when the price hold lapses without a signed order.
EOF

cat > areas/network/pia-vermeer.md <<EOF
# Pia Vermeer

**Kind:** buyer

Ops lead at northwind-quoting, the champion pushing the rebuild internally.

## Next actions

- [ ] Confirm the signer with Pia before the price hold lapses 📅 $(day 7)
EOF

cat > resources/ideas/harbor-freight-labs/brief.md <<EOF
# harbor-freight-labs

**Stage:** Qualified (since $(day -30))
**Opened:** $(day -30)
**Source:** referral from [Tom Ekberg](../../../areas/network/tom-ekberg.md), network
**Champion:** [Tom Ekberg](../../../areas/network/tom-ekberg.md)
**Signer:** unknown
**Value:** at most €9,000 (proposal cap)
**Last touch:** $(day -30), discovery call

## Why now

A contract lab wanting a faster intake form, met at a conference.

## Open questions

- Whether they need multi-site support.

## Revisit trigger

Revisit when Tom confirms budget for next quarter.
EOF

cat > areas/network/tom-ekberg.md <<'EOF'
# Tom Ekberg

**Kind:** buyer

Lab manager at harbor-freight-labs, first conversation at a conference.

## Next actions

_None currently._
EOF

cat > archive/ideas/old-mill-bakery/brief.md <<EOF
# old-mill-bakery

**Stage:** Lost (since $(day -6))
**Lost reason:** went elsewhere, picked a cheaper freelancer instead
**Opened:** $(day -10)
**Source:** outreach, cold email
**Champion:** unknown
**Signer:** unknown
**Value:** at most €4,000 (proposal cap)
**Last touch:** $(day -6), closing email sent

## Why now

Wanted an online ordering page before the busy season.

## Revisit trigger

Revisit if they mention pricing again next year.
EOF
