# Delivery: readonly-ipad

One person maintains the vault in markdown; another person consumes it read-only as PDFs on an iPad through Google Drive. Built for a non-technical reader who lives in PDFs, not markdown.

Two iPadOS + Google Drive quirks shape the design: the Drive file provider on iOS reliably opens only formats with a native preview handler (`.pdf`, images, Office docs), so tapping `.md` files is unreliable; and Drive doesn't hide dotfiles or tooling files, so the reader's entry points must sit below the vault root to keep `CLAUDE.md`, `.git/` and friends out of view. The render pipeline answers the first, the Drive-shortcut access model the second.

## What this delivery adds to the base

0. **A CLAUDE.md template** ([`skeleton/CLAUDE.md.template`](skeleton/CLAUDE.md.template)): `base/CLAUDE.md.template` with the deltas its header comment lists, all downstream of "no `actions.md`, and the reader is on an iPad"; every other line tracks base verbatim. A vault on this delivery follows this template, not base's, and says so with its `**Delivery:** readonly-ipad` line under `**Type:**`, which is how `/para-upgrade` knows.
0b. **A README template** ([`skeleton/README.md.template`](skeleton/README.md.template)): identical to `base/README.md.template` except for its closing line. The base line points at `CLAUDE.md` and `/para-daily-brief`; in this delivery `CLAUDE.md` is on the render denylist so no PDF of it exists, and there is no `actions.md` for the brief to read, so both references would be dead ends in a rendered README. This delivery's line points at the PARA folders instead. Changing it means re-rendering `README.pdf` in every vault on the delivery.
0c. **A `.gitignore`** ([`skeleton/.gitignore`](skeleton/.gitignore)): the base vault's file plus Drive-for-Desktop noise (`desktop.ini`, the `*.gdoc`/`*.gsheet` stub formats). Its defensive secret guard matters more here than in the base, not less: this delivery lives on a *shared* drive, so a credential dropped into the vault leaks to every reader.
These three skeleton files are derived copies of their `base/` counterparts, so each one rots the moment base moves. `tools/check.py` fails until someone has reconciled the two: it stamps the digest of each base file in `DELIVERY_TRACKING` and compares. Reviewing base's diff, changing nothing here, and re-stamping is a legitimate outcome - the record that someone looked is the point.

1. **The pipeline** ([`pipeline/`](pipeline/)), three files copied verbatim into the vault root:
   - `render.ps1` + `render.mjs`: render every `.md` to a sibling `.pdf` with one persistent headless Chromium (Puppeteer + github-markdown-css). Incremental by mtime; `-Force` re-renders all. Also renders standalone `.html` documents (full designed pages authored as HTML, e.g. one-pagers) to `.pdf` siblings - everywhere except `sources/` folders, which hold raw saved webpages and are never rendered. `flip.ps1` round-trips a rendered `.html` (one with a `.pdf` sibling) the same way it does `.md`.
   - `flip.ps1`: switches the vault between **spread** (`.md` next to `.pdf`, the editing state) and **collected** (all `.md` files in a flat `resources/mds/` bucket, path encoded into the filename with `__`). Collected is the default; the reader's folders then contain only PDFs.
   - All three carry a `para-os-integration: readonly-ipad <revision>` marker in their header, which puts them in `/para-upgrade`'s drift check like any installed integration. The marker resolves to `delivery/readonly-ipad/pipeline/<file>`, and the check diffs content rather than comparing the marker string.
2. **A `resources/mds/` folder** (create it with a short README; it must exist for the pipeline and sits on the render denylist).
3. **Reader access via Drive shortcuts**: in the reader's personal My Drive, a folder named after the vault containing five Google Drive shortcuts to the vault's `triage/`, `projects/`, `areas/`, `resources/`, `archive/`. The reader navigates via iOS Files into those shortcuts and never reaches the vault root, which keeps `CLAUDE.md` and dotfiles out of view. If you add a new top-level folder, create a matching shortcut.

## What this delivery removes

**No `actions.md` files.** The reader doesn't track tasks; capture next steps as prose in the relevant brief, contact file, or README. `/para-daily-brief` detects this delivery at runtime (render pipeline present, no `actions.md`) and drops its task panels instead of reporting an error.

## Setup

1. Copy `base/` into the vault root, dotfiles included, then overwrite its `CLAUDE.md.template`, `README.md.template` and `.gitignore` with this delivery's [`skeleton/`](skeleton/) files and copy `pipeline/*` beside them.
2. Create `resources/mds/` with a short README (the pipeline needs this folder to exist).
3. Run the bootstrap (`bootstrap-prompt.md`) as usual, with two changes. **Skip every step that creates an `actions.md` file**: do not seed `areas/business/actions.md`, and give `projects/vault-setup/` only a `brief.md` with the next steps as prose. And ask who reads the PDFs and in which language, to fill `{{Reader}}` and the Language section's reader-language placeholder, which the bootstrap's three questions do not cover. Everything else applies unchanged: the skeleton's header comment already tells the bootstrap which base sections it drops.
4. Install the render dependencies once per machine: Node.js plus `npm install -g puppeteer marked github-markdown-css` (Puppeteer downloads a bundled Chromium once, ~170 MB).
5. Acceptance test from the vault root: `.\flip.ps1 spread` then `.\render.ps1` then `.\flip.ps1 collect`. Confirm `.pdf` siblings generate and `.md` sources land in `resources/mds/`.
6. Create the reader's My Drive shortcuts (manual, Drive UI).

## The edit cycle

```powershell
.\flip.ps1 spread    # .md files back to their PARA homes
# edit in your editor
.\render.ps1         # regenerate .pdf siblings
.\flip.ps1 collect   # .md files back into resources/mds/
```

Both flip directions are idempotent; `-DryRun` previews. Keep the three pipeline files byte-identical across every vault on this delivery: if you change one copy, propagate to the others.

## Notes for Claude sessions in a vault on this delivery

- If the vault is already spread, the maintainer may be mid-edit; don't re-collect without checking.
- **A check that looks up a vault file by name looks in both states.** At rest a `.md` sits at `resources/mds/<a>__<b>__<file>.md` and its PARA path holds only the rendered `.pdf`, which itself proves the source exists. A lookup at the PARA path alone finds nothing in a healthy collected vault, silently, and reports a file missing that is there.
- If the reader reports a file not opening on the iPad, the answer is "look for the PDF sibling", not a technical fix on their side.
