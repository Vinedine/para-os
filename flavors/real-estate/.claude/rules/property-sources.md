---
paths:
  - "resources/ideas/*/sources/**"
  - "projects/*/sources/**"
  - "areas/properties/*/sources/**"
  - "archive/properties/*/sources/**"
  - "archive/researched-deals/*/sources/**"
  - "resources/mds/resources__ideas__*__sources__*"
  - "resources/mds/projects__*__sources__*"
  - "resources/mds/areas__properties__*__sources__*"
  - "resources/mds/archive__properties__*__sources__*"
  - "resources/mds/archive__researched-deals__*__sources__*"
---

# Property source documents

How a document is named inside a property's `sources/`, the same at every stage. A convention extending [filing.md](filing.md), whose rules all still apply: this file adds a unit scope and which party is `<Who>`. A non-property project's `sources/` follows `filing.md` alone. The `resources/mds/` globs cover a read-only-iPad vault in collected state; anywhere else they match nothing.

## Naming

```
YYYYMMDD <Who> <Description>[ <Unit scope>].<ext>
```

- **`<Who>`** by document type:
  - Lease, deposit, check-in inventory, notice: the tenant's surname
  - Contractor work: the contractor
  - Permit or decision: the issuing authority
  - Deed or conveyance: whoever executed it
  - Utility: the provider
  - Insurance: the insurer
  - Certificate or inspection of one unit: omitted, the unit scope identifies it
- **`<Unit scope>`**, on a unit-specific document only: the unit as the dossier's units table names it, or `Common Parts`.
- **A field that cannot be identified is left out**, never guessed. A personal suffix a scanner or sender added is dropped on rename.

## Exceptions

- **`photos/`** keeps the camera's filenames.
- **`plans/`** keeps the drawing numbers; revisions group in dated or named subfolders.
