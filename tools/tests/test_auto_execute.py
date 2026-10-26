#!/usr/bin/env python3
"""Tests for auto_execute.py. Each pins a rule its docstring states: every refusal of `run`,
the quarantine and its manifest, a byte-identical restore that demotes its action, the
ledger both paths write, the promotion offer, the proposal and its item states, and purge.

    python3 test_auto_execute.py
    py -3 test_auto_execute.py

Standard library only. Every vault here is synthetic, built in a temporary folder, and
scanned by the real triage_scan.py, whose saved copy `run` reads.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "base" / ".claude" / "skills" / "para-triage" / "scripts"))

import auto_execute  # noqa: E402
import triage_scan  # noqa: E402


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


DUP = b"same bytes\n" * 20


def call(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = auto_execute.main([str(a) for a in argv])
    return code, json.loads(out.getvalue())


class Executor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "paraos"
        self.vault = self.tmp / "north"
        write(self.vault, "CLAUDE.md", "# north Vault Conventions\n")
        for p in ("projects", "areas", "triage"):
            (self.vault / p).mkdir(parents=True, exist_ok=True)
        write(self.vault, "triage/dup.pdf", DUP.decode())
        write(self.vault, "projects/site/dup.pdf", DUP.decode())
        write(self.vault, "triage/noise.md", "A newsletter.\n")
        write(self.vault, "triage/invoice.md", "Pay the host by Friday.\n")
        write(self.vault, "triage/linked.md", "Linked from a project.\n")
        write(self.vault, "projects/site/README.md", "See [it](../../triage/linked.md).\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def scan(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            triage_scan.main(["--vault", str(self.vault), "--paraos-home", str(self.home)])
        return json.loads(out.getvalue())["saved_to"]

    def decide(self, rows, name="decisions.json"):
        return write(self.tmp, name, json.dumps(rows))

    def switch_on(self, *actions):
        for a in actions:
            self.assertEqual(call("switch", "--vault-name", "north", "--on", a,
                                  "--paraos-home", self.home)[0], 0)

    def run_all(self, rows, cap=25):
        return call("run", "--scan", self.scan(), "--decisions", self.decide(rows),
                    "--cap", cap, "--paraos-home", self.home)

    ROWS = [{"item": "dup.pdf", "action": "Delete (duplicate)",
             "survivor": "projects/site/dup.pdf"},
            {"item": "noise.md", "action": "Dismiss (noise)"},
            {"item": "invoice.md", "action": "Delete (duplicate)", "hold": "money owed"},
            {"item": "linked.md", "action": "Delete (duplicate)"}]

    def test_only_switched_on_unheld_unlinked_items_are_quarantined(self):
        self.switch_on("Delete (duplicate)")
        code, out = self.run_all(self.ROWS)
        self.assertEqual(code, 0)
        self.assertEqual(out["acted"], [{"item": "dup.pdf", "action": "Delete (duplicate)"}])
        reasons = {r["item"]: r["reason"] for r in out["refused"]}
        self.assertIn("not switched on", reasons["noise.md"])
        self.assertEqual(reasons["invoice.md"], "money owed")
        self.assertEqual(reasons["linked.md"], "other files link to it")
        self.assertFalse((self.vault / "triage" / "dup.pdf").exists())
        manifest = json.loads((Path(out["quarantine"]) / "manifest.json").read_text())
        self.assertEqual(manifest["items"][0]["file"]["md5"],
                         auto_execute.hashlib.md5(DUP).hexdigest())
        proposal = Path(out["proposal"]).read_text()
        self.assertIn("| invoice.md | Delete (duplicate) |  | money owed |", proposal)

    def test_refusals_outside_triage_after_a_change_past_the_cap_and_never_types(self):
        self.switch_on("Delete (duplicate)", "Dismiss (noise)")
        saved = self.scan()
        write(self.vault, "triage/noise.md", "Edited after the scan.\n")
        rows = [{"item": "../CLAUDE.md", "action": "Delete (duplicate)"},
                {"item": "noise.md", "action": "Dismiss (noise)"},
                {"item": "dup.pdf", "action": "File it"},
                {"item": "invoice.md", "action": "Dismiss (noise)"},
                {"item": "dup.pdf", "action": "Delete (duplicate)"}]
        code, out = call("run", "--scan", saved, "--decisions", self.decide(rows),
                         "--cap", 1, "--paraos-home", self.home)
        reasons = [r["reason"] for r in out["refused"]]
        self.assertEqual(reasons, ["not a loose file of the scan's triage/",
                                   "changed since the scan", "File it is never unattended",
                                   "over the run's cap of 1"])
        self.assertEqual([a["item"] for a in out["acted"]], ["invoice.md"])

    def test_a_duplicate_the_scan_finds_no_byte_match_for_is_refused(self):
        self.switch_on("Delete (duplicate)")
        write(self.vault, "areas/mail/sources/full.md", "A filed mail.\n" * 20)
        write(self.vault, "triage/shorter.md", "A filed mail.\n" * 19)
        code, out = self.run_all([{"item": "shorter.md", "action": "Delete (duplicate)",
                                   "survivor": "areas/mail/sources/full.md"}])
        self.assertEqual(out["refused"], [{"item": "shorter.md",
                                           "reason": "the scan finds no byte match for it"}])
        self.assertTrue((self.vault / "triage" / "shorter.md").exists())

    def test_a_run_consumes_its_decisions_file(self):
        self.switch_on("Delete (duplicate)")
        saved = self.scan()
        decisions = self.decide(self.ROWS)
        code, out = call("run", "--scan", saved, "--decisions", decisions,
                         "--paraos-home", self.home)
        self.assertEqual(code, 0)
        self.assertTrue(Path(out["quarantine"], "manifest.json").is_file())
        self.assertFalse(decisions.exists())

    def test_a_decisions_file_older_than_the_scan_is_refused_and_removed(self):
        self.switch_on("Delete (duplicate)")
        decisions = self.decide(self.ROWS)
        old = time.time() - 86400
        os.utime(decisions, (old, old))
        code, out = call("run", "--scan", self.scan(), "--decisions", decisions,
                         "--paraos-home", self.home)
        self.assertEqual(code, 3)
        self.assertIn("not written this run", out["refused"])
        self.assertTrue((self.vault / "triage" / "dup.pdf").exists())
        self.assertFalse(decisions.exists())

    def test_the_kill_switch_and_a_shared_vault_refuse_the_whole_run(self):
        self.switch_on("Delete (duplicate)")
        write(self.home, "auto-triage.off", "")
        self.assertEqual(self.run_all(self.ROWS)[0], 3)
        os.remove(self.home / "auto-triage.off")
        write(self.vault, "CLAUDE.md", "# north\n\n## Who writes this vault\n\n| a | b |\n")
        code, out = self.run_all(self.ROWS)
        self.assertEqual(code, 3)
        self.assertIn("roster", out["refused"])
        self.assertTrue((self.vault / "triage" / "dup.pdf").exists())

    def test_restore_is_byte_identical_and_demotes(self):
        self.switch_on("Delete (duplicate)", "Dismiss (noise)")
        _, out = self.run_all(self.ROWS[:2])
        code, back = call("restore", "--vault-name", "north", "--run", out["run"],
                          "--item", "dup.pdf", "--paraos-home", self.home)
        self.assertEqual(code, 0)
        self.assertEqual((self.vault / "triage" / "dup.pdf").read_bytes(), DUP)
        _, status = call("status", "--vault-name", "north", "--paraos-home", self.home)
        self.assertEqual(status["on"], ["Dismiss (noise)"])
        self.assertEqual(status["runs"][0]["acted"],
                         {"Delete (duplicate)": 1, "Dismiss (noise)": 1})
        chosen = [ln["chosen"] for ln in auto_execute.State(str(self.home), "north").decisions()]
        self.assertEqual(chosen, ["Delete (duplicate)", "Dismiss (noise)", "restored"])
        code, _ = call("restore", "--vault-name", "north", "--run", out["run"],
                       "--item", "dup.pdf", "--paraos-home", self.home)
        self.assertEqual(code, 3)

    def test_a_restored_file_whose_bytes_differ_fails(self):
        self.switch_on("Delete (duplicate)")
        _, out = self.run_all(self.ROWS[:1])
        write(out["quarantine"], "files/dup.pdf", "tampered\n")
        code, back = call("restore", "--vault-name", "north", "--run", out["run"],
                          "--paraos-home", self.home)
        self.assertEqual(code, 4)
        self.assertIn("md5", back["failed"][0]["reason"])

    def test_status_names_each_proposed_item_and_record_retires_the_proposal(self):
        _, out = self.run_all(self.ROWS)
        write(self.vault, "triage/invoice.md", "Changed.\n")
        os.remove(self.vault / "triage" / "linked.md")
        _, status = call("status", "--vault-name", "north", "--paraos-home", self.home)
        states = {i["item"]: i["state"] for i in status["proposal"]["items"]}
        self.assertIsNone(status["nothing_new"])
        args = ("status", "--vault-name", "north", "--vault", self.vault,
                "--paraos-home", self.home)
        self.assertFalse(call(*args)[1]["nothing_new"])
        os.remove(self.vault / "triage" / "invoice.md")
        self.assertTrue(call(*args)[1]["nothing_new"])
        write(self.vault, "triage/invoice.md", "Changed.\n")
        self.assertEqual(states, {"dup.pdf": "unchanged", "noise.md": "unchanged",
                                  "invoice.md": "changed", "linked.md": "missing"})
        rows = self.decide([{"item": "dup.pdf", "recommended": "Delete (duplicate)",
                             "chosen": "Delete (duplicate)"}], "chosen.json")
        code, rec = call("record", "--vault-name", "north", "--decisions", rows,
                         "--proposal", status["proposal"]["path"], "--paraos-home", self.home)
        self.assertEqual((code, rec["recorded"]), (0, 1))
        _, status = call("status", "--vault-name", "north", "--paraos-home", self.home)
        self.assertIsNone(status["proposal"])

    def test_status_reads_no_proposal_of_a_vault_whose_name_extends_this_one(self):
        write(self.home, "cache/triage/proposals/north-east-20261018-1200.md", "x\n")
        _, status = call("status", "--vault-name", "north", "--paraos-home", self.home)
        self.assertIsNone(status["proposal"])

    def test_an_offer_needs_fifty_decisions_at_ninety_five_percent(self):
        def ledger(accepted, rejected):
            rows = [{"item": f"i{n}", "recommended": "Dismiss (noise)",
                     "chosen": "Dismiss (noise)" if n < accepted else "Leave in triage"}
                    for n in range(accepted + rejected)]
            call("record", "--vault-name", "north", "--decisions",
                 self.decide(rows, "ledger.json"), "--paraos-home", self.home)
            return call("status", "--vault-name", "north", "--paraos-home", self.home)[1]
        self.assertEqual(ledger(45, 0)["offers"], [])
        self.assertEqual(ledger(5, 0)["offers"], ["Dismiss (noise)"])
        self.switch_on("Dismiss (noise)")
        self.assertEqual(call("status", "--vault-name", "north",
                              "--paraos-home", self.home)[1]["offers"], [])

    def test_only_delete_and_dismiss_can_be_switched_on(self):
        code, out = call("switch", "--vault-name", "north", "--on", "File it",
                         "--paraos-home", self.home)
        self.assertEqual(code, 3)

    def test_a_git_vault_is_left_for_the_operator_to_commit(self):
        def git(*a):
            return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                                   *a], cwd=self.vault, check=True, capture_output=True,
                                  text=True).stdout
        git("init", "-q")
        git("add", "-A")
        git("commit", "-qm", "start")
        self.switch_on("Delete (duplicate)")
        _, out = self.run_all(self.ROWS[:1])
        self.assertNotIn("commit", out)
        self.assertEqual(git("log", "-1", "--format=%s").strip(), "start")
        self.assertEqual(git("status", "--porcelain").strip(), "D triage/dup.pdf")
        call("restore", "--vault-name", "north", "--run", out["run"], "--paraos-home", self.home)
        self.assertEqual(git("status", "--porcelain"), "")

    def test_purge_trashes_only_expired_runs(self):
        self.switch_on("Delete (duplicate)")
        _, out = self.run_all(self.ROWS[:1])
        manifest = Path(out["quarantine"]) / "manifest.json"
        with mock.patch.object(auto_execute, "trash", return_value=True) as trash:
            self.assertEqual(call("purge", "--paraos-home", self.home)[1]["trashed"], [])
            old = time.time() - 40 * 86400
            os.utime(manifest, (old, old))
            self.assertEqual(call("purge", "--paraos-home", self.home)[1]["trashed"],
                             [out["quarantine"]])
            trash.assert_called_once()


if __name__ == "__main__":
    unittest.main()
