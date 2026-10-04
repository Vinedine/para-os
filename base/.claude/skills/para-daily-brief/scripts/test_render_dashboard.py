#!/usr/bin/env python3
"""Tests for render_dashboard.py. Each one pins a rule references/dashboard.md states.

    python3 test_render_dashboard.py
    py -3 test_render_dashboard.py

Standard library only. Every fixture is a throwaway vault scanned by brief_scan.py in a
temporary directory, and the URL cache lives in a temporary PARAOS_HOME: nothing reads or
writes a real vault or the machine's own cache.
"""

import contextlib
import io
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from brief_scan import scan
from render_dashboard import JudgmentError, cut, main, remember, remembered_url, render
from test_brief_scan import build_vault, write

TODAY = date(2026, 9, 15)


class DashboardCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "vault"
        build_vault(self.root)
        write(self.root, "CLAUDE.md", "# BelFoot Vault Conventions\n")

    def tearDown(self):
        self.tmp.cleanup()

    def report(self):
        return json.loads(json.dumps(scan(self.root, TODAY)))

    def first_task(self, report):
        t = report["tasks"][0]
        return {"file": t["file"], "line": t["line"]}

    def judgment(self, report, **extra):
        j = {"now": [self.first_task(report)], "flags": [],
             "next_action": {"text": "Open the file", **self.first_task(report)}}
        j.update(extra)
        return j


class Page(DashboardCase):

    def test_the_title_is_the_h1_without_vault_conventions(self):
        title, page = render(self.report(), self.judgment(self.report()))
        self.assertEqual(title, "BelFoot Dashboard")
        self.assertIn("<title>BelFoot Dashboard</title>", page)

    def test_the_page_loads_nothing_and_runs_nothing(self):
        _, page = render(self.report(), self.judgment(self.report()))
        self.assertNotIn("<script", page)
        self.assertNotIn("<link", page)
        self.assertIsNone(re.search(r"https?://", page))

    def test_both_dark_mode_guards_are_present(self):
        _, page = render(self.report(), self.judgment(self.report()))
        self.assertIn(':root:not([data-theme="light"])', page)
        self.assertIn(':root[data-theme="dark"]', page)

    def test_task_text_is_escaped(self):
        write(self.root, "projects/acme-website/actions.md",
              "# a\n\n- [ ] Fix <script>alert(1)</script> & co 📅 2026-09-01\n")
        report = self.report()
        risky = next(t for t in report["tasks"] if "<script>" in t["text"])
        pick = {"file": risky["file"], "line": risky["line"], "text": risky["text"]}
        _, page = render(report, self.judgment(report, now=[pick]))
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)


class Bars(DashboardCase):

    def test_segments_partition_each_row_and_counts_use_full_words(self):
        _, page = render(self.report(), self.judgment(self.report()))
        for row in re.findall(r'<div class="bar"[^>]*>(.*?)</div>', page):
            widths = [float(w) for w in re.findall(r"width:([\d.]+)%", row)]
            self.assertAlmostEqual(sum(widths), 100, delta=0.05)
        self.assertNotRegex(page, r"\b(over|up|und)\.")

    def test_entities_past_ten_join_one_strip_and_not_the_chart(self):
        for i in range(12):
            write(self.root, f"areas/area-{i:02}/actions.md", f"# a\n\n- [ ] Thing {i}\n")
        _, page = render(self.report(), self.judgment(self.report()))
        self.assertEqual(page.count('<summary class="row">'), 10)
        self.assertRegex(page, r'class="rest">\+\d+ more entities')

    def test_each_row_opens_on_its_own_open_tasks_in_bar_order(self):
        report = self.report()
        _, page = render(report, self.judgment(report))
        rows = re.findall(r'<summary class="row">.*?</span>([^<]*)</span>.*?</summary>'
                          r'<ol class="drill">(.*?)</ol>', page)
        self.assertEqual(len(rows), len(report["entities"]))
        for (label, drill), entity in zip(rows, report["entities"]):
            self.assertTrue(label.startswith(entity["label"]))
            segs = re.findall(r'<li><i class="seg-(\w+)"', drill)
            self.assertEqual(len(segs), entity["open"])
            self.assertEqual(segs, sorted(segs, key=["over", "up", "und"].index))
        acme = dict(rows)["acme-website"]
        self.assertLess(acme.index("Late thing"), acme.index("Due today"))
        self.assertLess(acme.index("Due today"), acme.index("No date at all"))
        self.assertNotIn("Done already", page)

    def test_the_remainder_strip_opens_on_the_tasks_it_counts(self):
        for i in range(12):
            write(self.root, f"areas/area-{i:02}/actions.md", f"# a\n\n- [ ] Thing {i}\n")
        report = self.report()
        _, page = render(report, self.judgment(report))
        drill = re.search(r'<summary class="rest">.*?</summary><ol class="drill">(.*?)</ol>',
                          page).group(1)
        self.assertEqual(drill.count("<li>"), sum(e["open"] for e in report["entities"][10:]))

    def test_the_overdue_tile_is_alert_only_when_nonzero(self):
        report = self.report()
        _, page = render(report, self.judgment(report))
        alert = '<div class="tile alert">' in page
        self.assertEqual(alert, report["totals"]["overdue"] > 0)


class Judgment(DashboardCase):

    def test_a_now_item_the_scan_does_not_hold_is_an_error(self):
        report = self.report()
        with self.assertRaises(JudgmentError):
            render(report, self.judgment(report, now=[{"file": "nope.md", "line": 1}]))

    def test_more_than_five_now_items_is_an_error(self):
        report = self.report()
        with self.assertRaises(JudgmentError):
            render(report, self.judgment(report, now=[self.first_task(report)] * 6))

    def test_a_next_action_is_required(self):
        report = self.report()
        with self.assertRaises(JudgmentError):
            render(report, {"now": []})

    def test_now_items_leave_the_later_counts(self):
        report = self.report()
        _, with_now = render(report, self.judgment(report))
        _, without = render(report, self.judgment(report, now=[]))
        total = lambda page: sum(int(n) for n in re.findall(
            r"(\d+) [a-z0-9 ]+", re.search(r'class="later">(.*?)</p>', page).group(1)))
        self.assertLessEqual(total(with_now), total(without))
        self.assertNotIn("<h2>Now", without)

    def test_empty_agenda_and_flags_render_no_section(self):
        report = self.report()
        _, page = render(report, self.judgment(report))
        self.assertNotIn("<h2>Agenda", page)
        self.assertNotIn("<h2>Health flags", page)


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


class RememberedUrl(DashboardCase):

    def test_a_url_round_trips_per_vault(self):
        home = Path(self.tmp.name) / "home"
        self.assertIsNone(remembered_url(self.root, home))
        remember(self.root, "https://example.invalid/a", home)
        self.assertEqual(remembered_url(self.root, home), "https://example.invalid/a")
        self.assertIsNone(remembered_url(Path(self.tmp.name) / "other", home))

    def test_a_corrupt_cache_reads_as_empty(self):
        home = Path(self.tmp.name) / "home"
        write(home, "cache/daily-brief/dashboards.json", "{not json")
        self.assertIsNone(remembered_url(self.root, home))


class Cli(DashboardCase):

    def test_the_page_is_never_written_inside_the_vault(self):
        report = self.report()
        s = Path(self.tmp.name) / "scan.json"
        j = Path(self.tmp.name) / "judgment.json"
        s.write_text(json.dumps(report), encoding="utf-8")
        j.write_text(json.dumps(self.judgment(report)), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--scan", str(s), "--judgment", str(j),
                                   "--out", str(self.root / "page.html")]), 2)
        self.assertFalse((self.root / "page.html").exists())
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = main(["--scan", str(s), "--judgment", str(j),
                         "--out", str(Path(self.tmp.name) / "out" / "page.html")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(printed.getvalue())["title"], "BelFoot Dashboard")


if __name__ == "__main__":
    unittest.main()
