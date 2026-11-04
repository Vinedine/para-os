#!/usr/bin/env python3
"""Tests for paraos_repos.py, the code-repos table, its reader and its converter. Each one pins
a rule of the script, which is the specification.

    python3 test_paraos_repos.py
    py -3 test_paraos_repos.py

Standard library only. Every vault and para-os home is a temporary directory.
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from paraos_repos import (  # noqa: E402
    COLUMNS, convert, home_candidates, list_repos, main, parse, role_of, site_hints, write,
)

FRONT = '---\npaths:\n  - "projects/**"\n  - "areas/**"\n---\n\n# Code repos\n\nThe repos this vault steers.\n\n'
HEADER = "| " + " | ".join(COLUMNS) + " |\n|---|---|---|---|---|---|\n"

TABLE_STYLE = FRONT + (
    "| Repo | What it is | Vault home |\n|---|---|---|\n"
    "| `billing-api` | Functions app for invoices | [areas/billing/](../../areas/billing/) |\n"
    "| `ledger` | Batch jobs | [areas/ledger/](../../areas/ledger/) |\n"
    "\nReference-only, no vault area:\n\n"
    "- `old-bus` - Legacy bus, kept to read. History in `archive/projects/bus-exit/`.\n"
)
HEADING_STYLE = FRONT + (
    "Repos under the code folder:\n\n"
    "**Active** (current work):\n"
    "- `model` - Architecture model. See [overview](../../areas/model/overview.md).\n"
    "- `portfolio-api` - HTTP API for the portfolio.\n"
    "\n**Reference-only** (past work):\n"
    "- `poc-queue` - Messaging proof of concept.\n"
    "\n**Other** (queried now and then):\n"
    "- `engine` - Workflow engine.\n"
)
BULLET_STYLE = FRONT + (
    "- `shop-site` - React site for the shop at shop-example.com, see https://ci.example.org/x.\n"
    "  Built on the same pattern as the hub.\n"
    "- **scraper**: Node.js scraper. See `resources/ideas/scraper-relaunch/`.\n"
    "- [hub-site](https://example.com/hub) - Brand hub for example.com; archived at\n"
    "  `archive/projects/hub-v1/`, maintained at `areas/hub/`.\n"
    "- plain-repo - A bare name.\n"
    "\nA closing note that stays.\n"
)
TARGET = FRONT + HEADER + (
    "| `shop-site` | owned | The shop's site | [areas/shop/](../../areas/shop/) | shop-example.com | household |\n"
    "| `old-bus` | reference | Legacy bus |  |  |  |\n"
)


class Vault:
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = self.tmp / "vault"
        for folder in ("areas/billing", "areas/ledger", "areas/model", "areas/hub", "areas/shop",
                       "archive/projects/bus-exit", "archive/projects/hub-v1",
                       "resources/ideas/scraper-relaunch", "projects"):
            (self.vault / folder).mkdir(parents=True, exist_ok=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        (self.home / "vaults.json").write_text(json.dumps(
            [{"name": "household", "path": "x"}, {"name": "studio", "path": "y"}]), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, text, newline="\n"):
        f = self.vault / ".claude" / "rules" / "code-repos.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(text.replace("\n", newline).encode("utf-8"))
        return f

    def names(self, result):
        return [r["repo"] for r in result["repos"]]


class Reading(Vault, unittest.TestCase):
    def test_absent(self):
        self.assertEqual(list_repos(self.vault, self.home)["shape"], "absent")
        self.assertFalse(convert(self.vault)["changed"])

    def test_target_table(self):
        self.put(TARGET)
        out = list_repos(self.vault, self.home)
        self.assertEqual(out["shape"], "table")
        self.assertEqual(self.names(out), ["shop-site", "old-bus"])
        shop = out["repos"][0]
        self.assertEqual((shop["role"], shop["site"], shop["serves"], shop["home_path"]),
                         ("owned", "shop-example.com", "household", "areas/shop/"))
        self.assertEqual(out["problems"], [])

    def test_problems(self):
        self.put(FRONT + HEADER + (
            "| `a` | maybe | x |  |  |  |\n"
            "| `b` | owned | x |  | b.com |  |\n"
            "| `c` | owned | x |  | c.com | nowhere |\n"
            "| `a` | owned | again |  |  |  |\n"))
        problems = [(p["repo"], p["problem"].split(" ")[0]) for p in list_repos(self.vault, self.home)["problems"]]
        self.assertIn(("a", "role"), problems)
        self.assertIn(("b", "Serves"), problems)
        self.assertIn(("c", "serves"), problems)
        self.assertIn(("a", "listed"), problems)

    def test_no_registry_skips_the_vault_check(self):
        self.put(FRONT + HEADER + "| `c` | owned | x |  | c.com | nowhere |\n")
        empty = self.tmp / "empty"
        empty.mkdir()
        self.assertEqual(list_repos(self.vault, empty)["problems"], [])

    def test_legacy_list_reads_homes_from_text(self):
        self.put(HEADING_STYLE)
        out = list_repos(self.vault, self.home)
        self.assertEqual(out["shape"], "legacy")
        self.assertEqual(out["repos"][0]["home_path"], "areas/model/")

    def test_role_lines(self):
        self.assertEqual(role_of("**Reference-only** (past work):"), "reference")
        self.assertEqual(role_of("Reference-only, no vault area:"), "reference")
        self.assertEqual(role_of("## Other repos"), "other")
        self.assertEqual(role_of("**Active** (current work):"), "owned")
        self.assertIsNone(role_of("# Code repos"))
        self.assertIsNone(role_of("Repos under the code folder:"))
        self.assertIsNone(role_of("Kept for others to consult."))
        self.assertIsNone(role_of("- `x` - reference:"))

    def test_site_hints_skip_urls_and_code(self):
        self.assertEqual(site_hints("Site at shop.example.com, see https://ci.example.org/x"),
                         ["shop.example.com"])
        self.assertEqual(site_hints("Node.js and ASP.NET with a .NET 8 build"), [])

    def test_home_candidates_in_text_order(self):
        self.assertEqual(home_candidates("at `archive/projects/a/` then [b](../../areas/b/brief.md)"),
                         ["archive/projects/a/", "areas/b/"])
        self.assertEqual(home_candidates("`projects/x/sources/note.md`"), ["projects/x/"])
        self.assertEqual(home_candidates("`archive/projects/w-v{1,2}/`"), [])


class Converting(Vault, unittest.TestCase):
    def converted(self, text, newline="\n"):
        self.put(text, newline)
        out = convert(self.vault)
        self.assertTrue(out["changed"])
        return out

    def test_table_style_keeps_every_repo(self):
        out = self.converted(TABLE_STYLE)
        self.assertEqual(self.names(out), ["billing-api", "ledger", "old-bus"])
        self.assertEqual([r["role"] for r in out["repos"]], ["owned", "owned", "reference"])
        self.assertEqual(out["repos"][2]["home"], "[archive/projects/bus-exit/](../../archive/projects/bus-exit/)")
        self.assertIn("| `ledger` | owned | Batch jobs | [areas/ledger/](../../areas/ledger/) |  |  |", out["text"])
        self.assertEqual([d["text"] for d in out["dropped"]], ["Reference-only, no vault area:"])

    def test_heading_style_keeps_every_repo(self):
        out = self.converted(HEADING_STYLE)
        self.assertEqual([(r["repo"], r["role"]) for r in out["repos"]],
                         [("model", "owned"), ("portfolio-api", "owned"),
                          ("poc-queue", "reference"), ("engine", "other")])
        self.assertEqual(len(out["dropped"]), 3)
        self.assertNotIn("**Active**", out["text"])
        self.assertIn("Repos under the code folder:", out["text"])
        self.assertEqual([f["repo"] for f in out["to_fill"]], ["portfolio-api", "poc-queue", "engine"])

    def test_bullet_style(self):
        out = self.converted(BULLET_STYLE)
        self.assertEqual(self.names(out), ["shop-site", "scraper", "hub-site", "plain-repo"])
        shop, scraper, hub, _ = out["repos"]
        self.assertEqual(shop["what"], "React site for the shop at shop-example.com, see "
                         "https://ci.example.org/x. Built on the same pattern as the hub.")
        self.assertEqual(scraper["home_path"], "resources/ideas/scraper-relaunch/")
        self.assertEqual(hub["home_path"], "areas/hub/")
        hints = {f["repo"]: f.get("site_hint") for f in out["to_fill"]}
        self.assertEqual(hints["shop-site"], ["shop-example.com"])
        self.assertEqual(hints["hub-site"], ["example.com"])
        self.assertTrue(out["text"].rstrip().endswith("A closing note that stays."))

    def test_text_is_verbatim_and_pipes_escaped(self):
        out = self.converted(FRONT + "- `a` - Uses a | b split, **bold** kept.\n")
        self.assertIn("| `a` | owned | Uses a \\| b split, **bold** kept. |", out["text"])

    def test_dash_separators(self):
        out = self.converted(FRONT + "- `a` " + chr(0x2013) + " En.\n- b-repo " + chr(0x2014) + " Em.\n")
        self.assertEqual([(r["repo"], r["what"]) for r in out["repos"]], [("a", "En."), ("b-repo", "Em.")])

    def test_layout(self):
        out = self.converted(TABLE_STYLE)
        text = out["text"]
        self.assertTrue(text.startswith(FRONT))
        self.assertNotIn("\n\n\n", text)
        self.assertEqual(text.count("| Repo |"), 1)
        self.assertTrue(text.endswith("|\n"))

    def test_target_is_a_no_op(self):
        self.put(TARGET)
        out = convert(self.vault)
        self.assertFalse(out["changed"])
        self.assertIsNone(out["text"])

    def test_converted_file_reads_back_as_the_table(self):
        out = self.converted(TABLE_STYLE)
        self.put(out["text"])
        again = list_repos(self.vault, self.home)
        self.assertEqual(again["shape"], "table")
        self.assertEqual(self.names(again), self.names(out))
        self.assertFalse(convert(self.vault)["changed"])

    def test_half_converted_file_merges(self):
        out = self.converted(TARGET + "\n- `late` - Added as a bullet.\n")
        self.assertEqual(self.names(out), ["shop-site", "old-bus", "late"])
        self.assertEqual(out["repos"][0]["serves"], "household")

    def test_home_must_exist(self):
        out = self.converted(FRONT + "- `x` - Lives at `areas/missing/`.\n")
        self.assertEqual(out["repos"][0]["home"], "")
        self.assertEqual(out["to_fill"], [{"repo": "x", "home": True}])

    def test_older_table_extra_columns_join_what(self):
        out = self.converted(FRONT + "| Repo | Stack | Purpose |\n|---|---|---|\n| `x` | Python | Scraper |\n")
        self.assertEqual(out["repos"][0]["what"], "Scraper; Python")


class Edges(Vault, unittest.TestCase):
    def test_link_in_a_repo_cell(self):
        self.put(FRONT + HEADER + "| [shop-site](https://example.org/shop) | owned | x |  |  |  |\n")
        self.assertEqual(self.names(list_repos(self.vault, self.home)), ["shop-site"])

    def test_unclosed_frontmatter_is_body(self):
        repos, _, layout = parse("---\nnot closed\n- `a` - x\n")
        self.assertEqual([r["repo"] for r in repos], ["a"])
        self.assertEqual(layout[0], ("keep", "---"))

    def test_other_tables_and_empty_rows_are_kept(self):
        text = FRONT + ("| Host | Port |\n|---|---|\n| db | 5432 |\n\n"
                        "| Repo | What | Description | Notes |\n|---|---|---|---|\n"
                        "|  | orphan row |  |  |\n"
                        "| `a` | First | Second |  |\n")
        self.put(text)
        out = convert(self.vault)
        self.assertEqual(self.names(out), ["a"])
        self.assertEqual(out["repos"][0]["what"], "First")
        self.assertIn("| db | 5432 |", out["text"])
        self.assertIn("|  | orphan row |  |  |", out["text"])

    def test_list_keeps_an_older_tables_home(self):
        self.put(TABLE_STYLE)
        out = list_repos(self.vault, self.home)
        self.assertEqual(out["shape"], "legacy")
        self.assertEqual([r["home_path"] for r in out["repos"]],
                         ["areas/billing/", "areas/ledger/", "archive/projects/bus-exit/"])

    def test_empty_role_in_a_half_converted_file_becomes_owned(self):
        self.put(FRONT + HEADER + "| `a` |  | x |  |  |  |\n- `b` - y\n")
        self.assertEqual([r["role"] for r in convert(self.vault)["repos"]], ["owned", "owned"])

    def test_home_prefers_the_better_rank(self):
        self.put(FRONT + "- `a` - See `areas/hub/`, then `resources/ideas/scraper-relaunch/` and `docs/x/`.\n")
        self.assertEqual(convert(self.vault)["repos"][0]["home_path"], "areas/hub/")

    def test_site_hints_once_each_and_only_site_endings(self):
        self.assertEqual(site_hints("a.example.com, again a.example.com, and notes.md"),
                         ["a.example.com"])

    def test_no_blank_lines_around_the_table(self):
        self.put(FRONT + "Repos:\n- `a` - x\nAfter the list.\n")
        text = convert(self.vault)["text"]
        self.assertIn("Repos:\n\n| Repo |", text)
        self.assertIn("|\n\nAfter the list.\n", text)

    def test_write_keeps_lf_and_cleans_up_on_failure(self):
        f = self.put(BULLET_STYLE)
        out = convert(self.vault)
        with mock.patch("paraos_repos.os.replace", side_effect=OSError("held by sync")):
            with self.assertRaises(OSError):
                write(f, out["text"])
        self.assertEqual([p.name for p in f.parent.iterdir()], ["code-repos.md"])
        write(f, out["text"])
        self.assertNotIn(b"\r\n", f.read_bytes())


class Cli(Vault, unittest.TestCase):
    def run_main(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = main(list(args))
        return code, buf.getvalue()

    def test_bad_vault(self):
        self.assertEqual(self.run_main("list", "--vault", str(self.tmp / "nope"))[0], 2)

    def test_convert_dry_run_writes_nothing(self):
        f = self.put(BULLET_STYLE)
        code, out = self.run_main("convert", "--vault", str(self.vault))
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out)["written"])
        self.assertEqual(f.read_text(encoding="utf-8"), BULLET_STYLE)

    def test_write_keeps_crlf(self):
        f = self.put(HEADING_STYLE, "\r\n")
        code, out = self.run_main("convert", "--vault", str(self.vault), "--write")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["written"])
        data = f.read_bytes()
        self.assertIn(b"| Repo | Role |", data)
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
        self.assertEqual([p.name for p in f.parent.iterdir()], ["code-repos.md"])

    def test_list_prints_json(self):
        self.put(TARGET)
        code, out = self.run_main("list", "--vault", str(self.vault), "--paraos-home", str(self.home))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["shape"], "table")

    def test_parse_layout_kinds(self):
        _, shape, layout = parse(HEADING_STYLE)
        self.assertEqual(shape, "legacy")
        self.assertEqual([k for k, _ in layout].count("role"), 3)


if __name__ == "__main__":
    unittest.main()
