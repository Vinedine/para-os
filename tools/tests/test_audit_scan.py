#!/usr/bin/env python3
"""Tests for audit_scan.py. Each pins a rule the script's docstring states: which registry
entries are read, the revision outcomes, the declaration and add-on checks, shipped rule files
and the rule-file contract, and integration and skill copies read at a committed ref.

    python3 test_audit_scan.py
    py -3 test_audit_scan.py

Standard library only. Every vault and para-os clone here is synthetic, built in a temporary
folder: one throwaway git clone per test class, three revisions deep, with `origin/stable` set
by `update-ref` so no remote is needed.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "multi-vault" / "para-command-center" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import audit_scan  # noqa: E402
from paraos_clone import master_template  # noqa: E402
from upgrade_scan import open_clone  # noqa: E402

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
            "**Type:** {{vault-type}}\n\nGuidance.\n\n## Actions\n\nA rule.\n")


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
    write(root, "addons/sales/CLAUDE.md.sections", "## Deal lifecycle\n\nA section.\n")
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
    body = "\nGuidance.\n\n## Actions\n\nA rule.\n"
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
    def entry_at(work, name, **extra):
        return dict({"name": name, "path": str(work / name), "purpose": "A fixture.",
                     "active": True}, **extra)

    def entry(self, name, **extra):
        return self.entry_at(self.work, name, **extra)

    @classmethod
    def audit_at(cls, work, name, ref=None, **extra):
        block, code, kit = open_clone(cls.clone, ref)
        assert not code, block
        developing = master_template(kit.clone, block["ref"], worktree=True)["marker"]
        return audit_scan.audit_vault(cls.entry_at(work, name, **extra), kit, block["ref"],
                                      developing if developing > kit.master else None)

    def audit(self, name="v", ref=None, **extra):
        return self.audit_at(self.work, name, ref, **extra)

    def findings(self, row, check):
        return [f for f in row["findings"] if f["check"] == check]


# ======================================================== which entries are excluded

class ExcludedStatus(unittest.TestCase):
    THEIRS = {"name": "theirs", "machine": "the studio laptop"}

    def test_an_unreachable_vault_another_machine_pulls_names_that_machine(self):
        status, reason = audit_scan.excluded_status(dict(self.THEIRS, path="Q:/no such vault"))
        self.assertEqual(status, "UNREACHABLE")
        self.assertIn("pulled on the studio laptop", reason)

    def test_a_reachable_vault_is_read_whoever_pulls_it_and_active_or_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit_scan.excluded_status({"name": "bare", "path": tmp}),
                             ("UNREACHABLE", "the path holds no CLAUDE.md"))
            (Path(tmp) / "CLAUDE.md").write_text("# Theirs\n", encoding="utf-8")
            self.assertIsNone(audit_scan.excluded_status(dict(self.THEIRS, path=tmp)))
            self.assertIsNone(audit_scan.excluded_status(
                {"name": "quiet", "path": tmp, "active": False}))

    def test_an_entry_missing_its_name_or_path_is_invalid(self):
        for entry in ({"name": "nameless-path"}, "not an entry", {"name": "numbered", "path": 7}):
            self.assertEqual(audit_scan.excluded_status(entry)[0], "INVALID")


# ======================================================== the fixture fleet (Done when)

class FleetCase(CloneCase):
    """Two vaults: aligned, and behind with a stale integration and skill copy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        work = cls.fleet = cls.tmp / "fleet"
        build_vault(work / "aligned")
        build_vault(work / "behind", marker="2026.09.01", skill_version=1,
                    logbook_rev="2026.09.01", logbook_body="v1")
        cls.before = {n: tree_bytes(work / n) for n in ("aligned", "behind")}
        cls.rows = {n: cls.audit_at(work, n) for n in cls.before}

    def test_the_aligned_vault_has_no_finding_and_the_working_tree_is_never_the_bar(self):
        row = self.rows["aligned"]
        self.assertEqual((row["revision"]["verdict"], row["revision"]["master"]),
                         ("equal", "2026.10.01"))
        self.assertEqual(row["findings"], [])

    def test_the_behind_vault_lists_the_intervening_entries(self):
        row = self.rows["behind"]
        self.assertEqual(row["revision"]["verdict"], "behind")
        self.assertEqual(row["revision"]["entries"], ["2026.09.05", "2026.10.01"])
        self.assertIn("/para-upgrade", self.findings(row, "revision")[0]["fix"])

    def test_the_stale_integration_copy_is_behind_its_master(self):
        found = self.findings(self.rows["behind"], "integrations")
        self.assertEqual(len(found), 1)
        self.assertIn("resources/scripts/logbook.py", found[0]["detail"])
        self.assertIn("behind", found[0]["detail"])
        self.assertIn("integrations/logbook/logbook.py", found[0]["detail"])
        self.assertEqual(found[0]["route"], "upgrade")

    def test_the_stale_skill_copy_is_behind_its_master(self):
        found = self.findings(self.rows["behind"], "skills")
        self.assertEqual(len(found), 1)
        self.assertIn("para-notes", found[0]["detail"])

    def test_nothing_in_any_vault_is_written(self):
        for name, before in self.before.items():
            self.assertEqual(tree_bytes(self.fleet / name), before, name)


# ============================================================== the revision outcomes

class RevisionCase(CloneCase):
    def one(self, **vault):
        build_vault(self.work / "v", **vault)
        return self.audit()

    def test_equal(self):
        row = self.one()
        self.assertEqual(row["revision"]["verdict"], "equal")
        self.assertEqual(self.findings(row, "revision"), [])

    def test_behind(self):
        row = self.one(marker="2026.09.05")
        self.assertEqual(row["revision"]["entries"], ["2026.10.01"])

    def test_ahead_judges_nothing_against_the_older_master(self):
        row = self.one(marker="2026.10.02", rules=(), skill_version=1,
                       logbook_rev="2026.09.01", logbook_body="v1",
                       extra_header="**Modules:** nonesuch\n")
        self.assertEqual(row["revision"]["verdict"], "ahead")
        for check in ("rules", "integrations", "skills"):
            self.assertEqual(self.findings(row, check), [], check)
        self.assertFalse(any("nonesuch" in f["detail"] for f in row["findings"]))
        self.assertIn("in development", self.findings(row, "revision")[0]["detail"])

    def test_unstamped(self):
        row = self.one(marker=None)
        self.assertEqual(row["revision"]["verdict"], "no-marker")
        self.assertEqual(len(row["revision"]["entries"]), 3)
        self.assertIn("/para-upgrade", self.findings(row, "revision")[0]["fix"])

    def test_a_malformed_marker_is_unstamped_and_named(self):
        build_vault(self.work / "v")
        write(self.work / "v", "CLAUDE.md",
              claude_md(marker=None).replace("**Type:**",
                                             "<!-- para-os-template: 2026.10.1 -->\n**Type:**"))
        row = self.audit()
        self.assertEqual(row["revision"]["verdict"], "no-marker")
        self.assertTrue(any("2026.10.1" in f["detail"] for f in self.findings(row, "declarations")))

    def test_prose_naming_the_marker_is_not_a_marker(self):
        build_vault(self.work / "v")
        write(self.work / "v", "CLAUDE.md",
              claude_md() + "\nThe `<!-- para-os-template: YYYY.MM.NN -->` comment is read.\n")
        self.assertEqual(self.findings(self.audit(), "declarations"), [])

    def test_a_named_ref_is_read(self):
        build_vault(self.work / "v", marker="2026.09.05")
        self.assertEqual(self.audit(ref="main~1")["revision"]["verdict"], "equal")

    def test_without_a_clone_only_the_vault_s_own_lines_are_judged(self):
        build_vault(self.work / "v", marker="2026.09.05", rules=(),
                    extra_header="**Delivery:** readonly-ipad\n")
        row = audit_scan.audit_vault(self.entry("v"), None, None, None)
        self.assertEqual((row["revision"]["verdict"], row["revision"]["vault"]),
                         ("unverified", "2026.09.05"))
        self.assertEqual([f["check"] for f in row["findings"]], ["declarations"])

    def test_a_vault_ahead_is_never_sent_to_upgrade(self):
        build_vault(self.work / "v", marker="2026.10.02",
                    extra_header="**Delivery:** readonly-ipad\n")
        row = self.audit()
        self.assertTrue(any("**Delivery:**" in f["detail"] for f in row["findings"]))
        self.assertEqual({f["route"] for f in row["findings"]}, {"operator"})


# ================================================================ type and declarations

class DeclarationCase(CloneCase):
    def row(self, roster_rows=None, **vault):
        root = build_vault(self.work / "v", **vault)
        if roster_rows is not None:
            with (root / "CLAUDE.md").open("a", encoding="utf-8") as f:
                f.write("\n## Who writes this vault\n\n| Person | Role | Lane |\n|---|---|---|\n"
                        + "".join(f"| {p} | {r} | - |\n" for p, r in roster_rows))
        return self.audit()

    def test_the_type_is_the_vault_s_own_label_never_judged(self):
        self.assertEqual(self.row(type_line="**Type:** personal-vault")["findings"], [])

    def test_a_registry_kind_is_not_read(self):
        build_vault(self.work / "v")
        self.assertEqual(self.audit(kind="something-else")["findings"], [])

    def test_a_roster_with_no_roles_is_one_finding(self):
        found = self.findings(self.row(roster_rows=[("Ada", ""), ("Bram", "")]),
                              "declarations")
        self.assertEqual(len(found), 1)
        self.assertIn("no one a role", found[0]["detail"])
        self.assertEqual(found[0]["route"], "operator")

    def test_a_roster_row_with_no_role_is_named(self):
        found = self.findings(self.row(roster_rows=[("Ada", "keeper"), ("Bram", "boss")]),
                              "declarations")
        self.assertEqual([("Bram" in f["detail"], f["route"]) for f in found],
                         [(True, "operator")])

    def test_a_roster_with_every_role_set_is_clean(self):
        row = self.row(roster_rows=[("Ada", "keeper"), ("Bram", "steward")])
        self.assertEqual(self.findings(row, "declarations"), [])

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
        row = self.audit()
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


# ===================================================================== rules, skills

class CopiesCase(CloneCase):
    def test_a_crlf_skill_copy_reads_identical(self):
        build_vault(self.work / "v", skill_newline="\r\n")
        self.assertIn(b"\r\n", (self.work / "v/.claude/skills/para-notes/SKILL.md").read_bytes())
        self.assertEqual(self.findings(self.audit(), "skills"), [])

    def test_a_vault_s_own_skill_is_not_a_copy(self):
        build_vault(self.work / "v")
        write(self.work / "v", ".claude/skills/house-style/SKILL.md", "---\nname: house-style\n---\n")
        self.assertEqual(self.findings(self.audit(), "skills"), [])

    def test_a_para_copy_nothing_ships_is_a_finding(self):
        build_vault(self.work / "v")
        write(self.work / "v", ".claude/skills/para-gone/SKILL.md", "---\nname: para-gone\n---\n")
        found = self.findings(self.audit(), "skills")
        self.assertEqual(len(found), 1)
        self.assertIn("para-gone", found[0]["detail"])

    def test_no_copies_is_no_finding(self):
        build_vault(self.work / "v", skill_version=None, logbook_rev=None)
        self.assertEqual(self.audit()["findings"], [])

    def test_a_missing_shipped_rule_file(self):
        build_vault(self.work / "v", rules=())
        found = self.findings(self.audit(), "rules")
        self.assertEqual(len(found), 1)
        self.assertIn("`.claude/rules/filing.md` is missing", found[0]["detail"])

    def test_an_integration_naming_no_master(self):
        build_vault(self.work / "v")
        write(self.work / "v", "resources/scripts/other.py",
              "# para-os-integration: nonesuch 2026.10.01\n")
        found = self.findings(self.audit(), "integrations")
        self.assertEqual(len(found), 1)
        self.assertIn("other.py", found[0]["detail"])
        self.assertEqual(found[0]["route"], "operator")


class StateWordingCase(unittest.TestCase):
    """upgrade_scan classifies every file and its suite pins the states; these pin only what
    this script says about each and where it routes it."""

    def test_integration_states(self):
        found = audit_scan.integration_check(
            [{"path": "x.py", "state": "edited", "master": "integrations/x/x.py"},
             {"path": "y.py", "state": "no-master", "master": None}], "origin/stable")
        self.assertIn("edited against `integrations/x/x.py`", found[0]["detail"])
        self.assertEqual([f["route"] for f in found], ["upgrade", "operator"])

    def test_each_state_is_counted(self):
        rows = [{"state": s} for s in ("untouched", "untouched", "missing")]
        self.assertEqual(audit_scan.state_counts(rows), "2 behind, 1 missing")


SHAPE = ("---\npaths:\n  - \"**/brief.md\"\n---\n\n# Brief structure\n\n**Order:** fixed.\n\n"
         "## The shape\n\nTitle, then status.\n")
CLOSED_SHAPE = SHAPE + "\n## Placeholders\n\n`-` where a section does not apply.\n"
UNSCOPED = "# House\n\nA rule.\n"


class ContractCase(CloneCase):
    """para-shared/rule-files.md, read against every rule file on disk."""

    def row(self, files, name="v", newline="\n", **vault):
        root = build_vault(self.work / name, **vault)
        for file, text in files.items():
            write(root, f".claude/rules/{file}", text, newline)
        return self.audit(name)

    def test_a_rule_file_with_no_frontmatter_loads_in_every_session(self):
        row = self.row({"house.md": UNSCOPED})
        found = self.findings(row, "rules")
        self.assertEqual(len(found), 1)
        self.assertIn("`.claude/rules/house.md` has no frontmatter", found[0]["detail"])
        self.assertIn("every session", found[0]["detail"])
        self.assertIn("`paths:`", found[0]["fix"])
        self.assertIn("rule-files.md", found[0]["fix"])
        self.assertEqual(found[0]["route"], "operator")

    def test_frontmatter_with_no_paths_list_is_the_same_finding(self):
        for n, head in enumerate(("description: A rule.", "paths:", "paths: []",
                                  "paths:\nname: house")):
            with self.subTest(head=head):
                row = self.row({"house.md": f"---\n{head}\n---\n\n# House\n"}, name=f"v{n}")
                found = self.findings(row, "rules")
                self.assertEqual(len(found), 1)
                self.assertIn("no `paths:` list in its frontmatter", found[0]["detail"])

    def test_an_inline_paths_list_scopes_the_file(self):
        row = self.row({"house.md": "---\npaths: [\"projects/**\"]\n---\n\n# House\n"})
        self.assertEqual(self.findings(row, "rules"), [])

    def test_a_voice_profile_is_held_to_it_too(self):
        row = self.row({"voice-ada-peeters.md": "# Ada's voice\n"})
        self.assertIn("voice-ada-peeters.md", self.findings(row, "rules")[0]["detail"])

    def test_a_shape_file_with_no_placeholders(self):
        row = self.row({"brief-structure.md": SHAPE})
        found = self.findings(row, "rules")
        self.assertEqual([f["detail"] for f in found],
                         ["`.claude/rules/brief-structure.md` is a shape file with no "
                          "`## Placeholders`"])
        self.assertEqual(found[0]["route"], "operator")
        self.assertIn("rule-files.md", found[0]["fix"])

    def test_a_shape_file_closing_on_placeholders_is_clean(self):
        row = self.row({"brief-structure.md": CLOSED_SHAPE})
        self.assertEqual(self.findings(row, "rules"), [])

    def test_either_opening_marks_a_shape_file(self):
        for n, text in enumerate((SHAPE.replace("**Order:** fixed.\n\n", ""),
                                  SHAPE.replace("## The shape\n", ""))):
            with self.subTest(n=n):
                row = self.row({"brief-structure.md": text}, name=f"v{n}")
                self.assertEqual(len(self.findings(row, "rules")), 1)

    def test_a_convention_file_naming_the_shape_in_prose_is_not_one(self):
        text = RULE + "\nA shape file opens on an `**Order:**` line and `## The shape`.\n"
        self.assertEqual(self.findings(self.row({"house.md": text}), "rules"), [])

    def test_a_shape_quoted_in_a_fence_is_not_read(self):
        text = RULE + "\n```markdown\n**Order:** fixed.\n\n## The shape\n```\n"
        self.assertEqual(self.findings(self.row({"house.md": text}), "rules"), [])

    def test_a_file_saved_on_windows_reads_the_same(self):
        row = self.row({"brief-structure.md": "﻿" + CLOSED_SHAPE, "house.md": RULE},
                       newline="\r\n")
        self.assertEqual(self.findings(row, "rules"), [])

    def test_both_breaks_in_one_file_are_two_findings(self):
        row = self.row({"brief-structure.md": SHAPE.split("---\n", 2)[2]})
        self.assertEqual(len(self.findings(row, "rules")), 2)

    def test_counted_beside_the_shipped_files_states(self):
        row = self.row({"house.md": UNSCOPED}, rules=())
        self.assertEqual([f["route"] for f in self.findings(row, "rules")],
                         ["upgrade", "operator"])

    def test_a_vault_that_is_not_judged_gets_none(self):
        row = self.row({"house.md": UNSCOPED, "brief-structure.md": SHAPE},
                       marker="2026.10.02")
        self.assertEqual(self.findings(row, "rules"), [])


# ====================================================================== the libraries

class LibrariesCase(CloneCase):
    def installed(self):
        target = self.work / "skills" / "para-command-center" / "scripts" / SCRIPT.name
        target.parent.mkdir(parents=True)
        shutil.copy(SCRIPT, target)
        return subprocess.run([sys.executable, str(target)], capture_output=True, text=True)

    def test_without_the_libraries_beside_it_the_import_exits_2(self):
        done = self.installed()
        self.assertEqual(done.returncode, 2)
        self.assertIn("Install them", done.stderr)

    def test_libraries_that_do_not_import_exit_2(self):
        write(self.work / "skills", "para-shared/scripts/paraos_vault.py", "")
        write(self.work / "skills", "para-upgrade/scripts/upgrade_scan.py", "")
        done = self.installed()
        self.assertEqual(done.returncode, 2)
        self.assertIn("install para-shared", done.stderr)

    def test_in_a_checkout_the_libraries_resolve_from_base(self):
        self.assertEqual(audit_scan.SKILLS_ROOT.parts[-3:], ("base", ".claude", "skills"))

    def test_installed_beside_them_the_libraries_resolve_from_there(self):
        for lib in ("para-shared", "para-upgrade"):
            shutil.copytree(audit_scan.SKILLS_ROOT / lib / "scripts",
                            self.work / "skills" / lib / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
        done = self.installed()
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
