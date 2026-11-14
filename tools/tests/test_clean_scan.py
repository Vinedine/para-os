#!/usr/bin/env python3
"""Tests for clean_scan.py. Each one pins a rule of the script, which is the
specification, or a finding from one of the two
recorded --test runs of this skill.

    python3 test_clean_scan.py
    py -3 test_clean_scan.py

Standard library only, so a vault that runs the skill can run its tests. Every fixture is a
throwaway vault in a temporary directory, with synthetic names only: nothing reads or writes
a real vault, and nothing calls a model. The date is passed in, never taken from the clock,
except in the one mtime-fallback test that has to measure against a real file timestamp.

What paraos_vault.py itself decides (fenced-block-aware scanning, link extraction, content
hashing) is tested in test_paraos_vault.py. What is tested
here is what this skill alone decides: file scope, contact-citation counting, what an
"entity folder" is under archive/, and how a stale item's date is measured.
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
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-deep-clean" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import clean_scan
from clean_scan import (
    DEFAULT_DATED_PATTERN, DEFAULT_NEXT_STEPS_HEADINGS, main, scan,
)
from paraos_vault import (  # made importable by clean_scan's own guard
    STALE_FILE_DAYS, changed, duplicates, hashes, scan_snapshot,
)

TODAY = date(2026, 9, 22)
LEAD_LIFECYCLE = ("# Vault\n\n## Deal lifecycle\n\n| Stage | PARA home |\n|---|---|\n"
                  "| Lead | `areas/business/leads.md` (row) |\n| Qualified | resources/ideas/ |\n")
SCRIPT = SCRIPTS / "clean_scan.py"
SHARED_SCRIPT = SCRIPTS.parents[1] / "para-shared" / "scripts" / "paraos_vault.py"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def git_init(root):
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    # No auto maintenance: its detached run writes into .git while a test reads or deletes it.
    subprocess.run(["git", "config", "gc.auto", "0"], cwd=root, check=True)
    subprocess.run(["git", "config", "maintenance.auto", "false"], cwd=root, check=True)


def git_commit_at(root, date_str, message="commit"):
    env = dict(os.environ, GIT_AUTHOR_DATE=f"{date_str}T00:00:00",
              GIT_COMMITTER_DATE=f"{date_str}T00:00:00")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=root, check=True, env=env)


def marker_claude_md(marker, *extra):
    lines = ["# Vault Conventions", "", f"<!-- para-os-template: {marker} -->",
             "**Type:** vault", *extra, ""]
    return "\n".join(lines) + "\n"


def make_clone(base_marker="2026.09.05", root=None):
    """A throwaway committed para-os clone, for the template-marker precondition. Not
    cleaned up by the caller's addCleanup until it registers one; VaultCase.clone() does.
    `root`, where given, is the folder to build it in.
    """
    root = Path(root) if root else Path(tempfile.mkdtemp())
    write(root, "base/CLAUDE.md.template", marker_claude_md(base_marker))
    git_init(root)
    git_commit_at(root, "2026-01-01")
    return root


class VaultCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # Resolved, as the scan resolves its vault: macOS's temp folder sits behind the /var
        # symlink and Windows' behind a short RUNNER~1 name, and an absolute path the scan
        # reports would never equal the unresolved spelling.
        self.root = Path(tmp.name).resolve()
        # An empty para-os home, so no test finds the machine's own default clone.
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        self.home = Path(home.name).resolve()
        patch = mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)

    def clone(self, **kwargs):
        path = make_clone(**kwargs)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def run_scan(self, phase, today=TODAY, ref="HEAD", clone=None, templates_dirs=None,
                dated_pattern=DEFAULT_DATED_PATTERN, headings=None, **declared):
        report, code = scan(self.root, today, phase, ref, clone, templates_dirs or [],
                            dated_pattern, headings or list(DEFAULT_NEXT_STEPS_HEADINGS),
                            **declared)
        self.assertEqual(code, 0)
        return report


# ------------------------------------------------------------------------------ preconditions

class DeepCleanStamp(VaultCase):
    """Phase 3 dates its run outside the vault, for the daily brief; no other phase does."""

    def test_only_phase_3_writes_its_date_under_the_vaults_name(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        stamp = self.home / "data" / "deep-clean" / f"{self.root.name}.txt"
        self.run_scan("1")
        self.run_scan("4")
        self.assertFalse(stamp.exists())
        self.run_scan("3")
        self.assertEqual(stamp.read_text(encoding="utf-8"), "2026-09-22\n")


class AuditRecord(VaultCase):
    """`--record` leaves the phase's findings count beside the stamp, for the brief; without
    the flag nothing is written, and a phase-1 run never writes the stamp itself."""

    def test_record_writes_the_counts_and_nothing_else(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/x/brief.md", "# X\n\nSee [gone](missing.md).\n")
        record = self.home / "data" / "deep-clean" / f"{self.root.name}.audit.json"
        stamp = self.home / "data" / "deep-clean" / f"{self.root.name}.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            clean_scan.main(["--vault", str(self.root), "--phase", "1", "--today", "2026-09-22"])
        self.assertFalse(record.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            clean_scan.main(["--vault", str(self.root), "--phase", "1", "--today", "2026-09-22", "--record"])
        data = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"date", "phase", "findings", "total"})
        self.assertEqual((data["date"], data["phase"]), ("2026-09-22", "1"))
        self.assertEqual(data["total"], sum(data["findings"].values()))
        self.assertGreaterEqual(data["findings"].get("dangling", 0), 1)
        self.assertFalse(stamp.exists())

    def test_counts_lists_and_objects_of_lists_only(self):
        from clean_scan import finding_counts
        self.assertEqual(finding_counts({"dangling": [1, 2], "duplicates": {"groups": [1], "skipped": []},
                                         "placeholders": [], "note": "x", "n": 3}),
                         {"dangling": 2, "duplicates": 1})
        self.assertEqual(finding_counts(None), {})

    def test_phase_one_leaves_its_inventory_out(self):
        from clean_scan import finding_counts
        self.assertEqual(finding_counts({
            "map": {"top_level": ["areas", "projects"], "entity_counts": {"projects": 2},
                    "empty_leaf_dirs": ["areas/x"]},
            "uncited_exempt": ["a.md"], "duplicates": {"groups": [], "skipped": ["big.pdf"]},
            "scripts": {"marked": ["s.py"], "unmarked": ["t.py"]},
            "archive": {"misplaced_checkboxes": {"projects": [1], "closed": {"areas": [1, 2]}}}}),
            {"map": 1, "archive": 3})

    def test_phase_four_counts_its_failed_checks_only(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/x/brief.md", "# X\n\nSee [gone](missing.md).\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            clean_scan.main(["--vault", str(self.root), "--phase", "4", "--today", "2026-09-22",
                             "--record"])
        failed = {r["check"] for r in json.loads(out.getvalue())["phase4"]["rows"]
                  if r["pass"] is False}
        record = self.home / "data" / "deep-clean" / f"{self.root.name}.audit.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(set(data["findings"]), failed)
        self.assertEqual(data["findings"]["dangling_links"], 1)


class Preconditions(VaultCase):

    def test_triage_loose_excludes_readme_and_flags_it_separately(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "triage/note.md", "x\n")
        write(self.root, "triage/README.md", "x\n")
        write(self.root, "triage/.gitkeep", "")
        pre = self.run_scan("1")["preconditions"]
        self.assertEqual(pre["triage_loose"], ["note.md"])
        self.assertTrue(pre["triage_readme"])

    def test_no_clone_anywhere_is_not_found_never_unverified(self):
        write(self.root, "CLAUDE.md", marker_claude_md("2026.08.01"))
        m = self.run_scan("1", clone=None)["preconditions"]["template_marker"]
        self.assertEqual(m["verdict"], "no_clone")
        self.assertIsNone(m["master"])

    def test_a_clone_at_the_default_path_is_found_without_clone(self):
        make_clone(base_marker="2026.09.05", root=self.home / "para-os")
        write(self.root, "CLAUDE.md", marker_claude_md("2026.08.01"))
        m = self.run_scan("1", clone=None)["preconditions"]["template_marker"]
        self.assertEqual((m["verdict"], m["master"]), ("behind", "2026.09.05"))

    def test_an_explicit_clone_wins_over_the_default_path(self):
        make_clone(base_marker="2026.08.01", root=self.home / "para-os")
        clone = self.clone(base_marker="2026.09.05")
        write(self.root, "CLAUDE.md", marker_claude_md("2026.08.01"))
        m = self.run_scan("1", clone=str(clone))["preconditions"]["template_marker"]
        self.assertEqual((m["verdict"], m["master"]), ("behind", "2026.09.05"))

    def test_equal(self):
        clone = self.clone(base_marker="2026.09.05")
        write(self.root, "CLAUDE.md", marker_claude_md("2026.09.05"))
        m = self.run_scan("1", clone=clone)["preconditions"]["template_marker"]
        self.assertEqual(m["verdict"], "equal")

    def test_behind(self):
        clone = self.clone(base_marker="2026.09.05")
        write(self.root, "CLAUDE.md", marker_claude_md("2026.08.01"))
        m = self.run_scan("1", clone=clone)["preconditions"]["template_marker"]
        self.assertEqual(m["verdict"], "behind")

    def test_ahead(self):
        clone = self.clone(base_marker="2026.09.05")
        write(self.root, "CLAUDE.md", marker_claude_md("2026.10.01"))
        m = self.run_scan("1", clone=clone)["preconditions"]["template_marker"]
        self.assertEqual(m["verdict"], "ahead")

    def test_unverified_when_vault_carries_no_marker(self):
        clone = self.clone(base_marker="2026.09.05")
        write(self.root, "CLAUDE.md", "# Vault\n\n**Type:** x\n")
        m = self.run_scan("1", clone=clone)["preconditions"]["template_marker"]
        self.assertEqual(m["verdict"], "unverified")
        self.assertIsNone(m["vault"])
        self.assertEqual(m["master"], "2026.09.05")


# ------------------------------------------------------------------------------------- Phase 1

OWN_CORE = ("# Core\n\nAn idea promotes to a project when money or a formal engagement is committed.\n\n"
            "| Bucket | State |\n|---|---|\n| `projects/` | open |\n| `archive/` | closed |\n")
OWN_RULE = ('---\npaths:\n  - "**/sources/**"\n---\n\n# Filing\n\n'
            "A document is filed by function and never by the name of its issuer.\n")
OWN_FILE = """# Vault

**Type:** vault

@.claude/para-os/core.md

## Working here

An idea is promoted to a project once money or a formal engagement has been committed.
Invoices from the paper supplier are filed in `areas/supplies/` under the month they cover.
Always answer in short sentences and lead with the decision taken.
A document is filed by function and never by the name of its issuer.

| Bucket | State |
|---|---|
| `projects/` | open |
| `archive/` | open |
| `areas/supplies/` | never |

## Supplier lifecycle

| Bucket | State |
|---|---|
| Quoted | first |

## Triage sources

An idea promotes to a project when money or a formal engagement is committed.
"""


class OwnRules(VaultCase):
    """What the vault's own CLAUDE.md holds beside the kit files installed in it."""

    def own(self, text=OWN_FILE):
        write(self.root, "CLAUDE.md", text)
        write(self.root, ".claude/para-os/core.md", OWN_CORE)
        write(self.root, ".claude/rules/filing.md", OWN_RULE)
        return self.run_scan("1")["phase1"]

    def test_a_kit_sentence_reworded_or_repeated_is_near_and_names_its_file(self):
        near = self.own()["own_rules"]["near"]
        self.assertEqual([(n["line"], n["in"]) for n in near],
                         [(9, ".claude/para-os/core.md"), (12, ".claude/rules/filing.md")])
        self.assertEqual(near[0]["kit"],
                         "An idea promotes to a project when money or a formal engagement is committed.")
        self.assertGreaterEqual(near[0]["ratio"], clean_scan.NEAR_RATIO)
        self.assertEqual(near[1]["ratio"], 1.0)

    def test_a_local_fact_a_general_rule_and_a_script_read_section_are_never_near(self):
        texts = " ".join(n["text"] for n in self.own()["own_rules"]["near"])
        self.assertNotIn("paper supplier", texts)
        self.assertNotIn("short sentences", texts)
        self.assertEqual(texts.count("promote"), 1)

    def test_a_table_sharing_a_kit_table_s_header_and_a_row_departs(self):
        self.assertEqual(self.own()["own_rules"]["departs"], [
            {"line": 14, "heading": "Working here", "in": ".claude/para-os/core.md",
             "differ": ["`archive/`"], "new": ["`areas/supplies/`"]}])

    def test_sections_are_sized_and_the_script_read_ones_marked(self):
        own = self.own()["own_rules"]
        self.assertEqual([(s["heading"], s["script_read"]) for s in own["sections"]],
                         [("Working here", False), ("Supplier lifecycle", False),
                          ("Triage sources", True)])
        self.assertEqual(own["words"], len(OWN_FILE.split()))
        self.assertEqual(own["kit_words"], len(OWN_CORE.split()))
        self.assertEqual(own["start_words"], own["words"] + own["kit_words"])

    def test_it_is_a_suggestion_and_never_counted_as_a_finding(self):
        report = self.own()
        self.assertTrue(report["own_rules"]["near"])
        self.assertNotIn("own_rules", clean_scan.finding_counts(report))

    def test_a_vault_importing_no_fixed_file_has_nothing_to_compare(self):
        write(self.root, "CLAUDE.md", "# Vault\n\n## Working here\n\nA rule of six words or more.\n")
        own = self.run_scan("1")["phase1"]["own_rules"]
        self.assertEqual((own["kit_words"], own["near"], own["departs"]), (0, [], []))


class Phase1Map(VaultCase):

    def test_map_counts_entities_and_empty_leaf_dirs(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "areas/business/brief.md", "# Business\n")
        write(self.root, "resources/ideas/thing/brief.md", "# Thing\n")
        (self.root / "resources/ideas/empty-one").mkdir(parents=True)
        m = self.run_scan("1")["phase1"]["map"]
        self.assertEqual(m["entity_counts"], {"projects": 1, "areas": 1, "resources/ideas": 2})
        self.assertIn("resources/ideas/empty-one", m["empty_leaf_dirs"])


class Placeholders(VaultCase):

    def test_only_the_root_files_the_bootstrap_fills_are_read(self):
        write(self.root, "CLAUDE.md", "# Vault\n\n{{vault-type}}\n")
        write(self.root, "README.md", "# Vault\n")
        write(self.root, "resources/ideas/flow/brief.md",
              '# Flow\n\n::: mermaid\nWait1{{"Wait"}} --> Step3\n:::\n')
        hits = self.run_scan("1")["phase1"]["placeholders"]
        self.assertEqual([h["file"] for h in hits], ["CLAUDE.md"])


class DanglingLinks(VaultCase):

    def test_dangling_link_reported(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\n[gone](missing.md)\n")
        hits = self.run_scan("1")["phase1"]["dangling"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["href"], "missing.md")

    def test_a_link_inside_a_declared_templates_folder_is_not_reported(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/templates/brief.md", "# Name\n\n[offer](sources/offer.pdf)\n")
        declared = {"templates_dirs": ["resources/templates"]}
        self.assertEqual(self.run_scan("1", **declared)["phase1"]["dangling"], [])
        rows = {r["check"]: r for r in self.run_scan("4", **declared)["phase4"]["rows"]}
        self.assertTrue(rows["dangling_links"]["pass"])
        self.assertEqual(len(self.run_scan("1")["phase1"]["dangling"]), 1)

    def test_a_rule_file_s_links_resolve_from_two_folders_down(self):
        # A repo list moved into .claude/rules/ carries ../../ links.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, ".claude/rules/code-repos.md",
              "# Code repos\n\n- [acme](../../projects/acme/brief.md)\n"
              "- [gone](../projects/acme/brief.md)\n")
        hits = self.run_scan("1")["phase1"]["dangling"]
        self.assertEqual([(h["file"], h["href"]) for h in hits],
                         [(".claude/rules/code-repos.md", "../projects/acme/brief.md")])

    def test_excludes_schemes_and_placeholders(self):
        # Finding 5 of the 20260915-2146 test run.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "\n".join([
            "# Acme", "",
            "[mail](mailto:jan@example.com)",
            "[call](tel:+3212345678)",
            "[local](file:///C:/nope.md)",
            "[tmpl](<placeholder>.md)", "",
        ]) + "\n")
        self.assertEqual(self.run_scan("1")["phase1"]["dangling"], [])

    def test_resolves_percent_encoded_spaces(self):
        # Finding 2 of the 20260915-2146 test run: a %20 link a plain-text grep would miss.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/ideas/the thing/brief.md", "# Thing\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n[good](../../resources/ideas/the%20thing/brief.md)\n")
        self.assertEqual(self.run_scan("1")["phase1"]["dangling"], [])

    def test_archived_entity_outward_link_checked(self):
        # A link written inside an archived entity is checked like a live one, decoded;
        # the same path named in prose is a historical mention and stays exempt.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan claes.md", "# Jan Claes\n")
        write(self.root, "archive/projects/old-shop/brief.md", "\n".join([
            "# Old shop", "",
            "[contact](../../../areas/network/jan%20claes.md)",
            "[plan](../../../projects/old-shop/plan.md)",
            "Was filed at projects/old-shop/notes.md before the move.", "",
        ]))
        for phase, hits in (("1", self.run_scan("1")["phase1"]["dangling"]),
                            ("4", next(r["detail"] for r in self.run_scan("4")["phase4"]["rows"]
                                       if r["check"] == "dangling_links"))):
            with self.subTest(phase=phase):
                self.assertEqual([(h["file"], h["href"]) for h in hits],
                                 [("archive/projects/old-shop/brief.md",
                                   "../../../projects/old-shop/plan.md")])


class Wikilinks(VaultCase):

    def test_resolved_and_unresolved(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nSee [[Jan Claes]] and [[Nobody Home|nobody]].\n")
        hits = {h["target"]: h for h in self.run_scan("1")["phase1"]["wikilinks"]}
        self.assertEqual(hits["Jan Claes"]["resolved"], "areas/network/jan-claes.md")
        self.assertIsNone(hits["Nobody Home"]["resolved"])
        self.assertEqual(hits["Nobody Home"]["display"], "nobody")

    def test_a_path_form_wikilink_resolves_vault_relative(self):
        # The index is keyed by stem, so [[projects/acme/brief]] used to fold to one
        # unmatchable key and report unresolved however right the path was.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/other/brief.md", "# Other\n")
        write(self.root, "areas/business/notes.md",
              "See [[projects/acme/brief]], [[projects/acme/brief.md]], [[acme/brief]] "
              "and [[projects/gone/brief]].\n")
        hits = {h["target"]: h["resolved"] for h in self.run_scan("1")["phase1"]["wikilinks"]}
        self.assertEqual(hits["projects/acme/brief"], "projects/acme/brief.md")
        self.assertEqual(hits["projects/acme/brief.md"], "projects/acme/brief.md")
        self.assertEqual(hits["acme/brief"], "projects/acme/brief.md")
        self.assertIsNone(hits["projects/gone/brief"])


class UncitedContacts(VaultCase):

    def test_mention_with_no_link_is_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nNot about anyone here.\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nJan Claes flagged a risk.\n")
        found = {c["card"]: c for c in self.run_scan("1")["phase1"]["uncited_contacts"]}
        self.assertEqual(found["areas/network/jan-claes.md"]["files"], ["projects/acme/brief.md"])

    def test_mention_with_a_link_is_not_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n[Jan Claes](../../areas/network/jan-claes.md) flagged a risk.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])

    def test_name_source_is_h1_plus_aliases(self):
        # Finding 6 of the 20260915-2146 test run.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/marten-van-oost.md",
              "# Marten Van Oost\n\n**Aliases:** Marten Vanoost\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMarten Vanoost called.\n")
        found = {c["card"] for c in self.run_scan("1")["phase1"]["uncited_contacts"]}
        self.assertIn("areas/network/marten-van-oost.md", found)

    def test_archive_is_out_of_scope(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "archive/meetings/20260101 Notes.md", "# Notes\n\nJan Claes was there.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])

    def test_principal_unlinked_mention_elsewhere_is_not_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "README.md",
              "# Vault\n\n## Identity\n\n[Jan Claes](areas/network/jan-claes.md) runs it.\n\n"
              "## Operating model\n\nn/a\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nJan Claes signed off.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])

    def test_principal_top_level_area_readme_must_still_link(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "areas/network/README.md", "# Network\n\nJan Claes is in here.\n")
        write(self.root, "README.md",
              "# Vault\n\n## Identity\n\n[Jan Claes](areas/network/jan-claes.md) runs it.\n")
        found = {c["card"] for c in self.run_scan("1")["phase1"]["uncited_contacts"]}
        self.assertIn("areas/network/jan-claes.md", found)

    def test_a_name_inside_backticks_is_not_a_mention(self):
        # Finding 1: a name quoted as a code sample is not a use of it.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nSee `Jan Claes` in the template.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])

    def test_a_name_inside_a_link_text_or_target_is_not_a_mention(self):
        # Finding 2 of the 20260923-1124 test run: 8 of 33 hits named the person only in a
        # linked source filename or a percent-encoded href.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nSee [the call](sources/20260922%20Jan%20Claes%20call.md).\n\n"
              "Also [20260922 Jan Claes call](sources/call.md).\n")
        write(self.root, "projects/beta/brief.md",
              "# Beta\n\nJan Claes agreed, per [20260922 Jan Claes call](sources/call.md).\n")
        found = {c["card"]: c for c in self.run_scan("1")["phase1"]["uncited_contacts"]}
        self.assertEqual(found["areas/network/jan-claes.md"]["files"], ["projects/beta/brief.md"])

    def test_a_link_only_line_to_the_card_still_cites_a_prose_mention(self):
        # A line naming the person only as the card link's label counts no mention, but
        # its link still cites every prose mention elsewhere in the file.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes flagged a risk.\n\n"
              "Contact: [Jan Claes](../../areas/network/jan-claes.md)\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])

    def test_a_card_link_on_a_line_naming_a_short_form_still_cites(self):
        # The file links the card twice, each on a line calling the person by a short form
        # the card does not list, and never on the line spelling the name in full.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes flagged a risk.\n\n"
              "Owner: [Jan](../../areas/network/jan-claes.md)\n\n"
              "Ask [JC](../../areas/network/jan-claes.md) first.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])

    def test_a_name_inside_a_longer_word_is_not_a_mention(self):
        # A contact "Mark" is not named by "Marketing": inbound_references() without a
        # parent is a substring find, so the name is re-matched as a whole word.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/mark.md", "# Mark\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMarketing owns `Mark` now.\n")
        write(self.root, "projects/beta/brief.md", "# Beta\n\nMarketing said Mark agreed.\n")
        found = {c["card"]: c for c in self.run_scan("1")["phase1"]["uncited_contacts"]}
        self.assertEqual(found["areas/network/mark.md"]["files"], ["projects/beta/brief.md"])

    def test_a_first_name_card_is_not_named_by_another_card_s_longer_name(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/sam.md", "# Sam\n")
        write(self.root, "areas/network/sam-hart.md", "# Sam Hart\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nSam Hart called.\n")
        write(self.root, "projects/beta/brief.md", "# Beta\n\nSam called, then Sam Hart.\n")
        got = {c["card"]: c["files"] for c in self.run_scan("1")["phase1"]["uncited_contacts"]}
        self.assertEqual(got["areas/network/sam.md"], ["projects/beta/brief.md"])

    def test_a_name_in_yaml_frontmatter_is_not_a_mention(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md", "---\nowner: Jan Claes\n---\n# Acme\n")
        write(self.root, "projects/beta/brief.md", "# Beta\n\n---\nJan Claes\n---\n")
        got = self.run_scan("1")["phase1"]["uncited_contacts"]
        self.assertEqual([c["files"] for c in got], [["projects/beta/brief.md"]])

    def test_a_ledger_record_is_exempt_but_named_for_override(self):
        # Finding 3: the mechanical proxy for "analytical and ledger records that are
        # evidence in all but folder name" - the file is dropped from the finding but
        # still listed, so the skill can override the proxy.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "areas/claude-platform/session-usage-review.md",
              "# Review\n\nJan Claes ran the session.\n")
        phase1 = self.run_scan("1")["phase1"]
        self.assertEqual(phase1["uncited_contacts"], [])
        self.assertEqual(phase1["uncited_exempt"],
                         ["areas/claude-platform/session-usage-review.md"])

    def test_a_ledger_word_in_a_folder_segment_also_exempts(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "areas/business/transcript/20260101 Call.md",
              "# Call\n\nJan Claes joined.\n")
        phase1 = self.run_scan("1")["phase1"]
        self.assertEqual(phase1["uncited_contacts"], [])
        self.assertIn("areas/business/transcript/20260101 Call.md", phase1["uncited_exempt"])

    def test_a_ledger_word_inside_a_longer_word_does_not_exempt(self):
        # Issue #32: "log" in "technologies" and "review" in "reviewer" hid real mentions.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "areas/acme-technologies-website/brief.md", "# Site\n\nJan Claes owns it.\n")
        write(self.root, "projects/acme/reviewer-feedback.md", "# Feedback\n\nJan Claes replied.\n")
        write(self.root, "projects/acme/strategy-log.md", "# Log\n\nJan Claes called.\n")
        write(self.root, "areas/usage/20260101 Digest.md", "# Digest\n\nJan Claes logged in.\n")
        phase1 = self.run_scan("1")["phase1"]
        found = {c["card"]: c for c in phase1["uncited_contacts"]}
        self.assertEqual(found["areas/network/jan-claes.md"]["files"],
                         ["areas/acme-technologies-website/brief.md",
                          "projects/acme/reviewer-feedback.md"])
        self.assertEqual(sorted(phase1["uncited_exempt"]),
                         ["areas/usage/20260101 Digest.md", "projects/acme/strategy-log.md"])

    def test_a_ledger_record_quoting_the_name_only_in_code_is_not_named_for_override(self):
        # uncited_exempt lists what the proxy dropped; a file with no prose mention had
        # nothing to drop, so naming it would invite an override of a non-finding.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "areas/ops/run-log.md", "# Log\n\nMatched `Jan Claes` in the config.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_exempt"], [])

    def contact_vault(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")

    def uncited_files(self, **declared):
        return [f for c in self.run_scan("1", **declared)["phase1"]["uncited_contacts"]
                for f in c["files"]]

    def test_prompts_and_declared_template_folders_are_excluded(self):
        # Issue #38: text pasted outside the vault is not a mention to cite.
        self.contact_vault()
        write(self.root, "resources/prompts/outreach.md", "# Outreach\n\nDear Jan Claes,\n")
        write(self.root, "resources/letters/intro.md", "# Intro\n\nDear Jan Claes,\n")
        self.assertEqual(self.uncited_files(templates_dirs=["resources/letters"]), [])

    def test_a_declared_sync_output_folder_is_excluded(self):
        self.contact_vault()
        write(self.root, "resources/newsletter/issue-12.md", "# Issue 12\n\nJan Claes wrote in.\n")
        self.assertEqual(self.uncited_files(), ["resources/newsletter/issue-12.md"])
        self.assertEqual(self.uncited_files(generated_dirs=["resources/newsletter/"]), [])

    def test_a_lifecycle_registers_contact_column_is_not_a_mention(self):
        # Issue #763: the sales add-on declares the register's Contact a name, not a link,
        # and the run that had to pass a flag for it did not.
        self.contact_vault()
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "| Company | Contact |", "|---|---|", "| Orchard | Jan Claes |", "",
        ]))
        self.assertEqual(self.uncited_files(), ["areas/business/leads.md"])
        write(self.root, "CLAUDE.md", LEAD_LIFECYCLE)
        self.assertEqual(self.uncited_files(), [])
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | **Contact** | Next step |",
            "|---|---|---|",
            "| Orchard | Jan Claes | Demo |",
            "| Harbour | Piet | Ask Jan Claes for an intro |", "",
        ]))
        self.assertEqual(self.uncited_files(), ["areas/business/leads.md"])

    def test_a_frozen_record_marker_exempts_a_client_facing_document(self):
        self.contact_vault()
        write(self.root, "projects/acme/proposal.md",
              "<!-- frozen record: sent to the client -->\n# Proposal\n\nFor Jan Claes.\n")
        write(self.root, "projects/acme/draft.md",
              "# Draft\n" + "\n" * 15 + "Not a frozen record.\n\nFor Jan Claes.\n")
        self.assertEqual(self.uncited_files(), ["projects/acme/draft.md"])

    def test_a_card_with_no_h1_is_named_by_its_also_line(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan.md", "Card notes\n\nAlso: Jan C; Janneke\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nJanneke called.\n")
        found = self.run_scan("1")["phase1"]["uncited_contacts"]
        self.assertEqual([(c["card"], c["name"]) for c in found], [("areas/network/jan.md", "Jan C")])

    def test_a_card_naming_no_one_is_skipped_rather_than_named_by_its_filename(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/stub.md", "Just notes, no title.\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nThe stub is still open.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])

    def test_a_line_before_the_title_does_not_hide_the_h1_name(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "<!-- card -->\n\n# Jan Claes\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nJan Claes flagged a risk.\n")
        found = self.run_scan("1")["phase1"]["uncited_contacts"]
        self.assertEqual([c["name"] for c in found], ["Jan Claes"])


    def test_the_network_readme_is_not_a_card(self):
        # Finding 1 of the 20261018 test runs: the folder README base ships was read as a
        # card named after its H1, so a "Network" tab in a script README was an uncited
        # contact.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/README.md", "# Network\n\nOne file per person.\n")
        write(self.root, "areas/network/actions.md", "# Network actions\n")
        write(self.root, "resources/scripts/README.md",
              "# Scripts\n\nOpen DevTools, Network tab, then reload.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["uncited_contacts"], [])


class InlineContactDetails(VaultCase):

    def test_the_network_readme_puts_no_name_on_the_line(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/README.md", "# Network\n")
        write(self.root, "resources/scripts/README.md",
              "# Scripts\n\nNetwork support: +32 470 12 34 56.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])

    def test_email_beside_a_named_contact_is_flagged_unattributed(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nReach Jan Claes at jan.claes@example.com.\n")
        hits = self.run_scan("1")["phase1"]["inline_contact_details"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["names_on_line"], ["Jan Claes"])
        self.assertEqual(hits[0]["detail"], "jan.claes@example.com")
        self.assertNotIn("card", hits[0])

    def test_a_detail_on_the_operator_s_own_card_is_not_one_to_move(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "areas/network/ann-smet.md", "# Ann Smet\n\nann.smet@example.com\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes invoices Ann.Smet@example.com, copy jan.claes@example.com.\n")
        self.assertEqual(len(self.run_scan("1")["phase1"]["inline_contact_details"]), 2)
        write(self.home, "operator.json", '{"card": "ann-smet"}')
        hits = self.run_scan("1")["phase1"]["inline_contact_details"]
        self.assertEqual([h["detail"] for h in hits], ["jan.claes@example.com"])

    def test_a_form_feed_above_a_detail_shifts_no_line(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "page one\x0cstill line one\nReach Jan Claes at jan.claes@example.com.\n")
        hits = self.run_scan("1")["phase1"]["inline_contact_details"]
        self.assertEqual([(h["line"], h["detail"]) for h in hits], [(2, "jan.claes@example.com")])

    def test_a_sentence_full_stop_is_not_part_of_the_email(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nReach Jan Claes at jan.claes@example.com.\n")
        hits = self.run_scan("1")["phase1"]["inline_contact_details"]
        self.assertEqual(hits[0]["detail"], "jan.claes@example.com")

    def test_every_carded_name_on_the_line_is_listed_not_just_the_nearest(self):
        # Finding 2: a detail is never attributed by proximity, so both names sharing the
        # line come back, and neither is picked as the owner.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes and Ann Peeters can both be reached at team@example.com.\n")
        hits = self.run_scan("1")["phase1"]["inline_contact_details"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["names_on_line"], ["Ann Peeters", "Jan Claes"])

    def test_a_name_inside_a_longer_word_does_not_put_it_on_the_line(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/mark.md", "# Mark\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nMarketing is at team@example.com.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])

    def test_sources_folder_is_excluded(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/sources/20260101 Email.md",
              "Jan Claes wrote from jan.claes@example.com.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])

    def test_a_detail_inside_a_code_span_is_not_a_detail(self):
        # Finding 1: a phone-shaped run of digits quoted in a code span is a path, not a
        # contact detail.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes filed it at `projects/acme/2026-0470123456.md`.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])

    def test_leading_plus_phone_is_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nReach Jan Claes at +32 470 12 34 56.\n")
        hits = self.run_scan("1")["phase1"]["inline_contact_details"]
        self.assertEqual([h["detail"] for h in hits], ["+32 470 12 34 56"])

    def test_eight_digit_phone_with_only_spaces_is_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nReach Jan Claes at 03 234 56 78.\n")
        hits = self.run_scan("1")["phase1"]["inline_contact_details"]
        self.assertEqual([h["detail"] for h in hits], ["03 234 56 78"])

    def test_a_short_digit_run_with_no_plus_is_not_a_phone(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes is in room 12 34 56.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])

    def test_an_iso_date_is_not_a_phone(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes signed off on 2026-06-19.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])

    def test_a_compact_eight_digit_date_is_not_a_phone(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes signed off on 20260619.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])

    def test_digits_inside_a_percent_encoded_link_target_are_not_a_phone(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes: see [scan](Jan%20Claes%2020260619.pdf).\n")
        self.assertEqual(self.run_scan("1")["phase1"]["inline_contact_details"], [])


    def phones_on(self, line):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md", f"# Acme\n\nJan Claes: {line}\n")
        return [h["detail"] for h in self.run_scan("1")["phase1"]["inline_contact_details"]]

    def test_phone_shaped_numbers_are_phones(self):
        # A leading + or a leading 0 with grouped digits, in the shapes people write them.
        for number in ("+32 470 12 34 56", "+33 6 12 34 56 78", "+31 (0)20 123 4567",
                       "03 234 56 78", "0470/12.34.56", "06 12 34 56 78", "06.12.34.56.78",
                       "06-12345678", "020 123 4567"):
            with self.subTest(number=number):
                self.assertEqual(self.phones_on(f"call {number} after six."), [number])

    def test_two_phones_on_one_line_are_two_details(self):
        self.assertEqual(self.phones_on("03 234 56 78 / 0470 12 34 56."),
                         ["03 234 56 78", "0470 12 34 56"])

    def test_identifiers_and_references_are_not_phones(self):
        for line in ("file 1111.2222222 is closed.", "identifier 123456782 on the letter.",
                     "case 2000 01234 is pending.", "docket 1111/22222.",
                     "IBAN BE71 0961 2345 6769.", "account NL91 ABNA 0417 1643 00.",
                     "register number 90.01.01-123.45.", "ref. 0123 456 789.",
                     "n° 0470 12 34 56 on the invoice.", "total 3333.4444444 units."):
            with self.subTest(line=line):
                self.assertEqual(self.phones_on(line), [])


class Duplicates(VaultCase):

    def test_cross_entity_duplicate_flagged(self):
        # Finding 7 of the 20260915-2146 test run.
        write(self.root, "CLAUDE.md", "# Vault\n")
        body = "x" * 250
        write(self.root, "projects/acme/sources/plan.md", body)
        write(self.root, "projects/other/sources/plan.md", body)
        groups = self.run_scan("1")["phase1"]["duplicates"]["groups"]
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["cross_entity"])

    def test_copies_inside_one_live_entity_are_not_cross_entity(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        body = "x" * 250
        write(self.root, "projects/acme/sources/plan.md", body)
        write(self.root, "projects/acme/notes/plan-copy.md", body)
        groups = self.run_scan("1")["phase1"]["duplicates"]["groups"]
        self.assertEqual([g["cross_entity"] for g in groups], [False])

    def test_an_archived_entity_is_the_folder_two_levels_below_archive(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/projects/acme/sources/a.md", "a" * 250)
        write(self.root, "archive/projects/acme/b.md", "a" * 250)
        write(self.root, "archive/projects/beta/c.md", "c" * 250)
        write(self.root, "archive/projects/gamma/d.md", "c" * 250)
        groups = {tuple(g["files"]): g["cross_entity"]
                  for g in self.run_scan("1")["phase1"]["duplicates"]["groups"]}
        self.assertFalse(groups[("archive/projects/acme/b.md", "archive/projects/acme/sources/a.md")])
        self.assertTrue(groups[("archive/projects/beta/c.md", "archive/projects/gamma/d.md")])

    def test_an_idea_is_the_folder_two_levels_below_resources(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/ideas/thing/a.md", "a" * 250)
        write(self.root, "resources/ideas/thing/sources/b.md", "a" * 250)
        groups = self.run_scan("1")["phase1"]["duplicates"]["groups"]
        self.assertEqual([g["cross_entity"] for g in groups], [False])

    def test_a_root_file_and_a_project_copy_are_cross_entity(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "notes.md", "n" * 250)
        write(self.root, "projects/acme/notes.md", "n" * 250)
        groups = self.run_scan("1")["phase1"]["duplicates"]["groups"]
        self.assertEqual([g["cross_entity"] for g in groups], [True])

    def test_skipped_folder_reported_not_dropped(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/sources/photos/a.jpg", "y" * 250)
        skipped = self.run_scan("1")["phase1"]["duplicates"]["skipped"]
        self.assertIn("projects/acme/sources/photos/a.jpg", skipped)

    def test_only_a_shared_size_is_read_and_the_report_matches_a_full_read(self):
        # On a vault a streaming client syncs, reading a file downloads it.
        write(self.root, "projects/a/plan.md", "a" * 250)
        write(self.root, "projects/b/plan.md", "a" * 250)
        write(self.root, "projects/a/same-size.md", "b" * 250)
        write(self.root, "projects/a/unique.md", "c" * 300)
        write(self.root, "projects/a/photos/unique.jpg", "d" * 400)
        write(self.root, "projects/a/photos/same-size.jpg", "a" * 250)
        full = hashes(self.root)
        real, read = Path.read_bytes, []
        with mock.patch.object(Path, "read_bytes", autospec=True,
                               side_effect=lambda p: read.append(p.name) or real(p)):
            report = clean_scan.duplicate_report(self.root)
        self.assertEqual([g["files"] for g in report["groups"]], duplicates(full))
        self.assertEqual(report["skipped"], full["skipped"])
        self.assertEqual(sorted(read), ["plan.md", "plan.md", "same-size.md"])


class FigurePairs(VaultCase):

    def test_rollup_figure_missing_from_brief_is_a_candidate_pair(self):
        # Finding 2 of the 20260916-0030 test run.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMargin: EUR6,2k\n")
        write(self.root, "README.md", "# Vault\n\nacme margin is EUR19k this year.\n")
        pairs = self.run_scan("1")["phase1"]["figure_pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["entity"], "acme")

    def test_matching_figures_produce_no_finding(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMargin: EUR19k\n")
        write(self.root, "README.md", "# Vault\n\nacme margin is EUR19k this year.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_trailing_space_and_punctuation_are_not_part_of_a_figure(self):
        # MONEY_RE kept the space before "total" and the sentence's own full stop, so the
        # same figure read as two and every matching pair was reported.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nBudget is €1,200 total.\n")
        write(self.root, "README.md", "# Vault\n\nacme cost €1,200.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_an_entity_name_inside_a_hyphenated_name_is_not_a_mention(self):
        # `\b` sits between "acme" and "-", so acme matched inside acme-website-v2.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nEUR5k\n")
        write(self.root, "projects/acme-website-v2/brief.md", "# Site\n\nEUR19k\n")
        write(self.root, "README.md", "# Vault\n\nacme-website-v2 costs EUR19k.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_a_figure_shaped_run_inside_a_link_target_is_not_a_figure(self):
        # A percent-encoded link target holding digits directly followed by "%" reads as a
        # figure to a naive scan; stripping the href before matching drops it.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMargin: EUR5k.\n")
        write(self.root, "README.md",
              "# Vault\n\nacme via [scan](sources/20260709%20Invoice.md) paid EUR10,000\n")
        pairs = self.run_scan("1")["phase1"]["figure_pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["rollup_figures"], ["EUR10,000"])

    def test_a_brief_stating_no_figure_is_not_one_side_of_a_pair(self):
        # Finding 5 of the 20260923-1124 test run: one figure in one file is not "the
        # same number, two files, two values".
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nNo figures here.\n")
        write(self.root, "README.md", "# Vault\n\nacme's accountant cost €10,000 a year.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_an_entity_name_only_inside_a_link_target_is_not_a_mention(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/business/brief.md", "# Business\n\nEUR5k baseline.\n")
        write(self.root, "README.md",
              "# Vault\n\nSee [notes](areas/business/x.md) for EUR19k context.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_an_entitys_readme_is_read_over_its_brief(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/README.md", "# Acme\n\nMargin: EUR19k\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMargin: EUR5k\n")
        write(self.root, "README.md", "# Vault\n\nacme margin is EUR19k this year.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_an_entity_with_no_brief_or_readme_is_never_one_side_of_a_pair(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/sources/quote.md", "EUR5k\n")
        write(self.root, "README.md", "# Vault\n\nacme margin is EUR19k this year.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_an_area_entity_is_compared_against_its_own_brief(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/business/brief.md", "# Business\n\nRevenue: EUR5k\n")
        write(self.root, "README.md", "# Vault\n\nbusiness revenue is EUR19k.\n")
        pairs = self.run_scan("1")["phase1"]["figure_pairs"]
        self.assertEqual([(p["entity"], p["rollup_figures"], p["brief_figures"]) for p in pairs],
                         [("business", ["EUR19k"], ["EUR5k"])])

    def test_bucket_readmes_and_dashboards_are_rollups_too(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMargin: EUR5k\n")
        write(self.root, "projects/README.md", "# Projects\n\nacme: EUR19k\n")
        write(self.root, "areas/business/Dashboard.md", "# Dash\n\nacme is at EUR20k\n")
        write(self.root, "areas/business/notes.md", "# Notes\n\nacme is at EUR30k\n")
        pairs = self.run_scan("1")["phase1"]["figure_pairs"]
        self.assertEqual(sorted(p["rollup_file"] for p in pairs),
                         ["areas/business/Dashboard.md", "projects/README.md"])

    def test_a_rollup_line_naming_an_entity_with_no_figure_is_not_a_pair(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nMargin: EUR5k\n")
        write(self.root, "README.md", "# Vault\n\nacme is going well.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["figure_pairs"], [])

    def test_the_entitys_own_brief_href_never_contributes_a_phantom_brief_figure(self):
        # A real-vault finding: an un-decoded href inside the entity's own brief (a dated
        # meeting record filename) produced a phantom figure. figure_pairs() runs on
        # cleaned lines on both sides, so a reported pair's own brief_figures list never
        # carries it.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nEUR5k baseline, see "
              "[notes](../../archive/meetings/20260709%20Call.md).\n")
        write(self.root, "README.md", "# Vault\n\nacme margin is EUR19k this year.\n")
        pairs = self.run_scan("1")["phase1"]["figure_pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["brief_figures"], ["EUR5k"])


class Archive(VaultCase):

    def test_loose_root_file_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/stray.md", "x\n")
        loose = self.run_scan("1")["phase1"]["archive"]["loose_root_files"]
        self.assertEqual(loose, ["archive/stray.md"])

    def test_loose_resources_root_file_flagged_beside_its_index(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/README.md", "# Resources\n")
        write(self.root, "resources/.gitkeep", "")
        write(self.root, "resources/playbook.md", "x\n")
        write(self.root, "resources/prompts/draft.md", "x\n")
        loose = self.run_scan("1")["phase1"]["resources_loose"]
        self.assertEqual(loose, ["resources/playbook.md"])

    def test_meetings_naming_violation_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/meetings/not-dated.md", "x\n")
        write(self.root, "archive/meetings/20260101 Kickoff.md", "x\n")
        naming = self.run_scan("1")["phase1"]["archive"]["meetings_naming"]
        self.assertEqual(naming, ["archive/meetings/not-dated.md"])

    def test_meetings_readme_is_not_a_naming_violation(self):
        write(self.root, "archive/meetings/README.md", "# archive / meetings\n")
        write(self.root, "archive/meetings/not-dated.md", "x\n")
        naming = self.run_scan("1")["phase1"]["archive"]["meetings_naming"]
        self.assertEqual(naming, ["archive/meetings/not-dated.md"])

    def test_dated_pattern_is_overridable(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/meetings/2026-01-01 Kickoff.md", "x\n")
        naming = self.run_scan("1", dated_pattern=r"^\d{4}-\d{2}-\d{2} ")["phase1"]["archive"]["meetings_naming"]
        self.assertEqual(naming, [])

    def test_archived_entity_missing_record_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/projects/acme/sources/note.md", "x\n")
        missing = self.run_scan("1")["phase1"]["archive"]["missing_record"]
        self.assertEqual(missing, ["archive/projects/acme"])

    def test_an_archived_entity_with_a_brief_or_readme_has_its_record(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/projects/done/brief.md", "# Done\n")
        write(self.root, "archive/ideas/old/README.md", "# Old\n")
        write(self.root, "archive/meetings/nested/20260101 Call.md", "x\n")
        self.assertEqual(self.run_scan("1")["phase1"]["archive"]["missing_record"], [])

    def test_an_area_archived_whole_is_one_entity_and_an_index_readme_is_not(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/old-area/README.md", "# Old area\n\n**Status:** Archived\n")
        write(self.root, "archive/old-area/sources/a.md", "a" * 250)
        write(self.root, "archive/old-area/b.md", "a" * 250)
        write(self.root, "archive/projects/README.md", "# archive / projects\n")
        write(self.root, "archive/projects/acme/sources/note.md", "x\n")
        phase1 = self.run_scan("1")["phase1"]
        self.assertEqual(phase1["archive"]["missing_record"], ["archive/projects/acme"])
        self.assertEqual([g["cross_entity"] for g in phase1["duplicates"]["groups"]], [False])

    def test_a_card_checkbox_is_misplaced_where_the_network_row_says_never(self):
        write(self.root, "CLAUDE.md", "# Vault\n\n### Where a checkbox may live\n\n"
              "| Bucket | `actions.md` | State |\n|---|---|---|\n"
              "| `areas/network/` | **never** | a checkbox on a card is a filing error |\n")
        write(self.root, "areas/network/ann-smet.md",
              "# Ann Smet\n\n## Next actions\n\n- [ ] Send the deck\n- [x] Thanked ✅ 2026-09-01\n")
        found = self.run_scan("1")["phase1"]["archive"]["misplaced_checkboxes"]
        self.assertEqual(found["areas/network"], [{"file": "areas/network/ann-smet.md", "open": 1}])
        self.assertEqual(found["closed"]["areas/network"],
                         [{"file": "areas/network/ann-smet.md", "closed": 1}])


    def test_a_meeting_record_naming_one_entity_is_a_single_owner(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "areas/finance/README.md", "# Finance\n")
        write(self.root, "archive/meetings/20260901 Kickoff.md",
              "# Kickoff\n\n**Project:** [acme](../../projects/acme/brief.md)\n")
        write(self.root, "archive/meetings/20260902 Sync.md", "# Sync\n\n**Project:** Acme\n")
        write(self.root, "archive/meetings/20260903 Board.md",
              "# Board\n\nSee [acme](../../projects/acme/brief.md) and "
              "[finance](../../areas/finance/README.md).\n")
        write(self.root, "archive/meetings/20260904 Call.md",
              "# Call\n\nOnly [acme](../../projects/acme/brief.md), twice: "
              "[again](../../projects/acme/brief.md).\n")
        write(self.root, "archive/meetings/20260905 Notes.md", "# Notes\n\nNo links.\n")
        self.assertEqual(self.run_scan("1")["phase1"]["archive"]["single_owner"], [
            {"file": "archive/meetings/20260901 Kickoff.md", "entity": "projects/acme"},
            {"file": "archive/meetings/20260902 Sync.md", "entity": "projects/acme"},
            {"file": "archive/meetings/20260904 Call.md", "entity": "projects/acme"},
        ])

    def test_a_checkbox_in_a_meeting_record_or_under_sources_is_the_records(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/meetings/20260101 Kickoff.md", "# Kickoff\n\n- [ ] Next step\n")
        write(self.root, "archive/projects/old/sources/offer.md", "# Offer\n\n- [ ] Sign\n")
        write(self.root, "archive/projects/old/notes.md", "# Notes\n\n- [ ] Left open\n")
        found = self.run_scan("1")["phase1"]["archive"]["misplaced_checkboxes"]
        self.assertEqual(found["archive"], [{"file": "archive/projects/old/notes.md", "open": 1}])


class StaleDrafts(VaultCase):

    def test_doc_beside_pdf_is_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/sources/contract.docx", "x")
        write(self.root, "projects/acme/sources/contract.pdf", "x")
        drafts = self.run_scan("1")["phase1"]["stale_drafts"]
        self.assertEqual(drafts, [{"draft": "projects/acme/sources/contract.docx",
                                   "pdf": "projects/acme/sources/contract.pdf"}])

    def test_a_draft_with_no_pdf_beside_it_is_not_stale(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/sources/proposal.docx", "x")
        write(self.root, "projects/acme/sources/Old.DOC", "x")
        write(self.root, "projects/acme/sources/Old.pdf", "x")
        drafts = self.run_scan("1")["phase1"]["stale_drafts"]
        self.assertEqual([d["draft"] for d in drafts], ["projects/acme/sources/Old.DOC"])


class Scripts(VaultCase):

    def test_an_unmarked_script_is_listed_beside_the_marked_integrations(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/scripts/outlook.py",
              "# para-os-integration: outlook 2026.10.03\n")
        write(self.root, "resources/scripts/my-mail.py", "print('mail')\n")
        write(self.root, "resources/scripts/README.md", "# scripts\n")
        got = self.run_scan("1")["phase1"]["scripts"]
        self.assertEqual(got, {"marked": [{"file": "resources/scripts/outlook.py",
                                           "name": "outlook"}],
                               "unmarked": ["resources/scripts/my-mail.py"]})

    def test_a_vault_with_no_scripts_folder_lists_none(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        self.assertEqual(self.run_scan("1")["phase1"]["scripts"], {"marked": [], "unmarked": []})


class ConflictCopies(VaultCase):

    def test_sync_conflict_copies_are_listed_with_their_survivor(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        for rel in ("projects/acme/brief.md", "projects/acme/brief (1).md",
                    "projects/acme/notes (Ann's conflicted copy 2026-10-10).md",
                    "projects/acme/data.csv",
                    "projects/acme/data.sync-conflict-20261010-101010-ABCDEFG.csv",
                    ".claude/settings.local.json", ".claude/settings.local-DESKTOP7.json",
                    "archive/old/brief.md", "archive (1)/old/other.md",
                    "projects/acme/invoice.pdf", "projects/acme/invoice-signed.pdf",
                    "projects/acme/report.md", "projects/acme/report-v2.md",
                    ".claude/skills/x/SKILL (1).md"):
            write(self.root, rel, "x\n")
        write(self.root, "archive (1)/old/brief.md", "")
        rows = self.run_scan("1")["phase1"]["conflict_copies"]
        self.assertEqual(rows, [
            {"copy": ".claude/settings.local-DESKTOP7.json",
             "survivor": ".claude/settings.local.json", "empty": False},
            {"copy": "archive (1)", "survivor": "archive", "empty": False},
            {"copy": "archive (1)/old/brief.md", "survivor": "archive/old/brief.md",
             "empty": True},
            {"copy": "projects/acme/brief (1).md", "survivor": "projects/acme/brief.md",
             "empty": False},
            {"copy": "projects/acme/data.sync-conflict-20261010-101010-ABCDEFG.csv",
             "survivor": "projects/acme/data.csv", "empty": False},
            {"copy": "projects/acme/notes (Ann's conflicted copy 2026-10-10).md",
             "survivor": None, "empty": False},
        ])


# ------------------------------------------------------------------------------------- Phase 3

class OverThreshold(VaultCase):

    def test_at_threshold_flagged(self):
        items = "\n".join(f"- [ ] Item {i}" for i in range(12))
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", f"# Acme\n\n{items}\n")
        rows = self.run_scan("3")["phase3"]["over_threshold"]
        self.assertEqual(rows, [{"file": "projects/acme/actions.md", "open": 12}])

    def test_under_threshold_not_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] One\n")
        self.assertEqual(self.run_scan("3")["phase3"]["over_threshold"], [])

    def test_a_non_action_file_over_threshold_is_flagged_too(self):
        # Finding 5: phase3-open-items.md Step 3.4 scans every checkbox-bearing file in
        # projects/ and areas/, not only action_files().
        items = "\n".join(f"- [ ] Item {i}" for i in range(12))
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/plan.md", f"# Plan\n\n{items}\n")
        rows = self.run_scan("3")["phase3"]["over_threshold"]
        self.assertEqual(rows, [{"file": "projects/acme/plan.md", "open": 12}])


class OtherCheckboxFiles(VaultCase):

    def test_a_non_action_checkbox_file_is_reported_with_its_count(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/business/session-log.md", "# Log\n\n- [ ] Review last week\n")
        rows = self.run_scan("3")["phase3"]["other_checkbox_files"]
        self.assertEqual(rows, [{"file": "areas/business/session-log.md", "open": 1}])

    def test_action_files_and_contact_files_are_excluded(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] One\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan\n\n- [ ] Follow up\n")
        rows = self.run_scan("3")["phase3"]["other_checkbox_files"]
        self.assertEqual(rows, [])

    def test_a_file_with_no_open_checkbox_is_not_reported(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/notes.md", "# Notes\n\n- [x] Done already\n")
        rows = self.run_scan("3")["phase3"]["other_checkbox_files"]
        self.assertEqual(rows, [])

    def test_a_document_under_sources_is_never_reported(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/sources/proposal.md", "# Proposal\n\n- [ ] Phase one\n")
        self.assertEqual(self.run_scan("3")["phase3"]["other_checkbox_files"], [])

    def test_resources_and_archive_are_out_of_scope(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/playbook/notes.md", "# p\n\n- [ ] Not in scope\n")
        write(self.root, "archive/projects/old/notes.md", "# n\n\n- [ ] Not in scope\n")
        rows = self.run_scan("3")["phase3"]["other_checkbox_files"]
        self.assertEqual(rows, [])


class BriefsToRead(VaultCase):

    def test_an_over_grown_brief_is_listed_for_phase_3_to_read(self):
        # Finding 6: over_grown_briefs moves from a Phase 4 pass/fail row to Phase 3's own
        # selection list, per phase3-open-items.md Step 3.5.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/wordy/brief.md", "# wordy\n" + ("line\n" * 600))
        rows = self.run_scan("3")["phase3"]["briefs_to_read"]
        self.assertEqual(rows[0]["file"], "projects/wordy/brief.md")

    def test_every_over_grown_brief_is_listed_not_the_first_three(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        for i in range(5):
            write(self.root, f"projects/wordy{i}/brief.md", "# w\n" + ("line\n" * (600 + i)))
        self.assertEqual(len(self.run_scan("3")["phase3"]["briefs_to_read"]), 5)

    def test_a_normal_length_brief_is_not_listed(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nShort.\n")
        self.assertEqual(self.run_scan("3")["phase3"]["briefs_to_read"], [])

    def test_a_brief_grown_by_more_than_half_since_the_last_deep_clean_is_read(self):
        git_init(self.root)
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n" + "line\n" * 9)
        write(self.root, "projects/calm/brief.md", "# Calm\n" + "line\n" * 9)
        git_commit_at(self.root, "2026-09-01")
        write(self.home, f"data/deep-clean/{self.root.name}.txt", "2026-09-05\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n" + "line\n" * 15)
        write(self.root, "projects/calm/brief.md", "# Calm\n" + "line\n" * 12)
        git_commit_at(self.root, "2026-09-10")
        got = self.run_scan("3")["phase3"]
        self.assertEqual(got["briefs_to_read"],
                         [{"file": "projects/acme/brief.md", "lines": 16, "reasons": ["grown"]}])
        self.assertEqual((got["briefs_skipped"], got["growth"]),
                         (["projects/calm/brief.md"], "measured"))

    def test_a_brief_holding_more_log_entries_than_open_actions_is_read(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\n## Development log\n\n"
              "- 2026-09-01 Chose the host.\n- 2026-09-02 Moved the site.\n")
        write(self.root, "projects/acme/actions.md", "# Actions\n\n- [ ] Launch\n")
        got = self.run_scan("3")["phase3"]
        self.assertEqual([(b["file"], b["reasons"]) for b in got["briefs_to_read"]],
                         [("projects/acme/brief.md", ["log_heavy"])])

    def test_growth_says_why_it_was_not_measured(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nShort.\n")
        got = self.run_scan("3")["phase3"]
        self.assertEqual((got["briefs_skipped"], got["growth"]),
                         (["projects/acme/brief.md"], "no deep clean on record"))
        write(self.home, f"data/deep-clean/{self.root.name}.txt", "2026-09-05\n")
        self.assertEqual(self.run_scan("3")["phase3"]["growth"], "no git history")


class Orphans(VaultCase):

    def test_a_file_nothing_links_to_is_an_orphan(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\nSee [the guide](resources/guide.md).\n")
        write(self.root, "resources/guide.md", "# Guide\n")
        write(self.root, "resources/old-notes.md", "# Old notes\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\n[The plan](site%20plan.md)\n")
        write(self.root, "projects/acme/site plan.md", "# Plan\n")
        write(self.root, "projects/acme/actions.md", "# Actions\n")
        write(self.root, "projects/acme/README.md", "# Acme\n")
        write(self.root, "projects/acme/sources/contract.md", "# Contract\n")
        self.assertEqual(self.run_scan("3")["phase3"]["orphans"],
                         {"files": ["resources/old-notes.md"], "folders": {}})

    def test_a_ledger_a_script_and_its_bytecode_are_no_orphans(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/logs/sessions/2026-09-20-sam-aaaaaaaa.jsonl", "{}\n")
        write(self.root, "resources/scripts/sync.py", "\n")
        write(self.root, "areas/billing/scripts/export.py", "\n")
        write(self.root, "areas/billing/tools/__pycache__/sync.cpython-312.pyc", "\n")
        write(self.root, "resources/old-notes.md", "# Old notes\n")
        self.assertEqual(self.run_scan("3")["phase3"]["orphans"]["files"],
                         ["resources/old-notes.md"])

    def test_an_entity_past_five_is_counted_across_its_subfolders(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        for n in range(3):
            write(self.root, f"areas/contracts/signed-{n}.pdf", "\n")
            write(self.root, f"areas/contracts/2026/signed-{n}.pdf", "\n")
        for n in range(5):
            write(self.root, f"projects/acme/note-{n}.md", "# Note\n")
        found = self.run_scan("3")["phase3"]["orphans"]
        self.assertEqual(found["folders"], {"areas/contracts": 6})
        self.assertEqual(found["files"], [f"projects/acme/note-{n}.md" for n in range(5)])


class StaleUndated(VaultCase):

    def test_a_tracked_item_is_measured_by_git_blame_on_its_line(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Old undated item\n")
        git_init(self.root)
        git_commit_at(self.root, "2026-01-01")
        rows = self.run_scan("3", today=TODAY)["phase3"]["stale_undated"]["projects/acme/actions.md"]
        self.assertGreaterEqual(rows[0]["days"], STALE_FILE_DAYS)

    def test_a_line_shifted_by_a_later_edit_is_still_measured_by_its_own_last_touch(self):
        # The finding this replaces git log -L for: a line edited recently, then shifted
        # to a new line number by an unrelated edit, must not be measured against the
        # older commit that first created it.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Shifted item\n")
        git_init(self.root)
        git_commit_at(self.root, "2026-01-01", "first")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Shifted item, edited\n")
        git_commit_at(self.root, "2026-08-24", "second")
        write(self.root, "projects/acme/actions.md",
              "# Acme\n\n- [ ] An unrelated item added above\n- [ ] Shifted item, edited\n")
        git_commit_at(self.root, "2026-09-20", "third")
        rows = self.run_scan("3", today=TODAY)["phase3"]["stale_undated"].get(
            "projects/acme/actions.md", [])
        self.assertNotIn("Shifted item, edited", [r["text"] for r in rows])

    def test_an_uncommitted_edit_is_unmeasurable(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Old item\n")
        git_init(self.root)
        git_commit_at(self.root, "2026-01-01")
        write(self.root, "projects/acme/actions.md",
              "# Acme\n\n- [ ] A brand new uncommitted item\n- [ ] Old item\n")
        rows = self.run_scan("3", today=TODAY)["phase3"]["stale_undated"]["projects/acme/actions.md"]
        by_text = {r["text"]: r for r in rows}
        self.assertEqual(by_text["A brand new uncommitted item"]["unmeasurable"],
                         "line not yet committed")

    def test_untracked_file_falls_back_to_mtime_per_file(self):
        # Finding 3 of the 20260916-0030 test run: a git-less vault still gets a real
        # per-file answer, not the whole check reporting "could not run".
        write(self.root, "CLAUDE.md", "# Vault\n")
        path = write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Old undated item\n")
        old = time.time() - (STALE_FILE_DAYS + 1) * 86400
        os.utime(path, (old, old))
        rows = self.run_scan("3", today=date.today())["phase3"]["stale_undated"]["projects/acme/actions.md"]
        self.assertGreaterEqual(rows[0]["days"], STALE_FILE_DAYS)

    def test_untracked_file_whose_mtime_cannot_be_read_is_unmeasurable_per_item(self):
        # A synced file can vanish between the read and the stat; each item still comes
        # back, said to be unmeasurable, rather than being dropped as fresh.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] One\n- [ ] Two\n")
        with mock.patch.object(clean_scan, "date") as fake_date:
            fake_date.fromtimestamp.side_effect = OSError("gone")
            rows = self.run_scan("3")["phase3"]["stale_undated"]["projects/acme/actions.md"]
        self.assertEqual([r["text"] for r in rows], ["One", "Two"])
        self.assertTrue(all(r["unmeasurable"].startswith("untracked") for r in rows))
        self.assertTrue(all("days" not in r for r in rows))

    def test_tracked_but_uncommitted_line_is_unmeasurable(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Old undated item\n")
        git_init(self.root)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        rows = self.run_scan("3", today=TODAY)["phase3"]["stale_undated"]["projects/acme/actions.md"]
        self.assertEqual(len(rows), 1)
        self.assertIn("unmeasurable", rows[0])

    def test_dated_item_is_never_reported_here(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Dated 📅 2026-01-01\n")
        self.assertEqual(self.run_scan("3")["phase3"]["stale_undated"], {})


class Aspirational(VaultCase):

    def test_overdue_beyond_threshold_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Blown deadline 📅 2026-01-01\n")
        rows = self.run_scan("3", today=TODAY)["phase3"]["aspirational"]["projects/acme/actions.md"]
        self.assertEqual(rows[0]["days_overdue"], (TODAY - date(2026, 1, 1)).days)

    def test_a_checkbox_file_other_than_actions_is_groomed_too(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/plan.md", "# Plan\n\n- [ ] Blown deadline 📅 2026-01-01\n")
        self.assertIn("projects/acme/plan.md",
                      self.run_scan("3", today=TODAY)["phase3"]["aspirational"])

    def test_recently_overdue_not_flagged(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Just missed it 📅 2026-09-10\n")
        self.assertEqual(self.run_scan("3", today=TODAY)["phase3"]["aspirational"], {})


class ProseNextSteps(VaultCase):

    def test_not_applicable_when_an_actions_md_exists_anywhere(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Do it\n")
        write(self.root, "projects/other/brief.md", "# Other\n\n## Next steps\n\n- A bullet\n")
        self.assertFalse(self.run_scan("3")["phase3"]["prose_next_steps"]["applicable"])

    def test_bullets_collected_under_declared_heading_only(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n## Next steps\n\n- Call the vendor\n\n## Other\n\n- Not counted\n")
        pns = self.run_scan("3")["phase3"]["prose_next_steps"]
        self.assertTrue(pns["applicable"])
        self.assertEqual([i["text"] for i in pns["items"]], ["Call the vendor"])

    def test_bullets_under_a_sub_heading_of_the_declared_heading_count(self):
        # phase3-open-items.md: "each bullet under those headings". A sub-heading groups the
        # section's bullets; it does not end the section.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n## Next steps\n\n- Top level\n\n### This week\n\n- Call vendor\n\n"
              "#### Maybe\n\n- Deeper still\n\n## Other\n\n- Not counted\n")
        pns = self.run_scan("3")["phase3"]["prose_next_steps"]
        self.assertEqual([i["text"] for i in pns["items"]],
                         ["Top level", "Call vendor", "Deeper still"])

    def test_a_declared_heading_nested_in_another_does_not_cut_the_outer_short(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n## Next steps\n\n### Open items\n\n- One\n\n### Later\n\n- Two\n\n"
              "## Background\n\n- Not counted\n")
        pns = self.run_scan("3", headings=["Next steps", "Open items"])["phase3"]["prose_next_steps"]
        self.assertEqual([i["text"] for i in pns["items"]], ["One", "Two"])

    def test_a_same_level_heading_ends_the_section(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n### Next steps\n\n- Counted\n\n### Notes\n\n- Not counted\n\n"
              "## Higher\n\n- Not counted either\n")
        pns = self.run_scan("3")["phase3"]["prose_next_steps"]
        self.assertEqual([i["text"] for i in pns["items"]], ["Counted"])

    def test_custom_heading_argument(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/business/brief.md", "# Business\n\n## Watching\n\n- Renewal date\n")
        pns = self.run_scan("3", headings=["Watching"])["phase3"]["prose_next_steps"]
        self.assertEqual([i["text"] for i in pns["items"]], ["Renewal date"])


# ------------------------------------------------------------------------------------- Phase 4

class Phase4Rows(VaultCase):

    CANDIDATE_ROWS = {"uncited_contacts", "inline_contact_details"}

    def test_clean_vault_passes_every_gate_row(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        rows = {r["check"]: r["pass"] for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]}
        gates = {check: passed for check, passed in rows.items()
                 if check not in self.CANDIDATE_ROWS}
        self.assertTrue(all(gates.values()), gates)

    def test_triage_not_empty_fails_only_that_row(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "triage/pending.md", "x\n")
        rows = {r["check"]: r["pass"] for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]}
        self.assertFalse(rows["triage_empty"])
        self.assertTrue(rows["dangling_links"])

    def test_a_loose_resources_file_fails_only_its_row(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "resources/checklist.md", "x\n")
        rows = {r["check"]: r["pass"] for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]}
        self.assertFalse(rows["resources_clean"])
        self.assertTrue(rows["archive_clean"])

    def test_an_open_checkbox_where_the_vault_forbids_one_fails_its_row(self):
        write(self.root, "CLAUDE.md", "# Vault\n\n### Where a checkbox may live\n\n| Bucket | "
              "`actions.md` | State |\n|---|---|---|\n| `areas/network/` | **never** | an error |\n")
        write(self.root, "resources/prompts/p.md", "# P\n\n- [ ] Send the deck\n")
        write(self.root, "areas/network/ann-smet.md", "# Ann Smet\n\n- [ ] Send the deck\n")
        row = next(r for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]
                   if r["check"] == "misplaced_checkboxes")
        self.assertFalse(row["pass"])
        self.assertEqual([row["detail"][b][0]["file"] for b in ("resources", "areas/network")],
                         ["resources/prompts/p.md", "areas/network/ann-smet.md"])

    def test_aspirational_row_reports_detail(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Blown deadline 📅 2026-01-01\n")
        rows = self.run_scan("4", today=TODAY)["phase4"]["rows"]
        row = next(r for r in rows if r["check"] == "aspirational_dates")
        self.assertFalse(row["pass"])
        self.assertIn("projects/acme/actions.md", row["detail"])

    def test_over_grown_briefs_is_no_longer_a_phase_4_row(self):
        # Finding 6: brief length is never a Phase 4 gate; it feeds Phase 3's
        # briefs_to_read selection instead.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/wordy/brief.md", "# wordy\n" + ("line\n" * 600))
        checks = {r["check"] for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]}
        self.assertNotIn("over_grown_briefs", checks)

    def test_uncited_row_labels_cards_and_card_file_pairs(self):
        # Issue #37: Phase 1 groups by card, so a bare pair count read as a regression.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nJan Claes called.\n")
        write(self.root, "projects/beta/brief.md", "# Beta\n\nJan Claes called.\n")
        rows = {r["check"]: r for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]}
        self.assertEqual(rows["uncited_contacts"]["detail"], {"cards": 1, "card_files": 2})
        phase1 = self.run_scan("1")["phase1"]["uncited_contacts"]
        self.assertEqual((len(phase1), sum(len(c["files"]) for c in phase1)), (1, 2))

    def test_over_threshold_row_counts_the_files_phase_3_grooms(self):
        # Issue #37: a contract-less plan with 12 open items passed Phase 4 while Phase 3
        # flagged it. Whether it declares its own contract is the skill's ruling.
        items = "\n".join(f"- [ ] Item {i}" for i in range(12))
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/plan.md", f"# Plan\n\n{items}\n")
        row = next(r for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]
                   if r["check"] == "over_threshold_files")
        self.assertIsNone(row["pass"])
        self.assertEqual(row["detail"], self.run_scan("3")["phase3"]["over_threshold"])
        write(self.root, "projects/acme/actions.md", f"# Acme\n\n{items}\n")
        row = next(r for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]
                   if r["check"] == "over_threshold_files")
        self.assertFalse(row["pass"])
        self.assertEqual(len(row["detail"]), 2)

    def test_uncited_and_inline_rows_report_pass_none_with_a_candidate_count(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nJan Claes flagged a risk, reach him at jan.claes@example.com.\n")
        rows = {r["check"]: r for r in self.run_scan("4", today=TODAY)["phase4"]["rows"]}
        self.assertIsNone(rows["uncited_contacts"]["pass"])
        self.assertEqual(rows["uncited_contacts"]["detail"], {"cards": 1, "card_files": 1})
        self.assertIsNone(rows["inline_contact_details"]["pass"])
        self.assertEqual(rows["inline_contact_details"]["detail"], 1)


# --------------------------------------------------------------------------------- snapshot

class Snapshot(VaultCase):

    def test_snapshot_detects_a_later_edit(self):
        # Finding 3 of the 20260915-2146 test run: check changed() before a write.
        write(self.root, "CLAUDE.md", "# Vault\n")
        path = write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] One\n")
        before = self.run_scan("3")["phase3"]["snapshot"]
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] One\n- [ ] Two\n")
        self.assertIn(str(path), changed(before))

    def test_every_phase_output_carries_a_snapshot_the_changed_check_finds(self):
        # The re-check reads the whole scan output, as para-shared/scripts.md tells a skill
        # to pass it: an unchanged vault must read as unchanged in every phase.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] One\n")
        for phase in ("1", "3", "4"):
            snap = scan_snapshot(self.run_scan(phase))
            self.assertIsNotNone(snap, phase)
            self.assertEqual(changed(snap), [], phase)


# ---------------------------------------------------------------------------------- refusals

# ------------------------------------------------------------------------------ command line

class CommandLine(VaultCase):
    """main() as SKILL.md's Step 0 calls it: --vault, --phase and the optional flags, one
    JSON document on stdout and an exit code the skill reads."""

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def run_json(self, *args):
        code, out, err = self.run_main("--vault", str(self.root), *args)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def usage_error(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as raised:
            main(list(args))
        self.assertEqual(raised.exception.code, 2)
        return err.getvalue()

    def test_each_phase_prints_one_document_carrying_only_its_own_findings(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        for phase in ("1", "3", "4"):
            report = self.run_json("--phase", phase, "--today", "2026-09-22")
            self.assertEqual(set(report), {"preconditions", f"phase{phase}"}, phase)
            self.assertIn("snapshot", report[f"phase{phase}"])

    def test_uncited_contact_declarations_reach_the_scan(self):
        write(self.root, "CLAUDE.md", LEAD_LIFECYCLE)
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        write(self.root, "resources/newsletter/issue.md", "# Issue\n\nJan Claes wrote.\n")
        write(self.root, "areas/business/leads.md",
              "# Leads\n\n| Company | Contact |\n|---|---|\n| Orchard | Jan Claes |\n")
        for phase in ("1", "4"):
            report = self.run_json("--phase", phase, "--generated-dir", "resources/newsletter")
            if phase == "1":
                self.assertEqual(report["phase1"]["uncited_contacts"], [])
            else:
                rows = {r["check"]: r["detail"] for r in report["phase4"]["rows"]}
                self.assertEqual(rows["uncited_contacts"], {"cards": 0, "card_files": 0})

    def test_ref_defaults_to_origin_stable_and_the_marker_is_not_found_without_a_clone(self):
        write(self.root, "CLAUDE.md", marker_claude_md("2026.09.05"))
        marker = self.run_json("--phase", "1")["preconditions"]["template_marker"]
        self.assertEqual(marker["verdict"], "no_clone")
        self.assertFalse(marker["ref_missing"])

    def test_the_default_ref_reads_origin_stable_and_a_clone_without_it_is_unverified(self):
        clone = self.clone(base_marker="2026.09.05")
        write(self.root, "CLAUDE.md", marker_claude_md("2026.08.01"))
        missing = self.run_json("--phase", "1", "--clone", str(clone))
        subprocess.run(["git", "update-ref", "refs/remotes/origin/stable", "HEAD"], cwd=clone,
                       check=True, capture_output=True)
        present = self.run_json("--phase", "1", "--clone", str(clone))
        missing, present = (r["preconditions"]["template_marker"] for r in (missing, present))
        self.assertEqual((missing["master"], missing["verdict"], missing["ref_missing"]),
                         (None, "unverified", True))
        self.assertEqual((present["master"], present["verdict"], present["ref_missing"]),
                         ("2026.09.05", "behind", False))

    def test_clone_and_ref_reach_the_template_marker_precondition(self):
        clone = self.clone(base_marker="2026.09.05")
        write(self.root, "CLAUDE.md", marker_claude_md("2026.08.01"))
        marker = self.run_json("--phase", "1", "--clone", str(clone),
                               "--ref", "HEAD")["preconditions"]["template_marker"]
        self.assertEqual((marker["master"], marker["verdict"]), ("2026.09.05", "behind"))

    def test_templates_dir_is_repeatable(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "areas/network/jan-claes.md", "# Jan Claes\n")
        for folder in ("resources/tmpl-a", "resources/tmpl-b", "resources/real"):
            write(self.root, f"{folder}/note.md", "# Note\n\nDear Jan Claes,\n")
        report = self.run_json("--phase", "1", "--templates-dir", "resources/tmpl-a",
                               "--templates-dir", "resources/tmpl-b")
        self.assertEqual([f for c in report["phase1"]["uncited_contacts"] for f in c["files"]],
                         ["resources/real/note.md"])

    def test_dated_pattern_reaches_the_meetings_naming_check(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "archive/meetings/2026-01-01 Kickoff.md", "x\n")
        write(self.root, "archive/meetings/20260101 Kickoff.md", "x\n")
        report = self.run_json("--phase", "1", "--dated-pattern", r"^\d{4}-\d{2}-\d{2} ")
        self.assertEqual(report["phase1"]["archive"]["meetings_naming"],
                         ["archive/meetings/20260101 Kickoff.md"])

    def test_next_steps_heading_replaces_the_defaults_rather_than_adding_to_them(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n## Next steps\n\n- Default heading\n\n## Watching\n\n- Renewal\n\n"
              "## Parked\n\n- Later\n")
        report = self.run_json("--phase", "3", "--next-steps-heading", "Watching",
                               "--next-steps-heading", "Parked")
        self.assertEqual([i["text"] for i in report["phase3"]["prose_next_steps"]["items"]],
                         ["Renewal", "Later"])

    def test_indent_pretty_prints_the_same_document(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        code, out, _ = self.run_main("--vault", str(self.root), "--phase", "4",
                                     "--today", "2026-09-22", "--indent", "2")
        self.assertEqual(code, 0)
        self.assertIn('\n  "phase4": {', out)
        self.assertIn("phase4", json.loads(out))

    def test_a_malformed_today_is_a_usage_error(self):
        write(self.root, "CLAUDE.md", "# Vault\n")
        err = self.usage_error("--vault", str(self.root), "--phase", "1", "--today", "22/09/2026")
        self.assertIn("--today wants YYYY-MM-DD", err)

    def test_a_vault_path_that_is_not_a_folder_is_a_usage_error(self):
        err = self.usage_error("--vault", str(self.root / "missing"), "--phase", "1")
        self.assertIn("no such vault", err)

    def test_phase_is_required_and_phase_2_has_no_scan(self):
        self.assertIn("--phase", self.usage_error("--vault", str(self.root)))
        self.assertIn("invalid choice", self.usage_error("--vault", str(self.root), "--phase", "2"))


class ScriptRun(VaultCase):
    """The script as a separate process, run from the vault with `--vault .` and its stdout
    redirected, as SKILL.md and para-shared/scripts.md run it."""

    def run_script(self, *args, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.root,
                              capture_output=True, timeout=120, env=env)

    def test_output_is_utf8_json_even_where_the_pipe_defaults_to_ascii(self):
        # A Windows pipe defaults to a codepage that cannot encode what a vault holds;
        # PYTHONIOENCODING=ascii reproduces that on every platform.
        write(self.root, "CLAUDE.md", "# Vault\n")
        write(self.root, "README.md", "# Vault\n\n## Identity\n\nn/a\n")
        write(self.root, "areas/network/zoe-peeters.md", "# Zoë Peeters\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n\nZoë Peeters called.\n")
        result = self.run_script("--vault", ".", "--phase", "1", "--today", "2026-09-22",
                                 env=dict(os.environ, PYTHONIOENCODING="ascii"))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        report = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual([c["name"] for c in report["phase1"]["uncited_contacts"]],
                         ["Zoë Peeters"])

    def test_the_saved_output_feeds_the_shared_changed_check(self):
        # scripts.md's re-check before a delete or move: the saved scan output, snapshot
        # nested under its phase key, read back by paraos_vault.py changed.
        write(self.root, "CLAUDE.md", "# Vault\n")
        actions = write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] One\n")
        result = self.run_script("--vault", ".", "--phase", "3", "--today", "2026-09-22")
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        with tempfile.TemporaryDirectory() as out_dir:
            saved = Path(out_dir) / "scan.json"
            saved.write_bytes(result.stdout)
            check = [sys.executable, str(SHARED_SCRIPT), "changed", str(saved)]
            unchanged = subprocess.run(check, capture_output=True, timeout=60)
            self.assertEqual(unchanged.returncode, 0, unchanged.stdout)
            actions.write_text("# Acme\n\n- [ ] One\n- [ ] Two\n", encoding="utf-8")
            edited = subprocess.run(check, capture_output=True, timeout=60)
            self.assertEqual(edited.returncode, 1)
            self.assertEqual(json.loads(edited.stdout.decode("utf-8"))["changed"],
                         [str(actions.resolve())])


class MissingLibrary(unittest.TestCase):

    def test_missing_shared_library_exits_2(self):
        script = SCRIPT
        with tempfile.TemporaryDirectory() as tmp:
            isolated = Path(tmp) / "skills" / "para-deep-clean" / "scripts"
            isolated.mkdir(parents=True)
            shutil.copy(script, isolated / "clean_scan.py")
            result = subprocess.run(
                [sys.executable, str(isolated / "clean_scan.py"), "--vault", ".", "--phase", "1"],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertIn("clean_scan:", result.stderr)
            self.assertIn("install para-shared", result.stderr)
            self.assertNotIn("by hand", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
