#!/usr/bin/env python3
"""Tests for ingest_scan.py: /para-ingest's plan, script runs and routing preparation.

    python3 test_ingest_scan.py
    py -3 test_ingest_scan.py

Standard library only. Every vault, registry, ledger and script here is synthetic, built in a
temporary folder that stands in for the paraos home.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "multi-vault" / "para-ingest" / "scripts"))

from ingest_scan import main, prepare, route  # noqa: E402

NOW = "2026-10-24T12:00:00+00:00"
WORK = "owner@example.org"
SHARED = "shared@example.org"
OUTLOOK = "outbox@example.net"

SOURCES = """
## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
{rows}
"""

# A sync script fixture: its dry run prints the count in `count.txt`; `--write` records the run.
SYNC = """import sys
from pathlib import Path
here = Path(__file__).resolve().parent
n = int((here / "count.txt").read_text())
if "--write" in sys.argv:
    (here / "written.txt").write_text(str(n))
    print(f"WRITE\\nwrote: {n} · skipped(exists): 0")
else:
    print(f"DRY RUN\\nwould write: {n} · skipped(exists): 0")
"""

# A fetch script fixture: prints one thread for the account it is asked for, and records the
# arguments of every call beside itself.
FETCH = """import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
with (here / "calls.txt").open("a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
account = sys.argv[sys.argv.index("--account") + 1]
msg = {"id": "m1", "message_id": "<o1@example.net>", "received": "2026-10-24T08:00:00Z",
       "from_name": "Olga", "from": "olga@client.example", "from_owner": False,
       "to": [account], "cc": [], "subject": "Order 42", "preview": "Where is my order?",
       "link": "https://outlook.example/o1"}
print(json.dumps([dict(msg, account=account, thread_id="conv-1", message_count=1,
                       read="raw me/messages/m1 --account " + account,
                       participants=["olga@client.example"], messages=[msg])]))
"""


def write(base, rel, text):
    path = Path(base) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def gmail_thread(thread_id="t1", sender="Anna <anna@client.example>", subject="Quarterly report",
                 received="2026-10-24T09:00:00+00:00", mailbox=WORK, message_id=None):
    return {"mailbox": mailbox, "source": "google-workspace", "thread_id": thread_id,
            "subject": subject, "link": f"https://mail.example/{thread_id}", "read": thread_id,
            "text": "preview", "own_messages": False,
            "messages": [{"message_id": message_id or f"<{thread_id}@client.example>",
                          "from": sender, "received": received, "subject": subject,
                          "preview": "Figures attached."}]}


class Case(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "paraos"
        self.home.mkdir()
        self.entries = []

    def vault(self, name, rows=None, active=True, claude=None, purpose=None):
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        text = claude if claude is not None else f"# {name}\n"
        if rows is not None:
            text += SOURCES.format(rows="\n".join(rows))
        write(path, "CLAUDE.md", text)
        (path / "triage").mkdir(exist_ok=True)
        self.entries.append({"name": name, "path": path.as_posix(), "active": active,
                             "purpose": purpose or f"The {name} vault."})
        self.save_registry()
        return path

    def save_registry(self):
        write(self.home, "vaults.json", json.dumps(self.entries))

    def prepare(self, mode="write", **kw):
        return prepare(mode, paraos_home=self.home, now=NOW, **kw)

    def route(self, prepared, connectors=None, unread=()):
        path = None
        if connectors is not None:
            path = write(self.root, "connectors.json", json.dumps(connectors))
        return route(prepared["work"], connectors=path, paraos_home=self.home, unread=unread)

    def run_file(self, routed):
        return json.loads(Path(routed["run"]).read_text(encoding="utf-8"))

    def plan(self, prepared):
        return json.loads((Path(prepared["work"]) / "plan.json").read_text(encoding="utf-8"))

    def log(self, started_at, mode="write", mailboxes=(WORK,), **extra):
        stamp = started_at[:10].replace("-", "") + "-" + started_at[11:19].replace(":", "")
        write(self.home, f"cache/ingest/runs/{stamp}.json", json.dumps(dict(
            {"mode": mode, "started_at": started_at,
             "source_plan": {"declaring_vaults": {mb: ["alpha"] for mb in mailboxes}}},
            **extra)))

    def ledger(self, mailboxes):
        write(self.home, "cache/ingest/ledger.json",
              json.dumps({"mailboxes": mailboxes, "by_message_id": {}}))


def connector_row(mailbox, relevant="Client mail.", server="google-workspace"):
    return f"| work | connector: {server} | `{mailbox}` | {relevant} |"


# A thread an earlier write run staged in alpha and still owed beta, as stage.py logs it.
OWED = {"mailbox": WORK, "thread_id": "t9", "subject": "Lease renewal",
        "routed": ["alpha", "beta"], "delivered": ["alpha"], "owed": ["beta"],
        "keys": ["<t8@client.example>", "<t9@client.example>"],
        "received": "2026-10-18T09:00:00+00:00"}


class Plan(Case):

    def test_a_mailbox_two_vaults_declare_is_one_entry_carrying_both(self):
        self.vault("alpha", [connector_row(WORK, "Client threads.")])
        self.vault("beta", [connector_row(WORK, "Supplier invoices.")])
        got = self.prepare()
        self.assertEqual(len(got["connectors"]), 1)
        entry = got["connectors"][0]
        self.assertEqual((entry["mailbox"], entry["connector"], entry["vaults"]),
                         (WORK, "google-workspace", ["alpha", "beta"]))
        self.assertEqual(got["totals"], {"vaults": 2, "mailboxes": 1, "script_runs": 0})

    def test_a_vault_without_the_block_or_inactive_pulls_nothing(self):
        self.vault("alpha", [connector_row(WORK)])
        self.vault("quiet")
        self.vault("asleep", [connector_row(SHARED)], active=False)
        got = self.prepare()
        self.assertEqual([c["mailbox"] for c in got["connectors"]], [WORK])
        self.assertEqual([v["name"] for v in got["vaults"]], ["alpha", "quiet"])
        self.assertFalse(next(v for v in got["vaults"] if v["name"] == "quiet")["declared"])

    def test_an_unmounted_vault_is_an_error_not_an_absence(self):
        self.vault("alpha", [connector_row(WORK)])
        self.entries.append({"name": "gone", "path": (self.root / "nowhere").as_posix(),
                             "active": True, "purpose": "Not mounted."})
        self.save_registry()
        got = self.prepare()
        gone = next(v for v in got["vaults"] if v["name"] == "gone")
        self.assertIn("not mounted", gone["error"])
        self.assertTrue(any("gone" in e for e in got["errors"]))

    def test_vaults_on_one_unmounted_drive_are_one_failure(self):
        self.vault("alpha", [connector_row(WORK)])
        for name in ("x", "y"):
            self.entries.append({"name": name, "path": f"Q:/Team vaults/{name}", "active": True,
                                 "purpose": "On a drive that is not there."})
        self.save_registry()
        got = self.prepare()
        self.assertEqual(got["drives"], [{"drive": "Q:", "vaults": ["x", "y"]}])
        self.assertEqual(len([e for e in got["errors"] if "not mounted" in e]), 2)

    def test_an_unmounted_vault_keeps_the_mailboxes_the_newest_log_gave_it(self):
        self.vault("alpha", [connector_row(WORK)])
        self.entries.append({"name": "gone", "path": (self.root / "nowhere").as_posix(),
                             "active": True, "purpose": "Not mounted."})
        self.save_registry()
        write(self.home, "cache/ingest/runs/20261023-120000.json", json.dumps(
            {"mode": "write", "started_at": "2026-10-23T12:00:00+00:00",
             "source_plan": {"declaring_vaults": {WORK: ["alpha", "gone"]}}}))
        got = self.prepare()
        self.assertEqual(got["connectors"][0]["vaults"], ["alpha", "gone"])
        routed = self.route(got, [gmail_thread()])
        self.assertEqual(routed["to_judge"][0]["candidates"], ["alpha", "gone"])

    def test_recording_and_drive_rows_are_skipped(self):
        self.vault("alpha", [connector_row(WORK),
                             "| calls | connector: granola recording | account | Meetings. |",
                             "| docs | drive | `folder-id` | Stubs. |"])
        got = self.prepare()
        self.assertEqual([c["mailbox"] for c in got["connectors"]], [WORK])
        self.assertEqual(sorted(s["source"] for s in got["skipped"]), ["calls", "docs"])

    def test_a_row_another_writer_pulls_is_skipped(self):
        claude = ("# Team\n\n## Who writes this vault\n\n| Person | Role |\n|---|---|\n"
                  "| [Me](areas/network/me.md) | keeper |\n"
                  "| [Sam](areas/network/sam.md) | member |\n")
        self.vault("team", [connector_row(WORK),
                            f"| sam | connector: google-workspace | `{SHARED}`, pulled by Sam "
                            "| Sam's mail. |"], claude=claude)
        write(self.home, "operator.json", json.dumps({"card": "me"}))
        got = self.prepare()
        self.assertEqual([c["mailbox"] for c in got["connectors"]], [WORK])
        self.assertEqual(got["skipped"][0]["reason"], "pulled by Sam")

    def test_the_plan_is_kept_in_the_work_folder(self):
        self.vault("alpha", [connector_row(WORK, "Client threads.")])
        got = self.prepare()
        plan = json.loads((Path(got["work"]) / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["mode"], "write")
        self.assertEqual(plan["started_at"], NOW)
        self.assertEqual(plan["mailboxes"][WORK]["relevant_when"],
                         {"alpha": "Client threads."})


class Windows(Case):

    def setUp(self):
        super().setUp()
        self.vault("alpha", [connector_row(WORK), connector_row(SHARED)])

    def since(self, prepared):
        return {c["mailbox"]: c["since"] for c in prepared["connectors"]}

    def test_a_write_run_starts_a_day_before_the_last_write_that_read_the_mailbox(self):
        self.log("2026-10-23T06:00:00+00:00")
        self.assertEqual(self.since(self.prepare()), {WORK: "2026-10-22T06:00:00+00:00",
                                                      SHARED: "2026-10-22T12:00:00+00:00"})

    def test_a_run_whose_errors_name_the_mailbox_did_not_read_it(self):
        self.log("2026-10-20T06:00:00+00:00")
        self.log("2026-10-23T06:00:00+00:00", errors=[f"{WORK}: connector could not be read"])
        self.assertEqual(self.since(self.prepare())[WORK], "2026-10-19T06:00:00+00:00")

    def test_a_preview_or_a_run_after_now_moves_no_cursor(self):
        self.log("2026-10-23T06:00:00+00:00", mode="preview")
        self.log("2026-10-25T06:00:00+00:00")
        self.assertEqual(self.since(self.prepare())[WORK], "2026-10-22T12:00:00+00:00")

    def test_preview_reads_30_days_and_days_sets_every_mailbox(self):
        self.log("2026-10-23T06:00:00+00:00")
        self.assertEqual(set(self.since(self.prepare("preview")).values()),
                         {"2026-09-24T12:00:00+00:00"})
        self.assertEqual(set(self.since(self.prepare("write", days=5)).values()),
                         {"2026-10-19T12:00:00+00:00"})

    def test_a_fetch_script_is_asked_for_the_whole_days_that_reach_its_since(self):
        vault = self.vault("orders", [f"| mail | fetch-script | `{OUTLOOK}` via "
                                      "`resources/scripts/outlook.py fetch` | Orders. |"])
        write(vault, "resources/scripts/outlook.py", FETCH)
        self.log("2026-10-20T18:00:00+00:00", mailboxes=(OUTLOOK,))
        self.prepare()
        self.assertEqual((vault / "resources/scripts/calls.txt").read_text().split()[-2:],
                         ["--days", "5"])

    def test_the_window_reaches_back_to_a_thread_still_undelivered(self):
        self.log("2026-10-24T06:00:00+00:00", undelivered=[dict(OWED, owed=["gone"])])
        self.assertEqual(self.since(self.prepare())[WORK], "2026-10-17T09:00:00+00:00")


class Undelivered(Case):

    def setUp(self):
        super().setUp()
        self.vault("alpha", [connector_row(WORK)])
        self.beta = self.vault("beta", [connector_row(WORK)])

    def recheck(self, record=OWED, entry=None, by_message_id=None):
        self.log("2026-10-24T06:00:00+00:00", undelivered=[record])
        write(self.home, "cache/ingest/ledger.json", json.dumps(
            {"mailboxes": {WORK: {"t9": entry}} if entry else {},
             "by_message_id": by_message_id or {}}))
        plan = self.plan(self.prepare())
        return plan["undelivered"], plan["resolved"]

    def test_a_thread_no_check_settles_stays_undelivered(self):
        self.assertEqual(self.recheck(), ([OWED], []))

    def test_a_ledger_watermark_at_its_newest_message_resolves_it(self):
        entry = {"routed": ["alpha", "beta"], "seen_through": "<t9@client.example>",
                 "seen_date": "2026-10-18T09:00:00+00:00"}
        self.assertEqual(self.recheck(entry=entry), ([], [OWED]))

    def test_a_ledger_watermark_from_before_it_resurfaced_does_not(self):
        entry = {"routed": ["alpha"], "seen_through": "<t7@client.example>",
                 "seen_date": "2026-10-16T09:00:00+00:00"}
        self.assertEqual(self.recheck(entry=entry), ([OWED], []))

    def test_every_key_recorded_against_the_owed_vault_resolves_it(self):
        both = {"<t8@client.example>": ["alpha", "beta"], "<t9@client.example>": ["alpha", "beta"]}
        self.assertEqual(self.recheck(by_message_id=both), ([], [OWED]))
        one = dict(both, **{"<t9@client.example>": ["alpha"]})
        self.assertEqual(self.recheck(by_message_id=one)[0], [OWED])

    def test_a_note_named_for_the_thread_in_the_owed_vault_resolves_it(self):
        from paraos_mail import thread_hash
        write(self.beta, f"triage/20261018 Lease renewal {thread_hash('t9')}.md", "x\n")
        self.assertEqual(self.recheck(), ([], [OWED]))

    def test_a_vault_settled_leaves_only_the_others_owed(self):
        from paraos_mail import thread_hash
        write(self.beta, f"triage/20261018 Lease renewal {thread_hash('t9')}.md", "x\n")
        still, resolved = self.recheck(dict(OWED, owed=["beta", "gone"]))
        self.assertEqual((still, resolved), ([dict(OWED, owed=["gone"],
                                                   delivered=["alpha", "beta"])], []))

    def test_only_the_newest_write_log_is_read(self):
        self.log("2026-10-23T06:00:00+00:00", undelivered=[OWED])
        self.log("2026-10-24T06:00:00+00:00", undelivered=[])
        plan = self.plan(self.prepare())
        self.assertEqual((plan["undelivered"], plan["resolved"]), ([], []))

    def test_route_carries_both_into_the_run_file(self):
        self.log("2026-10-24T06:00:00+00:00", undelivered=[OWED])
        run = self.run_file(self.route(self.prepare(), []))
        self.assertEqual((run["undelivered"], run["resolved"], run["carry_over"]),
                         ([OWED], [], []))


class CarryOver(Case):

    def setUp(self):
        super().setUp()
        self.vault("alpha", [connector_row(WORK)])

    def preview(self, started_at, *decisions):
        self.log(started_at, mode="preview", decisions=list(decisions))

    def decision(self, thread_id, received="2026-10-10T09:00:00+00:00", routed=("alpha",)):
        return {"mailbox": WORK, "thread_id": thread_id, "subject": f"Subject {thread_id}",
                "received": received, "routed": list(routed), "reason": "rule: alpha"}

    def carry(self, mode="write"):
        return self.plan(self.prepare(mode))["carry_over"]

    def test_a_first_write_carries_what_a_preview_routed_past_its_window(self):
        self.preview("2026-10-20T08:00:00+00:00", self.decision("old"),
                     self.decision("fresh", "2026-10-23T09:00:00+00:00"),
                     self.decision("nowhere", routed=()), self.decision("held"))
        self.ledger({WORK: {"held": {"routed": ["alpha"], "seen_through": "<held@x.example>",
                                     "seen_date": "2026-10-10T09:00:00+00:00"}}})
        self.assertEqual(self.carry(), [{
            "mailbox": WORK, "thread_id": "old", "subject": "Subject old", "routed": ["alpha"],
            "received": "2026-10-10T09:00:00+00:00", "days": 16}])

    def test_a_mailbox_a_write_run_read_carries_nothing(self):
        self.preview("2026-10-20T08:00:00+00:00", self.decision("old"))
        self.log("2026-10-21T08:00:00+00:00")
        self.assertEqual(self.carry(), [])

    def test_a_preview_older_than_the_last_write_is_not_read(self):
        self.preview("2026-10-20T08:00:00+00:00", self.decision("old"))
        self.log("2026-10-21T08:00:00+00:00", mailboxes=(SHARED,))
        self.assertEqual(self.carry(), [])

    def test_the_newest_preview_decides_a_thread_routed_twice(self):
        self.preview("2026-10-19T08:00:00+00:00", self.decision("old"))
        self.preview("2026-10-20T08:00:00+00:00", self.decision("old", routed=()))
        self.assertEqual(self.carry(), [])

    def test_a_preview_carries_nothing(self):
        self.preview("2026-10-20T08:00:00+00:00", self.decision("old"))
        self.assertEqual(self.carry("preview"), [])


class SyncScripts(Case):

    def sync_vault(self, name, count):
        vault = self.vault(name, ["| notes | sync-script | `resources/scripts/sync.py` | Meetings. |"])
        write(vault, "resources/scripts/sync.py", SYNC)
        write(vault, "resources/scripts/count.txt", str(count))
        return vault

    def test_a_small_dry_run_is_written_in_write_mode(self):
        vault = self.sync_vault("alpha", 3)
        got = self.prepare()
        self.assertEqual(got["sync_runs"], [{"vault": "alpha", "script": "resources/scripts/sync.py",
                                             "would_write": 3, "written": 3, "error": None}])
        self.assertEqual((vault / "resources/scripts/written.txt").read_text(), "3")

    def test_a_dry_run_over_the_gate_is_reported_and_never_written(self):
        vault = self.sync_vault("alpha", 21)
        run = self.prepare()["sync_runs"][0]
        self.assertEqual((run["would_write"], run["written"]), (21, 0))
        self.assertIn("over the 20-item gate", run["error"])
        self.assertFalse((vault / "resources/scripts/written.txt").exists())

    def test_preview_runs_every_script_dry_only(self):
        vault = self.sync_vault("alpha", 2)
        run = self.prepare("preview")["sync_runs"][0]
        self.assertEqual((run["would_write"], run["written"], run["error"]), (2, 0, None))
        self.assertFalse((vault / "resources/scripts/written.txt").exists())

    def test_a_dry_run_with_no_count_is_an_error_and_never_written(self):
        vault = self.sync_vault("alpha", 1)
        write(vault, "resources/scripts/sync.py", "print('done')\n")
        run = self.prepare()["sync_runs"][0]
        self.assertEqual(run["written"], 0)
        self.assertIn("would write", run["error"])

    def test_a_missing_script_is_an_error_and_the_run_goes_on(self):
        self.vault("alpha", ["| notes | sync-script | `resources/scripts/gone.py` | Meetings. |",
                             connector_row(WORK)])
        got = self.prepare()
        self.assertIn("not found", got["sync_runs"][0]["error"])
        self.assertEqual([c["mailbox"] for c in got["connectors"]], [WORK])


class FetchScripts(Case):

    def fetch_vault(self, name):
        row = (f"| mail | fetch-script | `{OUTLOOK}` via `resources/scripts/outlook.py fetch` "
               "| Orders. |")
        vault = self.vault(name, [row])
        write(vault, "resources/scripts/outlook.py", FETCH)
        return vault

    def test_a_mailbox_two_vaults_declare_is_fetched_once(self):
        first, second = self.fetch_vault("alpha"), self.fetch_vault("beta")
        got = self.prepare()
        self.assertEqual(len(got["fetch_scripts"]), 1)
        run = got["fetch_scripts"][0]
        self.assertEqual((run["mailbox"], run["vault"], run["threads"], run["error"]),
                         (OUTLOOK, "alpha", 1, None))
        self.assertEqual((first / "resources/scripts/calls.txt").read_text().split(),
                         ["fetch", "--account", OUTLOOK, "--days", "2"])
        self.assertFalse((second / "resources/scripts/calls.txt").exists())
        self.assertEqual(got["totals"]["mailboxes"], 1)

    def test_a_bare_script_name_resolves_under_resources_scripts(self):
        vault = self.vault("alpha", [f"| mail | fetch-script | `{OUTLOOK}` via outlook.py | Orders. |"])
        write(vault, "resources/scripts/outlook.py", FETCH)
        self.assertIsNone(self.prepare()["fetch_scripts"][0]["error"])

    def test_a_failing_fetch_script_is_an_error_and_the_run_goes_on(self):
        vault = self.fetch_vault("alpha")
        write(vault, "resources/scripts/outlook.py", "import sys\nsys.exit('token expired')\n")
        got = self.prepare()
        self.assertIn("token expired", got["fetch_scripts"][0]["error"])
        self.assertTrue(any(OUTLOOK in e for e in got["errors"]))


class Routing(Case):

    def setUp(self):
        super().setUp()
        self.alpha = self.vault("alpha", [connector_row(WORK, "Client threads.")])
        self.beta = self.vault("beta", [connector_row(WORK, "Supplier invoices.")])

    def test_no_contact_hit_leaves_the_thread_to_judge_among_its_candidates(self):
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual(got["counts"], {"fetched": 1, "already_seen": 0, "signin": 0,
                                         "excluded": 0, "decided": 0, "to_judge": 1})
        item = got["to_judge"][0]
        self.assertEqual((item["thread_id"], item["candidates"]), ("t1", ["alpha", "beta"]))
        self.assertEqual(item["snippet"], "Figures attached.")
        self.assertEqual(got["vaults"]["beta"]["relevant_when"], {WORK: "Supplier invoices."})
        self.assertIsNone(self.run_file(got)["threads"][0]["routed"])

    def test_a_contact_in_one_vault_decides(self):
        write(self.alpha, "areas/network/anna.md", "# Anna\n\nanna@client.example\n")
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual(got["to_judge"], [])
        thread = self.run_file(got)["threads"][0]
        self.assertEqual((thread["routed"], thread["reason"]),
                         (["alpha"], "contact: anna@client.example"))

    def test_the_mailbox_owner_is_no_counterparty(self):
        write(self.alpha, "areas/network/me.md", f"# Me\n\n{WORK}\n")
        got = self.route(self.prepare(), [gmail_thread(sender=f"Me <{WORK}>")])
        self.assertEqual(len(got["to_judge"]), 1)

    def test_a_roster_writer_is_no_counterparty_for_their_vault(self):
        claude = ("# alpha\n\n## Who writes this vault\n\n| Person | Role |\n|---|---|\n"
                  "| [Sam](areas/network/sam.md) | member |\n")
        write(self.alpha, "CLAUDE.md", claude + SOURCES.format(rows=connector_row(WORK)))
        write(self.alpha, "areas/network/sam.md", "# Sam\n\nsam@team.example\n")
        got = self.route(self.prepare(), [gmail_thread(sender="Sam <sam@team.example>")])
        self.assertEqual(len(got["to_judge"]), 1)

    def test_a_hit_in_triage_or_sources_does_not_count(self):
        write(self.alpha, "triage/note.md", "anna@client.example\n")
        write(self.alpha, "areas/network/sources/mail.md", "anna@client.example\n")
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual(len(got["to_judge"]), 1)

    def test_a_lifecycle_home_is_searched(self):
        claude = ("# alpha\n\n## Deal lifecycle\n\n| Stage | PARA home |\n|---|---|\n"
                  "| Lead | areas/sales/leads.md (row) |\n| Won | projects/ |\n")
        write(self.alpha, "CLAUDE.md", claude + SOURCES.format(rows=connector_row(WORK)))
        write(self.alpha, "areas/sales/leads.md", "| Name | Mail |\n|---|---|\n"
                                                  "| Anna | anna@client.example |\n")
        thread = self.run_file(self.route(self.prepare(), [gmail_thread()]))["threads"][0]
        self.assertEqual(thread["routed"], ["alpha"])

    def test_hits_in_two_vaults_narrow_without_deciding(self):
        self.vault("gamma", [connector_row(WORK, "Everything else.")])
        write(self.alpha, "areas/network/anna.md", "anna@client.example\n")
        write(self.beta, "areas/network/anna.md", "anna@client.example\n")
        got = self.route(self.prepare(), [gmail_thread()])
        item = got["to_judge"][0]
        self.assertEqual(item["candidates"], ["alpha", "beta"])
        self.assertEqual(item["contacts"], {"anna@client.example": ["alpha", "beta"]})

    def test_a_participant_known_to_one_vault_settles_a_shared_contact(self):
        write(self.alpha, "areas/network/anna.md", "anna@client.example\n")
        write(self.beta, "areas/network/anna.md", "anna@client.example\n")
        write(self.beta, "areas/network/bob.md", "bob@client.example\n")
        thread = gmail_thread()
        thread["messages"].append({"message_id": "<t1b@client.example>",
                                   "from": "Bob <bob@client.example>",
                                   "received": "2026-10-24T10:00:00+00:00",
                                   "subject": "Re: Quarterly report", "preview": "Agreed."})
        routed = self.run_file(self.route(self.prepare(), [thread]))["threads"][0]
        self.assertEqual((routed["routed"], routed["reason"]),
                         (["beta"], "contact: bob@client.example"))

    def test_a_thread_the_ledger_covers_through_its_newest_message_is_dropped(self):
        self.ledger({WORK: {"t1": {"routed": ["alpha"], "reason": "x", "date": "2026-10-24",
                                   "seen_through": "<t1@client.example>",
                                   "seen_date": "2026-10-24T09:00:00+00:00"}}})
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual((got["counts"]["already_seen"], got["to_judge"]), (1, []))
        self.assertEqual(self.run_file(got)["threads"], [])

    def test_a_thread_grown_past_its_watermark_is_routed_again(self):
        self.ledger({WORK: {"t1": {"routed": [], "reason": "x", "date": "2026-10-23",
                                   "seen_through": "<t0@client.example>",
                                   "seen_date": "2026-10-23T09:00:00+00:00"}}})
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual(got["to_judge"][0]["resurfaced"], True)

    def test_a_vault_whose_triage_already_saw_the_thread_is_no_candidate(self):
        write(self.home, "cache/triage-email/alpha.json", json.dumps(
            {"t1": {"disposition": "noted", "date": "2026-10-24",
                    "seen_through": "<t1@client.example>",
                    "seen_date": "2026-10-24T09:00:00+00:00"}}))
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual(got["to_judge"][0]["candidates"], ["beta"])

    def test_a_thread_every_candidate_already_saw_is_dropped(self):
        for vault in ("alpha", "beta"):
            write(self.home, f"cache/triage-email/{vault}.json", json.dumps(
                {"t1": {"seen_through": "<t1@client.example>",
                        "seen_date": "2026-10-24T09:00:00+00:00"}}))
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual((got["counts"]["already_seen"], got["to_judge"]), (1, []))

    def test_a_domain_a_board_holds_is_evidence_not_a_decision(self):
        claude = ("# alpha\n\n## Deal lifecycle\n\n| Stage | PARA home |\n|---|---|\n"
                  "| Lead | areas/sales/leads.md (row) |\n")
        write(self.alpha, "CLAUDE.md", claude + SOURCES.format(rows=connector_row(WORK)))
        write(self.alpha, "areas/sales/leads.md", "| Lead | Mail |\n|---|---|\n"
                                                  "| Bea | bea@client.example |\n")
        item = self.route(self.prepare(), [gmail_thread()])["to_judge"][0]
        self.assertEqual((item["candidates"], item["boards"]),
                         (["alpha", "beta"], {"client.example": ["alpha"]}))

    def test_a_message_no_dedup_key_fits_is_refused(self):
        thread = gmail_thread()
        thread["messages"][0].update(message_id="", **{"from": ""})
        with self.assertRaises(ValueError) as caught:
            self.route(self.prepare(), [thread])
        self.assertIn("no message_id", str(caught.exception))

    def test_route_refuses_no_registry(self):
        prepared = self.prepare()
        (self.home / "vaults.json").unlink()
        with self.assertRaises(ValueError) as caught:
            self.route(prepared, [gmail_thread()])
        self.assertIn("no registry", str(caught.exception))

    def test_a_work_folder_older_than_a_week_is_removed(self):
        import os
        old = self.home / "cache" / "ingest" / "work" / "20261001-060000"
        old.mkdir(parents=True)
        os.utime(old, (0, 0))
        self.prepare()
        self.assertFalse(old.exists())

    def test_an_excluded_thread_is_decided_and_never_shown(self):
        write(self.home, "triage-exclusions.json", json.dumps(
            {"*": [{"domain": "client.example", "reason": "noise"}]}))
        got = self.route(self.prepare(), [gmail_thread()])
        self.assertEqual((got["counts"]["excluded"], got["to_judge"]), (1, []))
        self.assertEqual(self.run_file(got)["threads"][0]["routed"], [])

    def test_fetch_script_candidates_are_read_from_the_work_folder(self):
        self.vault("orders", [f"| mail | fetch-script | `{OUTLOOK}` via "
                              "`resources/scripts/outlook.py fetch` | Orders. |"])
        write(self.root / "orders", "resources/scripts/outlook.py", FETCH)
        got = self.route(self.prepare())
        item = got["to_judge"][0]
        self.assertEqual((item["mailbox"], item["thread_id"], item["candidates"]),
                         (OUTLOOK, "conv-1", ["orders"]))
        thread = self.run_file(got)["threads"][0]
        self.assertEqual((thread["source"], thread["text"], thread["own_messages"]),
                         ("outlook.py", "preview", False))

    def test_the_run_file_carries_the_plan_for_stage(self):
        got = self.route(self.prepare(), [gmail_thread()])
        run = self.run_file(got)
        self.assertEqual((run["mode"], run["started_at"]), ("write", NOW))
        self.assertEqual(run["source_plan"]["declaring_vaults"], {WORK: ["alpha", "beta"]})
        self.assertEqual(run["threads"][0]["candidates"], ["alpha", "beta"])

    def test_the_run_file_carries_the_invocation_and_the_mailbox_counts(self):
        run = self.run_file(self.route(self.prepare(), [gmail_thread()]))
        self.assertEqual((run["invocation"], run["window_days"]), ("/para-ingest write", 2))
        plan = run["source_plan"]
        self.assertEqual((plan["mailboxes"], plan["mailboxes_read"], plan["mailboxes_errored"]),
                         (1, 1, 0))
        run = self.run_file(self.route(self.prepare("preview", days=5)))
        self.assertEqual((run["invocation"], run["window_days"]),
                         ("/para-ingest preview --days 5", 5))

    def test_an_unread_connector_is_an_error_and_counted(self):
        run = self.run_file(self.route(self.prepare(), [], unread=[WORK.upper()]))
        plan = run["source_plan"]
        self.assertEqual((plan["mailboxes_read"], plan["mailboxes_errored"]), (0, 1))
        self.assertIn(f"{WORK}: connector could not be read", run["errors"])

    def test_an_unread_mailbox_the_plan_holds_no_connector_for_is_refused(self):
        with self.assertRaisesRegex(ValueError, "--unread"):
            self.route(self.prepare(), [], unread=["nobody@example.org"])

    def test_a_sign_in_code_passes_as_its_keys_alone(self):
        code = {"mailbox": WORK, "thread_id": "c1", "signin": True,
                "messages": [{"message_id": "<c1@shop.example>",
                              "received": "2026-10-24T09:30:00+00:00"}]}
        got = self.route(self.prepare(), [code, gmail_thread()])
        self.assertEqual([t["thread_id"] for t in got["to_judge"]], ["t1"])
        self.assertEqual(self.run_file(got)["threads"][-1]["signin"], True)

    def test_a_connector_thread_missing_a_field_is_refused(self):
        thread = gmail_thread()
        del thread["link"]
        with self.assertRaises(ValueError) as caught:
            self.route(self.prepare(), [thread])
        self.assertIn("link", str(caught.exception))

    def test_a_connector_thread_for_an_undeclared_mailbox_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            self.route(self.prepare(), [gmail_thread(mailbox="stranger@example.org")])
        self.assertIn("stranger@example.org", str(caught.exception))


class Refusals(Case):

    def assert_refused(self, call, words):
        with self.assertRaises(ValueError) as caught:
            call()
        self.assertIn(words, str(caught.exception))

    def test_prepare_refuses_an_unknown_mode_or_no_registry(self):
        self.assert_refused(lambda: self.prepare("dry"), "mode")
        self.assert_refused(lambda: self.prepare(), "no registry")

    def test_prepare_refuses_a_ledger_that_does_not_parse(self):
        self.vault("alpha", [connector_row(WORK)])
        write(self.home, "cache/ingest/ledger.json", "not json")
        self.assert_refused(lambda: self.prepare(), "ledger")

    def test_prepare_refuses_a_now_with_no_offset(self):
        self.vault("alpha", [connector_row(WORK)])
        self.assert_refused(lambda: prepare("write", paraos_home=self.home,
                                            now="2026-10-24T12:00:00"), "--now")

    def test_route_refuses_a_folder_with_no_plan(self):
        self.vault("alpha", [connector_row(WORK)])
        self.assert_refused(lambda: route(self.root, paraos_home=self.home), "no plan")

    def test_route_refuses_a_ledger_that_does_not_parse(self):
        self.vault("alpha", [connector_row(WORK)])
        prepared = self.prepare()
        write(self.home, "cache/ingest/ledger.json", "not json")
        self.assert_refused(lambda: self.route(prepared, [gmail_thread()]), "ledger")

    def test_route_refuses_a_connector_file_that_is_no_list_of_threads(self):
        self.vault("alpha", [connector_row(WORK)])
        prepared = self.prepare()
        self.assert_refused(lambda: self.route(prepared, {"threads": []}), "no JSON list")
        self.assert_refused(lambda: self.route(prepared, ["x"]), "not an object")

    def test_route_refuses_a_thread_with_no_messages_or_no_instant(self):
        self.vault("alpha", [connector_row(WORK)])
        prepared = self.prepare()
        empty = dict(gmail_thread(), messages=[])
        self.assert_refused(lambda: self.route(prepared, [empty]), "no messages")
        undated = gmail_thread()
        undated["messages"][0]["received"] = "yesterday"
        self.assert_refused(lambda: self.route(prepared, [undated]), "message 1: received")

    def test_an_unrecognised_row_is_an_error(self):
        self.vault("alpha", [connector_row(WORK), "| odd | carrier pigeon | loft | Birds. |"])
        self.assertTrue(any("odd" in e for e in self.prepare()["errors"]))

    def test_a_script_of_a_kind_it_cannot_run_is_an_error(self):
        vault = self.vault("alpha", ["| notes | sync-script | `resources/scripts/sync.sh` | x |",
                                     f"| mail | fetch-script | `{OUTLOOK}` via "
                                     "`resources/scripts/mail.sh fetch` | Orders. |"])
        write(vault, "resources/scripts/sync.sh", "echo")
        write(vault, "resources/scripts/mail.sh", "echo")
        got = self.prepare()
        self.assertIn("cannot run a .sh script", got["sync_runs"][0]["error"])
        self.assertIn("cannot run a .sh script", got["fetch_scripts"][0]["error"])

    def test_a_fetch_script_that_prints_no_json_or_is_missing_is_an_error(self):
        vault = self.vault("alpha", [f"| mail | fetch-script | `{OUTLOOK}` via "
                                     "`resources/scripts/outlook.py fetch` | Orders. |",
                                     f"| other | fetch-script | `{SHARED}` via "
                                     "`resources/scripts/gone.py fetch` | Other. |"])
        write(vault, "resources/scripts/outlook.py", "print('hello')\n")
        runs = {r["mailbox"]: r["error"] for r in self.prepare()["fetch_scripts"]}
        self.assertIn("no JSON list", runs[OUTLOOK])
        self.assertIn("no declaring vault holds its script", runs[SHARED])

    def test_a_javascript_sync_script_runs_under_node(self):
        vault = self.vault("alpha", ["| notes | sync-script | `resources/scripts/sync.js` | x |"])
        write(vault, "resources/scripts/sync.js",
              "console.log(process.argv.includes('--write') ? 'wrote: 1' : 'would write: 1');\n")
        self.assertEqual(self.prepare()["sync_runs"][0]["written"], 1)


class ThroughStage(Case):

    def test_a_routed_run_stages_its_notes_and_a_rerun_stages_nothing(self):
        from stage import stage
        alpha = self.vault("alpha", [connector_row(WORK, "Client threads.")])
        self.vault("beta", [connector_row(WORK, "Supplier invoices.")])
        write(alpha, "areas/network/anna.md", "anna@client.example\n")
        threads = [gmail_thread(),
                   gmail_thread("t2", "Shop <shop@supplier.example>", "Invoice 7")]
        routed = self.route(self.prepare(), threads)
        self.assertEqual([t["thread_id"] for t in routed["to_judge"]], ["t2"])
        decisions = [{"mailbox": WORK, "thread_id": "t2", "routed": ["beta"],
                      "reason": "rule: beta Relevant when"}]
        summary = stage(self.run_file(routed), self.home, decisions=decisions)
        self.assertEqual(summary["counts"]["per_vault"], {"alpha": 1, "beta": 1})
        again = self.route(prepare("write", paraos_home=self.home,
                                   now="2026-10-24T18:00:00+00:00"), threads)
        self.assertEqual(again["counts"]["already_seen"], 2)

    def test_a_staged_run_moves_the_cursor_of_every_mailbox_it_read(self):
        from stage import stage
        self.vault("alpha", [connector_row(WORK), connector_row(SHARED)])
        routed = self.route(self.prepare(), [], unread=[SHARED])
        stage(self.run_file(routed), self.home, decisions=[])
        later = prepare("write", paraos_home=self.home, now="2026-10-25T00:00:00+00:00")
        self.assertEqual({c["mailbox"]: c["since"] for c in later["connectors"]},
                         {WORK: "2026-10-23T12:00:00+00:00", SHARED: "2026-10-23T00:00:00+00:00"})

    def test_staging_from_a_work_folder_removes_the_fetched_text(self):
        import stage
        self.vault("orders", [f"| mail | fetch-script | `{OUTLOOK}` via "
                              "`resources/scripts/outlook.py fetch` | Orders. |"])
        write(self.root / "orders", "resources/scripts/outlook.py", FETCH)
        prepared = self.prepare()
        work = Path(prepared["work"])
        connectors = write(work, "connectors.json", "[]")
        routed = route(work, connectors=connectors, paraos_home=self.home)
        decisions = write(work, "decisions.json", json.dumps(
            [{"mailbox": OUTLOOK, "thread_id": "conv-1", "routed": [], "reason": "unrouted"}]))
        with contextlib.redirect_stdout(io.StringIO()):
            stage.main([routed["run"], "--decisions", str(decisions),
                        "--paraos-home", str(self.home)])
        self.assertEqual(sorted(p.name for p in work.iterdir()), ["decisions.json", "plan.json"])


class Cli(Case):

    def test_prepare_then_route_print_json(self):
        self.vault("alpha", [connector_row(WORK)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["prepare", "--mode", "write", "--now", NOW,
                                   "--paraos-home", str(self.home)]), 0)
        work = json.loads(out.getvalue())["work"]
        connectors = write(self.root, "c.json", json.dumps([gmail_thread()]))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["route", "--work", work, "--connectors", str(connectors),
                                   "--unread", WORK, "--paraos-home", str(self.home)]), 0)
        routed = json.loads(out.getvalue())
        self.assertEqual(routed["counts"]["to_judge"], 1)
        self.assertEqual(self.run_file(routed)["errors"], [f"{WORK}: connector could not be read"])

    def test_a_refused_input_exits_2(self):
        self.vault("alpha", [connector_row(WORK)])
        work = self.prepare()["work"]
        bad = write(self.root, "c.json", "[{}]")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["route", "--work", work, "--connectors", str(bad),
                  "--paraos-home", str(self.home)])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
