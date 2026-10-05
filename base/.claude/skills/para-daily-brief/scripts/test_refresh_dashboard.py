#!/usr/bin/env python3
"""Tests for refresh_dashboard.py: the hook that keeps the dashboard current with no model.

    python3 test_refresh_dashboard.py
    py -3 test_refresh_dashboard.py

Standard library only. Every fixture is a throwaway vault in a temporary directory and the
page lands in a temporary PARAOS_HOME: nothing reads or writes a real vault or the
machine's own cache, and no background process is started (the spawn is mocked).
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import refresh_dashboard
from refresh_dashboard import cache_paths, find_vault, is_current, main, render_now
from test_brief_scan import build_vault, write

TODAY = date(2026, 9, 15)


class RefreshCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "vault"
        build_vault(self.root)
        write(self.root, "CLAUDE.md", "# BelFoot Vault Conventions\n")
        self.home = self.tmp / "home"
        patch = mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)

    def touch(self, rel, text):
        path = write(self.root, rel, text)
        st = path.stat()
        os.utime(path, (st.st_atime + 5, st.st_mtime + 5))


class ResolvingTheVault(RefreshCase):

    def test_the_root_is_found_from_a_folder_inside_it(self):
        self.assertEqual(find_vault(self.root / "projects" / "acme-website"), self.root)
        self.assertIsNone(find_vault(self.tmp))

    def test_outside_a_vault_the_hook_exits_quietly(self):
        with mock.patch.object(refresh_dashboard, "spawn_render") as spawn, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["--vault", str(self.tmp)]), 0)
        spawn.assert_not_called()
        self.assertEqual(out.getvalue(), "")
        self.assertFalse(self.home.exists())

    def test_render_outside_a_vault_is_an_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--render", "--vault", str(self.tmp)]), 2)


class Rendering(RefreshCase):

    def test_the_page_lands_in_the_cache_never_in_the_vault(self):
        result = render_now(self.root, today=TODAY)
        page, stamp, _ = cache_paths(self.root)
        self.assertEqual(Path(result["out"]), page)
        self.assertTrue(page.is_relative_to(self.home / "cache" / "daily-brief"))
        self.assertEqual(result["title"], "BelFoot Dashboard")
        html = page.read_text(encoding="utf-8")
        self.assertIn("from the scan alone", html)
        self.assertIn("come from the next <code>/para-daily-brief</code> run", html)
        self.assertTrue(stamp.is_file())
        self.assertEqual([], [p for p in self.root.rglob("*.html")])

    def test_the_cli_render_prints_where_the_page_went(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["--render", "--vault", str(self.root / "areas"),
                                   "--today", "2026-09-15"]), 0)
        self.assertEqual(json.loads(out.getvalue())["out"], cache_paths(self.root)[0].as_posix())


class Staleness(RefreshCase):

    def test_unchanged_vault_is_current_after_a_render(self):
        self.assertFalse(is_current(self.root))
        render_now(self.root, today=TODAY)
        self.assertTrue(is_current(self.root))

    def test_an_edited_action_file_a_new_triage_item_or_a_new_idea_makes_it_stale(self):
        render_now(self.root, today=TODAY)
        self.touch("projects/acme-website/actions.md", "# a\n\n- [ ] Rewritten\n")
        self.assertFalse(is_current(self.root))
        render_now(self.root, today=TODAY)
        self.touch("triage/20260915 Mail - New.md", "# New\n")
        self.assertFalse(is_current(self.root))
        render_now(self.root, today=TODAY)
        self.touch("resources/ideas/fresh/brief.md", "# Fresh\n")
        self.assertFalse(is_current(self.root))

    def test_a_deleted_entity_makes_it_stale(self):
        render_now(self.root, today=TODAY)
        for p in sorted((self.root / "projects" / "acme-website").rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        (self.root / "projects" / "acme-website").rmdir()
        self.assertFalse(is_current(self.root))

    def test_a_missing_or_corrupt_stamp_reads_as_stale(self):
        render_now(self.root, today=TODAY)
        _, stamp, _ = cache_paths(self.root)
        stamp.write_text("{not json", encoding="utf-8")
        self.assertFalse(is_current(self.root))


class TheHook(RefreshCase):

    def test_a_stale_vault_starts_one_detached_render_and_a_current_one_none(self):
        with mock.patch.object(refresh_dashboard.subprocess, "Popen") as popen:
            self.assertEqual(main(["--vault", str(self.root)]), 0)
        popen.assert_called_once()
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[-3:], ["--render", "--vault", str(self.root)])
        self.assertTrue(cmd[1].endswith("refresh_dashboard.py"))
        self.assertTrue(cache_paths(self.root)[2].is_file())  # the log the run writes to
        render_now(self.root, today=TODAY)
        with mock.patch.object(refresh_dashboard.subprocess, "Popen") as popen:
            self.assertEqual(main(["--vault", str(self.root)]), 0)
        popen.assert_not_called()

    def test_the_vault_comes_from_the_project_dir_or_the_working_directory(self):
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root / "areas")}), \
                mock.patch.object(refresh_dashboard, "spawn_render") as spawn:
            self.assertEqual(main([]), 0)
        spawn.assert_called_once_with(self.root)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(os, "getcwd", return_value=str(self.root / "projects")), \
                mock.patch.object(refresh_dashboard, "spawn_render") as spawn:
            self.assertEqual(main([]), 0)
        spawn.assert_called_once_with(self.root)

    def test_a_failure_in_the_hook_is_a_quiet_exit(self):
        with mock.patch.object(refresh_dashboard, "is_current", side_effect=OSError("boom")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["--vault", str(self.root)]), 0)
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
