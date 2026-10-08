"""Tests for check.py's own rules, run against fixtures built in a temporary folder."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402  (importing it runs no check)

SKILL = """---
name: demo
description: A fixture skill.
allowed-tools: {tools}
argument-hint: '[--test]'
---

# Demo

`--test`: [para-shared/test-run.md](../para-shared/test-run.md).

## Strict rules

- None.
"""


class SkillContractAllowedTools(unittest.TestCase):
    def failures_for(self, tools):
        """check_skills()'s failures over one fixture skill whose allowed-tools is `tools`."""
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        skills = root / "base" / ".claude" / "skills"
        (skills / "demo").mkdir(parents=True)
        (skills / "demo" / "SKILL.md").write_text(SKILL.format(tools=tools), encoding="utf-8")
        (skills / "para-shared").mkdir()
        (skills / "para-shared" / "test-run.md").write_text("# Test runs\n", encoding="utf-8")
        with mock.patch.object(check, "ROOT", root), \
                mock.patch.object(check, "SKILLS_DIR", skills), \
                mock.patch.object(check, "EXTRA_SKILL_DIRS", ()), \
                mock.patch.object(check, "failures", []):
            check.check_skills()
            return check.failures

    def test_bare_shell_entries_fail(self):
        failures = self.failures_for("Bash, PowerShell, Glob, Grep, Read")
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("base/.claude/skills/demo/SKILL.md", failures[0])
        self.assertIn("(Bash, PowerShell)", failures[0])

    def test_command_patterns_pass(self):
        self.assertEqual(self.failures_for(
            "Bash(python3 *), Bash(py *), Bash(git mv *), "
            "Bash(osascript -e 'tell application \"Finder\" to delete POSIX file *), "
            "Glob, Read, mcp__google-workspace__get_events"), [])

    def test_a_pattern_that_is_only_a_wildcard_is_the_whole_shell(self):
        self.assertEqual(check.whole_shell_grants("Bash(*), PowerShell(:*), Bash(ls *), Read"),
                         ["Bash(*)", "PowerShell(:*)"])


class InstalledLinks(unittest.TestCase):
    def failures_for(self, staging):
        """check_installed_links()'s failures over a base skill, para-shared/ and a multi-vault
        skill whose references/staging.md holds `staging`."""
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        skills = root / "base" / ".claude" / "skills"
        (skills / "para-shared").mkdir(parents=True)
        (skills / "para-shared" / "connectors.md").write_text("# Connectors\n", encoding="utf-8")
        (skills / "demo").mkdir()
        (skills / "demo" / "SKILL.md").write_text(
            "See [connectors](../para-shared/connectors.md).\n", encoding="utf-8")
        ingest = root / "multi-vault" / "ingest"
        (ingest / "references").mkdir(parents=True)
        (ingest / "SKILL.md").write_text("[Staging](references/staging.md)\n", encoding="utf-8")
        (ingest / "references" / "staging.md").write_text(staging, encoding="utf-8")
        with mock.patch.object(check, "ROOT", root), \
                mock.patch.object(check, "SKILLS_DIR", skills), \
                mock.patch.object(check, "EXTRA_SKILL_DIRS", (root / "multi-vault",)), \
                mock.patch.object(check, "failures", []):
            check.check_installed_links()
            return check.failures

    def test_links_through_the_installed_layout_pass(self):
        self.assertEqual(self.failures_for(
            "[connectors](../../para-shared/connectors.md#sign-in), [skill](../SKILL.md), "
            "[web](https://example.com/x.md), [anchor](#below)\n"), [])

    def test_a_link_that_resolves_only_from_the_repo_fails(self):
        failures = self.failures_for(
            "[codes](../../../base/.claude/skills/para-shared/connectors.md#sign-in)\n")
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("multi-vault/ingest/references/staging.md:1", failures[0])
        self.assertIn("leaves the skills folder", failures[0])

    def test_a_missing_target_fails(self):
        failures = self.failures_for("[gone](../../para-shared/missing.md)\n")
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("names no file", failures[0])

    def test_examples_in_code_are_not_links(self):
        self.assertEqual(self.failures_for(
            "`[x](../../../nowhere.md)`\n\n```\n[y](../../../nowhere.md)\n```\n"), [])


if __name__ == "__main__":
    unittest.main()
