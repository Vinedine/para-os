#!/usr/bin/env python3
"""Tests for audit_scan.py. Each pins a rule the script's docstring states: which registry entries are audited, the four revision outcomes, the declaration and
add-on checks, shipped rule files, integration and skill copies read at a committed ref, the
size target, the drive, and the vault named first.

    python3 test_audit_scan.py
    py -3 test_audit_scan.py

Standard library only. Every vault, registry and para-os clone here is synthetic, built in a
temporary folder: one throwaway git clone per test class, three revisions deep, with
`origin/stable` set by `update-ref` so no remote is needed.
"""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "multi-vault" / "para-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import audit_scan  # noqa: E402
from audit_scan import build_report, drive_of, main  # noqa: E402

SCRIPT = SCRIPTS / "audit_scan.py"


# ================================================================== fixture helpers

def write(root, rel, text, newline="\n"):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return path


def fixture_git(root, *args):
    # No auto maintenance: its detached run writes into .git while a test reads or deletes it.
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "core.autocrlf=false", "-c", "core.excludesFile=",
                    "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
                   cwd=root, check=True, capture_output=True)


def template(rev):
    return ("# {{Vault Name}} Vault Conventions\n\n"
            f"<!-- para-os-template: {rev} -->\n"
            "**Type:** {{vault-type}}\n\nGuidance.\n")


def changelog(*revs):
    body = "".join(f"## {r}\n\n**Change {r}.** Detail. Reaction: none.\n\n" for r in revs)
    return "# Changelog\n\n" + body


def logbook(rev, body):
    return (f"#!/usr/bin/env python3\n# para-os-integration: logbook {rev}\n"
            f"VALUE = {body!r}\n")


def skill(version):
    return (f"---\nname: para-notes\ndescription: Fixture skill, version {version}.\n---\n\n"
            f"# Notes\n\nVersion {version} of a fixture skill.\n")


RULE = "---\npaths:\n  - \"projects/**\"\n---\n\n# Filing\n\nA rule.\n"
SALES_RULE = "---\npaths:\n  - \"areas/**\"\n---\n\n# Pipeline\n\nA rule.\n"


def build_clone(root):
    """Three revisions: 2026.09.01 ships the rule, the skill and the integration at v1,
    2026.09.05 only moves the marker, 2026.10.01 moves both copies to v2. The working tree
    then carries an uncommitted 2026.10.02 template, the in-development revision."""
    fixture_git(root, "init", "-q", "-b", "main")
    write(root, "CHANGELOG.md", changelog("2026.09.01"))
    write(root, "base/CLAUDE.md.template", template("2026.09.01"))
    write(root, "base/.claude/rules/filing.md", RULE)
    write(root, "base/.claude/skills/para-notes/SKILL.md", skill(1))
    write(root, "integrations/logbook/logbook.py", logbook("2026.09.01", "v1"))
    write(root, "addons/sales/CLAUDE.md.sections", "## Sales\n\nA section.\n")
    write(root, "addons/sales/.claude/rules/pipeline.md", SALES_RULE)
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "-m", "2026.09.01")

    write(root, "CHANGELOG.md", changelog("2026.09.05", "2026.09.01"))
    write(root, "base/CLAUDE.md.template", template("2026.09.05"))
    fixture_git(root, "commit", "-q", "-am", "2026.09.05")

    write(root, "CHANGELOG.md", changelog("2026.10.01", "2026.09.05", "2026.09.01"))
    write(root, "base/CLAUDE.md.template", template("2026.10.01"))
    write(root, "base/.claude/skills/para-notes/SKILL.md", skill(2))
    write(root, "integrations/logbook/logbook.py", logbook("2026.10.01", "v2"))
    fixture_git(root, "commit", "-q", "-am", "2026.10.01")
    fixture_git(root, "update-ref", "refs/remotes/origin/stable", "HEAD")

    write(root, "base/CLAUDE.md.template", template("2026.10.02"))


def claude_md(marker="2026.10.01", type_line="**Type:** client-vault", extra_header="",
              body_lines=0):
    head = "# Fixture Vault Conventions\n\n"
    if marker:
        head += f"<!-- para-os-template: {marker} -->\n"
    if type_line:
        head += type_line + "\n"
    head += extra_header
    body = "\nA fixture vault.\n\n## Actions\n\nA rule.\n"
    body += "".join(f"Line {i}.\n" for i in range(body_lines))
    return head + body


def build_vault(root, marker="2026.10.01", type_line="**Type:** client-vault",
                extra_header="", rules=("filing.md",), skill_version=2, skill_newline="\n",
                logbook_rev="2026.10.01", logbook_body="v2", body_lines=0):
    root = Path(root)
    for d in ("projects", "areas", "archive", "triage"):
        (root / d).mkdir(parents=True, exist_ok=True)
    write(root, "CLAUDE.md", claude_md(marker, type_line, extra_header, body_lines))
    for name in rules:
        write(root, f".claude/rules/{name}", RULE)
    if skill_version:
        write(root, ".claude/skills/para-notes/SKILL.md", skill(skill_version), skill_newline)
    if logbook_rev:
        write(root, "resources/scripts/logbook.py", logbook(logbook_rev, logbook_body))
    return root


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in Path(root).rglob("*") if p.is_file()}


class CloneCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="audit-scan-"))
        cls.clone = cls.tmp / "para-os"
        cls.clone.mkdir()
        build_clone(cls.clone)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="audit-vaults-", dir=self.tmp))

    @staticmethod
    def entry_at(work, name, kind="client-vault", **extra):
        return dict({"name": name, "path": str(work / name), "kind": kind,
                     "purpose": "A fixture.", "active": True}, **extra)

    def entry(self, name, kind="client-vault", **extra):
        return self.entry_at(self.work, name, kind, **extra)

    @classmethod
    def audit_at(cls, work, entries, ref=None):
        return build_report(work / "vaults.json", entries, cls.clone, ref, "explicit",
                            cls.tmp / "no-home" / "para-os")

    def run_audit(self, entries, ref=None):
        return self.audit_at(self.work, entries, ref)

    def vault_row(self, report, name):
        return next(v for v in report["vaults"] if v["name"] == name)

    def findings(self, row, check):
        return [f for f in row["findings"] if f["check"] == check]


# ======================================================== the fixture fleet (Done when)

class FleetCase(CloneCase):
    """Three registered vaults and one retired entry: aligned, behind with a stale
    integration copy, unreachable, retired. Audited once for the class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        work = cls.fleet = cls.tmp / "fleet"
        build_vault(work / "aligned")
        build_vault(work / "behind", marker="2026.09.01", skill_version=1,
                    logbook_rev="2026.09.01", logbook_body="v1")
        build_vault(work / "old")
        entries = [cls.entry_at(work, "aligned"), cls.entry_at(work, "behind"),
                   cls.entry_at(work, "unreachable"), cls.entry_at(work, "old", retired=True)]
        cls.before = {n: tree_bytes(work / n) for n in ("aligned", "behind", "old")}
        cls.report, cls.code = cls.audit_at(work, entries)

    def test_answers(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.report["master"]["revision"], "2026.10.01")
        self.assertEqual([v["name"] for v in self.report["vaults"]], ["aligned", "behind"])

    def test_the_aligned_vault_has_no_finding(self):
        row = self.vault_row(self.report, "aligned")
        self.assertEqual(row["revision"]["verdict"], "equal")
        self.assertEqual(row["findings"], [])
        self.assertEqual(row["cells"]["revision"], "aligned")

    def test_the_behind_vault_lists_the_intervening_entries(self):
        row = self.vault_row(self.report, "behind")
        self.assertEqual(row["revision"]["verdict"], "behind")
        self.assertEqual(row["revision"]["entries"], ["2026.09.05", "2026.10.01"])
        self.assertEqual(row["revision"]["behind"], 2)
        self.assertEqual(row["cells"]["revision"], "behind 2")
        self.assertIn("/para-upgrade", self.findings(row, "revision")[0]["fix"])

    def test_the_stale_integration_copy_is_behind_its_master(self):
        row = self.vault_row(self.report, "behind")
        found = self.findings(row, "integrations")
        self.assertEqual(len(found), 1)
        self.assertIn("resources/scripts/logbook.py", found[0]["detail"])
        self.assertIn("behind", found[0]["detail"])
        self.assertIn("2026.10.01", found[0]["detail"])
        self.assertEqual(found[0]["route"], "upgrade")

    def test_the_stale_skill_copy_is_behind_its_master(self):
        row = self.vault_row(self.report, "behind")
        found = self.findings(row, "skills")
        self.assertEqual(len(found), 1)
        self.assertIn("para-notes", found[0]["detail"])

    def test_unreachable_and_retired_are_both_stated(self):
        excluded = {e["name"]: e for e in self.report["excluded"]}
        self.assertEqual(excluded["unreachable"]["status"], "UNREACHABLE")
        self.assertEqual(excluded["old"]["status"], "RETIRED (excluded)")

    def test_the_vault_furthest_behind_goes_first(self):
        self.assertEqual(self.report["upgrade_first"]["name"], "behind")
        self.assertEqual(self.report["upgrade_first"]["revisions_behind"], 2)

    def test_the_working_tree_revision_is_reported_once_and_is_never_the_bar(self):
        self.assertEqual(self.report["master"]["in_development"], "2026.10.02")
        row = self.vault_row(self.report, "aligned")
        self.assertEqual(row["revision"]["master"], "2026.10.01")

    def test_nothing_in_any_vault_is_written(self):
        for name, before in self.before.items():
            self.assertEqual(tree_bytes(self.fleet / name), before, name)


# ============================================================== the revision outcomes

class RevisionCase(CloneCase):
    def one(self, **vault):
        build_vault(self.work / "v", **vault)
        report, code = self.run_audit([self.entry("v")])
        self.assertEqual(code, 0)
        return self.vault_row(report, "v")

    def test_equal(self):
        row = self.one()
        self.assertEqual(row["revision"]["verdict"], "equal")
        self.assertEqual(self.findings(row, "revision"), [])

    def test_behind(self):
        row = self.one(marker="2026.09.05")
        self.assertEqual(row["revision"]["entries"], ["2026.10.01"])
        self.assertEqual(row["cells"]["revision"], "behind 1")

    def test_ahead_judges_nothing_against_the_older_master(self):
        row = self.one(marker="2026.10.02", rules=(), skill_version=1,
                       logbook_rev="2026.09.01", logbook_body="v1",
                       extra_header="**Modules:** nonesuch\n")
        self.assertEqual(row["revision"]["verdict"], "ahead")
        self.assertEqual(row["cells"]["revision"], "ahead 2026.10.02")
        for check in ("rules", "integrations", "skills"):
            self.assertEqual(row["cells"][check], "not judged", check)
            self.assertEqual(self.findings(row, check), [], check)
        self.assertFalse(any("nonesuch" in f["detail"] for f in row["findings"]))
        self.assertIn("in development", self.findings(row, "revision")[0]["detail"])

    def test_unstamped(self):
        row = self.one(marker=None)
        self.assertEqual(row["revision"]["verdict"], "no-marker")
        self.assertEqual(row["cells"]["revision"], "UNSTAMPED")
        self.assertEqual(row["revision"]["behind"], 3)
        self.assertIn("/para-upgrade", self.findings(row, "revision")[0]["fix"])

    def test_a_malformed_marker_is_unstamped_and_named(self):
        build_vault(self.work / "v")
        write(self.work / "v", "CLAUDE.md",
              claude_md(marker=None).replace("**Type:**",
                                             "<!-- para-os-template: 2026.10.1 -->\n**Type:**"))
        report, _ = self.run_audit([self.entry("v")])
        row = self.vault_row(report, "v")
        self.assertEqual(row["revision"]["verdict"], "no-marker")
        self.assertTrue(any("2026.10.1" in f["detail"] for f in self.findings(row, "declarations")))

    def test_prose_naming_the_marker_is_not_a_marker(self):
        build_vault(self.work / "v")
        write(self.work / "v", "CLAUDE.md",
              claude_md() + "\nThe `<!-- para-os-template: YYYY.MM.NN -->` comment is read.\n")
        report, _ = self.run_audit([self.entry("v")])
        self.assertEqual(self.findings(self.vault_row(report, "v"), "declarations"), [])


# ================================================================ type and declarations

class DeclarationCase(CloneCase):
    def row(self, kind="client-vault", **vault):
        build_vault(self.work / "v", **vault)
        report, _ = self.run_audit([self.entry("v", kind=kind)])
        return self.vault_row(report, "v")

    def test_a_type_kind_mismatch_names_both_and_decides_neither(self):
        row = self.row(kind="personal-vault")
        found = self.findings(row, "type")
        self.assertEqual(len(found), 1)
        self.assertIn("client-vault", found[0]["detail"])
        self.assertIn("personal-vault", found[0]["detail"])
        self.assertEqual(found[0]["route"], "operator")
        self.assertEqual(row["cells"]["type"], "mismatch")

    def test_type_and_kind_compare_as_one_name(self):
        row = self.row(kind="Client Vault")
        self.assertEqual(self.findings(row, "type"), [])

    def test_an_entry_with_no_kind_is_a_finding(self):
        build_vault(self.work / "v")
        entry = self.entry("v")
        del entry["kind"]
        report, _ = self.run_audit([entry])
        row = self.vault_row(report, "v")
        self.assertEqual(row["cells"]["type"], "no kind")

    def test_an_unknown_add_on_name_is_a_finding_and_a_known_one_is_not(self):
        row = self.row(extra_header="**Modules:** sales, nonesuch\n",
                       rules=("filing.md", "pipeline.md"))
        found = self.findings(row, "declarations")
        self.assertEqual(len(found), 1)
        self.assertIn("nonesuch", found[0]["detail"])
        self.assertIn("addons/", found[0]["detail"])

    def test_a_declared_add_on_s_rule_file_is_expected(self):
        row = self.row(extra_header="**Modules:** sales\n")
        found = self.findings(row, "rules")
        self.assertEqual(len(found), 1)
        self.assertIn(".claude/rules/pipeline.md", found[0]["detail"])

    def test_a_missing_type_line(self):
        row = self.row(type_line=None)
        self.assertTrue(any("**Type:**" in f["detail"] for f in self.findings(row, "declarations")))
        self.assertEqual(row["cells"]["type"], "-")

    def test_the_template_placeholder_is_not_a_type(self):
        row = self.row(type_line="**Type:** {{vault-type}}")
        self.assertTrue(any("placeholder" in f["detail"]
                            for f in self.findings(row, "declarations")))

    def test_a_line_off_the_literal_shape(self):
        row = self.row(type_line="**Type**: client-vault")
        self.assertTrue(any("**Type**: client-vault" in f["detail"]
                            for f in self.findings(row, "declarations")))

    def test_a_declaration_line_away_from_the_title_is_read_by_nothing(self):
        build_vault(self.work / "v")
        text = claude_md() + "\n**Modules:** sales\n"
        write(self.work / "v", "CLAUDE.md", text)
        report, _ = self.run_audit([self.entry("v")])
        row = self.vault_row(report, "v")
        self.assertTrue(any("not under the title" in f["detail"]
                            for f in self.findings(row, "declarations")))

    def test_two_flavors_on_one_line(self):
        row = self.row(extra_header="**Flavor:** sales, other\n")
        self.assertTrue(any("one flavor" in f["fix"] for f in self.findings(row, "declarations")))

    def test_a_delivery_line_is_reported_unknown(self):
        row = self.row(extra_header="**Delivery:** readonly-ipad\n")
        found = self.findings(row, "declarations")
        self.assertEqual(len(found), 1)
        self.assertIn("**Delivery:**", found[0]["detail"])


# =============================================================== rules, skills, size

class CopiesCase(CloneCase):
    def test_a_crlf_skill_copy_reads_identical(self):
        build_vault(self.work / "v", skill_newline="\r\n")
        self.assertIn(b"\r\n", (self.work / "v/.claude/skills/para-notes/SKILL.md").read_bytes())
        report, _ = self.run_audit([self.entry("v")])
        row = self.vault_row(report, "v")
        self.assertEqual(self.findings(row, "skills"), [])
        self.assertEqual(row["cells"]["skills"], "ok")

    def test_a_vault_s_own_skill_is_not_a_copy(self):
        build_vault(self.work / "v")
        write(self.work / "v", ".claude/skills/house-style/SKILL.md", "---\nname: house-style\n---\n")
        report, _ = self.run_audit([self.entry("v")])
        self.assertEqual(self.findings(self.vault_row(report, "v"), "skills"), [])

    def test_a_para_copy_nothing_ships_is_a_finding(self):
        build_vault(self.work / "v")
        write(self.work / "v", ".claude/skills/para-gone/SKILL.md", "---\nname: para-gone\n---\n")
        report, _ = self.run_audit([self.entry("v")])
        found = self.findings(self.vault_row(report, "v"), "skills")
        self.assertEqual(len(found), 1)
        self.assertIn("para-gone", found[0]["detail"])

    def test_no_copies_reads_none(self):
        build_vault(self.work / "v", skill_version=None, logbook_rev=None)
        report, _ = self.run_audit([self.entry("v")])
        row = self.vault_row(report, "v")
        self.assertEqual(row["cells"]["skills"], "none")
        self.assertEqual(row["cells"]["integrations"], "none")

    def test_a_missing_shipped_rule_file(self):
        build_vault(self.work / "v", rules=())
        report, _ = self.run_audit([self.entry("v")])
        row = self.vault_row(report, "v")
        self.assertEqual(row["cells"]["rules"], "1 missing")
        self.assertIn(".claude/rules/filing.md", self.findings(row, "rules")[0]["detail"])

    def test_an_integration_naming_no_master(self):
        build_vault(self.work / "v")
        write(self.work / "v", "resources/scripts/other.py",
              "# para-os-integration: nonesuch 2026.10.01\n")
        report, _ = self.run_audit([self.entry("v")])
        found = self.findings(self.vault_row(report, "v"), "integrations")
        self.assertEqual(len(found), 1)
        self.assertIn("nonesuch", found[0]["detail"])

    def test_size_over_the_target_is_an_adherence_finding(self):
        build_vault(self.work / "v", body_lines=200)
        report, _ = self.run_audit([self.entry("v")])
        row = self.vault_row(report, "v")
        found = self.findings(row, "size")
        self.assertEqual(len(found), 1)
        self.assertIn(".claude/rules/", found[0]["fix"])
        self.assertNotIn("token", found[0]["detail"] + found[0]["fix"])
        self.assertTrue(row["cells"]["size"].endswith("(over 200)"))

    def test_size_at_the_target_is_not(self):
        build_vault(self.work / "v")
        report, _ = self.run_audit([self.entry("v")])
        row = self.vault_row(report, "v")
        self.assertEqual(self.findings(row, "size"), [])


class VerdictWordingCase(unittest.TestCase):
    """upgrade_scan computes every verdict and its suite pins them; these pin only what the
    audit says about each and where it routes it."""

    def integration(self, verdict, **extra):
        row = dict({"file": "resources/scripts/x.py", "name": "x", "revision": "2026.10.01",
                    "verdict": verdict}, **extra)
        return audit_scan.integration_findings([row], None, "origin/stable")[0]

    def test_integration_verdicts(self):
        self.assertEqual(self.integration("marker-matches-content-differs")["route"], "upgrade")
        self.assertIn("local changes", self.integration("both")["detail"])
        self.assertEqual(self.integration("ahead")["route"], "operator")
        self.assertIn("a.py, b.py", self.integration("ambiguous-rename",
                                                     candidates=["a.py", "b.py"])["detail"])

    def skill(self, verdict, **extra):
        row = dict({"name": "para-x", "verdict": verdict}, **extra)
        return audit_scan.skill_findings([row], "origin/stable")[0]

    def test_skill_verdicts(self):
        self.assertIn("by 2 revisions, missing a.md",
                      self.skill("behind", revisions_behind=2, missing=["a.md"])["detail"])
        self.assertEqual(self.skill("ahead")["route"], "operator")
        self.assertIn("local changes", self.skill("both")["detail"])
        undeclared = audit_scan.skill_findings([{"name": "para-y", "undeclared_addon": "extra"}],
                                               "origin/stable")[0]
        self.assertIn("`extra`", undeclared["detail"])
        self.assertEqual(undeclared["route"], "operator")

    def test_a_folder_with_no_claude_md_has_no_size(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(audit_scan.size_check(Path(empty)), ("-", []))


class TopicFileCase(CloneCase):
    def fleet(self, sibling_rules, sibling_kind="client-vault"):
        build_vault(self.work / "a", rules=("filing.md", "house.md"))
        build_vault(self.work / "b", rules=sibling_rules)
        report, _ = self.run_audit([self.entry("a"), self.entry("b", kind=sibling_kind)])
        return self.vault_row(report, "a")

    def test_a_topic_file_no_sibling_carries_is_an_observation(self):
        row = self.fleet(("filing.md",))
        self.assertEqual([o["check"] for o in row["observations"]], ["rules"])
        self.assertIn("house.md", row["observations"][0]["detail"])
        self.assertEqual(self.findings(row, "rules"), [])

    def test_a_topic_file_a_sibling_carries_is_not(self):
        self.assertEqual(self.fleet(("filing.md", "house.md"))["observations"], [])

    def test_with_no_sibling_of_the_same_kind_there_is_nothing_to_compare(self):
        self.assertEqual(self.fleet(("filing.md",), sibling_kind="other")["observations"], [])

    def test_a_voice_profile_is_one_person_s_and_never_a_topic(self):
        build_vault(self.work / "a", rules=("filing.md", "voice-ada-peeters.md"))
        build_vault(self.work / "b", rules=("filing.md",))
        report, _ = self.run_audit([self.entry("a"), self.entry("b")])
        self.assertEqual(self.vault_row(report, "a")["observations"], [])


# ======================================================================= the registry

class RegistryCase(CloneCase):
    def test_an_inactive_vault_is_still_audited(self):
        build_vault(self.work / "quiet")
        report, _ = self.run_audit([self.entry("quiet", active=False)])
        self.assertEqual(self.vault_row(report, "quiet")["active"], False)
        self.assertEqual(report["excluded"], [])

    def test_a_folder_with_no_claude_md_is_unreachable(self):
        (self.work / "bare").mkdir()
        report, _ = self.run_audit([self.entry("bare")])
        self.assertEqual(report["excluded"][0]["status"], "UNREACHABLE")
        self.assertIn("CLAUDE.md", report["excluded"][0]["reason"])

    def test_an_entry_missing_its_path_is_stated_not_dropped(self):
        report, _ = self.run_audit([{"name": "nameless-path"}, "not an entry",
                                    {"name": "numbered", "path": 7}])
        self.assertEqual([e["status"] for e in report["excluded"]], ["INVALID"] * 3)

    def test_no_registry_is_exit_3(self):
        report, code = self.run_audit(None)
        self.assertEqual(code, 3)
        self.assertIn("vaults.json", report["error"])

    def test_an_empty_registry_is_exit_3(self):
        _, code = self.run_audit([])
        self.assertEqual(code, 3)

    def test_the_vault_with_most_findings_goes_first_when_none_is_behind(self):
        build_vault(self.work / "one", rules=())
        build_vault(self.work / "two", rules=(), skill_version=1)
        report, _ = self.run_audit([self.entry("one"), self.entry("two")])
        self.assertEqual(report["upgrade_first"]["name"], "two")

    def test_an_operator_only_finding_never_names_a_vault_to_upgrade(self):
        build_vault(self.work / "v")
        report, _ = self.run_audit([self.entry("v", kind="other")])
        self.assertIsNone(report["upgrade_first"])


class DriveCase(CloneCase):
    def test_drive_of(self):
        self.assertEqual(drive_of("K:/Team vaults/a"), "K:")
        self.assertEqual(drive_of("k:\\Team vaults\\a"), "K:")
        self.assertEqual(drive_of("//server/share/a"), "\\\\server\\share")
        self.assertEqual(drive_of("/Volumes/Shared/a"), "/Volumes/Shared")
        self.assertEqual(drive_of("/mnt/share/a"), "/mnt/share")
        self.assertEqual(drive_of("/media/me/disk/a"), "/media/me/disk")
        self.assertEqual(drive_of("/run/media/me/disk/a"), "/run/media/me/disk")
        self.assertEqual(drive_of("/home/me/a"), "/")

    def test_every_vault_on_one_drive_unreachable_is_the_drive(self):
        build_vault(self.work / "here")
        entries = [self.entry("here"),
                   dict(self.entry("x"), path="Q:/gone/x"),
                   dict(self.entry("y"), path="Q:/gone/y")]
        report, _ = self.run_audit(entries)
        self.assertEqual(report["drives"], [{"drive": "Q:", "vaults": ["x", "y"]}])

    def test_one_reachable_vault_on_the_drive_means_it_is_not_the_drive(self):
        build_vault(self.work / "here")
        entries = [self.entry("here"), self.entry("gone-1"), self.entry("gone-2")]
        report, _ = self.run_audit(entries)
        self.assertEqual(report["drives"], [])


# =========================================================================== the clone

class CloneErrorCase(CloneCase):
    def test_no_clone_found_is_exit_6(self):
        report, code = build_report(self.work / "vaults.json", [self.entry("v")], None, None,
                                    None, self.tmp / "no-home" / "para-os")
        self.assertEqual(code, 6)
        self.assertIn("no para-os clone", report["clone"]["error"])

    def test_a_ref_that_does_not_resolve_is_exit_4(self):
        _, code = self.run_audit([self.entry("v")], ref="no-such-ref")
        self.assertEqual(code, 4)

    def test_a_named_ref_is_read(self):
        build_vault(self.work / "v", marker="2026.09.05")
        report, code = self.run_audit([self.entry("v")], ref="main~1")
        self.assertEqual(code, 0)
        self.assertEqual(self.vault_row(report, "v")["revision"]["verdict"], "equal")

    def test_a_clone_without_origin_stable_is_exit_5(self):
        bare = self.tmp / "no-stable"
        bare.mkdir(exist_ok=True)
        fixture_git(bare, "init", "-q", "-b", "main")
        write(bare, "CHANGELOG.md", changelog("2026.10.01"))
        write(bare, "base/CLAUDE.md.template", template("2026.10.01"))
        fixture_git(bare, "add", "-A")
        fixture_git(bare, "commit", "-q", "-m", "one")
        report, code = build_report(self.work / "vaults.json", [self.entry("v")], bare, None,
                                    "explicit", self.tmp / "no-home" / "para-os")
        self.assertEqual(code, 5)
        self.assertTrue(report["clone"]["stable_missing"])

    def test_a_master_with_no_marker_is_exit_4(self):
        plain = self.tmp / "unmarked"
        plain.mkdir(exist_ok=True)
        fixture_git(plain, "init", "-q", "-b", "main")
        write(plain, "CHANGELOG.md", changelog("2026.10.01"))
        write(plain, "base/CLAUDE.md.template", "# Template\n")
        fixture_git(plain, "add", "-A")
        fixture_git(plain, "commit", "-q", "-m", "one")
        report, code = build_report(self.work / "vaults.json", [self.entry("v")], plain, "main",
                                    "explicit", self.tmp / "no-home" / "para-os")
        self.assertEqual(code, 4)
        self.assertIn("marker", report["clone"]["error"])


# ============================================================================ the CLI

class CliCase(CloneCase):
    def test_main_prints_one_json_document(self):
        home = self.work / "home"
        build_vault(self.work / "v")
        write(home, "vaults.json", json.dumps([self.entry("v")]))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--paraos-home", str(home), "--clone", str(self.clone)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["vaults"][0]["name"], "v")

    def test_main_with_no_registry_says_so_on_stderr(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--paraos-home", str(self.work / "empty"), "--clone", str(self.clone)])
        self.assertEqual(code, 3)
        self.assertIn("audit_scan:", err.getvalue())

    def test_without_the_libraries_beside_it_the_scan_exits_2(self):
        alone = self.work / "skills" / "para-audit" / "scripts"
        alone.mkdir(parents=True)
        shutil.copy(SCRIPT, alone / SCRIPT.name)
        done = subprocess.run([sys.executable, str(alone / SCRIPT.name)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("Install them", done.stderr)
        self.assertNotIn("by hand", done.stderr)

    def test_libraries_that_do_not_import_exit_2(self):
        skills = self.work / "skills"
        write(skills, "para-shared/scripts/paraos_vault.py", "")
        write(skills, "para-upgrade/scripts/upgrade_scan.py", "")
        (skills / "para-audit" / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, skills / "para-audit" / "scripts" / SCRIPT.name)
        done = subprocess.run([sys.executable, str(skills / "para-audit" / "scripts" / SCRIPT.name)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("install para-shared", done.stderr)
        self.assertNotIn("by hand", done.stderr)

    def test_in_a_checkout_the_libraries_resolve_from_base(self):
        self.assertEqual(audit_scan.SKILLS_ROOT.parts[-3:], ("base", ".claude", "skills"))

    def test_installed_beside_them_the_libraries_resolve_from_there(self):
        skills = self.work / "skills"
        for lib in ("para-shared", "para-upgrade"):
            shutil.copytree(audit_scan.SKILLS_ROOT / lib / "scripts", skills / lib / "scripts")
        (skills / "para-audit" / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, skills / "para-audit" / "scripts" / SCRIPT.name)
        done = subprocess.run([sys.executable, str(skills / "para-audit" / "scripts" / SCRIPT.name),
                               "--paraos-home", str(self.work / "empty"),
                               "--clone", str(self.clone)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 3, done.stderr)


if __name__ == "__main__":
    unittest.main()
