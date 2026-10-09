#!/usr/bin/env python3
"""Tests for upgrade_scan.py. Each one pins a rule of the script, which is the
specification, or a defect a --test run found
(the baseline walking HEAD, a missing setup file, the Node suite locator, a copy changed
between the report and the write).

    python3 test_upgrade_scan.py
    py -3 test_upgrade_scan.py

Standard library only. Fictitious names throughout: nothing here reads or writes a real
vault or a real para-os clone. The shared verdict rules (`compute_verdict`,
`_mechanical_equivalence`) are pinned with synthetic byte fixtures rather than a git history,
since every rule they state is a pure function of C, M, H and O; everything that has to walk
real git history (the baseline lookup, the clone-layout readers, the skill/integration
tree diffs) runs against one throwaway git clone built once per test class.
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
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-upgrade" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import upgrade_scan  # noqa: E402
from upgrade_scan import (  # noqa: E402
    HistoryBatch, _dirty_masters, _effective_blob,
    _entry_shape, _find_undeclared_addon_skill, _frontmatter_paths,
    _global_commit_order, _ignored_in_scope, _integration_master_path, _integration_suite,
    _mechanical_equivalence, _parse_batch_output, _reaction_paths, _root_history_map,
    _rule_anchors,
    _rule_kind, _rule_master, _scope_files, _sweep_root,
    _unmarked_matches, baseline_block, build_report,
    checkboxes_block, clone_block, compute_verdict, delta_block, integrations_block, main,
    masters_block,
    rules_block, sections_block, settings_block, since_block, skeleton_block, skills_block, smoke_block,
    snapshot_block, unmarked_scripts, vault_block,
)
from paraos_vault import integration_markers  # noqa: E402
from paraos_clone import changelog_entries, clone_read  # noqa: E402

SCRIPT = SCRIPTS / "upgrade_scan.py"


# ================================================================== small local helpers

def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_bytes(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def write_at(path, text):
    """Like write(), but for a caller that already has the full target Path (an entity
    folder built up in pieces) rather than a (root, rel) pair."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fixture_git(root, *args):
    # No global excludes: a maintainer ignoring .claude/ would drop fixture files silently.
    # No auto maintenance: its detached run writes into .git while a test reads or deletes it.
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "core.autocrlf=false", "-c", "core.excludesFile=",
                    "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
                   cwd=root, check=True, capture_output=True)


def fixture_template(marker):
    lines = ["# Vault Conventions", "", f"<!-- para-os-template: {marker} -->",
             "**Type:** vault-type"]
    return "\n".join(lines + ["", "Guidance.", ""])


def integration_source(revision, body):
    return f"#!/usr/bin/env python3\n# para-os-integration: widget {revision}\nVALUE = {body!r}\n"


CHANGELOG_TEXT = """# Changelog

Intro text, never a revision entry.

---

## 2026.09.01

**Widget integration rewritten.** New behaviour for the widget script. Reaction: re-sync
installed widget copies.

**Second change.** Base no longer ships `.editor/settings.json`. Reaction: delete the
vault's `.editor/settings.json`, and add `.editor/` to `.gitignore`.

---

## 2026.08.02

**A small fix.** One paragraph of detail. Reaction: re-sync the widget script.

---

## 2026.08.01

Six changes, before revisions carried a Reaction line.

**First change.** Detail about the first one.

**Second change.** Detail about the second one.

Also, both housekeeping:

- **Housekeeping one.** Detail one.
- **Housekeeping two.** Detail two.
"""


def build_clone(root, bare_dir):
    """A throwaway para-os clone: three revisions of base/CLAUDE.md.template and of
    integrations/widget/widget.py, an addon's pipeline script, a fake origin remote so
    origin/main and origin/stable exist, and a feature branch left checked out at the end -
    so a test calling baseline_block(clone, "main", ...) is genuinely reading a ref other
    than HEAD.
    """
    fixture_git(root, "init", "-q", "-b", "main")
    fixture_git(root, "config", "core.autocrlf", "false")
    fixture_git(root, "config", "core.excludesFile", str(root / ".git" / "no-excludes"))

    write(root, "CHANGELOG.md", CHANGELOG_TEXT)
    write(root, "base/CLAUDE.md.template", fixture_template("2026.08"))  # raw legacy label
    write(root, "base/bootstrap-prompt.md", "# Bootstrap\n")
    write(root, "base/.claude/skills/widget-skill/SKILL.md",
          "---\nname: widget-skill\n---\n# Widget skill\n\nscripts/run.py\n")
    write(root, "base/.claude/skills/widget-skill/scripts/run.py", "print('v1')\n")
    write(root, "base/.claude/skills/widget-skill/scripts/test_run.py", "# tests v1\n")
    write(root, "base/.claude/skills/widget-skill/scripts/helper.py", "# helper v1\n")
    write(root, "base/README.md.template", "# Vault\n")
    write(root, "addons/gadget/pipeline/gadget.ps1", "# gadget v1\n")
    write(root, "integrations/widget/widget.py", integration_source("2026.08.01", "V1"))
    write(root, "integrations/widget/README.md", "# widget\n")
    write(root, "integrations/widget/test_widget.py", "# tests\n")
    write(root, "integrations/widget/widget.config.json.template", "{}\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "rev 2026.08.01")
    fixture_git(root, "tag", "rev1")

    write(root, "base/CLAUDE.md.template", fixture_template("2026.08.02"))
    write(root, "integrations/widget/widget.py", integration_source("2026.08.02", "V2"))
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "rev 2026.08.02")
    fixture_git(root, "tag", "rev2")

    write(root, "base/CLAUDE.md.template", fixture_template("2026.09.01"))
    write(root, "integrations/widget/widget.py", integration_source("2026.09.01", "V3"))
    write(root, "base/.claude/skills/widget-skill/scripts/run.py", "print('v3')\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "rev 2026.09.01")
    fixture_git(root, "tag", "rev3")

    # A same-revision content fix: widget.py changes again with no marker bump - the
    # within-revision case, and also gives rev3's own history more than one entry.
    write(root, "integrations/widget/widget.py", integration_source("2026.09.01", "V3-fixed"))
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "typo fix, same revision")
    fixture_git(root, "tag", "rev3b")

    subprocess.run(["git", "init", "-q", "--bare", str(bare_dir)], check=True,
                   capture_output=True)
    # The push runs maintenance inside the bare repository, where fixture_git's -c never reaches.
    fixture_git(bare_dir, "config", "gc.auto", "0")
    fixture_git(bare_dir, "config", "maintenance.auto", "false")
    fixture_git(root, "remote", "add", "origin", str(bare_dir))
    fixture_git(root, "push", "-q", "origin", "main", "main:stable")
    fixture_git(root, "fetch", "-q", "origin")

    # A feature branch ahead on one skill file only - the "synced from a feature branch"
    # case - left checked out, so main's own history has to be read by naming it, never HEAD.
    fixture_git(root, "checkout", "-q", "-b", "feat/extra")
    write(root, "base/.claude/skills/widget-skill/scripts/run.py", "print('feature-branch')\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "feature branch edit")


class CloneCase(unittest.TestCase):
    """One fixture clone for every reader below: they only read it. main is at rev3b
    (marker 2026.09.01); feat/extra, branched from rev3b, is what's checked out."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.clone = base / "clone"
        cls.bare = base / "origin.git"
        cls.clone.mkdir()
        build_clone(cls.clone, cls.bare)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def make_vault(self, tmp_path, claude_md):
        vault = Path(tmp_path) / "Vault"
        for d in ("projects", "areas", "archive", "triage", "resources"):
            (vault / d).mkdir(parents=True)
        write(vault, "CLAUDE.md", claude_md)
        return vault

    def rev(self, tag):
        return subprocess.run(["git", "rev-parse", tag], cwd=self.clone, check=True,
                              capture_output=True, text=True).stdout.strip()

    @contextlib.contextmanager
    def on_main(self):
        """The fixture's checked-out HEAD is feat/extra (deliberately, so baseline tests
        prove they read the named ref rather than HEAD). A test that needs to add a
        throwaway commit reachable from "main" has to check it out first, and back to
        feat/extra after, or the commit lands on the wrong branch."""
        fixture_git(self.clone, "checkout", "-q", "main")
        try:
            yield
        finally:
            fixture_git(self.clone, "checkout", "-q", "feat/extra")


FIGURES_RULE = "---\npaths:\n  - areas/**/README.md\n  - projects/*/brief.md\n---\nFigures.\n"
HELPER_SOURCE = "def helper():\n    return 1\n"
ACTIVITY_SOURCE = "# para-os-integration: activity 2026.09.01\nLEDGER = 1\n"


def build_layout_clone(root):
    """A second throwaway clone for what the widget fixture never ships: base rule, settings
    and folder-placeholder files, rules and skills in two modules (sales, estate), a module
    shipping a pipeline script and a skill with no integrations/ folder (activity), the
    para-shared library, an unmarked integration helper, a one-script and a two-script
    integration folder, and a branch (never checked out) carrying a skill main lacks.
    """
    fixture_git(root, "init", "-q", "-b", "main")
    fixture_git(root, "config", "core.autocrlf", "false")
    fixture_git(root, "config", "core.excludesFile", str(root / ".git" / "no-excludes"))

    write(root, "CHANGELOG.md", CHANGELOG_TEXT)
    write(root, "base/CLAUDE.md.template", fixture_template("2026.09.01"))
    write(root, "base/bootstrap-prompt.md", "# Bootstrap\n")
    write(root, "base/README.md.template", "# Vault\n")
    write(root, "base/projects/README.md", "# Projects\n")
    write(root, "base/triage/.gitkeep", "")
    write(root, "base/.claude/settings.json",
          json.dumps({"autoMemoryEnabled": False, "theme": "dark"}))
    write(root, "base/.claude/rules/figures.md", FIGURES_RULE)
    write(root, "base/.claude/rules/shared-name.md", "---\npaths:\n  - projects/**\n---\nBase.\n")
    write(root, "base/.claude/skills/base-skill/SKILL.md", "---\nname: base-skill\n---\n# Base\n")
    write(root, "base/.claude/skills/shared-skill/SKILL.md",
          "---\nname: shared-skill\n---\n# Base copy\n")
    write(root, "base/.claude/skills/para-shared/scripts/lib.py", "LIB = 1\n")
    write(root, "addons/sales/.claude/rules/shared-name.md",
          "---\npaths:\n  - deals/**\n---\nSales.\n")
    write(root, "addons/sales/.claude/rules/deal-brief.md",
          "---\npaths:\n  - deals/*/brief.md\n---\nSales deal brief.\n")
    write(root, "addons/sales/skeleton/resources/deals/README.md", "# Deals\n")
    write(root, "addons/sales/.claude/skills/deal-skill/SKILL.md",
          "---\nname: deal-skill\n---\n# Deals\n")
    write(root, "addons/sales/.claude/skills/shared-skill/SKILL.md",
          "---\nname: shared-skill\n---\n# Sales copy\n")
    write(root, "addons/estate/.claude/rules/deal-brief.md",
          "---\npaths:\n  - properties/*/brief.md\n---\nEstate deal brief.\n")
    write(root, "addons/estate/skeleton/resources/properties/README.md", "# Properties\n")
    write(root, "addons/activity/pipeline/activity.py", ACTIVITY_SOURCE)
    write(root, "addons/activity/pipeline/test_activity.py", "# tests for activity\n")
    write(root, "addons/activity/.claude/skills/ledger-review/SKILL.md",
          "---\nname: ledger-review\n---\n# Ledger review\n")
    write(root, "integrations/helpers/common.py", HELPER_SOURCE)
    write(root, "integrations/helpers/test_common.py", "# tests for common\n")
    write(root, "integrations/pair/a.py", "# para-os-integration: pair 2026.09.01\nA = 1\n")
    write(root, "integrations/pair/b.py", "# para-os-integration: pair 2026.09.01\nB = 2\n")
    write(root, "integrations/solo/solo.py", "# para-os-integration: solo 2026.09.01\nSOLO = 1\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "layout")

    fixture_git(root, "checkout", "-q", "-b", "feat/new-skill")
    write(root, "base/.claude/skills/new-skill/SKILL.md", "---\nname: new-skill\n---\n# New\n")
    write(root, "base/.claude/skills/base-skill/notes.md", "Branch-only notes.\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "new skill on a branch")
    fixture_git(root, "checkout", "-q", "main")


class LayoutCase(unittest.TestCase):
    """The layout clone, built once per class: main is checked out, feat/new-skill is not."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.clone = Path(cls._tmp.name) / "layout"
        cls.clone.mkdir()
        build_layout_clone(cls.clone)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def tmp_vault(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        vault = Path(tmp.name).resolve() / "Vault"
        for d in ("projects", "areas", "archive", "triage", "resources"):
            (vault / d).mkdir(parents=True)
        write(vault, "CLAUDE.md", fixture_template("2026.09.01"))
        return vault

    def addons(self, **decl):
        """A declarations dict and the masters block's addon rows for it, at main."""
        decl = dict({"flavor": None, "modules": []}, **decl)
        return decl, masters_block(self.clone, "main", False, decl)["addons"]


# ============================================================== compute_verdict (rules 1-5)

class ComputeVerdictCase(unittest.TestCase):

    def test_identical_bytes_win_rule_1(self):
        got = compute_verdict(b"same\n", b"same\n", [], [], None, "2026.09.01", False)
        self.assertEqual(got["verdict"], "identical")

    def test_crlf_and_bom_only_drift_reads_identical(self):
        master = b"line one\nline two\n"
        copy = b"\xef\xbb\xbfline one\r\nline two\r\n"
        got = compute_verdict(copy, master, [], [], None, "2026.09.01", False)
        self.assertEqual(got["verdict"], "identical")

    def test_behind_matches_an_older_history_entry(self):
        history = [{"commit": "tip", "revision": "2026.09.01", "bytes": b"new\n"},
                   {"commit": "old", "revision": "2026.08.02", "bytes": b"old\n"}]
        got = compute_verdict(b"old\n", b"new\n", history, [], None, "2026.09.01", False)
        self.assertEqual(got["verdict"], "behind")
        self.assertEqual(got["commit"], "old")
        self.assertFalse(got["within_revision"])

    def test_behind_within_revision_when_the_old_entry_shares_the_master_s_revision(self):
        history = [{"commit": "tip", "revision": "2026.09.01", "bytes": b"new\n"},
                   {"commit": "fix", "revision": "2026.09.01", "bytes": b"mid\n"}]
        got = compute_verdict(b"mid\n", b"new\n", history, [], None, "2026.09.01", False)
        self.assertEqual(got["verdict"], "behind")
        self.assertTrue(got["within_revision"])

    def test_under_worktree_a_copy_of_the_committed_tip_is_behind_the_edited_master(self):
        # --worktree reads the master from disk, so H[0] (the committed tip) is not M.
        history = [{"commit": "tip", "revision": "2026.09.01", "bytes": b"committed\n"},
                   {"commit": "old", "revision": "2026.08.02", "bytes": b"old\n"}]
        other = [{"source": "feat/extra", "bytes": b"committed\n"}]
        got = compute_verdict(b"committed\n", b"edited in the worktree\n", history, other,
                              None, "2026.09.01", False)
        self.assertEqual(got["verdict"], "behind")
        self.assertEqual(got["commit"], "tip")

    def test_ahead_when_the_copy_matches_another_source(self):
        other = [{"source": "feat/extra", "bytes": b"feature copy\n"}]
        got = compute_verdict(b"feature copy\n", b"master\n", [], other, None, "x", False)
        self.assertEqual(got, {"verdict": "ahead", "source": "feat/extra"})

    def test_hand_bumped_marker_matches_content_differs(self):
        # copy's own marker equals the master's; its content matches an OLD revision's code.
        history = [
            {"commit": "tip", "revision": "2026.09.01",
             "bytes": b"# para-os-integration: widget 2026.09.01\nV3\n"},
            {"commit": "old", "revision": "2026.08.02",
             "bytes": b"# para-os-integration: widget 2026.08.02\nV2\n"},
        ]
        copy = b"# para-os-integration: widget 2026.09.01\nV2\n"  # hand-bumped header, old code
        got = compute_verdict(copy, history[0]["bytes"], history, [], "2026.09.01",
                              "2026.09.01", True)
        self.assertEqual(got["verdict"], "marker-matches-content-differs")
        self.assertEqual(got["case"], "hand-bumped")
        self.assertEqual(got["revision"], "2026.08.02")

    def test_behind_with_marker_edited_when_the_copy_s_marker_matches_neither(self):
        history = [
            {"commit": "tip", "revision": "2026.09.01",
             "bytes": b"# para-os-integration: widget 2026.09.01\nV3\n"},
            {"commit": "old", "revision": "2026.08.02",
             "bytes": b"# para-os-integration: widget 2026.08.02\nV2\n"},
        ]
        copy = b"# para-os-integration: widget 2026.08.01\nV2\n"  # neither marker
        got = compute_verdict(copy, history[0]["bytes"], history, [], "2026.08.01",
                              "2026.09.01", True)
        self.assertEqual(got["verdict"], "behind")
        self.assertEqual(got["commit"], "old")
        self.assertTrue(got["marker_edited"])

    def test_within_revision_rule_2_wins_before_the_marker_rules_are_even_tried(self):
        # C equals H[i]'s bytes EXACTLY (marker included), so rule 2 must fire, not rule 4.
        history = [
            {"commit": "tip", "revision": "2026.09.01",
             "bytes": b"# para-os-integration: widget 2026.09.01\nV3\n"},
            {"commit": "old", "revision": "2026.08.02",
             "bytes": b"# para-os-integration: widget 2026.08.02\nV2\n"},
        ]
        got = compute_verdict(history[1]["bytes"], history[0]["bytes"], history, [],
                              "2026.08.02", "2026.09.01", True)
        self.assertEqual(got["verdict"], "behind")
        self.assertNotIn("marker_edited", got)

    def test_rule_5_stays_fast_on_large_files_that_match_no_version(self):
        # A real vault's integration copy, a few thousand lines matching no version exactly,
        # hung the scan for minutes when rule 5 compared it character by character against
        # every version in H. Line-level first, it answers in well under a second each.
        import time
        base = [f"const value{i} = compute({i}, {i * 7});" for i in range(3000)]
        master = "\n".join(base).encode()
        history = []
        for k in range(12):
            version = list(base)
            for i in range(k, 3000, 97):
                version[i] = f"// revised in version {k}: " + version[i]
            history.append({"commit": f"c{k}", "revision": "2026.08.02",
                            "bytes": "\n".join(version).encode()})
        copy = list(base)
        for i in range(0, 3000, 50):
            copy[i] = copy[i] + "  // local edit"
        started = time.time()
        got = compute_verdict("\n".join(copy).encode(), master, history, [], None,
                              "2026.09.01", False)
        self.assertLess(time.time() - started, 10)
        self.assertEqual(got["verdict"], "ahead")  # closest to the master: only local edits

    def test_both_when_diverged_and_closer_to_an_old_version_than_the_master(self):
        master = b"alpha beta gamma delta epsilon\n"
        old = b"alpha beta gamma delta zzzzzzz\n"
        copy = b"alpha beta gamma delta zzzzzz!\n"  # one char off from `old`, far from master
        history = [{"commit": "old", "revision": "2026.08.02", "bytes": old}]
        got = compute_verdict(copy, master, history, [], None, "2026.09.01", False)
        self.assertEqual(got["verdict"], "both")
        self.assertEqual(got["closest"], "old")

    def test_marker_matches_content_differs_case_null_when_no_history_explains_it(self):
        master = b"# para-os-integration: widget 2026.09.01\nalpha beta gamma delta\n"
        copy = b"# para-os-integration: widget 2026.09.01\nalpha beta gamma ZETA!!\n"
        got = compute_verdict(copy, master, [], [], "2026.09.01", "2026.09.01", True)
        self.assertEqual(got["verdict"], "marker-matches-content-differs")
        self.assertIsNone(got["case"])

    def test_ahead_from_rule_5_when_closest_to_the_master_itself(self):
        master = b"alpha beta gamma delta epsilon zeta\n"
        copy = b"alpha beta gamma delta epsilon zetA\n"  # one char off master, no marker game
        got = compute_verdict(copy, master, [], [], None, "x", False)
        self.assertEqual(got["verdict"], "ahead")
        self.assertIsNone(got["source"])

    def test_a_history_entry_whose_blob_could_not_be_read_is_skipped(self):
        history = [{"commit": "lost", "revision": "2026.08.02", "bytes": None},
                   {"commit": "old", "revision": "2026.08.02",
                    "bytes": b"alpha beta gamma delta zzzzzzz\n"}]
        got = compute_verdict(b"alpha beta gamma delta zzzzzz!\n",
                              b"alpha beta gamma delta epsilon\n", history, [], None,
                              "2026.09.01", False)
        self.assertEqual(got, {"verdict": "both", "closest": "old"})


class MechanicalEquivalenceCase(unittest.TestCase):

    def test_history_match_is_the_strongest_proof(self):
        history = [{"commit": "old", "bytes": b"same\n"}]
        got = _mechanical_equivalence(b"same\n", b"different\n", history, is_python=False)
        self.assertEqual(got, {"eligible": True, "proof": "history-match", "proof_commit": "old"})

    def test_ast_equivalence_for_python_reformatted_only(self):
        old = b"def f( x ):\n    return   x+1\n"
        copy = b"def f(x):\n    return x + 1\n"
        history = [{"commit": "old", "bytes": old}]
        got = _mechanical_equivalence(copy, b"def f(x):\n    return x + 2\n", history,
                                      is_python=True)
        self.assertEqual(got["proof"], "ast")
        self.assertEqual(got["proof_commit"], "old")

    def test_ast_proof_strips_docstrings_first(self):
        # Code is byte-identical after the docstring; without stripping, ast.dump would
        # still differ on the Constant string value and this would fall through to
        # "whitespace" (which would also fail here, since the diff is not whitespace-only)
        # or report not eligible at all.
        old = b'def f(x):\n    """Old doc, fairly verbose about what f does."""\n    return x + 1\n'
        copy = b'def f(x):\n    """A completely different docstring for the same code."""\n    return x + 1\n'
        history = [{"commit": "old", "bytes": old}]
        got = _mechanical_equivalence(copy, b"def f(x):\n    return x + 2\n", history,
                                      is_python=True)
        self.assertEqual(got["proof"], "ast")
        self.assertEqual(got["proof_commit"], "old")

    def test_whitespace_only_is_the_last_resort(self):
        old = b"line one\r\nline two  \r\n"
        copy = b"line one\nline two\n"
        history = [{"commit": "old", "bytes": old}]
        got = _mechanical_equivalence(copy, b"unrelated\n", history, is_python=False)
        self.assertEqual(got["proof"], "whitespace")

    def test_genuine_drift_is_not_eligible(self):
        history = [{"commit": "old", "bytes": b"old content entirely\n"}]
        got = _mechanical_equivalence(b"new content entirely\n", b"master\n", history,
                                      is_python=False)
        self.assertFalse(got["eligible"])

    def test_a_python_copy_that_does_not_parse_can_still_prove_whitespace_equivalence(self):
        history = [{"commit": "lost", "bytes": None},
                   {"commit": "old", "bytes": b"def broken(:\n    pass\n"}]
        got = _mechanical_equivalence(b"def broken(:   \n    pass\n\n", b"master\n", history,
                                      is_python=True)
        self.assertEqual(got, {"eligible": True, "proof": "whitespace", "proof_commit": "old"})

    def test_unreadable_and_unparsable_versions_are_passed_over_on_the_way_to_an_ast_proof(self):
        history = [{"commit": "lost", "bytes": None},
                   {"commit": "broken", "bytes": b"def f(:\n"},
                   {"commit": "old", "bytes": b"def f( x ):\n    return   x+1\n"}]
        got = _mechanical_equivalence(b"def f(x):\n    return x + 1\n", b"master\n", history,
                                      is_python=True)
        self.assertEqual(got, {"eligible": True, "proof": "ast", "proof_commit": "old"})


# ============================================================================ small helpers

# ============================================== the efficiency fix: batched history reads

class ParseBatchOutputCase(unittest.TestCase):
    """No git needed - `git cat-file --batch`'s own framing, fed in by hand."""

    def test_a_found_blob_and_a_missing_one_in_one_call(self):
        blob = b"hello\nworld\n"
        sha = "0123456789abcdef0123456789abcdef01234567"
        data = f"{sha} blob {len(blob)}\n".encode() + blob + b"\n" + b"deadbeef missing\n"
        self.assertEqual(_parse_batch_output(data, 2), [blob, None])

    def test_a_tree_object_is_read_as_none_never_as_a_listing(self):
        listing = b"100644 blob abc\tfile.txt\n"
        sha = "fedcba9876543210fedcba9876543210fedcba98"
        data = f"{sha} tree {len(listing)}\n".encode() + listing + b"\n"
        self.assertEqual(_parse_batch_output(data, 1), [None])

    def test_order_is_preserved_even_when_two_requests_resolve_to_one_blob(self):
        blob = b"same content\n"
        sha = "1111111111111111111111111111111111111a"
        block = f"{sha} blob {len(blob)}\n".encode() + blob + b"\n"
        self.assertEqual(_parse_batch_output(block + block, 2), [blob, blob])

    def test_an_ambiguous_request_reads_as_none_and_the_next_result_still_lines_up(self):
        blob = b"after\n"
        sha = "2222222222222222222222222222222222222b"
        data = b"abc1 ambiguous\n" + f"{sha} blob {len(blob)}\n".encode() + blob + b"\n"
        self.assertEqual(_parse_batch_output(data, 2), [None, blob])


class EffectiveBlobCase(unittest.TestCase):
    """Which template blob was in effect at a commit. The index is newest first: 0 is the
    ref's tip."""

    INDEX = {"tip": 0, "mid": 1, "root": 2}
    HISTORY = [("tip", "tpl-tip"), ("mid", "tpl-mid")]

    def test_the_newest_template_change_at_or_before_the_commit_wins(self):
        self.assertEqual(_effective_blob("tip", self.HISTORY, self.INDEX), "tpl-tip")
        self.assertEqual(_effective_blob("mid", self.HISTORY, self.INDEX), "tpl-mid")

    def test_a_commit_older_than_every_template_change_has_none(self):
        self.assertIsNone(_effective_blob("root", self.HISTORY, self.INDEX))

    def test_a_commit_outside_the_ref_s_history_has_none(self):
        self.assertIsNone(_effective_blob("elsewhere", self.HISTORY, self.INDEX))


class HistoryBatchCase(CloneCase):
    """Against the real fixture clone: the raw-log parser, the effective-template lookup,
    and the batch's own two-phase (want, then resolve) discipline."""

    def test_root_history_map_lists_every_changing_commit_newest_first(self):
        history = _root_history_map(self.clone, "main", "integrations/widget")
        commits = [c for c, _ in history["integrations/widget/widget.py"]]
        self.assertEqual(commits, [self.rev("rev3b"), self.rev("rev3"), self.rev("rev2"),
                                   self.rev("rev1")])

    def test_past_the_cap_only_the_newest_versions_are_kept(self):
        with mock.patch.object(upgrade_scan, "HISTORY_LIMIT", 2):
            history = _root_history_map(self.clone, "main", "integrations/widget")
        commits = [c for c, _ in history["integrations/widget/widget.py"]]
        self.assertEqual(commits, [self.rev("rev3b"), self.rev("rev3")])

    def test_a_ref_that_does_not_resolve_has_no_history(self):
        self.assertEqual(_root_history_map(self.clone, "no-such-ref", "integrations"), {})

    def test_a_sweep_root_groups_every_skill_under_one_claude_skills_prefix(self):
        self.assertEqual(_sweep_root("base/.claude/skills/widget-skill"), "base/.claude/skills")
        self.assertEqual(_sweep_root("addons/sales/.claude/skills/deal-thing"),
                         "addons/sales/.claude/skills")
        self.assertEqual(_sweep_root("integrations/widget"), "integrations/widget")

    def test_effective_blob_is_the_newest_template_at_or_before_the_commit(self):
        order = _global_commit_order(self.clone, "main")
        index = {c: i for i, c in enumerate(order)}
        tpl_history = _root_history_map(self.clone, "main", "base/CLAUDE.md.template") \
            ["base/CLAUDE.md.template"]
        blob = _effective_blob(self.rev("rev2"), tpl_history, index)
        content = subprocess.run(["git", "cat-file", "blob", blob], cwd=self.clone, check=True,
                                 capture_output=True).stdout
        self.assertIn(b"2026.08.02", content)

    def test_resolve_is_safe_to_call_more_than_once(self):
        batch = HistoryBatch(self.clone, "main", False)
        path = "base/CLAUDE.md.template"
        batch.want_ref_path("main", path)
        batch.resolve()
        self.assertIn(b"2026.09.01", batch.ref_path("main", path))
        # Gathering more after the first resolve() (a second stage's wants) still resolves.
        batch.want_ref_path("rev1", path)
        batch.resolve()
        self.assertIn(b"2026.08", batch.ref_path("rev1", path))

    def test_a_renamed_file_is_keyed_by_its_own_path_not_the_rename_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture_git(repo, "init", "-q")
            write_bytes(repo, "skills/x/old.md", b"same content\n" * 20)
            fixture_git(repo, "add", "-A")
            fixture_git(repo, "commit", "-q", "-m", "add")
            fixture_git(repo, "mv", "skills/x/old.md", "skills/x/new.md")
            fixture_git(repo, "commit", "-q", "-m", "rename")
            history = _root_history_map(repo, "HEAD", "skills")
        self.assertEqual(sorted(history), ["skills/x/new.md", "skills/x/old.md"])

    def test_want_blob_and_blob_round_trip(self):
        batch = HistoryBatch(self.clone, "main", False)
        history = _root_history_map(self.clone, "main", "integrations/widget")
        entries = history["integrations/widget/widget.py"]
        for _, sha in entries:
            batch.want_blob(sha)
        batch.resolve()
        for commit, sha in entries:
            self.assertIsNotNone(batch.blob(sha))


# =============================================================================== vault block

def git_vault(tmp):
    """A vault that is its own git repository: CLAUDE.md and one rule committed, and a
    .gitignore that ignores the machine-local settings file."""
    vault = Path(tmp).resolve() / "Vault"
    for d in ("projects", "areas"):
        (vault / d).mkdir(parents=True)
    write(vault, "CLAUDE.md", fixture_template("2026.09.01"))
    write(vault, ".claude/rules/filing.md", "---\npaths:\n  - triage/**\n---\nA rule.\n")
    write(vault, ".gitignore", ".claude/settings.local.json\n")
    fixture_git(vault, "init", "-q")
    fixture_git(vault, "config", "core.autocrlf", "false")
    fixture_git(vault, "config", "core.excludesFile", str(vault / ".git" / "no-excludes"))
    fixture_git(vault, "add", "-A")
    fixture_git(vault, "commit", "-q", "--no-verify", "-m", "vault")
    return vault


class ScopeFilesCase(unittest.TestCase):
    """Precondition 5's scope: CLAUDE.md and every file under .claude/, nothing else."""

    def test_the_scope_is_claude_md_and_every_file_under_dot_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            write(vault, "CLAUDE.md", "# Vault\n")
            write(vault, ".claude/settings.json", "{}")
            write(vault, ".claude/skills/x/scripts/run.py", "print(1)\n")
            write(vault, "README.md", "# Not in scope\n")
            write(vault, "projects/alpha/brief.md", "# Not in scope\n")
            (vault / ".claude" / "empty-folder").mkdir()
            self.assertEqual(_scope_files(vault), ["CLAUDE.md", ".claude/settings.json",
                                                   ".claude/skills/x/scripts/run.py"])

    def test_a_folder_with_neither_has_an_empty_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp), "README.md", "# Vault\n")
            self.assertEqual(_scope_files(Path(tmp)), [])


class IgnoredInScopeCase(unittest.TestCase):

    def test_names_only_the_scope_files_git_ignores(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = git_vault(tmp)
            write(vault, ".claude/settings.local.json", "{}")
            got = _ignored_in_scope(vault, ["CLAUDE.md", ".claude/rules/filing.md",
                                            ".claude/settings.local.json"])
        self.assertEqual(got, [".claude/settings.local.json"])

    def test_outside_a_git_repository_nothing_is_reported_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp), "CLAUDE.md", "# Vault\n")
            self.assertEqual(_ignored_in_scope(Path(tmp), ["CLAUDE.md"]), [])

    def test_an_empty_scope_never_runs_git(self):
        with mock.patch.object(upgrade_scan, "_git_raw") as raw:
            self.assertEqual(_ignored_in_scope(Path("unused"), []), [])
        raw.assert_not_called()


class VaultBlockCase(unittest.TestCase):

    def test_a_git_vault_reports_dirty_untracked_and_ignored_files_in_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = git_vault(tmp)
            write(vault, "CLAUDE.md", fixture_template("2026.09.01") + "Local edit.\n")
            write(vault, ".claude/rules/new-rule.md", "---\npaths:\n  - x\n---\nNew.\n")
            write(vault, ".claude/settings.local.json", "{}")
            write(vault, "projects/alpha/brief.md", "# Alpha\n")  # untracked, out of scope
            got = vault_block(vault, [])
        self.assertTrue(got["root"])
        self.assertTrue(got["git"]["repo"])
        self.assertIn("CLAUDE.md", got["git"]["dirty"])
        self.assertEqual(got["git"]["untracked_in_scope"], [".claude/rules/new-rule.md"])
        self.assertEqual(got["git"]["ignored_in_scope"], [".claude/settings.local.json"])

    def test_outside_git_the_scope_lists_are_empty_and_repo_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "Vault"
            for d in ("projects", "areas"):
                (vault / d).mkdir(parents=True)
            write(vault, "CLAUDE.md", "# Vault\n")
            write(vault, ".claude/rules/x.md", "rule\n")
            got = vault_block(vault, [])
        self.assertEqual(got["git"], {"repo": False, "dirty": [], "untracked_in_scope": [],
                                      "ignored_in_scope": []})

    def test_claude_md_lines_counts_newlines_the_way_wc_l_does(self):
        # A last line with no newline is not counted, so the number matches `wc -l`.
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            write_bytes(vault, "CLAUDE.md", b"# Vault\n\nlast line, no newline")
            self.assertEqual(vault_block(vault, [])["claude_md_lines"], 2)

    def test_a_folder_the_registry_holds_is_named_in_the_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp).resolve() / "Work"
            (vault / "projects").mkdir(parents=True)
            entries = [{"name": "Other", "path": str(Path(tmp).resolve() / "Elsewhere")},
                       {"name": "Work", "path": str(vault)}]
            got = vault_block(vault / "projects", entries)
        self.assertFalse(got["root"])
        self.assertIn("CLAUDE.md", got["missing"])
        self.assertEqual(got["hint"], {"name": "Work", "path": str(vault)})

    def test_a_folder_the_registry_does_not_hold_has_no_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "Work" / "projects").mkdir(parents=True)
            got = vault_block(root / "Work" / "projects",
                              [{"name": "Other", "path": str(root / "Elsewhere")}])
        self.assertIsNone(got["hint"])


# =============================================================================== clone block

class CloneBlockCase(CloneCase):

    def test_not_a_git_repository(self):
        with tempfile.TemporaryDirectory() as bare:
            block, ok, ref = clone_block(Path(bare), None, False)
            self.assertFalse(ok)
            self.assertIn("not a git repository", block["error"])

    def test_ref_resolves_and_checked_out_branch_is_reported(self):
        block, ok, ref = clone_block(self.clone, "main", False)
        self.assertTrue(ok)
        self.assertEqual(ref, "main")
        self.assertEqual(block["checked_out"]["branch"], "feat/extra")
        self.assertIsNotNone(block["ref_commit"])

    def test_a_ref_that_does_not_resolve_is_exit_4(self):
        block, ok, ref = clone_block(self.clone, "no-such-ref", False)
        self.assertFalse(ok)
        self.assertIn("does not resolve", block["error"])

    def test_the_default_ref_is_origin_stable_and_same_commit_groups_it(self):
        block, ok, ref = clone_block(self.clone, None, False)
        self.assertTrue(ok)
        self.assertEqual(ref, "origin/stable")
        self.assertIsNotNone(block["origin_stable"])
        self.assertEqual(block["origin_stable"]["commit"], block["ref_commit"])
        self.assertIn(["origin_stable", "ref"], block["same_commit"])
        self.assertFalse(block["stable_missing"])

    def test_a_clone_with_no_origin_stable_is_reported_for_the_one_time_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture_git(repo, "init", "-q", "-b", "main")
            write(repo, "CHANGELOG.md", CHANGELOG_TEXT)
            write(repo, "base/CLAUDE.md.template", fixture_template("2026.09.01"))
            fixture_git(repo, "add", "-A")
            fixture_git(repo, "commit", "-q", "--no-verify", "-m", "one")
            block, ok, ref = clone_block(repo, None, False)
            named, named_ok, _ = clone_block(repo, "main", False)
        self.assertFalse(ok)
        self.assertTrue(block["stable_missing"])
        self.assertEqual(ref, "origin/stable")
        self.assertTrue(named_ok)
        self.assertIsNone(named["origin_stable"])
        self.assertIsNone(named["ref_merged"])
        self.assertFalse(named["stable_missing"])

    def test_a_named_ref_that_does_not_resolve_is_never_the_stable_switch(self):
        for ref in ("origin/nope", "origin/stable"):
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                fixture_git(repo, "init", "-q", "-b", "main")
                write(repo, "CHANGELOG.md", CHANGELOG_TEXT)
                fixture_git(repo, "add", "-A")
                fixture_git(repo, "commit", "-q", "--no-verify", "-m", "one")
                block, ok, _ = clone_block(repo, ref, False)
            self.assertFalse(ok)
            self.assertFalse(block["stable_missing"], ref)

    def test_dirty_masters_narrows_dirty_to_the_files_a_run_reads_a_master_from(self):
        # A --test run found a dirty root README.md, no master, read as an uncommitted one.
        write(self.clone, "README.md", "# para-os\n")
        write(self.clone, "addons/sales/.claude/rules/deal-brief.md", "draft\n")
        write(self.clone, "addons/other/README.md", "# other\n")
        self.addCleanup(lambda: [__import__("shutil").rmtree(self.clone / d, ignore_errors=True)
                                 for d in ("addons/sales", "addons/other")])
        self.addCleanup(lambda: (self.clone / "README.md").unlink())
        block, ok, _ = clone_block(self.clone, "main", False, {"modules": ["sales"]})
        self.assertTrue(ok)
        self.assertIn("README.md", block["dirty"])
        self.assertEqual(block["dirty_masters"], ["addons/sales/"])

    def test_dirty_masters_reads_every_master_root_and_a_collapsed_untracked_folder(self):
        dirty = ["README.md", "CHANGELOG.md", "base/CLAUDE.md.template",
                 "integrations/widget/widget.py", "multi-vault/para-ingest/SKILL.md",
                 "flavors/real-estate/x.md", "addons/", "tools/x.py", "examples/y.md"]
        got = _dirty_masters(dirty, {"flavor": "real-estate", "modules": []})
        self.assertEqual(got, ["CHANGELOG.md", "base/CLAUDE.md.template",
                               "integrations/widget/widget.py",
                               "multi-vault/para-ingest/SKILL.md", "flavors/real-estate/x.md",
                               "addons/"])

    def test_worktree_reads_the_checked_out_branch_and_rejects_a_conflicting_ref(self):
        block, ok, ref = clone_block(self.clone, None, True)
        self.assertTrue(ok)
        self.assertEqual(ref, "feat/extra")
        block2, ok2, _ = clone_block(self.clone, "main", True)
        self.assertFalse(ok2)
        self.assertIn("--worktree", block2["error"])

    def test_ref_merged_says_whether_the_ref_is_already_on_origin_stable(self):
        merged, ok, _ = clone_block(self.clone, "rev2", False)
        self.assertTrue(ok)
        self.assertTrue(merged["ref_merged"])
        unmerged, ok, _ = clone_block(self.clone, "feat/extra", False)
        self.assertTrue(ok)
        self.assertFalse(unmerged["ref_merged"])

    def test_worktree_on_a_detached_head_has_no_branch_to_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture_git(repo, "init", "-q", "-b", "main")
            write(repo, "CHANGELOG.md", CHANGELOG_TEXT)
            write(repo, "base/CLAUDE.md.template", fixture_template("2026.09.01"))
            fixture_git(repo, "add", "-A")
            fixture_git(repo, "commit", "-q", "--no-verify", "-m", "one")
            fixture_git(repo, "checkout", "-q", "--detach")
            block, ok, _ = clone_block(repo, None, True)
            named, named_ok, _ = clone_block(repo, "main", True)
        self.assertFalse(ok)
        self.assertIsNone(block["checked_out"]["branch"])
        self.assertIn("detached HEAD", block["error"])
        self.assertFalse(named_ok)
        self.assertIn("a detached HEAD", named["error"])


# ================================================================================== masters

class MastersBlockCase(CloneCase):

    def test_an_undeclared_module_with_no_folder_is_carried_forward_only_when_addons_missing(self):
        decl = {"flavor": None, "modules": ["no-such-module"]}
        got = masters_block(self.clone, "main", False, decl)
        row = got["addons"][0]
        self.assertIsNone(row["root"])
        self.assertIn("reported", row)  # addons/ DOES exist at this ref, so it is reported...
        self.assertNotIn("carried_forward", row)   # ...never carried_forward


class OlderLayoutMastersCase(unittest.TestCase):
    """A ref from before addons/ existed: a flavor under flavors/, and no folder a module
    could live in at all."""

    def test_each_addon_resolves_under_the_layout_the_ref_carries(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture_git(repo, "init", "-q", "-b", "main")
            write(repo, "base/CLAUDE.md.template", fixture_template("2026.08.02"))
            write(repo, "flavors/real-estate/.claude/rules/property.md", "A rule.\n")
            fixture_git(repo, "add", "-A")
            fixture_git(repo, "commit", "-q", "--no-verify", "-m", "older layout")
            got = masters_block(repo, "main", False, {"flavor": "real-estate",
                                                      "modules": ["sales"]})
            gone = masters_block(repo, "main", False, {"flavor": "gone", "modules": []})
        rows = {r["name"]: r for r in got["addons"]}
        self.assertEqual(got["template"]["path"], "base/CLAUDE.md.template")
        self.assertEqual(rows["real-estate"],
                         {"name": "real-estate", "kind": "flavor", "root": "flavors/real-estate"})
        # A module is carried forward; a flavor with no folder is reported, never carried.
        self.assertEqual(rows["sales"], {"name": "sales", "kind": "module", "root": None,
                                         "carried_forward": True})
        self.assertIn("reported", gone["addons"][0])
        self.assertNotIn("carried_forward", gone["addons"][0])


# ==================================================================================== delta

class DeltaBlockCase(CloneCase):

    def test_legacy_marker_reads_normalised_and_excludes_its_own_entry(self):
        vault = self.make_vault(self._tmpdir(), fixture_template("2026.08"))
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["vault_marker"], "2026.08.01")
        self.assertTrue(delta["legacy"])
        revisions = [e["revision"] for e in delta["entries"]]
        self.assertNotIn("2026.08.01", revisions)
        self.assertIn("2026.08.02", revisions)
        self.assertIn("2026.09.01", revisions)

    def test_equal_marker_reports_the_current_entry_and_no_others(self):
        vault = self.make_vault(self._tmpdir(), fixture_template("2026.09.01"))
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["verdict"], "equal")
        self.assertEqual(delta["entries"], [])
        self.assertEqual(delta["current"]["revision"], "2026.09.01")

    def test_ahead_marker_never_downgrades(self):
        vault = self.make_vault(self._tmpdir(), fixture_template("2099.01.01"))
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["verdict"], "ahead")
        self.assertEqual(delta["entries"], [])

    def test_no_marker_collects_every_entry(self):
        vault = self.make_vault(self._tmpdir(), "# Vault\n\nNo marker at all.\n")
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["verdict"], "no-marker")
        self.assertEqual({e["revision"] for e in delta["entries"]},
                         {"2026.08.01", "2026.08.02", "2026.09.01"})

    def test_a_master_with_no_marker_is_unverified_never_read_as_the_vault_s_problem(self):
        vault = self.make_vault(self._tmpdir(), fixture_template("2026.08.02"))
        template = {"path": "base/CLAUDE.md.template", "marker": None, "raw_marker": None,
                    "source": "base", "fallback": None}
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["verdict"], "unverified")
        self.assertEqual(delta["vault_marker"], "2026.08.02")
        self.assertEqual(delta["entries"], [])
        self.assertNotIn("current", delta)

    def _tmpdir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


# ================================================================================= baseline

class BaselineBlockCase(CloneCase):

    def test_ref_tip_case(self):
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = {"vault_marker": "2026.09.01", "vault_marker_raw": "2026.09.01"}
        got = baseline_block(self.clone, "main", delta, template)
        self.assertEqual(got["source"], "ref-tip")

    def test_log_s_case_finds_the_parent_of_the_change_commit(self):
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = {"vault_marker": "2026.08.02", "vault_marker_raw": "2026.08.02"}
        got = baseline_block(self.clone, "main", delta, template)
        self.assertEqual(got["source"], "log-S")
        rev2 = subprocess.run(["git", "rev-parse", "rev2"], cwd=self.clone, check=True,
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(got["commit"], rev2)

    def test_the_raw_marker_search_never_matches_by_substring(self):
        # 2026.08 (raw legacy) must not match the 2026.08.02 template via a bare substring
        # search - it needs the comment delimiters. Confirmed by finding the RIGHT commit:
        # the boundary between the legacy label and 2026.08.02, i.e. rev1's own commit.
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = {"vault_marker": "2026.08.01", "vault_marker_raw": "2026.08"}
        got = baseline_block(self.clone, "main", delta, template)
        rev1 = subprocess.run(["git", "rev-parse", "rev1"], cwd=self.clone, check=True,
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(got["commit"], rev1)

    def test_walks_the_named_ref_not_the_checked_out_head(self):
        # HEAD (checked out) is feat/extra, which never touches base/CLAUDE.md.template beyond
        # what it inherited from main - passing ref="main" explicitly must still resolve
        # against main's own history, not silently against whatever HEAD happens to be.
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = {"vault_marker": "2026.08.02", "vault_marker_raw": "2026.08.02"}
        got_main = baseline_block(self.clone, "main", delta, template)
        got_feat = baseline_block(self.clone, "feat/extra", delta, template)
        self.assertEqual(got_main["commit"], got_feat["commit"])  # feat/extra branched from main
        self.assertEqual(got_main["source"], "log-S")

    def test_no_marker_at_all(self):
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = {"vault_marker": None, "vault_marker_raw": None}
        got = baseline_block(self.clone, "main", delta, template)
        self.assertIsNone(got["commit"])
        self.assertIsNone(got["source"])

    def test_no_master_template_at_the_ref_means_no_baseline(self):
        delta = {"vault_marker": "2026.08.02", "vault_marker_raw": "2026.08.02"}
        got = baseline_block(self.clone, "main", delta, {"path": None, "marker": None})
        self.assertIsNone(got["commit"])
        self.assertIn("no master template", got["reason"])

    def test_a_marker_no_commit_along_the_ref_ever_carried_has_no_baseline(self):
        template = masters_block(self.clone, "main", False, {})["template"]
        delta = {"vault_marker": "2026.07.01", "vault_marker_raw": "2026.07.01"}
        got = baseline_block(self.clone, "main", delta, template)
        self.assertIsNone(got["commit"])
        self.assertIsNone(got["source"])
        self.assertIn("<!-- para-os-template: 2026.07.01 -->", got["reason"])


# ================================================================================ skeleton

class SkeletonBlockCase(CloneCase):

    def test_bootstrap_prompt_and_skills_and_own_template_are_excluded(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        rows = skeleton_block(vault, self.clone, "main", False, [])
        paths = {r["vault_path"] for r in rows["rows"]}
        self.assertNotIn("bootstrap-prompt.md", paths)
        self.assertNotIn("CLAUDE.md.template", paths)
        self.assertFalse(any(p.startswith(".claude/skills/") for p in paths))

    def test_readme_template_maps_to_plain_readme(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        rows = skeleton_block(vault, self.clone, "main", False, [])
        paths = {r["vault_path"]: r for r in rows["rows"]}
        self.assertIn("README.md", paths)
        self.assertNotIn("README.md.template", paths)

    def test_crlf_and_bom_only_copy_reads_identical(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        master_bytes = clone_read(self.clone, "main", "base/README.md.template")
        from paraos_vault import normalised as _norm  # canonical LF form, whatever this
        canonical = _norm(master_bytes)               # platform's own write() produced
        write_bytes(vault, "README.md", b"\xef\xbb\xbf" + canonical.replace(b"\n", b"\r\n"))
        rows = skeleton_block(vault, self.clone, "main", False, [])
        readme_row = next(r for r in rows["rows"] if r["vault_path"] == "README.md")
        self.assertTrue(readme_row["present"])
        self.assertTrue(readme_row["identical"])


class LayoutSkeletonCase(LayoutCase):

    def rows(self, vault, **decl):
        decl, addons = self.addons(**decl)
        block = skeleton_block(vault, self.clone, "main", False, addons)
        return {r["vault_path"]: r for r in block["rows"]}, block

    def test_base_ships_its_rules_settings_and_folder_placeholders_as_skeleton_files(self):
        rows, _ = self.rows(self.tmp_vault())
        self.assertEqual(sorted(rows), [".claude/rules/figures.md", ".claude/rules/shared-name.md",
                                        ".claude/settings.json", "README.md",
                                        "projects/README.md", "triage/.gitkeep"])
        self.assertEqual(rows["README.md"]["master"], "base/README.md.template")
        self.assertEqual(rows[".claude/rules/figures.md"]["master"],
                         "base/.claude/rules/figures.md")
        self.assertFalse(rows["projects/README.md"]["present"])
        self.assertIsNone(rows["projects/README.md"]["identical"])

    def test_a_present_file_that_drifted_reads_not_identical(self):
        vault = self.tmp_vault()
        write(vault, ".claude/rules/figures.md", FIGURES_RULE + "A local line.\n")
        rows, _ = self.rows(vault)
        self.assertTrue(rows[".claude/rules/figures.md"]["present"])
        self.assertFalse(rows[".claude/rules/figures.md"]["identical"])

    def test_a_declared_module_adds_its_rules_and_skeleton_and_an_undeclared_one_nothing(self):
        rows, _ = self.rows(self.tmp_vault(), modules=["sales"])
        self.assertEqual(rows[".claude/rules/deal-brief.md"]["master"],
                         "addons/sales/.claude/rules/deal-brief.md")
        self.assertEqual(rows["resources/deals/README.md"]["master"],
                         "addons/sales/skeleton/resources/deals/README.md")
        self.assertNotIn("resources/properties/README.md", rows)

    def test_folder_has_content_says_whether_a_placeholder_s_folder_holds_anything_else(self):
        # A placeholder that says to delete it once content lands is satisfied by a folder
        # that already has content.
        vault = self.tmp_vault()
        write(vault, "projects/alpha/brief.md", "# Alpha\n")
        write(vault, "triage/.gitkeep", "")
        rows, _ = self.rows(vault, modules=["sales"])
        self.assertTrue(rows["projects/README.md"]["folder_has_content"])
        self.assertFalse(rows["triage/.gitkeep"]["folder_has_content"])
        self.assertIsNone(rows["resources/deals/README.md"]["folder_has_content"])  # no folder
        self.assertIsNone(rows[".claude/settings.json"]["folder_has_content"])  # not a placeholder

    def test_an_old_skeleton_s_triage_readme_is_reported(self):
        vault = self.tmp_vault()
        _, block = self.rows(vault)
        self.assertFalse(block["triage_readme"])
        write(vault, "triage/README.md", "# Triage\n")
        _, block = self.rows(vault)
        self.assertTrue(block["triage_readme"])


# =================================================================================== rules

class RulesBlockCase(CloneCase):

    def test_a_shape_rule_the_vault_lacks_has_master_paths_but_none_of_its_own(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, ".claude/rules/widget-shape.md",
              "---\npaths:\n  - projects/*/widget.md\n---\n**Order:** a\n\n"
              "## The shape\n\nbody\n\n## Placeholders\n\nnone\n")
        rows = rules_block(vault, self.clone, "main", False, [])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row["master"])  # nothing named widget-shape.md ships from this clone
        self.assertEqual(row["kind"], "shape")
        self.assertEqual(row["paths"], ["projects/*/widget.md"])

    def test_with_no_master_the_paths_checks_are_null_not_every_path_extra(self):
        # A --test run found a vault-local brief-structure.md with every path under
        # paths_extra, which read as a failed paths check.
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, ".claude/rules/brief-structure.md",
              "---\npaths:\n  - projects/*/brief.md\n  - areas/*/brief.md\n---\nA rule.\n")
        rows = rules_block(vault, self.clone, "main", False, [])
        self.assertIsNone(rows[0]["master"])
        self.assertIsNone(rows[0]["paths_missing"])
        self.assertIsNone(rows[0]["paths_extra"])

    def test_pointer_wording_and_section_are_read_from_claude_md(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, ".claude/rules/filing.md", "---\npaths:\n  - triage/**\n---\nA rule.\n")
        write(vault, "CLAUDE.md",
              "# Vault\n\n## Filing and naming\n\nThe full convention is in "
              "[.claude/rules/filing.md](.claude/rules/filing.md), read before filing one.\n")
        rows = rules_block(vault, self.clone, "main", False, [])
        pointer = rows[0]["pointer"]
        self.assertTrue(pointer["present"])
        self.assertEqual(pointer["wording"], "convention")
        self.assertEqual(pointer["section"], "Filing and naming")

    def pointer_rows(self, claude_md, *names, master_texts=None):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        for name in names:
            write(vault, f".claude/rules/{name}", "---\npaths:\n  - projects/**\n---\nA.\n")
        write(vault, "CLAUDE.md", claude_md)
        return {Path(r["file"]).name: r["pointer"] for r in rules_block(
            vault, self.clone, "main", False, [],
            master_texts=master_texts)}

    def test_a_later_conforming_pointer_wins_over_an_earlier_passing_link(self):
        # The earlier link is itself an addon's own sentence: it conforms as `template`, and
        # still loses to the pointer proper.
        passing = ("A reason from the list in "
                   "[.claude/rules/deal-brief.md](.claude/rules/deal-brief.md).")
        rows = self.pointer_rows(
            f"# Vault\n\n## Deal lifecycle\n\n{passing}\n\n"
            "## Entity structures\n\nThe full shape is in "
            "[.claude/rules/deal-brief.md](.claude/rules/deal-brief.md), which loads.\n",
            "deal-brief.md", master_texts=[f"## Deal lifecycle\n\n{passing}\n"])
        self.assertEqual(rows["deal-brief.md"], {"present": True, "line": 9,
                                                 "section": "Entity structures", "wording": "shape"})

    def test_a_convention_pointer_with_its_list_before_is_in_conforms(self):
        rows = self.pointer_rows(
            "# Vault\n\n## Filing\n\nThe full convention (folder variants, machine exports) is in "
            "[.claude/rules/filing.md](.claude/rules/filing.md), which loads.\n", "filing.md")
        self.assertEqual(rows["filing.md"]["wording"], "convention")

    def test_a_moved_code_repos_list_is_a_convention_with_a_conforming_pointer(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, ".claude/rules/code-repos.md",
              "---\npaths:\n  - projects/**\n  - areas/**\n  - resources/ideas/**\n---\n"
              "# Code repos\n\n- `widget-api`: the API. Owned by "
              "[areas/platform](../../areas/platform/README.md).\n")
        write(vault, "CLAUDE.md",
              "# Vault\n\n## Code repos\n\nThe vault names the code repos it steers, and no repo "
              "names the vault back. The full convention (every repo, what it is, and where it "
              "lives in this vault) is in [.claude/rules/code-repos.md](.claude/rules/code-repos.md)"
              ", which loads on its own when a project, idea or area is read.\n")
        row = rules_block(vault, self.clone, "main", False, [])[0]
        self.assertEqual(row["kind"], "convention")
        self.assertEqual((row["pointer"]["section"], row["pointer"]["wording"]),
                         ("Code repos", "convention"))

    def test_the_template_s_own_sentence_conforms(self):
        sentence = ("How the operator likes to work is kept apart: it is in "
                    "[.claude/rules/prefs.md](.claude/rules/prefs.md), which loads on its own.")
        rows = self.pointer_rows(f"# Vault\n\n## Memory\n\nThe vault is the memory. {sentence}\n",
                                 "prefs.md", master_texts=[f"## Memory\n\nOther text. {sentence}\n"])
        self.assertEqual(rows["prefs.md"]["wording"], "template")

    def test_a_link_nothing_states_is_still_other(self):
        rows = self.pointer_rows("# Vault\n\n## Memory\n\nSee [this](.claude/rules/prefs.md).\n",
                                 "prefs.md", master_texts=["## Memory\n\nNothing about it.\n"])
        self.assertEqual(rows["prefs.md"]["wording"], "other")

    def test_pointer_wording_tells_the_shape_sentence_from_any_other_link(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, ".claude/rules/briefs.md", "---\npaths:\n  - projects/*/brief.md\n---\nA.\n")
        write(vault, ".claude/rules/linked.md", "---\npaths:\n  - triage/**\n---\nB.\n")
        write(vault, ".claude/rules/unnamed.md", "---\npaths:\n  - areas/**\n---\nC.\n")
        write(vault, "CLAUDE.md",
              "# Vault\n\n## Briefs\n\nThe full shape is in "
              "[.claude/rules/briefs.md](.claude/rules/briefs.md).\n\n## Other\n\n"
              "See [the triage rule](.claude/rules/linked.md) for more.\n")
        rows = {Path(r["file"]).name: r["pointer"] for r in rules_block(
            vault, self.clone, "main", False, [])}
        self.assertEqual(rows["briefs.md"],
                         {"present": True, "line": 5, "section": "Briefs", "wording": "shape"})
        self.assertEqual(rows["linked.md"]["wording"], "other")
        self.assertEqual(rows["linked.md"]["section"], "Other")
        self.assertEqual(rows["unnamed.md"],
                         {"present": False, "line": None, "section": None, "wording": None})


def module_sections(rows_wording):
    return ("<!-- orders MODULE: merged beside base. -->\n\n## Order lifecycle\n\n"
            "Orders move by stage.\n\n"
            f"- **Rows before folders.** {rows_wording}\n\n"
            "## Entity structures\n\n- **Order brief** - the shape.\n")


class SectionsBlockCase(unittest.TestCase):
    """A module whose sections changed between two revisions: an early hand copy of the
    first wording is behind the module, never the vault's own variant."""

    V1 = "An order is a row until it ships."
    V2 = "An order is a row in `{{areas/business/orders.md}}` until it ships."

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.clone = Path(cls._tmp.name) / "clone"
        cls.clone.mkdir()
        root = cls.clone
        fixture_git(root, "init", "-q", "-b", "main")
        base = "# Vault\n\n<!-- para-os-template: {} -->\n\n## Entity structures\n\n- Base.\n"
        write(root, "base/CLAUDE.md.template", base.format("2026.09.01"))
        write(root, "addons/orders/CLAUDE.md.sections", module_sections(cls.V1))
        write(root, "addons/other/CLAUDE.md.sections", "## Other lifecycle\n\nOther.\n")
        fixture_git(root, "add", "-A")
        fixture_git(root, "commit", "-q", "--no-verify", "-m", "module before release")
        cls.first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                   capture_output=True, text=True).stdout.strip()
        write(root, "base/CLAUDE.md.template", base.format("2026.09.02"))
        write(root, "addons/orders/CLAUDE.md.sections", module_sections(cls.V2))
        fixture_git(root, "add", "-A")
        fixture_git(root, "commit", "-q", "--no-verify", "-m", "module released")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def scan(self, claude_md, decl, baseline=None):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp), "CLAUDE.md", claude_md)
            rows = sections_block(Path(tmp), self.clone, "main", False, decl, baseline)
        return {r["name"]: r for r in rows}

    def test_an_early_hand_copy_is_behind_the_module_not_a_local_variant(self):
        rows = self.scan("# Vault\n\n" + module_sections(self.V1), {})
        self.assertEqual(set(rows), {"orders"})
        self.assertFalse(rows["orders"]["declared"])
        lifecycle = rows["orders"]["sections"][0]
        self.assertEqual(lifecycle["verdict"], "behind")
        self.assertEqual(lifecycle["behind"],
                         [{"paragraph": f"- **Rows before folders.** {self.V1}",
                           "commit": self.first, "revision": "2026.09.01"}])
        self.assertEqual(lifecycle["local"], [])
        self.assertEqual(lifecycle["missing"], [f"- **Rows before folders.** {self.V2}"])

    def test_a_filled_placeholder_and_a_vault_addition_read_current(self):
        vault = module_sections(self.V2.replace("{{areas/business/orders.md}}",
                                                "areas/sales/orders.md"))
        vault = vault.replace("Orders move by stage.",
                              "Orders move by stage.\n\nOur own rule.")
        rows = self.scan("# Vault\n\n" + vault, {"modules": ["orders"]})
        lifecycle, entities = rows["orders"]["sections"]
        self.assertEqual((lifecycle["verdict"], lifecycle["local"]), ("current",
                                                                      ["Our own rule."]))
        self.assertEqual(entities["verdict"], "current")

    def test_a_localised_paragraph_pairs_with_the_shipped_one_rather_than_joining_it(self):
        shipped = f"- **Rows before folders.** {self.V2}"
        ours = ("- **Rows before folders at Acme.** An order is a row in "
                "`areas/sales/orders.md` until Acme ships it.")
        rows = self.scan("# Vault\n\n" + module_sections(self.V2).replace(shipped, ours),
                         {"modules": ["orders"]})
        lifecycle = rows["orders"]["sections"][0]
        self.assertEqual(lifecycle["localised"], [{"paragraph": ours, "shipped": shipped}])
        self.assertEqual((lifecycle["local"], lifecycle["missing"]), ([], []))
        self.assertEqual(lifecycle["verdict"], "current")

    def test_a_paragraph_of_the_vault_s_own_does_not_pair_with_a_missing_one(self):
        shipped = f"- **Rows before folders.** {self.V2}"
        rows = self.scan("# Vault\n\n" + module_sections(self.V2).replace(
            shipped, "- **Weekly call.** Every client gets a Friday call."),
            {"modules": ["orders"]})
        lifecycle = rows["orders"]["sections"][0]
        self.assertEqual(lifecycle["localised"], [])
        self.assertEqual(lifecycle["missing"], [shipped])
        self.assertEqual(lifecycle["verdict"], "differs")

    def test_only_a_missing_paragraph_the_addon_changed_since_the_baseline_is_new(self):
        vault = ("# Vault\n\n## Order lifecycle\n\nWe track each sale on one line.\n\n"
                 "## Entity structures\n\n- Our brief, condensed.\n")
        lifecycle, entities = self.scan(vault, {"modules": ["orders"]},
                                        self.first)["orders"]["sections"]
        self.assertEqual(lifecycle["missing"],
                         ["Orders move by stage.", f"- **Rows before folders.** {self.V2}"])
        self.assertEqual(lifecycle["missing_new"], [f"- **Rows before folders.** {self.V2}"])
        self.assertEqual(entities["missing_new"], [])
        lifecycle = self.scan(vault, {"modules": ["orders"]})["orders"]["sections"][0]
        self.assertIsNone(lifecycle["missing_new"])

    def test_an_undeclared_addon_is_reported_only_where_the_vault_states_a_paragraph_of_it(self):
        rows = self.scan("# Vault\n\n## Entity structures\n\n- Base.\n\n## Other lifecycle\n\n"
                         "Ours.\n", {})
        self.assertEqual(rows, {})
        rows = self.scan("# Vault\n", {"modules": ["orders"]})
        self.assertEqual([s["verdict"] for s in rows["orders"]["sections"]],
                         ["absent", "absent"])


class RuleMasterCase(LayoutCase):
    """Base first, then the flavor and each module in the order **Modules:**
    lists them; the first match wins."""

    def test_a_base_rule_is_its_own_master_and_its_paths_are_held_against_the_master_s(self):
        vault = self.tmp_vault()
        write(vault, ".claude/rules/figures.md",
              "---\npaths:\n  - areas/**/README.md\n  - resources/**/brief.md\n---\nLocal.\n")
        decl, addons = self.addons()
        row = rules_block(vault, self.clone, "main", False, addons)[0]
        self.assertEqual(row["master"], "base/.claude/rules/figures.md")
        self.assertEqual(row["master_paths"], ["areas/**/README.md", "projects/*/brief.md"])
        self.assertEqual(row["paths_missing"], ["projects/*/brief.md"])
        self.assertEqual(row["paths_extra"], ["resources/**/brief.md"])
        self.assertEqual(row["paths_retired"], [])

    def test_a_glob_doubled_for_the_retired_delivery_is_reported_for_removal(self):
        vault = self.tmp_vault()
        write(vault, ".claude/rules/figures.md",
              "---\npaths:\n  - areas/**/README.md\n  - projects/*/brief.md\n"
              "  - resources/mds/areas__*__README.md\n"
              "  - resources/mds/projects__*__brief.md\n---\nLocal.\n")
        _, addons = self.addons()
        row = rules_block(vault, self.clone, "main", False, addons)[0]
        self.assertEqual(row["paths_retired"], ["resources/mds/areas__*__README.md",
                                                "resources/mds/projects__*__brief.md"])
        self.assertEqual(row["paths"], ["areas/**/README.md", "projects/*/brief.md"])
        self.assertEqual((row["paths_missing"], row["paths_extra"]), ([], []))

    def test_base_is_tried_before_an_addon_carrying_the_same_name(self):
        _, addons = self.addons(modules=["sales"])
        path, data = _rule_master(self.clone, "main", False, "shared-name.md", addons)
        self.assertEqual(path, "base/.claude/rules/shared-name.md")
        self.assertIn(b"Base.", data)

    def test_a_module_rule_resolves_through_the_declared_module(self):
        _, addons = self.addons(modules=["sales"])
        path, _ = _rule_master(self.clone, "main", False, "deal-brief.md", addons)
        self.assertEqual(path, "addons/sales/.claude/rules/deal-brief.md")

    def test_modules_are_tried_in_the_order_the_vault_lists_them(self):
        _, estate_first = self.addons(modules=["estate", "sales"])
        _, sales_first = self.addons(modules=["sales", "estate"])
        self.assertEqual(_rule_master(self.clone, "main", False, "deal-brief.md", estate_first)[0],
                         "addons/estate/.claude/rules/deal-brief.md")
        self.assertEqual(_rule_master(self.clone, "main", False, "deal-brief.md", sales_first)[0],
                         "addons/sales/.claude/rules/deal-brief.md")

    def test_no_addon_rule_is_found_for_an_addon_the_vault_does_not_declare(self):
        _, none_declared = self.addons()
        _, folder_missing = self.addons(modules=["no-such-module"])
        for addons in (none_declared, folder_missing):
            self.assertEqual(_rule_master(self.clone, "main", False, "deal-brief.md", addons),
                             (None, None))


# ============================================================================== checkboxes

class CheckboxesBlockCase(unittest.TestCase):
    """The template's checkbox table against the vault's, read from a worktree master."""

    TABLE = ("### Where a checkbox may live\n\n| Bucket | `actions.md` | State |\n|---|---|---|\n"
             "| `projects/`, `areas/` | yes | open + closed |\n")
    ROW = "| `areas/network/` | yes | any action about the person |"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.clone, self.vault = Path(tmp.name) / "clone", Path(tmp.name) / "vault"
        write(self.clone, "base/CLAUDE.md.template", "# T\n\n" + self.TABLE + self.ROW + "\n")

    def test_a_vault_without_the_network_row_is_offered_it_at_its_current_level(self):
        write(self.vault, "CLAUDE.md", "# V\n\n" + self.TABLE)
        got = checkboxes_block(self.vault, self.clone, None, True)
        self.assertEqual(got["missing"], [{"bucket": "areas/network/", "row": self.ROW}])
        self.assertEqual(got["contact_card_level"], "yes")

    def test_a_roster_makes_the_missing_row_never(self):
        write(self.vault, "CLAUDE.md", "# V\n\n" + self.TABLE + "\n## Who writes this vault\n")
        self.assertEqual(checkboxes_block(self.vault, self.clone, None, True)
                         ["contact_card_level"], "never")

    def test_a_vault_that_declares_the_row_at_any_level_is_left_alone(self):
        write(self.vault, "CLAUDE.md", "# V\n\n" + self.TABLE
              + "| `areas/network/` | **never** | a checkbox on a card is a filing error |\n")
        got = checkboxes_block(self.vault, self.clone, None, True)
        self.assertEqual((got["missing"], got["contact_card_level"]), ([], "never"))


# ================================================================================ settings

class SettingsBlockCase(CloneCase):

    def test_missing_effective_when_neither_level_carries_the_key(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, "base/.claude/settings.json", "{}")  # not read; clone is the master
        with tempfile.TemporaryDirectory() as home, self.on_main():
            user_settings = Path(home) / "settings.json"
            write(self.clone, "base/.claude/settings.json",
                  json.dumps({"autoMemoryEnabled": False}))
            fixture_git(self.clone, "add", "base/.claude/settings.json")
            fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "settings")
            try:
                got = settings_block(vault, self.clone, "main", False, str(user_settings))
                self.assertIn("autoMemoryEnabled", got["missing_effective"])
                user_settings.write_bytes(json.dumps({"autoMemoryEnabled": False}).encode())
                got2 = settings_block(vault, self.clone, "main", False, str(user_settings))
                self.assertEqual(got2["missing_effective"], [])
                self.assertIn("autoMemoryEnabled", got2["user_level"]["matching"])
            finally:
                fixture_git(self.clone, "rm", "-q", "base/.claude/settings.json")
                fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "revert settings")


class LayoutSettingsCase(LayoutCase):
    """The layout master's settings: autoMemoryEnabled false, theme dark."""

    def test_a_key_the_vault_level_file_already_sets_is_not_missing(self):
        vault = self.tmp_vault()
        write(vault, ".claude/settings.json", json.dumps({"autoMemoryEnabled": False, "own": 1}))
        got = settings_block(vault, self.clone, "main", False, str(vault.parent / "absent.json"))
        self.assertEqual(got["master_keys"], {"autoMemoryEnabled": False, "theme": "dark"})
        self.assertEqual(got["vault_level"],
                         {"present": True, "keys": ["autoMemoryEnabled", "own"]})
        self.assertEqual(got["user_level"]["matching"], [])
        self.assertEqual(got["missing_effective"], ["theme"])

    def test_a_key_set_to_another_value_still_counts_as_missing(self):
        vault = self.tmp_vault()
        user = write(vault.parent, "user-settings.json",
                     json.dumps({"autoMemoryEnabled": True, "theme": "dark"}))
        got = settings_block(vault, self.clone, "main", False, str(user))
        self.assertEqual(got["user_level"]["matching"], ["theme"])
        self.assertEqual(got["missing_effective"], ["autoMemoryEnabled"])

    def test_an_unparseable_or_non_object_settings_file_holds_no_keys(self):
        vault = self.tmp_vault()
        user = write(vault.parent, "user-settings.json", "{not json")
        write(vault, ".claude/settings.json", "[1, 2]")
        got = settings_block(vault, self.clone, "main", False, str(user))
        self.assertEqual(got["vault_level"], {"present": True, "keys": []})
        self.assertEqual(got["missing_effective"], ["autoMemoryEnabled", "theme"])


# ============================================================================ integrations

class IntegrationMasterPathCase(CloneCase):

    def test_direct_path_resolves(self):
        path, special, candidates = _integration_master_path(
            self.clone, "main", False, "widget", "widget.py", [])
        self.assertEqual(path, "integrations/widget/widget.py")
        self.assertIsNone(special)

    def test_an_addon_script_resolves_through_the_addon_s_pipeline_folder(self):
        path, special, candidates = _integration_master_path(
            self.clone, "main", False, "gadget", "gadget.ps1", [])
        self.assertEqual(path, "addons/gadget/pipeline/gadget.ps1")
        self.assertIsNone(special)
        self.assertIsNone(candidates)

    def test_a_renamed_script_resolves_through_the_lone_survivor(self):
        with self.on_main():
            write(self.clone, "integrations/gizmo/gizmo.py",
                  "# para-os-integration: gizmo 2026.09.01\nX\n")
            fixture_git(self.clone, "add", "-A")
            fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "add gizmo")
            try:
                path, special, candidates = _integration_master_path(
                    self.clone, "main", False, "gizmo", "old_name.py", [])
                self.assertEqual(special, "renamed")
                self.assertEqual(path, "integrations/gizmo/gizmo.py")
            finally:
                fixture_git(self.clone, "rm", "-rq", "integrations/gizmo")
                fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "remove gizmo")

    def test_several_scripts_in_the_folder_is_ambiguous(self):
        with self.on_main():
            write(self.clone, "integrations/gizmo/a.py",
                  "# para-os-integration: gizmo 2026.09.01\nA\n")
            write(self.clone, "integrations/gizmo/b.py",
                  "# para-os-integration: gizmo 2026.09.01\nB\n")
            fixture_git(self.clone, "add", "-A")
            fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "add gizmo pair")
            try:
                path, special, candidates = _integration_master_path(
                    self.clone, "main", False, "gizmo", "old_name.py", [])
                self.assertEqual(special, "ambiguous-rename")
                self.assertEqual(set(candidates),
                                 {"integrations/gizmo/a.py", "integrations/gizmo/b.py"})
            finally:
                fixture_git(self.clone, "rm", "-rq", "integrations/gizmo")
                fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "remove gizmo pair")

    def test_no_folder_at_all_is_unresolvable(self):
        path, special, candidates = _integration_master_path(
            self.clone, "main", False, "no-such-integration", "x.py", [])
        self.assertEqual(special, "unresolvable")
        self.assertIsNone(path)


class IntegrationSuiteCase(CloneCase):

    def test_node_locator_with_a_template_fixture_and_an_uncovered_script(self):
        with self.on_main():
            write(self.clone, "integrations/gizmo/gizmo.mjs", "# gizmo\n")
            write(self.clone, "integrations/gizmo/helper.mjs", "# helper\n")
            write(self.clone, "integrations/gizmo/gizmo.test.mjs", "// test\n")
            write(self.clone, "integrations/gizmo/README.md", "# gizmo\n")
            write(self.clone, "integrations/gizmo/gizmo.config.json.template", "{}\n")
            write(self.clone, "integrations/gizmo/live.config.json", "{\"key\": \"secret\"}\n")
            fixture_git(self.clone, "add", "-A")
            fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "add gizmo node suite")
            try:
                got = _integration_suite(self.clone, "main", False, "integrations/gizmo")
                self.assertEqual(got["runner"], "node --test integrations/gizmo/gizmo.test.mjs")
                self.assertIn("integrations/gizmo/gizmo.config.json.template", got["fixtures"])
                self.assertNotIn("integrations/gizmo/live.config.json", got["fixtures"])
                self.assertNotIn("integrations/gizmo/README.md", got["fixtures"])
                self.assertIn("integrations/gizmo/gizmo.mjs", got["covers"])
                self.assertIn("integrations/gizmo/helper.mjs", got["uncovered"])
            finally:
                fixture_git(self.clone, "rm", "-rq", "integrations/gizmo")
                fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "remove gizmo suite")

    def test_the_node_runner_runs_every_test_file_not_only_the_first(self):
        # granola ships two suites; the runner named only granola-auth-init.test.js, while
        # covers listed granola.js as tested.
        with self.on_main():
            write(self.clone, "integrations/gizmo/gizmo-auth.js", "// auth\n")
            write(self.clone, "integrations/gizmo/gizmo-auth.test.js", "// test\n")
            write(self.clone, "integrations/gizmo/gizmo.js", "// gizmo\n")
            write(self.clone, "integrations/gizmo/gizmo.test.js", "// test\n")
            fixture_git(self.clone, "add", "-A")
            fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "add two node suites")
            try:
                got = _integration_suite(self.clone, "main", False, "integrations/gizmo")
                self.assertEqual(got["runner"], "node --test integrations/gizmo/gizmo-auth.test.js "
                                                "integrations/gizmo/gizmo.test.js")
                self.assertEqual(got["uncovered"], [])
            finally:
                fixture_git(self.clone, "rm", "-rq", "integrations/gizmo")
                fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "remove gizmo suites")


    def test_covers_strips_only_the_test_prefix_and_suffix(self):
        with self.on_main():
            write(self.clone, "integrations/syncer/latest_sync.py", "# sync\n")
            write(self.clone, "integrations/syncer/test_latest_sync.py", "# tests\n")
            write(self.clone, "integrations/syncer/contest_feed.mjs", "// feed\n")
            write(self.clone, "integrations/syncer/contest_feed.test.mjs", "// test\n")
            fixture_git(self.clone, "add", "-A")
            fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "add syncer suite")
            try:
                got = _integration_suite(self.clone, "main", False, "integrations/syncer")
                self.assertIn("integrations/syncer/latest_sync.py", got["covers"])
                self.assertIn("integrations/syncer/contest_feed.mjs", got["covers"])
                self.assertEqual(got["uncovered"], [])
            finally:
                fixture_git(self.clone, "rm", "-rq", "integrations/syncer")
                fixture_git(self.clone, "commit", "-q", "--no-verify", "-m", "remove syncer suite")


class IntegrationsBlockCase(CloneCase):

    def test_a_marked_script_is_diffed_against_its_master(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, "resources/scripts/widget.py", integration_source("2026.08.02", "V2"))
        got = integrations_block(vault, self.clone, "main", False,
                                 [], "2026.09.01")
        row = next(r for r in got["rows"] if r["name"] == "widget")
        self.assertEqual(row["verdict"], "behind")
        self.assertEqual(row["revision"], "2026.08.02")
        self.assertEqual(row["matched_revision"], "2026.08.02")

    def test_a_hand_bumped_copy_keeps_its_own_marker_as_revision(self):
        # V1's code under the master's 2026.09.01 header: the row's revision is the copy's
        # own marker, and the history entry it matched is reported beside it.
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, "resources/scripts/widget.py", integration_source("2026.09.01", "V1"))
        got = integrations_block(vault, self.clone, "main", False,
                                 [], "2026.09.01")
        row = next(r for r in got["rows"] if r["name"] == "widget")
        self.assertEqual(row["verdict"], "marker-matches-content-differs")
        self.assertEqual(row["case"], "hand-bumped")
        self.assertEqual(row["revision"], "2026.09.01")
        self.assertEqual(row["matched_revision"], "2026.08.01")

    def test_a_behind_copy_with_an_edited_marker_keeps_its_own_marker(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, "resources/scripts/widget.py", integration_source("2026.08.02", "V1"))
        got = integrations_block(vault, self.clone, "main", False,
                                 [], "2026.09.01")
        row = next(r for r in got["rows"] if r["name"] == "widget")
        self.assertEqual(row["verdict"], "behind")
        self.assertTrue(row["marker_edited"])
        self.assertEqual(row["revision"], "2026.08.02")
        self.assertEqual(row["matched_revision"], "2026.08.01")


class IntegrationRowCase(CloneCase):
    """What the sanctioned overwrite reads off a row: the verdict, the diff, the overwrite
    proof (never eligible for ahead, both or marker-matches-content-differs) and the suite."""

    def row_for(self, text, name="widget", ref="main", worktree=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        vault = Path(tmp.name).resolve()
        write(vault, f"resources/scripts/{name}.py", text)
        got = integrations_block(vault, self.clone, ref, worktree, [],
                                 "2026.09.01")
        return next(r for r in got["rows"] if r["name"] == name)

    def test_a_behind_copy_proves_its_overwrite_by_history_match(self):
        row = self.row_for(integration_source("2026.08.02", "V2"))
        self.assertEqual(row["master"], "integrations/widget/widget.py")
        self.assertEqual(row["overwrite"], {"eligible": True, "proof": "history-match",
                                            "proof_commit": self.rev("rev2")})

    def test_the_diff_runs_from_the_master_to_the_copy_with_its_line_counts(self):
        row = self.row_for(integration_source("2026.08.02", "V2"))
        self.assertIn("-VALUE = 'V3-fixed'", row["diff"])
        self.assertIn("+VALUE = 'V2'", row["diff"])
        self.assertEqual(row["diff_stat"], {"added": 2, "removed": 2})  # marker and value
        self.assertFalse(row["diff_truncated"])

    def test_a_long_diff_is_capped_at_200_lines_and_says_so(self):
        extra = "".join(f"LINE_{i} = {i}\n" for i in range(300))
        row = self.row_for(integration_source("2026.08.02", "V2") + extra)
        self.assertTrue(row["diff_truncated"])
        self.assertEqual(len(row["diff"].splitlines()), 200)
        self.assertEqual(row["diff_stat"], {"added": 302, "removed": 2})  # counted uncapped

    def test_an_identical_copy_has_an_empty_diff_and_no_matched_revision(self):
        row = self.row_for(integration_source("2026.09.01", "V3-fixed"))
        self.assertEqual(row["verdict"], "identical")
        self.assertEqual(row["diff"], "")
        self.assertEqual(row["diff_stat"], {"added": 0, "removed": 0})
        self.assertNotIn("matched_revision", row)

    def test_a_diverged_copy_is_both_and_never_eligible(self):
        row = self.row_for(integration_source("2026.08.02", "V2") + "LOCAL = 1\n")
        self.assertEqual(row["verdict"], "both")
        self.assertEqual(row["closest"], self.rev("rev2"))
        self.assertEqual(row["overwrite"], {"eligible": False, "proof": None,
                                            "proof_commit": None})

    def test_a_hand_bumped_copy_is_never_eligible_though_its_code_matches_an_old_version(self):
        # Comments are not in the AST, so the ast proof alone would call this copy
        # equivalent to the 2026.08.01 version: the verdict gate is what refuses it.
        row = self.row_for(integration_source("2026.09.01", "V1"))
        self.assertEqual(row["verdict"], "marker-matches-content-differs")
        self.assertFalse(row["overwrite"]["eligible"])

    def test_the_row_locates_the_integration_s_own_suite(self):
        suite = self.row_for(integration_source("2026.08.02", "V2"))["suite"]
        self.assertEqual(suite, {
            "dir": "integrations/widget", "files": ["integrations/widget/test_widget.py"],
            "runner": 'py -3 -m unittest discover -s . -p "test_*.py"',
            "fixtures": ["integrations/widget/widget.config.json.template"],
            "covers": ["integrations/widget/widget.py"], "uncovered": []})

    def test_a_marker_naming_no_shipped_integration_is_unresolvable_and_left_alone(self):
        row = self.row_for("# para-os-integration: mystery 2026.09.01\nX = 1\n", name="mystery")
        self.assertEqual(row, {"file": "resources/scripts/mystery.py", "name": "mystery",
                               "revision": "2026.09.01", "verdict": "unresolvable"})

    def test_a_copy_of_the_clone_s_uncommitted_master_is_ahead_of_the_ref(self):
        edited = integration_source("2026.09.01", "V4-uncommitted")
        write(self.clone, "integrations/widget/widget.py", edited)
        self.addCleanup(fixture_git, self.clone, "checkout", "-q", "--",
                        "integrations/widget/widget.py")
        against_ref = self.row_for(edited)
        self.assertEqual(against_ref["verdict"], "ahead")
        self.assertEqual(against_ref["source"], "worktree")
        self.assertFalse(against_ref["overwrite"]["eligible"])
        # --worktree reads that uncommitted file as the master itself.
        under_worktree = self.row_for(edited, ref="feat/extra", worktree=True)
        self.assertEqual(under_worktree["verdict"], "identical")


class LayoutIntegrationsCase(LayoutCase):

    def rows(self, vault):
        return integrations_block(vault, self.clone, "main", False, [],
                                  "2026.09.01")["rows"]

    def test_a_renamed_master_is_diffed_against_the_folder_s_lone_script(self):
        vault = self.tmp_vault()
        write(vault, "resources/scripts/old_solo.py",
              "# para-os-integration: solo 2026.09.01\nSOLO = 1\n")
        row = self.rows(vault)[0]
        self.assertEqual(row["verdict"], "identical")
        self.assertTrue(row["renamed"])
        self.assertEqual(row["master"], "integrations/solo/solo.py")
        self.assertIsNone(row["suite"]["runner"])  # the folder ships no tests
        self.assertEqual(row["suite"]["uncovered"], ["integrations/solo/solo.py"])

    def test_a_folder_shipping_several_scripts_is_an_ambiguous_rename_naming_them(self):
        vault = self.tmp_vault()
        write(vault, "resources/scripts/old_pair.py",
              "# para-os-integration: pair 2026.09.01\nA = 1\n")
        self.assertEqual(self.rows(vault), [{
            "file": "resources/scripts/old_pair.py", "name": "pair", "revision": "2026.09.01",
            "verdict": "ambiguous-rename",
            "candidates": ["integrations/pair/a.py", "integrations/pair/b.py"]}])


    def test_a_module_s_script_resolves_from_its_pipeline_once_its_integration_is_gone(self):
        vault = self.tmp_vault()
        write(vault, "resources/scripts/activity.py", ACTIVITY_SOURCE)
        row = self.rows(vault)[0]
        self.assertEqual(row["master"], "addons/activity/pipeline/activity.py")
        self.assertEqual(row["verdict"], "identical")
        self.assertEqual(row["suite"]["covers"], ["addons/activity/pipeline/activity.py"])


class UnmarkedScriptsCase(LayoutCase):
    """`unmarked`: scripts carrying no marker, each with evidence (never a verdict) of the
    shipped file it matches under integrations/ at the ref's tip."""

    def unmarked(self, vault):
        return integrations_block(vault, self.clone, "main", False, [],
                                  "2026.09.01")["unmarked"]

    def test_an_unmarked_copy_of_a_shipped_script_names_it_as_evidence(self):
        vault = self.tmp_vault()
        write_bytes(vault, "resources/scripts/common.py",
                    HELPER_SOURCE.encode().replace(b"\n", b"\r\n"))  # CRLF still matches
        self.assertEqual(self.unmarked(vault), [{
            "file": "resources/scripts/common.py",
            "matches": [{"file": "integrations/helpers/common.py", "commit": None}]}])

    def test_a_script_matching_nothing_is_still_listed_with_no_matches(self):
        vault = self.tmp_vault()
        write(vault, "resources/scripts/mine.py", "print('mine')\n")
        self.assertEqual(self.unmarked(vault),
                         [{"file": "resources/scripts/mine.py", "matches": []}])

    def test_only_script_files_that_are_not_tests_are_candidates(self):
        vault = self.tmp_vault()
        for name in ("README.md", "notes.txt", "test_mine.py", "mine.test.js", "sync.sh"):
            write(vault, f"resources/scripts/{name}", "# content\n")
        self.assertEqual([u["file"] for u in self.unmarked(vault)], ["resources/scripts/sync.sh"])

    def test_a_marked_script_is_a_row_never_an_unmarked_entry(self):
        vault = self.tmp_vault()
        write(vault, "resources/scripts/solo.py",
              "# para-os-integration: solo 2026.09.01\nSOLO = 1\n")
        got = integrations_block(vault, self.clone, "main", False, [],
                                 "2026.09.01")
        self.assertEqual([r["file"] for r in got["rows"]], ["resources/scripts/solo.py"])
        self.assertEqual(got["unmarked"], [])

    def test_a_shipped_test_file_is_never_evidence(self):
        vault = self.tmp_vault()
        path = write(vault, "resources/scripts/checks.py", "# tests for common\n")
        self.assertEqual(_unmarked_matches(self.clone, "main", False, path), [])

    def test_under_worktree_an_uncommitted_script_in_the_clone_counts_as_evidence(self):
        write(self.clone, "integrations/helpers/draft.py", "DRAFT = 1\n")
        self.addCleanup((self.clone / "integrations" / "helpers" / "draft.py").unlink)
        vault = self.tmp_vault()
        path = write(vault, "resources/scripts/draft.py", "DRAFT = 1\n")
        self.assertEqual(_unmarked_matches(self.clone, "main", True, path),
                         [{"file": "integrations/helpers/draft.py", "commit": None}])
        self.assertEqual(_unmarked_matches(self.clone, "main", False, path), [])


# ================================================================================== skills

class UndeclaredAddonSkillCase(unittest.TestCase):
    """A real run against a ref still on the pre-addons/ flavors layout found this: a skill shipped by an addon the vault does not declare must be found under
    WHICHEVER layout the ref carries, never addons/ alone, or origin/main silently reports
    every real-estate skill as vault-local instead of undeclared_addon."""

    def old_layout_repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        fixture_git(root, "init", "-q", "-b", "main")
        fixture_git(root, "config", "core.autocrlf", "false")
        fixture_git(root, "config", "core.excludesFile", str(root / ".git" / "no-excludes"))
        write(root, "flavors/real-estate/.claude/skills/property-underwrite/SKILL.md",
              "---\nname: property-underwrite\n---\n# Underwrite\n")
        fixture_git(root, "add", "-A")
        fixture_git(root, "commit", "-q", "--no-verify", "-m", "old layout addon skill")
        return root

    def test_an_addon_skill_is_found_under_the_older_flavors_layout(self):
        root = self.old_layout_repo()
        got = _find_undeclared_addon_skill(root, "main", False, "property-underwrite", set())
        self.assertEqual(got, "real-estate")

    def test_a_declared_addon_or_a_name_no_addon_ships_is_never_reported(self):
        root = self.old_layout_repo()
        self.assertIsNone(_find_undeclared_addon_skill(root, "main", False,
                                                       "property-underwrite", {"real-estate"}))
        self.assertIsNone(_find_undeclared_addon_skill(root, "main", False, "no-such-skill",
                                                       set()))


class SkillsBlockCase(CloneCase):

    def test_revisions_behind_counts_changelog_entries_after_the_oldest_matched_revision(self):
        # scripts/run.py's real history in the fixture: "v1" at rev1 (template 2026.08 ->
        # normalised 2026.08.01), unchanged through rev2, rewritten to "v3" at rev3, unchanged
        # at rev3b (HEAD). A copy holding the rev1 content is "behind" at revision 2026.08.01,
        # and entries_between(2026.08.01, 2026.09.01) is exactly the 2026.08.02 and
        # 2026.09.01 entries CHANGELOG_TEXT carries - two.
        # SKILL.md, test_run.py and helper.py all match the master's real content exactly
        # (build_clone never edits them past rev1), so run.py is the only file that differs.
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md",
                "---\nname: widget-skill\n---\n# Widget skill\n\nscripts/run.py\n")
        write_at(skill_dir / "scripts" / "run.py", "print('v1')\n")
        write_at(skill_dir / "scripts" / "test_run.py", "# tests v1\n")
        write_at(skill_dir / "scripts" / "helper.py", "# helper v1\n")
        all_entries = changelog_entries(CHANGELOG_TEXT)
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", all_entries)
        row = next(r for r in got["rows"] if r.get("name") == "widget-skill")
        run_file = next(f for f in row["files"] if f["path"] == "scripts/run.py")
        self.assertEqual(run_file["verdict"], "behind")
        self.assertEqual(run_file["revision"], "2026.08.01")
        self.assertFalse(run_file["within_revision"])
        self.assertEqual(row["verdict"], "behind")
        self.assertEqual(row["revisions_behind"], 2)

    def test_no_user_skills_folder_reads_the_bundled_copies_alone(self):
        # /para-audit's call: a vault's bundled copies, never the machine's user-level ones.
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md",
                "---\nname: widget-skill\n---\n# Widget skill\n\nscripts/run.py\n")
        write_at(skill_dir / "scripts" / "run.py", "print('v3')\n")
        got = skills_block(vault, self.clone, "main", False, None,
                           {"flavor": None, "modules": []}, [], "2026.09.01",
                           changelog_entries(CHANGELOG_TEXT))
        self.assertEqual([(r["name"], r["location"]) for r in got["rows"][1:]],
                         [("widget-skill", "bundled")])
        self.assertIsNone(got["rows"][1]["wins"])
        self.assertEqual(got["rows"][0]["copies"], [])

    def test_revisions_behind_is_null_when_the_verdict_is_not_behind(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md",
                "---\nname: widget-skill\n---\n# Widget skill\n\nscripts/run.py\n")
        write_at(skill_dir / "scripts" / "run.py", "print('v3')\n")  # HEAD's real content
        write_at(skill_dir / "scripts" / "test_run.py", "# tests v1\n")
        write_at(skill_dir / "scripts" / "helper.py", "# helper v1\n")
        all_entries = changelog_entries(CHANGELOG_TEXT)
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", all_entries)
        row = next(r for r in got["rows"] if r.get("name") == "widget-skill")
        self.assertEqual(row["verdict"], "identical")
        self.assertIsNone(row["revisions_behind"])

    def test_tool_caches_and_sync_metadata_never_count_toward_the_tree(self):
        # A suite run in place leaves .pytest_cache/ and __pycache__/ beside the scripts, and a
        # Drive-synced vault a desktop.ini: none of it is the skill, so the copy stays identical.
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md",
                "---\nname: widget-skill\n---\n# Widget skill\n\nscripts/run.py\n")
        write_at(skill_dir / "scripts" / "run.py", "print('v3')\n")
        write_at(skill_dir / "scripts" / "test_run.py", "# tests v1\n")
        write_at(skill_dir / "scripts" / "helper.py", "# helper v1\n")
        write_at(skill_dir / "scripts" / ".pytest_cache" / "README.md", "# pytest cache\n")
        write_at(skill_dir / "scripts" / "__pycache__" / "run.cpython-312.pyc", "x")
        write_at(skill_dir / "desktop.ini", "[.ShellClassInfo]\n")
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01",
                           changelog_entries(CHANGELOG_TEXT))
        row = next(r for r in got["rows"] if r.get("name") == "widget-skill")
        self.assertEqual(row["verdict"], "identical")
        self.assertEqual(row["extra"], [])

    def test_a_copy_synced_from_a_feature_branch_is_reported_ahead(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md", "---\nname: widget-skill\n---\n# Widget skill\n\nscripts/run.py\n")
        write_at(skill_dir / "scripts" / "run.py", "print('feature-branch')\n")
        write_at(skill_dir / "scripts" / "test_run.py", "# tests v1\n")
        write_at(skill_dir / "scripts" / "helper.py", "# helper v1\n")
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", [])
        row = next(r for r in got["rows"] if r.get("name") == "widget-skill")
        run_file = next((f for f in row["files"] if f["path"] == "scripts/run.py"), None)
        self.assertIsNotNone(run_file)
        self.assertEqual(run_file["verdict"], "ahead")
        # feat/extra is the checked-out branch, so its own tip IS the working tree here;
        # "worktree" wins by appearing first in O, which is a legitimate answer too.
        self.assertIn(run_file["source"], ("worktree", "feat/extra"))

    def test_a_master_file_the_copy_lacks_is_reported_missing(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md", "---\nname: widget-skill\n---\n# Widget skill\n")
        write_at(skill_dir / "scripts" / "run.py", "print('v3')\n")
        # helper.py and test_run.py deliberately not copied: the helper is missing, the test
        # is not, since an install leaves every test_*.py in the kit.
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", [])
        row = next(r for r in got["rows"] if r.get("name") == "widget-skill")
        self.assertEqual(row["missing"], ["scripts/helper.py"])

    def test_a_test_file_in_the_copy_is_neither_extra_nor_compared(self):
        # An older install copied the tests along; a leftover one, the master's or the copy's
        # own, never makes the copy `extra` or `ahead`.
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md",
                "---\nname: widget-skill\n---\n# Widget skill\n\nscripts/run.py\n")
        write_at(skill_dir / "scripts" / "run.py", "print('v3')\n")
        write_at(skill_dir / "scripts" / "helper.py", "# helper v1\n")
        write_at(skill_dir / "scripts" / "test_run.py", "# tests, edited locally\n")
        write_at(skill_dir / "scripts" / "test_leftover.py", "# a test the master never had\n")
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", [])
        row = next(r for r in got["rows"] if r.get("name") == "widget-skill")
        self.assertEqual(row["verdict"], "identical")
        self.assertEqual(row["extra"], [])
        self.assertNotIn("suite", row)

    def test_a_name_with_no_master_and_no_source_anywhere_is_unmatched(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "totally-invented-skill"
        write_at(skill_dir / "SKILL.md", "---\nname: totally-invented-skill\n---\n# Invented\n")
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", [])
        row = next(r for r in got["rows"] if r.get("name") == "totally-invented-skill")
        self.assertEqual(row["verdict"], "unmatched")

    def widget_copy(self, run_py, skill_md="---\nname: widget-skill\n---\n# Widget skill\n\n"
                                          "scripts/run.py\n", helper=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        vault = Path(tmp.name).resolve()
        skill_dir = vault / ".claude" / "skills" / "widget-skill"
        write_at(skill_dir / "SKILL.md", skill_md)
        if run_py is not None:
            write_at(skill_dir / "scripts" / "run.py", run_py)
        write_at(skill_dir / "scripts" / "test_run.py", "# tests v1\n")
        if helper:
            write_at(skill_dir / "scripts" / "helper.py", "# helper v1\n")
        return vault

    def widget_row(self, vault, ref="main", worktree=False):
        got = skills_block(vault, self.clone, ref, worktree, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01",
                           changelog_entries(CHANGELOG_TEXT))
        return next(r for r in got["rows"] if r.get("name") == "widget-skill")

    def test_a_file_behind_and_locally_edited_makes_the_whole_skill_both(self):
        row = self.widget_row(self.widget_copy("print('v1!')\n"))  # rev1's line, edited
        run_file = next(f for f in row["files"] if f["path"] == "scripts/run.py")
        self.assertEqual(run_file, {"path": "scripts/run.py", "verdict": "both",
                                    "closest": self.rev("rev1")})
        self.assertEqual(row["verdict"], "both")
        self.assertIsNone(row["revisions_behind"])

    def test_a_missing_file_beside_one_synced_from_a_branch_makes_the_skill_both(self):
        row = self.widget_row(self.widget_copy("print('feature-branch')\n", helper=False))
        self.assertEqual(row["missing"], ["scripts/helper.py"])
        self.assertEqual(row["verdict"], "both")

    def test_a_script_skill_md_names_but_the_copy_lacks_is_reported(self):
        row = self.widget_row(self.widget_copy(None))
        self.assertEqual(row["names_missing_script"], ["scripts/run.py"])
        self.assertIn("scripts/run.py", row["missing"])

    def test_under_worktree_the_master_is_the_checked_out_file_on_disk(self):
        # feat/extra is checked out, its run.py reading 'feature-branch'; its parent's 'v3'
        # is then one version behind, within the same revision.
        row = self.widget_row(self.widget_copy("print('feature-branch')\n"), "feat/extra", True)
        self.assertEqual(row["verdict"], "identical")
        row = self.widget_row(self.widget_copy("print('v3')\n"), "feat/extra", True)
        run_file = next(f for f in row["files"] if f["path"] == "scripts/run.py")
        self.assertEqual(run_file["verdict"], "behind")
        self.assertEqual(run_file["commit"], self.rev("rev3"))
        self.assertTrue(run_file["within_revision"])


class LayoutSkillsCase(LayoutCase):

    def run_skills(self, vault, user_dir=None, **decl):
        decl, addons = self.addons(**decl)
        user = user_dir or (vault.parent / "no-user-skills")
        return skills_block(vault, self.clone, "main", False, str(user), decl, addons,
                            "2026.09.01", changelog_entries(CHANGELOG_TEXT))

    @staticmethod
    def row(got, name):
        return next(r for r in got["rows"] if r.get("name") == name)

    def test_a_declared_module_s_skill_is_diffed_against_that_module_s_master(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/deal-skill/SKILL.md", "---\nname: deal-skill\n---\n# Deals\n")
        row = self.row(self.run_skills(vault, modules=["sales"]), "deal-skill")
        self.assertEqual(row["master"], "addons/sales/.claude/skills/deal-skill")
        self.assertEqual(row["verdict"], "identical")
        self.assertIsNone(row["wins"])  # no user-level copy to shadow

    def test_with_a_copy_in_both_places_both_rows_name_the_bundled_one_as_winning(self):
        # derived-copies.md: the vault's bundled copy shadows the user-level install. Each row
        # used to name its own location, so the two rows contradicted each other.
        vault = self.tmp_vault()
        write(vault, ".claude/skills/deal-skill/SKILL.md", "---\nname: deal-skill\n---\n# Deals\n")
        user = vault.parent / "user-skills"
        write(user, "deal-skill/SKILL.md", "---\nname: deal-skill\n---\n# Deals\n")
        got = self.run_skills(vault, user_dir=user, modules=["sales"])
        rows = [r for r in got["rows"] if r.get("name") == "deal-skill"]
        self.assertEqual(sorted(r["location"] for r in rows), ["bundled", "user"])
        self.assertEqual([r["wins"] for r in rows], ["bundled", "bundled"])

    def test_a_skill_of_an_addon_the_vault_does_not_declare_is_skipped_not_diffed(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/deal-skill/SKILL.md", "---\nname: deal-skill\n---\n# Old\n")
        row = self.row(self.run_skills(vault), "deal-skill")
        self.assertEqual(row["undeclared_addon"], "sales")
        self.assertNotIn("verdict", row)

    def test_a_vault_declaring_a_module_resolves_its_skill_from_it(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/ledger-review/SKILL.md",
              "---\nname: ledger-review\n---\n# Ledger review\n")
        row = self.row(self.run_skills(vault, modules=["activity"]), "ledger-review")
        self.assertEqual(row["master"], "addons/activity/.claude/skills/ledger-review")
        self.assertEqual(row["verdict"], "identical")

    def test_a_module_s_skill_in_a_vault_that_does_not_declare_it_is_undeclared(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/ledger-review/SKILL.md",
              "---\nname: ledger-review\n---\n# Ledger review\n")
        row = self.row(self.run_skills(vault), "ledger-review")
        self.assertEqual(row["undeclared_addon"], "activity")
        self.assertNotIn("verdict", row)

    def test_base_is_tried_before_an_addon_skill_of_the_same_name(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/shared-skill/SKILL.md",
              "---\nname: shared-skill\n---\n# Sales copy\n")
        row = self.row(self.run_skills(vault, modules=["sales"]), "shared-skill")
        self.assertEqual(row["master"], "base/.claude/skills/shared-skill")
        self.assertNotEqual(row["verdict"], "identical")

    def test_no_master_but_a_folder_on_another_branch_is_ahead_never_unmatched(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/new-skill/SKILL.md", "---\nname: new-skill\n---\n# Mine\n")
        row = self.row(self.run_skills(vault), "new-skill")
        self.assertIsNone(row["master"])
        self.assertEqual(row["verdict"], "ahead")
        self.assertEqual(row["source"], "feat/new-skill")

    def test_no_master_but_a_folder_in_the_clone_s_working_tree_is_ahead(self):
        write(self.clone, "base/.claude/skills/wip-skill/SKILL.md", "# Work in progress\n")
        self.addCleanup(shutil.rmtree, self.clone / "base" / ".claude" / "skills" / "wip-skill",
                        True)
        vault = self.tmp_vault()
        write(vault, ".claude/skills/wip-skill/SKILL.md", "# Work in progress\n")
        row = self.row(self.run_skills(vault), "wip-skill")
        self.assertEqual(row["verdict"], "ahead")
        self.assertEqual(row["source"], "worktree")

    def test_a_file_only_the_copy_has_is_extra_or_ahead_where_a_branch_carries_it(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/base-skill/SKILL.md", "---\nname: base-skill\n---\n# Base\n")
        write(vault, ".claude/skills/base-skill/notes.md", "Branch-only notes.\n")
        write(vault, ".claude/skills/base-skill/local.md", "Mine alone.\n")
        row = self.row(self.run_skills(vault), "base-skill")
        self.assertEqual(row["extra"], [
            {"path": "local.md", "verdict": "extra"},
            {"path": "notes.md", "verdict": "ahead", "source": "feat/new-skill"}])
        self.assertEqual(row["verdict"], "ahead")

    def test_a_folder_with_no_skill_md_is_ignored_and_a_stray_file_skipped(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/drafts/notes.md", "Not a skill.\n")
        write(vault, ".claude/skills/stray.txt", "Not a folder.\n")
        got = self.run_skills(vault)
        drafts = vault / ".claude" / "skills" / "drafts"
        self.assertEqual(got["ignored"], [{"location": "bundled", "path": str(drafts)}])
        self.assertEqual([r["name"] for r in got["rows"]], ["para-shared"])

    def test_para_shared_is_one_library_row_holding_a_copy_per_installed_location(self):
        vault = self.tmp_vault()
        write(vault, ".claude/skills/para-shared/scripts/lib.py", "LIB = 1\n")
        user = vault.parent / "user-skills"
        write(user, "para-shared/scripts/lib.py", "LIB = 2\n")
        got = self.run_skills(vault, user_dir=user)
        self.assertEqual(got["rows"][0]["name"], "para-shared")
        self.assertEqual(got["rows"][0]["location"], "library")
        copies = {c["location"]: c for c in got["rows"][0]["copies"]}
        self.assertEqual(sorted(copies), ["bundled", "user"])
        self.assertEqual(copies["bundled"]["verdict"], "identical")
        self.assertNotEqual(copies["user"]["verdict"], "identical")
        self.assertEqual(copies["user"]["master"], "base/.claude/skills/para-shared")
        self.assertEqual(len(got["rows"]), 1)  # never listed again as a skill of its own


# =================================================================== smoke / snapshot / since

class SmokeBlockCase(unittest.TestCase):

    def test_an_ordinary_vault_reads_available(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        for d in ("projects", "areas", "archive"):
            (vault / d).mkdir()
        write(vault, "CLAUDE.md", "# Vault\n\n**Type:** vault\n")
        got = smoke_block(vault, "2026-09-22")
        self.assertTrue(got["available"])
        self.assertIn("open", got["totals"])


class SmokeStubCase(unittest.TestCase):
    """The vault's own bundled brief_scan.py is preferred over the one beside this skill, so
    a stub there stands in for each answer brief_scan.py can give."""

    def vault_with_stub(self, source):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        vault = Path(tmp.name).resolve()
        stub = write(vault, ".claude/skills/para-daily-brief/scripts/brief_scan.py", source)
        return vault, stub

    def test_the_vault_s_bundled_copy_runs_and_its_counts_are_kept(self):
        vault, stub = self.vault_with_stub(
            "import json, sys\n"
            "today = sys.argv[sys.argv.index('--today') + 1]\n"
            "print(json.dumps({'today': today, 'totals': {'open': 4},\n"
            "                  'entities': [{'label': 'Alpha', 'open': 3}],\n"
            "                  'lanes': {'now': [1, 2], 'later': []}, 'flags': ['f'],\n"
            "                  'ideas': [1], 'triage': [1, 2, 3], 'agenda': ['dropped']}))\n")
        got = smoke_block(vault, "2026-09-22")
        self.assertEqual(got, {
            "available": True, "script": str(stub), "today": "2026-09-22",
            "totals": {"open": 4}, "entities": [{"label": "Alpha", "open": 3}],
            "lanes": {"now": 2, "later": 0}, "flags": ["f"], "ideas": 1, "triage": 3})

    def test_output_that_is_not_json_reads_unavailable_with_the_reason(self):
        vault, _ = self.vault_with_stub("print('not json')\n")
        got = smoke_block(vault, None)
        self.assertFalse(got["available"])
        self.assertTrue(got["reason"].startswith("brief_scan.py output was not JSON"))

    def test_a_failing_run_with_nothing_on_stderr_names_its_exit_code(self):
        vault, _ = self.vault_with_stub("import sys\nsys.exit(3)\n")
        got = smoke_block(vault, None)
        self.assertFalse(got["available"])
        self.assertEqual(got["reason"], "brief_scan.py exited 3")

    def test_a_run_that_times_out_reads_unavailable_rather_than_hanging_the_scan(self):
        vault, _ = self.vault_with_stub("print('{}')\n")
        timeout = subprocess.TimeoutExpired("brief_scan.py", 120)
        with mock.patch.object(upgrade_scan.subprocess, "run", side_effect=timeout):
            got = smoke_block(vault, None)
        self.assertFalse(got["available"])
        self.assertIn("timed out", got["reason"])

    def test_with_no_brief_scan_anywhere_it_says_where_it_looked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "Vault").mkdir()
            elsewhere = root / "skills" / "para-upgrade" / "scripts" / "upgrade_scan.py"
            with mock.patch.object(upgrade_scan, "__file__", str(elsewhere)):
                got = smoke_block(root / "Vault", None)
        expected = root / "skills" / "para-daily-brief" / "scripts" / "brief_scan.py"
        self.assertFalse(got["available"])
        self.assertEqual(got["script"], str(expected))
        self.assertTrue(got["reason"].startswith("no brief_scan.py at"))


class SnapshotAndSinceCase(unittest.TestCase):

    def test_unchanged_catches_a_changed_and_a_deleted_file(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, "CLAUDE.md", "# Vault\n")
        write(vault, ".claude/rules/x.md", "---\npaths:\n  - a\n---\nrule\n")
        rules_rows = [{"file": ".claude/rules/x.md"}]
        before = snapshot_block(vault, [], rules_rows, [])
        earlier_doc = {"snapshot": before, "smoke": {"available": True,
                                                      "totals": {"open": 5}, "lanes": {},
                                                      "ideas": [], "triage": []}}
        write(vault, "CLAUDE.md", "# Vault\n\nEdited.\n")
        (vault / ".claude" / "rules" / "x.md").unlink()
        after = snapshot_block(vault, [], rules_rows, [])
        current_smoke = {"available": True, "totals": {"open": 7}, "lanes": {}, "ideas": [],
                         "triage": []}
        got = since_block(earlier_doc, after, current_smoke)
        changed_names = {Path(p).name for p in got["changed"]}
        self.assertIn("CLAUDE.md", changed_names)
        self.assertIn("x.md", changed_names)
        moved = {m["count"]: m for m in got["smoke"]}
        self.assertEqual(moved["totals.open"]["before"], 5)
        self.assertEqual(moved["totals.open"]["after"], 7)

    def test_the_snapshot_covers_skeleton_targets_and_marked_scripts_null_where_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp).resolve()
            write(vault, "CLAUDE.md", "# Vault\n")
            write(vault, "resources/scripts/widget.py", integration_source("2026.09.01", "V3"))
            snap = snapshot_block(vault, [{"vault_path": "triage/.gitkeep"}], [],
                                  ["resources/scripts/widget.py"])
        self.assertIsNotNone(snap[str(vault / "CLAUDE.md")])
        self.assertIsNotNone(snap[str(vault / "resources" / "scripts" / "widget.py")])
        self.assertIsNone(snap[str(vault / "triage" / ".gitkeep")])
        self.assertIsNone(snap[str(vault / "resources" / "scripts" / "README.md")])

    def test_since_reads_lane_entity_idea_and_triage_counts_and_skips_non_numeric_totals(self):
        before = {"available": True, "totals": {"open": 5, "window": "week"},
                  "lanes": {"now": 2}, "entities": [{"label": "Alpha", "open": 1}],
                  "ideas": 3, "triage": 0}
        after = {"available": True, "totals": {"open": 5, "window": "month"},
                 "lanes": {"now": 1}, "entities": [{"label": "Alpha", "open": 2}],
                 "ideas": 3, "triage": 4}
        got = since_block({"snapshot": {}, "smoke": before}, {}, after)
        moved = {m["count"]: (m["before"], m["after"]) for m in got["smoke"]}
        self.assertEqual(moved, {"lanes.now": (2, 1), "entities.Alpha.open": (1, 2),
                                 "triage": (0, 4)})

    def test_an_earlier_scan_with_no_smoke_reading_counts_every_current_count_as_moved(self):
        after = {"available": True, "totals": {"open": 2}, "lanes": {}, "ideas": 0,
                 "triage": 0}
        got = since_block({"snapshot": {}, "smoke": {"available": False, "reason": "x"}}, {},
                          after)
        self.assertEqual(got["smoke"], [{"count": "ideas", "before": None, "after": 0},
                                        {"count": "totals.open", "before": None, "after": 2},
                                        {"count": "triage", "before": None, "after": 0}])

    def test_reaction_paths_are_the_backticked_vault_file_paths_of_collected_reactions(self):
        entries = [{"reactions": [
            "Reaction: delete `.vscode/settings.json`; in `.gitignore`, delete `!.mcp.json` "
            "and add `.mcp.json`. Re-sync `/para-upgrade`, `para-shared/` and "
            "`base/.gitignore` at `2026.09.05`; keep `## Do not add` and "
            "`git rm --cached .mcp.json`, never `../other/CLAUDE.md`."]}, {"reactions": ["Reaction: none."]}]
        self.assertEqual(_reaction_paths(entries),
                         [".gitignore", ".mcp.json", ".vscode/settings.json"])

    def test_the_snapshot_covers_reaction_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp).resolve()
            write(vault, ".vscode/settings.json", "{}\n")
            snap = snapshot_block(vault, [], [], [], [".vscode/settings.json", ".mcp.json"])
        self.assertIsNotNone(snap[str(vault / ".vscode" / "settings.json")])
        self.assertIsNone(snap[str(vault / ".mcp.json")])

    def test_an_earlier_document_with_no_snapshot_reads_every_path_as_changed(self):
        # The safe side for a checkpoint: nothing to compare against stops the next write.
        current = {"b/CLAUDE.md": "abc", "a/README.md": None}
        got = since_block({"smoke": None}, current, None)
        self.assertEqual(got, {"changed": ["a/README.md", "b/CLAUDE.md"], "smoke": []})


# ==================================================================== build_report / main

class BuildReportCase(CloneCase):

    def test_exit_3_when_the_vault_is_not_a_root(self):
        with tempfile.TemporaryDirectory() as not_a_vault:
            report, code = build_report(Path(not_a_vault), self.clone, "main", False, None,
                                        str(Path(not_a_vault) / "skills"),
                                        str(Path(not_a_vault) / "settings.json"), None, [])
            self.assertEqual(code, 3)
            self.assertIn("vault", report)
            self.assertIn("clone", report)  # still built per the spec

    def test_exit_4_when_the_clone_is_not_a_para_os_clone(self):
        vault = self.make_vault(tempfile.mkdtemp(), fixture_template("2026.09.01"))
        with tempfile.TemporaryDirectory() as empty_repo:
            fixture_git(Path(empty_repo), "init", "-q")
            write(Path(empty_repo), "README.md", "# Not para-os\n")
            fixture_git(Path(empty_repo), "add", "-A")
            fixture_git(Path(empty_repo), "commit", "-q", "--no-verify", "-m", "unrelated repo")
            report, code = build_report(vault, Path(empty_repo), "HEAD", False, None,
                                        str(vault / "no-skills"), str(vault / "no-settings"),
                                        None, [])
            self.assertEqual(code, 4)
            self.assertIn("not a para-os clone", report["clone"]["error"])

    def test_exit_6_when_no_clone_was_found(self):
        vault = self.make_vault(tempfile.mkdtemp(), fixture_template("2026.09.01"))
        report, code = build_report(vault, None, None, False, None, str(vault / "no-skills"),
                                    str(vault / "no-settings"), None, [])
        self.assertEqual(code, 6)
        self.assertEqual((report["clone"]["path"], report["clone"]["source"]), (None, None))
        self.assertTrue(report["clone"]["error"].startswith("no para-os clone found"))
        self.assertNotIn("delta", report)  # never an unverified verdict

    def test_a_full_run_answers_zero_and_every_block_is_present(self):
        vault = self.make_vault(tempfile.mkdtemp(), fixture_template("2026.08.02"))
        report, code = build_report(vault, self.clone, "main", False, "2026-09-22",
                                    str(vault / "no-user-skills"),
                                    str(vault / "no-user-settings"), None, [])
        self.assertEqual(code, 0)
        for key in ("vault", "clone", "masters", "delta", "baseline", "skeleton", "rules",
                   "sections", "settings", "skills", "integrations", "smoke", "snapshot"):
            self.assertIn(key, report)
        self.assertEqual(report["delta"]["verdict"], "behind")

    def scan_args(self):
        root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        vault = self.make_vault(root, fixture_template("2026.09.01"))
        return root, vault, (vault, self.clone, "main", False, "2026-09-22",
                             str(root / "no-user-skills"), str(root / "no-user-settings"))

    def test_a_checkpoint_rerun_against_its_own_output_finds_nothing_changed(self):
        root, vault, args = self.scan_args()
        first, _ = build_report(*args, None, [])
        earlier = root / "phase0.json"
        earlier.write_text(json.dumps(first), encoding="utf-8")
        second, code = build_report(*args, str(earlier), [])
        self.assertEqual(code, 0)
        self.assertEqual(second["since"], {"changed": [], "smoke": []})
        write(vault, "CLAUDE.md", fixture_template("2026.09.01") + "A phase 1 edit.\n")
        third, _ = build_report(*args, str(earlier), [])
        self.assertEqual(third["since"]["changed"], [str(vault.resolve() / "CLAUDE.md")])

    def test_a_file_a_reaction_deletes_is_snapshotted_and_its_deletion_is_changed(self):
        root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        vault = self.make_vault(root, fixture_template("2026.08.02"))
        write(vault, ".editor/settings.json", "{}\n")
        args = (vault, self.clone, "main", False, "2026-09-22", str(root / "no-user-skills"),
                str(root / "no-user-settings"))
        first, _ = build_report(*args, None, [])
        target = str(vault / ".editor" / "settings.json")
        self.assertIsNotNone(first["snapshot"][target])
        self.assertIn(str(vault / ".gitignore"), first["snapshot"])
        earlier = root / "phase0.json"
        earlier.write_text(json.dumps(first), encoding="utf-8")
        (vault / ".editor" / "settings.json").unlink()
        second, _ = build_report(*args, str(earlier), [])
        self.assertEqual(second["since"]["changed"], [target])

    def test_an_unreadable_earlier_scan_is_reported_in_since_never_raised(self):
        root, _, args = self.scan_args()
        half_written = root / "phase0.json"
        half_written.write_text('{"snapshot": {', encoding="utf-8")
        report, code = build_report(*args, str(half_written), [])
        self.assertEqual(code, 0)
        self.assertTrue(report["since"]["error"].startswith("cannot read"))


class MainCase(unittest.TestCase):

    def test_main_exits_3_and_prints_json_on_stdout(self):
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as not_a_vault, tempfile.TemporaryDirectory() as clone:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--vault", not_a_vault, "--clone", clone])
            self.assertEqual(code, 3)
            data = json.loads(out.getvalue())
            self.assertIn("vault", data)

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, json.loads(out.getvalue()), err.getvalue()

    def test_main_exits_4_and_names_the_clone_s_problem_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            vault = root / "Vault"
            for d in ("projects", "areas"):
                (vault / d).mkdir(parents=True)
            write(vault, "CLAUDE.md", fixture_template("2026.09.01"))
            (root / "not-a-clone").mkdir()
            code, data, err = self.run_main(["--vault", str(vault),
                                             "--clone", str(root / "not-a-clone"),
                                             "--paraos-home", str(root / "home")])
        self.assertEqual(code, 4)
        self.assertTrue(data["clone"]["error"].startswith("not a git repository"))
        self.assertIn("upgrade_scan: not a git repository", err)

    def test_main_exits_5_when_the_clone_has_no_origin_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            vault = root / "Vault"
            for d in ("projects", "areas"):
                (vault / d).mkdir(parents=True)
            write(vault, "CLAUDE.md", fixture_template("2026.09.01"))
            clone = root / "clone"
            clone.mkdir()
            fixture_git(clone, "init", "-q", "-b", "main")
            write(clone, "CHANGELOG.md", CHANGELOG_TEXT)
            write(clone, "base/CLAUDE.md.template", fixture_template("2026.09.01"))
            fixture_git(clone, "add", "-A")
            fixture_git(clone, "commit", "-q", "--no-verify", "-m", "one")
            code, data, err = self.run_main(["--vault", str(vault), "--clone", str(clone),
                                             "--paraos-home", str(root / "home")])
        self.assertEqual(code, 5)
        self.assertTrue(data["clone"]["stable_missing"])
        self.assertIn("upgrade_scan: ref does not resolve: origin/stable", err)

    def a_vault(self, root):
        vault = root / "Vault"
        for d in ("projects", "areas"):
            (vault / d).mkdir(parents=True)
        write(vault, "CLAUDE.md", fixture_template("2026.08.02"))
        return vault

    def test_main_reads_the_clone_at_the_default_path_without_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            vault = self.a_vault(root)
            default = root / "home" / "para-os"
            default.mkdir(parents=True)
            build_clone(default, root / "origin.git")
            code, data, err = self.run_main(["--vault", str(vault), "--ref", "main",
                                             "--paraos-home", str(root / "home"),
                                             "--user-skills", str(root / "no-skills"),
                                             "--user-settings", str(root / "no-settings")])
        self.assertEqual(code, 0, err)
        self.assertEqual((data["clone"]["path"], data["clone"]["source"]),
                         (str(default), "default"))
        self.assertEqual(data["delta"]["verdict"], "behind")

    def test_main_takes_an_explicit_clone_over_the_default_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            vault = self.a_vault(root)
            (root / "home" / "para-os").mkdir(parents=True)
            (root / "not-a-clone").mkdir()
            code, data, _ = self.run_main(["--vault", str(vault),
                                           "--clone", str(root / "not-a-clone"),
                                           "--paraos-home", str(root / "home")])
        self.assertEqual(code, 4)
        self.assertEqual((data["clone"]["path"], data["clone"]["source"]),
                         (str(root / "not-a-clone"), "explicit"))

    def test_main_exits_6_when_no_clone_is_found_anywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            vault = self.a_vault(root)
            code, data, err = self.run_main(["--vault", str(vault),
                                             "--paraos-home", str(root / "home")])
        self.assertEqual(code, 6)
        self.assertIsNone(data["clone"]["path"])
        self.assertIn("upgrade_scan: no para-os clone found", err)
        self.assertIn(str(root / "home" / "para-os"), err)

    def test_main_exit_3_names_the_registered_vault_the_folder_sits_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            vault = root / "Work"
            for d in ("projects", "areas"):
                (vault / d).mkdir(parents=True)
            write(vault, "CLAUDE.md", fixture_template("2026.09.01"))
            write(root, "home/vaults.json", json.dumps([{"name": "Work", "path": str(vault)}]))
            code, data, err = self.run_main(["--vault", str(vault / "projects"),
                                             "--clone", str(root),
                                             "--paraos-home", str(root / "home")])
        self.assertEqual(code, 3)
        self.assertEqual(data["vault"]["hint"]["name"], "Work")
        self.assertIn(f"(registry: Work at {vault})", err)


class CommandLineCase(unittest.TestCase):
    """The script as the skill runs it: a separate process, one JSON document on stdout."""

    def test_run_as_a_command_it_exits_3_with_json_on_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([sys.executable, str(SCRIPT), "--vault", tmp, "--clone", tmp,
                                   "--paraos-home", tmp], capture_output=True)
        self.assertEqual(done.returncode, 3)
        self.assertFalse(json.loads(done.stdout.decode("utf-8"))["vault"]["root"])
        self.assertIn(b"not a vault root", done.stderr)

    def test_without_the_shared_library_it_exits_2_and_says_where_it_belongs(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "skills" / "para-upgrade" / "scripts" / "upgrade_scan.py"
            copy.parent.mkdir(parents=True)
            shutil.copyfile(SCRIPT, copy)
            done = subprocess.run([sys.executable, str(copy), "--vault", tmp, "--clone", tmp],
                                  capture_output=True)
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, b"")
        self.assertIn(b"paraos_vault", done.stderr)
        self.assertIn(b"install para-shared", done.stderr)
        self.assertNotIn(b"by hand", done.stderr)


if __name__ == "__main__":
    unittest.main()
