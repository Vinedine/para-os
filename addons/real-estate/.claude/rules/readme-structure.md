---
paths:
  - "projects/README.md"
  - "areas/**/README.md"
  - "resources/*/README.md"
  - "archive/**/README.md"
  - "resources/mds/projects__README.md"
  - "resources/mds/areas__*__README.md"
  - "resources/mds/resources__*__README.md"
  - "resources/mds/archive__*__README.md"
---

# README structure

**Order:** fixed for a property, not fixed for any other README. The `resources/mds/` globs cover a read-only-iPad vault in collected state; anywhere else they match nothing.

## The shape

**A property's README follows [property-dossier.md](property-dossier.md)**, which takes over every README its paths name: a held property in `areas/properties/`, a sold one in `archive/properties/`, a dropped one in `archive/researched-deals/`. The section order is there, not here.

Every other README is shaped by what it documents. Three conventions hold across them, and across every non-property brief ([brief-structure.md](brief-structure.md)):

- **A table up top** where the document tracks positions, accounts, or a portfolio.
- **Links out rather than restated figures**, per [figures.md](figures.md): a figure that belongs to a property lives in its dossier.
- **`## Open items / next steps` last.**

## Placeholders

As in [property-dossier.md](property-dossier.md#placeholders).
