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
                {"item": "dup.pdf", "action": "Add action"},
                {"item": "invoice.md", "action": "Dismiss (noise)"},
                {"item": "dup.pdf", "action": "Delete (duplicate)"}]
        code, out = call("run", "--scan", saved, "--decisions", self.decide(rows),
                         "--cap", 1, "--paraos-home", self.home)
        reasons = [r["reason"] for r in out["refused"]]
        self.assertEqual(reasons, ["not a loose file of the scan's triage/",
                                   "changed since the scan", "Add action is never unattended",
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

    def test_a_decision_with_no_recommendation_counts_toward_no_offer(self):
        rows = [{"item": f"i{n}", "recommended": "Dismiss (noise)", "chosen": "Dismiss (noise)"}
                for n in range(50)]
        rows.append({"item": "odd", "recommended": None, "chosen": "Dismiss (noise)"})
        call("record", "--vault-name", "north", "--decisions", self.decide(rows),
             "--paraos-home", self.home)
        self.assertEqual(call("status", "--vault-name", "north", "--paraos-home", self.home)
                         [1]["offers"], ["Dismiss (noise)"])

    def note(self, name, sender):
        write(self.vault, f"triage/{name}", f"# Club evening\n\n- **Source:** connector "
              f"(Box@Example.org)\n- **From:** Club <{sender}>\n- **Link:** https://m.example/"
              f"{name}\n\nCome along.\n")

    def record(self, rows, *extra):
        return call("record", "--vault-name", "north", "--decisions",
                    self.decide(rows, "chosen.json"), *extra, "--paraos-home", self.home)[1]

    def noise(self, item, sender, mailbox="box@example.org", chosen="Dismiss (noise)"):
        return {"item": item, "recommended": chosen, "chosen": chosen, "from": sender,
                "mailbox": mailbox}

    def test_unattended_dismissals_of_one_domain_are_offered_as_a_domain_until_the_next_record(self):
        self.note("a.md", "Campaigns@clubapp.example")
        self.note("b.md", "noreply@clubapp.example")
        self.switch_on("Dismiss (noise)")
        _, out = self.run_all([{"item": "a.md", "action": "Dismiss (noise)"},
                               {"item": "b.md", "action": "Dismiss (noise)"}])
        manifest = json.loads((Path(out["quarantine"]) / "manifest.json").read_text())
        self.assertEqual(manifest["items"][0]["from"], "campaigns@clubapp.example")
        _, status = call("status", "--vault-name", "north", "--paraos-home", self.home)
        [offer] = status["exclusion_offers"]
        self.assertEqual((offer["mailbox"], offer["entry"], offer["items"]),
                         ("box@example.org", {"domain": "clubapp.example"}, ["a.md", "b.md"]))
        self.assertEqual(offer["senders"], ["campaigns@clubapp.example", "noreply@clubapp.example"])
        self.record([{"item": "x", "recommended": "File it", "chosen": "File it"}])
        self.assertEqual(call("status", "--vault-name", "north", "--paraos-home", self.home)
                         [1]["exclusion_offers"], [])

    def test_a_second_noise_dismissal_of_one_address_offers_it_until_the_file_holds_it(self):
        self.assertEqual(self.record([self.noise("a", "x@club.example")])["exclusion_offers"], [])
        self.assertEqual(self.record([self.noise("b", "x@club.example", chosen="Note to triage"),
                                      self.noise("c", "x@club.example", "other@example.org")])
                         ["exclusion_offers"], [])
        [offer] = self.record([self.noise("d", "X@Club.example")])["exclusion_offers"]
        self.assertEqual((offer["entry"], offer["items"]), ({"from": "x@club.example"}, ["a", "d"]))
        code, added = call("add-exclusion", "--mailbox", "box@example.org", "--from",
                           "x@club.example", "--reason", "Club mail. Accepted risk: none",
                           "--paraos-home", self.home)
        self.assertEqual((code, added["backup"]), (0, None))
        self.assertEqual(self.record([self.noise("e", "x@club.example")])["exclusion_offers"], [])

    def test_record_takes_a_staged_notes_sender_from_the_scan(self):
        self.note("a.md", "news@club.example")
        rows = [{"item": "a.md", "recommended": "Dismiss (noise)", "chosen": "Dismiss (noise)"}]
        self.record(rows, "--scan", self.scan())
        line = auto_execute.State(self.home, "north").decisions()[-1]
        self.assertEqual((line["from"], line["mailbox"]), ("news@club.example", "box@example.org"))

    def test_a_group_domain_on_every_mailbox_holds_its_subdomains(self):
        write(self.home, "triage-exclusions.json", json.dumps(
            {"*": [{"group": "Clubs", "any": [{"domain": "club.example"}], "reason": "r"}]}))
        rows = [self.noise("a", "x@mail.club.example"), self.noise("b", "x@mail.club.example")]
        self.assertEqual(self.record(rows)["exclusion_offers"], [])

    def test_add_exclusion_backs_the_file_up_first_and_refuses_one_that_does_not_parse(self):
        path = self.home / "triage-exclusions.json"
        args = ("add-exclusion", "--mailbox", "Box@Example.org", "--reason", "r",
                "--paraos-home", self.home)
        call(*args, "--domain", "one.example")
        before = path.read_bytes()
        code, out = call(*args, "--domain", "two.example")
        self.assertEqual(code, 0)
        self.assertEqual(Path(out["backup"]).name, f"triage-exclusions.json.bak-"
                         f"{auto_execute.now_stamp()[:8]}")
        self.assertEqual(Path(out["backup"]).read_bytes(), before)
        _, again = call(*args, "--domain", "three.example")
        self.assertEqual(Path(out["backup"]).read_bytes(), before)
        self.assertRegex(Path(again["backup"]).name, r"\.bak-\d{8}-\d{6}$")
        entries = json.loads(path.read_text(encoding="utf-8"))["box@example.org"]
        self.assertEqual([e["domain"] for e in entries], ["one.example", "two.example",
                                                         "three.example"])
        self.assertEqual(set(entries[0]), {"domain", "reason", "added"})
        path.write_text("{ broken", encoding="utf-8")
        self.assertEqual(call(*args, "--domain", "four.example")[0], 3)
        self.assertEqual(path.read_text(encoding="utf-8"), "{ broken")

    def test_only_delete_dismiss_and_file_it_can_be_switched_on(self):
        code, out = call("switch", "--vault-name", "north", "--on", "Add action",
                         "--paraos-home", self.home)
        self.assertEqual(code, 3)
        self.switch_on("File it")

    def git(self, *a):
        return subprocess.run(["git", *a], cwd=self.vault, check=True, capture_output=True,
                              text=True).stdout

    def init_git(self):
        self.git("init", "-q")
        self.git("config", "user.name", "t")
        self.git("config", "user.email", "t@example.invalid")
        self.git("add", "-A")
        self.git("commit", "-qm", "start")

    def test_a_git_vault_is_left_for_the_operator_to_commit(self):
        self.init_git()
        self.switch_on("Delete (duplicate)")
        _, out = self.run_all(self.ROWS[:1])
        self.assertNotIn("commit", out)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "start")
        self.assertEqual(self.git("status", "--porcelain").strip(), "D triage/dup.pdf")
        call("restore", "--vault-name", "north", "--run", out["run"], "--paraos-home", self.home)
        self.assertEqual(self.git("status", "--porcelain"), "")

    FILE = {"item": "linked.md", "action": "File it", "entity": "projects/site",
            "name": "brief.md"}

    def test_file_it_files_into_an_entitys_sources_repoints_its_link_and_commits_those_paths(self):
        self.init_git()
        write(self.vault, "triage/invoice.md", "Paid, the operator notes.\n")
        self.switch_on("File it")
        code, out = self.run_all([self.FILE])
        self.assertEqual((code, out["acted"]), (0, [{"item": "linked.md", "action": "File it"}]))
        self.assertTrue((self.vault / "projects/site/sources/brief.md").is_file())
        self.assertFalse((self.vault / "triage/linked.md").exists())
        self.assertEqual((self.vault / "projects/site/README.md").read_text(),
                         "See [it](sources/brief.md).\n")
        self.assertEqual(self.git("log", "-1", "--format=%h").strip(), out["commit"])
        self.assertEqual(sorted(self.git("show", "--name-only", "--no-renames", "--format=",
                                         "HEAD").split()),
                         ["projects/site/README.md", "projects/site/sources/brief.md",
                          "triage/linked.md"])
        self.assertEqual(self.git("status", "--porcelain").strip(), "M triage/invoice.md")

    def test_file_it_refuses_a_missing_entity_a_bad_name_a_taken_target_and_a_changed_item(self):
        self.init_git()
        for n in "abcdefg":
            write(self.vault, f"triage/{n}.md", f"Item {n}.\n")
        write(self.vault, "projects/site/sources/f.md", "Already filed.\n")
        self.switch_on("File it")
        saved = self.scan()
        write(self.vault, "triage/g.md", "Edited after the scan.\n")
        names = {"a": "a.md", "b": "sub/b.md", "c": "../c.md", "d": ".d.md", "e": "e.txt",
                 "f": "f.md", "g": "g.md"}
        rows = [dict(self.FILE, item=f"{n}.md", name=name) for n, name in names.items()]
        rows[0]["entity"] = "projects/nope"
        code, out = call("run", "--scan", saved, "--decisions", self.decide(rows),
                         "--paraos-home", self.home)
        bad_name = "is not a bare file name with the item's extension"
        self.assertEqual([r["reason"] for r in out["refused"]],
                         ["projects/nope is no project, area or idea of this vault",
                          f"sub/b.md {bad_name}", f"../c.md {bad_name}", f".d.md {bad_name}",
                          f"e.txt {bad_name}", "projects/site/sources/f.md exists",
                          "changed since the scan"])
        self.assertEqual((out["acted"], "commit" in out), ([], False))
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "start")
        self.assertTrue(all((self.vault / f"triage/{n}.md").is_file() for n in names))

    def test_file_it_not_switched_on_outside_git_or_in_a_repo_above_the_vault_is_refused(self):
        self.switch_on("Dismiss (noise)")
        self.assertEqual(self.run_all([self.FILE])[1]["refused"][0]["reason"],
                         "File it is not switched on for this vault")
        self.switch_on("File it")
        outside = "File it runs only in a vault whose root is a git working tree"
        self.assertEqual(self.run_all([self.FILE])[1]["refused"][0]["reason"], outside)
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, check=True)
        self.assertEqual(self.run_all([self.FILE])[1]["refused"][0]["reason"], outside)
        self.assertTrue((self.vault / "triage/linked.md").is_file())

    def test_a_name_git_would_read_as_a_pattern_commits_that_file_alone(self):
        write(self.vault, "projects/site/sources/note 1.md", "Filed earlier.\n")
        self.init_git()
        write(self.vault, "projects/site/sources/note 1.md", "The operator's edit.\n")
        self.switch_on("File it")
        _, out = self.run_all([dict(self.FILE, item="noise.md", name="note [1].md")])
        self.assertIsNotNone(out["commit"])
        self.assertEqual(self.git("-c", "core.quotePath=false", "status", "--porcelain").strip(),
                         'M "projects/site/sources/note 1.md"')

    def test_restoring_a_filed_item_moves_it_back_demotes_file_it_and_commits(self):
        self.init_git()
        self.switch_on("File it", "Dismiss (noise)")
        _, out = self.run_all([self.FILE])
        code, back = call("restore", "--vault-name", "north", "--run", out["run"],
                          "--paraos-home", self.home)
        self.assertEqual((code, back["failed"]), (0, []))
        self.assertEqual((self.vault / "triage/linked.md").read_text(), "Linked from a project.\n")
        self.assertEqual((self.vault / "projects/site/README.md").read_text(),
                         "See [it](../../triage/linked.md).\n")
        self.assertEqual(self.git("log", "-1", "--format=%h %s").strip(),
                         f"{back['commit']} Restore unattended triage {out['run']}")
        self.assertEqual(self.git("status", "--porcelain"), "")
        _, status = call("status", "--vault-name", "north", "--paraos-home", self.home)
        self.assertEqual(status["on"], ["Dismiss (noise)"])

    def test_a_filed_item_gone_from_its_entity_is_not_restored(self):
        self.init_git()
        self.switch_on("File it")
        _, out = self.run_all([self.FILE])
        os.remove(self.vault / "projects/site/sources/brief.md")
        code, back = call("restore", "--vault-name", "north", "--run", out["run"],
                          "--paraos-home", self.home)
        self.assertEqual(code, 4)
        self.assertIn("nothing to move", back["failed"][0]["reason"])
        self.assertNotIn("commit", back)

    def test_a_commit_git_refuses_leaves_the_filed_item_moved_and_says_so(self):
        self.init_git()
        self.switch_on("File it")
        real = auto_execute.git
        with mock.patch.object(auto_execute, "git",
                               lambda root, a: None if "commit" in a else real(root, a)):
            code, out = self.run_all([self.FILE])
        self.assertEqual((code, out["commit"]), (0, None))
        self.assertTrue((self.vault / "projects/site/sources/brief.md").is_file())

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
