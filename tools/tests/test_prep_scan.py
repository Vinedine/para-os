#!/usr/bin/env python3
"""Tests for prep_scan.py. Each one pins a rule of the script, which is the specification.

    python3 test_prep_scan.py
    py -3 test_prep_scan.py

Standard library only, so a vault that runs the skill can run its tests. Every fixture is a
throwaway vault in a temporary directory, with synthetic names only: nothing reads or writes
a real vault, and nothing calls a model. The date is passed in, never taken from the clock.

What paraos_vault.py itself decides (a card's names, Stage lines, header fields, lifecycle
tables, open tasks, links) is tested in test_paraos_vault.py.
What is tested here is what this skill alone decides: which card a person is, which entities
and records belong to them, and which open items name them.
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
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-prep" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from prep_scan import RECORDS_SHOWN, main, parse_person, scan

TODAY = date(2026, 9, 21)
SCRIPT = SCRIPTS / "prep_scan.py"

LIFECYCLE = "\n".join([
    "# Vault", "",
    "## Deal lifecycle", "",
    "| Stage | Exit criterion | PARA home |",
    "|---|---|---|",
    "| Lead | A first conversation has been held | `areas/business/leads.md` (row) |",
    "| Qualified | The signer is named | `resources/ideas/<company>/` |",
    "| Proposal | The signer has seen it, and the next meeting is dated | `resources/ideas/<company>/` |",
    "| Goal | First paid phase agreed | `projects/<company>/` |", "",
]) + "\n"

JAN = "# Jan Janssen\n\n**Role:** Owner\n\n## Next actions\n\n_None currently._\n"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class VaultCase(unittest.TestCase):
    """A temporary vault root per test, removed afterwards, its CLAUDE.md declaring the one
    Deal lifecycle above."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        write(self.root, "CLAUDE.md", LIFECYCLE)
        (self.root / "projects").mkdir()

    def scan(self, *people):
        return scan(self.root, list(people), TODAY)

    def person(self, who):
        return self.scan(who)["people"][0]


class Parsing(unittest.TestCase):

    def test_a_calendar_attendee_carries_a_name_and_an_address(self):
        self.assertEqual(parse_person('"Jan Janssen" <Jan@Acme.example>'),
                         ("Jan Janssen", "jan@acme.example"))

    def test_a_bare_address_is_an_address_alone(self):
        self.assertEqual(parse_person("jan@acme.example"), (None, "jan@acme.example"))

    def test_a_parenthetical_is_dropped_and_last_first_kept_whole(self):
        self.assertEqual(parse_person("Peeters, Ann (Acme)"), ("Peeters, Ann", None))


class Matching(VaultCase):

    def test_a_whole_name_matches_in_either_order(self):
        write(self.root, "areas/network/peeters-ann.md", "# Peeters Ann\n")
        for who in ("Ann Peeters", "Peeters, Ann"):
            p = self.person(who)
            self.assertEqual((p["status"], p["matched_by"], p["card"]["path"]),
                             ("matched", "name", "areas/network/peeters-ann.md"))

    def test_the_file_name_answers_for_a_card_titled_by_first_name(self):
        write(self.root, "areas/network/ann-peeters.md", "# Ann\n")
        self.assertEqual(self.person("Ann Peeters")["card"]["path"],
                         "areas/network/ann-peeters.md")

    def test_accents_fold(self):
        write(self.root, "areas/network/desiree-dubois.md", "# Désirée Dubois\n")
        self.assertEqual(self.person("Desiree Dubois")["status"], "matched")

    def test_an_address_the_card_carries_wins_over_the_name(self):
        write(self.root, "areas/network/jan-janssen.md", "# Jan Janssen\n\n**Email:** jan@acme.example\n")
        write(self.root, "areas/network/jan-janssen-senior.md", "# Jan Janssen\n")
        p = self.person("Jan Janssen <JAN@acme.example>")
        self.assertEqual((p["matched_by"], p["card"]["path"]),
                         ("email", "areas/network/jan-janssen.md"))

    def test_an_alias_matches_and_says_so(self):
        write(self.root, "areas/network/marten-van-oost.md",
              "# Marten Van Oost\n\n**Aliases:** Tinus Vanoost\n")
        p = self.person("Tinus Vanoost")
        self.assertEqual((p["status"], p["matched_by"]), ("matched", "alias"))

    def test_a_title_match_outranks_another_cards_alias(self):
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        write(self.root, "areas/network/anna-peeters.md", "# Anna Peeters\n\nAlso: Ann Peeters\n")
        self.assertEqual(self.person("Ann Peeters")["card"]["path"], "areas/network/ann-peeters.md")

    def test_one_word_matches_the_one_card_carrying_it(self):
        write(self.root, "areas/network/jan-janssen.md", JAN)
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        p = self.person("Jan")
        self.assertEqual((p["matched_by"], p["card"]["path"]),
                         ("partial", "areas/network/jan-janssen.md"))

    def test_two_cards_are_ambiguous_and_never_chosen_between(self):
        write(self.root, "areas/network/jan-janssen.md", JAN)
        write(self.root, "areas/network/jan-peeters.md", "# Jan Peeters\n")
        p = self.person("Jan")
        self.assertEqual(p["status"], "ambiguous")
        self.assertEqual(p["candidates"], ["areas/network/jan-janssen.md",
                                           "areas/network/jan-peeters.md"])
        self.assertNotIn("card", p)
        self.assertIsNone(p["mentions"])
        self.assertIsNone(p["records"])

    def test_an_address_spelling_a_name_matches_that_name(self):
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        p = self.person("ann.peeters@acme.example")
        self.assertEqual((p["matched_by"], p["card"]["path"]),
                         ("email_name", "areas/network/ann-peeters.md"))

    def test_a_card_with_no_title_answers_to_its_file_name(self):
        write(self.root, "areas/network/ann-peeters.md", "**Role:** buyer\n")
        self.assertEqual(self.person("Ann Peeters")["card"]["name"], "ann-peeters")

    def test_nobody_matching_is_no_card(self):
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        for who in ("Lotte Maes", "info@acme.example", "lotte.maes@acme.example"):
            p = self.person(who)
            self.assertEqual((p["status"], p["matched_by"]), ("no_card", None))

    def test_a_vault_without_a_network_area_has_no_cards(self):
        self.assertEqual(self.person("Ann Peeters")["status"], "no_card")

    def test_a_folder_readme_and_an_actions_file_are_not_cards(self):
        write(self.root, "areas/network/README.md", "# Ann Peeters\n")
        write(self.root, "areas/network/actions.md", "# Ann Peeters\n")
        self.assertEqual(self.person("Ann Peeters")["status"], "no_card")

    def test_the_same_person_named_twice_is_scanned_once(self):
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        self.assertEqual(len(self.scan("Ann Peeters", "Ann Peeters")["people"]), 1)


class TheCard(VaultCase):

    def test_kind_header_and_open_items_come_from_the_card(self):
        write(self.root, "areas/network/jan-janssen.md", "\n".join([
            "# Jan Janssen", "", "**Kind:** buyer", "**Email:** jan@acme.example", "",
            "## Next actions", "",
            "- [ ] Send Jan the revised quote 📅 2026-09-25",
            "- [x] Call Jan back ✅ 2026-09-01", ""]))
        card = self.person("Jan Janssen")["card"]
        self.assertEqual(card["kind"], "buyer")
        self.assertEqual(card["emails"], ["jan@acme.example"])
        self.assertEqual([(i["text"], i["due"]) for i in card["items"]],
                         [("Send Jan the revised quote", "2026-09-25")])
        self.assertNotIn("first_link", card["items"][0])
        self.assertNotIn("malformed_date", card["items"][0])

    def test_a_card_with_no_kind_line_says_none(self):
        write(self.root, "areas/network/jan-janssen.md", JAN)
        self.assertIsNone(self.person("Jan Janssen")["card"]["kind"])


class Mentions(VaultCase):

    def setUp(self):
        super().setUp()
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan Janssen\n\n## Next actions\n\n- [ ] Ask Jan about the quote\n")
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")

    def mentioned(self, text, who="Jan Janssen"):
        write(self.root, "projects/acme/actions.md", f"# Acme\n\n## Open\n\n{text}\n")
        return [(m["file"], m["by"]) for m in self.person(who)["mentions"]]

    def test_a_link_to_the_card_is_a_mention(self):
        self.assertEqual(self.mentioned("- [ ] Ring [him](../../areas/network/jan-janssen.md)"),
                         [("projects/acme/actions.md", "link")])

    def test_a_link_to_another_file_is_not(self):
        self.assertEqual(self.mentioned("- [ ] Ring [the office](brief.md)"), [])

    def test_the_whole_name_in_either_order_is_a_mention(self):
        self.assertEqual(self.mentioned("- [ ] Raise the scope with Janssen, Jan"),
                         [("projects/acme/actions.md", "name")])

    def test_a_first_name_no_other_card_carries_is_a_short_name(self):
        self.assertEqual(self.mentioned("- [ ] Raise with Jan: the renewal terms"),
                         [("projects/acme/actions.md", "short name")])

    def test_a_word_another_card_also_carries_is_not_a_short_name(self):
        write(self.root, "areas/network/jan-peeters.md", "# Jan Peeters\n")
        self.assertEqual(self.mentioned("- [ ] Raise with Jan: the renewal terms",
                                        "Jan Janssen"), [])

    def test_a_month_before_a_number_is_not_a_name(self):
        self.assertEqual(self.mentioned("- [ ] Book the venue for Jan 2027"), [])

    def test_a_short_name_matches_its_case_only(self):
        self.assertEqual(self.mentioned("- [ ] Fix the jan field in the export"), [])

    def test_an_address_on_the_card_is_a_mention(self):
        write(self.root, "areas/network/jan-janssen.md", "# Jan Janssen\n\njan@acme.example\n")
        self.assertEqual(self.mentioned("- [ ] Reply to JAN@acme.example"),
                         [("projects/acme/actions.md", "email")])

    def test_the_cards_own_items_are_not_mentions_but_another_cards_are(self):
        write(self.root, "areas/network/ann-peeters.md",
              "# Ann Peeters\n\n## Next actions\n\n- [ ] Introduce Ann to Jan Janssen\n")
        found = self.mentioned("- [ ] Unrelated")
        self.assertEqual(found, [("areas/network/ann-peeters.md", "name")])

    def test_a_closed_item_and_a_fenced_one_are_not_mentions(self):
        self.assertEqual(self.mentioned("- [x] Raise with Jan Janssen\n\n```\n"
                                        "- [ ] Raise with Jan Janssen\n```"), [])

    def test_a_person_with_no_card_is_found_by_whole_name(self):
        found = self.mentioned("- [ ] Send Lotte Maes the deck", "Lotte Maes (Acme)")
        self.assertEqual(found, [("projects/acme/actions.md", "name")])

    def test_a_one_word_name_with_no_card_is_not_searched(self):
        p = self.person("Lotte")
        self.assertEqual(p["status"], "no_card")
        self.assertIsNone(p["mentions"])
        self.assertIsNone(p["rows"])
        self.assertIsNone(p["unfiled"])
        self.assertEqual((p["records"], p["records_total"]), (None, None))


class AcmeDeal(VaultCase):
    """Jan's card links one deal, resources/ideas/acme/, whose brief each test writes."""

    def deal(self, header):
        write(self.root, "resources/ideas/acme/brief.md", "# Acme\n\n" + header + "\n")

    def entity(self):
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan Janssen\n\n[Acme](../../resources/ideas/acme/brief.md)\n")
        return self.scan("Jan Janssen")["entities"][0]


class Entities(AcmeDeal):

    def test_entities_come_from_the_card_and_from_briefs_linking_it(self):
        write(self.root, "areas/network/jan-janssen.md", "\n".join([
            "# Jan Janssen", "",
            "- [Acme](../../projects/acme/brief.md), the [Acme deal](../../resources/ideas/acme/brief.md)",
            "- [Ann](ann-peeters.md), [the area](../business/actions.md), [site](https://acme.example)", ""]))
        write(self.root, "projects/acme/brief.md", "# Acme\n\n[Jan](../../areas/network/jan-janssen.md)\n")
        write(self.root, "projects/beta/README.md", "# Beta\n\n[Jan](../../areas/network/jan-janssen.md)\n")
        write(self.root, "projects/gamma/brief.md", "# Gamma\n")
        write(self.root, "resources/ideas/acme/brief.md", "# Acme deal\n")
        write(self.root, "areas/business/actions.md", "# Business\n")
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        report = self.scan("Jan Janssen")
        self.assertEqual(report["people"][0]["entities"], [
            {"path": "areas/business", "via": "card"},
            {"path": "projects/acme", "via": "both"},
            {"path": "projects/beta", "via": "entity"},
            {"path": "resources/ideas/acme", "via": "card"}])
        self.assertEqual([e["path"] for e in report["entities"]],
                         ["areas/business", "projects/acme", "projects/beta",
                          "resources/ideas/acme"])

    def test_two_attendees_share_one_entity_record(self):
        for name in ("jan-janssen", "ann-peeters"):
            write(self.root, f"areas/network/{name}.md",
                  f"# {name.replace('-', ' ').title()}\n\n[Acme](../../projects/acme/brief.md)\n")
        write(self.root, "projects/acme/brief.md", "# Acme\n")
        report = self.scan("Jan Janssen", "Ann Peeters")
        self.assertEqual(len(report["entities"]), 1)

    def test_a_staged_entity_carries_its_stage_and_the_tables_row(self):
        self.deal("\n".join([
            "**Stage:** Proposal (since 2026-09-01; prices hold to 2026-09-30)",
            "**Champion:** [Jan](../../../areas/network/jan-janssen.md)",
            "**Signer:** unknown", "**Last touch:** 2026-09-15, proposal sent"]))
        e = self.entity()
        self.assertEqual(e["stage"]["lifecycle"], "Deal lifecycle")
        self.assertEqual(e["stage"]["name"], "Proposal")
        self.assertEqual(e["stage"]["days_in_stage"], 20)
        self.assertEqual(e["stage"]["columns"]["Exit criterion"],
                         "The signer has seen it, and the next meeting is dated")
        self.assertEqual(e["stage"]["dated_facts"],
                         [{"clause": "prices hold to 2026-09-30", "date": "2026-09-30",
                           "days_ahead": 9}])
        self.assertEqual(e["header"]["Last touch"], "2026-09-15, proposal sent")
        self.assertEqual(e["unknown"], ["Signer"])

    def test_no_since_is_an_unknown_time_in_stage(self):
        self.deal("**Stage:** Qualified")
        self.assertIsNone(self.entity()["stage"]["days_in_stage"])

    def test_a_stage_naming_no_declared_stage_is_no_stage(self):
        self.deal("**Stage:** Concept")
        e = self.entity()
        self.assertIsNone(e["stage"])
        self.assertEqual(e["header"], {"Stage": "Concept"})

    def test_an_entity_with_no_document_is_named_by_its_folder(self):
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan Janssen\n\n[Acme](../../projects/acme/actions.md)\n")
        write(self.root, "projects/acme/actions.md", "# Acme\n\n- [ ] Ship it\n")
        e = self.scan("Jan Janssen")["entities"][0]
        self.assertEqual((e["title"], e["document"], e["stage"], e["do_not_raise"]),
                         ("acme", None, None, []))
        self.assertEqual(e["actions"], {"path": "projects/acme/actions.md", "open": 1,
                                        "next": None})

    def test_a_stage_two_lifecycles_share_is_read_against_the_home_holding_it(self):
        write(self.root, "CLAUDE.md", LIFECYCLE + "\n".join([
            "## Property lifecycle", "",
            "| Stage | Exit criterion | PARA home |", "|---|---|---|",
            "| Proposal | The offer is accepted | `areas/properties/<property>/` |", ""]) + "\n")
        self.deal("**Stage:** Proposal (since 2026-09-11)")
        self.assertEqual(self.entity()["stage"]["lifecycle"], "Deal lifecycle")

    def test_the_next_dated_open_item_and_the_open_count(self):
        self.deal("**Stage:** Qualified")
        write(self.root, "resources/ideas/acme/actions.md", "\n".join([
            "# Acme", "", "- [ ] Undated", "- [ ] Later 📅 2026-10-30",
            "- [ ] Sooner ⏳ 2026-09-25", "- [x] Done ✅ 2026-09-01", ""]))
        self.assertEqual(self.entity()["actions"], {
            "path": "resources/ideas/acme/actions.md", "open": 3,
            "next": {"line": 5, "text": "Sooner", "due": "2026-09-25"}})

    def test_the_newest_source_is_read_from_the_date_its_name_opens_on(self):
        self.deal("**Stage:** Qualified")
        write(self.root, "resources/ideas/acme/sources/20260801 Acme intro call.md", "x")
        write(self.root, "resources/ideas/acme/sources/2026-09-10 Acme demo.md", "x")
        write(self.root, "resources/ideas/acme/sources/zz notes.md", "x")
        self.assertEqual(self.entity()["newest_source"], {
            "path": "resources/ideas/acme/sources/2026-09-10 Acme demo.md",
            "date": "2026-09-10", "days_ago": 11})

    def test_no_dated_source_is_none(self):
        self.deal("**Stage:** Qualified")
        write(self.root, "resources/ideas/acme/sources/notes.md", "x")
        self.assertIsNone(self.entity()["newest_source"])

    def test_the_network_area_is_never_an_entity(self):
        write(self.root, "areas/network/jan-janssen.md", "# Jan Janssen\n\n[Ann](ann-peeters.md)\n")
        write(self.root, "areas/network/ann-peeters.md", "# Ann Peeters\n")
        self.assertEqual(self.scan("Jan Janssen")["entities"], [])


class DoNotRaise(AcmeDeal):

    def raised(self, body):
        write(self.root, "resources/ideas/acme/brief.md", "# Acme\n\n" + body)
        return self.entity()["do_not_raise"]

    def test_a_label_with_its_text_and_the_list_directly_under_it(self):
        self.assertEqual(self.raised("\n".join([
            "**Stage:** Qualified", "**Do not raise:** the old invoice",
            "  - their reorganisation", "**Last touch:** 2026-09-15, call", "",
            "- an unrelated list", ""])), ["the old invoice", "their reorganisation"])

    def test_a_bare_label_takes_the_list_after_a_blank_line(self):
        self.assertEqual(self.raised("\n".join([
            "- **Do not raise:**", "", "- pricing", "1. the merger", "", "- not this", ""])),
            ["pricing", "the merger"])

    def test_a_heading_takes_everything_under_it_to_the_next_peer(self):
        self.assertEqual(self.raised("\n".join([
            "## Do not raise", "", "- pricing", "", "Their merger, until it is public.",
            "### Detail", "- the lawsuit", "## Why now", "- not this", ""])),
            ["pricing", "Their merger, until it is public.", "the lawsuit"])

    def test_a_brief_without_one_has_none(self):
        self.assertEqual(self.raised("## Scope\n\n- everything\n"), [])


class Records(VaultCase):

    def setUp(self):
        super().setUp()
        write(self.root, "areas/network/jan-janssen.md", "# Jan Janssen\n\njan@acme.example\n")

    def found(self, who="Jan Janssen"):
        p = self.person(who)
        return [(r["path"], r["by"]) for r in p["records"]], p["records_total"]

    def test_a_record_names_the_person_by_file_name_link_address_or_name(self):
        write(self.root, "projects/acme/sources/20260901 Jan Janssen kickoff.pdf", "%PDF")
        write(self.root, "projects/acme/sources/20260905 Steering.md",
              "**Attendees:** [Jan](../../../areas/network/jan-janssen.md)\n")
        write(self.root, "areas/business/sources/20260910 Thread.eml", "From: jan@acme.example\n")
        write(self.root, "archive/meetings/20260912 Review.md", "Janssen, Jan joined late.\n")
        write(self.root, "resources/ideas/beta/sources/20260801 Intro.txt", "Nobody here.\n")
        write(self.root, "archive/projects/old/sources/20260915 Jan Janssen.md", "Archived.\n")
        self.assertEqual(self.found(), ([
            ("archive/meetings/20260912 Review.md", "name"),
            ("areas/business/sources/20260910 Thread.eml", "email"),
            ("projects/acme/sources/20260905 Steering.md", "link"),
            ("projects/acme/sources/20260901 Jan Janssen kickoff.pdf", "file name")], 4))

    def test_a_record_carries_its_date_and_age_and_an_undated_one_sorts_last(self):
        write(self.root, "projects/acme/sources/notes.md", "Jan Janssen\n")
        write(self.root, "projects/acme/sources/20260911 Call.md", "Jan Janssen\n")
        records = self.person("Jan Janssen")["records"]
        self.assertEqual([(r["date"], r["days_ago"]) for r in records],
                         [("2026-09-11", 10), (None, None)])

    def test_only_the_newest_are_listed_and_the_total_counts_the_rest(self):
        for day in range(1, RECORDS_SHOWN + 3):
            write(self.root, f"archive/meetings/202609{day:02d} Call.md", "Jan Janssen\n")
        records, total = self.found()
        self.assertEqual((len(records), total), (RECORDS_SHOWN, RECORDS_SHOWN + 2))
        self.assertEqual(records[0][0], f"archive/meetings/202609{RECORDS_SHOWN + 2:02d} Call.md")

    def test_an_unfiled_triage_item_naming_the_person_is_listed_apart(self):
        write(self.root, "triage/steering notes.md", "**Present:** Jan Janssen, Ann.\n")
        write(self.root, "triage/other.md", "Nobody here.\n")
        write(self.root, "triage/.gitkeep", "Jan Janssen")
        p = self.person("Jan Janssen")
        self.assertEqual(p["unfiled"], [{"path": "triage/steering notes.md", "by": "name"}])
        self.assertEqual(p["records"], [])

    def test_a_first_name_alone_does_not_make_a_record(self):
        write(self.root, "archive/meetings/20260912 Review.md", "Jan joined late.\n")
        self.assertEqual(self.found(), ([], 0))


class RegisterRows(VaultCase):

    def test_a_row_naming_the_person_carries_its_stage(self):
        write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Stage | Next step |", "|---|---|---|---|",
            "| Acme | Lotte Maes | Lead (since 2026-09-11) | Call back, 2026-09-25 |",
            "| Beta | Ann Peeters | Lead | - |", "",
            "## Closed", "",
            "| Company | Contact | Stage | Next step |", "|---|---|---|---|",
            "| Gamma | Lotte Maes | Won | |", ""]))
        rows = self.person("Lotte Maes")["rows"]
        self.assertEqual([(r["name"], r["closed"], r["line"], r["by"]) for r in rows],
                         [("Acme", False, 7, "name"), ("Gamma", True, 14, "name")])
        self.assertEqual(rows[0]["stage"]["days_in_stage"], 10)
        self.assertEqual(rows[0]["stage"]["columns"]["Exit criterion"],
                         "A first conversation has been held")
        self.assertEqual(rows[0]["cells"]["Next step"], "Call back, 2026-09-25")
        self.assertIsNone(rows[1]["stage"])

    def test_a_declared_register_not_yet_created_holds_no_rows(self):
        self.assertEqual(self.person("Lotte Maes")["rows"], [])


class Report(VaultCase):

    def test_the_report_names_the_vault_the_date_its_root_and_its_lifecycles(self):
        report = self.scan("Ann Peeters")
        self.assertEqual(report["vault"], self.root.resolve().as_posix())
        self.assertEqual(report["today"], "2026-09-21")
        self.assertEqual(report["root"], {"root": False, "missing": ["areas/ or archive/"]})
        self.assertEqual(report["lifecycles"], ["Deal lifecycle"])
        self.assertEqual(report["cards_hold"], "yes")

    def test_what_a_card_may_hold_is_the_vaults_checkbox_row(self):
        write(self.root, "CLAUDE.md", LIFECYCLE + "\n".join([
            "### Where a checkbox may live", "",
            "| Bucket | `actions.md` | State |", "|---|---|---|",
            "| `areas/network/` | never | open items about a person live with the entity |", ""]))
        self.assertEqual(self.scan("Ann Peeters")["cards_hold"], "never")


class CommandLine(VaultCase):

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--vault", str(self.root), *args])
        return code, out.getvalue()

    def usage_error(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as raised:
            main(list(args))
        self.assertEqual(raised.exception.code, 2)
        return err.getvalue()

    def test_indent_pretty_prints_and_today_defaults_to_the_system_date(self):
        before = date.today().isoformat()
        code, out = self.run_main("--person", "Ann Peeters", "--indent", "2")
        self.assertEqual(code, 0)
        self.assertIn('\n  "today": ', out)
        self.assertIn(json.loads(out)["today"], {before, date.today().isoformat()})

    def test_a_named_date_is_measured_against(self):
        code, out = self.run_main("--person", "Ann", "--today", "2026-09-21")
        self.assertEqual(json.loads(out)["today"], "2026-09-21")

    def test_a_person_is_required(self):
        self.assertIn("--person", self.usage_error("--vault", str(self.root)))

    def test_a_malformed_today_is_a_usage_error(self):
        err = self.usage_error("--vault", str(self.root), "--person", "Ann", "--today", "21/09/2026")
        self.assertIn("--today wants YYYY-MM-DD", err)

    def test_a_vault_path_that_is_not_a_folder_is_a_usage_error(self):
        err = self.usage_error("--vault", str(self.root / "missing"), "--person", "Ann")
        self.assertIn("no such vault", err)


class ScriptRun(VaultCase):
    """The script as a separate process, run from the vault with `--vault .`, as SKILL.md and
    para-shared/scripts.md run it."""

    def test_output_is_utf8_json_even_where_the_pipe_defaults_to_ascii(self):
        write(self.root, "areas/network/desiree-dubois.md",
              "# Désirée Dubois\n\n## Next actions\n\n- [ ] Send the café list 📅 2026-09-25\n")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", ".", "--person", "Désirée Dubois",
             "--today", "2026-09-21"],
            cwd=self.root, capture_output=True, timeout=120,
            env=dict(os.environ, PYTHONIOENCODING="ascii"))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        card = json.loads(result.stdout.decode("utf-8"))["people"][0]["card"]
        self.assertEqual(card["items"][0]["text"], "Send the café list")


class MissingLibrary(unittest.TestCase):

    def test_missing_shared_library_exits_2_and_says_where_it_belongs(self):
        # scripts.md: exit 2 stops the skill; the message names what to install.
        with tempfile.TemporaryDirectory() as tmp:
            isolated = Path(tmp) / "skills" / "para-prep" / "scripts"
            isolated.mkdir(parents=True)
            shutil.copy(SCRIPT, isolated / "prep_scan.py")
            result = subprocess.run(
                [sys.executable, str(isolated / "prep_scan.py"), "--vault", ".",
                 "--person", "Ann"], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(result.stderr.startswith("prep_scan: "), result.stderr)
            self.assertIn("install para-shared", result.stderr)
            self.assertNotIn("by hand", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=1)
