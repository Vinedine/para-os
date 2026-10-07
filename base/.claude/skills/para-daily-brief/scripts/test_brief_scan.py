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

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from brief_scan import OPEN_ITEM_CAP, scan


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
        self.assertEqual((task["lane"], task["also_lane"]), ("recurring", "overdue"))

    def test_a_recurring_item_due_today_joins_the_today_lane_but_not_its_total(self):
        write(self.root, "areas/ops/actions.md",
              "# ops\n\n## Recurring\n- [ ] Prune the log 🔁 every month 📅 2026-09-21\n")
        report = scan(self.root, TODAY)
        task = self.task(report, "Prune the log")
        self.assertEqual((task["lane"], task["also_lane"]), ("recurring", "today"))
        self.assertIn({"file": "areas/ops/actions.md", "line": 4}, report["lanes"]["today"])
        self.assertIn({"file": "areas/ops/actions.md", "line": 4}, report["lanes"]["recurring"])
        self.assertEqual(self.task(report, "Weekly review")["also_lane"], "overdue")
        self.assertIsNone(self.task(report, "Due today")["also_lane"])

    def test_an_overdue_recurring_item_joins_the_overdue_lane_but_not_its_total(self):
        weekly = self.task(self.report, "Weekly review")["line"]
        overdue = [(i["file"], i["line"]) for i in self.report["lanes"]["overdue"]]
        self.assertIn(("projects/acme-website/actions.md", weekly), overdue)
        self.assertEqual(self.report["totals"]["overdue"],
                         len(overdue) - 1)

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

    def test_an_open_card_checkbox_is_misplaced_where_the_network_row_says_never(self):
        write(self.root, "CLAUDE.md", "# V\n\n### Where a checkbox may live\n\n"
              "| Bucket | `actions.md` | State |\n|---|---|---|\n"
              "| `areas/network/` | **never** | a checkbox on a card is a filing error |\n")
        write(self.root, "areas/network/ann-smet.md",
              "# Ann Smet\n\n## Next actions\n\n- [ ] Send Ann the deck\n- [x] Thanked ✅ 2026-09-01\n")
        got = scan(self.root, TODAY)["flags"]["misplaced"]
        self.assertEqual(got["areas/network"], [{"file": "areas/network/ann-smet.md", "open": 1}])
        self.assertNotIn("closed", got)


class HealthFlags(VaultCase):

    def test_the_cap_flag_fires_one_past_the_cap(self):
        # The vault rule: a file holds at most the cap; at it, adding means closing first.
        items = "\n".join(f"- [ ] Item {n}" for n in range(OPEN_ITEM_CAP + 1))
        write(self.root, "projects/busy/actions.md", f"# busy\n\n{items}\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["over_threshold"],
                         [{"file": "projects/busy/actions.md", "open": OPEN_ITEM_CAP + 1}])

    def test_a_wait_of_twenty_days_is_flagged_and_one_of_three_is_only_listed(self):
        write(self.root, "projects/acme/actions.md", "# acme\n\n"
              "- [ ] Waiting on [Ann Smet](../../areas/network/ann-smet.md): the signed copy "
              "(since 2026-09-01)\n"
              "- [ ] Waiting on Jan: the export (since 2026-09-18)\n")
        got = scan(self.root, TODAY)
        self.assertEqual(sorted(e["line"] for e in got["lanes"]["waiting_on"]), [3, 4])
        self.assertEqual(got["flags"]["waiting_too_long"],
                         [{"file": "projects/acme/actions.md", "line": 3, "person": "Ann Smet",
                           "what": "the signed copy", "days": 20}])
        self.assertNotIn("undated", got["lanes"])

    def test_waits_stay_out_of_the_cap(self):
        items = "\n".join(f"- [ ] Item {n}" for n in range(OPEN_ITEM_CAP))
        waits = "\n".join(f"- [ ] Waiting on Jan: part {n} (since 2026-09-20)" for n in range(3))
        write(self.root, "projects/busy/actions.md", f"# busy\n\n{items}\n{waits}\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["over_threshold"], [])

    def test_a_file_at_the_cap_stays_quiet(self):
        items = "\n".join(f"- [ ] Item {n}" for n in range(OPEN_ITEM_CAP))
        write(self.root, "projects/busy/actions.md", f"# busy\n\n{items}\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["over_threshold"], [])

    def test_a_headline_over_the_cap_is_flagged_and_a_bold_lead_is_the_headline(self):
        long_line = "Send " + "the long story " * 10
        write(self.root, "projects/wordy/actions.md", "# wordy\n\n"
              f"- [ ] {long_line}\n"
              f"- [ ] **Send the deck** {long_line}\n")
        got = scan(self.root, TODAY)["flags"]["long_headlines"]
        self.assertEqual([(r["line"], r["chars"]) for r in got], [(3, len(long_line.strip()))])

    def test_open_boxes_outside_the_action_files_are_flagged_unless_frozen(self):
        write(self.root, "projects/acme/log.md", "# Log\n\n- [ ] Proposed: chase the host\n")
        write(self.root, "projects/acme/sources/20260901 Call.md",
              "# Call\n\nThis is a frozen record.\n\n- [ ] Next step from the room\n")
        got = scan(self.root, TODAY)["flags"]["stray_checkboxes"]
        self.assertEqual(got, [{"file": "projects/acme/log.md", "open": 1}])

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
        items = "\n".join(f"- [ ] Item {n}" for n in range(5))
        write(self.root, "projects/vague/actions.md",
              f"# vague\n\n{items}\n- [ ] Six 📅 2026-09-25\n"
              "- [ ] Seven 📅 2026-09-26\n- [ ] Eight 📅 2026-09-27\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["undated_majority"],
                         {"undated": 5, "open": 8})

    def test_a_new_vaults_bootstrap_actions_are_not_an_undated_majority(self):
        # The bootstrap writes four undated vault-setup actions; day zero is not a backlog.
        items = "\n".join(f"- [ ] Phase {n}" for n in range(1, 5))
        write(self.root, "projects/vault-setup/actions.md", f"# vault-setup\n\n{items}\n")
        self.assertIsNone(scan(self.root, TODAY)["flags"]["undated_majority"])

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

    def test_a_project_with_only_closed_items_has_nothing_open_and_a_recurring_area_does(self):
        write(self.root, "projects/stalled/actions.md", "# stalled\n\n- [x] Kicked off\n")
        write(self.root, "areas/home/actions.md",
              "# home\n\n## Recurring\n- [ ] Check the boiler 🔁 every year 📅 2026-11-01\n")
        got = scan(self.root, TODAY)["flags"]["nothing_open"]
        self.assertEqual([(e["bucket"], e["label"], e["file"]) for e in got],
                         [("P", "stalled", "projects/stalled/actions.md")])
        self.assertIsNotNone(got[0]["touched"])

    def test_an_entity_with_no_action_file_leads_the_nothing_open_list(self):
        write(self.root, "projects/stalled/actions.md", "# stalled\n\n- [x] Kicked off\n")
        write(self.root, "areas/garden/brief.md", "# garden\n")
        got = scan(self.root, TODAY)["flags"]["nothing_open"]
        self.assertEqual([(e["path"], e["file"], e["touched"]) for e in got][0],
                         ("areas/garden", None, None))
        self.assertEqual([e["path"] for e in got], ["areas/garden", "projects/stalled"])

    def test_open_work_anywhere_under_an_entity_or_in_a_contact_file_keeps_it_off(self):
        write(self.root, "areas/properties/main-street-4/actions.md",
              "# main-street-4\n\n- [ ] Index the rent 📅 2027-01-01\n")
        write(self.root, "areas/network/jan-janssen.md", "# Jan\n\n## Next actions\n_None currently._\n")
        self.assertEqual(scan(self.root, TODAY)["flags"]["nothing_open"], [])


class AggregationAndScope(VaultCase):

    def test_contact_files_aggregate_into_one_network_row(self):
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan\n\n## Next actions\n- [ ] Call Jan\n")
        write(self.root, "areas/network/ann-peeters.md",
              "# Ann\n\n## Next actions\n- [ ] Mail Ann\n")
        self.assertEqual(scan(self.root, TODAY)["entities"],
                         [{"bucket": "A", "label": "network", "open": 2, "overdue": 0,
                           "upcoming": 0, "undated": 2, "files": 2, "bar": 10}])

    def test_the_bar_width_rounds_half_up(self):
        write(self.root, "projects/big/actions.md",
              "# big\n\n" + "".join(f"- [ ] Item {n}\n" for n in range(12)))
        write(self.root, "projects/small/actions.md",
              "# small\n\n" + "".join(f"- [ ] Item {n}\n" for n in range(3)))
        bars = {r["label"]: r["bar"] for r in scan(self.root, TODAY)["entities"]}
        self.assertEqual(bars, {"big": 10, "small": 3})

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
        self.assertIsNone(flags["nothing_open"])

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

    def test_a_later_link_into_a_folder_carrying_parentheses_is_read_whole(self):
        write(self.root, "projects/plan(v2)/actions.md", "# p\n\n- [ ] Ship it\n")
        write(self.root, "areas/business/actions.md",
              "# business - Actions\n\n## Next actions\n"
              "- [ ] See [x](https://example.com) and [p](../../projects/plan(v2)/actions.md)\n")
        got = scan(self.root, TODAY, entity="plan(v2)")
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

    def test_a_long_stage_is_cut_to_its_first_sentence_without_link_syntax(self):
        write(self.root, "resources/ideas/jv/brief.md", "# jv\n\n**Stage:** idea (JV in "
              "planning. Not launched). **The name** moved to [the hub](../../../areas/hub/"
              "brief.md) on 2026-09-02.\n")
        write(self.root, "resources/ideas/hub/brief.md", "# hub\n\n**Stage:** Proposal, "
              "see [the offer](../../../areas/offer (v2).md) and e.g. the call\n")
        stages = {i["name"]: i["stage"] for i in scan(self.root, TODAY)["ideas"]}
        self.assertEqual(stages["jv"], "idea (JV in planning. Not launched)")
        self.assertEqual(stages["hub"], "Proposal, see the offer and e.g. the call")

    def test_ideas_touched_the_same_day_list_by_name(self):
        for name in ("zeta", "alpha", "mid"):
            write(self.root, f"resources/ideas/{name}/brief.md", f"# {name}\n")
        self.assertEqual([i["name"] for i in scan(self.root, TODAY)["ideas"]],
                         ["alpha", "mid", "zeta"])

    def test_triage_reaches_the_report(self):
        build_vault(self.root)
        self.assertEqual(scan(self.root, TODAY)["triage"],
                         ["20260919 Something - Note.md"])

    def test_an_idea_carries_days_in_stage_its_revisit_sentence_and_what_names_it(self):
        build_vault(self.root)
        write(self.root, "resources/ideas/acme-deal/brief.md", "\n".join([
            "# Acme deal", "", "**Stage:** Qualified (since 2026-09-01; prices hold to 2026-10-31)",
            "", "Some prose about it. Revisit when [Jan](../../../areas/network/jan.md) has "
            "replied, or by month end. Then decide.", ""]))
        write(self.root, "areas/business/actions.md", "# b\n\n"
              "- [ ] Call about [the deal](../../resources/ideas/acme-deal/brief.md) 📅 2026-09-25\n"
              "- [ ] Send the acme deal deck\n- [ ] Unrelated thing\n")
        idea = next(i for i in scan(self.root, TODAY)["ideas"] if i["name"] == "acme-deal")
        self.assertEqual((idea["since"], idea["days_in_stage"]), ("2026-09-01", 20))
        self.assertEqual(idea["revisit"], "Revisit when Jan has replied, or by month end")
        self.assertEqual(idea["actions"], [{"file": "areas/business/actions.md", "line": 3},
                                           {"file": "areas/business/actions.md", "line": 4}])

    def test_an_idea_without_a_since_date_or_trigger_carries_none(self):
        build_vault(self.root)
        idea = scan(self.root, TODAY)["ideas"][0]
        self.assertEqual((idea["days_in_stage"], idea["revisit"], idea["actions"]),
                         (None, None, []))

    def test_a_triage_note_previews_its_sender_title_and_first_paragraph(self):
        build_vault(self.root)
        write(self.root, "triage/20260920 Mail - Hello.md", "\n".join([
            "---", "source: gmail", "---", "# Re: Hello", "",
            "- **From:** Jan Janssen <jan@example.be>", "- **Received:** 2026-09-20", "",
            "**2026-09-20, Jan to Vincent**", "", "Plus: one thing.", "Second line.", "",
            "Later paragraph."]))
        got = scan(self.root, TODAY)["triage_preview"]["20260920 Mail - Hello.md"]
        self.assertEqual(got, {"from": "Jan Janssen <jan@example.be>", "subject": "Re: Hello",
                               "excerpt": "Plus: one thing. Second line."})

    def test_an_eml_previews_its_headers_and_plain_body_and_other_formats_have_none(self):
        build_vault(self.root)
        write(self.root, "triage/m.eml", "From: Ann <ann@example.be>\nSubject: Quote\n"
              "Content-Type: text/plain; charset=utf-8\n\nHello,\n\nthe quote is attached.\n")
        (self.root / "triage" / "scan.docx").write_bytes(b"PK\x03\x04")
        got = scan(self.root, TODAY)["triage_preview"]
        self.assertEqual(got["m.eml"], {"from": "Ann <ann@example.be>", "subject": "Quote",
                                        "excerpt": "Hello, the quote is attached."})
        self.assertNotIn("scan.docx", got)

    def test_a_sign_in_code_or_reset_link_is_marked_auth_and_never_previewed(self):
        build_vault(self.root)
        write(self.root, "triage/20260920 Your code 1a2b3c.md",
              "# Your code\n\n- **From:** Shop <noreply@shop.example>\n\n"
              "Your verification code is 482913.\n")
        write(self.root, "triage/reset.eml", "From: Bank <noreply@bank.example>\n"
              "Subject: Account notice\nContent-Type: text/plain; charset=utf-8\n\n"
              "Reset your password: https://bank.example/reset?token=9f8e7d\n")
        (self.root / "triage" / "Your sign-in link 774411.pdf").write_bytes(b"%PDF-1.4")
        got = scan(self.root, TODAY)["triage_preview"]
        for name in ("20260920 Your code 1a2b3c.md", "reset.eml", "Your sign-in link 774411.pdf"):
            self.assertEqual(got[name], {"auth": True}, name)
        for secret in ("482913", "9f8e7d", "noreply@"):
            self.assertNotIn(secret, json.dumps(got))

    def test_a_booking_confirmation_code_is_not_a_sign_in_code(self):
        build_vault(self.root)
        write(self.root, "triage/booking.md", "# Your booking\n\n"
              "Your booking confirmation code is K7Q2. The invoice is attached.\n")
        got = scan(self.root, TODAY)["triage_preview"]["booking.md"]
        self.assertNotIn("auth", got)

    def test_a_pdf_previews_through_its_markdown_twin(self):
        build_vault(self.root)
        (self.root / "triage" / "invoice.pdf").write_bytes(b"%PDF-1.4")
        write(self.root, "triage/invoice.md", "# Invoice 42\n\nAmount due by Friday.\n")
        got = scan(self.root, TODAY)["triage_preview"]
        self.assertEqual(got["invoice.pdf"]["excerpt"], "Amount due by Friday.")

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


class SilentSources(VaultCase):
    """A source's newest delivery to this vault, read from its own ledger in a temporary
    PARAOS_HOME, against the cadence its Triage sources row declares."""

    GRANOLA = "| granola | sync-script 🔁 every week | `resources/scripts/granola.js` | Meetings. |"

    def setUp(self):
        super().setUp()
        self.vault = self.root / "vault"
        self.home = self.root / "home"
        build_vault(self.vault)

    def declare(self, *rows):
        write(self.vault, "CLAUDE.md", "# Vault\n\n## Triage sources\n\n"
              "| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n"
              + "".join(r + "\n" for r in rows))

    def ledger(self, rel, data):
        write(self.home, rel, data if isinstance(data, str) else json.dumps(data))

    def notes(self, vault, *names):
        return {f"{vault.name}-{i}": str(vault / "triage" / n) for i, n in enumerate(names)}

    def silent(self, **kw):
        return scan(self.vault, TODAY, paraos_home=self.home, **kw)["flags"]["silent_sources"]

    def test_a_source_quiet_for_longer_than_its_cadence_is_flagged(self):
        self.declare(self.GRANOLA)
        self.ledger("data/granola/synced.json", {
            **self.notes(self.vault, "20260901 Kickoff.md", "20260912 Review.md"),
            **self.notes(self.root / "other-vault", "20260920 Routed elsewhere.md")})
        self.assertEqual([(s["source"], s["newest"], s["days"], s["cadence"]) for s in self.silent()],
                         [("granola", "2026-09-12", 9, "every week")])

    def test_a_source_heard_from_within_its_cadence_is_not_flagged(self):
        self.declare(self.GRANOLA)
        self.ledger("data/granola/synced.json", self.notes(self.vault, "20260918 Standup.md"))
        self.assertEqual(self.silent(), [])

    def test_a_row_with_no_cadence_or_a_source_with_no_ledger_is_not_checked(self):
        self.declare("| granola | sync-script | `resources/scripts/granola.js` | Meetings. |",
                     "| pocket | sync-script 🔁 every week | `resources/scripts/pocket.py` | Calls. |")
        self.ledger("data/granola/synced.json", self.notes(self.vault, "20260101 Old.md"))
        self.assertEqual(self.silent(), [])

    def test_a_date_later_than_today_never_makes_a_source_current(self):
        self.declare(self.GRANOLA)
        self.ledger("data/granola/synced.json",
                    self.notes(self.vault, "20260901 Real.md", "20261231 Corrupt.md"))
        self.assertEqual([s["newest"] for s in self.silent()], ["2026-09-01"])

    def test_an_unreadable_ledger_is_flagged_never_passed(self):
        self.declare(self.GRANOLA)
        self.ledger("data/granola/synced.json", "{not json")
        got = self.silent()
        self.assertEqual([(s["source"], s["newest"], s["error"]) for s in got],
                         [("granola", None, "unreadable")])

    def test_the_older_cache_copy_of_a_ledger_is_read_too(self):
        self.declare(self.GRANOLA)
        self.ledger("data/granola/synced.json", self.notes(self.vault, "20260901 Early.md"))
        self.ledger("cache/granola/synced.json", self.notes(self.vault, "20260919 Late.md"))
        self.assertEqual(self.silent(), [])

    def test_a_mailbox_reads_what_ingest_routed_to_this_vault(self):
        self.declare("| work | connector: google-workspace 🔁 every 2 weeks | "
                     "`ann@example.com` | Clients. |")
        self.ledger("cache/ingest/ledger.json", {"by_message_id": {}, "mailboxes": {
            "ann@example.com": {
                "t1": {"routed": ["vault"], "seen_date": "2026-09-02T10:00:00+02:00"},
                "t2": {"routed": ["other-vault"], "seen_date": "2026-09-20T10:00:00+02:00"}}}})
        self.assertEqual([(s["source"], s["newest"], s["days"]) for s in self.silent()],
                         [("work", "2026-09-02", 19)])

    def test_an_entity_scope_does_not_check_silence(self):
        self.declare(self.GRANOLA)
        self.ledger("data/granola/synced.json", self.notes(self.vault, "20260901 Old.md"))
        self.assertIsNone(self.silent(entity="acme-website"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
