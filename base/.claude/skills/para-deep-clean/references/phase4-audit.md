# Phase 4 - Final audit

`scripts/clean_scan.py --phase 4` implements every row below that resolves against disk and `scripts/test_clean_scan.py` pins each one to a case; the rows that read as a judgment (canonical structure followed, contradictions resolved, content grooming proposed and ruled on) stay this file's own. Two of the script's rows, `uncited_contacts` and `inline_contact_details`, report `pass: None` with the candidate count in `detail` rather than a pass/fail: the count re-verifies the finding class this file lists below, and whether each one is a real defect or a legitimate exemption is this file's call, not the script's. Brief length is never a row here - `clean_scan.py --phase 3`'s `briefs_to_read` feeds Step 3.5's selection instead, per phase3-open-items.md.

Read-only verification pass. Also the second half of the `audit` argument, which runs Phase 1 plus this one in observe-only mode.

- All archived entities have zero open items, or explicit "fully closed" notes - counting neither checkboxes inside fenced code blocks nor those in third-party verbatim records that carry a frozen-record marker (Phase 1 Step 1.2b)
- All active entities have Open items reflecting real outstanding work only
- All READMEs follow canonical structure
- CLAUDE.md documents the canonical structures used
- Triage folder is empty (a `.gitkeep` is fine; a `README.md` is not)
- No empty PARA leaf directories
- Archive folder is clean: no loose files at the archive root, `archive/meetings/` holds only cross-cutting records and they follow the dated-naming convention, archived entities carry their minimum record
- Every person holding a card in `areas/network/` is linked rather than merely named on first mention in each live-bucket file (exempting the vault's principals outside the root README and every Phase 1 Step 1.2 exclusion), and their contact details appear only on the card, attributed to their actual owner rather than to whoever shares a line with them
- No contradiction between live files survives unrecorded: each is corrected in the copies, or carried as an open item on the entity that owns the fact
- No dangling relative links in live buckets. Re-run the Phase 1 Step 1.2 check here rather than citing its earlier result: anything moved in 1.2b or later broke its inbound links after that scan ran.
- Root README passes the Step 1.1 shape check, and no unfilled `{{...}}` template placeholder survives in a file the bootstrap wrote (the root `README.md`, `CLAUDE.md`, entity briefs and action files), scoped exactly as Step 1.1 scopes it - **not** vault-wide. A backticked mention, `resources/prompts/`, any folder the vault's `CLAUDE.md` declares as holding templates, and a file whose subject *is* the template (a para-os release note, a migration plan) are all out of scope, per **A quoted syntax is not a used syntax** in [operating-discipline.md](../../para-shared/operating-discipline.md)
- Status tables ("where do we stand" per entity: cost basis, stage, key numbers) present and current, where the vault uses them
- Action files sit at the actionable frontier: none at or over the 12-open WIP threshold and no 30+-day-overdue aspirational dates remain, except where the operator explicitly decided to keep one, or the item was reworded as an open question with the date removed - both count as resolved, and either way the decision goes in the run summary
- Content grooming findings were **proposed and ruled on, not applied silently**: every removal was approved individually with its text shown, no file was deleted as a duplicate without a content diff against the copy that survived, and the run summary names which briefs Step 3.5 read and which it skipped
- **`/para-daily-brief` actually runs** against the cleaned vault and its counts look right. Run it; don't simulate its file scan with a grep.

Report a clean state summary, or list residual issues with proposed fixes.

**A vault this run spread** is rendered and collected again after this audit, closing [the edit cycle](../../para-shared/operating-discipline.md#the-read-only-ipad-delivery).

## Edge case

- **An Open items list grows indefinitely with low-priority items**: propose grouping into "Active" (real work) vs "Residual flags" (historical gaps, low priority). Keep both, but make the priority hierarchy visible.
