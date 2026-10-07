#!/usr/bin/env python3
"""Unit tests for mirror.py. Every vault and mirror is a temporary directory and git runs only
inside them; each mirror's global gitignore is a stand-in named in its own config, so the
machine's real one never applies.

Run from the repo root:
    py -3 integrations/vault-mirror/test_mirror.py
"""
import contextlib
import importlib.util
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mirror", HERE / "mirror.py")
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)

# A filename outside the Windows code page, cp1252.
NON_CP1252 = "Notes \u0141 \u4e2d.md"


def git(repo, *args):
    return subprocess.run(["git", "-c", "core.longpaths=true", "-C", str(repo), *args],
                          capture_output=True, check=True, text=True, encoding="utf-8").stdout


TEMPLATE = None  # one empty mirror repository, copied for each test: git is slow to start


def setUpModule():
    global TEMPLATE
    tmp = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(tmp.cleanup)
    root = Path(tmp.name).resolve()
    # Stands in for the operator's global gitignore, which keeps Claude's files out.
    ignore = root / "global-gitignore"
    ignore.write_text("CLAUDE.md\nCLAUDE.local.md\n.claude/\n.mcp.json\n")
    TEMPLATE = root / "mirror"
    TEMPLATE.mkdir()
    git(TEMPLATE, "init", "-q")
    for key, value in (("user.name", "t"), ("user.email", "t@example.invalid"),
                       ("core.autocrlf", "false"), ("core.excludesFile", str(ignore)),
                       # No background gc or maintenance: it writes into .git/objects after
                       # a commit returns, under a test that asserts nothing changed.
                       ("gc.auto", "0"), ("maintenance.auto", "false")):
        git(TEMPLATE, "config", key, value)


def make_mirror(path):
    shutil.copytree(TEMPLATE, path)


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def tree(root):
    """{relative path: bytes} of every file under root, .git included."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def tracked(repo):
    return set(git(repo, "ls-files", "-z").split("\0")) - {""}


class MirrorCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.mirror = self.root / "mirror"
        make_mirror(self.mirror)

    def run_mirror(self, *argv):
        out = io.StringIO()
        with mock.patch.object(mirror, "VAULT", self.vault), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            mirror.main(["--mirror", str(self.mirror), *argv])
        return out.getvalue()

    def refused(self, *argv):
        with self.assertRaises(SystemExit) as stop:
            self.run_mirror(*argv)
        return str(stop.exception.code)

    def exclude(self, *patterns):
        write(self.mirror / ".git" / "info" / "exclude", "\n".join(patterns) + "\n")

    def commit_in_mirror(self, files):
        for rel, text in files.items():
            write(self.mirror / rel, text)
        git(self.mirror, "add", "-A")
        git(self.mirror, "commit", "-q", "-m", "earlier")

    def head(self):
        return git(self.mirror, "rev-parse", "HEAD").strip()

    def message(self):
        return git(self.mirror, "log", "-1", "--format=%B")


class OneWayCopy(MirrorCase):
    def test_a_first_run_copies_and_commits_the_vault(self):
        write(self.vault / "notes" / "a.md", "alpha")
        write(self.vault / "b.txt", "beta")
        out = self.run_mirror()
        self.assertEqual((self.mirror / "notes" / "a.md").read_text(), "alpha")
        self.assertEqual(tracked(self.mirror), {"notes/a.md", "b.txt"})
        self.assertIn("committed", out)
        self.assertTrue(self.message().startswith("Mirror live vault: 2 added, 0 modified, 0 deleted"))

    def test_changed_and_removed_files_follow_the_vault(self):
        self.commit_in_mirror({"keep.md": "old", "gone.md": "bye", "same.md": "s"})
        write(self.vault / "keep.md", "new text")
        write(self.vault / "same.md", "s")
        self.run_mirror()
        self.assertEqual((self.mirror / "keep.md").read_text(), "new text")
        self.assertFalse((self.mirror / "gone.md").exists())
        self.assertEqual(tracked(self.mirror), {"keep.md", "same.md"})
        self.assertIn("0 added, 1 modified, 1 deleted", self.message())

    def test_the_vault_is_never_written(self):
        self.commit_in_mirror({"only-in-mirror.md": "m", "shared.md": "older"})
        write(self.vault / "shared.md", "newer")
        before = tree(self.vault)
        self.run_mirror()
        self.assertEqual(tree(self.vault), before)

    def test_a_folder_emptied_in_the_vault_is_pruned_from_the_mirror(self):
        self.commit_in_mirror({"projects/done/brief.md": "b"})
        (self.vault / "projects").mkdir()
        self.run_mirror()
        self.assertFalse((self.mirror / "projects").exists())

    def test_a_touched_file_with_the_same_bytes_is_not_a_change(self):
        write(self.vault / "a.md", "same")
        self.run_mirror()
        head = self.head()
        later = (self.vault / "a.md").stat().st_mtime + 3600
        os.utime(self.vault / "a.md", (later, later))
        out = self.run_mirror()
        self.assertIn("0 added, 0 modified, 0 deleted", out)
        self.assertIn("Nothing to commit", out)
        self.assertEqual(self.head(), head)

    def test_an_own_subject_replaces_the_generated_one(self):
        write(self.vault / "a.md")
        self.run_mirror("-m", "Archive the old project")
        msg = self.message()
        self.assertTrue(msg.startswith("Archive the old project\n\n1 added, 0 modified, 0 deleted."))
        self.assertIn("+ a.md", msg)

    def test_a_git_folder_in_the_vault_is_never_copied_and_the_mirrors_is_never_touched(self):
        write(self.vault / ".git" / "HEAD", "ref: refs/heads/vault-own\n")
        write(self.vault / "code" / ".git", "gitdir: elsewhere\n")
        write(self.vault / "a.md")
        before = (self.mirror / ".git" / "HEAD").read_bytes()
        self.run_mirror()
        self.assertEqual((self.mirror / ".git" / "HEAD").read_bytes(), before)
        self.assertFalse((self.mirror / "code" / ".git").exists())
        self.assertEqual(tracked(self.mirror), {"a.md"})


class Refusals(MirrorCase):
    def test_a_dirty_mirror_is_refused_and_left_as_it_was(self):
        self.commit_in_mirror({"a.md": "committed"})
        write(self.mirror / "a.md", "edited in the mirror")
        write(self.vault / "a.md", "vault")
        head = self.head()
        self.assertIn("--force", self.refused())
        self.assertEqual((self.mirror / "a.md").read_text(), "edited in the mirror")
        self.assertEqual(self.head(), head)

    def test_an_untracked_file_in_the_mirror_is_dirty_too(self):
        self.commit_in_mirror({"a.md": "committed"})
        write(self.mirror / "stray.md", "dropped here by hand")
        self.refused()
        self.assertTrue((self.mirror / "stray.md").exists())

    def test_force_overwrites_the_edits_and_commits(self):
        self.commit_in_mirror({"a.md": "committed"})
        write(self.mirror / "a.md", "edited in the mirror")
        write(self.vault / "a.md", "vault")
        out = self.run_mirror("--force")
        self.assertIn("about to be overwritten", out)
        self.assertEqual((self.mirror / "a.md").read_text(), "vault")
        self.assertEqual(git(self.mirror, "status", "--porcelain"), "")

    def test_a_mirror_overlapping_the_vault_is_refused(self):
        inside = self.vault / "history"
        make_mirror(inside)
        outer = self.root
        (outer / ".git").mkdir()
        write(self.vault / "a.md")
        for target in (self.vault, inside, outer):
            with self.subTest(mirror=target.name):
                with self.assertRaises(SystemExit) as stop, \
                        mock.patch.object(mirror, "VAULT", self.vault):
                    mirror.main(["--mirror", str(target)])
                self.assertIn("overlap", str(stop.exception.code))
        self.assertTrue((self.vault / "a.md").exists())

    def test_a_folder_that_is_not_a_repository_is_refused(self):
        plain = self.root / "plain"
        plain.mkdir()
        with self.assertRaises(SystemExit) as stop, mock.patch.object(mirror, "VAULT", self.vault):
            mirror.main(["--mirror", str(plain)])
        self.assertIn("Not a git repository", str(stop.exception.code))

    def test_no_mirror_named_anywhere_stops(self):
        with mock.patch.dict(os.environ, {"PARAOS_VAULT_MIRROR": ""}), \
                self.assertRaises(SystemExit) as stop:
            mirror.main([])
        self.assertIn("PARAOS_VAULT_MIRROR", str(stop.exception.code))

    def test_the_environment_names_the_mirror(self):
        write(self.vault / "a.md")
        with mock.patch.dict(os.environ, {"PARAOS_VAULT_MIRROR": str(self.mirror)}), \
                mock.patch.object(mirror, "VAULT", self.vault), \
                contextlib.redirect_stdout(io.StringIO()):
            mirror.main([])
        self.assertEqual(tracked(self.mirror), {"a.md"})


class DryRun(MirrorCase):
    def test_a_dry_run_writes_nothing(self):
        self.commit_in_mirror({"gone.md": "bye", "a.md": "old"})
        # A timestamp that moved under an unchanged file is what tempts git status to rewrite
        # its index on the way through.
        later = (self.mirror / "gone.md").stat().st_mtime + 60
        os.utime(self.mirror / "gone.md", (later, later))
        write(self.vault / "a.md", "changed")
        write(self.vault / "new" / "b.md", "b")
        before_mirror, before_vault = tree(self.mirror), tree(self.vault)
        out = self.run_mirror("--dry-run")
        self.assertEqual(tree(self.mirror), before_mirror)
        self.assertEqual(tree(self.vault), before_vault)
        self.assertIn("+ new/b.md", out)
        self.assertIn("~ a.md", out)
        self.assertIn("- gone.md", out)
        self.assertIn("dry run, nothing written: 1 added, 1 modified, 1 deleted", out)

    def test_a_dry_run_on_a_dirty_mirror_reports_and_carries_on(self):
        self.commit_in_mirror({"a.md": "committed"})
        write(self.mirror / "a.md", "edited in the mirror")
        before = tree(self.mirror)
        out = self.run_mirror("--dry-run")
        self.assertIn("would refuse", out)
        self.assertEqual(tree(self.mirror), before)


class IgnoreRules(MirrorCase):
    def test_every_file_is_copied_whatever_an_ignore_rule_says(self):
        self.exclude("archive/", "*.log", "__pycache__/")
        files = ["CLAUDE.md", ".mcp.json", "archive/old.pdf", "debug.log", "__pycache__/m.pyc",
                 "resources/logs/sessions/s.jsonl", "desktop.ini", ".gitignore", "secret.txt"]
        write(self.vault / ".gitignore", "secret.txt\n")
        for rel in files:
            if rel != ".gitignore":
                write(self.vault / rel)
        self.run_mirror()
        for rel in files:
            self.assertTrue((self.mirror / rel).is_file(), rel)

    def test_a_path_in_info_exclude_is_copied_but_not_committed(self):
        self.exclude("archive/")
        write(self.vault / "archive" / "scans" / "big.pdf", "bulk")
        write(self.vault / "notes.md")
        self.run_mirror()
        self.assertTrue((self.mirror / "archive" / "scans" / "big.pdf").is_file())
        self.assertEqual(tracked(self.mirror), {"notes.md"})
        self.assertNotIn("archive", self.message())
        self.assertEqual(git(self.mirror, "status", "--porcelain"), "")

    def test_only_excluded_paths_changed_makes_no_commit(self):
        self.exclude("archive/")
        write(self.vault / "notes.md")
        self.run_mirror()
        head = self.head()
        write(self.vault / "archive" / "late.pdf")
        out = self.run_mirror()
        self.assertIn("copied: 1 added", out)
        self.assertEqual(self.head(), head)

    def test_a_global_gitignore_keeps_claude_files_out_without_the_reinclude(self):
        write(self.vault / "CLAUDE.md")
        write(self.vault / "notes.md")
        self.run_mirror()
        self.assertEqual(tracked(self.mirror), {"notes.md"})

    def test_the_shipped_exclude_commits_claude_md_past_a_global_gitignore(self):
        shutil.copyfile(HERE / "info-exclude.template", self.mirror / ".git" / "info" / "exclude")
        for rel in ("CLAUDE.md", "CLAUDE.local.md", ".claude/settings.json",
                    ".claude/skills/x/SKILL.md", ".mcp.json", "resources/logs/sessions/s.jsonl",
                    "resources/scripts/__pycache__/m.pyc", "desktop.ini", "archive/a.md"):
            write(self.vault / rel)
        self.run_mirror()
        self.assertEqual(tracked(self.mirror),
                         {"CLAUDE.md", "CLAUDE.local.md", ".claude/settings.json",
                          ".claude/skills/x/SKILL.md", "archive/a.md"})
        self.assertTrue((self.mirror / ".mcp.json").is_file())


class Unreadable(MirrorCase):
    POINTERS = ["Budget.gsheet", "plans/Plan.gdoc", "Deck.GSLIDES",
                ".849C9593-D756-4E56-8D6E-42412F2A707B", "~$Report.docx"]

    def test_pointer_lock_and_marker_files_are_skipped(self):
        for rel in self.POINTERS + ["Report.docx", "notes.gdoc.md"]:
            write(self.vault / rel)
        self.run_mirror()
        for rel in self.POINTERS:
            self.assertFalse((self.mirror / rel).exists(), rel)
        self.assertEqual(tracked(self.mirror), {"Report.docx", "notes.gdoc.md"})

    def test_a_pointer_the_history_holds_stays_as_it_was(self):
        self.commit_in_mirror({"Budget.gsheet": "{\"doc_id\": \"x\"}"})
        write(self.vault / "a.md")
        self.run_mirror()
        self.assertIn("Budget.gsheet", tracked(self.mirror))
        self.assertTrue((self.mirror / "Budget.gsheet").is_file())


class LongPaths(MirrorCase):
    def test_long_path_is_unchanged_off_windows(self):
        with mock.patch.object(mirror.os, "name", "posix"):
            self.assertIs(mirror.long_path(self.root), self.root)

    # Not by patching os.name: before Python 3.12, pathlib picks WindowsPath from it and
    # refuses to build one anywhere else.
    @unittest.skipUnless(os.name == "nt", "the extended-length prefix is Windows' own")
    def test_long_path_is_extended_on_windows(self):
        forms = [str(mirror.long_path(Path(p))) for p in
                 ("C:\\v\\a.md", "\\\\?\\C:\\v\\a.md", "\\\\server\\share\\v")]
        self.assertEqual(forms, ["\\\\?\\C:\\v\\a.md", "\\\\?\\C:\\v\\a.md",
                                 "\\\\?\\UNC\\server\\share\\v"])

    @unittest.skipUnless(os.name == "nt", "the 260-character limit is Windows' own")
    def test_a_path_over_260_characters_is_copied_and_committed(self):
        deep = Path(*["folder-with-a-long-name-%02d" % i for i in range(10)], "file.md")
        rel = deep.as_posix()
        self.assertGreater(len(str(self.vault / deep)), 260)
        self.assertGreater(len(str(self.mirror / deep)), 260)
        self.addCleanup(shutil.rmtree, mirror.long_path(self.vault / "folder-with-a-long-name-00"))
        self.addCleanup(shutil.rmtree, mirror.long_path(self.mirror / "folder-with-a-long-name-00"),
                        ignore_errors=True)
        write(mirror.long_path(self.vault / deep), "deep")
        self.run_mirror()
        self.assertEqual(mirror.long_path(self.mirror / deep).read_text(), "deep")
        self.assertEqual(tracked(self.mirror), {rel})


class Failures(MirrorCase):
    def test_a_folder_that_cannot_be_listed_stops_rather_than_reading_as_empty(self):
        with self.assertRaises(OSError):
            mirror.relative_files(self.vault / "missing")

    def test_a_read_only_file_is_still_removed(self):
        target = self.mirror / "locked.md"
        write(target)
        real_unlink = Path.unlink
        refusals = []

        def unlink(path, *args, **kwargs):
            # The first attempt fails the way Windows fails a read-only file.
            if not refusals:
                refusals.append(path)
                raise PermissionError(13, "Access is denied", str(path))
            return real_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", unlink):
            mirror.remove(target)
        self.assertEqual(refusals, [target])
        self.assertFalse(target.exists())

    def test_a_read_only_copy_in_the_mirror_is_still_overwritten(self):
        self.commit_in_mirror({"shared.md": "old"})
        write(self.vault / "shared.md", "edited by someone else")
        for path in (self.vault / "shared.md", self.mirror / "shared.md"):
            os.chmod(path, stat.S_IREAD)
        self.run_mirror()
        self.assertEqual((self.mirror / "shared.md").read_text(), "edited by someone else")
        self.assertIn("~ shared.md", self.message())

    def test_a_file_the_vault_will_not_let_be_read_still_stops_the_run(self):
        with mock.patch.object(mirror.shutil, "copy2", side_effect=PermissionError(13, "denied")), \
                self.assertRaises(PermissionError):
            mirror.copy(self.vault / "a.md", self.mirror / "a.md")

    def test_a_git_failure_stops_the_run_with_gits_message(self):
        with self.assertRaises(SystemExit) as stop:
            mirror.git(self.mirror, "rev-parse", "--verify", "no-such-ref")
        self.assertIn("git rev-parse --verify no-such-ref failed", str(stop.exception.code))


class Encoding(MirrorCase):
    """Run as installed, in a child process with the console's own encoding: the failure this
    guards against is a UnicodeEncodeError at the console and at git's stdin."""

    def run_installed(self, *args, python=()):
        script = self.vault / "resources" / "scripts" / "vault-mirror" / "mirror.py"
        if not script.exists():
            script.parent.mkdir(parents=True)
            shutil.copyfile(HERE / "mirror.py", script)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
        env.update(PYTHONIOENCODING="cp1252", PARAOS_VAULT_MIRROR=str(self.mirror))
        r = subprocess.run([sys.executable, *python, str(script), *args], env=env,
                           capture_output=True)
        out = (r.stdout + r.stderr).decode("utf-8")
        self.assertEqual(r.returncode, 0, out)
        return out

    def test_a_non_cp1252_filename_reaches_the_output_and_the_commit_message(self):
        write(self.vault / NON_CP1252, "text")
        self.assertIn(f"+ {NON_CP1252}", self.run_installed("--dry-run"))
        self.run_installed()
        self.assertIn(f"+ {NON_CP1252}", self.message())
        self.assertIn(NON_CP1252, tracked(self.mirror))

    def test_it_runs_under_utf8_mode_too(self):
        write(self.vault / NON_CP1252, "text")
        self.run_installed(python=("-X", "utf8"))
        self.assertIn(f"+ {NON_CP1252}", self.message())


class PureFunctions(unittest.TestCase):
    def test_the_body_is_capped(self):
        added = [f"f{i}.md" for i in range(45)]
        msg = mirror.build_message(added, [], ["old.md"])
        self.assertTrue(msg.startswith("Mirror live vault: 45 added, 0 modified, 1 deleted\n\n"))
        self.assertIn("+ f39.md\n... and 6 more\n", msg)
        self.assertNotIn("+ f40.md", msg)

    def test_skipped_names(self):
        for name in ("a.gdoc", "B.GSHEET", "c.gjam", "~$d.xlsx", ".git",
                     ".849c9593-d756-4e56-8d6e-42412f2a707b"):
            self.assertTrue(mirror.skipped(name), name)
        for name in ("a.gdoc.md", "gdoc", ".gitignore", ".github", "x~$.md", ".claude"):
            self.assertFalse(mirror.skipped(name), name)


if __name__ == "__main__":
    unittest.main()
