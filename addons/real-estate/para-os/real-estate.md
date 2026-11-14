# para-os real-estate flavor

The fixed rules of the real-estate flavor, the same in every vault that declares it. `/para-upgrade` replaces this file whole: never edit it. The vault's own `CLAUDE.md` **wins wherever the two differ**: a stage table it writes under the same heading replaces the one below.

## Property lifecycle

A property's PARA home follows its stage, and a property is **bought** on the deed: a signed purchase agreement makes it a deal in progress, not yet bought. The dossier and the deal sheet name stages only as below.

| Stage | PARA home |
|---|---|
| **Prospecting**: considering, visiting, analysing, an offer out | `resources/ideas/<property>/` |
| **Acquiring**, **Permitting**, **Renovating**, **Selling**: signed agreement to deed, then a flip's permit, works and sale | `projects/<property>/` |
| **Held**: bought and kept, let or vacant | `areas/properties/<property>/` |
| **Sold**: bought, then sold | `archive/properties/<property>/` |
| **Dropped**: never bought | `archive/researched-deals/<property>/` |

- **A property idea promotes on a signed purchase agreement or deed**, not on a scheduled go/no-go review.
- **A buy-and-hold purchase enters Held on the deed**, by hand, since no skill runs the move: `projects/<property>/` moves to `areas/properties/<property>/` under the move rules of `para-shared/operating-discipline.md`, and every inbound link is repointed.
- **A property already bought when it enters the vault** is created with `/para-new area`, its proposed path corrected to `areas/properties/<property>/` before approval.
- **Works, a refinancing or a sale on a held property** is its own project, `projects/<property>-works/` or similarly suffixed, with an ordinary brief linking the dossier, which stays in the area at stage Held.
- **A property's `sources/` is named one way at every stage.** The full convention (the `Who` ladder, unit scopes) is in `.claude/rules/property-sources.md`; read it explicitly before filing one.

## Entity structures

- **Property dossier** - a property's `brief.md` is its dossier at every stage: sixteen sections from Acquiring on, a lighter shape while Prospecting and once Dropped. The full shape is in `.claude/rules/property-dossier.md`; read it explicitly before creating one.

## Deal sheets

A **deal sheet** is the designed rendering of a property's dossier: `<property>-dealsheet.html` beside it, built by `/property-dealsheet` from `resources/prompts/dealsheet-template.html`.

- **The dossier is the source of truth; the sheet is derived**, and its footer says so. Never hand-type a number into a sheet: regenerate it.
- **One format.** The design system, section skeleton and stage variants are in the template's header comment. A new component goes into the template.
- **The pipeline** is `/para-triage` → `/property-reconcile` (verify against `sources/` and the books) → `/property-underwrite` (enrich, and analyse through the analyst persona under `resources/prompts/`) → `/property-dealsheet` (present). Each writes to the dossier except the last.
- **Where every property fact comes from**, what it costs, and which facts no free source settles is `resources/property-evaluation/property-data-sources.md`. Read it before any lookup.
- **Available capital and the owner's books** are where the vault's `CLAUDE.md` names them. A property's ledger account is the authority on its cost and stage.
