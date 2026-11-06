#!/usr/bin/env python3
"""Tests for command_center.py. Each pins a rule the script's docstring states: where every
part of the page's data comes from, what a missing input becomes, and that nothing on the page
needs a judgment.

    python3 test_command_center.py
    py -3 test_command_center.py

Standard library only. Every vault, registry and repo here is synthetic, built in a temporary
folder; no command is run but the ones the test fakes.
"""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "multi-vault" / "para-command-center" / "scripts"))

import command_center as cc  # noqa: E402
from test_global_scan import TODAY, build_vault, write  # noqa: E402

NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
SOURCES = ("\n## Triage sources\n\n| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n{rows}\n"
           "\n## Agenda sources\n\n| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n{agenda}\n")
REPOS = ("# Code repos\n\n| Repo | Role | What it is | Vault home | Site | Serves vault |\n|---|---|---|---|---|---|\n"
         "| `site-repo` | owned | The public site | | alpha.test | alpha |\n"
         "| `lib` | owned | A library | | | |\n"
         "| `ref` | reference | Kept to read | | | |\n")


def claude_md(rows, agenda=""):
    return "# Fixture Vault Conventions\n\n**Type:** vault\n" + SOURCES.format(rows=rows, agenda=agenda)


def fake_run(answers):
    """A runner that answers a command by the first key found among its arguments."""
    def run(args, cwd=None, timeout=30):
        return next((v for k, v in answers.items() if k in args), None)
    return run


class Pieces(unittest.TestCase):
    def test_a_dated_item_falls_in_one_band(self):
        day = TODAY  # a Tuesday
        self.assertEqual([cc.band(day + timedelta(days=d), day) for d in (-1, 0, 5, 6, 19, 20)],
                         ["late", "today", "week", "next2", "next2", "later"])

    def test_tasks_come_from_the_scan_and_each_summed_vaults_top_items(self):
        scan = {"tasks": [{"vault": "a", "text": "**Do it** now", "effective_date": "2026-03-08", "priority": "🔺",
                           "recurring": None, "file": "f.md", "line": 3},
                          {"vault": "a", "text": "No date", "effective_date": None}],
                "summaries": [{"top": [{"vault": "b", "text": "Top", "effective_date": "2026-03-12"}]}]}
        rows = cc.task_rows(scan, TODAY)
        self.assertEqual([(r["id"], r["vault"], r["band"], r["days_late"], r["priority"]) for r in rows],
                         [("t1", "a", "late", 2, "🔺"), ("t2", "b", "week", 0, "")])
        self.assertEqual(rows[0]["text"], "Do it")

    def test_an_event_matching_a_meeting_shows_once_and_a_broken_one_is_counted(self):
        scan = {"meetings": [{"date": "2026-03-10", "start": "09:00", "end": None, "title": "Stand  up", "vault": "a"}]}
        fetched = [{"date": "2026-03-10", "start": "09:00", "title": "stand up", "source": "cal"},
                   {"date": "2026-03-11", "title": "**Review**", "recurring": True},
                   {"date": "soon", "title": "x"}, {"date": "2026-03-11"}, "junk"]
        rows, dropped = cc.agenda_rows(scan, fetched, TODAY)
        self.assertEqual(dropped, 3)
        self.assertEqual([(r["id"], r["title"], r["source"], r["band"], r["recurring"]) for r in rows],
                         [("e1", "Stand  up", "a", "today", False), ("e2", "Review", "calendar", "week", True)])

    def test_the_kit_signal_is_worded_like_the_others(self):
        self.assertEqual([cc.kit_value(k) for k in (
            {"verdict": "ahead"}, {"verdict": "unverified"}, {"findings": None}, {"findings": 0},
            {"findings": 1}, {"findings": 3, "upgrade": 2})],
            ["not judged: ahead of the kit", "not judged: no marker", "not judged: no para-os clone",
             "current", "1 finding", "3 findings, 2 the upgrade applies"])

    def test_a_vault_stands_where_its_entry_says_else_by_who_keeps_it(self):
        scan = [{"name": "a", "treatment": "full"}, {"name": "b", "treatment": "health"},
                {"name": "c", "treatment": "summary"}]
        entries = [{"name": "a", "neighbourhood": " Mine ", "street": "Work"}, {"name": "b"}, {"name": "c"},
                   {"name": "unread"}, "junk"]
        where, order = cc.places(entries, scan)
        self.assertEqual(where, {"a": ("Mine", 0, "Work"), "b": (cc.KEPT, 1, ""), "c": (cc.OWN, 2, "")})
        self.assertEqual(order, ["Mine", cc.KEPT, cc.OWN])

    def test_a_vault_with_no_card_is_not_judged_and_a_past_vault_is_handed_over(self):
        scan = {"vaults": [{"name": "a", "role": None, "treatment": "full", "machine": None, "open": 4,
                            "overdue": 1, "triage": None}]}
        feed = {"held": {"a": 2}, "routed": {}, "acted": {}}
        past = [{"name": "old", "ended": "last spring", "neighbourhood": "Clients", "street": "Sold", "note": "Gone."},
                {"name": "older"}, {"name": "a"}, {"nope": 1}, "junk"]
        rows, health = cc.vault_rows(scan, [{"name": "a"}], feed, [{"vault": "a", "signal": "dirty"},
                                                                    {"vault": "a", "signal": "quiet"}], TODAY, past)
        self.assertEqual(health, [])
        self.assertEqual([(r["vault"], r["level"], r["held"], r["repos"], r["state"], r["neighbourhood"],
                           r["neighbourhood_rank"], r["street"]) for r in rows],
                         [("a", "unknown", 2, 2, "", cc.OWN, 0, ""),
                          ("old", "", 0, 0, "handed over, ended last spring", "Clients", 1, "Sold"),
                          ("older", "", 0, 0, "handed over", cc.KEPT, 2, "")])
        self.assertEqual([r["note"] for r in rows[1:]], ["Gone.", "Handed over: no longer read on this machine."])

    def test_a_cron_line_gives_its_times_and_its_words(self):
        self.assertEqual(cc.schedule("0 6,16 * * *"), (["06:00", "16:00"], "06:00 and 16:00 every day"))
        self.assertEqual(cc.schedule("30 7 * * 1"), (["07:30"], "07:30 Mondays"))
        self.assertEqual(cc.schedule("0 7 * * 2-6")[1], "07:00 Tuesday to Saturday")
        self.assertEqual(cc.schedule("0 7 * * 2,4")[1], "07:00 Tuesdays and Thursdays")
        self.assertEqual(cc.schedule("0 7 * * MON-FRI")[1], "07:00 Monday to Friday")
        self.assertEqual(cc.schedule("0 7 * * mon,thu")[1], "07:00 Mondays and Thursdays")
        self.assertEqual(cc.schedule("0 7 * * SUN")[1], "07:00 Sundays")
        self.assertEqual(cc.schedule("0 7 * * FRI-SUN")[1], "07:00 Friday to Sunday")
        self.assertEqual(cc.schedule("*/5 * * * *"), ([], "*/5 * every day"))
        self.assertEqual(cc.schedule("0 x-3 * * 99"), ([], "0 x-3 every day"))
        self.assertEqual(cc.schedule("hourly"), ([], "hourly"))
        self.assertEqual(cc.schedule(None), ([], ""))

    def test_the_last_due_time_looks_a_week_back(self):
        self.assertEqual(cc.last_due("0 6,16 * * *", NOW), NOW.replace(hour=6))
        self.assertEqual(cc.last_due("0 16 * * *", NOW), NOW.replace(hour=16) - timedelta(days=1))
        self.assertEqual(cc.last_due("30 7 * * 1", NOW), datetime(2026, 3, 9, 7, 30, tzinfo=timezone.utc))
        saturday = NOW + timedelta(days=4)
        self.assertEqual(cc.last_due("0 7 * * MON-FRI", saturday), datetime(2026, 3, 13, 7, 0, tzinfo=timezone.utc))
        self.assertEqual(cc.last_due("0 7 * * SAT-SUN", saturday), datetime(2026, 3, 14, 7, 0, tzinfo=timezone.utc))
        self.assertIsNone(cc.last_due("0 6 1 * *", NOW))
        self.assertIsNone(cc.last_due("* * * * *", NOW))
        self.assertIsNone(cc.last_due("daily", NOW))

    def test_a_run_stands_by_its_last_record(self):
        run = {"cron": "0 6 * * *"}
        self.assertEqual(cc.run_status(run, NOW), "none")
        self.assertEqual(cc.run_status(dict(run, last={"status": "failed"}), NOW), "bad")
        self.assertEqual(cc.run_status(dict(run, last={"status": "partial"}), NOW), "warn")
        self.assertEqual(cc.run_status(dict(run, last={"status": "ok", "end": "2026-03-09T06:05:00Z"}), NOW), "watch")
        self.assertEqual(cc.run_status(dict(run, last={"status": "ok", "end": "2026-03-10T06:05:00Z"}), NOW), "ok")
        self.assertEqual(cc.run_status({"cron": "later", "last": {"status": "ok", "end": "2026-01-01T00:00:00Z"}}, NOW), "ok")
        late = NOW.replace(hour=6, minute=30)
        self.assertEqual(cc.run_status(dict(run, last={"status": "ok", "end": "2026-03-09T06:05:00Z"}), late), "ok")

    def test_names_are_folded(self):
        self.assertEqual(cc.script_name("resources\\scripts\\rec.py"), "rec.py")
        self.assertEqual(cc.provider_name("Books (ledger), hosted"), "Books")
        self.assertEqual(cc.provider_name("Azure, one sign-in"), "Azure")
        self.assertEqual(cc.provider_name(None), "")


class Repos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_command_answers_or_is_none(self):
        self.assertEqual(cc.run_command([sys.executable, "-c", "print('hi')"]), "hi")
        self.assertIsNone(cc.run_command([sys.executable, "-c", "import sys; sys.exit(3)"]))
        self.assertIsNone(cc.run_command([str(self.tmp / "no-such-tool")]))
        with mock.patch.object(cc.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertIsNone(cc.run_command(["x"]))

    def test_the_host_is_read_from_the_remote(self):
        self.assertEqual([cc.host_of(r) for r in ("", "git@github.com:a/b.git", "https://dev.azure.com/o/p",
                                                  "https://o.visualstudio.com/p", "https://git.example/r")],
                         ["none", "GitHub", "Azure DevOps", "Azure DevOps", "other"])

    def test_a_repo_says_the_one_thing_to_know(self):
        base = {"ci_result": "", "ahead": 0, "behind": 0, "dirty": 0, "days_quiet": 3}
        cases = [({"ci_result": "failure"}, "ci"), ({"ahead": 2, "behind": 1}, "diverged"), ({"ahead": 1}, "unpushed"),
                 ({"ahead": 2}, "unpushed"), ({"dirty": 1}, "dirty"), ({"dirty": 2}, "dirty"), ({"behind": 4}, "behind"),
                 ({"days_quiet": 200}, "quiet"), ({"days_quiet": None}, "clean"), ({}, "clean")]
        self.assertEqual([cc.signal_of(dict(base, **c))[0] for c, _ in cases], [want for _, want in cases])
        self.assertEqual(cc.signal_of(dict(base, ahead=2))[1], "2 unpushed commits")

    def test_a_repo_not_checked_out_is_missing(self):
        self.assertEqual(cc.repo_state("lib", None, TODAY)["signal"], "missing")

    def test_a_github_repo_carries_its_last_run(self):
        run = fake_run({"get-url": "git@github.com:me/site.git", "fetch": "", "--abbrev-ref": "main",
                        "--porcelain": " M a\n?? b", "--left-right": "1\t2", "log": "2026-03-01",
                        "run": json.dumps([{"workflowName": "check", "conclusion": "success"}])})
        row = cc.repo_state("site", self.tmp, TODAY, run)
        self.assertEqual({k: row[k] for k in ("host", "branch", "dirty", "behind", "ahead", "last_commit",
                                              "days_quiet", "ci", "ci_result", "signal")},
                         {"host": "GitHub", "branch": "main", "dirty": 2, "behind": 1, "ahead": 2,
                          "last_commit": "2026-03-01", "days_quiet": 9, "ci": "check",
                          "ci_result": "success", "signal": "diverged"})

    def test_what_a_command_does_not_answer_stays_empty(self):
        run = fake_run({"get-url": "git@github.com:me/site.git", "run": "not json"})
        row = cc.repo_state("site", self.tmp, TODAY, run)
        self.assertEqual((row["ci"], row["last_commit"], row["signal"]), ("", "", "clean"))
        running = fake_run({"get-url": "git@github.com:me/site.git", "--left-right": "x y z",
                            "run": json.dumps([{"status": "in_progress"}])})
        self.assertEqual(cc.repo_state("site", self.tmp, TODAY, running)["ci_result"], "in_progress")
        self.assertEqual(cc.repo_state("site", self.tmp, TODAY, fake_run({"get-url": "git@github.com:me/site.git", "run": "[]"}))["ci"], "")

    def test_offline_asks_the_remote_nothing(self):
        asked = []

        def run(args, cwd=None, timeout=30):
            asked.append(args)
            return "https://git.example/r" if "get-url" in args else None
        offline = cc.repo_state("site", self.tmp, TODAY, fake_run({"get-url": "git@github.com:me/site.git"}), online=False)
        self.assertEqual(offline["ci"], "")
        self.assertEqual(cc.repo_state("site", self.tmp, TODAY, run)["host"], "other")
        self.assertFalse(any(a[0] == "gh" for a in asked))
        self.assertEqual(cc.repo_state("site", self.tmp, TODAY, fake_run({}))["host"], "none")

    def test_a_repo_is_found_under_the_first_root_holding_it(self):
        (self.tmp / "two" / "site" / ".git").mkdir(parents=True)
        self.assertEqual(cc.checkout("site", [self.tmp / "one", self.tmp / "two"]), self.tmp / "two" / "site")
        self.assertIsNone(cc.checkout("lib", [self.tmp / "one"]))

    def test_only_a_vault_this_machine_reads_is_here(self):
        self.assertEqual([cc.here(e) for e in ("junk", {"name": "x", "path": str(self.tmp), "machine": "Sam"}, {"name": "x"},
                                               {"name": "x", "path": str(self.tmp / "gone")}, {"path": str(self.tmp)})], [None] * 5)
        self.assertEqual(cc.here({"name": "x", "path": str(self.tmp)}), self.tmp)


class Inbound(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_thread_is_one_row_per_place_it_went(self):
        write(self.tmp, "cache/ingest/ledger.json", json.dumps({"mailboxes": {
            "A@x.test": {"1": {"date": "2026-03-09", "routed": ["alpha", "beta"]},
                         "2": {"date": "2026-03-09", "reason": "Excluded: a rule"},
                         "3": {"date": "2026-03-09", "reason": "unrouted: excluded by triage-exclusions (x)"},
                         "4": {"date": "2026-03-09", "reason": "skipped: old"},
                         "5": {"date": "2026-03-09", "routed": ["alpha"], "reason": "suppressed"},
                         "6": {"date": "2026-03-09"}, "7": {"date": "2026-01-01", "routed": ["alpha"]},
                         "8": {"routed": ["alpha"]}, "9": "junk"},
            "odd": "junk"}}))
        rows = cc.flow_rows(self.tmp, "2026-03-03", {"a@x.test": "Me · Mail"})
        self.assertEqual([(r["label"], r["dest"], r["kind"], r["count"]) for r in rows],
                         [("Me · Mail", "", "excluded", 2), ("Me · Mail", "", "unrouted", 1),
                          ("Me · Mail", "alpha", "vault", 1), ("Me · Mail", "beta", "vault", 1)])
        self.assertEqual(rows[0]["id"], "A@x.test>excluded:")

    def test_no_ledger_is_no_flow(self):
        self.assertEqual(cc.flow_rows(self.tmp, "2026-03-03", {}), [])
        write(self.tmp, "cache/ingest/ledger.json", "[]")
        self.assertEqual(cc.flow_rows(self.tmp, "2026-03-03", {}), [])

    def test_a_sync_scripts_notes_are_counted_from_its_own_ledger(self):
        vault = self.tmp / "alpha"
        write(vault, "CLAUDE.md", claude_md("| notes | sync-script | `resources/scripts/rec.py` | all |\n"
                                             "| loose | sync-script | somewhere | all |\n"
                                             "| mail | connector: mailer | a@x.test | all |"))
        write(vault, "resources/scripts/rec.synced.json", json.dumps({
            "1": str(vault / "triage" / "20260309 A call.md"), "2": "triage/20260301 An old call.md",
            "3": "triage/undated.md", "4": 5}))
        bare = self.tmp / "beta"
        write(bare, "CLAUDE.md", claude_md("| notes | sync-script | `resources/scripts/rec.py` | all |"))
        write(bare, "resources/scripts/rec.synced.json", "[]")
        entries = [{"name": "alpha", "path": str(vault)}, {"name": "beta", "path": str(bare)},
                   {"name": "far", "path": str(vault), "machine": "Sam"}]
        self.assertEqual(dict(cc.synced_counts(entries, "2026-03-03")), {("rec.py", "alpha"): 1})

    def test_events_come_from_a_list_or_an_object(self):
        good = write(self.tmp, "events.json", json.dumps({"events": [{"date": "2026-03-10", "title": "x"}], "note": "**One** failed"}))
        self.assertEqual(cc.read_events(good), ([{"date": "2026-03-10", "title": "x"}], "One failed"))
        self.assertEqual(cc.read_events(write(self.tmp, "list.json", "[]")), ([], ""))
        events, note = cc.read_events(write(self.tmp, "bad.json", "{}"))
        self.assertIsNone(events)
        self.assertIn("could not be read", note)

    def test_the_last_calendar_read_is_kept_and_used_again(self):
        home = self.tmp / "home"
        self.assertEqual(cc.calendar_events(None, NOW, home), (None, ""))
        given = write(self.tmp, "events.json", json.dumps({"events": [{"date": "2026-03-10", "title": "x"}]}))
        self.assertEqual(cc.calendar_events(str(given), NOW, home), ([{"date": "2026-03-10", "title": "x"}], ""))
        self.assertEqual(cc.calendar_events(None, NOW + timedelta(hours=4), home)[1], "")
        events, note = cc.calendar_events(None, NOW + timedelta(days=1), home)
        self.assertEqual((len(events), note), (1, "The calendars were last read on 2026-03-10."))
        write(home, "cache/command-center/events.json", json.dumps({"events": [], "note": "One failed.", "read_at": "2026-03-08T07:00:00+00:00"}))
        self.assertEqual(cc.calendar_events(None, NOW, home)[1], "One failed. The calendars were last read on 2026-03-08.")
        self.assertIsNone(cc.calendar_events(str(write(self.tmp, "bad.json", "{}")), NOW, home)[0])
        self.assertEqual(cc.calendar_events(None, NOW, home)[1], "One failed. The calendars were last read on 2026-03-08.")
        write(home, "cache/command-center/events.json", "{}")
        self.assertIsNone(cc.calendar_events(None, NOW, home)[0])


class WholePage(unittest.TestCase):
    """One machine: two vaults read here, one another machine pulls, one unreachable, one past."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "paraos"
        alpha, beta, gamma = (self.tmp / n for n in ("alpha", "beta", "gamma"))
        build_vault(alpha, "- [ ] Renew the domain 📅 2026-03-08\n- [ ] Send the launch note 🔺 📅 2026-03-10\n")
        write(alpha, "CLAUDE.md", claude_md(
            "| mail | connector: mailer | a@x.test | all |\n"
            "| notes | sync-script | `resources/scripts/rec.py` | all |\n"
            "| loose | sync-script | nowhere | all |",
            "| work | connector: cal | me@x.test | all |\n| odd | calendar | other | all |"))
        write(alpha, ".claude/rules/code-repos.md", REPOS)
        write(alpha, "resources/scripts/rec.synced.json", json.dumps({"1": "triage/20260309 A call.md"}))
        write(alpha, "meetings.md", "- 🗓 2026-03-11 10:00-11:00 · Board\n")
        write(alpha, ".mcp.json", json.dumps({"mcpServers": {"tracker": {"url": "https://tracker.test"}}}))
        write(alpha, "triage/note.md", "A loose note.\n")
        build_vault(beta, "- [ ] Pay the host invoice 🔼 📅 2026-03-12\n")
        write(beta, "CLAUDE.md", claude_md(
            "| mail | connector: mailer | a@x.test | all |\n"
            "| inbox | fetch-script | `resources/scripts/fetch.py` b@x.test | all |\n"
            "| voice | connector: voice recording | voice | all |"))
        build_vault(gamma, "")
        write(gamma, "CLAUDE.md", claude_md(
            "| mail | connector: mailer | c@x.test | all |\n| notes | sync-script | `resources/scripts/rec.py` | all |"))
        self.entries = [
            {"name": "alpha", "path": str(alpha), "active": True, "neighbourhood": "Mine", "street": "Work"},
            {"name": "beta", "path": str(beta), "active": True},
            {"name": "gamma", "path": str(gamma), "active": False, "machine": "Sam"},
            {"name": "delta", "path": str(self.tmp / "delta"), "active": True},
            {"path": str(alpha)},
        ]
        write(self.home, "vaults.json", json.dumps(self.entries))
        write(self.home, "operator.json", json.dumps({"card": "me"}))
        write(self.home, "past-vaults.json", json.dumps([{"name": "omega", "ended": "last spring", "neighbourhood": "Clients"}]))
        common = {"machine": None, "secret": None, "writes": None, "read_only": True}
        write(self.home, "connections.json", json.dumps({
            "connections": [
                dict(common, id="mailer", kind="connector", provider="Mail (hosted)", vaults=["alpha", "beta"]),
                dict(common, id="rec", kind="script", provider="Recorder", vaults=["alpha"], path="resources/scripts/rec.py",
                     read_only=False, writes="notes into triage/"),
                dict(common, id="books", kind="cli", provider="Books, hosted", vaults=["alpha", "nowhere"]),
                dict(common, id="far", kind="script", provider="Far", vaults=["gamma"], machine="Sam", path="x.py")],
            "mailboxes": [{"address": "a@x.test", "owner": "Me", "label": "Me · Mail"}]}))
        write(self.home, "tasks.json", json.dumps([
            {"id": "ingest", "title": "Ingest", "cron": "0 6,16 * * *", "skill": "para-ingest", "vaults": "*", "sources": []},
            {"id": "center", "title": "Command Center", "cron": "0 7 * * *", "skill": "para-command-center", "vaults": "*", "sources": []},
            {"id": "watch", "title": "", "cron": "30 6 * * 1-5", "skill": None, "vaults": ["alpha", "nowhere"],
             "sources": [{"name": "Shop", "via": ["browser"]}, {"via": []}, "junk"]}]))
        write(self.home, "cache/runs/ingest.jsonl", json.dumps({"task": "ingest", "start": None, "end": "2026-03-10T06:08:00+00:00",
                                                                 "status": "ok", "summary": "Staged 3."}) + "\n")
        write(self.home, "cache/runs/center.jsonl", json.dumps({"task": "center", "start": None, "end": "2026-03-10T07:02:00+00:00",
                                                                 "status": "failed", "summary": "No registry."}) + "\n")
        write(self.home, "cache/ingest/ledger.json", json.dumps({"mailboxes": {
            "a@x.test": {"1": {"date": "2026-03-09", "routed": ["alpha"]}, "2": {"date": "2026-03-09", "routed": ["alpha", "beta"]},
                         "3": {"date": "2026-03-09", "reason": "excluded: a rule"}, "4": {"date": "2026-03-09"}},
            "b@x.test": {"1": {"date": "2026-03-09", "routed": ["ghost"]}}}}))
        table = "# Proposal\n\n| Item | Recommended | Why | Held |\n|---|---|---|---|\n"
        write(self.home, "cache/triage/proposals/alpha-20260309-0600.md", table + "| note.md | File | fits | money |\n| gone.md | File | fits | deadline |\n")
        write(self.home, "cache/triage/proposals/alpha-20260309-1600.md", table + "| note.md | File | fits | money |\n")
        write(self.home, "cache/triage/proposals/gamma-20260309-0600.md", table + "| far.md | File | fits | money |\n| far.md | File | fits | money |\n")
        write(self.home, "quarantine/alpha/20260309-060000/manifest.json",
              json.dumps({"vault": "alpha", "run": "20260309-060000", "items": [{"item": "x.md", "action": "Dismiss"}]}))
        write(self.home, "quarantine/alpha/20260101-060000/manifest.json",
              json.dumps({"vault": "alpha", "run": "20260101-060000", "items": [{"item": "y.md", "action": "Dismiss"}]}))
        write(self.home, "cache/pages.json", json.dumps([
            {"key": cc.vault_key(alpha), "page": "daily-brief", "url": "https://pages.test/1", "title": "Alpha Dashboard", "producer": "para-daily-brief"},
            {"key": cc.vault_key(self.home), "page": "command-center", "url": None, "title": None, "producer": "para-command-center"},
            {"key": "elsewhere", "page": "board", "url": None, "title": "Board", "producer": None},
            {"key": cc.vault_key(self.home), "page": "funnel", "url": None, "title": "Funnel", "producer": None, "replaced_by": "command-center"}]))
        self.code = self.tmp / "code"
        (self.code / "site-repo" / ".git").mkdir(parents=True)
        self.run = fake_run({"get-url": "https://git.example/site", "--porcelain": " M a"})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, **more):
        args = dict(events=[{"date": "2026-03-11", "start": "10:00", "title": "board", "source": "work"},
                            {"date": "2026-03-12", "start": "09:00", "title": "Demo", "source": "work"}, {"title": "no date"}],
                    note="One calendar failed.", roots=[self.code], run=self.run)
        args.update(more)
        return cc.build(self.entries, TODAY, NOW, str(self.home), **args)

    def test_every_part_is_built_from_the_files(self):
        data = self.build()
        self.assertEqual(sorted(data), ["agenda", "edges", "flows", "funnel", "health", "meta", "nodes", "repos",
                                        "sites", "tasks", "vaults"])
        self.assertEqual(data["meta"]["hub"], "run:ingest")
        self.assertEqual(data["meta"]["today"], "2026-03-10")
        self.assertEqual([(t["vault"], t["band"]) for t in data["tasks"]], [("alpha", "late"), ("alpha", "today"), ("beta", "week")])
        self.assertEqual([(e["title"], e["source"]) for e in data["agenda"]], [("Board", "alpha"), ("Demo", "work")])
        self.assertEqual([s["stage"] for s in data["funnel"]], ["fetch", "exclude", "route", "stage", "classify", "execute", "operator"])
        self.assertEqual({s["stage"]: s["value"] for s in data["funnel"]}["operator"], 2)
        self.assertEqual(self.build()["meta"]["hub"], "run:ingest")
        self.assertEqual([(f["address"], f["dest"], f["kind"], f["count"]) for f in data["flows"]],
                         [("a@x.test", "", "excluded", 1), ("a@x.test", "", "unrouted", 1), ("a@x.test", "alpha", "vault", 2),
                          ("a@x.test", "beta", "vault", 1), ("b@x.test", "ghost", "vault", 1)])

    def test_each_vault_carries_its_place_its_counts_and_its_card(self):
        data = self.build()
        rows = {v["vault"]: v for v in data["vaults"]}
        self.assertEqual(list(rows), ["alpha", "beta", "gamma", "omega"])
        self.assertEqual({k: rows["alpha"][k] for k in ("neighbourhood", "neighbourhood_rank", "street", "held", "acted", "routed",
                                                        "triage_items", "repos", "machine", "state")},
                         {"neighbourhood": "Mine", "neighbourhood_rank": 0, "street": "Work", "held": 1, "acted": 1, "routed": 2,
                          "triage_items": 1, "repos": 2, "machine": "", "state": ""})
        self.assertEqual((rows["beta"]["neighbourhood"], rows["gamma"]["machine"], rows["omega"]["state"]),
                         (cc.OWN, "Sam", "handed over, ended last spring"))
        self.assertEqual((rows["beta"]["held"], rows["gamma"]["held"]), (0, 1))
        self.assertIn(rows["alpha"]["level"], ("ok", "watch", "care"))
        keys = [h["key"] for h in data["health"] if h["vault"] == "alpha"]
        self.assertEqual(keys[keys.index("template") + 1], "kit")

    def test_the_deep_clean_audit_is_named_on_its_row(self):
        write(self.home, "data/deep-clean/alpha.audit.json", json.dumps({"date": "2026-03-10", "total": 1}))
        value = {h["id"]: h["value"] for h in self.build()["health"]}["alpha:deep_clean"]
        self.assertIn("audit today: 1 finding", value)
        write(self.home, "data/deep-clean/alpha.audit.json", json.dumps({"date": "2026-03-07", "total": 4}))
        self.assertIn("audit 3d ago: 4 findings", {h["id"]: h["value"] for h in self.build()["health"]}["alpha:deep_clean"])

    def test_repos_and_sites_come_from_the_owned_rows(self):
        data = self.build()
        self.assertEqual([(r["repo"], r["vault"], r["signal"]) for r in data["repos"]],
                         [("site-repo", "alpha", "dirty"), ("lib", "alpha", "missing")])
        self.assertEqual(data["sites"], [{"site": "alpha.test", "repo": "site-repo", "vault": "alpha", "serves": "alpha",
                                          "what": "The public site"}])

    def test_every_declared_link_is_drawn_and_no_other(self):
        data = self.build()
        nodes = {n["id"]: n for n in data["nodes"]}
        edges = {e["id"]: e for e in data["edges"]}
        for nid in ("vault:alpha", "vault:omega", "run:ingest", "run:watch", "src:Shop", "box:a@x.test", "box:b@x.test",
                    "box:c@x.test", "conn:mailer", "conn:fetch.py", "conn:rec", "conn:voice", "src:Recorder", "src:voice",
                    "machine:Sam", "cal:me@x.test", "conn:cal", "conn:books", "src:Books", "conn:tracker", "src:tracker",
                    "repos:alpha", "site:alpha.test", "page:elsewhere:board"):
            self.assertIn(nid, nodes)
        self.assertNotIn("conn:far", nodes)
        self.assertFalse([n for n in nodes if n.endswith(":funnel")])
        self.assertEqual({k: nodes["run:ingest"][k] for k in ("status", "sub", "label")},
                         {"status": "ok", "sub": "06:00 and 16:00 every day", "label": "Ingest"})
        self.assertEqual((nodes["run:center"]["status"], nodes["run:watch"]["status"], nodes["run:watch"]["label"]),
                         ("bad", "none", "watch"))
        self.assertEqual((nodes["box:a@x.test"]["label"], nodes["box:a@x.test"]["sub"], nodes["box:b@x.test"]["label"]),
                         ("Me · Mail", "5 threads in 7 days", "b@x.test"))
        self.assertEqual((nodes["conn:mailer"]["sub"], nodes["conn:fetch.py"]["sub"], nodes["conn:rec"]["sub"]),
                         ("read-only", "not in the connections registry", ""))
        self.assertEqual((nodes["src:Recorder"]["group"], nodes["src:Shop"]["group"], nodes["src:Books"]["group"]),
                         ("recording", "watch", "system"))
        self.assertEqual((nodes["repos:alpha"]["status"], nodes["repos:alpha"]["sub"], nodes["vault:gamma"]["sub"]),
                         ("warn", "2 to look at", "pulled on Sam"))
        for eid, count in (("box:a@x.test>conn:mailer", 5), ("conn:mailer>run:ingest", 5), ("run:ingest>vault:alpha", 2),
                           ("src:Recorder>conn:rec", 1), ("conn:rec>vault:alpha", 1), ("src:Shop>run:watch", 0),
                           ("run:watch>vault:alpha", 0), ("box:c@x.test>machine:Sam", 0), ("machine:Sam>vault:gamma", 0),
                           ("src:Recorder>machine:Sam", 0), ("cal:me@x.test>conn:cal", 0), ("conn:cal>run:center", 0),
                           ("src:Books>conn:books", 0), ("conn:books>vault:alpha", 0), ("conn:tracker>vault:alpha", 0),
                           ("vault:alpha>repos:alpha", 0), ("repos:alpha>site:alpha.test", 0), ("vault:alpha>site:alpha.test", 0),
                           ("run:center>page:" + cc.vault_key(self.home) + ":command-center", 0),
                           ("vault:alpha>page:" + cc.vault_key(self.tmp / "alpha") + ":daily-brief", 0)):
            self.assertEqual(edges[eid]["count"], count, eid)
        self.assertEqual(edges["machine:Sam>vault:gamma"]["kind"], "away")
        self.assertNotIn("run:ingest>vault:ghost", edges)
        self.assertNotIn("run:watch>vault:nowhere", edges)
        known = set(nodes)
        self.assertEqual([e["id"] for e in data["edges"] if e["source"] not in known or e["target"] not in known], [])

    def test_a_script_found_by_its_code_is_a_part(self):
        alpha = self.tmp / "alpha"
        write(alpha, "resources/scripts/ledger.py", "import subprocess\nsubprocess.run(['books', 'export'])\n")
        write(alpha, "resources/scripts/probe.py", "import urllib.request\nURL = 'https://api.shop.example/v1'\n")
        write(alpha, "resources/scripts/rec.py", "import subprocess\nsubprocess.run('books sync', shell=True)\n")
        write(alpha, ".claude/skills/close-books/SKILL.md", "Run `py -3 resources/scripts/ledger.py`.\n")
        data = self.build()
        nodes = {n["id"]: n for n in data["nodes"]}
        edges = {e["id"] for e in data["edges"]}
        self.assertEqual((nodes["conn:ledger.py"]["kind"], nodes["conn:ledger.py"]["sub"]), ("script", cc.UNLISTED))
        self.assertEqual(nodes["conn:ledger.py"]["detail"],
                         {"provider": "Books", "writes": "", "through": "books", "calls": "", "run_by": "close-books",
                          "path": "resources/scripts/ledger.py"})
        self.assertEqual(nodes["conn:probe.py"]["detail"],
                         {"provider": "", "writes": "", "through": "", "calls": "api.shop.example", "run_by": "",
                          "path": "resources/scripts/probe.py"})
        for eid in ("src:Books>conn:ledger.py", "conn:ledger.py>vault:alpha", "conn:probe.py>vault:alpha",
                    f"src:{cc.UNLABELLED}>conn:probe.py"):
            self.assertIn(eid, edges)
        self.assertEqual(nodes[f"src:{cc.UNLABELLED}"]["group"], "system")
        self.assertNotIn("src:Books>conn:rec", edges)

    def test_what_is_missing_is_said(self):
        notes = self.build()["meta"]["notes"]
        self.assertEqual(notes[0], "One calendar failed.")
        self.assertIn("1 calendar event had no date or no title and was left out.", notes)
        self.assertIn("delta was not read: the path is not there: not mounted, or moved", notes)
        self.assertTrue(any(n.startswith("An entry was not read") for n in notes))
        (self.home / "connections.json").unlink()
        (self.home / "tasks.json").unlink()
        data = self.build(events=None, note="")
        self.assertEqual(data["meta"]["notes"][:3], [
            "No connections registry: connections are named as the vaults write them.",
            "No calendar events were given: the agenda holds only the vaults' own meetings.",
            "No task registry: the scheduled runs are not shown."])
        self.assertIsNone(data["meta"]["hub"])
        self.assertIn("conn:mailer>vault:alpha", {e["id"] for e in data["edges"]})
        self.assertIn("2 calendar events had no date or no title and were left out.",
                      self.build(events=[{}, {}])["meta"]["notes"])

    def test_the_build_time_stands_in_the_header(self):
        self.assertIn('data-draw="built"', cc.page({"meta": {}}).split("</header>")[0])

    def test_the_page_embeds_the_data_and_loads_nothing(self):
        text = cc.page({"meta": {"notes": ["a <b> note"]}})
        self.assertIn("<title>Command Center</title>", text)
        self.assertIn('a \\u003cb> note', text)
        self.assertNotIn("__PARAOS_", text)
        self.assertNotIn("src=\"http", text)

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(cc, "run_command", self.run):
            try:
                code = cc.main([*args, "--paraos-home", str(self.home)])
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def test_the_cli_writes_the_page_and_its_data(self):
        events = write(self.tmp, "events.json", json.dumps([{"date": "2026-03-12", "title": "Demo"}]))
        page = self.tmp / "out" / "cc.html"
        with mock.patch.object(cc, "build", wraps=cc.build) as built:
            code, out, _ = self.run_main("--today", "2026-03-10", "--events", str(events), "--out", str(page),
                                         "--code-root", str(self.code), "--offline")
        self.assertEqual(code, 0)
        self.assertEqual(built.call_args.kwargs["online"], False)
        line = json.loads(out)
        self.assertEqual((line["page"], line["publish"], line["title"], line["url"]), ("command-center", "claude", "Command Center", None))
        self.assertEqual(Path(line["out"]), page.resolve())
        self.assertIn("Demo", page.read_text(encoding="utf-8"))
        saved = json.loads((self.home / "cache" / "command-center" / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["meta"]["today"], "2026-03-10")
        self.assertTrue((self.home / "cache" / "command-center" / "events.json").is_file())

    def test_a_local_page_needs_no_out(self):
        code, out, _ = self.run_main("--publish", "local")
        self.assertEqual((code, json.loads(out)["publish"]), (0, "local"))
        code, out, _ = self.run_main("--today", "2026-03-10")
        self.assertEqual(code, 0)
        self.assertTrue(Path(json.loads(out)["out"]).is_file())
        self.assertEqual(json.loads(out)["publish"], "local")

    def test_the_cli_lists_the_calendars_and_refuses_what_it_cannot_use(self):
        code, out, _ = self.run_main("--calendars", "--today", "2026-03-10")
        listed = json.loads(out)
        self.assertEqual((code, listed["today"], [c["endpoint"] for c in listed["calendars"]]), (0, "2026-03-10", ["me@x.test", "other"]))
        self.assertEqual(self.run_main("--today", "soon")[0], 2)
        code, _, err = self.run_main("--today", "2026-03-10")
        self.assertEqual(code, 2)
        self.assertIn("name it with --out", err)
        (self.home / "vaults.json").unlink()
        code, _, err = self.run_main("--calendars")
        self.assertEqual(code, 3)
        self.assertIn("no registry", err)


if __name__ == "__main__":
    unittest.main()
