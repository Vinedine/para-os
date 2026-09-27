#!/usr/bin/env python3
"""Tests for the activity integration's pure functions.

    python3 test_activity.py

No runner and no dependency beyond unittest. The cases that matter are the redaction
ones: everything else here is filename arithmetic, but a redaction bug writes a client's
file contents into a log and nothing downstream would ever notice.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "activity.py"

spec = importlib.util.spec_from_file_location("activity", SCRIPT)
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)

ROOT = Path("/vault").resolve()


class TestRedaction(unittest.TestCase):
    def test_file_path_is_relative_to_the_vault(self):
        got = ledger.redact_tool_input("Read", {"file_path": str(ROOT / "areas" / "x.md")}, ROOT)
        self.assertEqual(got, "areas/x.md")

    def test_path_outside_the_vault_is_kept_verbatim(self):
        # Not silently dropped: reading outside the vault is a real signal about how
        # someone works, and hiding it would make the review skill quietly wrong.
        got = ledger.redact_tool_input("Read", {"file_path": "/elsewhere/notes.md"}, ROOT)
        self.assertIn("elsewhere", got)

    def test_bash_keeps_only_the_first_token(self):
        got = ledger.redact_tool_input(
            "Bash", {"command": "curl -H 'Authorization: Bearer sk-secret' https://x"}, ROOT
        )
        self.assertEqual(got, "curl")

    def test_bash_skips_leading_environment_assignments(self):
        got = ledger.redact_tool_input(
            "Bash", {"command": "OPENAI_API_KEY=sk-live-123 DEBUG=1 python run.py"}, ROOT)
        self.assertEqual(got, "python")

    def test_bash_skips_quoted_assignment_values_holding_spaces(self):
        got = ledger.redact_tool_input(
            "Bash", {"command": "TOKEN=\"sk live 123\" NOTE='a b' node sync.js"}, ROOT)
        self.assertEqual(got, "node")

    def test_bash_of_only_assignments_records_nothing(self):
        for command in ("OPENAI_API_KEY=sk-live-123", "A=1 B='two words'", "TOKEN=\"unclosed sk-live"):
            with self.subTest(command=command):
                self.assertIsNone(ledger.redact_tool_input("Bash", {"command": command}, ROOT))

    def test_bash_with_an_empty_command_records_nothing(self):
        self.assertIsNone(ledger.redact_tool_input("Bash", {"command": "   "}, ROOT))

    def test_grep_keeps_the_pattern(self):
        got = ledger.redact_tool_input("Grep", {"pattern": "invoice"}, ROOT)
        self.assertEqual(got, "invoice")

    def test_grep_with_a_path_still_keeps_the_pattern(self):
        # `path` scopes a Grep/Glob search to a folder - a common combination. The pattern,
        # what was searched for, is the signal worth keeping, not the folder it was scoped to.
        got = ledger.redact_tool_input(
            "Grep", {"pattern": "invoice", "path": "areas/finance"}, ROOT)
        self.assertEqual(got, "invoice")

    def test_skill_records_the_skill_name(self):
        # The one signal the review skill is built on: "Skill" alone says a skill ran,
        # never which, so the capabilities nobody used could not be found.
        got = ledger.redact_tool_input("Skill", {"skill": "para-triage", "args": "apply"}, ROOT)
        self.assertEqual(got, "para-triage")

    def test_subagent_records_its_type_and_not_its_prompt(self):
        got = ledger.redact_tool_input(
            "Task", {"subagent_type": "Explore", "prompt": "confidential brief text"}, ROOT
        )
        self.assertEqual(got, "Explore")

    def test_unknown_tool_records_nothing_from_its_input(self):
        # The default has to be silence: an MCP tool's arguments can hold a mail body.
        got = ledger.redact_tool_input(
            "mcp__mail__search", {"query": "salary review", "body": "confidential"}, ROOT
        )
        self.assertIsNone(got)

    def test_non_dict_input_is_survivable(self):
        self.assertIsNone(ledger.redact_tool_input("Read", "not-a-dict", ROOT))


class TestRecord(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(ledger.DEFAULTS)

    def test_tool_response_never_reaches_the_record(self):
        event = {
            "hook_event_name": "PostToolUse",
            "session_id": "s1",
            "tool_name": "Read",
            "tool_input": {"file_path": str(ROOT / "a.md")},
            "tool_response": "the entire contents of a client file",
        }
        record = ledger.build_record(event, ROOT, self.cfg, "2026-08-29T10:00:00")
        self.assertNotIn("the entire contents", json.dumps(record))

    def test_prompt_is_truncated_to_the_configured_length(self):
        cfg = {"record_prompts": True, "prompt_max_chars": 10}
        event = {"hook_event_name": "UserPromptSubmit", "prompt": "x" * 50}
        record = ledger.build_record(event, ROOT, cfg, "2026-08-29T10:00:00")
        self.assertEqual(len(record["prompt"]), 10)

    def test_prompts_can_be_switched_off_entirely(self):
        cfg = {"record_prompts": False, "prompt_max_chars": 500}
        event = {"hook_event_name": "UserPromptSubmit", "prompt": "sensitive question"}
        record = ledger.build_record(event, ROOT, cfg, "2026-08-29T10:00:00")
        self.assertNotIn("prompt", record)

    def test_a_slash_command_survives_prompts_being_off(self):
        # A slash command is expanded, never issued as a tool call, so this is the only
        # place it appears. Dropping it with the prose would leave the privacy setting
        # unable to answer the question the ledger exists for.
        cfg = {"record_prompts": False, "prompt_max_chars": 500}
        event = {"hook_event_name": "UserPromptExpansion", "prompt": "/para-triage apply"}
        record = ledger.build_record(event, ROOT, cfg, "2026-08-29T10:00:00")
        self.assertEqual(record["prompt"], "/para-triage")

    def test_empty_fields_are_dropped_rather_than_written_as_null(self):
        event = {"hook_event_name": "SessionEnd", "session_id": "s1", "reason": "clear"}
        record = ledger.build_record(event, ROOT, self.cfg, "2026-08-29T10:00:00")
        self.assertEqual(set(record), {"at", "event", "session", "reason"})


class TestConfig(unittest.TestCase):
    def test_config_is_read_from_the_conventional_name_beside_the_script(self):
        # `<integration>.config.json` beside the script, per the scripts convention: the
        # secret uses the bare `<name>.json`, and one name across two trust zones is how a
        # credential ends up in a synced folder. Asserted so a rename cannot drift silently.
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "activity.py"
            script.touch()
            (script.with_name("activity.config.json")).write_text(
                json.dumps({"record_prompts": False}), encoding="utf-8")
            self.assertFalse(ledger.load_config(script)["record_prompts"])

    def test_an_unreadable_config_falls_back_to_the_defaults(self):
        # Fail open, like everything else here: a broken config must not stop a session.
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "activity.py"
            script.touch()
            script.with_name("activity.config.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(ledger.load_config(script), ledger.DEFAULTS)

    def test_a_setting_of_the_wrong_type_falls_back_to_its_default(self):
        # A string where a number belongs reaches arithmetic before the line is written,
        # and the catch-all in __main__ would swallow the whole record. The ledger would
        # stop, silently, and the review would report a vault nobody uses.
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "activity.py"
            script.touch()
            script.with_name("activity.config.json").write_text(
                json.dumps({"touched_slack_ms": "2s", "touched_max_files": 5}),
                encoding="utf-8")
            cfg = ledger.load_config(script)
            self.assertEqual(cfg["touched_slack_ms"], ledger.DEFAULTS["touched_slack_ms"])
            self.assertEqual(cfg["touched_max_files"], 5)   # the valid one still applies

    def test_a_config_that_is_not_an_object_falls_back_to_the_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "activity.py"
            script.touch()
            script.with_name("activity.config.json").write_text(
                '[{"record_prompts": false}]', encoding="utf-8")
            self.assertEqual(ledger.load_config(script), ledger.DEFAULTS)


class TestPaths(unittest.TestCase):
    def test_user_slug_is_filename_safe(self):
        self.assertEqual(ledger.user_slug({"USERNAME": "Sofie Vermeulen"}), "sofie-vermeulen")

    def test_user_slug_falls_back_rather_than_failing(self):
        self.assertEqual(ledger.user_slug({}), "unknown")

    def test_one_file_per_session_per_user_per_day(self):
        path = ledger.log_path(ROOT, "ann", "7638d0d5-03df-47ba", "20260829")
        self.assertEqual(path.name, "20260829-ann-7638d0d5.jsonl")
        self.assertEqual(path.parent.name, "sessions")

    def test_a_missing_session_id_still_produces_a_filename(self):
        path = ledger.log_path(ROOT, "ann", None, "20260829")
        self.assertEqual(path.name, "20260829-ann-nosessio.jsonl")

    def test_vault_root_is_two_levels_above_the_script(self):
        got = ledger.vault_root("/v/resources/scripts/activity.py")
        self.assertEqual(got.name, "v")


def scaffold_vault(tmp):
    """A vault holding an installed copy of the hook, at `<vault>/resources/scripts/`.

    Module-level because every end-to-end test needs it: the hook resolves its vault from
    its own location, so it can only be exercised from a real directory layout.
    """
    root = Path(tmp).resolve()
    scripts = root / "resources" / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "activity.py"
    script.write_bytes(SCRIPT.read_bytes())
    return root, script


def fire(script, event):
    """One hook invocation, the way Claude Code makes it: the event as JSON on stdin."""
    subprocess.run([sys.executable, str(script)], input=json.dumps(event),
                   capture_output=True, text=True, check=False)


def session_lines(root):
    """Every record the hook wrote, from the one session file it should have made."""
    logs = list((root / "resources" / "logs" / "sessions").glob("*.jsonl"))
    assert len(logs) == 1, f"expected one session file, got {len(logs)}"
    return [json.loads(x) for x in logs[0].read_text(encoding="utf-8").splitlines() if x.strip()]


class TestTouchScanSelection(unittest.TestCase):
    """Which events get a filesystem scan at all.

    A tool that already names its file needs no scan; scanning it would record the same
    path twice and make every write look like two.
    """

    def test_bash_is_scanned_because_its_writes_are_invisible(self):
        self.assertTrue(ledger.wants_touch_scan("PostToolUse", "Bash"))

    def test_a_failed_tool_call_is_still_scanned(self):
        # A script can write half its output and then exit non-zero. Those files exist.
        self.assertTrue(ledger.wants_touch_scan("PostToolUseFailure", "Bash"))

    def test_write_is_not_scanned_because_it_already_names_its_path(self):
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "Write"))
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "Edit"))
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "NotebookEdit"))

    def test_a_read_only_tool_is_not_scanned(self):
        # Not just wasted work. On a synced library something lands a file every few
        # seconds, so scanning a read attributes other people's writes to the reader.
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "Read"))
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "Grep"))
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "WebFetch"))
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "ToolSearch"))

    def test_a_subagent_is_not_scanned(self):
        # A subagent runs the hook for its own tools, so scanning it in the parent double-counts.
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", "Task"))

    def test_an_mcp_tool_is_scanned(self):
        self.assertTrue(ledger.wants_touch_scan("PostToolUse", "mcp__x__write_thing"))

    def test_non_tool_events_are_not_scanned(self):
        self.assertFalse(ledger.wants_touch_scan("UserPromptSubmit", None))
        self.assertFalse(ledger.wants_touch_scan("SessionEnd", None))

    def test_a_tool_event_that_names_no_tool_is_not_scanned(self):
        # Nothing to attribute the files to, so a scan would only produce noise.
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", None))
        self.assertFalse(ledger.wants_touch_scan("PostToolUse", ""))


class TestTouchedPaths(unittest.TestCase):
    """The fix for the blind spot: files a Bash-invoked script wrote.

    The hook only ever sees a command's first token, so a script that writes sixty files
    is recorded as `py`. This scan closes that gap by asking the filesystem what moved
    while the tool was running.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, relpath, age_s=0.0):
        p = self.root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        if age_s:
            old = time.time() - age_s
            os.utime(p, (old, old))
        return p

    def test_a_file_written_inside_the_window_is_found(self):
        self._write("resources/customers/ku-leuven.md")
        paths, total = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertIn("resources/customers/ku-leuven.md", paths)
        self.assertEqual(total, 1)

    def test_a_file_older_than_the_window_is_ignored(self):
        self._write("areas/network/jan.md", age_s=3600)
        paths, total = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertEqual(paths, [])
        self.assertEqual(total, 0)

    def test_the_ledger_itself_is_never_reported(self):
        # Without this the hook logs its own log file on every single call, forever.
        self._write("resources/logs/sessions/20260904-user-abc.jsonl")
        paths, _ = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertEqual(paths, [])

    def test_noise_directories_are_skipped(self):
        self._write("__pycache__/activity.cpython-312.pyc")
        self._write(".git/index")
        self._write("node_modules/pkg/index.js")
        paths, _ = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertEqual(paths, [])

    def test_a_vault_folder_named_logs_is_not_noise(self):
        # Only the ledger's own folder is excluded, by path. Skipping every directory
        # called `logs` would also hide a project that keeps one, for no stated reason.
        self._write("projects/x/logs/run-2026-09-04.md")
        paths, _ = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertEqual(paths, ["projects/x/logs/run-2026-09-04.md"])

    def test_office_lock_files_are_skipped(self):
        # Opening a .docx in Word creates one of these next to it; it is not an edit.
        self._write("projects/x/~$brief.docx")
        paths, _ = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertEqual(paths, [])

    def test_paths_are_vault_relative_and_posix(self):
        self._write("projects/jan-handover-workshops/actions.md")
        paths, _ = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertEqual(paths, ["projects/jan-handover-workshops/actions.md"])

    def test_the_list_is_capped_but_the_true_count_survives(self):
        # One script run can write dozens of files. The cap keeps one ledger line from
        # becoming a page; the count keeps the fact.
        for i in range(10):
            self._write(f"resources/customers/c{i:02d}.md")
        paths, total = ledger.touched_paths(self.root, time.time() - 30, 4)
        self.assertEqual(len(paths), 4)
        self.assertEqual(total, 10)

    def test_a_missing_root_fails_open(self):
        paths, total = ledger.touched_paths(self.root / "gone", time.time() - 30, 40)
        self.assertEqual((paths, total), ([], 0))

    def test_an_unreadable_file_does_not_abort_the_scan(self):
        self._write("areas/a.md")
        self._write("areas/b.md")
        real_scandir = os.scandir

        class Flaky:
            """A DirEntry whose stat() fails, as one the sync client holds a handle on does."""

            def __init__(self, entry):
                self._e = entry

            def __getattr__(self, name):
                return getattr(self._e, name)

            def is_dir(self, **kw):
                return self._e.is_dir(**kw)

            def stat(self, *a, **kw):
                if self._e.name == "a.md":
                    raise OSError("locked by the sync client")
                return self._e.stat(*a, **kw)

        class Scan:
            def __init__(self, path):
                self._entries = [Flaky(e) for e in real_scandir(path)]

            def __enter__(self):
                return iter(self._entries)

            def __exit__(self, *exc):
                return False

        with mock.patch("os.scandir", side_effect=Scan):
            paths, total = ledger.touched_paths(self.root, time.time() - 30, 40)
        self.assertEqual((paths, total), (["areas/b.md"], 1))


class TestTouchedEndToEnd(unittest.TestCase):
    def test_a_bash_event_records_the_file_a_script_just_wrote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            # Age the script itself so the assertion is about the customer file, not about
            # the copy this test just made.
            old = time.time() - 7200
            os.utime(script, (old, old))

            written = root / "resources" / "customers" / "umicore.md"
            written.parent.mkdir(parents=True, exist_ok=True)
            written.write_text("# Umicore", encoding="utf-8")

            event = {
                "hook_event_name": "PostToolUse",
                "session_id": "abcdef1234",
                "tool_name": "Bash",
                "tool_input": {"command": "py export.py --write"},
                "duration_ms": 4200,
            }
            fire(script, event)

            line = session_lines(root)[0]
            self.assertEqual(line["target"], "py")     # unchanged: still the first token only
            self.assertIn("resources/customers/umicore.md", line["touched"])

    def test_a_write_event_reports_no_touched_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            target = root / "areas" / "finance" / "brief.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Finance", encoding="utf-8")

            event = {
                "hook_event_name": "PostToolUse",
                "session_id": "abcdef1234",
                "tool_name": "Write",
                "tool_input": {"file_path": str(target)},
                "duration_ms": 30,
            }
            fire(script, event)

            line = session_lines(root)[0]
            self.assertEqual(line["target"], "areas/finance/brief.md")
            self.assertNotIn("touched", line)

    def test_record_touched_false_skips_the_filesystem_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            script.with_name("activity.config.json").write_text('{"record_touched": false}', encoding="utf-8")
            written = root / "new.md"
            written.write_text("content", encoding="utf-8")
            event = {
                "hook_event_name": "PostToolUse",
                "session_id": "abc",
                "tool_name": "Bash",
                "tool_input": {"command": "echo hi"},
                "duration_ms": 100,
            }
            fire(script, event)
            line = session_lines(root)[0]
            self.assertNotIn("touched", line)


class TestSessionSummary(unittest.TestCase):
    """What replaces a `reason` field that never varies.

    `reason` is the harness's, not ours: its five documented values are clear, resume,
    logout, prompt_input_exit and other, and a client may report `other` for every ending.
    The ledger cannot make that field truthful, so it answers the question the field was
    meant to answer - did this session do anything, and did it stop mid-request - from
    evidence it owns.
    """

    def _rec(self, event, at, **kw):
        r = {"event": event, "at": at}
        r.update(kw)
        return r

    def test_counts_come_from_the_session_own_lines(self):
        records = [
            self._rec("SessionStart", "2026-09-04T10:00:00"),
            self._rec("UserPromptSubmit", "2026-09-04T10:00:05", prompt="do it"),
            self._rec("PostToolUse", "2026-09-04T10:00:06", tool="Bash"),
            self._rec("PostToolUse", "2026-09-04T10:00:07", tool="Write"),
            self._rec("PostToolUseFailure", "2026-09-04T10:00:08", tool="Bash"),
            self._rec("PermissionDenied", "2026-09-04T10:00:09", tool="Bash"),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:01:00")
        self.assertEqual(s["prompts"], 1)
        self.assertEqual(s["tools"], 3)      # two PostToolUse plus the failure
        self.assertEqual(s["writes"], 1)
        self.assertEqual(s["failures"], 1)
        self.assertEqual(s["denials"], 1)
        self.assertEqual(s["duration_s"], 60)

    def test_a_script_write_counts_even_though_no_write_tool_ran(self):
        # The whole point of `touched`: work done by a Bash-invoked script is still work.
        records = [
            self._rec("SessionStart", "2026-09-04T10:00:00"),
            self._rec("UserPromptSubmit", "2026-09-04T10:00:01", prompt="build them"),
            self._rec("PostToolUse", "2026-09-04T10:00:02", tool="Bash",
                      touched=["resources/customers/a.md"]),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:10")
        self.assertEqual(s["writes"], 1)

    def test_a_failed_write_is_not_counted_as_a_write(self):
        # `writes: 0` is how the review finds a session that produced nothing. A session
        # whose every Write failed is exactly that session, and must not report otherwise.
        records = [
            self._rec("SessionStart", "2026-09-04T10:00:00"),
            self._rec("UserPromptSubmit", "2026-09-04T10:00:01", prompt="save it"),
            self._rec("PostToolUseFailure", "2026-09-04T10:00:02", tool="Write"),
            self._rec("PostToolUseFailure", "2026-09-04T10:00:03", tool="Edit"),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:10")
        self.assertEqual(s["writes"], 0)
        self.assertEqual(s["failures"], 2)

    def test_a_failed_call_that_still_touched_files_counts(self):
        # The other half: a script can write half its output and then exit non-zero.
        records = [
            self._rec("SessionStart", "2026-09-04T10:00:00"),
            self._rec("PostToolUseFailure", "2026-09-04T10:00:02", tool="Bash",
                      touched=["resources/customers/a.md"]),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:10")
        self.assertEqual(s["writes"], 1)

    def test_a_session_nobody_typed_into_is_explicit_rather_than_inferred(self):
        # Most sessions in a real ledger can look like this. Left implicit, every count downstream
        # is wrong; stated here, the review can exclude them by reading one field.
        records = [self._rec("SessionStart", "2026-09-04T10:00:00")]
        s = ledger.summarise_session(records, "2026-09-04T10:00:01")
        self.assertEqual(s["prompts"], 0)
        self.assertEqual(s["tools"], 0)

    def test_tool_calls_after_the_last_prompt_are_counted_separately(self):
        records = [
            self._rec("UserPromptSubmit", "2026-09-04T10:00:00", prompt="first"),
            self._rec("PostToolUse", "2026-09-04T10:00:01", tool="Bash"),
            self._rec("UserPromptSubmit", "2026-09-04T10:00:02", prompt="second"),
            self._rec("PostToolUse", "2026-09-04T10:00:03", tool="Bash"),
            self._rec("PostToolUse", "2026-09-04T10:00:04", tool="Bash"),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:05")
        self.assertEqual(s["last_prompt_tools"], 2)

    def test_a_final_prompt_that_produced_nothing_reads_as_zero(self):
        records = [
            self._rec("UserPromptSubmit", "2026-09-04T10:00:00", prompt="first"),
            self._rec("PostToolUse", "2026-09-04T10:00:01", tool="Bash"),
            self._rec("UserPromptSubmit", "2026-09-04T10:00:02", prompt="are you there"),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:03")
        self.assertEqual(s["last_prompt_tools"], 0)

    def test_a_slash_command_counts_as_a_prompt(self):
        # An expansion is how a skill invocation arrives; it is not a second prompt on top
        # of a submit, so the two must not both count for one request.
        records = [
            self._rec("UserPromptExpansion", "2026-09-04T10:00:00", prompt="/para-triage"),
            self._rec("PostToolUse", "2026-09-04T10:00:01", tool="Bash"),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:02")
        self.assertEqual(s["prompts"], 1)

    def test_an_expansion_and_its_submit_under_one_prompt_id_count_once(self):
        # A slash command fires both events under one id. Counting events would double every
        # skill invocation in the vault; counting ids keeps two real requests at two.
        records = [
            self._rec("UserPromptExpansion", "2026-09-04T10:00:00", prompt="/para-triage",
                      prompt_id="p1"),
            self._rec("UserPromptSubmit", "2026-09-04T10:00:00", prompt="/para-triage",
                      prompt_id="p1"),
            self._rec("PostToolUse", "2026-09-04T10:00:01", tool="Bash"),
            self._rec("UserPromptSubmit", "2026-09-04T10:00:02", prompt="and the rest",
                      prompt_id="p2"),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:03")
        self.assertEqual(s["prompts"], 2)
        self.assertEqual(s["last_prompt_tools"], 0)

    def test_an_unparseable_timestamp_does_not_lose_the_counts(self):
        records = [
            self._rec("UserPromptSubmit", "not-a-timestamp", prompt="x"),
            self._rec("PostToolUse", "also-not", tool="Bash"),
        ]
        s = ledger.summarise_session(records, "2026-09-04T10:00:02")
        self.assertEqual(s["prompts"], 1)
        self.assertNotIn("duration_s", s)

    def test_reading_a_missing_ledger_file_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ledger.read_session_records(Path(tmp) / "nope.jsonl"), [])

    def test_a_truncated_final_line_is_skipped_not_fatal(self):
        # The hook fails open mid-write, so a half line is a normal end-of-file artifact.
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "s.jsonl"
            p.write_text('{"event":"UserPromptSubmit","at":"2026-09-04T10:00:00"}\n'
                         '{"event":"PostToo', encoding="utf-8")
            records = ledger.read_session_records(p)
            self.assertEqual(len(records), 1)

    def test_blank_lines_and_lines_that_are_not_records_are_skipped(self):
        # A sync client's merge can leave blank lines, and valid JSON is not always an object.
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "s.jsonl"
            p.write_text('\n[1, 2]\n"a string"\n'
                         '{"event":"UserPromptSubmit","at":"2026-09-04T10:00:00"}\n\n',
                         encoding="utf-8")
            self.assertEqual(ledger.read_session_records(p),
                             [{"event": "UserPromptSubmit", "at": "2026-09-04T10:00:00"}])


class TestSessionEndEndToEnd(unittest.TestCase):
    def test_session_end_carries_a_summary_of_the_session_before_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            sid = "abcdef1234"
            fire(script, {"hook_event_name": "SessionStart", "session_id": sid,
                                "source": "startup"})
            fire(script, {"hook_event_name": "UserPromptSubmit", "session_id": sid,
                                "prompt": "file the invoice"})
            fire(script, {"hook_event_name": "PostToolUse", "session_id": sid,
                                "tool_name": "Read",
                                "tool_input": {"file_path": str(root / "a.md")},
                                "duration_ms": 12})
            fire(script, {"hook_event_name": "SessionEnd", "session_id": sid,
                                "reason": "other"})

            logs = list((root / "resources" / "logs" / "sessions").glob("*.jsonl"))
            lines = [json.loads(x) for x in
                     logs[0].read_text(encoding="utf-8").splitlines() if x.strip()]
            end = lines[-1]
            self.assertEqual(end["event"], "SessionEnd")
            self.assertEqual(end["reason"], "other")   # still recorded, still the harness's
            self.assertEqual(end["summary"]["prompts"], 1)
            self.assertEqual(end["summary"]["tools"], 1)
            self.assertEqual(end["summary"]["writes"], 0)

    def test_a_session_with_no_prompt_says_so_at_its_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            sid = "beefbeef99"
            fire(script, {"hook_event_name": "SessionStart", "session_id": sid,
                                "source": "startup"})
            fire(script, {"hook_event_name": "SessionEnd", "session_id": sid,
                                "reason": "other"})

            logs = list((root / "resources" / "logs" / "sessions").glob("*.jsonl"))
            lines = [json.loads(x) for x in
                     logs[0].read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(lines[-1]["summary"]["prompts"], 0)

    def test_a_tool_event_carries_no_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            fire(script, {"hook_event_name": "PostToolUse", "session_id": "s1",
                                "tool_name": "Read",
                                "tool_input": {"file_path": str(root / "a.md")},
                                "duration_ms": 5})
            line = session_lines(root)[0]
            self.assertNotIn("summary", line)

    def test_record_summary_false_skips_summarising(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            script.with_name("activity.config.json").write_text('{"record_summary": false}', encoding="utf-8")
            fire(script, {"hook_event_name": "SessionEnd", "session_id": "s1", "reason": "other"})
            line = session_lines(root)[0]
            self.assertNotIn("summary", line)


class TestHookInProcess(unittest.TestCase):
    """main() run in this process against an installed copy's location.

    The end-to-end tests above fire a copy in a subprocess, which is the real invocation but
    leaves the arithmetic inside main() unmeasured. These pin that arithmetic: the file a line
    lands in, the window the scan looks back over, and the cap on what it lists.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, self.script = scaffold_vault(tmp.name)
        self.age(self.script)

    @staticmethod
    def age(path, seconds=7200):
        old = time.time() - seconds
        os.utime(path, (old, old))

    def write(self, relpath, age_s=0):
        p = self.root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        if age_s:
            self.age(p, age_s)
        return p

    def configure(self, **settings):
        cfg = self.script.with_name("activity.config.json")
        cfg.write_text(json.dumps(settings), encoding="utf-8")
        self.age(cfg)

    def run_hook(self, event, user="Ann Smith"):
        with mock.patch.object(ledger, "__file__", str(self.script)), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), \
                mock.patch.dict(os.environ, {"USERNAME": user}):
            ledger.main()

    @staticmethod
    def bash(duration_ms, session="abcdef123456"):
        return {"hook_event_name": "PostToolUse", "session_id": session, "tool_name": "Bash",
                "tool_input": {"command": "py export.py"}, "duration_ms": duration_ms}

    def test_the_file_is_named_for_the_day_the_writer_and_the_session(self):
        days = {time.strftime("%Y%m%d")}
        self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "abcdef123456",
                       "prompt": "hi"})
        days.add(time.strftime("%Y%m%d"))          # a run that straddles midnight
        names = [p.name for p in (self.root / "resources" / "logs" / "sessions").iterdir()]
        self.assertEqual(len(names), 1)
        self.assertIn(names[0], {f"{d}-ann-smith-abcdef12.jsonl" for d in days})

    def test_an_event_that_is_not_a_named_event_writes_nothing(self):
        for event in ({"session_id": "abc", "prompt": "no hook_event_name"}, [1, 2, 3]):
            with self.subTest(event=event):
                self.run_hook(event)
                self.assertFalse((self.root / "resources" / "logs").exists())

    def test_the_scan_window_reaches_back_over_the_tools_own_duration(self):
        # A ten-minute script wrote its first file long before the hook fired; the same file
        # after a 100 ms call is somebody else's.
        self.write("resources/customers/early.md", age_s=300)
        self.write("areas/stale.md", age_s=3600)
        self.run_hook(self.bash(duration_ms=600000))
        self.run_hook(self.bash(duration_ms=100))
        long_run, short_run = session_lines(self.root)
        self.assertEqual(long_run["touched"], ["resources/customers/early.md"])
        self.assertNotIn("touched_total", long_run)       # nothing was capped
        self.assertNotIn("touched", short_run)

    def test_a_capped_touched_list_keeps_the_true_count(self):
        self.configure(touched_max_files=2)
        for i in range(5):
            self.write(f"resources/customers/c{i}.md")
        self.run_hook(self.bash(duration_ms=1000))
        line = session_lines(self.root)[0]
        self.assertEqual(line["touched"], ["resources/customers/c0.md", "resources/customers/c1.md"])
        self.assertEqual(line["touched_total"], 5)

    def test_a_session_end_summarises_its_own_session_only(self):
        # One file per session is what keeps concurrent sessions from reading as one.
        for sid, prompts in (("aaaa1111", 1), ("bbbb2222", 3)):
            for i in range(prompts):
                self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": sid,
                               "prompt": f"request {i}"})
        self.run_hook({"hook_event_name": "SessionEnd", "session_id": "aaaa1111",
                       "reason": "other"})
        sessions = self.root / "resources" / "logs" / "sessions"
        [own] = sessions.glob("*-aaaa1111.jsonl")
        end = json.loads(own.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(end["event"], "SessionEnd")
        self.assertEqual(end["summary"]["prompts"], 1)


class TestFailOpen(unittest.TestCase):
    """The contract that keeps a hook from becoming an outage."""

    def _run(self, payload):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=payload, capture_output=True, text=True,
        )

    def test_malformed_json_exits_zero(self):
        self.assertEqual(self._run("{not json").returncode, 0)

    def test_empty_stdin_exits_zero(self):
        self.assertEqual(self._run("").returncode, 0)

    def test_unknown_event_shape_exits_zero(self):
        self.assertEqual(self._run(json.dumps([1, 2, 3])).returncode, 0)

    def test_interactive_stdin_returns_without_blocking(self):
        # A tty read blocks forever; a manual invocation with nothing piped must not hang.
        with mock.patch.object(sys, "stdin") as fake_stdin:
            fake_stdin.isatty.return_value = True
            ledger.main()
            fake_stdin.read.assert_not_called()


class TestEndToEnd(unittest.TestCase):
    def test_a_real_event_lands_as_one_jsonl_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, script = scaffold_vault(tmp)
            fire(script, {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "abcdef1234",
                "prompt": "file the invoice",
                "cwd": str(root),
            })

            lines = session_lines(root)
            self.assertEqual(len(lines), 1)
            line = lines[0]
            self.assertEqual(line["event"], "UserPromptSubmit")
            self.assertEqual(line["prompt"], "file the invoice")


if __name__ == "__main__":
    unittest.main(verbosity=2)
