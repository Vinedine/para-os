---
paths:
  - "triage/**"
  - "**/sources/**"
  - "resources/mds/triage__*"
  - "resources/mds/*__sources__*"
---

# Filing source documents

How a document is named and where it lives once it leaves `triage/`. A convention, not a document shape: it applies to every file filed, whatever folder it lands in. The `resources/mds/` globs cover a read-only-iPad vault in collected state; anywhere else they match nothing.

## Naming

Match the folder you are filing into. Never mass-rename existing files to move a folder from one convention to another.

- **`YYYYMMDD <Who> <Description>.<ext>` is the default**, for one-off dated documents: invoices, letters, contracts, statements. The date is the one on the document itself (issue, signing, inspection), never the date it arrived. `<Who>` is the most identifying party; `<Description>` is the document type, ending in any reference number it carries. A vault that uses another default changes it here and in its `CLAUDE.md` one-liner together.
- **A folder that already follows a variant keeps it.** A folder established on `YYYYMMDD_<Description>_<Ref>.<ext>` stays underscored, so its listing stays sortable and consistent. The vault's own copy of this file names each variant and the folders it holds in.
- **A document attesting to a period files under the period it covers.** Annual attestations (tax, insurance, institutional certificates, loan interest) are `YYYY - <Issuer> - <Person>.<ext>`, one per year per person, and the year is the one covered, not the one issued: an attestation for 2019 income issued in 2020 files as `2019 - ...`.
- **A machine-generated export keeps the name its system produced.** The filename is part of the export's identity.
- **An executed filing rule outranks everything above.** Where a vault script names and files a document type, run it and never file that type by hand: `/para-triage` runs the script instead of proposing a destination and a name. The vault's `CLAUDE.md` names each such script in one line.

## Where it lives

- **By function, not by issuer.** One issuer's documents scatter by what each is about: a bank's loan attestation for a property files with the property, the same bank's account statement with the account.
- **One entity or several.** A document about one entity lives with that entity. A snapshot across several (every loan, every account) lives in the vault's cross-cutting area, `areas/business/sources/` unless the vault's copy names another, whoever issued it.
- **Project and area.** When a project's raw documents belong to an area (a renovation on a property), the documents stay in the area's `sources/` and the decisions and execution in `projects/<name>/`, cross-linked both ways.

## Sources and working files

- **`sources/` holds originals; a working file sits at the containing folder's root.** A spreadsheet or CSV someone actively maintains (a reconciliation worksheet, a running ledger, a tracker) is a working file.
- **A machine-generated export is a source, even in an editable format.** A system's statement CSV or report xlsx is a raw artifact and belongs in `sources/` beside its PDF twin. The test is authorship, not file extension: only a file maintained by hand goes to the root.

## What not to file

- **No proof-of-payment for a routine payment.** Once an invoice is filed and paid, record the payment date and amount where the payment is tracked; the invoice in `sources/` is the documentation. The exception is a high-value one-off, a disputed payment, or anything an accountant needs for a filing: ask first.
