#!/usr/bin/env python3
"""Tests for the activity integration's pure functions.

    python3 test_activity.py

No runner and no dependency beyond unittest. The cases that matter are the redaction
ones: everything else here is filename arithmetic, but a redaction bug writes a client's
file contents into a log and nothing downstream would ever notice.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
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
            root = Path(tmp)
            scripts = root / "resources" / "scripts"
            scripts.mkdir(parents=True)
            script = scripts / "activity.py"
            script.write_bytes(SCRIPT.read_bytes())

            event = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "abcdef1234",
                "prompt": "file the invoice",
                "cwd": str(root),
            }
            subprocess.run([sys.executable, str(script)], input=json.dumps(event),
                           capture_output=True, text=True, check=False)

            written = list((root / "resources" / "logs" / "sessions").glob("*.jsonl"))
            self.assertEqual(len(written), 1)
            line = json.loads(written[0].read_text(encoding="utf-8").strip())
            self.assertEqual(line["event"], "UserPromptSubmit")
            self.assertEqual(line["prompt"], "file the invoice")


if __name__ == "__main__":
    unittest.main(verbosity=2)
