#!/usr/bin/env python3
"""Tests for field_test.py.

    python3 test_field_test.py
    py -3 test_field_test.py

The para-os home and its one vault are synthetic, in a temporary directory; the scans run from
this repo's own HEAD on both sides, so every one of them must come back the same.
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from field_test import (MISSING, compare, differences, main, normalise, scratch_home,  # noqa: E402
                        swaps, unstamped)


def write(base, rel, text):
    path = Path(base) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class Diffing(unittest.TestCase):

    def test_an_object_differs_key_by_key_and_a_list_as_a_multiset(self):
        before = {"a": 1, "rows": [{"n": 1}, {"n": 2}, {"n": 2}], "gone": True}
        after = {"a": 2, "rows": [{"n": 2}, {"n": 3}, {"n": 1}], "new": "x"}
        self.assertEqual(list(differences(before, after)),
                         [("$.a", 1, 2), ("$.gone", True, MISSING), ("$.new", MISSING, "x"),
                          ("$.rows[]", {"n": 2}, MISSING), ("$.rows[]", MISSING, {"n": 3})])

    def test_a_list_of_named_objects_pairs_them_and_shows_the_field_that_moved(self):
        before = [{"name": "a", "x": 1}, {"name": "b"}]
        after = [{"name": "c"}, {"name": "a", "x": 2}]
        self.assertEqual(list(differences(before, after)),
                         [("$[name=a].x", 1, 2), ("$[name=b]", {"name": "b"}, MISSING),
                          ("$[name=c]", MISSING, {"name": "c"})])
        twice = [{"name": "a"}, {"name": "a", "x": 1}]
        self.assertEqual(list(differences(twice, [{"name": "a"}])),
                         [("$[]", {"name": "a", "x": 1}, MISSING)])

    def test_a_reordered_list_and_equal_values_are_no_change(self):
        self.assertEqual(list(differences({"x": [3, 1, 2]}, {"x": [1, 2, 3]})), [])
        self.assertEqual(list(differences(None, None)), [])

    def test_a_crash_on_head_alone_is_the_regression(self):
        ok, broken = {"code": 0, "out": {}, "error": None}, {"code": 1, "out": None, "error": "boom"}
        self.assertEqual(compare(ok, broken)[0], "CRASH on head: boom")
        self.assertEqual(compare(broken, ok)[0], "fixed: crashed on base (boom)")
        self.assertEqual(compare(broken, broken)[0], "crashes on both: boom")
        self.assertEqual(compare(ok, dict(ok, code=3)), ("1 change", [("$.exit", 0, 3)]))

    def test_every_spelling_of_a_scratch_folder_becomes_its_placeholder(self):
        folder = Path(tempfile.gettempdir()) / "kit-side"
        pairs = swaps((folder, "<kit>"), sha="0123abcd" * 5)
        out = normalise({str(folder / "a.py"): [folder.as_posix() + "/b", "0123abcd" * 5]}, pairs)
        self.assertEqual(out, {str(Path("<kit>") / "a.py"): ["<kit>/b", "<ref>"]})


class Stamp(unittest.TestCase):

    def test_a_changed_template_under_the_same_marker_is_unstamped(self):
        mark = "<!-- para-os-template: 2026.10.04 -->\n"
        self.assertEqual(unstamped(mark + "a\n", mark + "b\n"), "2026.10.04")
        self.assertIsNone(unstamped(mark + "a\n", mark + "a\n"))
        self.assertIsNone(unstamped(mark + "a\n", mark.replace("10.04", "11.01") + "b\n"))
        self.assertIsNone(unstamped("", mark))


class ScratchHome(unittest.TestCase):

    def test_the_copy_holds_what_the_scans_read_and_only_the_scanned_vaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            read = ["operator.json", "cache/ingest/ledger.json", "cache/ingest/runs/1.json",
                    "cache/triage/decisions/v.jsonl", "cache/outlook/synced.json",
                    "data/deep-clean/v.txt", "quarantine/v/run/manifest.json"]
            unread = ["secrets/token.json", "para-os/README.md", "cache/ingest/work/1/fetch-1.json",
                      "data/takeout/mail.pdf", "quarantine/v/run/files/letter.pdf"]
            for rel in read + unread:
                write(home, rel, "{}")
            write(home, "vaults.json", json.dumps([{"name": "a"}, {"name": "b"}]))
            scratch = Path(tmp) / "scratch"
            scratch_home(home, scratch, [{"name": "a"}])
            self.assertEqual([rel for rel in read + unread if (scratch / rel).is_file()], read)
            self.assertEqual(json.loads((scratch / "vaults.json").read_text()), [{"name": "a"}])


class EndToEnd(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        vault = self.tmp / "north"
        write(vault, "CLAUDE.md", "# north\n\n**Type:** vault\n")
        write(vault, "projects/site/actions.md", "# Site\n\n- [ ] Send the quote 📅 2026-11-01\n")
        write(vault, "triage/note.md", "A loose note.\n")
        write(self.home, "vaults.json", json.dumps(
            [{"name": "north", "path": vault.as_posix(), "purpose": "Tests.", "active": True},
             {"name": "gone", "path": (self.tmp / "absent").as_posix(), "active": True},
             {"name": "idle", "path": vault.as_posix(), "active": False}]))

    def field_test(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(["--paraos-home", str(self.home), "--no-example", "--today", "2026-11-02",
                         *argv])
        return code, (json.loads(out.getvalue()) if out.getvalue() else None)

    def test_one_commit_on_both_sides_reports_every_scan_the_same(self):
        code, out = self.field_test("--base", "HEAD", "--head", "HEAD")
        self.assertEqual((code, out["regressions"], out["unstamped"]), (0, 0, None))
        self.assertEqual(set(out["statuses"]), {"north", "gone", "(registry)"})
        self.assertEqual(set(out["statuses"]["north"].values()), {"same"})
        self.assertEqual(set(out["statuses"]["gone"].values()), {"not mounted"})
        self.assertEqual(set(out["statuses"]["(registry)"]), {"global", "audit"})
        report = Path(out["report"])
        self.assertEqual(report.parent, self.home / "data" / "test-runs")
        self.assertIn("| north |", report.read_text(encoding="utf-8"))

    def test_a_ref_that_names_nothing_and_no_vault_stop_with_exit_two(self):
        self.assertEqual(self.field_test("--base", "no-such-ref", "--head", "HEAD"), (2, None))
        self.assertEqual(self.field_test("--base", "HEAD", "--head", "HEAD", "--skip", "north",
                                         "--skip", "gone"), (2, None))


if __name__ == "__main__":
    unittest.main()
