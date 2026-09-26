#!/usr/bin/env python3
"""Tests for upgrade_scan.py. Each one pins a rule references/scan.md, delta.md,
rules-and-skeleton.md or derived-copies.md states in prose, or a defect a --test run found
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
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "para-shared" / "scripts"))

from upgrade_scan import (  # noqa: E402
    HistoryBatch, _collected_glob_twin, _dirty_masters, _doubled_block, _effective_blob,
    _entry_shape, _frontmatter_paths,
    _global_commit_order, _integration_master_path, _integration_suite,
    _mechanical_equivalence, _parse_batch_output, _root_history_map, _rule_anchors,
    _rule_kind, _sweep_root, _template_path_variants, baseline_block, build_report,
    clone_block, compute_verdict, delta_block, integrations_block, main, masters_block,
    rules_block, settings_block, since_block, skeleton_block, skills_block, smoke_block,
    snapshot_block,
)
from paraos_vault import changelog_entries, clone_read  # noqa: E402


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
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "core.autocrlf=false", *args],
                   cwd=root, check=True, capture_output=True)


def fixture_template(marker, delivery=None):
    lines = ["# Vault Conventions", "", f"<!-- para-os-template: {marker} -->",
             "**Type:** vault-type"]
    if delivery:
        lines.append(f"**Delivery:** {delivery}")
    return "\n".join(lines + ["", "Guidance.", ""])


def integration_source(revision, body):
    return f"#!/usr/bin/env python3\n# para-os-integration: widget {revision}\nVALUE = {body!r}\n"


CHANGELOG_TEXT = """# Changelog

Intro text, never a revision entry.

---

## 2026.09.01

**Widget integration rewritten.** New behaviour for the widget script. Reaction: re-sync
installed widget copies.

**Second change.** More text about it. Reaction: nothing to do.

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
    integrations/widget/widget.py, an addons/ delivery and skill, a fake origin remote so
    origin/main exists, and a feature branch left checked out at the end - so a test calling
    baseline_block(clone, "main", ...) is genuinely reading a ref other than HEAD.
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
    write(root, "addons/readonly-ipad/skeleton/CLAUDE.md.template",
          fixture_template("2026.08", "readonly-ipad"))
    write(root, "addons/readonly-ipad/skeleton/README.md.template", "# Vault\n")
    write(root, "addons/readonly-ipad/pipeline/flip.ps1", "# flip v1\n")
    write(root, "integrations/widget/widget.py", integration_source("2026.08.01", "V1"))
    write(root, "integrations/widget/README.md", "# widget\n")
    write(root, "integrations/widget/test_widget.py", "# tests\n")
    write(root, "integrations/widget/widget.config.json.template", "{}\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "rev 2026.08.01")
    fixture_git(root, "tag", "rev1")

    write(root, "base/CLAUDE.md.template", fixture_template("2026.08.02"))
    write(root, "addons/readonly-ipad/skeleton/CLAUDE.md.template",
          fixture_template("2026.08.02", "readonly-ipad"))
    write(root, "integrations/widget/widget.py", integration_source("2026.08.02", "V2"))
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "rev 2026.08.02")
    fixture_git(root, "tag", "rev2")

    write(root, "base/CLAUDE.md.template", fixture_template("2026.09.01"))
    write(root, "addons/readonly-ipad/skeleton/CLAUDE.md.template",
          fixture_template("2026.09.01", "readonly-ipad"))
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
    fixture_git(root, "remote", "add", "origin", str(bare_dir))
    fixture_git(root, "push", "-q", "origin", "main")
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
        self.assertEqual(got["content_of"], "old")
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


# ============================================================================ small helpers

class CollectedGlobTwinCase(unittest.TestCase):

    def test_trailing_star_star(self):
        self.assertEqual(_collected_glob_twin("triage/**"), "resources/mds/triage__*")

    def test_leading_and_trailing(self):
        self.assertEqual(_collected_glob_twin("**/sources/**"),
                         "resources/mds/*__sources__*")

    def test_interior_slashes_only(self):
        self.assertEqual(_collected_glob_twin("projects/*/brief.md"),
                         "resources/mds/projects__*__brief.md")

    def test_interior_star_star_collapses_to_one_star(self):
        # base/.claude/rules/figures.md writes areas/**/README.md's twin this way.
        self.assertEqual(_collected_glob_twin("areas/**/README.md"),
                         "resources/mds/areas__*__README.md")
        self.assertEqual(_collected_glob_twin("archive/**/brief.md"),
                         "resources/mds/archive__*__brief.md")


class DoubledBlockCase(unittest.TestCase):

    def test_a_plain_glob_with_no_twin_is_reported_missing(self):
        got = _doubled_block(["triage/**"], {"delivery": "readonly-ipad"})
        self.assertTrue(got["required"])
        self.assertEqual(got["missing_twins"], ["triage/**"])

    def test_a_glob_with_its_twin_present_is_not_missing(self):
        got = _doubled_block(["triage/**", "resources/mds/triage__*"],
                             {"delivery": "readonly-ipad"})
        self.assertEqual(got["missing_twins"], [])

    def test_not_required_for_an_ordinary_delivery(self):
        got = _doubled_block(["triage/**"], {"delivery": None})
        self.assertFalse(got["required"])

    def test_missing_twins_is_null_when_not_required(self):
        # A --test run found the shipped figures.md reported with missing twins on a vault
        # that needs none, which read as a failed check.
        got = _doubled_block(["areas/**/README.md", "projects/*/brief.md"],
                             {"delivery": None, "collected": False})
        self.assertIsNone(got["missing_twins"])


class TemplatePathVariantsCase(unittest.TestCase):

    def test_base_template_has_no_older_layout(self):
        self.assertEqual(_template_path_variants("base/CLAUDE.md.template", None),
                         ["base/CLAUDE.md.template"])

    def test_a_delivery_template_lists_every_layout_it_may_have_lived_at(self):
        got = _template_path_variants("addons/readonly-ipad/skeleton/CLAUDE.md.template",
                                      "readonly-ipad")
        self.assertEqual(got, [
            "addons/readonly-ipad/skeleton/CLAUDE.md.template",
            "delivery/readonly-ipad/skeleton/CLAUDE.md.template",
            "flavors/readonly-ipad/skeleton/CLAUDE.md.template",
        ])


class RuleAnchorsCase(unittest.TestCase):

    def test_front_matter_paths_read_the_same_from_a_crlf_file(self):
        text = "---\npaths:\n  - projects/*/brief.md\n  - areas/*/brief.md\n---\nbody\n"
        self.assertEqual(_frontmatter_paths(text.replace("\n", "\r\n")),
                         ["projects/*/brief.md", "areas/*/brief.md"])

    def test_a_shape_file_has_all_three_anchors(self):
        text = "---\npaths:\n  - x\n---\n**Order:** a, b\n\n## The shape\n\nbody\n\n## Placeholders\n\nnone\n"
        anchors = _rule_anchors(text)
        self.assertEqual(anchors, {"order": True, "shape": True, "placeholders_last": True})
        self.assertEqual(_rule_kind(anchors), "shape")

    def test_a_convention_file_has_none(self):
        text = "---\npaths:\n  - x\n---\nA rule stated in prose, no anchors at all.\n"
        anchors = _rule_anchors(text)
        self.assertEqual(anchors, {"order": False, "shape": False, "placeholders_last": False})
        self.assertEqual(_rule_kind(anchors), "convention")

    def test_a_partial_set_of_anchors_is_mixed(self):
        text = "---\npaths:\n  - x\n---\n**Order:** a\n\nprose only, no shape heading\n"
        anchors = _rule_anchors(text)
        self.assertEqual(_rule_kind(anchors), "mixed")


class ChangelogEntryShapeCase(unittest.TestCase):
    """Pins the items/reactions parser against the real changelog's two paragraph shapes:
    one bold-led sentence per paragraph with an inline Reaction, and the legacy 2026.08.01
    entry's un-reacted bulleted tail."""

    def setUp(self):
        self.entries = {e["revision"]: e for e in changelog_entries(CHANGELOG_TEXT)}

    def test_a_reacted_entry_pairs_items_with_reactions(self):
        shaped = _entry_shape(self.entries["2026.09.01"])
        self.assertEqual(shaped["items"],
                         ["Widget integration rewritten.", "Second change."])
        self.assertEqual(len(shaped["reactions"]), 2)
        self.assertTrue(shaped["reactions"][0].startswith("Reaction: re-sync"))

    def test_the_legacy_entry_s_bullets_are_their_own_items_with_no_reaction(self):
        shaped = _entry_shape(self.entries["2026.08.01"])
        self.assertIn("Housekeeping one.", shaped["items"])
        self.assertIn("Housekeeping two.", shaped["items"])
        self.assertEqual(shaped["reactions"], [])

    def test_intro_prose_with_no_bold_lead_is_not_an_item(self):
        shaped = _entry_shape(self.entries["2026.08.01"])
        self.assertNotIn("Six changes, before revisions carried a Reaction line.",
                         " ".join(shaped["items"]))

    def test_a_reaction_named_in_earlier_prose_is_skipped_for_the_paragraph_s_own(self):
        # The 2026.09.04 "Other skill changes" paragraph, cut down: its prose names the
        # 2026.09.03 entry's reaction before its own closing one.
        entry = {"revision": "2026.09.04", "line": 1, "body": (
            "**Other skill changes.** `rules-and-skeleton.md` states three points of the "
            "2026.09.03 `.claude/rules/` Reaction: a *richer version* is a fuller statement "
            "of the same rule. Reaction: re-sync installed skill copies. No other vault "
            "changes.\n")}
        shaped = _entry_shape(entry)
        self.assertEqual(shaped["reactions"],
                         ["Reaction: re-sync installed skill copies. No other vault changes."])


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


class HistoryBatchCase(CloneCase):
    """Against the real fixture clone: the raw-log parser, the effective-template lookup,
    and the batch's own two-phase (want, then resolve) discipline."""

    def test_root_history_map_lists_every_changing_commit_newest_first(self):
        history = _root_history_map(self.clone, "main", "integrations/widget")
        commits = [c for c, _ in history["integrations/widget/widget.py"]]
        self.assertEqual(commits, [self.rev("rev3b"), self.rev("rev3"), self.rev("rev2"),
                                   self.rev("rev1")])

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

    def test_origin_main_and_same_commit_grouping(self):
        block, ok, ref = clone_block(self.clone, "origin/main", False)
        self.assertTrue(ok)
        self.assertIsNotNone(block["origin_main"])
        self.assertEqual(block["origin_main"]["commit"], block["ref_commit"])
        self.assertIn(["origin_main", "ref"], block["same_commit"])

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


# ================================================================================== masters

class MastersBlockCase(CloneCase):

    def test_a_delivery_row_resolves_its_root(self):
        decl = {"delivery": "readonly-ipad", "flavor": None, "modules": []}
        got = masters_block(self.clone, "main", False, decl)
        rows = {r["name"]: r for r in got["addons"]}
        self.assertEqual(rows["readonly-ipad"]["root"], "addons/readonly-ipad")
        self.assertEqual(got["skeleton_overlay"], "addons/readonly-ipad/skeleton")

    def test_an_undeclared_module_with_no_folder_is_carried_forward_only_when_addons_missing(self):
        decl = {"delivery": None, "flavor": None, "modules": ["no-such-module"]}
        got = masters_block(self.clone, "main", False, decl)
        row = got["addons"][0]
        self.assertIsNone(row["root"])
        self.assertIn("reported", row)  # addons/ DOES exist at this ref, so it is reported...
        self.assertNotIn("carried_forward", row)   # ...never carried_forward


# ==================================================================================== delta

class DeltaBlockCase(CloneCase):

    def test_legacy_marker_reads_normalised_and_excludes_its_own_entry(self):
        vault = self.make_vault(self._tmpdir(), fixture_template("2026.08"))
        template = masters_block(self.clone, "main", False, {"delivery": None}).get("template") \
            or masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["vault_marker"], "2026.08.01")
        self.assertTrue(delta["legacy"])
        revisions = [e["revision"] for e in delta["entries"]]
        self.assertNotIn("2026.08.01", revisions)
        self.assertIn("2026.08.02", revisions)
        self.assertIn("2026.09.01", revisions)

    def test_equal_marker_reports_the_current_entry_and_no_others(self):
        vault = self.make_vault(self._tmpdir(), fixture_template("2026.09.01"))
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["verdict"], "equal")
        self.assertEqual(delta["entries"], [])
        self.assertEqual(delta["current"]["revision"], "2026.09.01")

    def test_ahead_marker_never_downgrades(self):
        vault = self.make_vault(self._tmpdir(), fixture_template("2099.01.01"))
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["verdict"], "ahead")
        self.assertEqual(delta["entries"], [])

    def test_no_marker_collects_every_entry(self):
        vault = self.make_vault(self._tmpdir(), "# Vault\n\nNo marker at all.\n")
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = delta_block(vault, self.clone, "main", False, template)
        self.assertEqual(delta["verdict"], "no-marker")
        self.assertEqual({e["revision"] for e in delta["entries"]},
                         {"2026.08.01", "2026.08.02", "2026.09.01"})

    def _tmpdir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


# ================================================================================= baseline

class BaselineBlockCase(CloneCase):

    def test_ref_tip_case(self):
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = {"vault_marker": "2026.09.01", "vault_marker_raw": "2026.09.01"}
        got = baseline_block(self.clone, "main", delta, template, {"delivery": None})
        self.assertEqual(got["source"], "ref-tip")

    def test_log_s_case_finds_the_parent_of_the_change_commit(self):
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = {"vault_marker": "2026.08.02", "vault_marker_raw": "2026.08.02"}
        got = baseline_block(self.clone, "main", delta, template, {"delivery": None})
        self.assertEqual(got["source"], "log-S")
        rev2 = subprocess.run(["git", "rev-parse", "rev2"], cwd=self.clone, check=True,
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(got["commit"], rev2)

    def test_the_raw_marker_search_never_matches_by_substring(self):
        # 2026.08 (raw legacy) must not match the 2026.08.02 template via a bare substring
        # search - it needs the comment delimiters. Confirmed by finding the RIGHT commit:
        # the boundary between the legacy label and 2026.08.02, i.e. rev1's own commit.
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = {"vault_marker": "2026.08.01", "vault_marker_raw": "2026.08"}
        got = baseline_block(self.clone, "main", delta, template, {"delivery": None})
        rev1 = subprocess.run(["git", "rev-parse", "rev1"], cwd=self.clone, check=True,
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(got["commit"], rev1)

    def test_walks_the_named_ref_not_the_checked_out_head(self):
        # HEAD (checked out) is feat/extra, which never touches base/CLAUDE.md.template beyond
        # what it inherited from main - passing ref="main" explicitly must still resolve
        # against main's own history, not silently against whatever HEAD happens to be.
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = {"vault_marker": "2026.08.02", "vault_marker_raw": "2026.08.02"}
        got_main = baseline_block(self.clone, "main", delta, template, {"delivery": None})
        got_feat = baseline_block(self.clone, "feat/extra", delta, template, {"delivery": None})
        self.assertEqual(got_main["commit"], got_feat["commit"])  # feat/extra branched from main
        self.assertEqual(got_main["source"], "log-S")

    def test_no_marker_at_all(self):
        template = masters_block(self.clone, "main", False, {"delivery": None})["template"]
        delta = {"vault_marker": None, "vault_marker_raw": None}
        got = baseline_block(self.clone, "main", delta, template, {"delivery": None})
        self.assertIsNone(got["commit"])
        self.assertIsNone(got["source"])


# ================================================================================ skeleton

class SkeletonBlockCase(CloneCase):

    def test_bootstrap_prompt_and_skills_and_own_template_are_excluded(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        rows = skeleton_block(vault, self.clone, "main", False, {"collected": False},
                              [{"kind": "delivery", "root": None}])
        paths = {r["vault_path"] for r in rows["rows"]}
        self.assertNotIn("bootstrap-prompt.md", paths)
        self.assertNotIn("CLAUDE.md.template", paths)
        self.assertFalse(any(p.startswith(".claude/skills/") for p in paths))

    def test_readme_template_maps_to_plain_readme(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        decl = {"collected": False, "delivery": "readonly-ipad"}
        addons = masters_block(self.clone, "main", False, decl)["addons"]
        rows = skeleton_block(vault, self.clone, "main", False, decl, addons)
        paths = {r["vault_path"]: r for r in rows["rows"]}
        self.assertIn("README.md", paths)
        self.assertNotIn("README.md.template", paths)

    def test_crlf_and_bom_only_copy_reads_identical(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        master_bytes = clone_read(self.clone, "main",
                                  "addons/readonly-ipad/skeleton/README.md.template")
        from paraos_vault import normalised as _norm  # canonical LF form, whatever this
        canonical = _norm(master_bytes)               # platform's own write() produced
        write_bytes(vault, "README.md", b"\xef\xbb\xbf" + canonical.replace(b"\n", b"\r\n"))
        decl = {"collected": False, "delivery": "readonly-ipad"}
        addons = masters_block(self.clone, "main", False, decl)["addons"]
        rows = skeleton_block(vault, self.clone, "main", False, decl, addons)
        readme_row = next(r for r in rows["rows"] if r["vault_path"] == "README.md")
        self.assertTrue(readme_row["present"])
        self.assertTrue(readme_row["identical"])

    def test_a_collected_vault_resolves_the_file_through_its_encoded_twin(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        master_bytes = clone_read(self.clone, "main",
                                  "addons/readonly-ipad/skeleton/README.md.template")
        write_bytes(vault, "resources/mds/README.md", master_bytes)  # top-level: no "__"
        decl = {"collected": True, "delivery": "readonly-ipad"}
        addons = masters_block(self.clone, "main", False, decl)["addons"]
        rows = skeleton_block(vault, self.clone, "main", False, decl, addons)
        readme_row = next(r for r in rows["rows"] if r["vault_path"] == "README.md")
        self.assertTrue(readme_row["present"])
        self.assertEqual(readme_row["collected_as"], "resources/mds/README.md")
        self.assertTrue(readme_row["identical"])


# =================================================================================== rules

class RulesBlockCase(CloneCase):

    def test_a_shape_rule_the_vault_lacks_has_master_paths_but_none_of_its_own(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        write(vault, ".claude/rules/widget-shape.md",
              "---\npaths:\n  - projects/*/widget.md\n---\n**Order:** a\n\n"
              "## The shape\n\nbody\n\n## Placeholders\n\nnone\n")
        rows = rules_block(vault, self.clone, "main", False, {"delivery": None, "collected": False}, [])
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
        rows = rules_block(vault, self.clone, "main", False, {"delivery": None, "collected": False}, [])
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
        rows = rules_block(vault, self.clone, "main", False, {"delivery": None, "collected": False}, [])
        pointer = rows[0]["pointer"]
        self.assertTrue(pointer["present"])
        self.assertEqual(pointer["wording"], "convention")
        self.assertEqual(pointer["section"], "Filing and naming")


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


# ============================================================================ integrations

class IntegrationMasterPathCase(CloneCase):

    def test_direct_path_resolves(self):
        path, special, candidates = _integration_master_path(
            self.clone, "main", False, "widget", "widget.py", [])
        self.assertEqual(path, "integrations/widget/widget.py")
        self.assertIsNone(special)

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
        got = integrations_block(vault, self.clone, "main", False, {"delivery": None},
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
        got = integrations_block(vault, self.clone, "main", False, {"delivery": None},
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
        got = integrations_block(vault, self.clone, "main", False, {"delivery": None},
                                 [], "2026.09.01")
        row = next(r for r in got["rows"] if r["name"] == "widget")
        self.assertEqual(row["verdict"], "behind")
        self.assertTrue(row["marker_edited"])
        self.assertEqual(row["revision"], "2026.08.02")
        self.assertEqual(row["matched_revision"], "2026.08.01")


# ================================================================================== skills

class UndeclaredAddonSkillCase(unittest.TestCase):
    """A real run against origin/main (still on the pre-addons/ delivery+flavors layout)
    found this: a skill shipped by an addon the vault does not declare must be found under
    WHICHEVER layout the ref carries, never addons/ alone, or origin/main silently reports
    every real-estate skill as vault-local instead of undeclared_addon."""

    def test_an_addon_skill_is_found_under_the_older_delivery_layout(self):
        from upgrade_scan import _find_undeclared_addon_skill
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        fixture_git(root, "init", "-q", "-b", "main")
        fixture_git(root, "config", "core.autocrlf", "false")
        fixture_git(root, "config", "core.excludesFile", str(root / ".git" / "no-excludes"))
        write(root, "delivery/real-estate/.claude/skills/property-underwrite/SKILL.md",
              "---\nname: property-underwrite\n---\n# Underwrite\n")
        fixture_git(root, "add", "-A")
        fixture_git(root, "commit", "-q", "--no-verify", "-m", "old layout addon skill")
        got = _find_undeclared_addon_skill(root, "main", False, "property-underwrite", set())
        self.assertEqual(got, "real-estate")


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
        # helper.py and test_run.py deliberately not copied
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", [])
        row = next(r for r in got["rows"] if r.get("name") == "widget-skill")
        self.assertIn("scripts/helper.py", row["missing"])
        self.assertIn("scripts/test_run.py", row["missing"])

    def test_a_name_with_no_master_and_no_source_anywhere_is_unmatched(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        skill_dir = vault / ".claude" / "skills" / "totally-invented-skill"
        write_at(skill_dir / "SKILL.md", "---\nname: totally-invented-skill\n---\n# Invented\n")
        got = skills_block(vault, self.clone, "main", False, str(vault / "no-user-skills"),
                           {"flavor": None, "modules": []}, [], "2026.09.01", [])
        row = next(r for r in got["rows"] if r.get("name") == "totally-invented-skill")
        self.assertEqual(row["verdict"], "unmatched")


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

    def test_a_collected_vault_is_refused_by_brief_scan_not_by_this_script(self):
        vault = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(vault, ignore_errors=True))
        for d in ("projects", "areas", "archive"):
            (vault / d).mkdir()
        write(vault, "CLAUDE.md", "# Vault\n\n**Type:** vault\n")
        write(vault, "resources/mds/projects__x__brief.md", "# brief\n")
        got = smoke_block(vault, "2026-09-22")
        self.assertFalse(got["available"])
        self.assertIn("collected", got["reason"])


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

    def test_a_full_run_answers_zero_and_every_block_is_present(self):
        vault = self.make_vault(tempfile.mkdtemp(), fixture_template("2026.08.02"))
        report, code = build_report(vault, self.clone, "main", False, "2026-09-22",
                                    str(vault / "no-user-skills"),
                                    str(vault / "no-user-settings"), None, [])
        self.assertEqual(code, 0)
        for key in ("vault", "clone", "masters", "delta", "baseline", "skeleton", "rules",
                   "settings", "skills", "integrations", "smoke", "snapshot"):
            self.assertIn(key, report)
        self.assertEqual(report["delta"]["verdict"], "behind")

    def test_a_collected_vault_is_answered_not_refused(self):
        vault = self.make_vault(tempfile.mkdtemp(), fixture_template("2026.09.01"))
        write(vault, "resources/mds/projects__x__brief.md", "# brief\n")
        report, code = build_report(vault, self.clone, "main", False, None,
                                    str(vault / "no-user-skills"),
                                    str(vault / "no-user-settings"), None, [])
        self.assertEqual(code, 0)
        self.assertTrue(report["vault"]["collected"])
        self.assertFalse(report["smoke"]["available"])


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


if __name__ == "__main__":
    unittest.main()
