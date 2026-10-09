---
paths:
  - "triage/**"
  - "**/sources/**"
---

# Filing source documents

How a filed document is named and where it lives.

## Naming

Match the folder you file into, and never mass-rename a folder to another convention.

- **`YYYYMMDD <Who> <Description>.<ext>` is the default** for a one-off dated document. The date is the document's own (issue, signing, inspection), never its arrival; `<Who>` is the most identifying party; `<Description>` is the document type, ending in any reference number. A vault with another default changes it here and in its `CLAUDE.md` together.
- **A folder on a variant keeps it**: one on `YYYYMMDD_<Description>_<Ref>.<ext>` stays underscored. The vault's copy of this file names each variant and its folders.
- **A document attesting to a period files under the period it covers**: an annual attestation is `YYYY - <Issuer> - <Person>.<ext>`, the year the one covered, not the one issued.
- **A machine-generated export keeps its system's name**; a second of that name takes a numeric suffix (`statement-2.csv`).
- **An executed filing rule outranks everything above.** Where a vault script names and files a document type, run it and never file that type by hand: `/para-triage` runs the script instead of proposing a name. The vault's `CLAUDE.md` names each such script in one line.

## Where it lives

- **By function, not by issuer**: a bank's loan attestation for a property files with the property, its account statement with the account.
- **One entity or several**: a document about one entity lives with it; a snapshot across several lives in the cross-cutting area, `areas/business/sources/` unless the vault's copy names another.
- **Project and area**: a project's raw documents that belong to an area stay in the area's `sources/`, the decisions and execution in `projects/<name>/`, cross-linked.

## Sources and working files

- **`sources/` holds originals; a working file sits at the containing folder's root.** A spreadsheet maintained by hand (a reconciliation, a running ledger, a tracker) is a working file.
- **A machine-generated export is a source, even in an editable format**: a statement CSV belongs in `sources/` beside its PDF twin. The test is authorship, not extension.

## What not to file

- **No proof of payment for a routine payment.** Record the payment's date and amount where it is tracked; the filed invoice is the documentation. For a high-value one-off, a disputed payment or anything an accountant needs, ask first.
