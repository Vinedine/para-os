#!/usr/bin/env python3
"""Tests for paraos_runs.py, the task registry and the app's runs. Each one pins a rule of
the script, which is the specification.

    python3 test_paraos_runs.py
    py -3 test_paraos_runs.py

Standard library only. The para-os home and the tasks folder are temporary directories:
nothing reads or writes the machine's own registry or scheduled tasks.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import paraos_runs  # noqa: E402
from paraos_runs import (  # noqa: E402
    app_list, app_runs, app_tasks, check, entry_problems, last_run, load_tasks, main, parse_time,
    status,
)

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


APP = [{"taskId": "ingest", "cronExpression": "0 6,16 * * *", "enabled": True,
        "runs": [{"status": "failed", "started_at": "2030-03-10T06:01:00Z",
                  "last_activity_at": "2030-03-10T06:09:00Z", "error": "mailbox\ndown",
                  "summary": "staged nothing"},
                 {"status": "succeeded", "started_at": "2030-03-09T16:01:00Z"}]},
       {"taskId": "price-watch", "cronExpression": "30 6 * * *", "enabled": False, "runs": []},
       {"taskId": "elsewhere", "enabled": True}]


class AppRuns(Home):
    def test_the_newest_run_speaks_in_the_apps_words_mapped(self):
        self.assertEqual(last_run(APP[0]), {"start": "2030-03-10T06:01:00Z", "end": "2030-03-10T06:09:00Z",
                                            "status": "failed", "summary": "mailbox down"})
        self.assertEqual(last_run({"runs": [{"status": "succeeded", "started_at": "s", "summary": "fine"}]}),
                         {"start": "s", "end": "s", "status": "ok", "summary": "fine"})
        self.assertEqual(last_run({"runs": [{"status": "running"}]})["status"], "running")
        self.assertEqual(last_run({"runs": [{"status": "needs_approval"}]})["status"], "partial")
        self.assertEqual(last_run({"runs": [{}]})["status"], "partial")
        for task in ({}, {"runs": []}, {"runs": "x"}, {"runs": ["x"]}):
            self.assertIsNone(last_run(task))

    def test_each_entry_gets_how_the_app_last_ran_it(self):
        self.tasks([INGEST, WATCH, dict(WATCH, id="unlisted"), "junk"])
        report = status(paraos_home=self.home, app=app_runs(APP))
        rows = {r["id"]: r for r in report["tasks"]}
        self.assertEqual(list(rows), ["ingest", "price-watch", "unlisted"])
        self.assertEqual((rows["ingest"]["enabled"], rows["ingest"]["last"]["status"]), (True, "failed"))
        self.assertEqual((rows["price-watch"]["enabled"], rows["price-watch"]["last"]), (False, None))
        self.assertEqual((rows["unlisted"]["enabled"], rows["unlisted"]["last"]), (None, None))
        self.assertEqual(rows["price-watch"]["sources"], WATCH["sources"])
        self.assertTrue(report["app_compared"])
        self.assertIsNone(report["error"])

    def test_without_the_apps_list_no_entry_has_a_run(self):
        self.tasks([INGEST])
        report = status(paraos_home=self.home)
        self.assertEqual((report["app_compared"], report["tasks"][0]["last"]), (False, None))
        self.tasks([])
        self.assertEqual(status(paraos_home=self.home)["tasks"], [])

    def test_the_command_reads_the_apps_list_for_one_entry_and_refuses_an_unreadable_one(self):
        self.tasks([INGEST, WATCH])
        listed = Path(self.tmp.name) / "app.json"
        listed.write_text(json.dumps({"tasks": APP}), encoding="utf-8")
        code, out, _ = self.run_main("status", "--task", "ingest", "--app-tasks", str(listed))
        self.assertEqual(code, 0)
        self.assertEqual([(r["id"], r["last"]["summary"]) for r in json.loads(out)["tasks"]],
                         [("ingest", "mailbox down")])
        code, _, err = self.run_main("status", "--app-tasks", str(listed) + ".missing")
        self.assertEqual(code, 2)
        self.assertIn("--app-tasks", err)

    def test_a_time_reads_with_or_without_its_zone(self):
        self.assertEqual(parse_time("2030-03-10T06:01:00Z").utcoffset().total_seconds(), 0)
        self.assertEqual(parse_time("2030-03-10T06:01:00").utcoffset().total_seconds(), 0)
        self.assertIsNone(parse_time("soon"))


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
        self.assertEqual(len(app_tasks(listed)), 2)
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
