---
type: llm
---

The triage folder holds one loose file, `taskboard-export.csv`: an export of the studio's task
board history. Two entries concern orchard-labs (the client quotes by hand from a spreadsheet
of about 1,400 supplier prices; the price list will be imported as a CSV each month) and two
concern acme-website (the DNS cutover was rehearsed on staging; goal tracking is set up). The
vault holds `resources/ideas/orchard-labs/brief.md` and `projects/acme-website/brief.md`.

PASS if the reply proposes edits that carry facts from the export into both entities' files
(the orchard-labs brief, and the acme-website brief or another acme-website file), the text
each edit would write naming the export or the task board as the facts' source (once per
entity's edit is enough), and recommends deleting the export itself (Delete (no lasting
value)) rather than filing it.

FAIL if the reply recommends filing the export into any folder of the vault, or leaving it in
triage, or edits only one of the two entities, or if the text an edit would write for either
entity never names the export or the task board as its source.
