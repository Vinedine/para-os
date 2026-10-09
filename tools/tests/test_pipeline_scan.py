#!/usr/bin/env python3
"""Tests for pipeline_scan.py. Each one pins a rule of the script, which is the
specification.

    python3 test_pipeline_scan.py
    py -3 test_pipeline_scan.py

Standard library only, so a vault that runs the skill can run its tests. Every fixture is a
throwaway vault in a temporary directory, with synthetic names only: nothing reads or writes
a real vault, and nothing calls a model. The date is passed in, never taken from the clock.

What paraos_vault.py itself decides (Stage lines, header fields, register rows, lifecycle
tables) is tested in test_paraos_vault.py. What is tested
here is what this skill alone decides: how a lifecycle's declared homes become entities,
how a next step is chosen, which flags fire, and how the quarter's metrics are counted.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-pipeline" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pipeline_scan import main, scan

TODAY = date(2026, 9, 21)   # falls in the third calendar quarter of its year
SCRIPT = SCRIPTS / "pipeline_scan.py"

LIFECYCLE = "\n".join([
    "# Vault", "",
    "## Deal lifecycle", "",
    "| Stage | PARA home |",
    "|---|---|",
    "| Lead | `areas/business/leads.md` (row) |",
    "| Qualified | `resources/ideas/<company>/` |",
    "| Goal | `projects/<company>/` |",
    "| Lost | `archive/ideas/<company>/` |", "",
]) + "\n"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def find(entities, name):
    return next(e for e in entities if e["name"] == name)


class VaultCase(unittest.TestCase):
    """A temporary vault root per test, removed afterwards. CLAUDE.md always declares the
    one Deal lifecycle above unless a test overrides it."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        write(self.root, "CLAUDE.md", LIFECYCLE)

    def deal(self, today=TODAY, lifecycle=None):
        report, code = scan(self.root, today, lifecycle)
        self.assertEqual(code, 0)
        return report["lifecycles"][0]


class FolderEntities(VaultCase):

    def test_a_folder_entity_is_read_from_its_brief(self):
        write(self.root, "resources/ideas/acme/brief.md", "\n".join([
            "# Acme", "",
            "**Stage:** Qualified (since 2026-09-01)",
            "**Opened:** 2026-08-01",
            "**Source:** outreach, cold call",
            "**Signer:** unknown",
            "**Last touch:** 2026-09-10, call happened", "",
        ]) + "\n")
        e = find(self.deal()["entities"], "acme")
        self.assertEqual(e["stage"], "Qualified")
        self.assertEqual(e["since"], "2026-09-01")
        self.assertEqual(e["days_in_stage"], 20)
        self.assertEqual(e["opened"], "2026-08-01")
        self.assertEqual(e["source"], "outreach, cold call")
        self.assertEqual(e["kind"], "folder")

    def test_both_brief_and_readme_read_from_readme_and_flag_the_duplicate(self):
        write(self.root, "resources/ideas/dual/brief.md",
              "# Dual\n\n**Stage:** Qualified\n**Opened:** 2026-08-01\n")
        write(self.root, "resources/ideas/dual/README.md",
              "# Dual\n\n**Stage:** Qualified\n**Opened:** 2026-08-05\n")
        e = find(self.deal()["entities"], "dual")
        self.assertEqual(e["opened"], "2026-08-05")
        self.assertTrue(e["duplicate_document"])

    def test_an_undeclared_stage_with_no_known_header_field_is_skipped(self):
        write(self.root, "resources/ideas/other/brief.md",
              "# Other\n\n**Stage:** idea (concept only)\n")
        lc = self.deal()
        self.assertEqual([e["name"] for e in lc["entities"]], [])
        self.assertNotIn("resources/ideas/other/brief.md", lc["no_stage"])
        self.assertEqual(lc["unknown_stage"], [])

    def test_trailing_punctuation_after_the_stage_name_is_ignored(self):
        # Issue #94: "Qualified." matched no declared name and the entity vanished.
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n_Stage: **Qualified**._\n**Opened:** 2026-08-01\n")
        self.assertEqual(find(self.deal()["entities"], "acme")["stage"], "Qualified")

    def test_an_undeclared_stage_on_a_staged_looking_entity_is_reported_not_dropped(self):
        # Issue #94: the entity disappeared from the board with no flag.
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Prospecting (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        self.assertEqual(self.deal()["unknown_stage"],
                         [{"path": "resources/ideas/acme/brief.md", "stage": "Prospecting"}])

    def test_an_ordinary_document_with_no_known_header_field_is_never_listed(self):
        write(self.root, "projects/harbor/brief.md", "# Harbor\n\n**Status:** active\n")
        self.assertNotIn("projects/harbor/brief.md", self.deal()["no_stage"])

    def test_a_document_with_no_stage_line_but_a_known_header_field_is_reported_by_path(self):
        write(self.root, "projects/tended/brief.md", "# Tended\n\n**Opened:** 2026-08-01\n")
        self.assertIn("projects/tended/brief.md", self.deal()["no_stage"])

    def test_an_ordinary_idea_with_no_stage_line_is_never_listed(self):
        # resources/ideas/ holds ordinary ideas too, however deep its path sits.
        write(self.root, "resources/ideas/kiln/brief.md", "# Kiln\n\nA concept.\n")
        self.assertNotIn("resources/ideas/kiln/brief.md", self.deal()["no_stage"])

    def test_a_lifecycle_only_home_reports_a_missing_stage_regardless_of_fields(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# Vault", "", "## Property lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Viewing | `areas/properties/<property>/` |",
            "| Held | `archive/ideas/<property>/` |", "",
        ]) + "\n")
        write(self.root, "areas/properties/oakview/brief.md", "# Oakview\n\nNo stage line.\n")
        self.assertIn("areas/properties/oakview/brief.md", self.deal()["no_stage"])

    def test_a_lifecycle_only_home_reports_an_undeclared_stage_regardless_of_fields(self):
        # Issue #67: a held dossier's label carries no header field, so a misnamed stage
        # dropped off the board silently.
        write(self.root, "CLAUDE.md", "\n".join([
            "# Vault", "", "## Property lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Held | `areas/properties/<property>/` |", "",
        ]) + "\n")
        write(self.root, "areas/properties/ashgrove/README.md",
              "# Ashgrove\n\n_Stage: Let - since the deed_\n")
        self.assertEqual(self.deal()["unknown_stage"],
                         [{"path": "areas/properties/ashgrove/README.md", "stage": "Let"}])

    def test_home_mismatch_names_both_paths(self):
        write(self.root, "projects/wrongplace/brief.md",
              "# Wrongplace\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        e = find(self.deal()["entities"], "wrongplace")
        self.assertEqual(e["home_mismatch"],
                         {"declared": "resources/ideas/<company>/", "actual": "projects/wrongplace"})

    def test_a_stage_with_no_home_yet_is_skipped_not_a_crash(self):
        write(self.root, "CLAUDE.md", LIFECYCLE.replace(
            "| Goal |", "| Negotiating | |\n| Goal |"))
        write(self.root, "resources/ideas/beta/brief.md", "# Beta\n\n**Stage:** Qualified\n")
        self.assertEqual([e["name"] for e in self.deal()["entities"]], ["beta"])

    def test_a_register_with_no_section_heading_is_read(self):
        write(self.root, "areas/business/leads.md",
              "# Leads\n\n| Company | Stage |\n|---|---|\n| Acme | Lead |\n")
        self.assertTrue(find(self.deal()["entities"], "Acme")["live"])

    def test_a_declared_home_that_does_not_exist_yet_is_reported_once(self):
        empty = set(self.deal()["empty_homes"])
        self.assertEqual(empty, {"areas/business/leads.md", "resources/ideas/<company>/",
                                 "projects/<company>/", "archive/ideas/<company>/"})

    def test_a_register_holding_no_table_rows_is_an_empty_home(self):
        write(self.root, "areas/business/leads.md", "# Leads\n\nNothing logged yet.\n")
        self.assertIn("areas/business/leads.md", self.deal()["empty_homes"])


class RowEntities(VaultCase):

    def test_a_row_is_read_per_table_row_with_its_section(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Alpha Co | Ray | outreach | 2026-09-01 | Lead | Call 2026-09-25 | 2026-09-01, x | open |",
            "",
            "## Closed", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Beta Co | Sue | outreach | 2026-06-01 | Lead | - | 2026-06-01, x | no reply |",
            "",
        ]) + "\n")
        entities = self.deal()["entities"]
        self.assertEqual({e["name"] for e in entities}, {"Alpha Co", "Beta Co"})
        self.assertEqual(find(entities, "Alpha Co")["section"], "Open")
        self.assertEqual(find(entities, "Beta Co")["section"], "Closed")

    def test_unknown_name_falls_back_to_the_contact_column(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| unknown | Jan Janssen | outreach | 2026-09-15 | Lead | Call 2026-09-25 | 2026-09-15, x | open |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertEqual(e["name"], "Jan Janssen")
        self.assertEqual(e["name_from"], "contact")

    def test_a_contact_fallback_name_drops_its_trailing_note(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| unknown | Jan Janssen (via a peer; no card) | outreach | 2026-09-15 | Lead | Call 2026-09-25 | 2026-09-15, x | open |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertEqual(e["name"], "Jan Janssen")
        self.assertEqual(e["name_from"], "contact")

    def test_unknown_name_with_no_contact_column_takes_the_second_column(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Person | Stage | Next step |",
            "|---|---|---|---|",
            "| unknown | Ann Lee | Lead | Call 2026-09-25 |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertEqual((e["name"], e["name_from"]), ("Ann Lee", "contact"))

    def test_a_row_with_an_empty_or_undeclared_stage_is_skipped(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Stage | Next step |",
            "|---|---|---|---|",
            "| Blank Co | Ray |  | Call 2026-09-25 |",
            "| Odd Co | Ray | Prospect | Call 2026-09-25 |",
            "| Real Co | Ray | **Lead** | Call 2026-09-25 |",
            "",
        ]) + "\n")
        self.assertEqual([e["name"] for e in self.deal()["entities"]], ["Real Co"])

    def test_row_missing_columns_is_flagged(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Big Co | Tom Baas | outreach | 2026-09-01 | Lead | Call 2026-09-25 | 2026-09-01, x |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertTrue(e["row_missing_columns"])

    def test_home_mismatch_for_a_row_naming_a_folder_stage(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Big Co | Tom Baas | outreach | 2026-09-01 | Qualified | Call 2026-09-25 | 2026-09-01, x | open |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertEqual(e["home_mismatch"],
                         {"stage_home": "resources/ideas/<company>/",
                          "found_in": "areas/business/leads.md"})

    def test_no_home_mismatch_on_a_closed_row_recording_its_move(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Closed", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Big Co | Tom Baas | outreach | 2026-06-19 | Qualified | - | 2026-07-01, x | moved to resources/ideas/big-co/ |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertTrue(e["closed"])
        self.assertIsNone(e["home_mismatch"])

    def test_a_row_under_closed_is_closed_and_not_live(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Closed", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Old Co | Sue | outreach | 2026-06-01 | Lead | - | 2026-06-01, x | no reply |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertTrue(e["closed"])
        self.assertFalse(e["live"])
        self.assertIsNone(e["next_step"])
        self.assertIsNone(e["flags"])

    def test_opened_stands_in_for_since_at_the_first_stage(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Gamma Co | Kim | outreach | 2026-08-01 | Lead | Call 2026-09-25 | 2026-08-01, x | open |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertEqual(e["since"], "2026-08-01")
        self.assertEqual(e["since_from"], "opened")
        self.assertEqual(e["days_in_stage"], 51)


class NextStep(VaultCase):

    def test_rule_order_own_actions_wins_over_everything_else(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n**Stage:** Goal (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Champion:** [jan](../../areas/network/jan.md)\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Own task 📅 2026-09-25\n")
        write(self.root, "areas/business/actions.md",
              "# Business\n\n- [ ] Revisit [Acme](../../projects/acme/brief.md) 📅 2026-09-22\n")
        write(self.root, "areas/network/jan.md",
              "# Jan\n\n## Next actions\n- [ ] Champion task 📅 2026-09-19\n")
        step = find(self.deal()["entities"], "acme")["next_step"]
        self.assertEqual(step["source"], "own_actions")
        self.assertEqual(step["text"], "Own task")

    def test_rule_1_never_reads_an_actions_file_under_resources_or_archive(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "resources/ideas/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Own task 📅 2026-09-25\n")
        write(self.root, "areas/business/actions.md",
              "# Business\n\n- [ ] Revisit [Acme](../../resources/ideas/acme/brief.md) 📅 2026-09-22\n")
        step = find(self.deal()["entities"], "acme")["next_step"]
        self.assertEqual(step["source"], "linked_checkbox")

    def test_linked_checkbox_picked_earliest_across_other_action_files(self):
        write(self.root, "resources/ideas/beta/brief.md",
              "# Beta\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "areas/business/actions.md",
              "# Business\n\n- [ ] Revisit [Beta](../../resources/ideas/beta/brief.md) 📅 2026-09-22\n")
        write(self.root, "projects/other/actions.md",
              "# Other\n\n- [ ] Also mentions [Beta](../../resources/ideas/beta/brief.md) 📅 2026-09-20\n")
        step = find(self.deal()["entities"], "beta")["next_step"]
        self.assertEqual(step["source"], "linked_checkbox")
        self.assertEqual(step["date"], "2026-09-20")

    def test_linked_checkbox_found_in_a_nested_actions_file(self):
        # scan.md Step 3 rule 2 reads any actions.md under projects/ or areas/, but the
        # scan only globbed their direct children, so a sub-area's file was never read.
        write(self.root, "resources/ideas/delta/brief.md",
              "# Delta\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "areas/business/clients/actions.md",
              "# Clients\n\n- [ ] Revisit [Delta](../../../resources/ideas/delta/brief.md) "
              "📅 2026-09-22\n")
        step = find(self.deal()["entities"], "delta")["next_step"]
        self.assertEqual(step["source"], "linked_checkbox")
        self.assertEqual(step["file"], "areas/business/clients/actions.md")

    def test_an_own_actions_file_with_nothing_open_falls_through_to_a_linked_checkbox(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n**Stage:** Goal (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "projects/acme/actions.md", "# Acme - Actions\n\n- [x] Done already\n")
        write(self.root, "areas/business/actions.md",
              "# Business\n\n- [ ] Revisit [Acme](../../projects/acme/brief.md) 📅 2026-09-22\n")
        step = find(self.deal()["entities"], "acme")["next_step"]
        self.assertEqual((step["source"], step["file"]),
                         ("linked_checkbox", "areas/business/actions.md"))

    def test_a_checkbox_linking_elsewhere_or_nowhere_is_not_a_next_step(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "resources/ideas/beta/brief.md",
              "# Beta\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "areas/business/actions.md",
              "# Business\n\n- [ ] Revisit [Beta](../../resources/ideas/beta/brief.md) 📅 2026-09-22\n"
              "- [ ] Revisit acme some day 📅 2026-09-22\n")
        entities = self.deal()["entities"]
        self.assertIsNone(find(entities, "acme")["next_step"])
        self.assertTrue(find(entities, "acme")["flags"]["no_next_step"])
        self.assertEqual(find(entities, "beta")["next_step"]["source"], "linked_checkbox")

    def test_a_champion_link_resolving_to_nothing_falls_through(self):
        write(self.root, "resources/ideas/gamma/brief.md",
              "# Gamma\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Champion:** [nobody](../../areas/network/nobody.md)\n")
        step = find(self.deal()["entities"], "gamma")["next_step"]
        self.assertIsNone(step)

    def test_a_champion_field_with_no_link_is_also_the_no_next_step_case(self):
        write(self.root, "resources/ideas/delta/brief.md",
              "# Delta\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Champion:** a friend, no card\n")
        step = find(self.deal()["entities"], "delta")["next_step"]
        self.assertIsNone(step)

    def test_champion_next_step_is_scoped_to_the_next_actions_heading(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Champion:** [jan](../../../areas/network/jan.md)\n")
        write(self.root, "areas/network/jan.md", "\n".join([
            "# Jan", "", "## History", "- [ ] Old task 📅 2026-09-01", "",
            "## Next actions", "- [ ] Champion task 📅 2026-09-19", "",
        ]) + "\n")
        step = find(self.deal()["entities"], "acme")["next_step"]
        self.assertEqual(step["text"], "Champion task")

    def test_a_champion_file_with_no_title_offers_the_tasks_under_no_heading(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Champion:** [jan](../../../areas/network/jan.md)\n")
        write(self.root, "areas/network/jan.md", "\n".join([
            "Notes on Jan", "", "- [ ] Call back 📅 2026-09-24", "",
            "## History", "- [ ] Old task 📅 2026-09-01", "",
        ]) + "\n")
        step = find(self.deal()["entities"], "acme")["next_step"]
        self.assertEqual((step["text"], step["source"]), ("Call back", "champion"))

    def test_a_malformed_champion_href_is_the_no_next_step_case_not_a_crash(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Champion:** [jan](jan%00.md)\n")
        self.assertIsNone(find(self.deal()["entities"], "acme")["next_step"])

    def test_a_row_champion_comes_before_the_rows_own_next_step_column(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Stage | Next step | Champion |",
            "|---|---|---|---|---|",
            "| Alpha Co | Ray | Lead | Call 2026-09-30 | [jan](../network/jan.md) |",
            "",
        ]) + "\n")
        write(self.root, "areas/network/jan.md",
              "# Jan\n\n## Next actions\n- [ ] Intro Alpha Co 📅 2026-09-24\n")
        step = self.deal()["entities"][0]["next_step"]
        self.assertEqual((step["source"], step["text"], step["file"]),
                         ("champion", "Intro Alpha Co", "areas/network/jan.md"))

    def test_the_row_next_step_column_is_the_last_resort(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Delta Co | Mia | outreach | 2026-08-01 | Lead | Call Monday 2026-09-30 | 2026-08-01, x | open |",
            "",
        ]) + "\n")
        step = self.deal()["entities"][0]["next_step"]
        self.assertEqual(step["source"], "register_row")
        self.assertEqual(step["date"], "2026-09-30")

    def test_a_row_next_step_with_no_date_still_produces_a_step(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Epsilon Co | Zoe | outreach | 2026-08-01 | Lead | No date yet | 2026-08-01, x | open |",
            "",
        ]) + "\n")
        step = self.deal()["entities"][0]["next_step"]
        self.assertEqual(step["text"], "No date yet")
        self.assertIsNone(step["date"])

    def row_entity(self, next_step, company="Theta Co"):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            f"| {company} | Ray | outreach | 2026-08-01 | Lead | {next_step} | 2026-08-01, x | open |",
            "",
        ]) + "\n")
        return self.deal()["entities"][0]

    def test_a_date_inside_the_step_prose_is_not_its_due_date(self):
        # Issue #34, finding 1: a date in prose read back as the step's due date.
        step = self.row_entity("Send the deck after the 2026-09-10 board meeting")["next_step"]
        self.assertEqual(step["text"], "Send the deck after the 2026-09-10 board meeting")
        self.assertIsNone(step["date"])

    def test_a_date_attached_to_the_step_is_its_due_date(self):
        for cell in ("Call on 2026-09-25 about the quote", "Send the quote by 2026-09-25",
                     "Call 📅 2026-09-25, then the deck", "Chase the reference names, 2026-09-25"):
            with self.subTest(cell=cell):
                self.assertEqual(self.row_entity(cell)["next_step"]["date"], "2026-09-25")

    def test_a_by_date_outranks_an_earlier_on_date(self):
        # Issue #173: the first attached date won, so the presentation date read as the due date.
        for cell, due in (
                ("Contact the director after the partner presentation on 2026-10-06, "
                 "by 2026-10-09 at the latest", "2026-10-09"),
                ("Call by 2026-10-09 to confirm the 📅 2026-10-12 visit", "2026-10-12"),
                ("Meet on 2026-10-06, send the notes 2026-10-08", "2026-10-06")):
            with self.subTest(cell=cell):
                self.assertEqual(self.row_entity(cell)["next_step"]["date"], due)

    def test_a_weekday_between_by_or_on_and_the_date_still_attaches_it(self):
        # Issue #301: "by Tuesday <date>" missed `by`, so an incidental `on` date won.
        for cell, due in (
                ("Wait for their answer to the demo offer; one short nudge if no answer by "
                 "Tuesday 2026-10-13. The office moved, per a web search on 2026-10-05",
                 "2026-10-13"),
                ("Send the notes by Tues. 2026-10-13, after the call on 2026-10-05", "2026-10-13"),
                ("Call on Fri, 2026-10-09 about the quote", "2026-10-09"),
                ("Visit on wednesday 2026-10-14, then the deck", "2026-10-14")):
            with self.subTest(cell=cell):
                self.assertEqual(self.row_entity(cell)["next_step"]["date"], due)

    def test_a_no_step_wording_is_no_next_step(self):
        # Issue #34, finding 2: "None planned" suppressed the no_next_step flag.
        for cell in ("None planned: raised at the partners meeting on 2026-09-10", "none planned",
                     "-"):
            with self.subTest(cell=cell):
                e = self.row_entity(cell)
                self.assertIsNone(e["next_step"])
                self.assertTrue(e["flags"]["no_next_step"])

    def test_a_linked_name_reduces_to_its_label(self):
        # Issue #34, finding 3: the markdown link stayed inside the entity name.
        e = self.row_entity("Call 2026-09-25", company="Acme NV ([acme.example](https://acme.example))")
        self.assertEqual(e["name"], "Acme NV")

    def test_no_next_step_when_nothing_produces_a_checkbox(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Zeta Co | Ray | outreach | 2026-08-01 | Lead |  | 2026-08-01, x | open |",
            "",
        ]) + "\n")
        e = self.deal()["entities"][0]
        self.assertIsNone(e["next_step"])
        self.assertTrue(e["flags"]["no_next_step"])


class Flags(VaultCase):

    def test_stale_uses_last_touch_when_present(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-06-01)\n**Opened:** 2026-05-01\n"
              "**Last touch:** 2026-09-15, called\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertIsNone(flags["stale"])   # 6 days since last touch, well under 14

    def test_an_old_last_touch_is_stale_on_its_own_basis_when_the_stage_is_older_still(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-07-01)\n**Opened:** 2026-05-01\n"
              "**Last touch:** 2026-08-21, emailed\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertEqual(flags["stale"], {"basis": "last_touch", "days": 31})

    def test_a_recent_stage_date_outweighs_an_old_last_touch(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-15)\n**Opened:** 2026-05-01\n"
              "**Last touch:** 2026-08-21, emailed\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertIsNone(flags["stale"])

    def lead_flags(self, opened, last_touch):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            f"| Alpha Co | Ray | outreach | {opened} | Lead |  | {last_touch}, x | open |",
            "",
        ]) + "\n")
        return find(self.deal()["entities"], "Alpha Co")["flags"]

    def test_a_row_opened_this_week_from_an_old_contact_is_not_stale(self):
        self.assertIsNone(self.lead_flags("2026-09-17", "2025-08-17")["stale"])

    def test_an_older_row_is_stale_on_its_opened_date(self):
        flags = self.lead_flags("2026-09-01", "2025-08-17")
        self.assertEqual(flags["stale"], {"basis": "opened", "days": 20})

    def test_a_dated_next_step_already_past_does_not_suppress_stale(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n**Stage:** Goal (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Missed call 📅 2026-09-15\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertEqual(flags["stale"], {"basis": "stage", "days": 51})

    def test_stale_falls_back_to_stage_with_no_last_touch(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertEqual(flags["stale"], {"basis": "stage", "days": 51})

    def test_a_dated_next_step_still_ahead_suppresses_stale(self):
        write(self.root, "projects/acme/brief.md",
              "# Acme\n\n**Stage:** Goal (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        write(self.root, "projects/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Next call 📅 2026-09-25\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertIsNone(flags["stale"])

    def test_an_undated_next_step_does_not_suppress_stale(self):
        # Finding 4 of the 20260921-2035 test run.
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        write(self.root, "resources/ideas/acme/actions.md",
              "# Acme - Actions\n\n- [ ] Next call, no date yet\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertEqual(flags["stale"], {"basis": "stage", "days": 51})

    def test_expiring_dated_fact_within_14_days_and_still_ahead(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01; prices hold to 2026-09-30)\n"
              "**Opened:** 2026-08-01\n")
        e = find(self.deal()["entities"], "acme")
        self.assertEqual(e["dated_facts"], [{"clause": "prices hold to 2026-09-30",
                                             "date": "2026-09-30", "days_ahead": 9}])
        self.assertEqual(e["flags"]["expiring"], e["dated_facts"])

    def test_a_dated_fact_already_past_is_not_expiring(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01; renewed by 2026-09-10)\n"
              "**Opened:** 2026-08-01\n")
        e = find(self.deal()["entities"], "acme")
        self.assertEqual(e["flags"]["expiring"], [])

    def test_signer_unknown_fires_from_the_second_stage_on_not_before(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome | Signer |",
            "|---|---|---|---|---|---|---|---|---|",
            "| Lead Co | Kim | outreach | 2026-08-01 | Lead | Call 2026-09-25 | 2026-08-01, x | open | unknown |",
            "",
        ]) + "\n")
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-08-01\n"
              "**Signer:** unknown\n")
        entities = self.deal()["entities"]
        self.assertFalse(find(entities, "Lead Co")["flags"]["signer_unknown"])
        self.assertTrue(find(entities, "acme")["flags"]["signer_unknown"])

    def test_signer_reads_unknown_from_its_first_clause(self):
        for value, expected in (("unknown; four owners decide", True),
                                ("Unknown (the money holder)", True),
                                ("unknown - to ask", True),
                                ("Kim Lee, unknown title", False)):
            write(self.root, "resources/ideas/acme/brief.md",
                  "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-08-01\n"
                  "**Signer:** " + value + "\n")
            e = find(self.deal()["entities"], "acme")
            self.assertEqual(e["flags"]["signer_unknown"], expected, value)

    def test_name_collision_across_homes(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Acme | Kim | outreach | 2026-08-01 | Lead | Call 2026-09-25 | 2026-08-01, x | open |",
            "",
        ]) + "\n")
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-08-01\n")
        entities = self.deal()["entities"]
        self.assertTrue(find(entities, "Acme")["flags"]["name_collision"])
        self.assertTrue(find(entities, "acme")["flags"]["name_collision"])

    def test_the_unknown_fallback_is_skipped_by_the_collision_check(self):
        # Finding 1 of the 20260921-2035 test run, second half.
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| unknown | Sam Rivera | outreach | 2026-08-01 | Lead | Call 2026-09-25 | 2026-08-01, x | open |",
            "| unknown | Sam Rivera | outreach | 2026-08-05 | Lead | Call 2026-09-26 | 2026-08-05, x | open |",
            "",
        ]) + "\n")
        entities = self.deal()["entities"]
        self.assertEqual(len(entities), 2)
        self.assertFalse(any(e["flags"]["name_collision"] for e in entities))

    def test_an_entity_at_a_terminal_stage_has_no_next_step_or_flags(self):
        write(self.root, "archive/ideas/omega/brief.md",
              "# Omega\n\n**Stage:** Lost (since 2026-06-25)\n"
              "**Lost reason:** relationship only, went cold\n**Opened:** 2026-03-01\n")
        e = find(self.deal()["entities"], "omega")
        self.assertTrue(e["terminal"])
        self.assertFalse(e["live"])
        self.assertIsNone(e["next_step"])
        self.assertIsNone(e["flags"])


class Metrics(VaultCase):

    def test_opened_this_quarter(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "resources/ideas/old/brief.md",
              "# Old\n\n**Stage:** Qualified (since 2026-05-01)\n**Opened:** 2026-05-01\n")
        self.assertEqual(self.deal()["metrics"]["opened"], 1)

    def test_reached_promoting_is_null_without_a_promoting_stage(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# Vault", "", "## Deal lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Lead | `areas/business/leads.md` (row) |",
            "| Lost | `archive/ideas/<company>/` |", "",
        ]) + "\n")
        m = self.deal()["metrics"]
        self.assertIsNone(m["promoting_stage"])
        self.assertIsNone(m["reached_promoting"])

    def test_reached_promoting_counts_an_entity_at_the_stage_this_quarter(self):
        write(self.root, "projects/nova/brief.md",
              "# Nova\n\n**Stage:** Goal (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["promoting_stage"], "Goal")
        self.assertEqual(m["reached_promoting"], 1)

    def test_a_won_date_on_an_archived_project_counts_as_reached(self):
        write(self.root, "archive/projects/nova/brief.md",
              "# Nova\n\n**Won:** 2026-08-15\n**Opened:** 2026-07-01\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["reached_promoting"], 1)
        self.assertEqual(m["median_days_opened_to_promoting"], {"n": 1, "median": None})

    def test_reached_promoting_counts_by_the_quarter_it_was_reached_in(self):
        # Reached last quarter: not this quarter's. Reached now with no Opened date:
        # counted, but it has no duration to add to the median.
        write(self.root, "projects/early/brief.md",
              "# Early\n\n**Stage:** Goal (since 2026-05-01)\n**Opened:** 2026-04-01\n")
        write(self.root, "projects/unopened/brief.md", "# Unopened\n\n**Stage:** Goal (since 2026-08-01)\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["reached_promoting"], 1)
        self.assertEqual(m["median_days_opened_to_promoting"], {"n": 0, "median": None})

    def test_an_archived_won_project_still_counts_as_opened_and_in_the_referrers(self):
        # Issue #66: won and delivered inside one quarter, it reached Goal from nowhere.
        write(self.root, "archive/projects/nova/brief.md",
              "# Nova\n\n**Stage:** Goal (since 2026-08-15)\n**Opened:** 2026-07-01\n"
              "**Source:** outreach, cold mail\n**Won:** 2026-08-15\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["opened"], 1)
        self.assertEqual(m["referrers"],
                         [{"source": "outreach", "entities": 1, "reached_promoting": 1}])

    def test_a_closed_row_that_moved_to_an_archived_won_project_is_counted_once(self):
        write(self.root, "archive/projects/nova/brief.md",
              "# Nova\n\n**Opened:** 2026-07-01\n**Source:** outreach, cold mail\n"
              "**Won:** 2026-08-15\n")
        write(self.root, "areas/business/leads.md", "\n".join([
            "## Closed", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Nova | Kim | outreach | 2026-07-01 | Lead | - | 2026-07-10 |"
            " [qualified](../../archive/projects/nova/) |", "",
        ]))
        m = self.deal()["metrics"]
        self.assertEqual(m["opened"], 1)
        self.assertEqual(m["referrers"][0]["entities"], 1)

    def test_a_won_date_is_the_reach_date_over_the_stage_since_date(self):
        write(self.root, "projects/nova/brief.md",
              "# Nova\n\n**Stage:** Goal (since 2026-05-01)\n**Opened:** 2026-07-01\n"
              "**Won:** 2026-08-15\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["reached_promoting"], 1)
        self.assertEqual(m["median_days_opened_to_promoting"]["n"], 1)

    def test_only_an_archived_project_folder_with_a_won_date_in_the_quarter_counts(self):
        write(self.root, "archive/projects/loose-note.md", "**Won:** 2026-08-15\n")
        write(self.root, "archive/projects/no-doc/sources/x.md", "**Won:** 2026-08-15\n")
        write(self.root, "archive/projects/never-won/brief.md", "# Never\n\n**Opened:** 2026-07-01\n")
        write(self.root, "archive/projects/last-q/brief.md",
              "# Last\n\n**Won:** 2026-06-15\n**Opened:** 2026-05-01\n")
        write(self.root, "archive/projects/unopened/brief.md", "# Unopened\n\n**Won:** 2026-08-15\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["reached_promoting"], 1)
        self.assertEqual(m["median_days_opened_to_promoting"]["n"], 0)

    def test_median_is_computed_from_three_values_on(self):
        for name, since in (("p1", "2026-07-11"), ("p2", "2026-08-01"), ("p3", "2026-09-01")):
            write(self.root, f"projects/{name}/brief.md",
                  f"# {name}\n\n**Stage:** Goal (since {since})\n**Opened:** 2026-07-01\n")
        info = self.deal()["metrics"]["median_days_opened_to_promoting"]
        self.assertEqual(info, {"n": 3, "median": 31})

    def test_no_median_below_three_values(self):
        write(self.root, "projects/p1/brief.md",
              "# P1\n\n**Stage:** Goal (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        write(self.root, "projects/p2/brief.md",
              "# P2\n\n**Stage:** Goal (since 2026-09-01)\n**Opened:** 2026-07-01\n")
        info = self.deal()["metrics"]["median_days_opened_to_promoting"]
        self.assertEqual(info, {"n": 2, "median": None})

    def test_terminal_reasons_group_on_text_before_the_first_comma(self):
        # Finding 2 of the 20260921-2035 test run.
        write(self.root, "archive/ideas/a1/brief.md",
              "# A1\n\n**Stage:** Lost (since 2026-08-01)\n"
              "**Lost reason:** relationship only, never engaged again\n**Opened:** 2026-03-01\n")
        write(self.root, "archive/ideas/a2/brief.md",
              "# A2\n\n**Stage:** Lost (since 2026-09-05)\n"
              "**Lost reason:** relationship only, ghosted after the demo\n**Opened:** 2026-04-01\n")
        terminal = self.deal()["metrics"]["terminal"]["Lost"]
        self.assertEqual(terminal["reasons_this_quarter"], {"relationship only": 2})
        self.assertEqual(terminal["all_time_reasons"], {"relationship only": 2})

    def test_all_time_reasons_shown_when_the_quarter_holds_none(self):
        # Finding 5 of the 20260921-2035 test run.
        write(self.root, "archive/ideas/omega/brief.md",
              "# Omega\n\n**Stage:** Lost (since 2026-06-25)\n"
              "**Lost reason:** relationship only, went cold\n**Opened:** 2026-03-01\n")
        terminal = self.deal()["metrics"]["terminal"]["Lost"]
        self.assertEqual(terminal["this_quarter"], 0)
        self.assertEqual(terminal["reasons_this_quarter"], {})
        self.assertEqual(terminal["all_time_reasons"], {"relationship only": 1})

    def test_a_terminal_entity_with_no_reason_line_is_named_not_counted(self):
        write(self.root, ".claude/rules/deal-brief.md", "**Lost reason:** <reason>\n")
        write(self.root, "archive/ideas/omega/brief.md",
              "# Omega\n\n**Stage:** Lost (since 2026-08-01)\n**Opened:** 2026-03-01\n")
        terminal = self.deal()["metrics"]["terminal"]["Lost"]
        self.assertEqual(terminal["missing_reason"], ["omega"])
        self.assertEqual(terminal["all_time_reasons"], {})

    def test_a_missing_reason_is_named_only_where_a_rule_file_declares_the_line(self):
        # Issue #181: every sold property was named as missing a "Sold reason" no rule asks for.
        write(self.root, "archive/ideas/omega/brief.md",
              "# Omega\n\n**Stage:** Lost (since 2026-08-01)\n**Opened:** 2026-03-01\n")
        self.assertEqual(self.deal()["metrics"]["terminal"]["Lost"]["missing_reason"], [])

    def test_referrers_table_has_an_unrecorded_row(self):
        write(self.root, "resources/ideas/withsource/brief.md",
              "# Withsource\n\n**Stage:** Qualified (since 2026-09-01)\n"
              "**Opened:** 2026-09-01\n**Source:** outreach, cold call\n")
        write(self.root, "resources/ideas/nosource/brief.md",
              "# Nosource\n\n**Stage:** Qualified (since 2026-09-05)\n**Opened:** 2026-09-05\n")
        rows = {r["source"]: r for r in self.deal()["metrics"]["referrers"]}
        self.assertEqual(rows["outreach"]["entities"], 1)
        self.assertEqual(rows["unrecorded"]["entities"], 1)

    def test_a_referrer_link_is_grouped_by_its_label_and_counts_who_reached_promoting(self):
        write(self.root, "projects/nova/brief.md",
              "# Nova\n\n**Stage:** Goal (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Source:** referral from [Jan](../../areas/network/jan.md), at the fair\n")
        write(self.root, "resources/ideas/vega/brief.md",
              "# Vega\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Source:** referral from Jan\n")
        rows = self.deal()["metrics"]["referrers"]
        self.assertEqual(rows, [{"source": "referral from Jan", "entities": 2,
                                 "reached_promoting": 1}])

    def test_two_labels_linking_one_contact_are_one_referrer_named_by_its_title(self):
        # Issue #174: the table grouped on the link label, so one contact showed twice.
        write(self.root, "areas/network/alex-rivera.md", "# Alex Rivera\n")
        write(self.root, "resources/ideas/nova/brief.md",
              "# Nova\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Source:** referral from [Alex Rivera](../../../areas/network/alex-rivera.md)\n")
        write(self.root, "resources/ideas/vega/brief.md",
              "# Vega\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Source:** referral from [alex-rivera](../../../areas/network/alex-rivera.md), "
              "at the fair\n")
        rows = self.deal()["metrics"]["referrers"]
        self.assertEqual(rows, [{"source": "referral from Alex Rivera", "entities": 2,
                                 "reached_promoting": 0}])

    def test_a_lead_opened_and_promoted_in_one_quarter_counts_once(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Closed", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Big Co | Tom Baas | outreach | 2026-08-01 | Qualified | - | 2026-08-10, x | moved to resources/ideas/big-co/ |",
            "",
        ]) + "\n")
        write(self.root, "resources/ideas/big-co/brief.md",
              "# Big Co\n\n**Stage:** Qualified (since 2026-08-10)\n"
              "**Opened:** 2026-08-01\n**Source:** outreach\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["opened"], 1)
        self.assertEqual({r["source"]: r["entities"] for r in m["referrers"]}, {"outreach": 1})

    def test_a_closed_row_linking_its_folder_counts_once_whatever_its_name(self):
        # Issue #57: "Acme NV" against the folder acme was counted twice.
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Closed", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Acme NV | Tom Baas | outreach | 2026-08-01 | Qualified | - | 2026-08-10, x "
            "| moved to [acme](../../resources/ideas/acme/) |",
            "",
        ]) + "\n")
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-10)\n"
              "**Opened:** 2026-08-01\n**Source:** outreach\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["opened"], 1)
        self.assertEqual({r["source"]: r["entities"] for r in m["referrers"]}, {"outreach": 1})

    def test_counts_by_stage_excludes_terminal_and_closed_rows(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Closed", "",
            "| Company | Contact | Source | Opened | Stage | Next step | Last touch | Outcome |",
            "|---|---|---|---|---|---|---|---|",
            "| Old Co | Sue | outreach | 2026-06-01 | Lead | - | 2026-06-01, x | no reply |",
            "",
        ]) + "\n")
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-01)\n**Opened:** 2026-08-01\n")
        write(self.root, "archive/ideas/omega/brief.md",
              "# Omega\n\n**Stage:** Lost (since 2026-08-01)\n"
              "**Lost reason:** timing, not now\n**Opened:** 2026-03-01\n")
        lc = self.deal()
        counts = {row["stage"]: row["count"] for row in lc["counts_by_stage"]}
        self.assertEqual(counts, {"Lead": 0, "Qualified": 1, "Goal": 0})
        self.assertNotIn("Lost", counts)


def locale_line(year_end):
    return ("\n## Language\n\nFolders in English.\n\n**Locale:** country Freedonia · currency"
            f" FRD · financial year ends {year_end} · numbers 1,234.56 · dates day-month-year"
            " · time zone Europe/Brussels. This line is the one home of these six.\n")


class FinancialYear(VaultCase):
    """Issue #264: the quarter is one of the financial year the Locale line declares."""

    def declare(self, year_end):
        write(self.root, "CLAUDE.md", LIFECYCLE + locale_line(year_end))

    def test_with_a_30_june_year_end_a_deal_won_in_august_counts_in_q1(self):
        self.declare("30 June")
        write(self.root, "archive/projects/nova/brief.md",
              "# Nova\n\n**Won:** 2026-08-15\n**Opened:** 2026-07-20\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["quarter"], "Q1 of the year ending 2027-06-30")
        self.assertEqual((m["quarter_start"], m["quarter_end"]), ("2026-07-01", "2026-09-30"))
        self.assertEqual(m["reached_promoting"], 1)
        self.assertEqual(self.deal(today=date(2026, 10, 5))["metrics"]["reached_promoting"], 0)

    def test_a_year_end_off_the_calendar_quarters_moves_every_boundary(self):
        # Year ending 31 January: Aug to Oct is Q3, so a July win is last quarter's.
        self.declare("31 January")
        write(self.root, "archive/projects/august/brief.md", "# August\n\n**Won:** 2026-08-15\n")
        write(self.root, "archive/projects/july/brief.md", "# July\n\n**Won:** 2026-07-20\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["quarter"], "Q3 of the year ending 2027-01-31")
        self.assertEqual((m["quarter_start"], m["quarter_end"]), ("2026-08-01", "2026-10-31"))
        self.assertEqual(m["reached_promoting"], 1)

    def test_a_year_end_inside_a_month_starts_each_quarter_the_day_after(self):
        self.declare("5 April")
        m = self.deal(today=date(2026, 7, 3))["metrics"]
        self.assertEqual(m["quarter"], "Q1 of the year ending 2027-04-05")
        self.assertEqual((m["quarter_start"], m["quarter_end"]), ("2026-04-06", "2026-07-05"))
        m = self.deal(today=date(2026, 7, 6))["metrics"]
        self.assertEqual((m["quarter"], m["quarter_start"]),
                         ("Q2 of the year ending 2027-04-05", "2026-07-06"))

    def test_a_28_february_year_end_is_the_end_of_february_in_a_leap_year_too(self):
        self.declare("28 February")
        m = self.deal(today=date(2028, 2, 29))["metrics"]
        self.assertEqual((m["quarter"], m["quarter_end"]),
                         ("Q4 of the year ending 2028-02-29", "2028-02-29"))

    def test_with_no_locale_line_the_quarter_is_the_calendar_one(self):
        m = self.deal()["metrics"]
        self.assertEqual((m["quarter"], m["quarter_start"], m["quarter_end"]),
                         ("2026-Q3", "2026-07-01", "2026-09-30"))
        self.assertIsNone(m["year_end_unread"])

    def test_a_31_december_year_end_is_the_calendar(self):
        self.declare("31 December")
        self.assertEqual(self.deal()["metrics"]["quarter"], "2026-Q3")

    def test_a_year_end_nobody_can_read_falls_back_to_the_calendar_and_says_so(self):
        self.declare("end of the season")
        m = self.deal()["metrics"]
        self.assertEqual((m["quarter"], m["year_end_unread"]), ("2026-Q3", "end of the season"))

    def test_the_template_placeholder_is_no_declaration(self):
        self.declare("{{day and month, e.g. 31 December}}")
        m = self.deal()["metrics"]
        self.assertEqual((m["quarter"], m["year_end_unread"]), ("2026-Q3", None))

    def test_opened_and_terminal_counts_follow_the_financial_quarter(self):
        self.declare("31 January")
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-08-02)\n**Opened:** 2026-07-31\n")
        write(self.root, "archive/ideas/omega/brief.md",
              "# Omega\n\n**Stage:** Lost (since 2026-08-01)\n"
              "**Lost reason:** timing, not now\n**Opened:** 2026-08-01\n")
        lc = self.deal()
        self.assertEqual(lc["metrics"]["opened"], 1)
        self.assertEqual(lc["terminal_this_quarter"], 1)


PROPERTY_LIFECYCLE = "\n".join([
    "# Vault", "",
    "## Property lifecycle", "",
    "| Stage | PARA home |",
    "|---|---|",
    "| **Prospecting**: considering, an offer out | `resources/ideas/<property>/` |",
    "| **Acquiring**, **Permitting**, **Renovating**, **Selling**: agreement to sale"
    " | `projects/<property>/` |",
    "| **Held**: bought and kept | `areas/properties/<property>/` |",
    "| **Sold**: bought, then sold | `archive/properties/<property>/` |",
    "| **Dropped**: never bought | `archive/researched-deals/<property>/` |", "",
]) + "\n"


class PropertyDossier(VaultCase):
    """Issue #181: the real-estate flavor's dossier, header as property-dossier.md gives it."""

    def setUp(self):
        super().setUp()
        write(self.root, "CLAUDE.md", PROPERTY_LIFECYCLE)

    def test_a_prospect_takes_its_next_step_from_an_area_checkbox_linking_the_dossier(self):
        write(self.root, "resources/ideas/elm-row-4/brief.md",
              "# Elm Row 4\n\n**Stage:** Prospecting (since 2026-09-01)\n**Opened:** 2026-09-01\n")
        write(self.root, "areas/business/actions.md",
              "# Business\n\n- [ ] Second viewing of [Elm Row 4]"
              "(../../resources/ideas/elm-row-4/brief.md) 📅 2026-09-25\n")
        e = find(self.deal()["entities"], "elm-row-4")
        self.assertIn("Second viewing", e["next_step"]["text"])
        self.assertFalse(e["flags"]["no_next_step"])

    def test_days_in_stage_and_a_dated_fact_come_from_the_dossier_stage_line(self):
        write(self.root, "projects/elm-row-4/brief.md",
              "# Elm Row 4\n\n**Stage:** Acquiring (since 2026-09-01; deed due 2026-11-30)\n"
              "**Opened:** 2026-07-15\n**Source:** listing, portal\n"
              "**Last touch:** 2026-09-18, notary call\n")
        e = find(self.deal()["entities"], "elm-row-4")
        self.assertEqual(e["days_in_stage"], 20)
        self.assertEqual(e["last_touch"]["days"], 3)
        self.assertEqual(len(e["dated_facts"]), 1)

    def test_a_dropped_property_reason_line_is_read(self):
        write(self.root, "archive/researched-deals/elm-row-4/brief.md",
              "# Elm Row 4 (skipped)\n\n**Stage:** Dropped (since 2026-09-10)\n"
              "**Dropped reason:** price, asking stayed above the walk-away\n"
              "**Opened:** 2026-08-01\n")
        dropped = self.deal()["metrics"]["terminal"]["Dropped"]
        self.assertEqual(dropped["reasons_this_quarter"], {"price": 1})
        self.assertEqual(dropped["missing_reason"], [])

    def test_the_first_stage_under_projects_is_the_promoting_one(self):
        write(self.root, "projects/elm-row-4/brief.md",
              "# Elm Row 4\n\n**Stage:** Acquiring (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        write(self.root, "projects/oak-lane-9/brief.md",
              "# Oak Lane 9\n\n**Stage:** Renovating (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["promoting_stage"], "Acquiring")
        self.assertEqual(m["reached_promoting"], 1)


class Scope(VaultCase):

    def test_a_lifecycle_filter_matches_by_noun_or_by_heading(self):
        self.assertEqual(self.deal(lifecycle="deal")["heading"], "Deal lifecycle")
        self.assertEqual(self.deal(lifecycle="Deal Lifecycle")["heading"], "Deal lifecycle")

    def test_a_lifecycle_filter_matching_nothing_returns_an_error(self):
        report, code = scan(self.root, TODAY, "property")
        self.assertEqual(code, 3)
        self.assertEqual(report["error"], "no such lifecycle")
        self.assertEqual(report["declared"], ["Deal lifecycle"])

    def test_two_lifecycles_are_scanned_independently(self):
        write(self.root, "CLAUDE.md", LIFECYCLE + "\n".join([
            "## Property lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Viewing | `resources/ideas/<property>/` |",
            "| Held | `archive/ideas/<property>/` |", "",
        ]) + "\n")
        report, code = scan(self.root, TODAY)
        self.assertEqual(code, 0)
        self.assertEqual([lc["heading"] for lc in report["lifecycles"]],
                         ["Deal lifecycle", "Property lifecycle"])


class CommandLine(VaultCase):
    """main() as SKILL.md's Steps 2 and 3 call it: --vault, an optional --lifecycle and
    --today, one JSON document on stdout and an exit code the skill reads."""

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--vault", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def usage_error(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as raised:
            main(list(args))
        self.assertEqual(raised.exception.code, 2)
        return err.getvalue()

    def two_lifecycles(self):
        write(self.root, "CLAUDE.md", LIFECYCLE + "\n".join([
            "## Property lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Viewing | `resources/ideas/<property>/` |",
            "| Held | `archive/ideas/<property>/` |", "",
        ]) + "\n")

    def test_prints_one_document_with_every_declared_lifecycle(self):
        self.two_lifecycles()
        code, out, _ = self.run_main("--today", "2026-09-21")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(set(report), {"vault", "today", "lifecycles"})
        self.assertEqual(report["vault"], self.root.resolve().as_posix())
        self.assertEqual(report["today"], "2026-09-21")
        self.assertEqual([lc["heading"] for lc in report["lifecycles"]],
                         ["Deal lifecycle", "Property lifecycle"])
        self.assertEqual(set(report["lifecycles"][0]),
                         {"heading", "noun", "stages", "entities", "no_stage", "unknown_stage",
                          "empty_homes", "counts_by_stage", "terminal_this_quarter", "metrics"})

    def test_lifecycle_scopes_the_document_to_the_one_it_names(self):
        self.two_lifecycles()
        code, out, _ = self.run_main("--lifecycle", "property", "--today", "2026-09-21")
        self.assertEqual(code, 0)
        self.assertEqual([lc["heading"] for lc in json.loads(out)["lifecycles"]],
                         ["Property lifecycle"])

    def test_a_lifecycle_matching_nothing_exits_3_with_the_declared_ones_as_json(self):
        code, out, _ = self.run_main("--lifecycle", "hiring", "--today", "2026-09-21")
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out), {"vault": self.root.resolve().as_posix(),
                                           "today": "2026-09-21",
                                           "error": "no such lifecycle",
                                           "declared": ["Deal lifecycle"]})

    def test_today_defaults_to_the_system_date(self):
        before = date.today().isoformat()
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn(json.loads(out)["today"], {before, date.today().isoformat()})

    def test_today_measures_days_in_stage(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n")
        code, out, _ = self.run_main("--today", "2026-09-11")
        self.assertEqual(code, 0)
        self.assertEqual(find(json.loads(out)["lifecycles"][0]["entities"], "acme")["days_in_stage"], 10)

    def test_indent_pretty_prints_the_same_document(self):
        code, out, _ = self.run_main("--today", "2026-09-21", "--indent", "2")
        self.assertEqual(code, 0)
        self.assertIn('\n  "today": "2026-09-21"', out)
        self.assertEqual(json.loads(out)["today"], "2026-09-21")

    def test_a_malformed_today_is_a_usage_error(self):
        err = self.usage_error("--vault", str(self.root), "--today", "21/09/2026")
        self.assertIn("--today wants YYYY-MM-DD", err)

    def test_a_vault_path_that_is_not_a_folder_is_a_usage_error(self):
        err = self.usage_error("--vault", str(self.root / "missing"))
        self.assertIn("no such vault", err)


class ScriptRun(VaultCase):
    """The script as a separate process, run from the vault with `--vault .` and its stdout
    redirected, as SKILL.md and para-shared/scripts.md run it."""

    def test_output_is_utf8_json_even_where_the_pipe_defaults_to_ascii(self):
        # A Windows pipe defaults to a codepage that cannot encode what a vault holds;
        # PYTHONIOENCODING=ascii reproduces that on every platform.
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-01)\n**Opened:** 2026-08-01\n"
              "**Source:** café owner, via the market\n")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", ".", "--lifecycle", "deal",
             "--today", "2026-09-21"],
            cwd=self.root, capture_output=True, timeout=120,
            env=dict(os.environ, PYTHONIOENCODING="ascii"))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        report = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(report["vault"], self.root.resolve().as_posix())
        self.assertEqual(find(report["lifecycles"][0]["entities"], "acme")["source"],
                         "café owner, via the market")

    def test_an_unmatched_lifecycle_exits_3_from_the_process_too(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", ".", "--lifecycle", "hiring"],
            cwd=self.root, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["declared"], ["Deal lifecycle"])


class MissingLibrary(unittest.TestCase):

    def test_missing_shared_library_exits_2_and_says_where_it_belongs(self):
        # scripts.md: exit 2 stops the skill; the message names what to install.
        with tempfile.TemporaryDirectory() as tmp:
            isolated = Path(tmp) / "skills" / "para-pipeline" / "scripts"
            isolated.mkdir(parents=True)
            shutil.copy(SCRIPT, isolated / "pipeline_scan.py")
            result = subprocess.run(
                [sys.executable, str(isolated / "pipeline_scan.py"), "--vault", "."],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(result.stderr.startswith("pipeline_scan: "), result.stderr)
            self.assertIn("install para-shared", result.stderr)
            self.assertNotIn("by hand", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=1)
