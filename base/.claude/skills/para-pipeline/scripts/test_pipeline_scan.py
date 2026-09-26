#!/usr/bin/env python3
"""Tests for pipeline_scan.py. Each one pins a rule references/scan.md or references/render.md
states in prose.

    python3 test_pipeline_scan.py
    py -3 test_pipeline_scan.py

Standard library only, so a vault that runs the skill can run its tests. Every fixture is a
throwaway vault in a temporary directory, with synthetic names only: nothing reads or writes
a real vault, and nothing calls a model. The date is passed in, never taken from the clock.

What paraos_vault.py itself decides (Stage lines, header fields, register rows, lifecycle
tables) is tested beside it, in para-shared/scripts/test_paraos_vault.py. What is tested
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

from pipeline_scan import CollectedVault, main, scan

TODAY = date(2026, 9, 21)   # falls in the third calendar quarter of its year
SCRIPT = Path(__file__).resolve().parent / "pipeline_scan.py"

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

    def test_a_folder_entity_is_collected_from_its_brief(self):
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

    def test_a_stage_matching_no_declared_name_is_dropped_silently(self):
        write(self.root, "resources/ideas/other/brief.md",
              "# Other\n\n**Stage:** idea (concept only)\n")
        lc = self.deal()
        self.assertEqual([e["name"] for e in lc["entities"]], [])
        self.assertNotIn("resources/ideas/other/brief.md", lc["no_stage"])

    def test_an_ordinary_document_with_no_known_header_field_is_never_listed(self):
        write(self.root, "projects/harbor/brief.md", "# Harbor\n\n**Status:** active\n")
        self.assertNotIn("projects/harbor/brief.md", self.deal()["no_stage"])

    def test_a_document_with_no_stage_line_but_a_known_header_field_is_reported_by_path(self):
        write(self.root, "projects/tended/brief.md", "# Tended\n\n**Opened:** 2026-08-01\n")
        self.assertIn("projects/tended/brief.md", self.deal()["no_stage"])

    def test_a_home_with_an_extra_fixed_segment_is_reported_regardless_of_fields(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# Vault", "", "## Property lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Viewing | `areas/properties/<property>/` |",
            "| Held | `archive/ideas/<property>/` |", "",
        ]) + "\n")
        write(self.root, "areas/properties/oakview/brief.md", "# Oakview\n\nNo stage line.\n")
        self.assertIn("areas/properties/oakview/brief.md", self.deal()["no_stage"])

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

    def test_a_row_is_collected_per_table_row_with_its_section(self):
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

    def test_an_old_last_touch_is_stale_on_its_own_basis_whatever_the_stage_date(self):
        write(self.root, "resources/ideas/acme/brief.md",
              "# Acme\n\n**Stage:** Qualified (since 2026-09-15)\n**Opened:** 2026-05-01\n"
              "**Last touch:** 2026-08-21, emailed\n")
        flags = find(self.deal()["entities"], "acme")["flags"]
        self.assertEqual(flags["stale"], {"basis": "last_touch", "days": 31})

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
        self.assertEqual(m["median_days_opened_to_promoting"], {"n": 1, "median": None, "values": [45]})

    def test_reached_promoting_counts_by_the_quarter_it_was_reached_in(self):
        # Reached last quarter: not this quarter's. Reached now with no Opened date:
        # counted, but it has no duration to add to the median.
        write(self.root, "projects/early/brief.md",
              "# Early\n\n**Stage:** Goal (since 2026-05-01)\n**Opened:** 2026-04-01\n")
        write(self.root, "projects/unopened/brief.md", "# Unopened\n\n**Stage:** Goal (since 2026-08-01)\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["reached_promoting"], 1)
        self.assertEqual(m["median_days_opened_to_promoting"], {"n": 0, "median": None, "values": None})

    def test_a_won_date_is_the_reach_date_over_the_stage_since_date(self):
        write(self.root, "projects/nova/brief.md",
              "# Nova\n\n**Stage:** Goal (since 2026-05-01)\n**Opened:** 2026-07-01\n"
              "**Won:** 2026-08-15\n")
        m = self.deal()["metrics"]
        self.assertEqual(m["reached_promoting"], 1)
        self.assertEqual(m["median_days_opened_to_promoting"]["values"], [45])

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
        self.assertEqual(info, {"n": 3, "median": 31, "values": None})

    def test_median_reports_individual_values_below_three(self):
        write(self.root, "projects/p1/brief.md",
              "# P1\n\n**Stage:** Goal (since 2026-08-01)\n**Opened:** 2026-07-01\n")
        write(self.root, "projects/p2/brief.md",
              "# P2\n\n**Stage:** Goal (since 2026-09-01)\n**Opened:** 2026-07-01\n")
        info = self.deal()["metrics"]["median_days_opened_to_promoting"]
        self.assertEqual(info["n"], 2)
        self.assertIsNone(info["median"])
        self.assertEqual(sorted(info["values"]), [31, 62])

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
        write(self.root, "archive/ideas/omega/brief.md",
              "# Omega\n\n**Stage:** Lost (since 2026-08-01)\n**Opened:** 2026-03-01\n")
        terminal = self.deal()["metrics"]["terminal"]["Lost"]
        self.assertEqual(terminal["missing_reason"], ["omega"])
        self.assertEqual(terminal["all_time_reasons"], {})

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


class Scope(VaultCase):

    def test_a_lifecycle_filter_matches_by_noun_or_by_heading(self):
        self.assertEqual(self.deal(lifecycle="deal")["heading"], "Deal lifecycle")
        self.assertEqual(self.deal(lifecycle="Deal Lifecycle")["heading"], "Deal lifecycle")

    def test_a_lifecycle_filter_matching_nothing_returns_an_error(self):
        report, code = scan(self.root, TODAY, "property")
        self.assertEqual(code, 3)
        self.assertEqual(report["error"], "no such lifecycle")
        self.assertEqual(report["declared"], ["Deal lifecycle"])

    def test_a_collected_vault_is_refused_rather_than_read_as_empty(self):
        write(self.root, "resources/mds/projects__acme__brief.md", "# acme\n")
        with self.assertRaises(CollectedVault):
            scan(self.root, TODAY)

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
                         {"heading", "noun", "stages", "entities", "no_stage", "empty_homes",
                          "counts_by_stage", "terminal_this_quarter", "metrics"})

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

    def test_a_collected_vault_exits_2_with_the_reason_on_stderr_and_nothing_on_stdout(self):
        write(self.root, "resources/mds/projects__acme__brief.md", "# acme\n")
        code, out, err = self.run_main("--today", "2026-09-21")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("pipeline_scan: "), err)


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

    def test_missing_shared_library_exits_2_and_names_the_fallback(self):
        # SKILL.md falls back to references/scan.md on exit 2; the message says so.
        with tempfile.TemporaryDirectory() as tmp:
            isolated = Path(tmp) / "skills" / "para-pipeline" / "scripts"
            isolated.mkdir(parents=True)
            shutil.copy(SCRIPT, isolated / "pipeline_scan.py")
            result = subprocess.run(
                [sys.executable, str(isolated / "pipeline_scan.py"), "--vault", "."],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(result.stderr.startswith("pipeline_scan: "), result.stderr)
            self.assertIn("references/scan.md", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=1)
