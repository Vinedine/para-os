#!/usr/bin/env python3
"""Tests for stage.py: /para-ingest's notes, ledger and run log, written from one run's
routed threads.

    python3 test_stage.py
    py -3 test_stage.py

Standard library only. Every vault, registry and ledger here is synthetic, built in a
temporary folder that stands in for the paraos home.
"""

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "multi-vault" / "para-ingest" / "scripts"))

from stage import main, safe_subject, stage  # noqa: E402

MAILBOX = "me@example.org"
THREAD = {
    "mailbox": MAILBOX, "source": "gmail", "thread_id": "18c2f0a1b2c3d4e5",
    "subject": "Re: Quarterly report",
    "link": "https://mail.google.com/mail/u/0/#all/18c2f0a1b2c3d4e5",
    "routed": ["alpha"], "reason": "contact: anna@example.org",
    "text": "preview", "own_messages": False,
    "messages": [
        {"message_id": "<m2@example.org>", "from": "Anna Example <anna@example.org>",
         "received": "2026-10-23T11:30:00+00:00", "subject": "Re: Quarterly report",
         "read": "18c2f0a1b2c3d4f0", "text": "Corrected figures."},
        {"message_id": "<m1@example.org>", "from": "Anna Example <anna@example.org>",
         "received": "2026-10-23T09:00:00+00:00", "subject": "Quarterly report",
         "read": "18c2f0a1b2c3d4e5", "text": "First draft attached."},
    ],
}
NOTE_NAME = "20261023 Re Quarterly report 85f8ab.md"
NOTE = """# Re: Quarterly report

- **Source:** gmail (me@example.org)
- **From:** Anna Example <anna@example.org>
- **Received:** 2026-10-23T11:30:00+00:00
- **Routed:** contact: anna@example.org
- **Content:** preview of 2 messages, not the full text; own messages not fetched
- **Link:** https://mail.google.com/mail/u/0/#all/18c2f0a1b2c3d4e5
- **Message id:** 18c2f0a1b2c3d4f0

**Anna Example <anna@example.org>**, 2026-10-23T09:00:00+00:00

First draft attached.

**Anna Example <anna@example.org>**, 2026-10-23T11:30:00+00:00

Corrected figures.
"""


class StageCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "paraos"
        self.home.mkdir()
        registry = []
        for name, active in (("alpha", True), ("beta", True), ("gamma", False)):
            vault = self.root / name
            (vault / "triage").mkdir(parents=True)
            (vault / "CLAUDE.md").write_text("# Vault\n", encoding="utf-8")
            registry.append({"name": name, "path": vault.as_posix(), "kind": "test",
                             "purpose": f"The {name} vault.", "active": active})
        registry.append({"name": "delta", "path": (self.root / "unmounted").as_posix(),
                         "kind": "test", "purpose": "A drive that is not there.",
                         "active": True})
        (self.home / "vaults.json").write_text(json.dumps(registry), encoding="utf-8")

    def run_input(self, mode="write", threads=None, **extra):
        run = {"mode": mode, "started_at": "2026-10-24T12:00:00+00:00",
               "source_plan": {"declaring_vaults": {MAILBOX: ["alpha", "beta"]}},
               "threads": copy.deepcopy([THREAD] if threads is None else threads)}
        run.update(extra)
        return run

    def stage(self, mode="write", threads=None, **extra):
        return stage(self.run_input(mode, threads, **extra), self.home)

    def thread(self, **changes):
        return dict(copy.deepcopy(THREAD), **changes)

    def notes(self, vault="alpha"):
        return sorted(p.name for p in (self.root / vault / "triage").iterdir())

    def ledger(self):
        path = self.home / "cache" / "ingest" / "ledger.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def log(self, summary):
        return json.loads(Path(summary["log"]).read_text(encoding="utf-8"))


class Preview(StageCase):

    def test_preview_writes_the_run_log_and_nothing_else(self):
        summary = self.stage("preview")
        self.assertEqual(self.notes(), [])
        self.assertFalse((self.home / "cache" / "ingest" / "ledger.json").exists())
        log = self.log(summary)
        self.assertEqual(Path(summary["log"]).parent, self.home / "cache" / "ingest" / "runs")
        self.assertEqual((log["mode"], log["files_written"]), ("preview", []))
        self.assertEqual(log["counts"]["per_vault"], {"alpha": 1, "beta": 0})
        self.assertEqual([d["routed"] for d in log["decisions"]], [["alpha"]])

    def test_preview_names_what_falls_outside_the_write_window(self):
        old = self.thread(thread_id="18c2f0a1b2c3d4ee", messages=[
            dict(THREAD["messages"][1], message_id="<old@example.org>",
                 received="2026-10-19T09:00:00+00:00")])
        log = self.log(self.stage("preview", [THREAD, old]))
        self.assertEqual(log["outside_write_window"],
                         [{"mailbox": MAILBOX, "thread_id": "18c2f0a1b2c3d4ee",
                           "subject": "Re: Quarterly report", "routed": ["alpha"],
                           "received": "2026-10-19T09:00:00+00:00"}])


class Write(StageCase):

    def test_a_write_stages_the_documented_note(self):
        self.stage()
        self.assertEqual(self.notes(), [NOTE_NAME])
        text = (self.root / "alpha" / "triage" / NOTE_NAME).read_text(encoding="utf-8")
        self.assertEqual(text, NOTE)

    def test_a_write_ledgers_the_thread_on_its_newest_message(self):
        self.stage()
        self.assertEqual(self.ledger(), {
            "mailboxes": {MAILBOX: {"18c2f0a1b2c3d4e5": {
                "routed": ["alpha"], "reason": "contact: anna@example.org",
                "date": "2026-10-23", "subject": "Re: Quarterly report",
                "seen_through": "<m2@example.org>",
                "seen_date": "2026-10-23T11:30:00+00:00"}}},
            "by_message_id": {"<m1@example.org>": ["alpha"], "<m2@example.org>": ["alpha"]}})

    def test_a_write_logs_what_triage_reads_and_keeps_what_it_was_given(self):
        summary = self.stage(sync_runs=[{"vault": "beta", "script": "s.py", "written": 0,
                                         "error": None}], errors=["x: expired"],
                             carry_over=[], resolved=[])
        log = self.log(summary)
        self.assertEqual(Path(summary["log"]).name[:9], "20261024-")
        self.assertEqual(log["mode"], "write")
        self.assertEqual(log["started_at"], "2026-10-24T12:00:00+00:00")
        self.assertEqual(log["files_written"],
                         [(self.root / "alpha" / "triage" / NOTE_NAME).as_posix()])
        self.assertEqual(log["counts"]["per_vault"], {"alpha": 1, "beta": 0})
        self.assertEqual(log["source_plan"],
                         {"declaring_vaults": {MAILBOX: ["alpha", "beta"]}})
        self.assertEqual(log["sync_runs"][0]["vault"], "beta")
        self.assertEqual((log["errors"], log["carry_over"], log["resolved"]),
                         (["x: expired"], [], []))
        self.assertEqual(log["decisions"], [{
            "mailbox": MAILBOX, "thread_id": "18c2f0a1b2c3d4e5",
            "subject": "Re: Quarterly report", "received": "2026-10-23T11:30:00+00:00",
            "routed": ["alpha"], "reason": "contact: anna@example.org", "resurfaced": False,
            "staged": ["alpha"], "suppressed": [], "owed": []}])

    def test_a_second_write_of_the_same_mail_stages_nothing(self):
        self.stage()
        again = self.stage(started_at="2026-10-24T12:05:00+00:00")
        self.assertEqual(self.notes(), [NOTE_NAME])
        log = self.log(again)
        self.assertEqual((log["files_written"], log["counts"]["per_vault"]["alpha"]), ([], 0))

    def test_a_thread_routed_to_two_vaults_is_staged_in_both(self):
        self.stage(threads=[self.thread(routed=["alpha", "beta"])])
        self.assertEqual((self.notes("alpha"), self.notes("beta")), ([NOTE_NAME], [NOTE_NAME]))
        self.assertEqual(self.ledger()["by_message_id"]["<m2@example.org>"], ["alpha", "beta"])

    def test_an_unrouted_thread_is_ledgered_and_staged_nowhere(self):
        log = self.log(self.stage(threads=[self.thread(routed=[], reason="no vault's rules")]))
        self.assertEqual(self.notes(), [])
        entry = self.ledger()["mailboxes"][MAILBOX]["18c2f0a1b2c3d4e5"]
        self.assertEqual((entry["routed"], entry["seen_through"]), ([], "<m2@example.org>"))
        self.assertEqual(self.ledger()["by_message_id"], {})
        self.assertEqual(log["counts"]["unrouted"], {MAILBOX: 1})

    def test_a_sign_in_code_is_ledgered_from_its_keys_alone(self):
        code = {"mailbox": MAILBOX, "thread_id": "18c2f0a1b2c3d4e5", "signin": True,
                "messages": [{"message_id": "<code@example.org>",
                              "received": "2026-10-23T11:30:00+00:00"}]}
        log = self.log(self.stage(threads=[code]))
        self.assertEqual(self.notes(), [])
        entry = self.ledger()["mailboxes"][MAILBOX]["18c2f0a1b2c3d4e5"]
        self.assertEqual((entry["subject"], entry["reason"], entry["seen_through"]),
                         ("sign-in or security code", "sign-in or security code",
                          "<code@example.org>"))
        self.assertEqual(log["counts"]["signin_codes"], {MAILBOX: 1})
        self.assertEqual(log["counts"]["unrouted"], {})

    def test_a_fetch_script_record_passes_as_it_is(self):
        message = {"subject": "Invoice 2611", "from": "billing@hostco.example",
                   "from_name": "HostCo", "received": "2026-10-23T11:30:00+00:00",
                   "preview": "Invoice 2611 is attached.", "id": "t3",
                   "message_id": "<t3@mail.example>"}
        record = dict(message, thread_id="t3", link="https://mail.example/t3",
                      message_count=1, messages=[message], participants=[message["from"]],
                      from_owner=False, read="py resources/scripts/mail.py raw t3",
                      mailbox=MAILBOX, source="mail.py fetch", routed=["alpha"],
                      reason="contact: billing@hostco.example", text="preview",
                      own_messages=False)
        self.stage(threads=[record])
        [name] = self.notes()
        text = (self.root / "alpha" / "triage" / name).read_text(encoding="utf-8")
        self.assertIn("- **From:** HostCo <billing@hostco.example>\n", text)
        self.assertIn("- **Message id:** py resources/scripts/mail.py raw t3\n", text)
        self.assertTrue(text.endswith("\n\nInvoice 2611 is attached.\n"))

    def test_a_vault_not_mounted_is_owed_and_the_thread_not_ledgered(self):
        log = self.log(self.stage(threads=[self.thread(routed=["alpha", "delta"])]))
        self.assertEqual(self.notes(), [NOTE_NAME])
        self.assertEqual(self.ledger()["mailboxes"], {})
        self.assertEqual(self.ledger()["by_message_id"]["<m2@example.org>"], ["alpha"])
        self.assertEqual(log["undelivered"], [{
            "mailbox": MAILBOX, "thread_id": "18c2f0a1b2c3d4e5",
            "subject": "Re: Quarterly report", "routed": ["alpha", "delta"],
            "delivered": ["alpha"], "owed": ["delta"],
            "keys": ["<m1@example.org>", "<m2@example.org>"]}])

    def test_the_best_grouped_copy_stages_and_the_other_is_suppressed(self):
        other = self.thread(mailbox="other@example.org", thread_id="AAMkAGI2THREAD",
                            messages=[copy.deepcopy(THREAD["messages"][0])])
        log = self.log(self.stage(threads=[other, THREAD]))
        self.assertEqual(self.notes(), [NOTE_NAME])
        self.assertEqual(log["suppressed"], [{"mailbox": "other@example.org",
                                              "thread_id": "AAMkAGI2THREAD",
                                              "subject": "Re: Quarterly report",
                                              "vaults": ["alpha"]}])
        self.assertEqual(sorted(self.ledger()["mailboxes"]), [MAILBOX, "other@example.org"])

    def test_a_resurfaced_thread_stages_only_what_arrived_after_its_watermark(self):
        first = self.thread(routed=[], reason="no vault's rules",
                            messages=[copy.deepcopy(THREAD["messages"][1])])
        self.stage(threads=[first])
        self.stage(started_at="2026-10-24T13:00:00+00:00")
        text = (self.root / "alpha" / "triage" / NOTE_NAME).read_text(encoding="utf-8")
        self.assertIn("- **Routed:** contact: anna@example.org; resurfaced; previously "
                      "unrouted 2026-10-23, reason: no vault's rules\n", text)
        self.assertIn("- **Content:** preview of 1 message, not the full text; own messages "
                      "not fetched; 1 earlier message left out, already seen\n", text)
        self.assertNotIn("First draft attached.", text)
        entry = self.ledger()["mailboxes"][MAILBOX]["18c2f0a1b2c3d4e5"]
        self.assertEqual((entry["routed"], entry["seen_through"]), (["alpha"], "<m2@example.org>"))

    def test_the_watermark_never_moves_back(self):
        self.stage()
        older = self.thread(routed=[], reason="no vault's rules",
                            messages=[copy.deepcopy(THREAD["messages"][1])])
        self.stage(threads=[older], started_at="2026-10-24T13:00:00+00:00")
        entry = self.ledger()["mailboxes"][MAILBOX]["18c2f0a1b2c3d4e5"]
        self.assertEqual((entry["routed"], entry["seen_through"]), (["alpha"], "<m2@example.org>"))

    def test_a_same_day_restage_takes_the_next_free_name(self):
        triage = self.root / "alpha" / "triage"
        (triage / NOTE_NAME).write_text(NOTE.replace("18c2f0a1b2c3d4f0", "older"),
                                        encoding="utf-8")
        self.stage()
        self.assertEqual(self.notes(), sorted([NOTE_NAME, NOTE_NAME.replace(".md", " 2.md")]))

    def test_a_note_already_on_disk_for_this_message_is_not_written_again(self):
        (self.root / "alpha" / "triage" / NOTE_NAME).write_text(NOTE, encoding="utf-8")
        log = self.log(self.stage())
        self.assertEqual((self.notes(), log["files_written"]), ([NOTE_NAME], []))
        self.assertEqual(self.ledger()["by_message_id"]["<m2@example.org>"], ["alpha"])

    def test_a_full_body_with_own_messages_says_so(self):
        self.stage(threads=[self.thread(text="body", own_messages=True)])
        text = (self.root / "alpha" / "triage" / NOTE_NAME).read_text(encoding="utf-8")
        self.assertIn("- **Content:** full text of 2 messages\n", text)

    def test_a_conversation_id_gets_its_line(self):
        self.stage(threads=[self.thread(conversation_id="AAQkAGI2")])
        text = (self.root / "alpha" / "triage" / NOTE_NAME).read_text(encoding="utf-8")
        self.assertIn("- **Message id:** 18c2f0a1b2c3d4f0\n- **Conversation id:** AAQkAGI2\n\n",
                      text)


class Refusals(StageCase):

    def assert_refused(self, run, words):
        with self.assertRaises(ValueError) as refused:
            stage(run, self.home)
        self.assertIn(words, str(refused.exception))
        self.assertEqual(self.notes(), [])
        self.assertFalse((self.home / "cache" / "ingest" / "runs").exists())

    def test_a_route_to_a_vault_not_active_in_the_registry_is_refused(self):
        for vault in ("gamma", "nowhere"):
            with self.subTest(vault=vault):
                self.assert_refused(self.run_input(threads=[self.thread(routed=[vault])]),
                                    f"thread 1: routed to {vault}")

    def test_a_routed_thread_missing_what_its_note_needs_is_refused(self):
        for field in ("link", "source", "text", "own_messages"):
            with self.subTest(field=field):
                thread = self.thread()
                del thread[field]
                self.assert_refused(self.run_input(threads=[thread]), f"thread 1: no {field}")

    def test_a_routed_thread_with_no_read_for_its_newest_message_is_refused(self):
        thread = self.thread()
        del thread["messages"][0]["read"]
        self.assert_refused(self.run_input(threads=[thread]),
                            "thread 1: no read for its newest message")

    def test_a_message_no_key_or_instant_fits_is_refused(self):
        thread = self.thread()
        thread["messages"][0].update(message_id="", received="yesterday")
        self.assert_refused(self.run_input(threads=[thread]), "thread 1 message 1:")

    def test_an_unknown_mode_is_refused(self):
        self.assert_refused(self.run_input(mode="dry"), "mode")

    def test_a_ledger_that_does_not_parse_is_refused_untouched(self):
        path = self.home / "cache" / "ingest" / "ledger.json"
        path.parent.mkdir(parents=True)
        path.write_text("not json", encoding="utf-8")
        self.assert_refused(self.run_input(), "ledger")
        self.assertEqual(path.read_text(encoding="utf-8"), "not json")

    def test_no_registry_is_refused(self):
        (self.home / "vaults.json").unlink()
        self.assert_refused(self.run_input(), "registry")


class SafeSubject(unittest.TestCase):

    def test_path_hostile_characters_become_spaces_collapsed(self):
        self.assertEqual(safe_subject('Re: a/b\\c *d?* "e" <f>|g'), "Re a b c d e f g")

    def test_edges_a_filesystem_refuses_are_trimmed_and_length_capped(self):
        self.assertEqual(safe_subject(" .Invoice. "), "Invoice")
        self.assertEqual(len(safe_subject("x" * 200)), 80)

    def test_no_subject_still_names_a_note(self):
        self.assertEqual(safe_subject("  "), "no subject")


class CommandLine(StageCase):

    def run_main(self, run):
        path = self.root / "run.json"
        path.write_text(json.dumps(run), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([str(path), "--paraos-home", str(self.home)])
        return code, json.loads(out.getvalue())

    def test_the_command_prints_the_summary_with_its_log(self):
        code, summary = self.run_main(self.run_input())
        self.assertEqual(code, 0)
        self.assertTrue(Path(summary["log"]).is_file())
        self.assertEqual(summary["counts"]["per_vault"], {"alpha": 1, "beta": 0})

    def test_the_command_refuses_bad_input_with_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            self.run_main(self.run_input(mode="dry"))
        self.assertEqual(stop.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
