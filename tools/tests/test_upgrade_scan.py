#!/usr/bin/env python3
"""Tests for upgrade_scan.py, whose docstring is the specification: the revision and its
baseline, the file table and its states, the contract diff, the retired list, exit codes.

    python3 test_upgrade_scan.py
    py -3 test_upgrade_scan.py

Standard library only. Every vault and clone is synthetic: one throwaway git clone per class,
two revisions deep, `origin/stable` set by `update-ref`, a feature branch beside it.
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


RULE = "---\npaths:\n  - \"**\"\n---\n# Filing {}\n"
OLD_ENTRY = "## 2026.09.01\n\n**Start.** Reaction: none.\n"
NEW_ENTRY = ("## 2026.10.01\n\n**Areas too.** An area's file is one\ntoo. Reaction: take the "
             "sentence into `## Actions`.\n\n**Kit.** Reaction: re-sync `/para-notes`.\n\n"
             "Retired: `.claude/skills/para-notes/*.md`, `triage/README.md`\n\n---\n\n")

REV_A = {
    "CHANGELOG.md": "# Changelog\n\n" + OLD_ENTRY,
    "base/CLAUDE.md.template": template("2026.09.01"),
    "base/bootstrap-prompt.md": "# Bootstrap\n",
    "base/README.md.template": "# {{Vault Name}}\n",
    "base/.gitignore": "*.pyc\n",
    "base/projects/README.md": "# projects\n\n<!-- Placeholder so the folder exists. -->\n",
    "base/.claude/settings.json": '{"autoMemoryEnabled": false}\n',
    "base/.claude/rules/filing.md": RULE.format("v1"),
    "base/.claude/skills/para-notes/SKILL.md": "# Notes v1\n",
    "base/.claude/skills/para-notes/old.md": "Old.\n",
    "base/.claude/skills/para-shared/scripts/lib.py": "LIB = 1\n",
    "integrations/logbook/logbook.py": logbook("2026.09.01", "v1"),
    "addons/sales/CLAUDE.md.sections": "<!-- sales -->\n\n## Deals\n\nDeals v1.\n",
    "addons/sales/.claude/rules/deal.md": "---\npaths:\n  - \"deals/**\"\n---\n# Deal\n",
    "addons/sales/.claude/skills/deal-skill/SKILL.md": "# Deal skill\n",
    "addons/sales/skeleton/resources/deals/README.md": "# Deals\n",
    "addons/sales/pipeline/tally.py": "# para-os-integration: sales 2026.09.01\n",
    "multi-vault/para-audit/SKILL.md": "# Audit\n",
    "multi-vault/vaults.json.template": "[]\n",
}
REV_B = {
    "CHANGELOG.md": "# Changelog\n\n" + NEW_ENTRY + OLD_ENTRY,
    "base/CLAUDE.md.template": template("2026.10.01", "One checkbox per line.\n\nAreas too.",
                                        "\n## Language\n\nEnglish.\n"),
    "base/.claude/rules/filing.md": RULE.format("v2"),
    "base/.claude/skills/para-notes/SKILL.md": "# Notes v2\n",
    "base/.claude/skills/para-notes/references/new.md": "New.\n",
    "base/.claude/skills/para-prep/SKILL.md": "# Prep\n",
    "integrations/logbook/logbook.py": logbook("2026.10.01", "v2"),
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
            ".claude/rules/deal.md": "---\npaths:\n  - \"deals/**\"\n---\n# Deal\nOur line.\n",
            "projects/refit/brief.md": "# Refit\n",
            "resources/scripts/logbook.py": logbook("2026.09.01", "v1"),
            "resources/scripts/other.py": "# para-os-integration: nonesuch 2026.09.01\n",
            "resources/scripts/tally.py": "# para-os-integration: sales 2026.09.01\nmine\n",
            "triage/README.md": "# Triage\n",
        })
        write(cls.v, ".claude/rules/filing.md", RULE.format("v1"), newline="\r\n")
        cls.report, cls.code = cls.scan(cls.v, user=cls.user)

    def test_answers(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.report["clone"]["commit"], self.rev_b)
        self.assertEqual(self.report["clone"]["ref"], "origin/stable")

    def test_the_revision_collects_each_entry_after_the_vault_s_with_its_reactions(self):
        rev = self.report["revision"]
        self.assertEqual((rev["vault"], rev["master"], rev["verdict"]),
                         ("2026.09.01", "2026.10.01", "behind"))
        self.assertEqual(rev["baseline"], self.rev_a)
        self.assertEqual(rev["entries"], [{"revision": "2026.10.01", "reactions": [
            "Reaction: take the sentence into `## Actions`.",
            "Reaction: re-sync `/para-notes`."]}])

    def test_each_kit_file_is_classified_by_hash(self):
        user = str(self.user.resolve())
        self.assertEqual(self.states(self.report), {
            ".claude/rules/deal.md": "edited",
            ".claude/rules/filing.md": "untouched",
            ".claude/settings.json": "missing",
            ".claude/skills/deal-skill/SKILL.md": "missing",
            ".claude/skills/para-notes/SKILL.md": "untouched",
            ".claude/skills/para-notes/old.md": "retired",
            ".claude/skills/para-notes/references/new.md": "missing",
            ".claude/skills/para-prep/SKILL.md": "missing",
            ".gitignore": "missing",
            "README.md": "missing",
            "resources/deals/README.md": "missing",
            "resources/scripts/logbook.py": "untouched",
            "resources/scripts/other.py": "no-master",
            "resources/scripts/tally.py": "edited",
            "triage/README.md": "retired",
            str(Path(user, "para-audit", "SKILL.md")): "edited",
            str(Path(user, "para-notes", "old.md")): "retired",
        })

    def test_rows_name_their_kind_and_master(self):
        rows = {r["path"]: r for r in self.report["files"]}
        self.assertEqual((rows["resources/scripts/logbook.py"]["kind"],
                          rows["resources/scripts/logbook.py"]["master"]),
                         ("integration", "integrations/logbook/logbook.py"))
        self.assertEqual(rows["resources/scripts/tally.py"]["master"], "addons/sales/pipeline/tally.py")
        self.assertEqual(rows[".claude/rules/deal.md"]["kind"], "rule")
        self.assertEqual(rows["README.md"]["master"], "base/README.md.template")
        self.assertEqual(rows["triage/README.md"]["kind"], "skeleton")
        self.assertIsNone(rows[".claude/skills/para-notes/old.md"]["master"])

    def test_an_edited_copy_carries_the_diff_from_its_master(self):
        row = next(r for r in self.report["files"] if r["path"] == ".claude/rules/deal.md")
        self.assertIn("+Our line.", row["diff"])
        self.assertNotIn("diff", next(r for r in self.report["files"] if r["state"] != "edited"))

    def test_a_placeholder_whose_folder_holds_content_is_not_missing(self):
        self.assertNotIn("projects/README.md", self.states(self.report))

    def test_the_contract_is_the_template_s_change_section_by_section(self):
        rows = {(r["file"], r["heading"]): r["diff"] for r in self.report["contract"]}
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

    def test_a_skill_the_vault_runs_from_the_user_level_is_compared_there(self):
        user = self.tmp / "user-level"
        write(user, "para-notes/SKILL.md", "# Notes v2\n")
        v = self.vault("user-only")
        files = self.scan(v, user=user)[0]["files"]
        self.assertIn(str((user / "para-notes" / "references" / "new.md").resolve()),
                      [r["path"] for r in files])
        self.assertFalse(any(r["path"].startswith(".claude/skills") for r in files))

    def test_a_vault_with_no_skill_home_gets_no_skill_rows(self):
        v = self.vault("no-skills")
        self.assertFalse(any(r["kind"] == "skill" for r in self.scan(v)[0]["files"]))

    def test_a_long_diff_is_capped(self):
        v = self.vault("long", files={".claude/rules/filing.md": "x\n" * 300})
        row = next(r for r in self.scan(v)[0]["files"] if r["path"] == ".claude/rules/filing.md")
        self.assertTrue(row["diff"].endswith("more lines\n"))
        self.assertEqual(row["diff"].count("\n"), upgrade_scan.DIFF_CAP + 1)

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
    def test_equal_has_no_entries_and_no_contract(self):
        report, _ = self.scan(self.vault("equal", marker="2026.10.01"))
        self.assertEqual(report["revision"]["verdict"], "equal")
        self.assertEqual(report["revision"]["baseline"], self.rev_b)
        self.assertEqual((report["revision"]["entries"], report["contract"]), ([], []))

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


class ExitCase(CloneCase):
    def test_not_a_vault_root_is_exit_3(self):
        (self.tmp / "loose").mkdir()
        self.assertEqual(self.scan(self.tmp / "loose")[1], 3)

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

    def test_without_the_shared_library_it_exits_2(self):
        alone = self.tmp / "skills" / "para-upgrade" / "scripts"
        alone.mkdir(parents=True)
        shutil.copy(SCRIPT, alone / SCRIPT.name)
        done = subprocess.run([sys.executable, str(alone / SCRIPT.name), "--vault", "."],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("para-shared", done.stderr)


if __name__ == "__main__":
    unittest.main()
