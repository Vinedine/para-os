---
paths:
  - "resources/ideas/*/brief.md"
  - "projects/*/brief.md"
  - "areas/properties/*/README.md"
  - "archive/properties/*/brief.md"
  - "archive/properties/*/README.md"
  - "archive/researched-deals/*/brief.md"
  - "archive/researched-deals/*/README.md"
  - "resources/mds/resources__ideas__*__brief.md"
  - "resources/mds/projects__*__brief.md"
  - "resources/mds/areas__properties__*__README.md"
  - "resources/mds/archive__properties__*__brief.md"
  - "resources/mds/archive__properties__*__README.md"
  - "resources/mds/archive__researched-deals__*__brief.md"
  - "resources/mds/archive__researched-deals__*__README.md"
---

# Property dossier

**Order:** fixed. A section that does not apply stays, marked as in [Placeholders](#placeholders).

One document per property. From Acquiring on it carries the sixteen sections below: a flip and a rental differ only in which sections carry content, never in the order or the names. Prospecting, Sold and Dropped vary as [What each stage carries](#what-each-stage-carries) says, and the stage names are those of `## Property lifecycle` in the vault's `CLAUDE.md`. The filename follows the bucket: `brief.md` in `resources/ideas/` and `projects/`, `README.md` in `areas/properties/`; an archived property keeps the filename it had. These paths also match other projects and ideas, which follow `brief-structure.md`: a non-property one, and a works project on a held property, whose dossier is the area's `README.md`. The `resources/mds/` globs cover a read-only-iPad vault in collected state; anywhere else they match nothing.

## The shape

1. **H1 title** - the address; append `(sold)` once a bought property is sold, never to a deal that collapsed before the deed. Follow it with a one-line stage label: `_Stage: <stage> - <key date>_`.
2. **Snapshot** - one paragraph: type and units, parcel or title identifier, bought for X (date), the plan, the current stage. Links to the portfolio overview where the vault keeps one.
3. **Deal economics** - the headline block, and what the property is judged on. It carries **three kinds of number, never mixed in one table**:
   - **Contracted** - fixed by a signed or invoiced document: purchase price, transfer taxes, conveyancing fees, credit drawn, loans received. Each line cites the document.
   - **Booked** - straight from the owner's books, with its as-of date per [figures.md](figures.md). This is the authority on what a property has cost.
   - **Projected** - renovation estimate, target sale, expected margin. Estimates, marked as such, and never the basis for a cost claim.

   A held property opens this section with a **Capital deployed** summary (purchase + renovation rounds + total invested) and follows it with its running-cost summary. A margin is stated as realised only when a booked sale sits against a booked cost; a figure derived rather than read off a ledger line says so and shows the reconciliation. At every stage the underwriting's scenarios and verdict, with the bid zone and walk-away while Prospecting or Acquiring, close this section as projected figures.
4. **Timeline** - acquisition, permit, renovation, sale or letting, with dates, done and next.
5. **Ownership & financing** - who owns what share (a company or individuals, per unit where they differ), plus the financing stack: lender, loan reference, amount, rate, term, status, guarantees and collateral.
6. **Parties** - whoever executed the deed, architect, main contractor, agent, building manager, insurance broker: each linking its card in `areas/network/`.
7. **Background** - the sourcing story: seller, off-market or listed, what made the deal happen at that price.
8. **Permits & compliance** - planning permission status and reference, the legally permitted state and unit count, any legal division into units and each unit's share, hazardous materials, mandatory inspections, and the energy rating per unit where the register names one. The vault's source register names the local document that settles each.
9. **Units & sale status** - per-unit table. A flip: unit and scope, area, asking, sold, buyer, status. A held property: the unit split, area and per-unit ownership.
10. **Tenancy** - `### Active` and `### Former` tables: tenant, contract dates, rent, deposit, indexation.
11. **Utilities** - per provider (water, electricity, gas, heating, waste): account number, connection or meter id, tariff.
12. **Co-ownership** - owners' association or building manager and contact, the property's share, service charge, meeting cadence.
13. **Insurance** - policy table: insurer, policy number, annual premium, period, holder, plus history where it matters. A property under renovation carries its works policy here.
14. **Damage events** - one subsection per event (water, fire, burglary): date, scope, claim reference, broker, outcome.
15. **Open items / next steps** - what is still unknown or unconfirmed, phrased as what to confirm and with whom. Committed next steps follow the vault's action convention. A sold property titles it `Open items / residual flags` and records post-sale gaps rather than actions.
16. **Source documents** - `sources/` grouped (acquisition / permit / plans / renovation / leases / utilities / insurance / damage / sale / photos), each line citing the filename and a one-line description.

**Extra sections.** A property may carry one or two sections the list does not name, where the deal produced something that belongs nowhere else: a structural survey, a boundary dispute, a photo index. Place each next to the section it extends, and never invent one speculatively.

### What each stage carries

- **Prospecting** (`resources/ideas/`) - at least Snapshot, Deal economics, and an open-items section in the place of Open items. **Use the heading the vault's own next-steps convention already recognises** - `CLAUDE.md`'s Filing and naming section, or a vault-local pickup script such as `openstaande-punten.py`, names the exact heading text (and its language) a vault scans for; a prospect brief written under any other heading, however similar, silently drops off that pickup. Where the vault states no such convention, `## Open questions` then `## Next step` are the default. Any other section of the shape joins, in the shape's order, once there is a fact for it. It takes the full shape on promotion.
- **Sold** (`archive/properties/`) - the shape it had, plus a financing line saying how the credit closed.
- **Dropped** (`archive/researched-deals/`) - opens on five sections: H1 with a `(skipped)`, `(researched, not pursued)` or `(collapsed)` marker; one intro paragraph on the property and how far the research went; `## Status` (a table: address, type, asking price, source channel, stage when stopped); `## Source documents` (or `_None._`); `## Reason for skipping`. Every other section it carried follows unchanged.

## Placeholders

A section that does not apply gets `_n/a_` with a short reason (`_n/a_ - owner-occupied._`, `_n/a_ - unencumbered._`), never a bare `_n/a_` and never an omitted heading. A figure not yet known is marked in words inside its table (`_to confirm_`, `_pending_`, `_not yet computable_`), never left blank. A closed dossier says so in full: `_Fully closed (sold <date>); the flags below are historical, no action outstanding._`
