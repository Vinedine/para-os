#!/usr/bin/env python3
"""Tests for paraos_connections.py, the connections registry, what the files already declare,
the drift check and the manifest block. Each one pins a rule of the script, which is the
specification.

    python3 test_paraos_connections.py
    py -3 test_paraos_connections.py

Standard library only. The para-os home and every vault are temporary directories.
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

import paraos_connections  # noqa: E402
from paraos_connections import (  # noqa: E402
    END, START, check, discover, entry_problems, key, list_all, load, mailbox_problems, main,
    manifest,
)

WORK_CLAUDE = """# Work

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| notes | sync-script | `resources/scripts/notes.js` (writes to `triage/`) | Always. |
| mail | connector: claude.ai Gmail | me@example.com | Work mail. |
| team | connector: `workspace-mcp` | Team@Example.org | Team mail. |
| calls | connector: recorder recording | me@example.com | Calls. |
| outbox | fetch-script | `mail.py fetch` | Old mail. |

## Agenda sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| cal | connector: claude.ai Google Calendar (its prefix rotates) | me@example.com | All. |
| cal2 | connector: google-calendar (claude.ai) | me@example.com | All. |
| paper | manual | meetings.md | All. |
"""

HOME_CLAUDE = """# Home

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| mail | connector: Claude.ai gmail | me@example.com | Bills. |
"""

GOOD = {"id": "notes", "kind": "script", "provider": "Notes app", "vaults": ["work"],
        "machine": None, "secret": "notes.json", "writes": "notes into triage/",
        "read_only": True, "path": "resources/scripts/notes.js"}


class Home:
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.work = self.vault("work", WORK_CLAUDE)
        self.house = self.vault("house", HOME_CLAUDE)
        (self.work / "resources" / "scripts").mkdir(parents=True)
        (self.work / "resources" / "scripts" / "notes.js").write_text("//", encoding="utf-8")
        (self.work / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "tracker": {"command": "npx", "args": ["tracker-mcp", "--token", "SECRET"],
                        "env": {"TOKEN": "SECRET"}},
            "wiki": {"type": "http", "url": "https://wiki.example.org/mcp"}}}), encoding="utf-8")
        self.registry([{"name": "work", "path": str(self.work)},
                       {"name": "house", "path": str(self.house)},
                       {"name": "away", "path": str(self.tmp / "away"), "machine": "laptop"}])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def vault(self, name, claude):
        root = self.tmp / name
        root.mkdir()
        (root / "CLAUDE.md").write_text(claude, encoding="utf-8")
        return root

    def registry(self, entries):
        (self.home / "vaults.json").write_text(json.dumps(entries), encoding="utf-8")

    def connections(self, conns, boxes=None):
        (self.home / "connections.json").write_text(
            json.dumps({"connections": conns, "mailboxes": boxes or []}), encoding="utf-8")

    def tasks(self, tasks):
        (self.home / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")

    def kinds(self, result):
        return sorted((f["kind"], f["connection"] or "") for f in result["findings"])


class Registry(Home, unittest.TestCase):
    def test_missing_is_empty(self):
        self.assertEqual(load(self.home), ({"connections": [], "mailboxes": []}, None))

    def test_unparseable_and_wrong_shape(self):
        (self.home / "connections.json").write_text("{", encoding="utf-8")
        self.assertIn("does not parse", load(self.home)[1])
        (self.home / "connections.json").write_text("[]", encoding="utf-8")
        self.assertIn("is not an object", load(self.home)[1])
        (self.home / "connections.json").write_text('{"connections": 1, "mailboxes": 2}', encoding="utf-8")
        self.assertEqual(load(self.home), ({"connections": [], "mailboxes": []}, None))

    def test_entry_shape(self):
        self.assertEqual(entry_problems(GOOD), [])
        self.assertEqual(entry_problems("x"), ["is not an object"])
        bad = {"id": " ", "kind": "robot", "vaults": "work", "machine": 1, "secret": "a/b.json",
               "read_only": "yes"}
        problems = " | ".join(entry_problems(bad))
        for phrase in ("has no id", "kind 'robot'", "has no provider", "vaults is neither",
                       "machine is neither", "secret is a path", "read_only"):
            self.assertIn(phrase, problems)
        self.assertIn("is a script with no path", entry_problems({**GOOD, "path": None}))
        self.assertEqual(entry_problems({**GOOD, "vaults": "*"}), [])

    def test_mailbox_shape(self):
        self.assertEqual(mailbox_problems({"address": "a@b.c", "owner": "A", "label": "B"}), [])
        self.assertEqual(mailbox_problems({"address": "nope"}), ["has no address"])
        self.assertEqual(mailbox_problems({"address": "a@b.c"}), ["has no owner", "has no label"])

    def test_key_folds_spellings(self):
        self.assertEqual(key("claude.ai Gmail"), key("Claude.ai gmail"))
        self.assertEqual(key("claude.ai Google Calendar (rotates)"), key("google-calendar (claude.ai)"))
        self.assertEqual(key("Booking.com (prices only)"), "booking.com")
        self.assertEqual(key(None), "")


class Discovery(Home, unittest.TestCase):
    def test_vault_files(self):
        uses, boxes = discover(self.home)
        got = sorted((u["kind"], u["name"], u["vault"], u["via"]) for u in uses)
        self.assertIn(("script", "resources/scripts/notes.js", "work", "triage"), got)
        self.assertIn(("script", "mail.py", "work", "triage"), got)
        self.assertIn(("connector", "claude_ai_Gmail", "work", "triage"), got)
        self.assertIn(("connector", "claude_ai_Gmail", "house", "triage"), got)
        self.assertIn(("connector", "workspace-mcp", "work", "triage"), got)
        self.assertIn(("connector", "recorder", "work", "triage"), got)
        self.assertEqual(sum(1 for g in got if g[3] == "agenda"), 2)
        self.assertIn(("mcp", "tracker", "work", "mcp.json"), got)
        self.assertNotIn("away", {u["vault"] for u in uses})
        self.assertEqual(sorted({(b["address"], b["vault"]) for b in boxes}),
                         [("me@example.com", "house"), ("me@example.com", "work"),
                          ("team@example.org", "work")])

    def test_mcp_json_gives_names_and_urls_only(self):
        servers = {u["name"]: u.get("url") for u in discover(self.home)[0] if u["via"] == "mcp.json"}
        self.assertEqual(servers, {"tracker": None, "wiki": "https://wiki.example.org/mcp"})
        self.assertNotIn("SECRET", json.dumps(list_all(self.home)))

    def test_unreadable_mcp_json(self):
        (self.work / ".mcp.json").write_text("{", encoding="utf-8")
        (self.house / ".mcp.json").write_text('{"mcpServers": []}', encoding="utf-8")
        self.assertFalse([u for u in discover(self.home)[0] if u["via"] == "mcp.json"])

    def test_task_via(self):
        self.tasks([{"id": "watch", "vaults": ["house"], "sources": [
            {"name": "Shop", "via": ["browser", "mcp:Shop API", "script:C:/tools/watch", "cli:gh", "fax:x"]}]},
            {"id": "all", "vaults": "*", "sources": [{"name": "X", "via": ["cli:az"]}]},
            "junk", {"id": "bad", "sources": ["junk"]}])
        got = sorted((u["kind"], u["name"], u["vault"]) for u in discover(self.home)[0]
                     if u["via"].startswith("task:"))
        self.assertEqual(got, [("browser", "browser", "house"), ("cli", "az", "*"),
                               ("cli", "gh", "house"), ("connector", "Shop API", "house"),
                               ("script", "C:/tools/watch", "house")])

    def test_registry_entries_that_are_not_here(self):
        self.registry([{"name": "work", "path": str(self.work), "machine": "laptop"},
                       {"name": "gone", "path": str(self.tmp / "nope")}, "junk"])
        self.assertEqual(discover(self.home), ([], []))


class Listing(Home, unittest.TestCase):
    def test_declared_and_discovered(self):
        self.connections([GOOD, {"id": "claude.ai Gmail", "kind": "connector", "provider": "Gmail",
                                 "vaults": ["house", "work"], "machine": None, "secret": None,
                                 "writes": None, "read_only": True},
                          {"id": "spare", "kind": "cli", "provider": "Cloud", "vaults": ["work"],
                           "read_only": False},
                          {"id": "broken"}],
                         [{"address": "Me@Example.com", "owner": "Me", "label": "Mine"}, {"address": "x"}])
        out = list_all(self.home)
        by_id = {c["id"]: c for c in out["connections"]}
        self.assertNotIn("broken", by_id)
        self.assertEqual(by_id["notes"]["used_by"], [{"vault": "work", "via": "triage"}])
        self.assertEqual(sorted(u["vault"] for u in by_id["claude.ai Gmail"]["used_by"]), ["house", "work"])
        self.assertEqual(by_id["spare"]["used_by"], [{"vault": "work", "via": "registry"}])
        self.assertFalse(by_id["wiki"]["declared"])
        self.assertEqual(by_id["wiki"]["url"], "https://wiki.example.org/mcp")
        self.assertEqual(out["mailboxes"], [{"address": "Me@Example.com", "owner": "Me",
                                             "label": "Mine", "vaults": ["house", "work"]}])

    def test_bare_script_name_matches_the_path(self):
        self.connections([{**GOOD, "id": "mail", "path": "resources/scripts/mail.py"}])
        mail = next(c for c in list_all(self.home)["connections"] if c["id"] == "mail")
        self.assertIn({"vault": "work", "via": "triage"}, mail["used_by"])

    def test_one_discovered_server_in_two_vaults(self):
        (self.house / ".mcp.json").write_text('{"mcpServers": {"tracker": {"command": "x"}}}', encoding="utf-8")
        tracker = next(c for c in list_all(self.home)["connections"] if c["id"] == "tracker")
        self.assertEqual(sorted(tracker["vaults"]), ["house", "work"])


class Checking(Home, unittest.TestCase):
    def test_no_registry_reports_every_use(self):
        out = check(self.home)
        self.assertFalse(out["exists"])
        kinds = self.kinds(out)
        self.assertIn(("undeclared", "claude_ai_Gmail"), kinds)
        self.assertEqual(sum(1 for k in kinds if k[1] == "claude_ai_Gmail"), 1)
        self.assertIn(("undeclared", "resources/scripts/notes.js"), kinds)
        self.assertEqual(sum(1 for k in kinds if k[0] == "undeclared" and "calendar" in k[1].lower()), 1)
        self.assertNotIn("tracker", [k[1] for k in kinds])
        self.assertIn(("unlabelled_mailbox", "team@example.org"), kinds)

    def test_unparseable_registry(self):
        (self.home / "connections.json").write_text("{", encoding="utf-8")
        self.assertIn(("invalid", ""), self.kinds(check(self.home)))

    def test_entry_findings(self):
        self.connections([GOOD, dict(GOOD), {"id": "x", "kind": "robot"},
                          {**GOOD, "id": "far", "vaults": ["work", "elsewhere"],
                           "path": "resources/scripts/far.py"},
                          {**GOOD, "id": "abs", "vaults": "*", "path": str(self.tmp / "nope.py")},
                          {**GOOD, "id": "abs-ok", "vaults": "*", "path": str(self.work / "CLAUDE.md")},
                          {**GOOD, "id": "every", "vaults": "*", "path": "resources/scripts/none.py"},
                          {**GOOD, "id": "remote", "machine": "laptop", "path": "resources/scripts/none.py"},
                          {**GOOD, "id": "awayonly", "vaults": ["away"], "path": "resources/scripts/none.py"}],
                         [{"address": "nope"}])
        kinds = self.kinds(check(self.home))
        self.assertIn(("invalid", "notes"), kinds)
        self.assertIn(("invalid", "x"), kinds)
        self.assertIn(("unknown_vault", "far"), kinds)
        self.assertIn(("missing_script", "far"), kinds)
        self.assertIn(("missing_script", "abs"), kinds)
        self.assertIn(("invalid", "nope"), kinds)
        for quiet in ("abs-ok", "every", "remote", "awayonly"):
            self.assertNotIn(("missing_script", quiet), kinds)

    def test_a_retired_script_still_listed(self):
        scripts = self.work / "resources" / "scripts"
        marker = "para-os-retired: 2026-01-15\n"
        (scripts / "old.py").write_text("#!/usr/bin/env python3\n# " + marker, encoding="utf-8")
        (scripts / "late.py").write_text("\n" * 10 + "# " + marker, encoding="utf-8")
        (scripts / "undated.py").write_text("# para-os-retired: soon\n", encoding="utf-8")
        (self.tmp / "abs.js").write_text("// " + marker, encoding="utf-8")
        self.connections([{**GOOD, "id": i, "path": f"resources/scripts/{i}.py"}
                          for i in ("old", "late", "undated")]
                         + [{**GOOD, "id": "abs", "vaults": "*", "path": str(self.tmp / "abs.js")}])
        result = check(self.home)
        kinds = self.kinds(result)
        self.assertIn(("retired_script", "old"), kinds)
        self.assertIn(("retired_script", "abs"), kinds)
        self.assertNotIn(("retired_script", "late"), kinds)
        self.assertNotIn(("retired_script", "undated"), kinds)
        self.assertIn("2026-01-15", next(f["detail"] for f in result["findings"]
                                         if f["connection"] == "old"))

    def test_a_complete_registry_is_clean(self):
        gmail = {"id": "claude.ai Gmail", "kind": "connector", "provider": "Gmail", "vaults": ["work", "house"],
                 "read_only": True}
        rest = [{"id": i, "kind": k, "provider": "x", "vaults": ["work"], "read_only": True}
                for i, k in (("workspace-mcp", "mcp"), ("recorder", "connector"),
                             ("claude.ai Google Calendar", "connector"))]
        mail = {**GOOD, "id": "mail", "path": "resources/scripts/mail.py"}
        (self.work / "resources" / "scripts" / "mail.py").write_text("#", encoding="utf-8")
        self.connections([GOOD, gmail, mail] + rest,
                         [{"address": a, "owner": "Me", "label": "L"} for a in ("me@example.com", "team@example.org")])
        self.assertEqual(check(self.home)["findings"], [])


class Manifest(Home, unittest.TestCase):
    def test_block_rows(self):
        self.connections([GOOD, {"id": "b", "kind": "browser", "provider": "Web", "vaults": "*",
                                 "read_only": False, "writes": "a | b"}])
        block = manifest(self.home)["block"]
        lines = block.splitlines()
        self.assertEqual((lines[0], lines[-1]), (START, END))
        self.assertIn("| `notes` | script | Notes app | work | `notes.json` | notes into triage/ | yes |", block)
        self.assertIn("| `b` | browser | Web | * |  | a \\| b | no |", block)
        self.assertIn("| `tracker` (from .mcp.json) | mcp |  | work |  |  |  |", block)
        self.assertLess(block.index("`notes`"), block.index("`b`"))

    def test_write_appends_then_replaces_only_the_block(self):
        readme = self.home / "README.md"
        readme.write_bytes(b"# Machine\r\n\r\nHand prose.\r\n")
        first = manifest(self.home, write_it=True)
        self.assertTrue(first["written"])
        text = readme.read_bytes().decode("utf-8")
        self.assertIn("Hand prose.\r\n\r\n## Connections\r\n\r\n" + START, text)
        self.assertEqual(text.count("\n"), text.count("\r\n"))
        readme.write_bytes(text.replace("## Connections", "## Connections\r\n\r\nKept.").encode("utf-8")
                           + b"\r\nAfter.\r\n")
        self.connections([GOOD])
        second = manifest(self.home, write_it=True)
        self.assertTrue(second["written"])
        text = readme.read_text(encoding="utf-8")
        self.assertIn("Kept.", text)
        self.assertIn("After.", text)
        self.assertEqual(text.count(START), 1)
        self.assertIn("`notes`", text)
        self.assertFalse(manifest(self.home, write_it=True)["written"])

    def test_no_readme_yet(self):
        out = manifest(self.home, write_it=True)
        self.assertTrue(out["written"])
        self.assertTrue((self.home / "README.md").read_text(encoding="utf-8").startswith("## Connections"))

    def test_failed_write_leaves_no_temp_file(self):
        with mock.patch("paraos_connections.os.replace", side_effect=OSError("held")):
            with self.assertRaises(OSError):
                manifest(self.home, write_it=True)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["vaults.json"])


class Cli(Home, unittest.TestCase):
    def run_main(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = main(["--paraos-home", str(self.home), *args])
        return code, json.loads(buf.getvalue())

    def test_commands(self):
        self.assertEqual(self.run_main("list")[1]["exists"], False)
        self.assertTrue(self.run_main("check")[1]["findings"])
        code, out = self.run_main("manifest")
        self.assertEqual((code, out["written"]), (0, False))
        self.assertFalse((self.home / "README.md").exists())

    def test_bad_argument(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            main(["nope"])
        self.assertEqual(ctx.exception.code, 2)

    def test_default_home(self):
        with mock.patch.dict("os.environ", {"PARAOS_HOME": str(self.home)}):
            self.assertEqual(Path(paraos_connections.list_all()["registry"]).parent, self.home)


if __name__ == "__main__":
    unittest.main()
