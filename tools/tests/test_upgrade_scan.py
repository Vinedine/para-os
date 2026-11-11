#!/usr/bin/env python3
"""Tests for upgrade_scan.py, whose docstring is the specification: the revision and its
baseline, the file table and its states, the contract diff, the retired list, exit codes.

    python3 test_upgrade_scan.py
    py -3 test_upgrade_scan.py

Standard library only. Every vault and clone is synthetic: one throwaway git clone per class,
two revisions deep, `origin/stable` set by `update-ref`, a feature branch beside it. The one
exception, ExampleCase, scans the real example vault against a clone of this checkout's template.
"""

import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-upgrade" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import upgrade_scan  # noqa: E402
from upgrade_scan import build_report, main  # noqa: E402

SCRIPT = SCRIPTS / "upgrade_scan.py"


def write(root, rel, text, newline="\n"):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return path


def git_in(root, *args):
    # No global excludes (a maintainer ignoring .claude/ drops fixture files), no maintenance.
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "core.autocrlf=false", "-c", "core.excludesFile=",
                           "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
                          cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def template(rev, actions="One checkbox per line.", tail=""):
    return (f"# {{{{Vault Name}}}} Vault Conventions\n\n<!-- para-os-template: {rev} -->\n"
            f"**Type:** {{{{vault-type}}}}\n\n## Actions\n\n{actions}\n\n## Memory\n\nFacts.\n{tail}")


def logbook(rev, body):
    return f"#!/usr/bin/env python3\n# para-os-integration: logbook {rev}\nVALUE = {body!r}\n"


MIRROR_OLD = "WALK = 'past errors'\n"
MIRROR_NEW = "# para-os-integration: vault-mirror 2026.10.01\nWALK = 'stop'\n"
RULE = "---\npaths:\n  - \"**\"\n---\n# Filing {}\n"
PREFS = "# Preferences\n\nHow {}.\n\n## Preferences\n\n"
OLD_ENTRY = "## 2026.09.01\n\n- Start a notes log: `notes/`\n"
NEW_ENTRY = ("## 2026.10.01\n\n- Move each deal note to its deal folder: `notes/`\n"
             "- In a sales vault, add a `**Stage:**` line: each deal brief  \n"
             "Retired: `.claude/skills/para-notes/*.md`, `triage/README.md`\n\n")

REV_A = {
    "CHANGELOG.md": "# Changelog\n\n" + OLD_ENTRY,
    "base/CLAUDE.md.template": template("2026.09.01"),
    "base/bootstrap-prompt.md": "# Bootstrap\n",
    "base/README.md.template": "# {{Vault Name}}\n",
    "base/.gitignore": "*.pyc\n",
    "base/projects/README.md": "# projects\n\n<!-- Placeholder so the folder exists. -->\n",
    "base/.claude/settings.json": '{"autoMemoryEnabled": false}\n',
    "base/.claude/rules/filing.md": RULE.format("v1"),
    "base/.claude/rules/prefs.md": PREFS.format("v1"),
    "base/.claude/skills/para-notes/SKILL.md": "# Notes v1\n",
    "base/.claude/skills/para-notes/old.md": "Old.\n",
    "base/.claude/skills/para-shared/scripts/lib.py": "LIB = 1\n",
    "integrations/logbook/logbook.py": logbook("2026.09.01", "v1"),
    "integrations/vault-mirror/mirror.py": MIRROR_OLD,
    "integrations/vault-mirror/test_mirror.py": "TESTS = 1\n",
    "addons/sales/CLAUDE.md.sections": "<!-- sales -->\n\n## Deals\n\nDeals v1.\n",
    "addons/sales/.claude/rules/deal.md": "---\npaths:\n  - \"deals/**\"\n---\n# Deal\n",
    "addons/sales/.claude/skills/deal-skill/SKILL.md": "# Deal skill\n",
    "addons/sales/skeleton/resources/deals/README.md": "# Deals\n",
    "addons/sales/pipeline/tally.py": "# para-os-integration: sales 2026.09.01\n",
    "multi-vault/para-audit/SKILL.md": "# Audit\n",
    "multi-vault/vaults.json.template": "[]\n",
    "examples/shop/.claude/rules/filing.md": RULE.format("ours"),
}
REV_B = {
    "CHANGELOG.md": "# Changelog\n\n" + NEW_ENTRY + OLD_ENTRY,
    "base/CLAUDE.md.template": template("2026.10.01", "One checkbox per line.\n\nAreas too.",
                                        "\n## Language\n\nEnglish.\n"),
    "base/.claude/rules/filing.md": RULE.format("v2"),
    "base/.claude/rules/prefs.md": PREFS.format("v2"),
    "base/.claude/skills/para-notes/SKILL.md": "# Notes v2\n",
    "base/.claude/skills/para-notes/references/new.md": "New.\n",
    "base/.claude/skills/para-prep/SKILL.md": "# Prep\n",
    "integrations/logbook/logbook.py": logbook("2026.10.01", "v2"),
    "integrations/vault-mirror/mirror.py": MIRROR_NEW,
    "addons/sales/CLAUDE.md.sections": "<!-- sales -->\n\n## Deals\n\nDeals v2.\n",
}


def build_clone(root):
    git_in(root, "init", "-q", "-b", "main")
    for rel, text in REV_A.items():
        write(root, rel, text)
    git_in(root, "add", "-A")
    git_in(root, "commit", "-q", "-m", "2026.09.01")
    for rel, text in REV_B.items():
        write(root, rel, text)
    git_in(root, "rm", "-q", "base/.claude/skills/para-notes/old.md")
    git_in(root, "add", "-A")
    git_in(root, "commit", "-q", "-m", "2026.10.01")
    git_in(root, "update-ref", "refs/remotes/origin/stable", "HEAD")
    git_in(root, "checkout", "-q", "-b", "feat/next")
    write(root, "base/.claude/skills/para-notes/SKILL.md", "# Notes v3\n")
    git_in(root, "commit", "-q", "-am", "next")
    git_in(root, "checkout", "-q", "main")


def vault_md(marker, header=""):
    head = f"<!-- para-os-template: {marker} -->\n" if marker else ""
    return f"# Shop Vault Conventions\n\n{head}**Type:** vault\n{header}\n## Actions\n\nOurs.\n"


class CloneCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="upgrade-scan-")).resolve()
        cls.clone = cls.tmp / "para-os"
        cls.clone.mkdir()
        build_clone(cls.clone)
        cls.rev_a = git_in(cls.clone, "rev-parse", "main~1")
        cls.rev_b = git_in(cls.clone, "rev-parse", "main")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def vault(cls, name, marker="2026.09.01", files=(), header=""):
        root = cls.tmp / name
        for d in ("projects", "areas"):
            (root / d).mkdir(parents=True, exist_ok=True)
        write(root, "CLAUDE.md", vault_md(marker, header))
        for rel, text in dict(files).items():
            write(root, rel, text)
        return root

    @classmethod
    def scan(cls, vault, ref=None, user=None, clone="default"):
        return build_report(vault, cls.clone if clone == "default" else clone, ref,
                            user or cls.tmp / "no-user", cls.tmp / "no-home" / "para-os")

    @staticmethod
    def states(report):
        return {r["path"]: r["state"] for r in report["files"]}


class BehindCase(CloneCase):
    """One vault on 2026.09.01 declaring sales, with a skill run from the user level."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.tmp / "user-skills"
        write(cls.user, "para-audit/SKILL.md", "# Audit, mine\n")
        write(cls.user, "para-notes/old.md", "Old.\n")
        cls.v = cls.vault("behind", header="**Modules:** sales\n", files={
            ".claude/skills/para-notes/SKILL.md": "# Notes v1\n",
            ".claude/skills/para-notes/old.md": "Old.\n",
            ".claude/skills/para-shared/scripts/lib.py": "LIB = 1\n",
            ".claude/rules/filing.md": RULE.format("v1"),
            ".claude/rules/deal.md": "---\npaths:\n  - \"deals/**\"\n---\n# Our deals\n",
            "projects/refit/brief.md": "# Refit\n",
            "resources/scripts/logbook.py": logbook("2026.09.01", "v1"),
            "resources/scripts/other.py": "# para-os-integration: nonesuch 2026.09.01\n",
            "resources/scripts/tally.py": "# para-os-integration: sales 2026.09.01, ours\n",
            "triage/README.md": "# Triage\n",
        })
        write(cls.v, ".claude/rules/filing.md", RULE.format("v1"), newline="\r\n")
        cls.report, cls.code = cls.scan(cls.v, user=cls.user)

    def test_answers(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.report["clone"]["commit"], self.rev_b)
        self.assertEqual(self.report["clone"]["ref"], "origin/stable")

    def test_the_revision_collects_each_entry_after_the_vault_s_with_its_lines(self):
        rev = self.report["revision"]
        self.assertEqual((rev["vault"], rev["master"], rev["verdict"]),
                         ("2026.09.01", "2026.10.01", "behind"))
        self.assertEqual(rev["baseline"], self.rev_a)
        self.assertEqual(rev["entries"], [{"revision": "2026.10.01", "reactions": [
            "Move each deal note to its deal folder: `notes/`",
            "In a sales vault, add a `**Stage:**` line: each deal brief"]}])

    def test_each_kit_file_is_classified_by_hash(self):
        user = str(self.user.resolve())
        self.assertEqual(self.states(self.report), {
            ".claude/rules/deal.md": "edited",
            ".claude/rules/filing.md": "untouched",
            ".claude/rules/prefs.md": "missing",
            ".claude/settings.json": "missing",
            ".claude/skills/deal-skill/SKILL.md": "missing",
            ".claude/skills/para-notes/SKILL.md": "untouched",
            ".claude/skills/para-notes/old.md": "retired",
            ".claude/skills/para-notes/references/new.md": "missing",
            ".claude/skills/para-prep/SKILL.md": "missing",
            "resources/scripts/logbook.py": "untouched",
            "resources/scripts/other.py": "no-master",
            "resources/scripts/tally.py": "edited",
            "triage/README.md": "retired",
            str(Path(user, "para-audit", "SKILL.md")): "edited",
            str(Path(user, "para-notes", "old.md")): "retired",
            str(Path(user, "para-shared", "scripts", "lib.py")): "missing",
        })

    def test_rows_name_their_kind_and_master(self):
        rows = {r["path"]: r for r in self.report["files"]}
        self.assertEqual((rows["resources/scripts/logbook.py"]["kind"],
                          rows["resources/scripts/logbook.py"]["master"]),
                         ("integration", "integrations/logbook/logbook.py"))
        self.assertEqual(rows["resources/scripts/tally.py"]["master"], "addons/sales/pipeline/tally.py")
        self.assertEqual(rows[".claude/rules/deal.md"]["kind"], "rule")
        self.assertIsNone(rows["triage/README.md"]["kind"])
        self.assertIsNone(rows[".claude/skills/para-notes/old.md"]["master"])

    def test_an_edited_copy_carries_the_diff_from_its_master(self):
        row = next(r for r in self.report["files"] if r["path"] == ".claude/rules/deal.md")
        self.assertIn("+# Our deals", row["diff"])
        self.assertNotIn("diff", next(r for r in self.report["files"] if r["state"] != "edited"))

    def test_the_contract_is_the_template_s_change_section_by_section(self):
        rows = {(r["file"], r["heading"]): r["diff"] for r in self.report["contract"]
                if r["state"] == "changed"}
        self.assertEqual(sorted(rows), [("addons/sales/CLAUDE.md.sections", "Deals"),
                                        ("base/CLAUDE.md.template", "Actions"),
                                        ("base/CLAUDE.md.template", "Language")])
        self.assertIn("+Areas too.", rows[("base/CLAUDE.md.template", "Actions")])
        self.assertIn("+## Language", rows[("base/CLAUDE.md.template", "Language")])
        self.assertIn("-Deals v1.", rows[("addons/sales/CLAUDE.md.sections", "Deals")])
        self.assertFalse(any("para-os-template" in d for d in rows.values()))

    def test_the_snapshot_covers_claude_md_and_every_listed_file(self):
        snap = self.report["snapshot"]
        self.assertIn(str(self.v / "CLAUDE.md"), snap)
        self.assertIn(str(self.v / ".claude" / "settings.json"), snap)
        self.assertIsNone(snap[str(self.v / ".claude" / "settings.json")])
        self.assertEqual(len(snap), len(self.report["files"]) + 1)

    def test_the_output_has_under_30_keys(self):
        keys = set()

        def walk(node, prefix):
            if isinstance(node, list):
                for item in node:
                    walk(item, prefix)
            elif isinstance(node, dict):
                for k, v in node.items():
                    keys.add(prefix + k)
                    if prefix + k != "snapshot":   # its keys are paths, not fields
                        walk(v, prefix + k + ".")
        walk(json.loads(json.dumps(self.report)), "")
        self.assertLess(len(keys), 30, sorted(keys))


class StatesCase(CloneCase):
    def test_a_copy_from_another_branch_is_edited_never_untouched(self):
        v = self.vault("branch", files={".claude/skills/para-notes/SKILL.md": "# Notes v3\n"})
        self.assertEqual(self.states(self.scan(v)[0])[".claude/skills/para-notes/SKILL.md"],
                         "edited")

    def test_a_copy_of_bytes_the_kit_held_only_at_another_path_is_edited(self):
        v = self.vault("elsewhere", files={".claude/rules/filing.md": RULE.format("ours")})
        self.assertEqual(self.states(self.scan(v)[0])[".claude/rules/filing.md"], "edited")

    def test_a_skill_the_vault_runs_from_the_user_level_is_compared_there(self):
        user = self.tmp / "user-level"
        write(user, "para-notes/SKILL.md", "# Notes v2\n")
        v = self.vault("user-only")
        files = self.scan(v, user=user)[0]["files"]
        self.assertIn(str((user / "para-notes" / "references" / "new.md").resolve()),
                      [r["path"] for r in files])
        self.assertFalse(any(r["path"].startswith(".claude/skills") for r in files))

    def test_a_user_level_skill_is_compared_with_the_user_level_shared_library_it_imports(self):
        user = self.tmp / "user-and-vault"
        write(user, "para-notes/SKILL.md", "# Notes v2\n")
        write(user, "para-shared/scripts/lib.py", "LIB = 0\n")
        v = self.vault("vault-shared", files={".claude/skills/para-shared/scripts/lib.py": "LIB = 0\n"})
        states = self.states(self.scan(v, user=user)[0])
        self.assertEqual(states[str((user / "para-shared" / "scripts" / "lib.py").resolve())],
                         "edited")
        self.assertEqual(states[".claude/skills/para-shared/scripts/lib.py"], "edited")

    def test_a_skill_both_homes_hold_is_compared_in_each(self):
        user = self.tmp / "user-stale"
        write(user, "para-notes/SKILL.md", "# Notes v1\n")
        v = self.vault("vault-current", files={".claude/skills/para-notes/SKILL.md": "# Notes v2\n",
                                              ".claude/skills/para-notes/references/new.md": "New.\n"})
        states = self.states(self.scan(v, user=user)[0])
        self.assertEqual(states[str((user / "para-notes" / "SKILL.md").resolve())], "untouched")
        self.assertNotIn(".claude/skills/para-notes/SKILL.md", states)

    def test_a_user_level_copy_never_hides_a_skill_missing_from_the_bundled_ones(self):
        user = self.tmp / "user-prep"
        write(user, "para-prep/SKILL.md", "# Prep, mine\n")
        v = self.vault("vault-no-prep", files={".claude/skills/para-notes/SKILL.md": "# Notes v2\n",
                                              ".claude/skills/para-notes/references/new.md": "New.\n"})
        states = self.states(self.scan(v, user=user)[0])
        self.assertEqual(states[".claude/skills/para-prep/SKILL.md"], "missing")
        self.assertEqual(states[str((user / "para-prep" / "SKILL.md").resolve())], "edited")

    def test_a_vault_bundling_no_kit_skill_takes_none_beside_the_user_level_ones(self):
        user = self.tmp / "user-runs-all"
        write(user, "para-notes/SKILL.md", "# Notes v2\n")
        write(user, "para-audit/SKILL.md", "# Audit\n")
        v = self.vault("vault-no-skill", files={".claude/skills/para-shared/scripts/lib.py": "LIB = 1\n",
                                               ".claude/skills/para-audit/SKILL.md": "# Audit\n"})
        paths = [r["path"] for r in self.scan(v, user=user)[0]["files"]]
        self.assertIn(str((user / "para-prep" / "SKILL.md").resolve()), paths)
        self.assertFalse(any(p.startswith(".claude/skills/para-") and "para-shared" not in p
                             for p in paths), paths)

    def test_a_copy_that_only_adds_lines_to_its_master_has_nothing_to_take(self):
        v = self.vault("adds", files={".claude/rules/filing.md": RULE.format("v2") + "Ours.\n"})
        self.assertNotIn(".claude/rules/filing.md", self.states(self.scan(v)[0]))

    def test_an_older_kit_text_with_lines_of_the_vault_s_own_is_offered_as_untouched(self):
        v = self.vault("older-adds", files={".claude/rules/prefs.md": PREFS.format("v1") + "- Short.\n"})
        row = next(r for r in self.scan(v)[0]["files"] if r["path"] == ".claude/rules/prefs.md")
        self.assertEqual((row["state"], row["own"]), ("untouched", ["- Short."]))
        self.assertNotIn("diff", row)

    def test_a_vault_line_whose_neighbour_the_kit_changed_stays_edited_and_is_named(self):
        text = PREFS.format("v1").replace("How v1.\n", "How v1.\nAnd ours.\n")
        v = self.vault("older-moved", files={".claude/rules/prefs.md": text + "- Short.\n"})
        row = next(r for r in self.scan(v)[0]["files"] if r["path"] == ".claude/rules/prefs.md")
        self.assertEqual((row["state"], row["own"]), ("edited", ["And ours.", "- Short."]))
        self.assertIn("+And ours.", row["diff"])

    def test_an_edited_copy_that_is_no_kit_text_plus_lines_names_none(self):
        v = self.vault("not-added", files={".claude/rules/prefs.md": "Ours.\n"})
        row = next(r for r in self.scan(v)[0]["files"] if r["path"] == ".claude/rules/prefs.md")
        self.assertEqual(row["state"], "edited")
        self.assertNotIn("own", row)

    def test_settings_that_only_add_keys_and_entries_have_nothing_to_take(self):
        ours = {"autoMemoryEnabled": False, "permissions": {"deny": ["mcp__*__send_message"]}}
        v = self.vault("settings-adds", files={".claude/settings.json": json.dumps(ours, indent=2)})
        self.assertNotIn(".claude/settings.json", self.states(self.scan(v)[0]))

    def test_settings_that_change_a_kit_value_or_do_not_parse_are_edited(self):
        for name, text in (("settings-changes", '{"autoMemoryEnabled": true}\n'),
                           ("settings-broken", '{"autoMemoryEnabled": false,\n')):
            v = self.vault(name, files={".claude/settings.json": text})
            self.assertEqual(self.states(self.scan(v)[0])[".claude/settings.json"], "edited")

    def test_an_unmarked_copy_at_an_install_path_is_compared_with_its_master(self):
        v = self.vault("unmarked", files={
            "resources/scripts/vault-mirror/mirror.py": MIRROR_OLD,
            "resources/scripts/logbook.py": "VALUE = 'ours'\n",
            "resources/scripts/test_mirror.py": "TESTS = 1\n",
            "resources/scripts/notes/mirror.py": MIRROR_OLD,
        })
        rows = {r["path"]: (r["kind"], r["master"], r["state"]) for r in self.scan(v)[0]["files"]}
        self.assertEqual(rows["resources/scripts/vault-mirror/mirror.py"],
                         ("integration", "integrations/vault-mirror/mirror.py", "untouched"))
        self.assertEqual(rows["resources/scripts/logbook.py"],
                         ("integration", "integrations/logbook/logbook.py", "edited"))
        self.assertNotIn("resources/scripts/test_mirror.py", rows)
        self.assertNotIn("resources/scripts/notes/mirror.py", rows)

    def test_a_vault_with_no_skill_home_gets_no_skill_rows(self):
        v = self.vault("no-skills")
        self.assertFalse(any(r["kind"] == "skill" for r in self.scan(v)[0]["files"]))

    def test_a_long_diff_is_capped(self):
        v = self.vault("long", files={".claude/rules/filing.md": "x\n" * 300})
        row = next(r for r in self.scan(v)[0]["files"] if r["path"] == ".claude/rules/filing.md")
        self.assertTrue(row["diff"].endswith("more lines\n"))
        self.assertEqual(row["diff"].count("\n"), upgrade_scan.DIFF_CAP + 1)

    def test_a_no_master_file_a_retired_line_names_is_retired(self):
        clone = self.tmp / "retire-integration-clone"
        shutil.copytree(self.clone, clone)
        write(clone, "CHANGELOG.md", REV_B["CHANGELOG.md"].replace(
            "`triage/README.md`", "`resources/scripts/other.py`"))
        git_in(clone, "commit", "-q", "-am", "retire an integration")
        v = self.vault("retire-int", files={
            "resources/scripts/other.py": "# para-os-integration: nonesuch 2026.09.01\n"})
        states = self.states(self.scan(v, ref="main", clone=clone)[0])
        self.assertEqual(states["resources/scripts/other.py"], "retired")

    def test_a_folder_named_by_a_retired_line_retires_every_file_under_it(self):
        clone = self.tmp / "retire-clone"
        shutil.copytree(self.clone, clone)
        write(clone, "CHANGELOG.md", REV_B["CHANGELOG.md"].replace(
            "`triage/README.md`", "`resources/old/`, `../escape.md`"))
        git_in(clone, "commit", "-q", "-am", "retire a folder")
        write(self.tmp, "escape.md", "Outside the vault.\n")
        v = self.vault("retire", files={"resources/old/a/b.md": "B\n", "resources/old/c.md": "C\n"})
        states = self.states(self.scan(v, ref="main", clone=clone)[0])
        self.assertEqual(states["resources/old/a/b.md"], "retired")
        self.assertEqual(states["resources/old/c.md"], "retired")
        self.assertFalse(any("escape" in path for path in states))


class RevisionCase(CloneCase):
    def test_equal_has_no_entries_and_no_change(self):
        report, _ = self.scan(self.vault("equal", marker="2026.10.01",
                                         header="**Modules:** nonesuch\n"))
        self.assertEqual(report["revision"]["verdict"], "equal")
        self.assertEqual(report["revision"]["baseline"], self.rev_b)
        self.assertEqual(report["revision"]["entries"], [])
        self.assertEqual({r["state"] for r in report["contract"]}, {"drift", "missing"})

    def test_ahead_has_no_baseline(self):
        report, _ = self.scan(self.vault("ahead", marker="2026.11.01"))
        self.assertEqual(report["revision"]["verdict"], "ahead")
        self.assertIsNone(report["revision"]["baseline"])

    def test_no_marker_collects_every_entry_and_every_section_is_new(self):
        report, _ = self.scan(self.vault("unstamped", marker=None))
        self.assertEqual(report["revision"]["verdict"], "no-marker")
        self.assertEqual([e["revision"] for e in report["revision"]["entries"]],
                         ["2026.10.01", "2026.09.01"])
        memory = next(r for r in report["contract"] if r["heading"] == "Memory")
        self.assertIn("+Facts.", memory["diff"])

    def test_a_marker_no_commit_carried_has_no_baseline(self):
        report, _ = self.scan(self.vault("odd", marker="2026.09.05"))
        self.assertIsNone(report["revision"]["baseline"])

    def test_a_named_ref_is_read(self):
        report, code = self.scan(self.vault("named"), ref="main~1")
        self.assertEqual((code, report["revision"]["verdict"]), (0, "equal"))


class BetweenBumpsCase(CloneCase):
    """Two template changes merge on 2026.10.01, then a fold bumps the marker and nothing
    else, as a revision's pull requests land before its fold."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.later = cls.tmp / "later"
        shutil.copytree(cls.clone, cls.later)
        text = REV_B["base/CLAUDE.md.template"]
        for old, new in (("Facts.", "Facts, dated."), ("English.", "English or the vault's own."),
                         ("2026.10.01", "2026.11.01")):
            text = text.replace(old, new)
            write(cls.later, "base/CLAUDE.md.template", text)
            git_in(cls.later, "commit", "-q", "-am", new)
        cls.released = git_in(cls.later, "rev-parse", "main~2")
        cls.tagged = cls.tmp / "tagged"
        shutil.copytree(cls.later, cls.tagged)
        git_in(cls.tagged, "tag", "-a", "-m", "2026.10.01", "2026.10.01", cls.released)
        git_in(cls.tagged, "tag", "2026.11.01", "main")

    def contract(self, name, marker, ref, clone):
        report, _ = self.scan(self.vault(name, marker=marker), ref=ref, clone=clone)
        return report["revision"], {r["heading"]: r["diff"] for r in report["contract"]
                                    if r["state"] == "changed"}

    def test_a_change_merged_before_the_bump_is_in_the_contract(self):
        rev, rows = self.contract("between", "2026.10.01", "main", self.later)
        self.assertEqual(rev["baseline"], self.rev_b)
        self.assertEqual(sorted(rows), ["Language", "Memory"])
        self.assertIn("+Facts, dated.", rows["Memory"])

    def test_the_release_tag_the_marker_names_is_the_baseline(self):
        rev, rows = self.contract("released", "2026.10.01", "main", self.tagged)
        self.assertEqual(rev["baseline"], self.released)
        self.assertEqual(list(rows), ["Language"])

    def test_a_tag_the_ref_never_carried_is_no_baseline(self):
        rev, _ = self.contract("ahead-tagged", "2026.11.01", "main~1", self.tagged)
        self.assertEqual((rev["verdict"], rev["baseline"]), ("ahead", None))


def kit_template(rev):
    hygiene, retiring = ("No loose files.", "\n## Retiring\n\nThe old rule.\n") \
        if rev == "2026.10.01" else ("No loose files at the root.", "")
    return f"""# {{{{Vault Name}}}} Vault Conventions

<!-- para-os-template: {rev} -->
**Type:** {{{{vault-type}}}}

{{{{One-line description of what this vault covers.}}}}

The lines above are machine-read.

## Layout

- **projects/** - {{{{what a project means here.}}}} One folder each, with a `brief.md`.
- **archive/** - inactive artifacts.{{{{ Add `ideas/` if this vault archives ideas.}}}}

### Hygiene

- No live work.
- {hygiene}

## Checkboxes

| Bucket | `actions.md` | State |
|---|---|---|
| `projects/` | yes | open + closed |
| `areas/network/` | yes | any action about the person |

## Sources

Name the owning file before answering.

{{{{OPTIONAL: a short `Question | Source` table; delete this line otherwise.}}}}

- **Capital** is stated on {{{{the page holding it, or delete this line}}}}.
{retiring}
## Do not add

- **Templates** before a second instance.
- {{{{What belongs in another vault.}}}}
"""


DEALS = "<!-- sales MODULE: merge it in. -->\n\n## Deals\n\nA deal is won on a paid phase.\n"

ALIGNED = """# Shop Vault Conventions

<!-- para-os-template: 2026.10.02 -->
**Type:** vault
**Modules:** sales

A bike shop.

The lines above are machine-read.

## Who writes this vault

Only me.

## Layout

- **projects/** - a refit with a date. One folder each, with a `brief.md`.
- **archive/** - inactive artifacts. `ideas/` = shelved ideas.

### Hygiene

- No live work.
- No loose files at the root.
- Our own rule.

## checkboxes

| Bucket | `actions.md` | State |
| --- | --- | --- |
| `projects/` | yes | open + closed |
| **areas/network/** | never | contact files carry none |
| `suppliers/` | never | tracked in their portal |

## Sources

```text
## Not a heading
```

Name the owning file before answering.

| Question | Source |
|---|---|
| Prices | the supplier list |

## Deals

A deal is won on a paid phase.

## Do not add

- **Templates** before a second instance.
- Accounting: another vault.
- Payroll: another system.
"""

DRIFTED = """# Shop Vault Conventions

<!-- para-os-template: 2026.10.02 -->
**Type:** vault

A bike shop.

## Layout

- **projects/** - a refit with a date. One folder each, holding a brief.
- **archive/** - inactive artifacts.

### Hygiene

- No live work, ever.
- No loose files at the root.

## Checkboxes

| Bucket | `actions.md` | State |
|---|---|---|
| `areas/network/` | never | none |

## Sources

Name the owning file before answering.

## Never add (ours)

- **Templates** before a second instance.
- Accounting: another vault.
"""


class DriftCase(CloneCase):
    """A kit whose template fills, declares and drops lines, at two revisions; the second
    rewords one `###` section and drops a `##` one."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kit = cls.tmp / "drift-kit"
        cls.kit.mkdir()
        git_in(cls.kit, "init", "-q", "-b", "main")
        for rev in ("2026.10.01", "2026.10.02"):
            write(cls.kit, "CHANGELOG.md", f"# Changelog\n\n## {rev}\n")
            write(cls.kit, "base/CLAUDE.md.template", kit_template(rev))
            write(cls.kit, "addons/sales/CLAUDE.md.sections", DEALS)
            git_in(cls.kit, "add", "-A")
            git_in(cls.kit, "commit", "-q", "-m", rev)
        git_in(cls.kit, "update-ref", "refs/remotes/origin/stable", "HEAD")

    def rows(self, name, text):
        report, code = self.scan(self.vault(name, files={"CLAUDE.md": text}), clone=self.kit)
        self.assertEqual(code, 0)
        return {r["heading"]: r for r in report["contract"] if r["state"] != "changed"}

    def test_a_vault_holding_every_kit_line_has_no_drift(self):
        # Fills, own lines and sections, a declared row, dropped optional lines, a heading's
        # case, a fenced heading, and the add-on's lead comment left out.
        self.assertEqual(self.rows("aligned", ALIGNED), {})

    def test_a_line_that_is_only_a_placeholder_may_be_dropped(self):
        text = ALIGNED.replace("- Accounting: another vault.\n- Payroll: another system.\n", "")
        self.assertEqual(self.rows("dropped", text), {})

    def test_the_template_itself_holds_at_each_revision(self):
        for rev in ("2026.10.01", "2026.10.02"):
            self.assertEqual(self.rows(f"bare-{rev}", kit_template(rev)), {})

    def test_each_section_missing_a_kit_line_is_a_row_down_to_level_3(self):
        rows = self.rows("drifted", DRIFTED)
        self.assertEqual({h: r["state"] for h, r in rows.items()}, {
            "": "drift", "Layout": "drift", "Hygiene": "drift", "Checkboxes": "drift",
            "Do not add": "missing"})
        self.assertEqual({r["file"] for r in rows.values()}, {"base/CLAUDE.md.template"})

    def test_a_drift_diff_shows_what_the_vault_lacks_its_fills_as_written(self):
        rows = self.rows("drifted", DRIFTED)
        self.assertIn("-- No live work.\n+- No live work, ever.\n", rows["Hygiene"]["diff"])
        self.assertIn(" ### Hygiene\n", rows["Hygiene"]["diff"])
        layout = rows["Layout"]["diff"]
        self.assertIn("-- **projects/** - {{what a project means here.}} One folder each", layout)
        self.assertIn(" - **archive/** - inactive artifacts.\n", layout)
        self.assertIn("-| `projects/` | yes | open + closed |", rows["Checkboxes"]["diff"])
        self.assertIn(" | `areas/network/` | never | none |", rows["Checkboxes"]["diff"])
        self.assertIn("-The lines above are machine-read.", rows[""]["diff"])

    def test_a_missing_heading_diffs_to_the_vault_s_closest_own_section(self):
        diff = self.rows("drifted", DRIFTED)["Do not add"]["diff"]
        self.assertIn("-## Do not add\n", diff)
        self.assertIn("+## Never add (ours)\n", diff)
        alone = self.rows("alone", DRIFTED.replace("Templates** before a second instance",
                                                   "Nothing alike here at all"))
        self.assertNotIn("\n+", alone["Do not add"]["diff"])

    def test_a_behind_vault_holding_the_ref_s_wording_or_its_own_has_no_drift(self):
        old = kit_template("2026.10.01")
        ahead = old.replace("No loose files.", "No loose files at the root.") \
                   .replace("\n## Retiring\n\nThe old rule.\n", "")
        for name, text in (("behind", old), ("behind-ahead", ahead)):
            self.assertEqual(self.rows(name, text), {}, name)

    def test_no_marker_has_no_drift(self):
        self.assertEqual(self.rows("unmarked", DRIFTED.replace(
            "<!-- para-os-template: 2026.10.02 -->\n", "")), {})

    @staticmethod
    def kept(text, heading, rev):
        return text.replace(f"{heading}\n", f"{heading}\n<!-- para-os-kept: {rev} -->\n", 1)

    def test_a_section_kept_at_the_ref_s_revision_is_no_drift(self):
        text = self.kept(self.kept(DRIFTED, "## Layout", "2026.10.02"), "### Hygiene", "2026.10.02")
        self.assertEqual(set(self.rows("kept", text)), {"", "Checkboxes", "Do not add"})

    def test_a_section_kept_at_an_older_revision_holds_while_the_kit_s_wording_is_unchanged(self):
        # Layout reads the same at both revisions; Hygiene was reworded at the second.
        text = self.kept(self.kept(DRIFTED, "## Layout", "2026.10.01"), "### Hygiene", "2026.10.01")
        rows = self.rows("kept-old", text)
        self.assertNotIn("Layout", rows)
        self.assertEqual(rows["Hygiene"]["state"], "drift")
        self.assertIn("+<!-- para-os-kept: 2026.10.01 -->\n", rows["Hygiene"]["diff"])

    def test_a_behind_vault_keeping_the_ref_s_wording_has_no_drift_before_its_stamp(self):
        # What /para-upgrade's re-run sees after "keep" and before the marker moves.
        text = kit_template("2026.10.01").replace("- No live work.\n", "- No live work, ever.\n")
        self.assertEqual(set(self.rows("behind-drift", text)), {"Hygiene"})
        self.assertEqual(self.rows("behind-kept", self.kept(text, "### Hygiene", "2026.10.02")), {})

    def test_a_kept_revision_the_ref_never_carried_or_a_kept_line_elsewhere_holds_nothing(self):
        for name, text in (("kept-unknown", self.kept(DRIFTED, "### Hygiene", "2026.09.09")),
                           ("kept-other", self.kept(DRIFTED, "## Sources", "2026.10.02"))):
            self.assertEqual(self.rows(name, text)["Hygiene"]["state"], "drift", name)


class ExampleCase(unittest.TestCase):
    """examples/belfoot-vault against a clone of this checkout's template and add-on sections:
    everything base ships has a working instance there, its fixed wording included."""

    EXAMPLE = ROOT / "examples" / "belfoot-vault"

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="upgrade-scan-example-")).resolve()
        cls.kit = cls.tmp / "para-os"
        for rel in ["CHANGELOG.md", "base/CLAUDE.md.template"] + sorted(
                p.relative_to(ROOT).as_posix() for p in ROOT.glob("addons/*/CLAUDE.md.sections")):
            write(cls.kit, rel, (ROOT / rel).read_text(encoding="utf-8"))
        git_in(cls.kit, "init", "-q", "-b", "main")
        git_in(cls.kit, "add", "-A")
        git_in(cls.kit, "commit", "-q", "-m", "kit")
        git_in(cls.kit, "update-ref", "refs/remotes/origin/stable", "HEAD")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def drift(self, vault):
        report, code = build_report(vault, self.kit, None, self.tmp / "no-user",
                                    self.tmp / "no-home" / "para-os")
        self.assertEqual(code, 0)
        self.assertIsNotNone(report["revision"]["baseline"])
        return {r["heading"]: r["state"] for r in report["contract"] if r["state"] != "changed"}

    def test_the_example_vault_holds_every_kit_line(self):
        self.assertEqual(self.drift(self.EXAMPLE), {})

    def test_a_kit_line_the_example_rewords_is_drift(self):
        vault = self.tmp / "belfoot"
        shutil.copytree(self.EXAMPLE, vault, ignore=shutil.ignore_patterns("skills"))
        md = vault / "CLAUDE.md"
        md.write_text(md.read_text(encoding="utf-8").replace(
            "creates every project,", "creates every workstream,"), encoding="utf-8")
        self.assertEqual(self.drift(vault), {"Lifecycle": "drift"})

    def test_a_vault_naming_its_own_cross_cutting_area_and_entity_file_holds(self):
        vault = self.tmp / "own-area"
        shutil.copytree(self.EXAMPLE, vault, ignore=shutil.ignore_patterns("skills"))
        md = vault / "CLAUDE.md"
        md.write_text(md.read_text(encoding="utf-8")
                      .replace("`business/` = running", "`wealth/` = running")
                      .replace("its own `brief.md` + `actions.md`", "its own `README.md` + `actions.md`")
                      .replace("in `areas/business/actions.md`", "in `areas/wealth/actions.md`"),
                      encoding="utf-8")
        self.assertEqual(self.drift(vault), {})

    def own_lines(self, name, areas, routing):
        vault = self.tmp / name
        shutil.copytree(self.EXAMPLE, vault, ignore=shutil.ignore_patterns("skills"))
        md = vault / "CLAUDE.md"
        lines = md.read_text(encoding="utf-8").split("\n")
        lines = [areas if ln.startswith("- **areas/** - ") else
                 routing if ln.startswith("An action goes in the `actions.md`") else ln
                 for ln in lines]
        md.write_text("\n".join(lines), encoding="utf-8")
        return vault

    def test_a_vault_restructuring_its_areas_bullet_and_routing_sentence_holds(self):
        vault = self.own_lines(
            "restructured",
            "- **areas/** - ongoing responsibilities. Per-entity folders (`properties/x/`, "
            "`banking/y/`) each with `README.md` + `sources/` and an `actions.md`; `network/` = "
            "one file per person. `wealth/` = the cross-cutting area: household strategy. "
            "Entities that gate each other form **one** area.",
            "An action goes in the `actions.md` of the project or area it belongs to; one about "
            "a person in their contact file (`areas/network/<person>.md`) under `## Next actions`, "
            "else with the entity it serves; strategic household work tied to no single entity in "
            "`areas/wealth/actions.md`. Scheduled multi-step work means the thing is a project, "
            "not an idea. Never a root `actions.md`; an `actions.md` archives *with its entity*, "
            "fully closed.")
        self.assertEqual(self.drift(vault), {})

    def test_a_routing_sentence_dropping_the_root_actions_ban_is_drift(self):
        vault = self.own_lines(
            "no-ban",
            "- **areas/** - ongoing responsibilities: anything live that is maintained.",
            "A dated go/no-go on an idea is a strategic action in the owning area's `actions.md`.")
        self.assertEqual(self.drift(vault), {"Where a checkbox may live": "drift"})

    def test_a_rule_file_pointer_names_the_paths_its_rule_file_covers_in_the_vault(self):
        vault = self.tmp / "own-paths"
        shutil.copytree(self.EXAMPLE, vault, ignore=shutil.ignore_patterns("skills"))
        md = vault / "CLAUDE.md"
        text, pointers = re.subn(r"(loads on its own when ).+?( is read)",
                                 r"\1a brief or an area's `overview.md`\2",
                                 md.read_text(encoding="utf-8"))
        self.assertGreaterEqual(pointers, 3)
        md.write_text(text, encoding="utf-8")
        self.assertEqual(self.drift(vault), {})
        md.write_text(text.replace("elsewhere it is a link.", "elsewhere it is a link, never a copy."),
                      encoding="utf-8")
        self.assertEqual(self.drift(vault), {"The content frontier": "drift"})


class ExitCase(CloneCase):
    def test_not_a_vault_root_is_exit_3_naming_what_it_lacks(self):
        (self.tmp / "loose" / "projects").mkdir(parents=True)
        (self.tmp / "loose" / "areas").mkdir()
        report, code = self.scan(self.tmp / "loose")
        self.assertEqual((code, report["vault"]), (3, {"root": False, "missing": ["CLAUDE.md"]}))

    def test_no_clone_is_exit_6(self):
        report, code = self.scan(self.vault("v6"), clone=None)
        self.assertEqual(code, 6)
        self.assertIn("no para-os clone", report["clone"]["error"])

    def test_a_ref_that_does_not_resolve_is_exit_4(self):
        self.assertEqual(self.scan(self.vault("v4"), ref="no-such-ref")[1], 4)

    def test_a_folder_that_is_no_repository_is_exit_4(self):
        report, code = self.scan(self.vault("v4b"), clone=self.tmp / "projects-only")
        self.assertEqual(code, 4)
        self.assertIn("not a git repository", report["clone"]["error"])

    def test_no_origin_stable_is_exit_5(self):
        bare = self.tmp / "no-stable"
        bare.mkdir()
        git_in(bare, "init", "-q", "-b", "main")
        write(bare, "README.md", "x\n")
        git_in(bare, "add", "-A")
        git_in(bare, "commit", "-q", "-m", "one")
        self.assertEqual(self.scan(self.vault("v5"), clone=bare)[1], 5)
        report, code = self.scan(self.vault("v5"), ref="main", clone=bare)
        self.assertEqual(code, 4)
        self.assertIn("not a para-os clone", report["clone"]["error"])

    def test_a_template_with_no_marker_is_exit_4(self):
        plain = self.tmp / "unmarked"
        plain.mkdir()
        git_in(plain, "init", "-q", "-b", "main")
        write(plain, "CHANGELOG.md", "# Changelog\n")
        write(plain, "base/CLAUDE.md.template", "# Template\n")
        git_in(plain, "add", "-A")
        git_in(plain, "commit", "-q", "-m", "one")
        report, code = self.scan(self.vault("v4c"), ref="main", clone=plain)
        self.assertEqual(code, 4)
        self.assertIn("marker", report["clone"]["error"])


class CopyCase(CloneCase):
    def copy(self, master, target, commit=None, vault=None):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["copy", "--vault", str(vault or self.tmp), "--clone", str(self.clone),
                         "--commit", commit or self.rev_b, master, str(target)])
        return code, err.getvalue()

    def test_copy_writes_the_master_s_bytes_creating_its_folder(self):
        v = self.vault("copy-new")
        self.assertEqual(self.copy("base/.claude/rules/filing.md", ".claude/rules/filing.md",
                                   vault=v)[0], 0)
        self.assertEqual((v / ".claude" / "rules" / "filing.md").read_bytes(),
                         RULE.format("v2").encode())

    def test_copy_replaces_a_copy_on_disk(self):
        target = write(self.tmp / "copy-old", "filing.md", RULE.format("v1"), newline="\r\n")
        self.assertEqual(self.copy("base/.claude/rules/filing.md", target)[0], 0)
        self.assertEqual(target.read_bytes(), RULE.format("v2").encode())

    def test_copy_keeps_the_vault_s_own_lines_where_they_stood(self):
        v = self.vault("copy-adds", files={
            ".claude/rules/prefs.md": "# Preferences\nMine.\n" + PREFS.format("v1")[14:]
            + "- Short.\n"})
        self.assertEqual(self.copy("base/.claude/rules/prefs.md", ".claude/rules/prefs.md",
                                   vault=v)[0], 0)
        self.assertEqual((v / ".claude" / "rules" / "prefs.md").read_text(),
                         "# Preferences\nMine.\n" + PREFS.format("v2")[14:] + "- Short.\n")

    def test_a_master_that_cannot_be_read_leaves_the_target_as_it_was(self):
        folder = self.tmp / "copy-kept"
        target = write(folder, "filing.md", "Ours.\n")
        for master, commit in (("base/.claude/rules/nope.md", None),
                               ("base/.claude/rules/filing.md", "no-such-ref"),
                               ("base/.claude/rules", None)):
            code, err = self.copy(master, target, commit)
            self.assertEqual(code, 4)
            self.assertIn(master, err)
            self.assertEqual(target.read_bytes(), b"Ours.\n")
            self.assertEqual([p.name for p in folder.iterdir()], ["filing.md"])

    def test_a_target_that_cannot_be_written_leaves_nothing_behind(self):
        folder = self.tmp / "copy-blocked"
        (folder / "a-folder").mkdir(parents=True)
        write(folder, "a-file", "Ours.\n")
        for target in (folder / "a-folder", folder / "a-file" / "filing.md"):
            self.assertEqual(self.copy("base/.claude/rules/filing.md", target)[0], 4)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["a-file", "a-folder"])
        self.assertEqual(list((folder / "a-folder").iterdir()), [])


class CliCase(CloneCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_main_prints_the_report_and_drops_current_rows(self):
        v = self.vault("cli", files={".claude/rules/filing.md": RULE.format("v2")})
        code, out, _ = self.run_main("--vault", str(v), "--clone", str(self.clone),
                                     "--user-skills", str(self.tmp / "no-user"))
        self.assertEqual(code, 0)
        self.assertNotIn(".claude/rules/filing.md", [r["path"] for r in json.loads(out)["files"]])

    def test_main_finds_the_default_clone_and_names_a_failure_on_stderr(self):
        home = self.tmp / "home"
        home.mkdir()
        shutil.copytree(self.clone, home / "para-os")
        code, out, _ = self.run_main("--vault", str(self.vault("cli2")), "--paraos-home", str(home))
        self.assertEqual((code, json.loads(out)["clone"]["path"]), (0, str((home / "para-os").resolve())))
        code, _, err = self.run_main("--vault", str(self.tmp), "--clone", str(self.clone))
        self.assertEqual(code, 3)
        self.assertIn("not a vault root", err)
        code, _, err = self.run_main("--vault", str(self.vault("cli3")), "--clone", str(self.clone),
                                     "--ref", "nope")
        self.assertEqual(code, 4)
        self.assertIn("nope", err)

    def test_run_as_a_command_it_exits_3_or_2_without_the_shared_library(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(self.tmp),
                               "--clone", str(self.clone)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 3)
        alone = self.tmp / "skills" / "para-upgrade" / "scripts"
        alone.mkdir(parents=True)
        shutil.copy(SCRIPT, alone / SCRIPT.name)
        done = subprocess.run([sys.executable, str(alone / SCRIPT.name), "--vault", "."],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("para-shared", done.stderr)


if __name__ == "__main__":
    unittest.main()
