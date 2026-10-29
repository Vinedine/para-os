#!/usr/bin/env python3
"""Tests for funnel_page.py. Each pins a rule the script's docstring states: a connector row and
a fetch-script row declare a mailbox and a sync-script row does not, the ledger's entries
count by their reason inside the window only, the drops a run log's report line names are
read per exclusion, the decision ledger gives each action type its window share, the kill
switch and the quarantine show, and the printed line is what paraos_pages.py expects.

    python3 test_funnel_page.py
    py -3 test_funnel_page.py

Standard library only. Every vault, registry and state file here is synthetic, built in a
temporary folder.
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "multi-vault" / "para-ingest" / "scripts"))

from funnel_page import gather, main, parse_table, render  # noqa: E402

TODAY = date(2030, 6, 20)
STAMP = TODAY.strftime("%Y%m%d")
OLD = (TODAY - timedelta(days=30)).isoformat()
RECENT = (TODAY - timedelta(days=2)).isoformat()

SOURCES = """# Fixture Vault Conventions

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| mail-ops | connector: `google-workspace` | `ops@example.test` | Everything about orders. |
| mail-shared | fetch-script | `shared@example.test` via `resources/scripts/outlook.py fetch` | Shared inbox threads. |
| notes | sync-script | `resources/scripts/notes.py` (writes meeting notes to `triage/`) | Meetings carrying the prefix. |

## Something else
"""


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FunnelPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.alpha = Path(self.tmp) / "alpha"
        self.beta = Path(self.tmp) / "beta"
        write(self.alpha, "CLAUDE.md", SOURCES)
        write(self.beta, "CLAUDE.md", "# Beta\n\n## Triage sources\n\n| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n| mail-ops | connector: gmail | `ops@example.test` | Invoices only. |\n")
        write(self.home, "vaults.json", json.dumps([
            {"name": "Alpha", "path": str(self.alpha), "purpose": "Orders and operations.", "active": True},
            {"name": "Beta", "path": str(self.beta), "purpose": "Invoices.", "active": True},
            {"name": "Gone", "path": str(Path(self.tmp) / "gone"), "purpose": "Retired.", "active": False},
        ]))
        write(self.home, "triage-exclusions.json", json.dumps({
            "ops@example.test": [
                {"from": "noreply@shop.test", "reason": "receipts", "added": RECENT},
                {"domain": "school.test", "reason": "class mail", "added": RECENT},
                {"subject_contains": "newsletter", "reason": "noise", "added": RECENT},
            ]}))
        write(self.home, "cache/ingest/ledger.json", json.dumps({"mailboxes": {
            "ops@example.test": {
                "a": {"date": RECENT, "subject": "Order 1", "routed": ["Alpha"], "reason": "rule: Alpha Relevant when"},
                "b": {"date": RECENT, "subject": "Lunch?", "routed": [], "reason": "unrouted: no candidate vault matched"},
                "c": {"date": RECENT, "subject": "Receipt", "routed": [], "reason": "excluded: from noreply@shop.test"},
                "d": {"date": RECENT, "subject": "Order 1 copy", "routed": ["Alpha"], "reason": "rule; suppressed: better-grouped copy"},
                "e": {"date": OLD, "subject": "Old", "routed": ["Alpha"], "reason": "rule"},
                "f": {"date": RECENT, "subject": "Known", "routed": [], "reason": "skipped: already dispositioned"},
            },
            "shared@example.test": {
                "g": {"date": RECENT, "subject": "Invoice 7", "routed": ["Beta", "Alpha"], "reason": "contact"},
            }}}))
        write(self.home, f"cache/ingest/runs/{STAMP}-061500.json", json.dumps({
            "mode": "write", "invocation": "/para-ingest write", "started_at": f"{TODAY.isoformat()}T06:15:00+00:00",
            "source_plan": {"mailboxes": 2, "mailboxes_read": 2, "mailboxes_errored": 0},
            "sync_runs": [{"vault": "Alpha", "script": "resources/scripts/notes.py", "written": 2, "error": None}],
            "exclusions_applied": "ops@example.test: noreply@shop.test dropped 3, domain school.test dropped 1; every other entry 0",
            "files_written": [str(self.alpha / "triage" / "a.md"), str(self.alpha / "triage" / "b.md"), str(self.beta / "triage" / "c.md")],
            "errors": [], "warnings": ["one"]}))
        write(self.home, "cache/ingest/runs/20200101-000000.json", json.dumps({"mode": "write", "files_written": [str(self.alpha / "triage" / "old.md")]}))
        rows = [{"date": RECENT, "item": f"item {i}", "recommended": "File it", "chosen": "File it", "path": "interactive"} for i in range(3)]
        rows.append({"date": RECENT, "item": "item x", "recommended": "File it", "chosen": "Delete (noise)", "path": "interactive"})
        rows.append({"date": RECENT, "item": "item auto", "recommended": "Dismiss (noise)", "chosen": "Dismiss (noise)", "path": "auto"})
        rows.append({"date": OLD, "item": "item old", "recommended": "Add action", "chosen": "Add action", "path": "interactive"})
        write(self.home, "cache/triage/decisions/Alpha.jsonl", "\n".join(json.dumps(r) for r in rows) + "\n")
        write(self.home, "auto-triage.json", json.dumps({"Alpha": {"on": ["Dismiss (noise)"], "demoted": []}}))
        write(self.home, f"quarantine/Alpha/{STAMP}-070000/manifest.json", json.dumps({
            "vault": "Alpha", "run": f"{STAMP}-070000",
            "items": [{"item": "dup.md", "action": "Delete (duplicate)", "reason": "same bytes"},
                      {"item": "noise.md", "action": "Dismiss (noise)", "reason": "a reminder"}]}))
        write(self.home, "quarantine/Alpha/20200101-000000/manifest.json", json.dumps({
            "vault": "Alpha", "run": "20200101-000000", "items": [{"item": "ancient.md", "action": "Dismiss (noise)", "reason": "old"}]}))
        write(self.home, f"cache/triage/proposals/Beta-{STAMP}-0616.md",
              "# Unattended triage: waiting for the operator\n\n| Item | Recommended | Why | Held because |\n|---|---|---|---|\n"
              "| invoice.pdf | Move | an invoice | money owed |\n\n```json\n{\"vault\": \"Beta\", \"run\": \"" + STAMP + "-061626\"}\n```\n")
        write(self.home, "cache/triage/proposals/decided/Beta-old.md", "decided\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_table_rows_keyed_by_header(self):
        rows = parse_table(SOURCES, "Triage sources")
        self.assertEqual([r["source"] for r in rows], ["mail-ops", "mail-shared", "notes"])
        self.assertEqual(parse_table(SOURCES, "Absent"), [])

    def test_connector_and_fetch_script_declare_a_mailbox(self):
        d = gather(str(self.home), 7, today=TODAY)
        self.assertEqual(sorted(v for v, _, _ in d["mailbox_vaults"]["ops@example.test"]), ["Alpha", "Beta"])
        self.assertEqual(d["mailbox_vaults"]["shared@example.test"], [("Alpha", "Shared inbox threads.", "script")])
        self.assertEqual([s["source"] for s in d["sources"] if s["type"].startswith("sync-script")], ["notes"])
        self.assertEqual([v["name"] for v in d["vaults"]], ["Alpha", "Beta"])

    def test_ledger_counts_by_reason_inside_the_window(self):
        L = gather(str(self.home), 7, today=TODAY)["ledger"]
        self.assertEqual((L["seen"], L["routed"], L["unrouted"], L["excluded"], L["suppressed"], L["skipped"]), (6, 2, 1, 1, 1, 1))
        self.assertEqual(L["routed_per_vault"], {"Alpha": 2, "Beta": 1})
        self.assertEqual(L["per_mailbox"]["ops@example.test"]["unrouted"], 1)
        self.assertEqual(L["unrouted_samples"]["ops@example.test"], ["Lunch?"])

    def test_drops_read_from_the_run_line_per_exclusion(self):
        d = gather(str(self.home), 7, today=TODAY)
        by_value = {e["value"]: e["dropped"] for e in d["exclusions"]}
        self.assertEqual(by_value, {"noreply@shop.test": 3, "school.test": 1, "newsletter": 0})
        self.assertEqual(d["drops_unparsed_runs"], 0)
        self.assertEqual(d["staged"], 3)
        self.assertEqual([r["run"] for r in d["runs"]], [f"{STAMP}-061500"])

    def test_decisions_window_share_and_switches(self):
        d = gather(str(self.home), 7, today=TODAY)
        alpha = d["decisions"]["Alpha"]
        file_it = next(t for t in alpha["types"] if t["type"] == "File it")
        self.assertEqual((file_it["n"], file_it["accepted"], file_it["window_n"]), (4, 3, 4))
        self.assertAlmostEqual(file_it["share"], 0.75)
        self.assertEqual(len(file_it["overrides"]), 1)
        self.assertEqual((alpha["total"], alpha["window"], alpha["window_accepted"]), (5, 4, 3))
        self.assertEqual(d["interactive_window"], 4)
        self.assertEqual(d["switches"]["Alpha"]["on"], ["Dismiss (noise)"])
        self.assertFalse(d["kill_switch"])

    def test_quarantine_and_proposals(self):
        d = gather(str(self.home), 7, today=TODAY)
        self.assertEqual(d["acted"], 2)
        self.assertEqual(d["acted_by_action"], {"Delete (duplicate)": 1, "Dismiss (noise)": 1})
        self.assertEqual([q["in_window"] for q in d["quarantine"]], [False, True])
        self.assertIn("restore --vault-name \"Alpha\" --run " + STAMP + "-070000", d["quarantine"][1]["restore"])
        self.assertEqual(d["waiting_items"], 1)
        self.assertEqual(d["proposals"][0]["vault"], "Beta")
        self.assertEqual(d["proposals"][0]["items"][0]["held"], "money owed")
        self.assertEqual(d["decided"], 1)

    def test_render_marks_each_stage_and_the_kill_switch(self):
        page = render(gather(str(self.home), 7, today=TODAY))
        self.assertIn("<title>Triage funnel</title>", page)
        self.assertNotIn("not declared", page)
        self.assertIn('<span class="who prose"', page)
        self.assertNotIn("Kill switch on", page)
        self.assertIn('class="chip on">Dismiss (noise)', page)
        write(self.home, "auto-triage.off", "")
        page = render(gather(str(self.home), 7, today=TODAY))
        self.assertIn("Kill switch on", page)

    def test_main_prints_the_page_line(self):
        out = Path(self.tmp) / "page" / "funnel.html"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--paraos-home", str(self.home), "--days", "7", "--out", str(out)])
        self.assertEqual(code, 0)
        line = json.loads(buf.getvalue().strip().splitlines()[-1])
        self.assertEqual((line["page"], line["title"], line["out"]), ("funnel", "Triage funnel", str(out)))
        self.assertEqual(line["key"], str(self.home))
        self.assertTrue(out.is_file())
        self.assertNotIn(chr(0x2014), out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
