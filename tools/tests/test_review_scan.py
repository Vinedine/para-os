#!/usr/bin/env python3
"""Tests for review_scan.py. Each one pins a counting rule references/signals.md states in
prose.

    python3 test_review_scan.py
    py -3 test_review_scan.py

Standard library only. Every fixture is a throwaway vault in a temporary directory, with
synthetic names only, and the date is passed in, never taken from the clock.
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
SCRIPTS = ROOT / "addons" / "activity" / ".claude" / "skills" / "para-activity-review" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from review_scan import main, scan

TODAY = date(2026, 9, 21)


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "CLAUDE.md").write_text("# Vault\n", encoding="utf-8")
        for bucket in ("projects", "areas", "archive", "triage"):
            (self.root / bucket).mkdir()
        for skill in ("para-daily-brief", "para-new", "para-triage", "para-shared"):
            (self.root / ".claude" / "skills" / skill).mkdir(parents=True)
        self.logs = self.root / "resources" / "logs" / "sessions"
        self.logs.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root)

    def session(self, person, sid, day, *events, raw=()):
        """One ledger file: SessionStart, the events given, SessionEnd. `raw` lines are
        appended verbatim, for malformed input."""
        stamp = day.isoformat()
        lines = [{"at": f"{stamp}T09:00:00", "event": "SessionStart", "session": sid}]
        for i, ev in enumerate(events):
            lines.append({"at": f"{stamp}T09:{i + 1:02d}:00", "session": sid, **ev})
        lines.append({"at": f"{stamp}T09:59:00", "event": "SessionEnd", "session": sid,
                      "reason": "other"})
        name = f"{stamp.replace('-', '')}-{person}-{sid[:8]}.jsonl"
        text = "".join(json.dumps(line) + "\n" for line in lines) + "".join(r + "\n" for r in raw)
        (self.logs / name).write_text(text, encoding="utf-8")

    def run_scan(self, days=30):
        return scan(self.root, TODAY, days)


def slash(pid, command):
    return [{"event": "UserPromptExpansion", "prompt_id": pid, "prompt": command},
            {"event": "UserPromptSubmit", "prompt_id": pid, "prompt": command}]


def skill_call(pid, name):
    return {"event": "PostToolUse", "prompt_id": pid, "tool": "Skill", "target": name}


class Adoption(LedgerCase):
    def test_a_plain_language_request_counts_through_its_skill_call(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20),
                     {"event": "UserPromptSubmit", "prompt_id": "p1",
                      "prompt": "what is overdue this week?"},
                     skill_call("p1", "para-daily-brief"))
        adoption = self.run_scan()["adoption"]
        self.assertEqual(adoption["para-daily-brief"]["invocations"], 1)

    def test_a_slash_command_that_also_calls_skill_counts_once(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20),
                     *slash("p1", "/para-daily-brief"), skill_call("p1", "para-daily-brief"))
        adoption = self.run_scan()["adoption"]
        self.assertEqual(adoption["para-daily-brief"]["invocations"], 1)

    def test_a_plugin_prefix_is_dropped(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20), skill_call("p1", "para-os:para-new"))
        self.assertIn("para-new", self.run_scan()["adoption"])

    def test_a_prompt_starting_with_a_slash_counts_without_an_expansion(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20),
                     {"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "/para-new acme"})
        self.assertEqual(self.run_scan()["adoption"]["para-new"]["invocations"], 1)

    def test_invocations_split_by_person(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 18), *slash("p1", "/para-daily-brief"))
        self.session("robin", "bbbbbbbb-1", date(2026, 9, 19), *slash("p1", "/para-daily-brief"))
        self.session("sam", "cccccccc-1", date(2026, 9, 20), *slash("p1", "/para-daily-brief"))
        brief = self.run_scan()["adoption"]["para-daily-brief"]
        self.assertEqual(brief["by_person"], {"robin": 1, "sam": 2})
        self.assertEqual((brief["first"], brief["last"]), ("2026-09-18", "2026-09-20"))

    def test_declared_skills_never_invoked_are_listed_and_para_shared_is_not_a_skill(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20), *slash("p1", "/para-daily-brief"))
        report = self.run_scan()
        self.assertEqual(report["declared_skills"], ["para-daily-brief", "para-new", "para-triage"])
        self.assertEqual(report["never_invoked"], ["para-new", "para-triage"])


class Frame(LedgerCase):
    def test_sessions_nobody_typed_into_are_counted_apart(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20), *slash("p1", "/para-daily-brief"))
        self.session("sam", "bbbbbbbb-1", date(2026, 9, 20))
        frame = self.run_scan()["frame"]
        self.assertEqual((frame["sessions"], frame["typed_sessions"]), (2, 1))

    def test_a_file_outside_the_window_is_not_read(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 8, 1), *slash("p1", "/para-new x"))
        self.session("sam", "bbbbbbbb-1", date(2026, 9, 20), *slash("p1", "/para-daily-brief"))
        report = self.run_scan(days=30)
        self.assertEqual(report["frame"]["sessions"], 1)
        self.assertNotIn("para-new", report["adoption"])

    def test_a_malformed_line_is_skipped_and_counted(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20), *slash("p1", "/para-daily-brief"),
                     raw=("{not json",))
        report = self.run_scan()
        self.assertEqual(report["frame"]["skipped_lines"], 1)
        self.assertEqual(report["adoption"]["para-daily-brief"]["invocations"], 1)

    def test_people_and_days(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 10), *slash("p1", "/para-daily-brief"))
        self.session("robin", "bbbbbbbb-1", date(2026, 9, 20), *slash("p1", "/para-daily-brief"))
        frame = self.run_scan()["frame"]
        self.assertEqual(frame["people"], ["robin", "sam"])
        self.assertEqual((frame["first"], frame["last"], frame["days"]),
                         ("2026-09-10", "2026-09-20", 11))


class ReachAndFriction(LedgerCase):
    def test_reach_counts_sessions_per_bucket_from_targets_and_touched(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20),
                     {"event": "PostToolUse", "prompt_id": "p1", "tool": "Read",
                      "target": "projects/acme/actions.md"},
                     {"event": "PostToolUse", "prompt_id": "p1", "tool": "Bash", "target": "py",
                      "touched": ["areas/business/actions.md"]})
        reach = self.run_scan()["reach"]
        self.assertEqual(reach["sessions_by_bucket"], {"areas": 1, "projects": 1})
        self.assertEqual(reach["untouched_buckets"], ["archive", "triage"])

    def test_files_written_list_every_writer(self):
        write = {"event": "PostToolUse", "prompt_id": "p1", "tool": "Edit",
                 "target": "projects/acme/actions.md"}
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 19), write)
        self.session("robin", "bbbbbbbb-1", date(2026, 9, 20), write)
        self.assertEqual(self.run_scan()["reach"]["writers_by_file"],
                         {"projects/acme/actions.md": ["robin", "sam"]})

    def test_a_skill_name_is_not_a_path(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20), skill_call("p1", "para-new"))
        self.assertEqual(self.run_scan()["reach"]["sessions_by_bucket"], {})

    def test_failures_and_denials_group_by_tool_and_target(self):
        fail = {"event": "PostToolUseFailure", "prompt_id": "p1", "tool": "Edit",
                "target": "projects/acme/actions.md"}
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20), fail, fail,
                     {"event": "PermissionDenied", "prompt_id": "p2", "tool": "Bash",
                      "target": "rm"})
        friction = self.run_scan()["friction"]
        self.assertEqual(friction["failures"],
                         [{"event": "PostToolUseFailure", "tool": "Edit",
                           "target": "projects/acme/actions.md", "count": 2},
                          {"event": "PermissionDenied", "tool": "Bash", "target": "rm",
                           "count": 1}])

    def test_tool_calls_per_request(self):
        read = {"event": "PostToolUse", "prompt_id": "p1", "tool": "Read", "target": "areas/x.md"}
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20),
                     {"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "tidy it"},
                     read, read, read)
        worst = self.run_scan()["friction"]["tools_per_request"][0]
        self.assertEqual((worst["tools"], worst["prompt"]), (3, "tidy it"))

    def test_a_session_that_wrote_nothing_is_listed(self):
        self.session("sam", "aaaaaaaa-1", date(2026, 9, 20),
                     {"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "file this"})
        self.assertEqual(self.run_scan()["friction"]["typed_without_writes"], 1)


class Cli(LedgerCase):
    def test_no_ledger_exits_3(self):
        shutil.rmtree(self.root / "resources")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--vault", str(self.root), "--today", "2026-09-21"])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out.getvalue())["error"], "no ledger")


if __name__ == "__main__":
    unittest.main()
