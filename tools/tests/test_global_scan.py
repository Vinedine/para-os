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

    def test_kit_is_unknown_without_a_clone_and_the_deep_clean_audit_record_is_read(self):
        north = self.report()["vaults"][0]
        self.assertEqual(north["kit"], {"level": "unknown", "verdict": None, "findings": None,
                                        "upgrade": None, "behind": None})
        self.assertIsNone(north["deep_clean_audit"])
        self.assertIsNone(self.report()["funnel_url"])
        write(self.home, "data/deep-clean/north.audit.json",
              json.dumps({"date": "2026-03-08", "phase": "1", "findings": {"dangling": 5, "wikilinks": 2}, "total": 7}))
        write(self.home, "data/deep-clean/south.audit.json", "{not json")
        north, south = self.report()["vaults"]
        self.assertEqual(north["deep_clean_audit"], {"date": "2026-03-08", "total": 7,
                                                     "findings": {"dangling": 5, "wikilinks": 2}})
        self.assertIsNone(south["deep_clean_audit"])

    def test_each_vault_carries_its_own_counts(self):
        north, south = self.report()["vaults"]
        self.assertEqual((north["name"], north["open"], north["overdue"], north["this_week"],
                          north["undated"], north["triage"]), ("north", 4, 1, 1, 1, 1))
        self.assertEqual((south["name"], south["open"], south["overdue"]), ("south", 1, 1))
        self.assertIsNone(north["proposal"])
        self.assertIn(north["health"]["level"], ("ok", "watch", "care"))
        self.assertEqual(north["health"]["signals"]["triage"]["items"], 1)
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

    def test_a_vault_you_keep_lists_its_dated_tasks_areas_and_undated_count(self):
        report = self.report()
        self.assertEqual([v["treatment"] for v in report["vaults"]], ["full", "full"])
        self.assertEqual(sorted((t["vault"], t["effective_date"]) for t in report["tasks"]),
                         [("north", "2026-03-08"), ("north", "2026-03-10"),
                          ("north", "2026-03-12"), ("south", "2026-03-09")])
        self.assertEqual({e["vault"] for e in report["entities"]}, {"north", "south"})
        self.assertEqual(report["undated"], 1)

    def test_a_summary_setting_counts_the_vault_instead_of_listing_it(self):
        self.entries[1]["brief"] = "summary"
        write(self.tmp / "south", "areas/ops/actions.md", "- [ ] Restart the box 🔺 📅 2026-03-10\n")
        report = self.report()
        south = report["summaries"][0]
        self.assertEqual((south["vault"], south["overdue"], south["today"]), ("south", 1, 1))
        self.assertEqual([t["text"] for t in south["top"]], ["Restart the box"])
        self.assertEqual(dict(south["by_area"]), {"site": 1, "ops": 1})
        self.assertFalse([t for t in report["tasks"] + report["urgent"] if t["vault"] == "south"])

    def roster(self, me=None):
        write(self.tmp / "north", "CLAUDE.md", "# North\n\n**Type:** client-vault\n\n"
              "## Who writes this vault\n\n| Person | Role | Lane |\n|---|---|---|\n"
              "| [Ann Smet](areas/network/ann-smet.md) | keeper | Sales |\n"
              "| [Bo Peeters](areas/network/bo-peeters.md) | steward | - |\n")
        if me:
            write(self.home, "operator.json", json.dumps({"card": me}))

    def test_a_vault_you_steward_shows_its_health_only(self):
        self.roster(me="bo-peeters")
        north = self.report()["vaults"][0]
        self.assertEqual((north["role"], north["treatment"], north["type"]),
                         ("steward", "health", "client-vault"))
        self.assertFalse([t for t in self.report()["tasks"] if t["vault"] == "north"])
        self.assertIn("level", north["health"])

    def test_a_roster_that_does_not_name_you_is_health_only(self):
        self.roster()
        north = self.report()["vaults"][0]
        self.assertEqual((north["role"], north["treatment"]), (None, "health"))

    def test_a_card_in_two_vaults_is_one_person(self):
        for vault in ("north", "south"):
            write(self.tmp / vault, "areas/network/ann-smet.md",
                  "# Ann Smet\n\n## Next actions\n\n- [ ] Send Ann the deck 📅 2026-03-15\n")
        people = self.report()["people"]
        self.assertEqual([(p["person"], p["vaults"], p["owe"]) for p in people],
                         [("ann-smet", ["north", "south"], 2)])

    def test_a_calendar_two_vaults_declare_is_read_once(self):
        for vault, kind in (("north", "connector: google-workspace"),
                            ("south", "connector: `google-workspace`")):
            write(self.tmp / vault, "CLAUDE.md",
                  "# V\n\n**Type:** vault\n\n## Agenda sources\n\n"
                  "| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n"
                  f"| work | {kind} | `Me@Example.com` | All events |\n")
        cals = self.report()["calendars"]
        self.assertEqual([(c["endpoint"], c["vaults"]) for c in cals],
                         [("me@example.com", ["north", "south"])])

    def test_meetings_in_the_horizon_and_a_recurring_one_rolled_forward(self):
        write(self.tmp / "north", "meetings.md", "\n".join([
            "# Meetings", "", "## Upcoming", "",
            "- 🗓 2026-03-11 10:00\u201311:00 · Kick-off · Ann · Teams",
            "- 🗓 2026-03-01 · Already past",
            "- 🗓 2026-05-01 · Too far out", "", "## Recurring", "",
            "- 🗓 2026-03-02 09:00 · Weekly sync 🔁 every week · Teams",
            "- 🗓 2026-03-03 09:30 · Stand-up · Teams 🔁 every Tuesday", ""]))
        write(self.tmp / "north", "archive/meetings.md", "- 🗓 2026-03-12 · Archived one\n")
        meetings = self.report()["meetings"]
        self.assertEqual(next(m["end"] for m in meetings if m["title"] == "Kick-off"), "11:00")
        got = [(m["date"], m["start"], m["title"], m["recurring"]) for m in meetings]
        self.assertEqual(got, [
            ("2026-03-10", "09:30", "Stand-up", True),
            ("2026-03-11", "10:00", "Kick-off", False),
            ("2026-03-16", "09:00", "Weekly sync", True),
            ("2026-03-17", "09:30", "Stand-up", True),
            ("2026-03-23", "09:00", "Weekly sync", True),
            ("2026-03-24", "09:30", "Stand-up", True),
            ("2026-03-30", "09:00", "Weekly sync", True)])

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
