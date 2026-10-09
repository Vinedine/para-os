#!/usr/bin/env python3
"""Tests for fold_changelog.py.

    python3 test_fold_changelog.py
    py -3 test_fold_changelog.py

Every fixture is a throwaway repo in a temporary directory: nothing reads or writes the real
CHANGELOG.md or RELEASES.md.
"""

import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".claude" / "skills" / "release" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fold_changelog
from fold_changelog import (FoldError, changelog_problems, fold, line_problems, main,
                            parse_fragment)

CHANGELOG = """# Changelog

How revisions work.

## 2026.02.01

- Older change: `CLAUDE.md`

## 2026.01.01

- Oldest change: `README.md`
"""

RELEASES = """# Release notes

How to upgrade.

---

## 2026.02.01

**What changes for you.** Older sentence.

**Do you need to do anything?** Run `/para-upgrade`.

## 2026.01.01

**What changes for you.** Oldest sentence.

**Do you need to do anything?** Nothing.
"""

NOT_A_LINE = ("is neither a `- ` Reaction line nor a `Retired:` line naming a backticked "
              "path")


def fragment(changelog, what, todo=None):
    text = f"## Changelog\n\n{changelog}\n\n" if changelog is not None else ""
    text += f"## What changes for you\n\n{what}\n"
    if todo:
        text += f"\n## Do you need to do anything?\n\n{todo}\n"
    return text


def fixture_git(root, *args):
    # No auto maintenance: its detached run writes into .git while a test reads or deletes it.
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "core.autocrlf=false", "-c", "core.excludesFile=",
                    "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
                   cwd=root, check=True, capture_output=True)


class Repo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.write("CHANGELOG.md", CHANGELOG)
        self.write("RELEASES.md", RELEASES)
        self.write("changelog.d/README.md", "# Changelog fragments\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def read(self, name):
        return (self.root / name).read_bytes().decode("utf-8")

    def assertUnchanged(self):
        self.assertEqual(self.read("CHANGELOG.md"), CHANGELOG)
        self.assertEqual(self.read("RELEASES.md"), RELEASES)


class ParseFragment(unittest.TestCase):
    def test_a_whole_fragment_parses(self):
        sections, problems = parse_fragment(fragment(
            "- Do it: `a.md`\n\nRetired: `b.md`, `c/`", "Z.", "Do it."))
        self.assertEqual(problems, [])
        self.assertEqual(sections, {"Changelog": "- Do it: `a.md`\n\nRetired: `b.md`, `c/`",
                                    "What changes for you": "Z.",
                                    "Do you need to do anything?": "Do it."})

    def test_a_fragment_with_nothing_for_a_vault_to_do_has_no_changelog(self):
        self.assertEqual(parse_fragment(fragment(None, "Z.")),
                         ({"What changes for you": "Z."}, []))

    def test_each_problem_is_named(self):
        text = ("Preamble.\n\n## Changelog\n\n**X.** A paragraph. Reaction: none.\n"
                "Retired: the old folder\n\n## Changelog\n\nAgain.\n\n## Notes\n\nStray.\n")
        _, problems = parse_fragment(text)
        self.assertEqual(problems, [
            "text before the first `## ` section",
            "`## Changelog` appears twice",
            "unknown section `## Notes`; the sections are `## Changelog`, "
            "`## What changes for you`, `## Do you need to do anything?`",
            "`## What changes for you` is missing or empty",
            f"`## Changelog` line 1 {NOT_A_LINE}: `**X.** A paragraph. Reaction: none.`",
            f"`## Changelog` line 2 {NOT_A_LINE}: `Retired: the old folder`",
        ])


class LineProblems(unittest.TestCase):
    def test_every_line_of_every_entry_is_a_reaction_or_a_retired_line(self):
        self.assertEqual(changelog_problems(CHANGELOG), [])
        text = CHANGELOG.replace("- Oldest change: `README.md`",
                                 "- Fine: `x`\nRetired: `y`\nA wrapped\n-not a list line")
        self.assertEqual(changelog_problems(text), [
            f"`## 2026.01.01` line 3 {NOT_A_LINE}: `A wrapped`",
            f"`## 2026.01.01` line 4 {NOT_A_LINE}: `-not a list line`"])

    def test_an_entry_may_be_empty_and_the_preamble_is_not_an_entry(self):
        self.assertEqual(changelog_problems("# Changelog\n\nProse.\n\n## 2026.03.01\n\n"
                                            "## 2026.02.01\n\n- A: `b`\n"), [])

    def test_a_long_line_is_quoted_short(self):
        problem, = line_problems("x" * 200, "`## Changelog`")
        self.assertTrue(problem.endswith("`" + "x" * 60 + "...`"), problem)


class Fold(Repo):
    def test_extends_the_open_revision_and_deletes_the_fragments(self):
        self.write("changelog.d/10.md", fragment("- First: `a.md`", "First\nsentence."))
        self.write("changelog.d/11.md", fragment("- Second: `b.md` (#9)\n\nRetired: `c.md`",
                                                 "Second sentence.", "Wire the hook."))
        self.write("changelog.d/12.md", fragment(None, "Third sentence."))
        folded = fold(self.root, "2026.02.01")

        self.assertEqual([p.name for p in folded], ["10.md", "11.md", "12.md"])
        self.assertEqual(self.read("CHANGELOG.md"), CHANGELOG.replace(
            "- Older change: `CLAUDE.md`\n",
            "- Older change: `CLAUDE.md`\n- First: `a.md` (#10)\n- Second: `b.md` (#9)\n"
            "Retired: `c.md`\n"))
        self.assertEqual(self.read("RELEASES.md"), RELEASES.replace(
            "Older sentence.", "Older sentence. First sentence. Second sentence. Third sentence."
        ).replace("Run `/para-upgrade`.\n\n## 2026.01.01",
                  "Run `/para-upgrade`. Wire the hook.\n\n## 2026.01.01"))
        self.assertEqual(sorted(p.name for p in (self.root / "changelog.d").iterdir()),
                         ["README.md"])

    def test_opens_a_new_revision_above_the_newest(self):
        self.write("changelog.d/fix.md", fragment("- New: `n.md`", "New sentence."))
        fold(self.root, "2026.03.01")
        self.assertEqual(self.read("CHANGELOG.md"), CHANGELOG.replace(
            "## 2026.02.01", "## 2026.03.01\n\n- New: `n.md`\n\n## 2026.02.01", 1))
        self.assertEqual(self.read("RELEASES.md"), RELEASES.replace(
            "## 2026.02.01", "## 2026.03.01\n\n**What changes for you.** New sentence.\n\n"
            "**Do you need to do anything?** Run `/para-upgrade`.\n\n## 2026.02.01", 1))

    def test_a_revision_with_nothing_for_a_vault_to_do_is_its_heading(self):
        self.write("changelog.d/12.md", fragment(None, "S."))
        fold(self.root, "2026.03.01")
        opened = self.read("CHANGELOG.md")
        self.assertIn("## 2026.03.01\n\n## 2026.02.01\n", opened)
        self.write("changelog.d/14.md", fragment(None, "U."))
        fold(self.root, "2026.03.01")
        self.assertEqual(self.read("CHANGELOG.md"), opened)
        self.write("changelog.d/13.md", fragment("- Now: `x`", "T."))
        fold(self.root, "2026.03.01")
        self.assertIn("## 2026.03.01\n\n- Now: `x` (#13)\n\n## 2026.02.01\n",
                      self.read("CHANGELOG.md"))

    def test_a_new_revision_carries_what_the_upgrade_cannot_do(self):
        self.write("changelog.d/12.md", fragment("- New: `n`", "S.", "Pull first."))
        fold(self.root, "2026.03.01")
        self.assertIn("**Do you need to do anything?** Run `/para-upgrade`. Pull first.\n",
                      self.read("RELEASES.md"))

    def test_extends_a_revision_that_is_the_only_one(self):
        self.write("CHANGELOG.md", CHANGELOG.split("\n## 2026.01.01")[0])
        self.write("RELEASES.md", RELEASES.split("\n## 2026.01.01")[0])
        self.write("changelog.d/13.md", fragment("- Last: `l`", "S."))
        fold(self.root, "2026.02.01")
        self.assertTrue(self.read("CHANGELOG.md").endswith(
            "- Older change: `CLAUDE.md`\n- Last: `l` (#13)\n"))

    def test_nothing_to_fold(self):
        self.assertEqual(fold(self.root, "2026.02.01"), [])
        shutil.rmtree(self.root / "changelog.d")
        self.assertEqual(fold(self.root, "2026.02.01"), [])
        self.assertUnchanged()

    def test_refuses_and_writes_nothing(self):
        good = self.write("changelog.d/14.md", fragment("- A: `a`", "S."))
        cases = {
            "2026.2.1": "`2026.2.1` is not a YYYY.MM.NN revision label",
            "2026.01.01": "`2026.01.01` is older than the newest revision, `2026.02.01`",
        }
        for label, message in cases.items():
            with self.subTest(label=label), self.assertRaises(FoldError) as caught:
                fold(self.root, label)
            self.assertEqual(str(caught.exception), message)

        self.write("changelog.d/15.md", "## Changelog\n\n**B.** A paragraph.\n")
        with self.assertRaises(FoldError) as caught:
            fold(self.root, "2026.02.01")
        self.assertEqual(str(caught.exception).splitlines(), [
            "changelog.d/15.md: `## What changes for you` is missing or empty",
            f"changelog.d/15.md: `## Changelog` line 1 {NOT_A_LINE}: `**B.** A paragraph.`"])
        self.assertUnchanged()
        self.assertTrue(good.exists())

    def test_refuses_files_it_cannot_fold_into(self):
        self.write("changelog.d/16.md", fragment("- A: `a`", "S.", "Do it."))
        cases = {
            "no heading": ("# Changelog\n", RELEASES,
                           "CHANGELOG.md has no `## YYYY.MM.NN` revision heading"),
            "disagree": (CHANGELOG, RELEASES.replace("## 2026.02.01\n", ""),
                         "CHANGELOG.md and RELEASES.md disagree on the newest revision; "
                         "run tools/check.py"),
            "no todo paragraph": (CHANGELOG, RELEASES.replace(
                "**Do you need to do anything?** Run `/para-upgrade`.\n\n", ""),
                "RELEASES.md `## 2026.02.01` has no `**Do you need to do anything?**` paragraph"),
        }
        for name, (changelog, releases, message) in cases.items():
            with self.subTest(name):
                self.write("CHANGELOG.md", changelog)
                self.write("RELEASES.md", releases)
                with self.assertRaises(FoldError) as caught:
                    fold(self.root, "2026.02.01")
                self.assertEqual(str(caught.exception), message)
                self.assertEqual(self.read("CHANGELOG.md"), changelog)
                self.assertEqual(self.read("RELEASES.md"), releases)


class MergeOrder(Repo):
    def test_folds_in_the_order_git_added_them_then_the_uncommitted(self):
        fixture_git(self.root, "init", "-q")
        self.write("changelog.d/b.md", fragment("- B: `b`", "B."))
        fixture_git(self.root, "add", "-A")
        fixture_git(self.root, "commit", "-q", "--no-verify", "-m", "b")
        self.write("changelog.d/a.md", fragment("- A: `a`", "A."))
        fixture_git(self.root, "add", "-A")
        fixture_git(self.root, "commit", "-q", "--no-verify", "-m", "a")
        # Folded away by a release, then a later pull request adds the same name again.
        (self.root / "changelog.d" / "b.md").unlink()
        fixture_git(self.root, "commit", "-q", "--no-verify", "-am", "fold")
        self.write("changelog.d/b.md", fragment("- B again: `b`", "B."))
        fixture_git(self.root, "add", "-A")
        fixture_git(self.root, "commit", "-q", "--no-verify", "-m", "b again")
        self.write("changelog.d/0.md", fragment("- Zero: `z`", "Z."))

        self.assertEqual([p.name for p in fold(self.root, "2026.02.01")],
                         ["a.md", "b.md", "0.md"])

    def test_without_git_folds_by_name(self):
        for name in ("b.md", "a.md"):
            self.write(f"changelog.d/{name}", fragment(f"- {name}: `x`", "S."))
        with mock.patch.object(fold_changelog.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual([p.name for p in fold(self.root, "2026.02.01")], ["a.md", "b.md"])


class Main(Repo):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([*argv, "--root", str(self.root)])
        return code, out.getvalue(), err.getvalue()

    def test_reports_what_it_folded(self):
        self.assertEqual(self.run_main("2026.02.01"),
                         (0, "No fragments in changelog.d/; nothing to fold.\n", ""))
        self.write("changelog.d/20.md", fragment("- A: `a`", "S."))
        self.assertEqual(self.run_main("2026.02.01"),
                         (0, "Folded 1 fragment(s) into 2026.02.01: 20.md\n", ""))

    def test_a_refusal_exits_non_zero(self):
        self.assertEqual(self.run_main("2026.01.01")[0], 0)   # nothing to fold is not a refusal
        self.write("changelog.d/21.md", fragment("- A: `a`", "S."))
        code, out, err = self.run_main("2026.01.01")
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err, "fold_changelog: `2026.01.01` is older than the newest revision, "
                              "`2026.02.01`\n")


if __name__ == "__main__":
    unittest.main()
