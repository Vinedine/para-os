# Steps 1 to 4 - Setup, cleanup and enrichment

## Step 1 - Setup

1. **Resolve the vault root** once and hold it (`operating-discipline.md`). Resolve the property to exactly one folder and its dossier (`brief.md` in `projects/` or `resources/ideas/`, `README.md` in `areas/properties/`); none or several, stop and ask.
2. **Note the mode**: **acquisition** for a prospect or a deal in progress, **hold review** for a property in `areas/properties/`.
3. **Recommend `/property-reconcile` first** when `sources/` holds files newer than the dossier's last material edit, the dossier states two values for one load-bearing number, or it projects a cost an invoice shows already paid.

## Step 2 - Focused folder cleanup

Scoped to the target folder, never a vault-wide clean.

1. **Source filenames.** List `<folder>/sources/**` and propose a rename, with the reason, only for a file that conforms to neither `filing.md` nor `property-sources.md`. Never move the folder from one convention to another. Apply after approval.
2. **Dossier freshness.** Check the dossier against `property-dossier.md`: missing sections for its stage, placeholders that should now be real, stale numbers, people named without a link to their card. For each projection line, open the source it cites and confirm the dossier's description of it (date, scope, basis) still holds, not only the number.
3. **Near-duplicates.** Documents of one type, date and party are compared, never assumed identical: a difference in parties, clauses or signatures is a finding, and the dossier cites the copy actually signed.
4. **No sources for a deal in progress, or an empty-stub dossier, stops the run** with the checklist of what to provide.

## Step 3 - Email enrichment

Read the mailboxes the vault's `## Triage sources` declares, **read-only**, with the tools the dispatch table in [para-shared/connectors.md](../../para-shared/connectors.md) names. That file is the triage fetch; this is a lookup, so it takes neither the row's `Relevant when` filter nor its query frame and `newer_than` window. A `fetch-script` mailbox is searched with the script's `search` subcommand in place of `fetch` (a script without one reaches only its fetch window; say so). A preview is not evidence: a hit the decision turns on is read in full, attachments included, as the script's README says. No declared mailbox, or a connector that is not connected: skip the step and say so. A search that errors is reported and the run moves on.

1. **Search for the property**: street and number, the agent, seller, tenant, conveyancer and lender names already in the dossier, and its references (listing, loan, file). Fetch the promising threads.
2. **Extract what a decision turns on**: asking price and negotiation history, key dates (agreement, deed, viewings), quotes and conditions from the agent or conveyancer, the state of a loan application, energy or inspection mentions, renovation quotes, the architect's or engineer's own cost estimates, and an authority's pre-advice or remarks, read against the design actually filed.
3. **Write it into the dossier**, citing sender and date inline.
4. **Network cards.** For a new person of substance (agent, seller, conveyancer, architect, contractor, lender), create their card with `/para-new`, or edit an existing card in place, and cross-link both ways. A contact whose primary card lives in another vault gets a pointer line, never a copy.

## Step 4 - Register and web enrichment

1. **Read the register first**, all of it, and act on each source's access class as it defines. Never re-test a dead end or hand-roll a lookup the register already covers. A source you use that it does not list gets a row, proposed with the rest of this step's changes.
2. **Run the parcel lookup** where the register names one, with the full address from the dossier. Write the parcel identifier, building count and unit breakdown into Snapshot and Permits & compliance in this run: `/property-dealsheet` prints only what the dossier holds. A low match score or no result is a question, not a guess. With no lookup named, leave the parcel identifier as an open item unless a source document already gives it.
3. **Read the unit breakdown against the register's traps.** A registry's physical division says nothing about the legal one or the permitted state: those come from the documents the register names.
4. **Listings and comparables.** `WebSearch` and `WebFetch` the listing on the portals the register names, and recent comparables nearby: asking and, where available, closed prices, rent levels, days on market, price history. **Label every comparable as asking or closed**; where closed prices are paywalled, the dossier says most of what was reached is asking. Capture figures when first seen.
5. **Write the findings into the dossier**, each with its source. With no solid comparables, say so rather than presenting weak ones as evidence.

**A hold review** runs the same steps for what has changed since the last review: current listing and rent levels nearby, a new energy or permit obligation, a lease or refinancing event in the mailbox. It does not re-derive facts the dossier already holds from documents.
