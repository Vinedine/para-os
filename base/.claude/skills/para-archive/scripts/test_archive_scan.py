#!/usr/bin/env python3
"""Tests for archive_scan.py. Each one pins a rule references/reconcile.md or
references/move.md states in prose.

    python3 test_archive_scan.py
    py -3 test_archive_scan.py

Standard library only, so a vault that runs the skill can run its tests. Every fixture is a
throwaway vault in a temporary directory, with synthetic names only: nothing reads or writes
a real vault, and nothing calls a model. The date is passed in, never taken from the clock.

What paraos_vault.py itself decides (resolving an entity, the registry, header fields, stage
lines, lifecycle tables, tasks, links, snapshots) is tested beside it, in
para-shared/scripts/test_paraos_vault.py. What is tested here is what this skill alone
decides: the default destination and its version suffix, how a Backlog item is parsed and
judged settled, how a lifecycle's reason line is parsed from a vault's own rule-file prose,
how an inbound reference is classified, and what a verify pass has to re-check after a move.
"""

import io
import json
import contextlib
import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from archive_scan import CollectedVault, main, plan, reason_allowed, verify

TODAY = date(2026, 9, 22)

DEAL_LIFECYCLE = "\n".join([
    "# Vault", "",
    "**Type:** vault", "**Modules:** sales", "",
    "## Deal lifecycle", "",
    "| Stage | PARA home |",
    "|---|---|",
    "| Lead | `areas/business/leads.md` (row) |",
    "| Qualified | `resources/ideas/<company>/` |",
    "| Goal | `projects/<company>/` |",
    "| Lost | `archive/ideas/<company>/` |", "",
]) + "\n"

# The real wording of addons/sales/.claude/rules/deal-brief.md's "A lost deal carries one
# more line" paragraph, the parser's one contract.
DEAL_BRIEF_RULE = (
    "---\n"
    "paths:\n"
    '  - "resources/ideas/*/brief.md"\n'
    "---\n\n"
    "# Deal brief\n\n"
    "**A lost deal carries one more line**, directly under `Stage`: "
    "`**Lost reason:** <reason>, <one free clause>`, the reason being one of "
    "**no decision**, **timing**, **budget**, **went elsewhere**, **not a fit**, "
    "**relationship only**. The free clause is what a later reader needs and the list "
    "cannot hold. `/para-archive` refuses the move to `archive/ideas/` without it.\n"
)


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def git_init(root):
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


class VaultCase(unittest.TestCase):
    """A temporary vault root per test, removed afterwards."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for d in ("projects", "areas", "archive"):
            (self.root / d).mkdir()
        write(self.root, "CLAUDE.md", "# Vault\n\n**Type:** vault\n")

    def declare_deal_lifecycle(self):
        write(self.root, "CLAUDE.md", DEAL_LIFECYCLE)
        write(self.root, ".claude/rules/deal-brief.md", DEAL_BRIEF_RULE)

    def plan(self, entity, destination=None, today=TODAY, paraos_home=None, route=()):
        report, code = plan(self.root, entity, destination, today, paraos_home, route)
        self.assertEqual(code, 0)
        return report

    def verify(self, moved_from, moved_to, routed=()):
        report, code = verify(self.root, moved_from, moved_to, list(routed))
        self.assertEqual(code, 0)
        return report


# ------------------------------------------------------------------------------ vault root

class VaultRoot(unittest.TestCase):

    def test_exit_3_on_a_non_root_names_the_registered_vault_that_contains_it(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        vault = root / "vaults" / "BF"
        (vault / "projects").mkdir(parents=True)
        (vault / "areas").mkdir()
        write(vault, "CLAUDE.md", "# Vault\n")
        subdir = vault / "subdir"
        subdir.mkdir()
        home = root / "paraoshome"
        home.mkdir()
        write(home, "vaults.json",
              json.dumps([{"name": "BF", "path": str(vault), "kind": "personal"}]))

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--vault", str(subdir), "--entity", "acme",
                        "--paraos-home", str(home)])
        self.assertEqual(code, 3)
        out = json.loads(buf.getvalue())
        self.assertFalse(out["vault"]["root"])
        self.assertIn("projects/", out["vault"]["missing"])
        self.assertEqual(out["vault"]["hint"], {"name": "BF", "path": str(vault)})

    def test_exit_3_names_no_hint_when_the_registry_holds_nothing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        root.mkdir(exist_ok=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--vault", str(root), "--entity", "acme",
                        "--paraos-home", str(root / "nohome")])
        self.assertEqual(code, 3)
        out = json.loads(buf.getvalue())
        self.assertIsNone(out["vault"]["hint"])

    def test_exit_2_on_a_collected_vault(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for d in ("projects", "areas", "archive"):
            (root / d).mkdir()
        write(root, "CLAUDE.md", "# Vault\n")
        write(root, "resources/mds/projects__acme__brief.md", "# acme\n")
        with self.assertRaises(CollectedVault):
            plan(root, "acme", None, TODAY, None)

    def test_a_nonexistent_vault_path_exits_3_with_json_rather_than_bare_usage_text(self):
        # A typo'd or stale --vault used to hit argparse's own "no such vault" error before
        # vault_block ever ran, exiting 2 with no JSON at all - a different failure shape
        # from every other non-root path, against SKILL.md and the docstring both.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        missing = Path(tmp.name) / "does-not-exist-at-all"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--vault", str(missing), "--entity", "acme"])
        self.assertEqual(code, 3)
        out = json.loads(buf.getvalue())
        self.assertFalse(out["vault"]["root"])
        self.assertEqual(set(out["vault"]["missing"]),
                         {"projects/", "areas/ or archive/", "CLAUDE.md"})


# --------------------------------------------------------------------------------- entity

class EntityResolution(VaultCase):

    def test_a_project_resolves_by_exact_name(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        r = self.plan("acme")
        self.assertEqual(r["entity"]["status"], "resolved")
        self.assertEqual(r["entity"]["kind"], "project")
        self.assertEqual(r["entity"]["source"], "projects/acme")

    def test_an_idea_resolves_by_a_unique_partial_name(self):
        write(self.root, "resources/ideas/acme-website/brief.md", "# Acme website\n")
        r = self.plan("website")
        self.assertEqual(r["entity"]["status"], "resolved")
        self.assertEqual(r["entity"]["kind"], "idea")
        self.assertEqual(r["entity"]["source"], "resources/ideas/acme-website")

    def test_an_area_resolves_when_a_folder_under_areas_matches(self):
        write(self.root, "areas/harbor-website/brief.md", "# Harbor website\n")
        r = self.plan("harbor-website")
        self.assertEqual(r["entity"]["kind"], "area")

    def test_ambiguous_reports_candidates_and_nothing_else(self):
        write(self.root, "projects/acme-a/brief.md", "# A\n")
        write(self.root, "projects/acme-b/brief.md", "# B\n")
        e = self.plan("acme")["entity"]
        self.assertEqual(e["status"], "ambiguous")
        self.assertEqual(sorted(e["candidates"]), ["projects/acme-a", "projects/acme-b"])
        self.assertIsNone(e["this_vault"])

    def test_an_elsewhere_hit_under_archive_is_named_already_archived(self):
        write(self.root, "archive/projects/acme/brief.md", "# Acme\n")
        e = self.plan("acme")["entity"]
        self.assertEqual(e["status"], "elsewhere")
        self.assertEqual(e["already_archived"], "archive/projects/acme")

    def test_unresolved_lists_this_vaults_own_folders_and_other_vaults(self):
        write(self.root, "projects/harbor/brief.md", "# Harbor\n")
        write(self.root, "resources/ideas/dune/brief.md", "# Dune\n")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name)
        other = home / "other-vault"
        (other / "projects" / "acme").mkdir(parents=True)
        write(home, "vaults.json",
              json.dumps([{"name": "other", "path": str(other), "kind": "personal"}]))
        e = self.plan("acme", paraos_home=str(home))["entity"]
        self.assertEqual(e["status"], "unresolved")
        self.assertEqual(e["this_vault"], {"projects": ["harbor"],
                                           "resources/ideas": ["dune"]})
        self.assertEqual(len(e["other_vaults"]), 1)
        self.assertEqual(e["other_vaults"][0]["vault"], "other")

    def test_entity_not_resolved_leaves_every_other_block_null(self):
        r = self.plan("nothing-like-this")
        self.assertIsNone(r["destination"])
        self.assertIsNone(r["lifecycle"])
        self.assertIsNone(r["actions"])
        self.assertIsNone(r["gate"])
        self.assertIsNone(r["inbound"])
        self.assertIsNone(r["move_plan"])
        self.assertEqual(r["snapshot"], {})


# ---------------------------------------------------------------------------- destination

class Destination(VaultCase):

    def test_default_destination_for_a_project(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        d = self.plan("acme")["destination"]
        self.assertEqual(d["path"], "archive/projects/acme")
        self.assertTrue(d["default"])
        self.assertFalse(d["exists"])

    def test_default_destination_for_an_idea(self):
        write(self.root, "resources/ideas/acme/brief.md", "# Acme\n")
        d = self.plan("acme")["destination"]
        self.assertEqual(d["path"], "archive/ideas/acme")

    def test_an_area_has_no_default_and_needs_a_vault_rule(self):
        write(self.root, "areas/harbor-website/brief.md", "# Harbor website\n")
        d = self.plan("harbor-website")["destination"]
        self.assertIsNone(d["path"])
        self.assertTrue(d["needs_vault_rule"])

    def test_an_area_destination_override_settles_it(self):
        write(self.root, "areas/harbor-website/brief.md", "# Harbor website\n")
        d = self.plan("harbor-website", destination="archive/websites/harbor-website")["destination"]
        self.assertEqual(d["path"], "archive/websites/harbor-website")
        self.assertFalse(d["default"])
        self.assertFalse(d["needs_vault_rule"])

    def test_destination_that_already_exists_is_flagged(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "archive/projects/acme/brief.md", "# Already there\n")
        d = self.plan("acme")["destination"]
        self.assertTrue(d["exists"])

    def test_suffix_siblings_and_next_suffix(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "archive/projects/acme-v1/brief.md", "# v1\n")
        write(self.root, "archive/projects/acme-v2/brief.md", "# v2\n")
        write(self.root, "archive/projects/acme-other/brief.md", "# not a sibling\n")
        d = self.plan("acme")["destination"]
        self.assertEqual(sorted(d["suffix_siblings"]), ["acme-v1", "acme-v2"])
        self.assertEqual(d["next_suffix"], 3)

    def test_next_suffix_is_1_with_no_existing_siblings(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        d = self.plan("acme")["destination"]
        self.assertEqual(d["suffix_siblings"], [])
        self.assertEqual(d["next_suffix"], 1)

    def test_ideas_and_areas_carry_no_suffix_fields(self):
        write(self.root, "resources/ideas/acme/brief.md", "# Acme\n")
        d = self.plan("acme")["destination"]
        self.assertNotIn("suffix_siblings", d)
        self.assertNotIn("next_suffix", d)


# ---------------------------------------------------------------------------- lifecycle

class Lifecycle(VaultCase):

    def test_no_lifecycle_when_the_entity_carries_no_stage_line(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n\nOrdinary project.\n")
        self.assertIsNone(self.plan("acme")["lifecycle"])

    def test_no_lifecycle_when_the_stage_matches_no_declared_name(self):
        self.declare_deal_lifecycle()
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** idea (concept only)\n")
        self.assertIsNone(self.plan("acme")["lifecycle"])

    def test_reason_allowed_parses_the_real_deal_brief_wording(self):
        write(self.root, ".claude/rules/deal-brief.md", DEAL_BRIEF_RULE)
        allowed = reason_allowed(self.root, "Lost")
        self.assertEqual(allowed, ["no decision", "timing", "budget", "went elsewhere",
                                   "not a fit", "relationship only"])

    def test_an_abbreviation_inside_the_list_does_not_end_it(self):
        # The list was cut at the first ".", so "e.g." dropped every value after it.
        write(self.root, ".claude/rules/deal-brief.md",
              "**A lost deal** carries `**Lost reason:** <reason>`, the reason being one of "
              "**no decision**, **price** (e.g. over budget), **timing**, **n.v.t.** or "
              "**not a fit**. The free clause follows.\n")
        self.assertEqual(reason_allowed(self.root, "Lost"),
                         ["no decision", "price", "timing", "n.v.t.", "not a fit"])

    def test_a_rule_file_declaring_no_reason_gives_allowed_null(self):
        write(self.root, ".claude/rules/other.md", "# Other rule\n\nNothing about reasons.\n")
        self.assertIsNone(reason_allowed(self.root, "Lost"))

    def test_no_rules_dir_at_all_gives_allowed_null(self):
        self.assertIsNone(reason_allowed(self.root, "Lost"))

    def test_stage_not_yet_terminal_flags_the_line_as_not_naming_the_destination(self):
        self.declare_deal_lifecycle()
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-08-01\n")
        lc = self.plan("acme")["lifecycle"]
        self.assertEqual(lc["current_stage"], "Qualified")
        self.assertEqual(lc["destination_matches"], "Lost")
        self.assertFalse(lc["stage_line_names_destination"])
        self.assertIsNone(lc["reason"]["raw"])

    def test_stage_already_terminal_with_a_valid_reason(self):
        self.declare_deal_lifecycle()
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Lost (since 2026-09-15)\n"
              "**Lost reason:** relationship only, went cold\n**Opened:** 2026-08-01\n")
        lc = self.plan("acme")["lifecycle"]
        self.assertTrue(lc["stage_line_names_destination"])
        self.assertEqual(lc["reason"]["key"], "relationship only")
        self.assertIn("relationship only", lc["reason"]["allowed"])

    def test_reason_present_but_not_in_the_allowed_list(self):
        self.declare_deal_lifecycle()
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Lost (since 2026-09-15)\n"
              "**Lost reason:** ghosted us, no further contact\n**Opened:** 2026-08-01\n")
        lc = self.plan("acme")["lifecycle"]
        self.assertEqual(lc["reason"]["key"], "ghosted us")
        self.assertNotIn(lc["reason"]["key"], lc["reason"]["allowed"])

    def test_both_stage_and_reason_missing_at_once(self):
        self.declare_deal_lifecycle()
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Goal (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        lc = self.plan("acme")["lifecycle"]
        self.assertFalse(lc["stage_line_names_destination"])
        self.assertIsNone(lc["reason"]["raw"])

    def test_terminal_stages_are_made_concrete_for_this_entity(self):
        self.declare_deal_lifecycle()
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-08-01\n")
        lc = self.plan("acme")["lifecycle"]
        self.assertEqual(lc["terminal_stages"],
                         [{"name": "Lost", "home": "archive/ideas/<company>/",
                           "concrete_home": "archive/ideas/acme"}])


# ------------------------------------------------------------------------------- actions

class Actions(VaultCase):

    def test_no_actions_file_reports_file_null(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        a = self.plan("acme")["actions"]
        self.assertIsNone(a["file"])
        self.assertEqual(a["done"], [])
        self.assertEqual(a["open"], [])

    def test_open_task_carries_ahead_when_its_date_is_on_or_after_today(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Still ahead 📅 2026-09-22\n- [ ] Already past 📅 2026-09-01\n")
        a = self.plan("acme")["actions"]
        ahead = {t["text"]: t["ahead"] for t in a["open"]}
        self.assertTrue(ahead["Still ahead"])
        self.assertFalse(ahead["Already past"])

    def test_a_fenced_checkbox_is_never_counted_open(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\nSample shape:\n\n```\n- [ ] Not a real task\n```\n\n"
              "- [ ] Real task\n")
        a = self.plan("acme")["actions"]
        self.assertEqual([t["text"] for t in a["open"]], ["Real task"])

    def test_a_settled_backlog_item_is_not_open(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n"
              "- Considered a rebrand. Decided against it after the pitch.\n"
              "- Still genuinely open, no resolution yet.\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        by_text = {b["text"]: b for b in backlog}
        settled = next(v for k, v in by_text.items() if k.startswith("Considered"))
        open_one = next(v for k, v in by_text.items() if k.startswith("Still"))
        self.assertTrue(settled["settled"])
        self.assertEqual(settled["by"], "Decided")
        self.assertFalse(open_one["settled"])
        self.assertIsNone(open_one["by"])

    def test_a_lowercase_done_inside_a_sentence_is_not_settled(self):
        # reconcile.md Step 2: the match is a capitalised Done, Decided or Resolved as a
        # whole word, case-sensitive - a lowercase "done" inside a condition is not a
        # disposition, and reading it as one would silently skip asking about live work.
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n"
              "- Revisit once the migration is done, no capital marker here.\n")
        item = self.plan("acme")["actions"]["backlog"][0]
        self.assertFalse(item["settled"])
        self.assertIsNone(item["by"])

    def test_backlog_is_read_from_both_actions_and_brief(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n## Backlog\n- A brief-side idea, still open.\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n- An actions-side idea, still open.\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        files = {b["file"] for b in backlog}
        self.assertEqual(files, {"projects/acme/brief.md", "projects/acme/actions.md"})

    def test_a_fenced_backlog_sample_is_never_an_item(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n```\n- A sample line, not a real backlog item.\n```\n")
        self.assertEqual(self.plan("acme")["actions"]["backlog"], [])

    def test_a_prose_backlog_section_is_read_as_paragraphs(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n"
              "First paragraph, still open.\n\nSecond paragraph. Decided to skip it.\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        self.assertEqual(len(backlog), 2)
        self.assertFalse(backlog[0]["settled"])
        self.assertTrue(backlog[1]["settled"])

    def test_a_checkbox_between_bullets_is_not_folded_into_the_bullet_above(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n"
              "- Migrate CRM to new vendor\n- [x] Decided on vendor shortlist\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        self.assertEqual([(b["text"], b["settled"]) for b in backlog],
                         [("Migrate CRM to new vendor", False)])

    def test_prose_before_the_first_bullet_is_an_item_too(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n"
              "Revisit the loyalty tie-in.\n\n- Rebuild the site\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        self.assertEqual([b["text"] for b in backlog],
                         ["Revisit the loyalty tie-in.", "Rebuild the site"])

    def test_prose_after_a_blank_line_is_not_folded_into_the_bullet_above(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n"
              "- Migrate the export. Done: moved to the new system.\n\n"
              "Renegotiate the Wi-Fi SLA before the season opens.\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        self.assertEqual([(b["text"], b["settled"]) for b in backlog],
                         [("Migrate the export. Done: moved to the new system.", True),
                          ("Renegotiate the Wi-Fi SLA before the season opens.", False)])

    def test_a_bullet_keeps_its_lazy_and_indented_continuations(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n"
              "- Rebuild the site\nonce the brand refresh lands.\n\n"
              "  Decided: after the season.\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        self.assertEqual([(b["text"], b["settled"]) for b in backlog],
                         [("Rebuild the site once the brand refresh lands. "
                           "Decided: after the season.", True)])

    def test_items_under_a_backlog_subheading_are_still_backlog(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n## Backlog\n- Now-ish\n\n### Later\n- Rebuild site\n"
              "\n## Recurring\n- Not backlog\n")
        backlog = self.plan("acme")["actions"]["backlog"]
        self.assertEqual([b["text"] for b in backlog], ["Now-ish", "Rebuild site"])

    def test_other_checkbox_files_names_a_stray_file_and_whether_it_is_in_sources(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/plan.md", "# Plan\n\n- [ ] Stray open item\n")
        write(self.root, "projects/acme/sources/notes.md", "# Notes\n\n- [ ] Also stray\n")
        other = self.plan("acme")["actions"]["other_checkbox_files"]
        by_file = {o["file"]: o for o in other}
        self.assertEqual(by_file["projects/acme/plan.md"]["count"], 1)
        self.assertFalse(by_file["projects/acme/plan.md"]["in_sources"])
        self.assertTrue(by_file["projects/acme/sources/notes.md"]["in_sources"])

    def test_idea_holds_actions_flags_a_filing_error(self):
        write(self.root, "resources/ideas/acme/brief.md", "# Acme\n")
        write(self.root, "resources/ideas/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Should not be here\n")
        self.assertTrue(self.plan("acme")["actions"]["idea_holds_actions"])

    def test_idea_with_no_actions_file_does_not_flag(self):
        write(self.root, "resources/ideas/acme/brief.md", "# Acme\n")
        self.assertFalse(self.plan("acme")["actions"]["idea_holds_actions"])


# ---------------------------------------------------------------------------------- gate

class Gate(VaultCase):

    def test_status_line_prefers_the_status_field_over_stage_line(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n\n**Status:** shipped\n")
        self.assertEqual(self.plan("acme")["gate"]["status_line"], "shipped")

    def test_status_line_falls_back_to_stage_line_with_no_status_field(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n\nJust an opening line.\n")
        self.assertEqual(self.plan("acme")["gate"]["status_line"], "Just an opening line.")

    def test_open_dated_and_future_dated_lines_are_reported_separately(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n**Status:** open\n\nWe expect to renew by 2026-10-01.\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Wrap-up call 📅 2026-09-25\n- [ ] Undated item\n")
        g = self.plan("acme")["gate"]
        self.assertEqual(g["status_line"], "open")
        self.assertEqual([t["text"] for t in g["open_dated"]], ["Wrap-up call"])
        self.assertEqual([f["text"] for f in g["future_dated_lines"]],
                         ["We expect to renew by 2026-10-01."])

    def test_a_stale_status_line_is_not_conflated_with_live_work(self):
        # The done-gate reads live work only, not a status line Step 3 exists to retense
        # (CHANGELOG 2026.09.04, /para-archive committed bugs).
        write(self.root, "projects/acme/brief.md", "# Acme\n\n**Status:** open\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n- [x] Everything is actually done ✅ 2026-09-01\n")
        g = self.plan("acme")["gate"]
        self.assertEqual(g["status_line"], "open")
        self.assertEqual(g["open_dated"], [])

    def test_a_date_inside_a_code_span_is_not_a_future_dated_line(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nSee the log filed as `20261001 example.md`.\n")
        self.assertEqual(self.plan("acme")["gate"]["future_dated_lines"], [])

    def test_a_date_inside_a_fence_is_not_a_future_dated_line(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n```\nSample: renew by 2026-10-01\n```\n")
        self.assertEqual(self.plan("acme")["gate"]["future_dated_lines"], [])

    def test_a_past_date_is_not_a_future_dated_line(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nThis renewed on 2026-01-01 already.\n")
        self.assertEqual(self.plan("acme")["gate"]["future_dated_lines"], [])

    def test_a_date_inside_a_link_target_is_not_a_future_dated_line(self):
        # A filed meeting note's own dated filename in a link's target is not a stated
        # future event - only its display text, or plain prose, is.
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nSee [notes](../../archive/meetings/2026-10-01-notes.md).\n")
        self.assertEqual(self.plan("acme")["gate"]["future_dated_lines"], [])

    def test_a_date_inside_link_display_text_is_still_a_future_dated_line(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\nSee [renew by 2026-10-01](../../brief.md).\n")
        lines = self.plan("acme")["gate"]["future_dated_lines"]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["text"], "See [renew by 2026-10-01](../../brief.md).")


# ------------------------------------------------------------------------------- inbound

class Inbound(VaultCase):

    def test_the_four_reference_shapes_are_all_classified_as_references(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "areas/network/jan.md", "\n".join([
            "# Jan", "",
            "Working with [Acme](../../projects/acme/brief.md) this week.",
            "Also written as [projects/acme/brief.md](../../projects/acme/brief.md).",
            "Cited as `projects/acme/brief.md` in a footnote.",
            "And mentioned in prose: the projects/acme folder is where it lives.",
            "",
        ]) + "\n")
        inbound = self.plan("acme")["inbound"]
        shapes = {h["shape"] for h in inbound["references"]}
        self.assertEqual(shapes, {"link_target", "link_text", "backtick", "prose"})
        self.assertEqual(inbound["name_only"], [])

    def test_a_substring_hit_is_name_only_not_a_reference(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nWorking on acme-website-v2 this month.\n")
        inbound = self.plan("acme")["inbound"]
        self.assertEqual(inbound["references"], [])
        self.assertEqual(len(inbound["name_only"]), 1)
        self.assertIn("acme-website-v2", inbound["name_only"][0]["text"])

    def test_hits_inside_the_entity_folder_itself_are_excluded(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n\nAcme is a project.\n")
        write(self.root, "projects/acme/sources/notes.md", "# Notes\n\nAbout acme.\n")
        write(self.root, "areas/network/jan.md", "# Jan\n\nNothing about acme here.\n")
        inbound = self.plan("acme")["inbound"]
        files = {h["file"] for h in inbound["references"] + inbound["name_only"]}
        self.assertNotIn("projects/acme/brief.md", files)
        self.assertNotIn("projects/acme/sources/notes.md", files)

    def test_living_reference_candidates_group_by_target_file(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/playbook.md", "# Playbook\n\nReusable steps.\n")
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nFollow [the playbook](../../projects/acme/playbook.md).\n")
        write(self.root, "areas/business/actions.md",
              "# Business\n\n- [ ] Reread [the playbook](../../projects/acme/playbook.md) 📅 2026-09-25\n")
        candidates = self.plan("acme")["inbound"]["living_reference_candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["file"], "projects/acme/playbook.md")
        self.assertEqual(len(candidates[0]["linked_from"]), 2)

    def test_route_finds_a_backtick_only_mention_that_never_names_the_folder(self):
        # move.md Step 6: the filename of a file routed out of the entity, not only the
        # entity's own folder name, is a reference - and Step 4 only decides what routes
        # after Step 0 has already run once, so this is a second, narrower call.
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/playbook.md", "# Playbook\n")
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nCited as `playbook.md` in a footnote, nothing about the folder here.\n")
        inbound = self.plan("acme", route=["projects/acme/playbook.md"])["inbound"]
        self.assertEqual(inbound["references"], [])  # the folder name itself is never hit
        routed = inbound["routed"]["projects/acme/playbook.md"]
        self.assertEqual(len(routed), 1)
        self.assertEqual(routed[0]["shape"], "backtick")
        self.assertEqual(routed[0]["file"], "areas/network/jan.md")

    def test_route_excludes_hits_inside_the_entity_folder_itself(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n\nSee `playbook.md` here too.\n")
        write(self.root, "projects/acme/playbook.md", "# Playbook\n")
        routed = self.plan("acme", route=["projects/acme/playbook.md"])["inbound"]["routed"]
        self.assertEqual(routed["projects/acme/playbook.md"], [])

    def test_with_no_route_argument_routed_is_an_empty_dict(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        self.assertEqual(self.plan("acme")["inbound"]["routed"], {})


# ------------------------------------------------------------------------------ move plan

class MovePlanAndSnapshot(VaultCase):

    def test_move_plan_is_present_when_the_destination_is_known(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        r = self.plan("acme")
        self.assertIsNotNone(r["move_plan"])
        self.assertIn("inside", r["move_plan"])
        self.assertIn("inbound", r["move_plan"])

    def test_move_plan_is_null_for_an_area_with_no_destination(self):
        write(self.root, "areas/harbor-website/brief.md", "# Harbor website\n")
        r = self.plan("harbor-website")
        self.assertIsNone(r["move_plan"])

    def test_snapshot_covers_the_entity_folder_and_reference_hits(self):
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        write(self.root, "projects/acme/actions.md", "# Acme - Actions\n")
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nSee [Acme](../../projects/acme/brief.md).\n")
        r = self.plan("acme")
        snap = r["snapshot"]
        self.assertEqual(len(snap), 3)
        self.assertTrue(all(Path(p).is_absolute() for p in snap))


# ---------------------------------------------------------------------------------- verify

class Verify(VaultCase):

    def setUp(self):
        super().setUp()
        write(self.root, "archive/projects/acme/brief.md", "# Acme\n\nShipped.\n")

    def test_stale_links_and_mentions_caught_in_every_shape(self):
        write(self.root, "areas/network/jan.md", "\n".join([
            "# Jan", "",
            "See [Acme](../../projects/acme/brief.md).",
            "Also [projects/acme/brief.md](../../projects/acme/brief.md).",
            "Cited as `projects/acme/brief.md`.",
            "Or just projects/acme in prose.",
            "The real home now is [here](../../archive/projects/acme/brief.md).",
            "",
        ]) + "\n")
        v = self.verify("projects/acme", "archive/projects/acme")
        # lines 3 and 4 each carry a real markdown link whose target is stale. stale_mentions
        # reports every occurrence of the old path as text: line 4 spells it twice (its link
        # text and its target), plus the backtick citation on line 5 and the bare prose on
        # line 6 - five occurrences from four lines.
        self.assertEqual(len(v["stale_links"]), 2)
        self.assertEqual(len(v["stale_mentions"]), 5)
        self.assertEqual(sum(1 for m in v["stale_mentions"] if m["line"] == 4), 2)
        self.assertFalse(v["clean"])
        # the correctly-updated link is never read as a stale mention
        self.assertTrue(all("archive/projects/acme" not in m["text"]
                            or "archive/projects/acme/brief.md](../../archive" in m["text"]
                            for m in v["stale_mentions"]))

    def test_a_trailing_slash_or_backslash_path_is_normalised(self):
        # Plan mode normalised --destination but verify took --moved-from/--moved-to as
        # given, so `projects/acme/` matched no mention and read a false clean.
        write(self.root, "areas/network/jan.md", "# Jan\n\nOr just projects/acme in prose.\n")
        for moved_from, moved_to in (("projects/acme/", "archive/projects/acme/"),
                                     ("projects\\acme", " archive\\projects\\acme ")):
            v = self.verify(moved_from, moved_to)
            self.assertEqual((v["moved_from"], v["moved_to"]),
                             ("projects/acme", "archive/projects/acme"))
            self.assertEqual(len(v["stale_mentions"]), 1)
            self.assertFalse(v["clean"])

    def test_a_versioned_new_path_also_excludes_its_own_old_path_substring(self):
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nNow at [Acme](../../archive/projects/acme-v1/brief.md).\n")
        v = self.verify("projects/acme", "archive/projects/acme-v1")
        self.assertEqual(v["stale_mentions"], [])

    def test_an_older_archived_folder_of_the_same_name_is_not_a_stale_mention(self):
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nThe first round is [here](../../archive/projects/acme/brief.md).\n")
        v = self.verify("projects/acme", "archive/projects/acme-v2")
        self.assertEqual(v["stale_mentions"], [])

    def test_third_party_content_goes_to_the_exempt_list(self):
        write(self.root, "projects/other/sources/transcript.md",
              "# Transcript\n\nSomeone mentioned projects/acme in the call.\n")
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertEqual(v["stale_mentions"], [])
        self.assertEqual(len(v["stale_mentions_exempt"]), 1)

    def test_a_link_inside_a_fence_is_neither_scanned_nor_counted(self):
        write(self.root, "areas/network/jan.md",
              "# Jan\n\n```\n[Acme](../../projects/acme/brief.md)\nprojects/acme\n```\n"
              "Nothing outside the fence names it.\n")
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertEqual(v["stale_links"], [])
        self.assertEqual(v["stale_mentions"], [])

    def test_a_repoint_resolving_under_the_new_folder_but_to_a_missing_file_is_unresolved(self):
        # move.md Step 8: a repoint has to resolve against the filesystem, not merely land
        # somewhere under the new location - passing "the old path is gone" is not enough.
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nSee [Acme](../../archive/projects/acme/actions.md).\n")
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertEqual(v["inbound_resolved"]["resolved"], 0)
        self.assertEqual(len(v["inbound_resolved"]["unresolved"]), 1)
        self.assertFalse(v["clean"])

    def test_a_correctly_repointed_link_resolves(self):
        write(self.root, "areas/network/jan.md",
              "# Jan\n\nSee [Acme](../../archive/projects/acme/brief.md).\n")
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertEqual(v["inbound_resolved"]["resolved"], 1)
        self.assertEqual(v["inbound_resolved"]["unresolved"], [])

    def test_inside_checks_links_in_the_new_folder_and_routed_files(self):
        write(self.root, "archive/projects/acme/sources/note.md",
              "# Note\n\nSee [gone](../missing.md).\n")
        write(self.root, "resources/acme/playbook.md",
              "# Playbook\n\nSee [gone too](../../archive/projects/acme/missing2.md).\n")
        v = self.verify("projects/acme", "archive/projects/acme",
                        routed=["resources/acme/playbook.md"])
        self.assertEqual(len(v["inside"]["dangling"]), 2)

    def test_old_path_still_present_and_empty_is_named(self):
        (self.root / "projects" / "acme").mkdir(parents=True)
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertTrue(v["old_path"]["exists"])
        self.assertTrue(v["old_path"]["empty"])

    def test_old_path_gone_is_named_too(self):
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertFalse(v["old_path"]["exists"])
        self.assertFalse(v["old_path"]["empty"])

    def test_a_clean_move_reports_clean_true(self):
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertTrue(v["clean"])

    def test_untracked_is_null_with_no_git(self):
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertIsNone(v["untracked"])

    @unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
    def test_untracked_lists_a_never_committed_file_after_a_real_git_mv(self):
        # No pre-existing archive/projects/acme here (Verify.setUp's is never committed):
        # the move destination has to be clear for a real git mv to land on it.
        shutil.rmtree(self.root / "archive" / "projects" / "acme")
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        git_init(self.root)
        # A folder git already tracks moves cleanly with git mv; a file never committed
        # still travels on disk and shows up untracked at the new path.
        write(self.root, "projects/acme/never-committed.md", "# Never committed\n")
        (self.root / "archive" / "projects").mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", "projects/acme", "archive/projects/acme"],
                       cwd=self.root, check=True)
        v = self.verify("projects/acme", "archive/projects/acme")
        self.assertIn("archive/projects/acme/never-committed.md", v["untracked"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
