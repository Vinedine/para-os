#!/usr/bin/env python3
"""Tests for paraos_pages.py, where a skill's page goes. Each one pins a rule of the script,
which is the specification.

    python3 test_paraos_pages.py
    py -3 test_paraos_pages.py

Standard library only. Every vault is a temporary directory and the cache lives in a
temporary PARAOS_HOME: nothing reads or writes a real vault or the machine's own cache.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from paraos_pages import (  # noqa: E402
    declared_pages, local_page, main, publish_choice, refresh, remember, remembered_url, run,
    store,
)

PAGES = """# Example Vault Conventions

## Pages

| Skill | Script |
|---|---|
| `/para-pipeline` | `resources/scripts/board.py` |
| para-daily-brief | `resources/scripts/week.py` |

## Later

| Skill | Script |
|---|---|
| para-pipeline | `resources/scripts/not-a-page.py` |
"""

BOARD = """import argparse, json, sys
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--vault"); ap.add_argument("--scan"); ap.add_argument("--out")
a = ap.parse_args()
rows = json.loads(Path(a.scan).read_text(encoding="utf-8"))["rows"]
Path(a.out).write_text("<title>Board</title>" + str(len(rows)), encoding="utf-8")
print("building")
print(json.dumps({"title": "Example Board", "description": "The board."}))
"""


def write(base, rel, text):
    path = Path(base) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class PagesCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        patch = mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)
        self.root = Path(self.tmp.name) / "vault"
        write(self.root, "CLAUDE.md", PAGES)
        write(self.root, "resources/scripts/board.py", BOARD)
        self.scan = write(self.tmp.name, "scan.json", json.dumps({"rows": [1, 2, 3]}))
        self.out_dir = Path(self.tmp.name) / "scratch"


class Cache(PagesCase):

    def test_a_url_round_trips_per_vault_and_per_page(self):
        self.assertIsNone(remembered_url(self.root, "board"))
        remember(self.root, "board", "https://example.invalid/a", "Example Board")
        self.assertEqual(remembered_url(self.root, "board"), "https://example.invalid/a")
        self.assertIsNone(remembered_url(self.root, "daily-brief"))
        self.assertIsNone(remembered_url(Path(self.tmp.name) / "other", "board"))

    def test_a_corrupt_cache_reads_as_empty_and_claude_is_the_default(self):
        write(self.home, "cache/board/dashboards.json", "{not json")
        self.assertIsNone(remembered_url(self.root, "board"))
        self.assertEqual(publish_choice(self.root, "board"), "claude")

    def test_a_choice_survives_a_remembered_url(self):
        store(self.root, "board", publish="local")
        remember(self.root, "board", "https://example.invalid/b", "Example Board")
        self.assertEqual(publish_choice(self.root, "board"), "local")
        self.assertEqual(local_page(self.root, "board"), self.home / "cache" / "board" / "vault.html")


class Declared(PagesCase):

    def test_rows_come_from_the_pages_section_alone(self):
        rows = declared_pages(self.root)
        self.assertEqual([(r["skill"], r["script"]) for r in rows],
                         [("para-pipeline", "resources/scripts/board.py"),
                          ("para-daily-brief", "resources/scripts/week.py")])

    def test_columns_are_found_by_their_heading(self):
        write(self.root, "CLAUDE.md", "## Pages\n\n| Script | Note | Skill |\n|---|---|---|\n"
                                      "| `a.py` | x | para-prep |\n")
        self.assertEqual([(r["skill"], r["script"]) for r in declared_pages(self.root)],
                         [("para-prep", "a.py")])

    def test_a_fenced_sample_and_a_missing_claude_md_declare_nothing(self):
        write(self.root, "CLAUDE.md", "## Pages\n\n```\n| Skill | Script |\n|---|---|\n"
                                      "| para-pipeline | a.py |\n```\n")
        self.assertEqual(declared_pages(self.root), [])
        self.assertEqual(declared_pages(Path(self.tmp.name) / "nothing"), [])


class Run(PagesCase):

    def test_a_declared_page_is_built_from_the_skills_scan_outside_the_vault(self):
        remember(self.root, "board", "https://example.invalid/c", "Example Board")
        [page] = run(self.root, "/para-pipeline", self.scan, self.out_dir)
        self.assertEqual((page["page"], page["publish"], page["title"], page["url"], page["error"]),
                         ("board", "claude", "Example Board", "https://example.invalid/c", None))
        self.assertEqual(Path(page["out"]), self.out_dir.resolve() / "board.html")
        self.assertEqual(Path(page["out"]).read_text(encoding="utf-8"), "<title>Board</title>3")

    def test_a_local_choice_writes_the_local_page(self):
        store(self.root, "board", publish="local")
        [page] = run(self.root, "para-pipeline", self.scan, self.out_dir)
        self.assertEqual(Path(page["out"]), local_page(self.root, "board"))
        self.assertTrue(local_page(self.root, "board").is_file())

    def test_only_the_rows_naming_the_skill_run(self):
        self.assertEqual(run(self.root, "para-prep", self.scan, self.out_dir), [])

    def test_each_failure_is_named_not_raised(self):
        [missing] = run(self.root, "para-daily-brief", self.scan, self.out_dir)
        self.assertIn("no script", missing["error"])
        [inside] = run(self.root, "para-pipeline", self.scan, self.root / "pages")
        self.assertIn("inside the vault", inside["error"])
        self.assertFalse((self.root / "pages").exists())
        write(self.root, "resources/scripts/board.py", "import sys\nsys.exit('scan unreadable')\n")
        [failed] = run(self.root, "para-pipeline", self.scan, self.out_dir)
        self.assertIn("scan unreadable", failed["error"])
        write(self.root, "resources/scripts/board.py", "print('done')\n")
        [silent] = run(self.root, "para-pipeline", self.scan, self.out_dir)
        self.assertIn("no {title, description}", silent["error"])


class Refresh(PagesCase):

    def skills(self, scan_body):
        skills = Path(self.tmp.name) / "skills"
        write(skills, "para-pipeline/scripts/pipeline_scan.py", scan_body)
        return skills

    def test_a_declared_page_is_rebuilt_from_a_fresh_scan_of_its_skill(self):
        skills = self.skills('import json\nprint(json.dumps({"rows": [1, 2]}))\n')
        store(self.root, "board", publish="local")
        page = refresh(self.root, "board", skills_dir=skills)
        self.assertEqual((page["title"], page["error"]), ("Example Board", None))
        self.assertEqual(local_page(self.root, "board").read_text(encoding="utf-8"),
                         "<title>Board</title>2")

    def test_each_failure_is_named_not_raised(self):
        self.assertIn("no row", refresh(self.root, "nothing")["error"])
        self.assertIn("no single scan", refresh(self.root, "board",
                                                 skills_dir=Path(self.tmp.name))["error"])
        failing = self.skills("import sys\nsys.exit('vault unreadable')\n")
        self.assertIn("vault unreadable", refresh(self.root, "board", skills_dir=failing)["error"])


class Example(PagesCase):

    def test_the_example_vaults_declared_page_builds_from_its_board(self):
        sys.path.insert(0, str(ROOT / "base" / ".claude" / "skills" / "para-pipeline" / "scripts"))
        from pipeline_scan import scan
        example = ROOT / "examples" / "belfoot-vault"
        report = write(self.tmp.name, "board.json", json.dumps(scan(example, date(2026, 6, 24))[0]))
        [page] = run(example, "para-pipeline", report, self.out_dir)
        self.assertEqual((page["title"], page["error"]), ("BelFoot Vendor Board", None))
        self.assertIn("Gateline Sport", Path(page["out"]).read_text(encoding="utf-8"))


class Cli(PagesCase):

    def call(self, argv):
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = main(argv)
        return code, json.loads(printed.getvalue())

    def test_publish_remember_and_run(self):
        vault = ["--vault", str(self.root)]
        self.assertEqual(self.call(["publish", "local", "--page", "board"] + vault)[1]["publish"],
                         "local")
        self.call(["remember", "https://example.invalid/d", "--page", "board",
                   "--title", "Example Board"] + vault)
        code, printed = self.call(["run", "--skill", "para-pipeline", "--scan", str(self.scan),
                                   "--out-dir", str(self.out_dir)] + vault)
        self.assertEqual((code, [p["url"] for p in printed["pages"]]),
                         (0, ["https://example.invalid/d"]))


if __name__ == "__main__":
    unittest.main()
