#!/usr/bin/env python3
"""Tests for global_scan.py. Each pins a rule the script's docstring states: per-vault counts
from brief_scan, the urgent list across vaults with its vault named, the newest proposal, and
the retired, invalid and unreachable entries listed, never dropped.

    python3 test_global_scan.py
    py -3 test_global_scan.py

Standard library only. Every vault and registry here is synthetic, built in a temporary folder.
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "multi-vault" / "para-global-brief" / "scripts"))

from global_scan import build_report, main  # noqa: E402

TODAY = date(2026, 3, 10)


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build_vault(root, actions):
    write(root, "CLAUDE.md", "# Fixture Vault Conventions\n\n**Type:** vault\n")
    for p in ("projects", "areas", "archive", "resources", "triage"):
        (Path(root) / p).mkdir(parents=True, exist_ok=True)
    write(root, "projects/site/actions.md", "# site - Actions\n\n" + actions)


class GlobalScan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "paraos"
        build_vault(self.tmp / "north", "- [ ] Renew the domain 📅 2026-03-08\n"
                                        "- [ ] Send the launch note 🔺 📅 2026-03-10\n"
                                        "- [ ] Brief the copywriter 📅 2026-03-12\n"
                                        "- [ ] Write the case study\n")
        write(self.tmp / "north", "triage/note.md", "A loose note.\n")
        build_vault(self.tmp / "south", "- [ ] Pay the host invoice 🔼 📅 2026-03-09\n")
        build_vault(self.tmp / "west", "- [ ] Never read 📅 2026-03-01\n")
        self.entries = [
            {"name": "north", "path": str(self.tmp / "north")},
            {"name": "south", "path": str(self.tmp / "south")},
            {"name": "east", "path": str(self.tmp / "east")},
            {"name": "west", "path": str(self.tmp / "west"), "retired": True},
            {"path": str(self.tmp / "north")},
        ]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def report(self):
        return build_report(self.entries, TODAY, str(self.home))

    def test_each_vault_carries_its_own_counts(self):
        north, south = self.report()["vaults"]
        self.assertEqual((north["name"], north["open"], north["overdue"], north["this_week"],
                          north["undated"], north["triage"]), ("north", 4, 1, 1, 1, 1))
        self.assertEqual((south["name"], south["open"], south["overdue"]), ("south", 1, 1))
        self.assertIsNone(north["proposal"])
        self.assertEqual(south["flags"], [])
        write(self.tmp / "south", "resources/notes.md", "- [ ] A checkbox out of place\n")
        self.assertEqual(self.report()["vaults"][1]["flags"], ["misplaced"])

    def test_urgent_spans_the_vaults_in_the_brief_sort(self):
        urgent = [(t["vault"], t["text"].split(" ")[0]) for t in self.report()["urgent"]]
        self.assertEqual(urgent, [("north", "Send"), ("south", "Pay"), ("north", "Renew")])

    def test_retired_invalid_and_unreachable_are_listed(self):
        excluded = {(e["name"], e["status"]) for e in self.report()["excluded"]}
        self.assertEqual(excluded, {("east", "UNREACHABLE"), ("west", "RETIRED (excluded)"),
                                    (None, "INVALID")})

    def test_the_newest_proposal_is_named(self):
        for stamp in ("20260309-0800", "20260310-0700"):
            write(self.home, f"cache/triage/proposals/north-{stamp}.md", "x\n")
        write(self.home, "cache/triage/proposals/northwest-20260311-0700.md", "x\n")
        write(self.home, "cache/triage/proposals/north-east-20260311-0700.md", "x\n")
        north = self.report()["vaults"][0]
        self.assertTrue(north["proposal"].endswith("north-20260310-0700.md"))

    def test_the_cli_prints_json_and_stops_without_a_registry(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--paraos-home", str(self.home)]), 3)
        write(self.home, "vaults.json", json.dumps(self.entries))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--paraos-home", str(self.home), "--today", "2026-03-10"]), 0)
        self.assertEqual(len(json.loads(out.getvalue())["vaults"]), 2)


if __name__ == "__main__":
    unittest.main()
