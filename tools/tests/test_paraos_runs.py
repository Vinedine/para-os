#!/usr/bin/env python3
"""Tests for paraos_runs.py, the task registry and its run records. Each one pins a rule of
the script, which is the specification.

    python3 test_paraos_runs.py
    py -3 test_paraos_runs.py

Standard library only. The para-os home and the tasks folder are temporary directories:
nothing reads or writes the machine's own registry, runs or scheduled tasks.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import paraos_runs  # noqa: E402
from paraos_runs import (  # noqa: E402
    KEEP_DAYS, SUMMARY_MAX, app_list, check, entry_problems, load_tasks, main, record,
    runs_dir, status,
)

NOW = datetime(2030, 3, 10, 6, 30, tzinfo=timezone.utc)

INGEST = {"id": "ingest", "title": "Ingest", "cron": "0 6,16 * * *", "skill": "para-ingest",
          "vaults": "*", "sources": []}
WATCH = {"id": "price-watch", "title": "Price watch", "cron": "30 6 * * *", "skill": None,
         "vaults": ["household"],
         "sources": [{"name": "Hotel site", "via": ["browser", "mcp:hotels"]}]}


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.tasks_dir = Path(self.tmp.name) / "scheduled-tasks"
        self.tasks_dir.mkdir()
        (self.home / "vaults.json").write_text(json.dumps(
            [{"name": "household", "path": "/nowhere"}, {"name": "studio", "path": "/x"}]),
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def tasks(self, entries):
        (self.home / "tasks.json").write_text(json.dumps(entries), encoding="utf-8")

    def folder(self, name, skill=True):
        path = self.tasks_dir / name
        path.mkdir()
        if skill:
            (path / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")

    def kinds(self, report):
        return sorted(((f["task"], f["kind"]) for f in report["findings"]),
                      key=lambda tk: (tk[0] or "", tk[1]))

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--paraos-home", str(self.home), *argv])
        return code, out.getvalue(), err.getvalue()


class Registry(Home):
    def test_a_missing_registry_is_an_empty_one(self):
        self.assertEqual(load_tasks(self.home), ([], None))

    def test_a_registry_that_does_not_parse_says_why(self):
        (self.home / "tasks.json").write_text("{nope", encoding="utf-8")
        entries, error = load_tasks(self.home)
        self.assertEqual(entries, [])
        self.assertIn("does not parse", error)

    def test_a_registry_that_is_not_a_list_says_so(self):
        (self.home / "tasks.json").write_text("{}", encoding="utf-8")
        self.assertIn("not a JSON list", load_tasks(self.home)[1])

    def test_a_well_formed_entry_has_no_problems(self):
        self.assertEqual(entry_problems(INGEST, {"household"}), [])
        self.assertEqual(entry_problems(WATCH, {"household"}), [])

    def test_each_problem_of_an_entry_is_named(self):
        bad = {"id": "x", "vaults": ["household", "elsewhere"],
               "sources": [{"name": "Site", "via": ["browser", "web", "mcp:"]}, {"via": []}]}
        problems = entry_problems(bad, {"household"})
        self.assertEqual(len(problems), 4)
        self.assertTrue(any("'elsewhere'" in p for p in problems))
        self.assertTrue(any("'web'" in p for p in problems))
        self.assertTrue(any("'mcp:'" in p for p in problems))
        self.assertTrue(any("no `name`" in p for p in problems))

    def test_an_entry_without_an_id_stops_there(self):
        self.assertEqual(entry_problems({"vaults": 3}, set()), ["has no string `id`"])
        self.assertEqual(entry_problems("ingest", set()), ["has no string `id`"])

    def test_vaults_must_be_a_list_or_star(self):
        self.assertIn("neither a list", entry_problems({"id": "x", "vaults": "all"}, set())[0])


class Record(Home):
    def lines(self, task):
        return [json.loads(x) for x in
                (runs_dir(self.home) / f"{task}.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_a_run_appends_one_line(self):
        line = record("ingest", "ok", "staged 4\nin 2 vaults", paraos_home=self.home, now=NOW)
        self.assertEqual(line, {"task": "ingest", "start": None, "end": "2030-03-10T06:30:00Z",
                                "status": "ok", "summary": "staged 4 in 2 vaults"})
        record("ingest", "failed", "mailbox down", "2030-03-10T15:59:00Z",
               paraos_home=self.home, now=NOW + timedelta(hours=10))
        lines = self.lines("ingest")
        self.assertEqual([x["status"] for x in lines], ["ok", "failed"])
        self.assertEqual(lines[1]["start"], "2030-03-10T15:59:00Z")

    def test_a_long_summary_is_cut(self):
        line = record("ingest", "ok", "x" * (SUMMARY_MAX + 50), paraos_home=self.home, now=NOW)
        self.assertEqual(len(line["summary"]), SUMMARY_MAX)
        self.assertTrue(line["summary"].endswith("..."))

    def test_lines_older_than_the_window_are_dropped_and_unparsed_ones_kept(self):
        folder = runs_dir(self.home)
        folder.mkdir(parents=True)
        old = NOW - timedelta(days=KEEP_DAYS + 1)
        recent = NOW - timedelta(days=KEEP_DAYS - 1)
        (folder / "ingest.jsonl").write_text(
            json.dumps({"end": old.strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "ok"}) + "\n"
            + json.dumps({"end": recent.strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "ok"}) + "\n"
            + "not json\n" + json.dumps({"status": "partial"}) + "\n", encoding="utf-8")
        record("ingest", "ok", "now", paraos_home=self.home, now=NOW)
        text = (folder / "ingest.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(text), 4)
        self.assertIn("not json", text)
        self.assertNotIn(old.strftime("%Y-%m-%dT%H:%M:%SZ"), "".join(text))

    def test_an_unregistered_task_is_recorded_all_the_same(self):
        record("never-listed", "partial", "x", paraos_home=self.home, now=NOW)
        self.assertEqual(self.lines("never-listed")[0]["status"], "partial")

    def test_the_command_records_and_refuses_a_path_or_a_bad_time(self):
        code, out, _ = self.run_main("record", "--task", "ingest", "--status", "ok",
                                     "--summary", "fine")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "ok")
        self.assertEqual(self.run_main("record", "--task", "../x", "--status", "ok",
                                       "--summary", "s")[0], 2)
        self.assertEqual(self.run_main("record", "--task", "x", "--status", "ok",
                                       "--summary", "s", "--started", "soon")[0], 2)
        with self.assertRaises(SystemExit):
            self.run_main("record", "--task", "x", "--status", "maybe", "--summary", "s")


class Status(Home):
    def test_each_entry_gets_its_last_run_and_its_counts(self):
        self.tasks([INGEST, WATCH, "junk"])
        record("ingest", "ok", "one", paraos_home=self.home, now=NOW)
        record("ingest", "failed", "two", paraos_home=self.home, now=NOW + timedelta(hours=1))
        record("old-task", "ok", "gone", paraos_home=self.home, now=NOW)
        report = status(paraos_home=self.home)
        rows = {r["id"]: r for r in report["tasks"]}
        self.assertEqual(rows["ingest"]["last"]["summary"], "two")
        self.assertEqual(rows["ingest"]["runs"], {"ok": 1, "failed": 1, "partial": 0})
        self.assertIsNone(rows["price-watch"]["last"])
        self.assertEqual(rows["price-watch"]["sources"], WATCH["sources"])
        self.assertEqual(report["unregistered_runs"], ["old-task"])
        self.assertIsNone(report["error"])

    def test_task_narrows_to_one_entry(self):
        self.tasks([INGEST, WATCH])
        code, out, _ = self.run_main("status", "--task", "price-watch")
        self.assertEqual(code, 0)
        self.assertEqual([r["id"] for r in json.loads(out)["tasks"]], ["price-watch"])

    def test_no_registry_and_no_runs_is_an_empty_answer(self):
        report = status(paraos_home=self.home)
        self.assertEqual((report["tasks"], report["unregistered_runs"]), ([], []))


class Check(Home):
    def test_folders_alone_find_the_unregistered_and_the_folderless(self):
        self.tasks([INGEST, WATCH])
        self.folder("ingest")
        self.folder("deal-flow")
        self.folder("half-made", skill=False)
        report = check(self.home, None, self.tasks_dir)
        self.assertFalse(report["app_compared"])
        self.assertTrue(report["exists"])
        self.assertEqual(self.kinds(report), [("deal-flow", "unregistered"),
                                              ("price-watch", "no_folder")])

    def test_the_app_list_finds_every_kind_of_drift(self):
        self.tasks([INGEST, WATCH, dict(WATCH, id="retired-one")])
        for name in ("ingest", "price-watch", "leftover", "deal-flow"):
            self.folder(name)
        app = {"ingest": "0 6,16 * * *", "price-watch": "0 7 * * *", "deal-flow": "0 8 * * 1"}
        report = check(self.home, app, self.tasks_dir)
        self.assertTrue(report["app_compared"])
        self.assertEqual(self.kinds(report), [
            ("deal-flow", "unregistered"), ("leftover", "stale_folder"),
            ("price-watch", "schedule_differs"), ("retired-one", "not_scheduled")])
        differs = [f for f in report["findings"] if f["kind"] == "schedule_differs"][0]
        self.assertIn("'0 7 * * *'", differs["detail"])

    def test_invalid_entries_and_a_repeated_id_are_findings(self):
        self.tasks([INGEST, dict(INGEST), {"title": "no id"}, dict(WATCH, vaults=["gone"])])
        self.folder("ingest")
        self.folder("price-watch")
        found = check(self.home, None, self.tasks_dir)["findings"]
        invalid = [f for f in found if f["kind"] == "invalid"]
        self.assertEqual([f["task"] for f in invalid], ["ingest", None, "price-watch"])
        self.assertIn("repeats", invalid[0]["detail"])
        self.assertIn("entry 4", invalid[2]["detail"])

    def test_a_registry_that_does_not_parse_is_one_finding_and_every_task_unregistered(self):
        (self.home / "tasks.json").write_text("[", encoding="utf-8")
        self.folder("ingest")
        report = check(self.home, None, self.tasks_dir)
        self.assertEqual(self.kinds(report), [(None, "invalid"), ("ingest", "unregistered")])

    def test_no_registry_lists_every_task_as_unregistered(self):
        self.folder("ingest")
        report = check(self.home, {"ingest": "0 6 * * *"}, self.tasks_dir)
        self.assertFalse(report["exists"])
        self.assertEqual(self.kinds(report), [("ingest", "unregistered")])

    def test_a_missing_tasks_folder_holds_no_task(self):
        self.tasks([INGEST])
        report = check(self.home, None, Path(self.tmp.name) / "absent")
        self.assertEqual(self.kinds(report), [("ingest", "no_folder")])

    def test_the_default_tasks_folder_follows_the_claude_config_dir(self):
        with mock.patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(self.tmp.name)}):
            self.assertEqual(paraos_runs.default_tasks_dir(),
                             Path(self.tmp.name) / "scheduled-tasks")

    def test_the_app_list_reads_both_shapes_and_refuses_anything_else(self):
        listed = Path(self.tmp.name) / "app.json"
        listed.write_text(json.dumps([{"taskId": "a", "cronExpression": "1 * * * *"},
                                      {"id": "b", "cron": None}, {"title": "no id"}, 7]),
                          encoding="utf-8")
        self.assertEqual(app_list(listed), {"a": "1 * * * *", "b": None})
        listed.write_text(json.dumps({"tasks": [{"taskId": "c", "cron": "x"}]}),
                          encoding="utf-8")
        self.assertEqual(app_list(listed), {"c": "x"})
        listed.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            app_list(listed)

    def test_the_command_compares_with_the_app_and_refuses_an_unreadable_list(self):
        self.tasks([INGEST])
        self.folder("ingest")
        listed = Path(self.tmp.name) / "app.json"
        listed.write_text(json.dumps([{"taskId": "ingest", "cronExpression": "0 6,16 * * *",
                                       "enabled": True}]), encoding="utf-8")
        code, out, _ = self.run_main("check", "--app-tasks", str(listed),
                                     "--tasks-dir", str(self.tasks_dir))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["findings"], [])
        code, _, err = self.run_main("check", "--app-tasks", str(listed) + ".missing")
        self.assertEqual(code, 2)
        self.assertIn("--app-tasks", err)


if __name__ == "__main__":
    unittest.main()
