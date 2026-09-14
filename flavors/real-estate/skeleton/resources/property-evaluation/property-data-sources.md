# Property data sources

Where property facts come from in {{jurisdiction}}, what each source can and cannot answer, and what it costs. The property skills take every local fact from this file: a registry, a document, a tax or a portal it does not name is never assumed.

## What each source answers

| Question | Source | Access |
|---|---|---|
| Parcel or title identifier, buildings on the parcel | {{land or title registry}} | {{free / login / paid}} |
| Whether the building is already divided into units | {{...}} | {{...}} |
| Cadastral or site plan | {{...}} | {{...}} |
| Assessed or taxable value, registered owner | {{...}} | {{...}} |
| Legally permitted state, permits and planning history | {{...}} | {{...}} |
| Title restrictions, easements, charges | {{...}} | {{...}} |
| Energy rating | {{...}} | {{...}} |
| Owners' association or building manager | {{...}} | {{...}} |
| Utility connections and meters | {{...}} | {{...}} |
| Asking prices and listings | {{portals}} | {{...}} |
| Closed sale prices | {{...}} | {{...}} |
| Area price statistics | {{...}} | {{...}} |

**Access** is one of three values, and the skills act on it: **free** is looked up; **login** sits behind a personal login, is never scripted, and is exported by the operator; **paid** is settled only by a paid request, named as a next step and never searched for.

## Facts no free source settles

The facts that stay pending until a login export or a paid request arrives. A gap listed here is a named next step, never drift or a stop: `/property-reconcile` reports it as unobtainable, and `/property-dealsheet` prints it as pending.

- {{fact}}: {{the request that settles it, and who normally orders it}}

## Lookup commands

{{A local script that answers one of the rows above, run from the vault root, or delete this section. `/property-underwrite` runs a parcel lookup named here, and `/property-dealsheet` a plan renderer; with neither, both skip that step.}}

```
{{parcel lookup "<address>"}}
{{plan renderer <parcel id> <file>.svg}}
```

## Transaction and holding costs

The rates `/property-underwrite` and the deal sheet use. Tax treatment (which structure, how a margin is taxed) is reasoning and belongs in the analyst persona's `knowledge/`; the numbers live here.

| Cost | Rate or amount | Basis |
|---|---|---|
| Transfer tax on purchase | {{...}} | {{...}} |
| Conveyancing ({{who executes the deed}}) | {{...}} | {{...}} |
| Agent fee on sale | {{...}} | {{...}} |
| Annual property tax | {{...}} | {{...}} |

## Traps

{{The local rules that decide real money and are easy to get wrong: a presumption that settles the permitted state for older buildings, a registry quirk that miscounts units, a portal whose "sold" prices are asking prices.}}

## Dead ends

{{Sources proven not to work (an anti-bot wall, partial coverage), so they are not retried.}}
