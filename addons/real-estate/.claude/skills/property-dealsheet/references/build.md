# Readiness check, build and verify

## The readiness check (Step 1)

The dossier must carry:

- **The deal's figures**: price or prices, plus a bid zone and walk-away while the price is open, or, once it is contracted, the cost ceiling and sale or rent floor (the works ceiling for an own home); capital deployed as booked, with its as-of date, for a held property
- **A verdict** backed by underwriting numbers (yield or margin, or the equity at risk for an own home, and the scenarios; while a permit is undecided, the scenarios are its outcomes)
- **A rent roll or a renovation scope**, per the stage variant
- **Key facts**: parcel or title identifier with the building and unit count, the parties (agent, seller, whoever executes the deed), financing (while Prospecting, the funding route wherever the dossier states it: a prospect carries no financing section yet), and the energy rating
- **Every figure the sheet prints**, written in the dossier: the cost basis and each of its lines, each scenario's margin or yields, the per-unit amounts. One the sheet would have to work out from others is missing, however easily the dossier's numbers give it, and so is a total whose parts, summed by running code, do not equal it, as `property-dossier.md`'s Derived figures says
- **An open-items list**
- **Per-unit area and price**, and the costs of dividing the building, where the dossier prices the property per unit

A field the dossier marks `_n/a_` with its reason passes (a private sale has no agent). Anything else missing: **stop** and report the gaps as a checklist naming what fills each (`/property-underwrite`, or `/property-reconcile` for an unverified fact), except a fact the register lists under facts no free source settles, which ships as the register says. No image is a gate.

**An existing sheet is checked too.** List its verdict and scenario figures and confirm each traces to the dossier; one that does not is a `/property-underwrite` gap, reported as such, and the rebuild drops it.

## Building the sheet (Step 2)

Follow the template's header comment: copy-fill, the stage variant, cost lines, pagination. Then:

1. **Where it goes**: `<property folder>/<property>-dealsheet.html`, beside the dossier. A rebuild replaces it.
2. **A building sold unit by unit** gets the template's per-unit table, and its cost basis shows the costs of dividing it (legal division, surveys, per-unit certificates and inspections, meters) as the dossier's own lines.
3. **Images**, as data URIs, no external reference:
   - **Plan image**: where the register names a plan renderer, run it from the vault root with the dossier's parcel identifier. Without one, use the facade or a site photo in that slot, or drop the image column.
   - **Facade photo**: reuse the previous sheet's when unchanged; otherwise take it from `sources/photos/` or a `sources/` PDF. With none, follow the template's no-photo instruction.
4. **Footer**: says the sheet is derived from the dossier, as of the date of the dossier's last material edit.

## Verify and report (Step 3)

The HTML is the deliverable. Read it back for an unfilled `{{placeholder}}`, an unreplaced image token or a dropped section, fix, and report the HTML path.

Report the verdict quoted from the dossier and the open items the sheet prints.
