#!/usr/bin/env python3
"""Tests for render_dashboard.py. Each one pins a rule of the script, which is the specification.

    python3 test_render_dashboard.py
    py -3 test_render_dashboard.py

Standard library only. Every fixture is a throwaway vault scanned by brief_scan.py in a
temporary directory, and the cache lives in a temporary PARAOS_HOME: nothing reads or writes
a real vault or the machine's own cache. The page's script, which lays the data out and dates
it against the day it is opened, is not run here; what it is handed is.
"""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-daily-brief" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from brief_scan import scan
from render_dashboard import (JudgmentError, cut, local_page, main, mechanical_now,
                              publish_choice, remember, remembered_url, render)
from test_brief_scan import build_people_vault, build_vault, write

TODAY = date(2026, 9, 15)
DATA_RE = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)


def data(page):
    """What the page's script is handed."""
    return json.loads(DATA_RE.search(page).group(1))


class DashboardCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        patch = mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)
        self.root = Path(self.tmp.name) / "vault"
        build_vault(self.root)
        write(self.root, "CLAUDE.md", "# BelFoot Vault Conventions\n")

    def report(self):
        return json.loads(json.dumps(scan(self.root, TODAY)))

    def first_task(self, report):
        t = report["tasks"][0]
        return {"file": t["file"], "line": t["line"]}

    def judgment(self, report, **extra):
        j = {"flags": [], "next_action": {"text": "Open the file", **self.first_task(report)}}
        j.update(extra)
        return j

    def page(self, judgment=None, report=None, **kw):
        report = report or self.report()
        return data(render(report, judgment, **kw)[1])


class Page(DashboardCase):

    def test_the_title_is_the_h1_without_vault_conventions(self):
        title, page = render(self.report(), self.judgment(self.report()))
        self.assertEqual(title, "BelFoot Dashboard")
        self.assertIn("<title>BelFoot Dashboard</title>", page)

    def test_the_page_loads_nothing_from_the_network(self):
        _, page = render(self.report(), self.judgment(self.report()))
        self.assertNotIn("<link", page)
        self.assertNotIn(" src=", page)
        self.assertIsNone(re.search(r"https?://", page))

    def test_both_dark_mode_guards_are_present(self):
        _, page = render(self.report(), self.judgment(self.report()))
        self.assertIn(':root:not([data-theme="light"])', page)
        self.assertIn(':root[data-theme="dark"]', page)

    def test_no_text_in_the_data_can_close_its_block(self):
        write(self.root, "projects/acme-website/actions.md",
              "# a\n\n- [ ] Fix </script><script>alert(1)</script> & co 📅 2026-09-01\n")
        _, page = render(self.report(), self.judgment(self.report()))
        self.assertNotIn("<script>alert", page)
        self.assertEqual(page.count("</script>"), 2)
        self.assertIn("</script><script>alert(1)", json.dumps(data(page), ensure_ascii=False))

    def test_a_judgment_string_reaches_the_page_escaped(self):
        report = self.report()
        got = self.page(self.judgment(report, flags=["**x** <b>y</b> `z`"]), report)
        self.assertEqual(got["flags"][0]["html"], "<b>x</b> &lt;b&gt;y&lt;/b&gt; <code>z</code>")


class Tasks(DashboardCase):

    def test_each_task_carries_its_headline_due_date_and_where_it_sits(self):
        t = next(t for t in self.page(self.judgment(self.report()))["tasks"]
                 if t["headline"] == "Due today")
        self.assertEqual((t["due"], t["priority"], t["where"], t["entity_key"]),
                         ("2026-09-21", "🔺", "acme-website:5", "P:acme-website"))

    def test_a_time_is_read_only_off_a_dated_line(self):
        write(self.root, "areas/business/actions.md", "# b\n\n"
              "- [ ] Call Ann at 9:30 📅 2026-09-16\n- [ ] Ask about the 11:00 slot\n"
              "- [ ] Board at 25:61 📅 2026-09-17\n")
        rows = {t["headline"]: t["time"] for t in self.page(self.judgment(self.report()))["tasks"]}
        self.assertEqual((rows["Call Ann at 9:30"], rows["Ask about the 11:00 slot"],
                          rows["Board at 25:61"]), ("09:30", None, None))

    def test_a_wait_carries_its_own_fields_and_no_date(self):
        write(self.root, "areas/business/actions.md", "# b\n\n"
              "- [ ] Waiting on [Ann](../network/ann.md): the signed deed (since 2026-09-01)\n")
        t = next(t for t in self.page(self.judgment(self.report()))["tasks"] if t["waiting"])
        self.assertEqual((t["due"], t["waiting"]),
                         (None, {"person": "Ann", "what": "the signed deed", "since": "2026-09-01"}))

    def test_people_and_pipeline_reach_the_page_with_contact_names(self):
        root = build_people_vault(Path(self.tmp.name) / "people")
        report = json.loads(json.dumps(scan(root, date(2026, 9, 21))))
        got = data(render(report)[1])
        self.assertEqual({p["person"] for p in got["people"]}, {"an-aerts", "piet-peeters"})
        acme = next(i for i in got["pipeline_items"] if i["name"] == "acme")
        self.assertEqual(acme["contact_name"], "An Aerts")
        owed = next(t for t in got["tasks"] if t["headline"] == "Draft the plan")
        self.assertEqual(owed["person_name"], "Piet Peeters")
        self.assertEqual([c["stage"] for c in got["pipeline"][0]["counts"]], ["Lead", "Proposal", "Won"])


class Drilldowns(DashboardCase):

    def test_a_flag_object_opens_on_the_tasks_the_scan_flagged(self):
        report = self.report()
        self.assertTrue(report["flags"]["stale_recurrence"])
        flag = {"text": "**Weekly review** is behind", "kind": "stale_recurrence"}
        got = self.page(self.judgment(report, flags=[flag]), report)["flags"][0]
        self.assertEqual(len(got["tasks"]), len(report["flags"]["stale_recurrence"]))
        self.assertTrue(got["tasks"][0].startswith("projects/acme-website/actions.md:"))

    def test_a_flag_object_naming_what_the_scan_did_not_raise_is_an_error(self):
        report = self.report()
        for flag in ({"text": "x", "kind": "undated_majority"},
                     {"text": "x", "kind": "over_threshold", "file": "projects/acme-website/actions.md"},
                     {"text": "x", "kind": "nothing_open"},
                     {"text": "x", "kind": "made_up"}):
            with self.assertRaises(JudgmentError):
                render(report, self.judgment(report, flags=[flag]))

    def test_a_nothing_open_flag_opens_on_each_entity_and_its_action_files_date(self):
        write(self.root, "projects/stalled/actions.md", "# s\n\n- [x] Kicked off\n")
        write(self.root, "areas/garden/brief.md", "# g\n")
        report = self.report()
        flag = {"text": "**garden: nothing open**", "kind": "nothing_open"}
        rows = self.page(self.judgment(report, flags=[flag]), report)["flags"][0]["rows"]
        touched = report["flags"]["nothing_open"][1]["touched"]
        self.assertEqual(rows, [{"label": "areas/garden", "meta": "no actions.md"},
                                {"label": "projects/stalled", "meta": f"since {touched}"}])

    def test_a_plain_string_flag_opens_on_nothing(self):
        report = self.report()
        got = self.page(self.judgment(report, flags=["**x: 14 open**"]), report)["flags"]
        self.assertEqual(got, [{"html": "<b>x: 14 open</b>", "tasks": [], "rows": []}])

    def test_an_idea_carries_its_stage_date_revisit_and_the_actions_naming_it(self):
        write(self.root, "resources/ideas/acme-deal/brief.md",
              "# Acme deal\n\n**Stage:** Qualified (since 2026-09-01)\n\n"
              "Revisit when Jan replies.\n")
        write(self.root, "areas/business/actions.md", "# b\n\n"
              "- [ ] Send the acme deal deck\n"
              "- [ ] Call about [it](../../resources/ideas/acme-deal/brief.md) 📅 2026-09-20\n")
        idea = next(i for i in self.page(self.judgment(self.report()))["ideas"]
                    if i["name"] == "acme-deal")
        self.assertEqual(idea["since"], "2026-09-01")
        self.assertIn("Revisit when Jan replies", idea["revisit"])
        self.assertEqual(sorted(idea["actions"]), ["areas/business/actions.md:3",
                                                   "areas/business/actions.md:4"])

    def test_sign_in_codes_are_counted_and_never_named(self):
        write(self.root, "triage/20260914 Your verification code 482913.md",
              "# Your verification code\n\nYour verification code is 482913.\n")
        write(self.root, "triage/20260914 Mail - Quote.md",
              "# Quote\n\n- **From:** Ann <ann@example.be>\n\nThe quote is attached.\n")
        _, page = render(self.report(), self.judgment(self.report()))
        got = data(page)
        self.assertEqual(got["triage_codes"], 1)
        self.assertEqual(len(got["triage"]), 2)
        self.assertNotIn("482913", page)
        self.assertNotIn("verification code", page.lower())
        quote = next(x for x in got["triage"] if x["name"] == "20260914 Mail - Quote")
        self.assertEqual(quote["from"], "Ann <ann@example.be>")


class Judgment(DashboardCase):

    def test_a_next_action_the_scan_does_not_hold_is_an_error(self):
        report = self.report()
        with self.assertRaises(JudgmentError):
            render(report, self.judgment(report, next_action={"text": "x", "file": "nope.md",
                                                              "line": 1}))

    def test_a_next_action_is_required(self):
        with self.assertRaises(JudgmentError):
            render(self.report(), {"flags": []})

    def test_the_next_action_names_where_it_sits(self):
        got = self.page(self.judgment(self.report()))["next_action"]
        self.assertEqual((got["html"], got["where"], got["note"]),
                         ("Open the file", "business:4", None))

    def test_the_agenda_is_the_judgments_and_an_empty_day_is_dropped(self):
        report = self.report()
        got = self.page(self.judgment(report, agenda=[
            {"label": "Today", "events": [{"when": "09:30", "title": "**Call**", "sub": "Ann"}]},
            {"label": "Tomorrow", "events": []}], agenda_note="Calendar unread"), report)
        self.assertEqual(got["agenda"], [{"label": "Today", "events": [
            {"when": "09:30", "html": "<b>Call</b> · Ann"}]}])
        self.assertEqual(got["agenda_note"], "Calendar unread")

    def test_an_entity_scope_has_no_page(self):
        with self.assertRaises(JudgmentError):
            render(json.loads(json.dumps(scan(self.root, TODAY, entity="acme-website"))))


class Mechanical(DashboardCase):

    def test_the_next_action_is_the_first_of_the_briefs_own_sort(self):
        got = self.page()
        self.assertEqual((got["next_action"]["html"], got["generated_by"], got["agenda"]),
                         ("Late thing", "from the scan alone", []))
        self.assertIn("the next /para-daily-brief run chooses", got["next_action"]["note"])

    def test_a_deadline_due_today_is_not_cut_for_plan_dates_or_overdue_recurrences(self):
        other = Path(self.tmp.name) / "six"
        write(other, "areas/work/actions.md", "# a\n\n"
              "- [ ] Plan the layout 🔼 ⏳ 2026-09-15\n"
              "- [ ] Monthly housekeeping 🔁 every month 📅 2026-09-07\n"
              "- [ ] Weekly review 🔁 every week 📅 2026-09-09\n"
              "- [ ] Reply to Sam 📅 2026-09-14\n"
              "- [ ] Sketch the cover ⏳ 2026-09-14\n"
              "- [ ] Ship the release 📅 2026-09-15\n")
        report = json.loads(json.dumps(scan(other, TODAY)))
        text = {(t["file"], t["line"]): t["text"] for t in report["tasks"]}
        now = [text[(p["file"], p["line"])] for p in mechanical_now(report)]
        self.assertEqual(len(now), 5)
        # Priority first; then a 📅 before a ⏳, a non-recurring item before a recurring one.
        self.assertEqual([n.split(" ")[0] for n in now],
                         ["Plan", "Reply", "Ship", "Monthly", "Weekly"])

    def test_nothing_due_says_so(self):
        other = Path(self.tmp.name) / "quiet"
        write(other, "areas/work/actions.md", "# a\n\n- [ ] Someday\n")
        got = data(render(json.loads(json.dumps(scan(other, TODAY))))[1])
        self.assertEqual(got["next_action"]["html"], "Nothing is overdue or due this week.")

    def test_every_fired_flag_is_worded_and_opens_on_its_items(self):
        write(self.root, "areas/busy/actions.md",
              "# b\n\n" + "".join(f"- [ ] Thing {n}\n" for n in range(12)))
        write(self.root, "archive/old/actions.md", "# o\n\n- [ ] Left open\n")
        write(self.root, "projects/acme-website/brief.md", "# a\n" + "line\n" * 501)
        write(self.root, "projects/stalled/actions.md", "# s\n\n- [x] Kicked off\n")
        write(self.root, "projects/waiting/actions.md", "# w\n\n- [x] Sent the quote\n")
        report = self.report()
        fired = [k for k, v in report["flags"].items() if v]
        self.assertGreaterEqual(len(fired), 6, fired)
        flags = self.page(report=report)["flags"]
        self.assertEqual(len(flags), len(fired))
        self.assertTrue(all(f["tasks"] or f["rows"] for f in flags))
        text = " ".join(f["html"] for f in flags)
        self.assertIn("busy: 12 open</b>, over the cap of 8", text)
        self.assertIn("Weekly review", " ".join(json.dumps(f) for f in flags) +
                      json.dumps(self.page(report=report)["tasks"]))
        self.assertIn("projects/acme-website/brief.md: 502 lines", text)
        self.assertIn("undated", text)
        self.assertIn("<b>stalled: nothing open</b>, and 1 more", text)

    def test_open_card_checkboxes_are_worded_as_the_vaults_own_rule(self):
        write(self.root, "CLAUDE.md", "# BelFoot Vault Conventions\n\n"
              "### Where a checkbox may live\n\n| Bucket | `actions.md` | State |\n|---|---|---|\n"
              "| `areas/network/` | **never** | a checkbox on a card is a filing error |\n")
        write(self.root, "areas/network/ann-smet.md", "# Ann\n\n## Next actions\n\n- [ ] Call\n")
        text = " ".join(f["html"] for f in self.page()["flags"])
        self.assertIn("2 under areas/network/ (worst: areas/network/ann-smet.md, 1)", text)
        self.assertIn("this vault's contact cards hold none", text)
        self.assertNotIn("archive hygiene", text)


class SilentSource(DashboardCase):

    def silent_report(self):
        home = Path(self.tmp.name) / "ledgers"
        write(self.root, "CLAUDE.md", "# BelFoot Vault Conventions\n\n## Triage sources\n\n"
              "| Source | Type | Endpoint | Relevant when |\n|---|---|---|---|\n"
              "| granola | sync-script 🔁 every week | `resources/scripts/granola.js` | Meetings. |\n")
        write(home, "data/granola/synced.json",
              json.dumps({"a": str(self.root / "triage" / "20260901 Kickoff.md")}))
        return json.loads(json.dumps(scan(self.root, TODAY, paraos_home=home)))

    def test_a_silent_source_is_worded_and_opens_on_its_ledger(self):
        flag = next(f for f in self.page(report=self.silent_report())["flags"]
                    if "granola" in f["html"])
        self.assertIn("<b>granola: nothing since 2026-09-01</b> (14 days, expected every week)",
                      flag["html"])
        self.assertTrue(flag["rows"][0]["label"].endswith("data/granola/synced.json"))

    def test_a_judgment_flag_opens_only_on_a_source_the_scan_flagged(self):
        report = self.silent_report()
        flag = {"text": "granola is quiet", "kind": "silent_sources", "source": "granola"}
        self.assertTrue(self.page(self.judgment(report, flags=[flag]), report)["flags"][0]["rows"])
        with self.assertRaises(JudgmentError):
            render(report, self.judgment(report, flags=[dict(flag, source="pocket")]))


class Cut(unittest.TestCase):

    def test_a_bold_lead_is_the_whole_line(self):
        self.assertEqual(cut("**Chase the vendor.** Then the rest"), "Chase the vendor")

    def test_otherwise_the_first_clause(self):
        self.assertEqual(cut("Send the export; then wait"), "Send the export")

    def test_a_long_line_stops_at_a_word_with_an_ellipsis(self):
        out = cut("word " * 40)
        self.assertLessEqual(len(out), 101)
        self.assertTrue(out.endswith("…"))

    def test_a_link_keeps_its_label(self):
        self.assertEqual(cut("Read [the notes](a/b.md) twice"), "Read the notes twice")

    def test_a_full_stop_before_a_number_or_a_lowercase_word_ends_no_sentence(self):
        self.assertEqual(cut("Ask for the art. 12 statement, e.g. the fund. Then file it"),
                         "Ask for the art. 12 statement, e.g. the fund")

    def test_a_clause_end_inside_parentheses_is_kept(self):
        self.assertEqual(cut("Call the notary (deed; date. Soon) about it; then wait"),
                         "Call the notary (deed; date. Soon) about it")

    def test_emphasis_keeps_its_text(self):
        self.assertEqual(cut("Send the *signed* plans _(from the listing)_ to my_agent"),
                         "Send the signed plans (from the listing) to my_agent")
        out = cut("Ask for the art. 12 statement (reserve fund, arrears, three years of "
                  "minutes, the last balance) _(suggested from the listing)_")
        self.assertTrue(out.startswith("Ask for the art. 12 statement (reserve fund"))
        self.assertNotIn("_", out)


class Cache(DashboardCase):

    def test_a_url_round_trips_per_vault(self):
        self.assertIsNone(remembered_url(self.root))
        remember(self.root, "https://example.invalid/a")
        self.assertEqual(remembered_url(self.root), "https://example.invalid/a")
        self.assertIsNone(remembered_url(Path(self.tmp.name) / "other"))

    def test_a_corrupt_cache_reads_as_empty(self):
        write(self.home, "cache/daily-brief/dashboards.json", "{not json")
        self.assertIsNone(remembered_url(self.root))
        self.assertEqual(publish_choice(self.root), "claude")

    def test_claude_is_the_default_and_a_choice_survives_a_remembered_url(self):
        self.assertEqual(publish_choice(self.root), "claude")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--publish", "local", "--vault", str(self.root)]), 0)
        remember(self.root, "https://example.invalid/b")
        self.assertEqual(publish_choice(self.root), "local")
        self.assertEqual(remembered_url(self.root), "https://example.invalid/b")


class Cli(DashboardCase):

    def files(self, mechanical=False):
        report = self.report()
        s = Path(self.tmp.name) / "scan.json"
        j = Path(self.tmp.name) / "judgment.json"
        s.write_text(json.dumps(report), encoding="utf-8")
        j.write_text(json.dumps(self.judgment(report)), encoding="utf-8")
        return ["--scan", str(s)] + (["--mechanical"] if mechanical else ["--judgment", str(j)])

    def run_main(self, argv):
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = main(argv)
        return code, json.loads(printed.getvalue()) if code == 0 else None

    def test_the_page_is_never_written_inside_the_vault(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(self.files() + ["--out", str(self.root / "page.html")]), 2)
        self.assertFalse((self.root / "page.html").exists())
        code, printed = self.run_main(self.files() + ["--out", str(Path(self.tmp.name) / "o.html")])
        self.assertEqual((code, printed["title"], printed["publish"]),
                         (0, "BelFoot Dashboard", "claude"))
        self.assertFalse(data(Path(printed["out"]).read_text(encoding="utf-8"))["local"])

    def test_a_claude_page_needs_an_out_and_a_mechanical_render_no_judgment(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(self.files())
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(self.files(mechanical=True) + ["--judgment", "x.json", "--out", "o.html"])

    def test_a_local_vault_writes_the_refreshed_page_with_work_on_this_links(self):
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--publish", "local", "--vault", str(self.root)])
        code, printed = self.run_main(self.files(mechanical=True))
        self.assertEqual((code, printed["publish"]), (0, "local"))
        self.assertEqual(Path(printed["out"]), local_page(self.root))
        self.assertTrue(local_page(self.root).is_relative_to(self.home))
        self.assertTrue(data(local_page(self.root).read_text(encoding="utf-8"))["local"])


if __name__ == "__main__":
    unittest.main()
