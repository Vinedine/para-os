# Flavor: readonly-ipad

One person maintains the vault in markdown; another person consumes it read-only as PDFs on an iPad through Google Drive. Built for a non-technical reader who lives in PDFs, not markdown.

Two iPadOS + Google Drive quirks shape the design: the Drive file provider on iOS reliably opens only formats with a native preview handler (`.pdf`, images, Office docs), so tapping `.md` files is unreliable; and Drive doesn't hide dotfiles or tooling files, so the reader's entry points must sit below the vault root to keep `CLAUDE.md`, `.git/` and friends out of view. The render pipeline answers the first, the Drive-shortcut access model the second.

## What this flavor adds to the base

1. **The pipeline** ([`pipeline/`](pipeline/)), three files copied verbatim into the vault root:
   - `render.ps1` + `render.mjs`: render every `.md` to a sibling `.pdf` with one persistent headless Chromium (Puppeteer + github-markdown-css). Incremental by mtime; `-Force` re-renders all.
   - `flip.ps1`: switches the vault between **spread** (`.md` next to `.pdf`, the editing state) and **collected** (all `.md` files in a flat `resources/mds/` bucket, path encoded into the filename with `__`). Collected is the default; the reader's folders then contain only PDFs.
2. **A `resources/mds/` folder** (create it with a short README; it must exist for the pipeline and sits on the render denylist).
3. **Reader access via Drive shortcuts**: in the reader's personal My Drive, a folder named after the vault containing five Google Drive shortcuts to the vault's `triage/`, `projects/`, `areas/`, `resources/`, `archive/`. The reader navigates via iOS Files into those shortcuts and never reaches the vault root, which keeps `CLAUDE.md` and dotfiles out of view. If you add a new top-level folder, create a matching shortcut.

## What this flavor removes

**No `actions.md` files.** The reader doesn't track tasks; capture next steps as prose in the relevant brief, contact file, or README. `/daily-brief` detects this flavor at runtime (render pipeline present, no `actions.md`) and degrades to a triage-only view instead of reporting an error.

## Setup

1. Copy `base/skeleton/*` to the vault root, then copy `pipeline/*` next to it.
2. Run the bootstrap (`bootstrap-prompt.md`) as usual, and document the flavor in `CLAUDE.md`: the collect/spread workflow, the no-actions rule, and the reader-access model (see the template's optional sections).
3. Install the render dependencies once per machine: Node.js plus `npm install -g puppeteer marked github-markdown-css` (Puppeteer downloads a bundled Chromium once, ~170 MB).
4. Acceptance test from the vault root: `.\flip.ps1 spread` then `.\render.ps1` then `.\flip.ps1 collect`. Confirm `.pdf` siblings generate and `.md` sources land in `resources/mds/`.
5. Create the reader's My Drive shortcuts (manual, Drive UI).

## The edit cycle

```powershell
.\flip.ps1 spread    # .md files back to their PARA homes
# edit in your editor
.\render.ps1         # regenerate .pdf siblings
.\flip.ps1 collect   # .md files back into resources/mds/
```

Both flip directions are idempotent; `-DryRun` previews. Keep the three pipeline files byte-identical across every vault of this flavor: if you change one copy, propagate to the others.

## Notes for Claude sessions in a vault of this flavor

- If the vault is already spread, the maintainer may be mid-edit; don't re-collect without checking.
- If the reader reports a file not opening on the iPad, the answer is "look for the PDF sibling", not a technical fix on their side.
