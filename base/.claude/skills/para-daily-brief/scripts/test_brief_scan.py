#!/usr/bin/env python3
"""Tests for brief_scan.py. Each one pins a rule the skill states in prose.

    python3 test_brief_scan.py
    py -3 test_brief_scan.py

Standard library only, so a vault that runs the skill can run its tests. Every fixture is
a throwaway vault in a temporary directory: nothing reads or writes a real vault, and
nothing calls a model. The date is passed in, never taken from the clock, so a run in a
year's time scores what it scores now.

What the shared library owns is tested beside it, in
`para-shared/scripts/test_paraos_vault.py`: name matching, fenced lines, markers, file
dates, hygiene sweeps. What is tested here is what the brief itself decides, and what the
two produce together.
"""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from brief_scan import CollectedVault, WIP_THRESHOLD, scan


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build_vault(root):
    """One project, one area, one contact, an idea and a triage item."""
    write(root, "README.md", "# Vault\n\n## Vision\n\nShip good work.\n")
    write(root, "projects/acme-website/actions.md", "\n".join([
        "# acme-website - Actions",
        "",
        "## Build",
        "- [ ] Late thing 📅 2026-09-01",
        "- [ ] Due today 🔺 📅 2026-09-21",
        "- [ ] This week 📅 2026-09-24",
        "- [ ] Next month 📅 2026-10-15",
        "- [ ] Far out 📅 2026-12-31",
        "- [ ] No date at all",
        "- [x] Done already 📅 2026-08-01",
        "",
        "## Recurring",
        "- [ ] Weekly review 🔁 every week 📅 2026-08-10",
        "",
    ]) + "\n")
    write(root, "areas/business/actions.md", "\n".join([
        "# business - Actions",
        "",
        "## Next actions",
        "- [ ] Gated until later 🛫 2026-12-01 📅 2026-12-05",
        "- [ ] Gate already open 🛫 2026-01-01 📅 2026-09-19",
        "- [ ] Scheduled only ⏳ 2026-09-23",
        "- [ ] Broken marker 📅 2026-13-45",
        "",
    ]) + "\n")
    write(root, "areas/network/jan-janssen.md",
          "# Jan Janssen\n\n## Next actions\n- [ ] Reply to Jan about acme website 📅 2026-09-10\n")
    write(root, "resources/ideas/orchard-labs/brief.md",
          "# orchard-labs\n\n**Stage:** Taste\n\nSome prose.\n")
    write(root, "triage/.gitkeep", "")
    write(root, "triage/20260919 Something - Note.md", "note\n")
    return root


TODAY = date(2026, 9, 21)


class VaultCase(unittest.TestCase):
    """A temporary vault root per test, removed afterwards."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def task(self, report, text):
        return [t for t in report["tasks"] if t["text"] == text][0]

    def lanes(self, report):
        return {t["text"]: t["lane"] for t in report["tasks"]}


class Lanes(VaultCase):

    def setUp(self):
        super().setUp()
        build_vault(self.root)
        self.report = scan(self.root, TODAY)

    def test_every_lane_lands_where_the_date_says(self):
        got = self.lanes(self.report)
        self.assertEqual(got["Late thing"], "overdue")
        self.assertEqual(got["Due today"], "today")
        self.assertEqual(got["This week"], "this_week")
        self.assertEqual(got["Next month"], "next_30")
        self.assertEqual(got["Far out"], "later")
        self.assertEqual(got["No date at all"], "undated")
        self.assertEqual(got["Weekly review"], "recurring")

    def test_a_future_start_gate_waits_and_a_past_one_does_not(self):
        got = self.lanes(self.report)
        self.assertEqual(got["Gated until later"], "waiting")
        self.assertEqual(got["Gate already open"], "overdue")

    def test_a_scheduled_date_counts_when_there_is_no_due_date(self):
        self.assertEqual(self.lanes(self.report)["Scheduled only"], "this_week")

    def test_a_malformed_date_lands_in_undated(self):
        task = self.task(self.report, "Broken marker")
        self.assertEqual(task["lane"], "undated")
        self.assertTrue(task["malformed_date"])

    def test_a_recurring_item_with_a_past_date_is_also_flagged_overdue(self):
        task = self.task(self.report, "Weekly review")
        self.assertEqual(task["lane"], "recurring")
        self.assertTrue(task["also_overdue"])

    def test_a_task_keeps_its_priority_and_its_heading(self):
        task = self.task(self.report, "Due today")
        self.assertEqual(task["priority"], "🔺")
        self.assertEqual(task["section"], "Build")


class WhatCounts(VaultCase):

    def test_a_checkbox_inside_a_fence_never_reaches_the_totals(self):
        write(self.root, "projects/docs/actions.md", "\n".join([
            "# docs", "", "- [ ] Real work", "", "```markdown",
            "- [ ] Sample from a template", "```", "",
        ]) + "\n")
        self.assertEqual([t["text"] for t in scan(self.root, TODAY)["tasks"]], ["Real work"])

    def test_archive_and_resources_never_feed_the_totals(self):
        write(self.root, "projects/live/actions.md", "# live\n\n- [ ] Open one\n")
        write(self.root, "archive/projects/old/actions.md", "# old\n\n- [ ] Left open\n")
        write(self.root, "resources/playbook/actions.md", "# playbook\n\n- [ ] Misfiled\n")
        got = scan(self.root, TODAY)
        self.assertEqual(got["totals"]["open"], 1)
        self.assertEqual(got["flags"]["misplaced"]["archive"][0]["open"], 1)
        self.assertEqual(got["flags"]["misplaced"]["resources"][0]["open"], 1)


class HealthFlags(VaultCase):

    def test_the_wip_flag_fires_at_the_threshold_not_above_it(self):
        # The vault rule reads "12 or more open items"; the prose said "more than 12".
        items = "\n".join(f"- [ ] Item {n}" for n in range(WIP_THRESHOLD))
        write(self.root, "projects/busy/actions.md", f"# busy\n\n{items}\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["over_threshold"],
                         [{"file": "projects/busy/actions.md", "open": WIP_THRESHOLD}])

    def test_one_item_below_the_threshold_stays_quiet(self):
        items = "\n".join(f"- [ ] Item {n}" for n in range(WIP_THRESHOLD - 1))
        write(self.root, "projects/busy/actions.md", f"# busy\n\n{items}\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["over_threshold"], [])

    def test_a_date_blown_by_more_than_a_month_reads_as_never_real(self):
        build_vault(self.root)
        worst = scan(self.root, TODAY)["flags"]["falsely_overdue"]
        self.assertTrue(worst)
        self.assertGreater(worst[0]["days"], 30)

    def test_a_recurrence_counts_the_periods_it_is_behind(self):
        build_vault(self.root)
        stale = scan(self.root, TODAY)["flags"]["stale_recurrence"]
        self.assertEqual(stale[0]["cadence"], "every week")
        self.assertEqual(stale[0]["periods_behind"], 6)

    def test_exactly_one_period_behind_is_not_yet_stale(self):
        write(self.root, "areas/ops/actions.md", "# ops\n\n## Recurring\n"
              "- [ ] Weekly sync 🔁 every week 📅 2026-09-14\n"
              "- [ ] Weekly report 🔁 every week 📅 2026-09-13\n")
        stale = scan(self.root, TODAY)["flags"]["stale_recurrence"]
        self.assertEqual([(s["date"], s["periods_behind"]) for s in stale],
                         [("2026-09-13", 1)])

    def test_an_undated_majority_is_reported_with_both_numbers(self):
        write(self.root, "projects/vague/actions.md",
              "# vague\n\n- [ ] One\n- [ ] Two\n- [ ] Three 📅 2026-09-25\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["undated_majority"],
                         {"undated": 2, "open": 3})

    def test_an_over_grown_brief_reaches_the_flags(self):
        write(self.root, "projects/wordy/actions.md", "# wordy\n\n- [ ] One\n")
        write(self.root, "projects/wordy/brief.md", "# wordy\n" + ("line\n" * 600))
        self.assertEqual(scan(self.root, TODAY)["flags"]["over_grown_briefs"][0]["lines"], 601)

    def test_an_over_grown_brief_under_a_scope_is_that_entitys_alone(self):
        write(self.root, "projects/wordy/actions.md", "# wordy\n\n- [ ] One\n")
        write(self.root, "projects/wordy/brief.md", "# wordy\n" + ("line\n" * 600))
        write(self.root, "projects/other/actions.md", "# other\n\n- [ ] Two\n")
        write(self.root, "projects/other/brief.md", "# other\n" + ("line\n" * 700))
        got = scan(self.root, TODAY, entity="wordy")["flags"]["over_grown_briefs"]
        self.assertEqual([b["file"] for b in got], ["projects/wordy/brief.md"])


class AggregationAndScope(VaultCase):

    def test_contact_files_aggregate_into_one_network_row(self):
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan\n\n## Next actions\n- [ ] Call Jan\n")
        write(self.root, "areas/network/ann-peeters.md",
              "# Ann\n\n## Next actions\n- [ ] Mail Ann\n")
        self.assertEqual(scan(self.root, TODAY)["entities"],
                         [{"bucket": "A", "label": "network", "open": 2, "overdue": 0,
                           "upcoming": 0, "undated": 2, "files": 2}])

    def test_the_three_counts_always_partition_the_open_count(self):
        build_vault(self.root)
        report = scan(self.root, TODAY)
        for row in report["entities"]:
            self.assertEqual(row["overdue"] + row["upcoming"] + row["undated"], row["open"])
        totals = report["totals"]
        self.assertEqual(totals["overdue"] + totals["upcoming"] + totals["undated"],
                         totals["open"])

    def test_a_dotted_name_scopes_the_whole_scan_to_one_project(self):
        build_vault(self.root)
        write(self.root, "projects/para-os-2026-09-04/actions.md", "# rev\n\n- [ ] Ship it\n")
        got = scan(self.root, TODAY, entity="Para OS 2026.09.04")
        self.assertEqual(got["entity"]["status"], "resolved")
        self.assertEqual([t["text"] for t in got["tasks"]], ["Ship it"])

    def test_an_entity_scope_counts_only_its_own_file(self):
        build_vault(self.root)
        got = scan(self.root, TODAY, entity="acme-website")
        self.assertEqual({t["file"] for t in got["tasks"]},
                         {"projects/acme-website/actions.md"})

    def test_a_mention_in_someone_elses_file_never_joins_the_totals(self):
        build_vault(self.root)
        got = scan(self.root, TODAY, entity="acme-website")
        self.assertEqual([m["file"] for m in got["mentioned_elsewhere"]],
                         ["areas/network/jan-janssen.md"])
        self.assertTrue(all(t["file"] != "areas/network/jan-janssen.md" for t in got["tasks"]))

    def test_the_vault_wide_flags_are_skipped_under_an_entity_scope(self):
        build_vault(self.root)
        flags = scan(self.root, TODAY, entity="acme-website")["flags"]
        self.assertIsNone(flags["misplaced"])
        self.assertIsNone(flags["undated_majority"])

    def test_an_unresolved_name_returns_no_tasks_at_all(self):
        build_vault(self.root)
        got = scan(self.root, TODAY, entity="nothing-like-this")
        self.assertEqual(got["entity"]["status"], "unresolved")
        self.assertEqual(got["tasks"], [])
        self.assertEqual(got["totals"]["open"], 0)

    def test_an_archived_name_reports_its_home_and_no_tasks(self):
        write(self.root, "projects/live/actions.md", "# live\n\n- [ ] Open one\n")
        write(self.root, "archive/projects/old-build/brief.md", "# shipped\n")
        got = scan(self.root, TODAY, entity="old build")
        self.assertEqual(got["entity"]["elsewhere"][0]["path"], "archive/projects/old-build")
        self.assertEqual(got["tasks"], [])


class MentionsElsewhere(VaultCase):

    def test_a_single_token_name_is_not_matched_by_a_word_in_its_text(self):
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan Janssen\n\n## Next actions\n- [ ] Call Jan\n")
        write(self.root, "areas/business/actions.md",
              "# business - Actions\n\n## Next actions\n"
              "- [ ] Follow up on the partner programme application\n")
        got = scan(self.root, TODAY, entity="network")
        self.assertEqual(got["mentioned_elsewhere"], [])

    def test_a_single_token_name_is_matched_by_a_link_into_its_folder(self):
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan Janssen\n\n## Next actions\n- [ ] Call Jan\n")
        write(self.root, "areas/business/actions.md",
              "# business - Actions\n\n## Next actions\n"
              "- [ ] Loop in [Jan](../network/jan-janssen.md) before the demo\n")
        got = scan(self.root, TODAY, entity="network")
        self.assertEqual([m["file"] for m in got["mentioned_elsewhere"]],
                         ["areas/business/actions.md"])

    def test_a_multi_token_name_is_matched_by_its_bare_name_in_text(self):
        write(self.root, "projects/para-os-2026-09-04/actions.md", "# rev\n\n- [ ] Ship it\n")
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan Janssen\n\n## Next actions\n- [ ] Ask Jan whether he wants a "
              "walkthrough of the para-os-2026-09-04 quickstart\n")
        got = scan(self.root, TODAY, entity="para-os-2026-09-04")
        self.assertEqual([m["file"] for m in got["mentioned_elsewhere"]],
                         ["areas/network/jan-janssen.md"])

    def test_a_link_to_a_longer_sibling_folder_is_not_a_mention(self):
        write(self.root, "projects/acme-website/actions.md", "# a\n\n- [ ] Ship it\n")
        write(self.root, "projects/acme-website-v2/brief.md", "# v2\n")
        write(self.root, "areas/business/actions.md",
              "# business - Actions\n\n## Next actions\n"
              "- [ ] Scope [the rebuild](../../projects/acme-website-v2/brief.md)\n"
              "- [ ] Plan the acme-website-v2 kickoff\n")
        got = scan(self.root, TODAY, entity="acme-website")
        self.assertEqual(got["mentioned_elsewhere"], [])

    def test_a_single_token_name_matches_only_by_link_never_by_the_word_alone(self):
        write(self.root, "projects/quill/actions.md", "# quill\n\n- [ ] Ship it\n")
        write(self.root, "areas/business/actions.md",
              "# business - Actions\n\n## Next actions\n- [ ] Mention quill in the newsletter\n")
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan Janssen\n\n## Next actions\n"
              "- [ ] See [notes](../../projects/quill/actions.md) before calling Jan\n")
        got = scan(self.root, TODAY, entity="quill")
        self.assertEqual([m["file"] for m in got["mentioned_elsewhere"]],
                         ["areas/network/jan-janssen.md"])


class IdeasAndTriage(VaultCase):

    def test_the_ideas_lane_carries_each_idea_with_its_stage(self):
        build_vault(self.root)
        idea = scan(self.root, TODAY)["ideas"][0]
        self.assertEqual(idea["name"], "orchard-labs")
        self.assertEqual(idea["stage"], "Taste")
        self.assertFalse(idea["dormant"])

    def test_ideas_touched_the_same_day_list_by_name(self):
        for name in ("zeta", "alpha", "mid"):
            write(self.root, f"resources/ideas/{name}/brief.md", f"# {name}\n")
        self.assertEqual([i["name"] for i in scan(self.root, TODAY)["ideas"]],
                         ["alpha", "mid", "zeta"])

    def test_triage_reaches_the_report(self):
        build_vault(self.root)
        self.assertEqual(scan(self.root, TODAY)["triage"],
                         ["20260919 Something - Note.md"])

    def test_an_entity_scope_asks_neither_question(self):
        build_vault(self.root)
        got = scan(self.root, TODAY, entity="acme-website")
        self.assertNotIn("ideas", got)
        self.assertNotIn("triage", got)
        self.assertNotIn("lifecycles", got)


class LifecycleCounts(VaultCase):

    def test_one_line_per_lifecycle_with_counts_by_live_stage(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# Vault", "", "## Deal lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Lead | `areas/business/leads.md` (row) |",
            "| Qualified | `resources/ideas/<company>/` |",
            "| Lost | `archive/ideas/<company>/` |", "",
        ]) + "\n")
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Stage |", "|---|---|", "| Acme | Lead |",
            "", "## Closed", "",
            "| Company | Stage |", "|---|---|", "| Old Co | Lead |", "",
        ]) + "\n")
        write(self.root, "resources/ideas/beta/brief.md", "# Beta\n\n**Stage:** Qualified\n")
        write(self.root, "archive/ideas/gone/brief.md", "# Gone\n\n**Stage:** Lost\n")
        lc = scan(self.root, TODAY)["lifecycles"][0]
        self.assertEqual(lc["heading"], "Deal lifecycle")
        self.assertEqual(lc["counts"], [{"stage": "Lead", "count": 1},
                                        {"stage": "Qualified", "count": 1}])

    def test_a_register_stage_reads_the_way_the_pipeline_reads_it(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# Vault", "", "## Deal lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| Lead, Qualified | `areas/business/leads.md` (row) |",
            "| Negotiating | |", "",
        ]) + "\n")
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "| Company | stage |", "|---|---|",
            "| Acme | Qualified - since 2026-09-01 |", "| Beta | Lead (since 2026-09-02) |", "",
        ]) + "\n")
        lc = scan(self.root, TODAY)["lifecycles"][0]
        self.assertEqual(lc["counts"], [{"stage": "Lead", "count": 1},
                                        {"stage": "Qualified", "count": 1},
                                        {"stage": "Negotiating", "count": 0}])

    def test_a_vault_with_no_lifecycle_carries_an_empty_list(self):
        build_vault(self.root)
        self.assertEqual(scan(self.root, TODAY)["lifecycles"], [])


class VaultKind(VaultCase):

    def test_a_vault_with_no_action_files_is_the_read_only_kind(self):
        write(self.root, "README.md", "# Read-only vault\n")
        write(self.root, "areas/health/brief.md", "# health\n")
        self.assertEqual(scan(self.root, TODAY)["vault_type"], "B")

    def test_a_vault_with_action_files_is_the_full_kind(self):
        build_vault(self.root)
        self.assertEqual(scan(self.root, TODAY)["vault_type"], "A")

    def test_a_collected_vault_is_refused_rather_than_read_as_empty(self):
        write(self.root, "resources/mds/projects__acme__actions.md", "# acme\n\n- [ ] One\n")
        write(self.root, "README.md", "# Collected\n")
        with self.assertRaises(CollectedVault):
            scan(self.root, TODAY)


if __name__ == "__main__":
    unittest.main(verbosity=1)
