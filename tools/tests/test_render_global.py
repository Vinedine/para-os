#!/usr/bin/env python3
"""Tests for render_global.py. Each pins a rule the script's docstring states: the page holds
the scan's dated items, summed vaults and health cards, the calendars' events merged with the
`meetings.md` ones, and a next action naming a task the scan does not hold is an error.

    python3 test_render_global.py
    py -3 test_render_global.py

Standard library only. Every vault and registry here is synthetic, built in a temporary folder.
"""

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "multi-vault" / "para-global-brief" / "scripts"))

from global_scan import build_report  # noqa: E402
from render_global import JudgmentError, main, page_data, render  # noqa: E402
from test_global_scan import TODAY, build_vault, write  # noqa: E402

DATA_RE = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)


class RenderGlobal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "paraos"
        build_vault(self.tmp / "north", "- [ ] Send the launch note 🔺 📅 2026-03-10\n"
                                        "- [ ] Brief the copywriter 📅 2026-03-12\n")
        write(self.tmp / "north", "meetings.md", "- 🗓 2026-03-11 10:00 · Kick-off · Teams\n")
        build_vault(self.tmp / "south", "- [ ] Pay the host invoice 🔺 📅 2026-03-09\n")
        self.entries = [{"name": "north", "path": str(self.tmp / "north")},
                        {"name": "south", "path": str(self.tmp / "south"), "brief": "summary"}]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def scan(self):
        return json.loads(json.dumps(build_report(self.entries, TODAY, str(self.home))))

    def judgment(self, **extra):
        return dict({"next_action": {"text": "Send the **launch note**", "vault": "north"},
                     "events": [{"date": "2026-03-11", "start": "10:00", "title": "kick-off ",
                                 "source": "work"},
                                {"date": "2026-03-10", "start": "13:00", "end": "14:00",
                                 "title": "Demo", "source": "work"}]}, **extra)

    def test_the_page_holds_the_scan_and_the_merged_events(self):
        data = page_data(self.scan(), self.judgment(), local=False)
        self.assertEqual(data["next_action"], {"text": "Send the launch note", "vault": "north"})
        self.assertEqual([(t["vault"], t["text"], t["date"]) for t in data["tasks"]],
                         [("north", "Send the launch note", "2026-03-10"),
                          ("north", "Brief the copywriter", "2026-03-12")])
        self.assertEqual(data["own_vaults"], ["north"])
        self.assertEqual([(s["vault"], s["overdue"], [t["text"] for t in s["top"]])
                          for s in data["summaries"]], [("south", 1, ["Pay the host invoice"])])
        self.assertEqual([(e["date"], e["title"], e["source"]) for e in data["events"]],
                         [("2026-03-10", "Demo", "work"), ("2026-03-11", "Kick-off", "north")])
        self.assertEqual([(h["vault"], h["treatment"], len(h["card"]["rows"]))
                          for h in data["health"]], [("north", "full", 8), ("south", "summary", 8)])
        labels = [s["label"] for s in data["signals"]]
        self.assertEqual(len(labels), 8)
        self.assertEqual(labels.index("Kit"), labels.index("Template") + 1)
        kit = next(r for r in data["health"][0]["card"]["rows"] if r["key"] == "kit")
        self.assertEqual((kit["level"], kit["value"]), ("unknown", "not judged: no para-os clone"))
        self.assertIsNone(data["funnel_url"])

    def test_the_deep_clean_row_carries_the_audit_count_and_the_page_links_the_funnel(self):
        scan = self.scan()
        scan["vaults"][0]["deep_clean_audit"] = {"date": "2026-03-08", "total": 7, "findings": {"dangling": 7}}
        scan["vaults"][0]["kit"] = {"level": "watch", "verdict": "aligned", "findings": 3, "upgrade": 2, "behind": 0}
        scan["funnel_url"] = "https://example.test/funnel"
        data = page_data(scan, self.judgment(), local=False)
        rows = {r["key"]: r for r in data["health"][0]["card"]["rows"]}
        self.assertEqual(rows["deep_clean"]["value"], "no run recorded · audit 2d ago: 7 findings")
        self.assertEqual((rows["kit"]["level"], rows["kit"]["value"]), ("watch", "3 findings, 2 the upgrade applies"))
        self.assertEqual(data["funnel_url"], "https://example.test/funnel")
        self.assertIn("https://example.test/funnel", render(scan, self.judgment()))

    def test_a_next_action_naming_a_task_the_scan_lacks_is_an_error(self):
        scan = self.scan()
        t = scan["tasks"][0]
        page_data(scan, self.judgment(next_action={"text": "x", "vault": "north",
                                                   "file": t["file"], "line": t["line"]}), False)
        with self.assertRaises(JudgmentError):
            page_data(scan, self.judgment(next_action={"text": "x", "vault": "north",
                                                       "file": t["file"], "line": 99}), False)
        with self.assertRaises(JudgmentError):
            page_data(scan, self.judgment(next_action={}), False)
        with self.assertRaises(JudgmentError):
            page_data(scan, self.judgment(events=[{"date": "soon", "title": "x"}]), False)

    def test_the_page_embeds_its_data_with_no_tag_breaking_out(self):
        scan = self.scan()
        scan["tasks"][0]["text"] = "Fix </script> handling"
        page = render(scan, self.judgment())
        self.assertIn("<title>All Vaults</title>", page)
        self.assertEqual(json.loads(DATA_RE.search(page).group(1))["tasks"][0]["text"],
                         "Fix </script> handling")

    def test_the_cli_writes_the_page_and_names_where_it_goes(self):
        scan_path = write(self.tmp, "scan.json", json.dumps(self.scan()))
        judgment_path = write(self.tmp, "judgment.json", json.dumps(self.judgment()))
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.home)}), \
                contextlib.redirect_stdout(out):
            code = main(["--scan", str(scan_path), "--judgment", str(judgment_path),
                         "--out", str(self.tmp / "page.html")])
        self.assertEqual(code, 0)
        printed = json.loads(out.getvalue())
        self.assertEqual((printed["page"], printed["publish"], printed["url"]),
                         ("global-brief", "claude", None))
        self.assertTrue((self.tmp / "page.html").is_file())
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.home)}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--publish", "local"]), 0)
            main(["--scan", str(scan_path), "--judgment", str(judgment_path)])
        self.assertTrue((self.home / "cache" / "global-brief" / "paraos.html").is_file())

    def test_a_bad_judgment_exits_2(self):
        scan_path = write(self.tmp, "scan.json", json.dumps(self.scan()))
        judgment_path = write(self.tmp, "judgment.json", json.dumps({"next_action": {}}))
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--scan", str(scan_path), "--judgment", str(judgment_path),
                                   "--out", str(self.tmp / "page.html")]), 2)


if __name__ == "__main__":
    unittest.main()
