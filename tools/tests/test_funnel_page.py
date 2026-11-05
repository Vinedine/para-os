#!/usr/bin/env python3
"""Tests for funnel_page.py. Each pins a rule the script's docstring states: a connector row and
a fetch-script row declare a mailbox and a sync-script row does not, the ledger's entries
count by their reason inside the window only, the drops a run log's report line names are
read per exclusion, the decision ledger gives each action type its window share, the kill
switch and the quarantine show, and the script prints the model as one JSON document.

    python3 test_funnel_page.py
    py -3 test_funnel_page.py

Standard library only. Every vault, registry and state file here is synthetic, built in a
temporary folder.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "multi-vault" / "para-ingest" / "scripts"))

from funnel_page import gather, main, parse_table, strip_md  # noqa: E402

TODAY = date(2030, 6, 20)
STAMP = TODAY.strftime("%Y%m%d")
OLD = (TODAY - timedelta(days=30)).isoformat()
RECENT = (TODAY - timedelta(days=2)).isoformat()

SOURCES = """# Fixture Vault Conventions

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| mail-ops | connector: `google-workspace` | `ops@example.test` | Everything about orders. |
| mail-shared | fetch-script | `shared@example.test` via `resources/scripts/outlook.py fetch` | Shared inbox threads. |
| notes | sync-script | `resources/scripts/notes.py` (writes meeting notes to `triage/`) | Meetings carrying the prefix. |

## Something else
"""


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FunnelModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.alpha = Path(self.tmp) / "alpha"
        self.beta = Path(self.tmp) / "beta"
        write(self.alpha, "CLAUDE.md", SOURCES)
        write(self.beta, "CLAUDE.md", "# Beta\n\n## Triage sources\n\n| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n| mail-ops | connector: gmail | `ops@example.test` | Invoices only. |\n")
        write(self.home, "vaults.json", json.dumps([
            {"name": "Alpha", "path": str(self.alpha), "purpose": "Orders and operations.", "active": True},
            {"name": "Beta", "path": str(self.beta), "purpose": "Invoices.", "active": True},
            {"name": "Gone", "path": str(Path(self.tmp) / "gone"), "purpose": "Retired.", "active": False},
            {"name": "Theirs", "path": str(self.beta), "purpose": "Pulled elsewhere.", "active": True, "machine": "the studio laptop"},
        ]))
        write(self.home, "triage-exclusions.json", json.dumps({
            "ops@example.test": [
                {"from": "noreply@shop.test", "reason": "receipts", "added": RECENT},
                {"domain": "school.test", "reason": "class mail", "added": RECENT},
                {"subject_contains": "newsletter", "reason": "noise", "added": RECENT},
            ]}))
        write(self.home, "cache/ingest/ledger.json", json.dumps({"mailboxes": {
            "ops@example.test": {
                "a": {"date": RECENT, "subject": "Order 1", "routed": ["Alpha"], "reason": "rule: Alpha Relevant when"},
                "b": {"date": RECENT, "subject": "Lunch?", "routed": [], "reason": "unrouted: no candidate vault matched"},
                "c": {"date": RECENT, "subject": "Receipt", "routed": [], "reason": "excluded: from noreply@shop.test"},
                "d": {"date": RECENT, "subject": "Order 1 copy", "routed": ["Alpha"], "reason": "rule; suppressed: better-grouped copy"},
                "e": {"date": OLD, "subject": "Old", "routed": ["Alpha"], "reason": "rule"},
                "f": {"date": RECENT, "subject": "Known", "routed": [], "reason": "skipped: already dispositioned"},
            },
            "shared@example.test": {
                "g": {"date": RECENT, "subject": "Invoice 7", "routed": ["Beta", "Alpha"], "reason": "contact"},
            }}}))
        write(self.home, f"cache/ingest/runs/{STAMP}-061500.json", json.dumps({
            "mode": "write", "invocation": "/para-ingest write", "started_at": f"{TODAY.isoformat()}T06:15:00+00:00",
            "source_plan": {"mailboxes": 2, "mailboxes_read": 2, "mailboxes_errored": 0},
            "sync_runs": [{"vault": "Alpha", "script": "resources/scripts/notes.py", "written": 2, "error": None}],
            "exclusions_applied": "ops@example.test: noreply@shop.test dropped 3, domain school.test dropped 1; every other entry 0",
            "files_written": [str(self.alpha / "triage" / "a.md"), str(self.alpha / "triage" / "b.md"), str(self.beta / "triage" / "c.md")],
            "errors": [], "warnings": ["one"]}))
        write(self.home, "cache/ingest/runs/20200101-000000.json", json.dumps({"mode": "write", "files_written": [str(self.alpha / "triage" / "old.md")]}))
        rows = [{"date": RECENT, "item": f"item {i}", "recommended": "File it", "chosen": "File it", "path": "interactive"} for i in range(3)]
        rows.append({"date": RECENT, "item": "item x", "recommended": "File it", "chosen": "Delete (noise)", "path": "interactive"})
        rows.append({"date": RECENT, "item": "item auto", "recommended": "Dismiss (noise)", "chosen": "Dismiss (noise)", "path": "auto"})
        rows.append({"date": OLD, "item": "item old", "recommended": "Add action", "chosen": "Add action", "path": "interactive"})
        write(self.home, "cache/triage/decisions/Alpha.jsonl", "\n".join(json.dumps(r) for r in rows) + "\n")
        write(self.home, "auto-triage.json", json.dumps({"Alpha": {"on": ["Dismiss (noise)"], "demoted": []}}))
        write(self.home, f"quarantine/Alpha/{STAMP}-070000/manifest.json", json.dumps({
            "vault": "Alpha", "run": f"{STAMP}-070000",
            "items": [{"item": "dup.md", "action": "Delete (duplicate)", "reason": "same bytes"},
                      {"item": "noise.md", "action": "Dismiss (noise)", "reason": "a reminder"}]}))
        write(self.home, "quarantine/Alpha/20200101-000000/manifest.json", json.dumps({
            "vault": "Alpha", "run": "20200101-000000", "items": [{"item": "ancient.md", "action": "Dismiss (noise)", "reason": "old"}]}))
        write(self.home, f"cache/triage/proposals/Beta-{STAMP}-0616.md",
              "# Unattended triage: waiting for the operator\n\n| Item | Recommended | Why | Held because |\n|---|---|---|---|\n"
              "| invoice.pdf | Move | an invoice | money owed |\n\n```json\n{\"vault\": \"Beta\", \"run\": \"" + STAMP + "-061626\"}\n```\n")
        write(self.home, "cache/triage/proposals/decided/Beta-old.md", "decided\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_table_rows_read_by_position(self):
        rows = parse_table(SOURCES, "Triage sources")
        self.assertEqual([r[0] for r in rows], ["mail-ops", "mail-shared", "notes"])
        self.assertEqual(parse_table(SOURCES, "Absent"), [])
        translated = "## Triage sources\n\n| Bron | Soort | Eindpunt | Relevant wanneer |\n|---|---|---|---|\n| post | connector: x | `post@example.com` | Alleen facturen. |\n"
        self.assertEqual(parse_table(translated, "Triage sources"), [["post", "connector: x", "`post@example.com`", "Alleen facturen."]])

    def test_connector_and_fetch_script_declare_a_mailbox(self):
        d = gather(str(self.home), 7, today=TODAY)
        self.assertEqual(sorted(v for v, _, _ in d["mailbox_vaults"]["ops@example.test"]), ["Alpha", "Beta"])
        self.assertEqual(d["mailbox_vaults"]["shared@example.test"], [("Alpha", "Shared inbox threads.", "script")])
        self.assertEqual([s["source"] for s in d["sources"] if s["type"].startswith("sync-script")], ["notes"])
        self.assertEqual([v["name"] for v in d["vaults"]], ["Alpha", "Beta"])

    def test_ledger_counts_by_reason_inside_the_window(self):
        L = gather(str(self.home), 7, today=TODAY)["ledger"]
        self.assertEqual((L["seen"], L["routed"], L["unrouted"], L["excluded"], L["suppressed"], L["skipped"]), (6, 2, 1, 1, 1, 1))
        self.assertEqual(L["routed_per_vault"], {"Alpha": 2, "Beta": 1})
        self.assertEqual(L["per_mailbox"]["ops@example.test"]["unrouted"], 1)
        self.assertEqual(L["unrouted_samples"]["ops@example.test"], ["Lunch?"])

    def test_drops_read_from_the_run_line_per_exclusion(self):
        d = gather(str(self.home), 7, today=TODAY)
        by_value = {e["value"]: e["dropped"] for e in d["exclusions"]}
        self.assertEqual(by_value, {"noreply@shop.test": 3, "school.test": 1, "newsletter": 0})
        self.assertEqual(d["drops_unparsed_runs"], 0)
        self.assertEqual(d["staged"], 3)
        self.assertEqual([r["run"] for r in d["runs"]], [f"{STAMP}-061500"])

    def test_drops_from_the_log_per_entry_with_groups_and_the_every_mailbox_key(self):
        write(self.home, "triage-exclusions.json", json.dumps({
            "*": [{"group": "Class list", "any": [{"domain": "school.test"}, {"from": "parent@mail.test"}], "reason": "class mail", "added": RECENT},
                  {"to": "members@club.test", "reason": "club list", "added": RECENT}],
            "ops@example.test": [{"from": "noreply@shop.test", "reason": "receipts", "added": RECENT}]}))
        write(self.home, f"cache/ingest/runs/{STAMP}-161500.json", json.dumps({
            "mode": "write", "files_written": [],
            "exclusions_applied": {"by_entry": {"*": {"Class list": 2, "to members@club.test": 0},
                                                "ops@example.test": {"from noreply@shop.test": 1}},
                                   "dropped": 3, "file": "applied"}}))
        d = gather(str(self.home), 7, today=TODAY)
        rows = {(e["mailbox"], e["label"]): e for e in d["exclusions"]}
        self.assertEqual(rows[("*", "Class list")]["dropped"], 2)
        self.assertEqual(rows[("*", "Class list")]["matchers"], ["domain school.test", "from parent@mail.test"])
        self.assertEqual(rows[("*", "to members@club.test")]["dropped"], 0)
        self.assertEqual(rows[("ops@example.test", "from noreply@shop.test")]["dropped"], 4)
        self.assertEqual((rows[("*", "Class list")]["kind"], rows[("*", "to members@club.test")]["kind"]),
                         ("group", "to"))

    def test_decisions_window_share_and_switches(self):
        d = gather(str(self.home), 7, today=TODAY)
        alpha = d["decisions"]["Alpha"]
        file_it = next(t for t in alpha["types"] if t["type"] == "File it")
        self.assertEqual((file_it["n"], file_it["accepted"], file_it["window_n"]), (4, 3, 4))
        self.assertAlmostEqual(file_it["share"], 0.75)
        self.assertEqual(len(file_it["overrides"]), 1)
        self.assertEqual((alpha["total"], alpha["window"], alpha["window_accepted"]), (5, 4, 3))
        self.assertEqual(d["interactive_window"], 4)
        self.assertEqual(d["switches"]["Alpha"]["on"], ["Dismiss (noise)"])
        self.assertFalse(d["kill_switch"])

    def test_quarantine_and_proposals(self):
        d = gather(str(self.home), 7, today=TODAY)
        self.assertEqual(d["acted"], 2)
        self.assertEqual(d["acted_by_action"], {"Delete (duplicate)": 1, "Dismiss (noise)": 1})
        self.assertEqual([q["in_window"] for q in d["quarantine"]], [False, True])
        self.assertIn("restore --vault-name \"Alpha\" --run " + STAMP + "-070000", d["quarantine"][1]["restore"])
        self.assertEqual(d["waiting_items"], 1)
        self.assertEqual(d["proposals"][0]["vault"], "Beta")
        self.assertEqual(d["proposals"][0]["items"][0]["held"], "money owed")
        self.assertEqual(d["decided"], 1)

    def test_the_kill_switch_shows_once_its_file_exists(self):
        write(self.home, "auto-triage.off", "")
        self.assertTrue(gather(str(self.home), 7, today=TODAY)["kill_switch"])

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, json.loads(out.getvalue())

    def test_main_prints_the_model_as_one_json_document(self):
        code, model = self.run_main("--paraos-home", str(self.home), "--today", TODAY.isoformat())
        self.assertEqual(code, 0)
        self.assertEqual((model["days"], model["since"], model["today"], model["home"]),
                         (7, (TODAY - timedelta(days=7)).isoformat(), TODAY.isoformat(), str(self.home)))
        self.assertEqual(model["ledger"]["seen"], 6)
        gathered = json.loads(json.dumps(gather(str(self.home), 7, today=TODAY)))
        for moving in (model, gathered):
            moving.pop("generated")
        self.assertEqual(model, gathered)

    def test_main_honours_the_window_and_the_home_in_the_environment(self):
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.home)}):
            code, model = self.run_main("--days", "40", "--today", TODAY.isoformat())
        self.assertEqual((code, model["home"], model["days"], model["since"]),
                         (0, str(self.home), 40, (TODAY - timedelta(days=40)).isoformat()))
        self.assertEqual((model["ledger"]["seen"], model["ledger"]["routed"]), (7, 3))

    def test_main_defaults_to_seven_days_up_to_the_system_date(self):
        before = date.today()
        code, model = self.run_main("--paraos-home", str(self.home))
        today = date.fromisoformat(model["today"])
        self.assertTrue(before <= today <= date.today())
        self.assertEqual((code, model["days"], today - date.fromisoformat(model["since"])),
                         (0, 7, timedelta(days=7)))

    def test_a_today_that_is_no_date_stops_with_exit_two(self):
        for bad in ("20300620", "tomorrow", "2030-02-30"):
            out = io.StringIO()
            with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(io.StringIO()):
                main(["--paraos-home", str(self.home), "--today", bad])
            self.assertEqual((stop.exception.code, out.getvalue()), (2, ""))


NORTH_PURPOSE = ("Everything the north office runs day to day: supplier orders, the warehouse rota, deliveries "
                 "and returns, the yearly stock count, and the paperwork each of them leaves behind, kept until "
                 "the next audit closes and the auditors sign off on the file.")
NORTH_RULE = ("Supplier orders and deliveries. Threads from a supplier on the order list, a carrier booking a "
              "slot at the warehouse, or a customer asking where a return went; never newsletters, never the "
              "shared calendar invitations, never anything already filed by hand.")
NORTH_SYNC_RULE = ("Meeting notes whose title carries the office prefix, written by the notes script straight into "
                   "triage, one file per meeting, with the attendees, the decisions and the follow-ups each one "
                   "agreed to take on before the next meeting.")
SOUTH_DESK_RULE = "Seulement les factures du fournisseur."
SOUTH_SHARED_RULE = "Les fils de la boite commune."
LONG_REASON = ("Automated receipts from the checkout that repeat what the order confirmation already said, sent "
               "again whenever a parcel changes hands between two carriers.")
LONG_SUBJECT = ("Question about the delivery window for the second warehouse and whether the loading bay can "
                "take the larger trucks next month")
LONG_QUARANTINE_REASON = ("A reminder the shop sends every week about a loyalty card nobody uses, with the same "
                          "three offers as the week before and a link to unsubscribe that has never worked for "
                          "this address, so it goes to quarantine like the others.")
LONG_PROPOSAL_ITEM = ("Supplier - the signed framework agreement for the next three years with all of its annexes "
                      "and the price list.pdf")


class BrokenRegistryTests(unittest.TestCase):
    def test_an_entry_with_no_name_or_no_path_is_not_a_vault_of_the_run(self):
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        write(home, "vaults.json", json.dumps([{"path": str(home / "nameless")}, {"name": "pathless"}, "junk"]))
        self.assertEqual(gather(str(home), 7, today=TODAY)["vaults"], [])


class RulesTests(unittest.TestCase):
    """The rules the model carries: read whatever the header language, whole and once, beside
    the vault they belong to, with no Markdown markers left in them."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        north, south = Path(self.tmp) / "north", Path(self.tmp) / "south"
        write(north, "CLAUDE.md",
              "# North\n\n## Triage sources\n\n| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n"
              f"| desk | connector: `mail` | `desk@example.com` | **{NORTH_RULE[:30]}**{NORTH_RULE[30:]} |\n"
              f"| notes | sync-script | `resources/scripts/notes.py` | {NORTH_SYNC_RULE} |\n")
        write(south, "CLAUDE.md",
              "# Sud\n\n## Triage sources\n\n| Source | Type | Point d'acces | Pertinent quand |\n|---|---|---|---|\n"
              f"| bureau | connector: `mail` | `desk@example.com` | {SOUTH_DESK_RULE} |\n"
              f"| commun | fetch-script | `shared@example.com` via `resources/scripts/fetch.py` | *{SOUTH_SHARED_RULE}* |\n")
        write(self.home, "vaults.json", json.dumps([
            {"name": "North", "path": str(north), "purpose": NORTH_PURPOSE},
            {"name": "South", "path": str(south), "purpose": "Invoices of the south office."},
        ]))
        write(self.home, "triage-exclusions.json", json.dumps({
            "desk@example.com": [{"from": "receipts@example.com", "reason": LONG_REASON, "added": RECENT}]}))
        write(self.home, "cache/ingest/ledger.json", json.dumps({"mailboxes": {"desk@example.com": {
            "a": {"date": RECENT, "subject": LONG_SUBJECT, "routed": [], "reason": "unrouted: no candidate vault matched"}}}}))
        write(self.home, f"quarantine/North/{STAMP}-070000/manifest.json", json.dumps({
            "vault": "North", "run": f"{STAMP}-070000",
            "items": [{"item": "loyalty.md", "action": "Dismiss (noise)", "reason": LONG_QUARANTINE_REASON}]}))
        write(self.home, f"cache/triage/proposals/North-{STAMP}-0616.md",
              "| Item | Recommended | Why | Held because |\n|---|---|---|---|\n"
              f"| {LONG_PROPOSAL_ITEM} | Move | a contract | a deadline |\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_columns_read_by_position_whatever_the_header_language(self):
        d = gather(str(self.home), 7, today=TODAY)
        self.assertIn(("South", SOUTH_DESK_RULE, "connector"), d["mailbox_vaults"]["desk@example.com"])
        self.assertEqual(d["mailbox_vaults"]["shared@example.com"], [("South", SOUTH_SHARED_RULE, "script")])
        self.assertEqual([(s["source"], s["type"]) for s in d["sources"] if s["vault"] == "South"],
                         [("bureau", "connector: mail"), ("commun", "fetch-script")])

    def test_every_rule_and_every_other_text_is_carried_whole(self):
        d = gather(str(self.home), 7, today=TODAY)
        self.assertEqual([s["relevant"] for s in d["sources"]],
                         [NORTH_RULE, NORTH_SYNC_RULE, SOUTH_DESK_RULE, SOUTH_SHARED_RULE])
        self.assertEqual(d["exclusions"][0]["reason"], LONG_REASON)
        self.assertEqual(d["ledger"]["unrouted_samples"], {"desk@example.com": [LONG_SUBJECT]})
        self.assertEqual(d["quarantine"][0]["items"][0]["reason"], LONG_QUARANTINE_REASON)
        self.assertEqual(d["proposals"][0]["items"][0]["item"], LONG_PROPOSAL_ITEM)

    def test_a_proposal_with_no_metadata_block_takes_its_vault_from_its_file_name(self):
        [proposal] = gather(str(self.home), 7, today=TODAY)["proposals"]
        self.assertEqual((proposal["vault"], proposal["run"]), ("North", ""))

    def test_emphasis_markers_stripped(self):
        self.assertEqual(strip_md("**The company address of record.**"), "The company address of record.")
        self.assertEqual(strip_md("*only* this, __that__ and _those_"), "only this, that and those")
        self.assertEqual(strip_md("`first_last@example.com` reads `resources/*.py`"), "first_last@example.com reads resources/*.py")
        self.assertEqual(strip_md("snake_case_name, 2 * 3 * 4 and docs/*.md"), "snake_case_name, 2 * 3 * 4 and docs/*.md")
        sources = gather(str(self.home), 7, today=TODAY)["sources"]
        self.assertFalse([s for s in sources if "*" in s["relevant"] or "`" in s["type"] + s["endpoint"]])

    def test_each_vault_carries_its_purpose_and_its_rule_per_mailbox(self):
        d = gather(str(self.home), 7, today=TODAY)
        north, south = d["vaults"]
        self.assertEqual((north["name"], north["purpose"]), ("North", NORTH_PURPOSE))
        self.assertEqual(north["mailboxes"], [
            {"mailbox": "desk@example.com", "relevant": NORTH_RULE, "how": "connector"}])
        self.assertEqual((south["name"], south["purpose"]), ("South", "Invoices of the south office."))
        self.assertEqual(south["mailboxes"], [
            {"mailbox": "desk@example.com", "relevant": SOUTH_DESK_RULE, "how": "connector"},
            {"mailbox": "shared@example.com", "relevant": SOUTH_SHARED_RULE, "how": "script"}])


if __name__ == "__main__":
    unittest.main()
