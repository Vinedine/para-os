"""Tests for paraos_clone.py: reading the para-os clone a vault is measured against, at a ref."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from paraos_clone import (  # noqa: E402
    addon_root, clone_files, clone_read, clone_ref, clone_session, master_template,
)


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fixture_git(root, *args):
    # No global excludes: a maintainer ignoring .claude/ would drop fixture files silently.
    # No auto maintenance: its detached run writes into .git while a test reads or deletes it.
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "core.autocrlf=false", "-c", "core.excludesFile=",
                    "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
                   cwd=root, check=True, capture_output=True)


def fixture_template(marker):
    lines = ["# Vault Conventions", "", f"<!-- para-os-template: {marker} -->",
             "**Type:** vault-type"]
    return "\n".join(lines + ["", "Guidance.", ""])


def write_bytes(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


DOSSIER = "addons/real-estate/.claude/rules/property-dossier.md"


def build_clone(root):
    """A throwaway para-os clone carrying the two addon layouts this repo's own history
    shipped, one tagged commit each, plus a working tree that differs from the last commit.

    - `layout-flavors`: the real-estate flavor under `flavors/real-estate/`, before addons
      had a folder of their own; the base template still on the legacy `2026.08`.
    - `layout-addons` (and the annotated `v2026.09.04`): everything under `addons/`, plus a
      leftover `flavors/legacy-kit/` that an `addons/` ref must never answer from.
    - Working tree: an unstaged base edit (2026.09.05); a rule file edit staged at
      2026.09.06 then rewritten on disk to 2026.09.07; an untracked file and an untracked
      folder; an ignored `__pycache__`; a folder holding only ignored files; a tracked file
      deleted.
    """
    fixture_git(root, "init", "-q")
    # Hermetic against the machine's own git config: a system autocrlf would rewrite the
    # CRLF fixture, and a global excludes file ignoring `.claude/` would drop the rule files.
    fixture_git(root, "config", "core.autocrlf", "false")
    fixture_git(root, "config", "core.excludesFile", str(root / ".git" / "no-excludes"))
    write(root, "CHANGELOG.md", "# Changelog\n\n## 2026.08.01\n\nThe first.\n")
    write(root, "base/CLAUDE.md.template", fixture_template("2026.08"))
    write(root, "flavors/real-estate/.claude/rules/property-dossier.md", "# Dossier 2026.08\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "flavors layout")
    fixture_git(root, "tag", "layout-flavors")

    (root / "addons").mkdir()
    fixture_git(root, "mv", "flavors/real-estate", "addons/real-estate")
    write(root, "base/CLAUDE.md.template", fixture_template("2026.09.04"))
    write(root, DOSSIER, "# Dossier 2026.09.04\n")
    write(root, "addons/sales/.claude/rules/deal-brief.md", "# Deal brief\n")
    write(root, "addons/sales/README.md", "# Sales\n")
    write(root, "addons/sales/Réunion notes.md", "# Réunion\n")
    write_bytes(root, "addons/sales/crlf.txt", b"caf\xe9\r\nline\r\n")
    write(root, "addons/sales-extra/README.md", "# Not sales\n")
    write(root, "flavors/legacy-kit/README.md", "# Left behind\n")
    write(root, ".gitignore", "__pycache__/\n")
    fixture_git(root, "add", "-A")
    fixture_git(root, "commit", "-q", "--no-verify", "-m", "addons layout")
    fixture_git(root, "tag", "layout-addons")
    fixture_git(root, "tag", "-a", "v2026.09.04", "-m", "revision")

    write(root, "base/CLAUDE.md.template", fixture_template("2026.09.05"))
    write(root, DOSSIER, "# Dossier 2026.09.06\n")
    fixture_git(root, "add", DOSSIER)
    write(root, DOSSIER, "# Dossier 2026.09.07\n")
    write(root, "addons/sales/untracked.md", "# New\n")
    write(root, "addons/northwind-kit/README.md", "# Northwind kit\n")
    write_bytes(root, "addons/sales/__pycache__/x.cpython-312.pyc", b"\0")
    write_bytes(root, "addons/stale/__pycache__/y.cpython-312.pyc", b"\0")
    (root / "addons/sales/README.md").unlink()


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class CloneCase(unittest.TestCase):
    """One fixture clone for every reader below: they only read it."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.clone = Path(cls._tmp.name)
        build_clone(cls.clone)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def rev(self, ref):
        return subprocess.run(["git", "rev-parse", ref], cwd=self.clone, check=True,
                              capture_output=True, text=True).stdout.strip()


class CloneRef(CloneCase):

    def test_a_ref_answers_with_its_full_commit(self):
        got = clone_ref(self.clone, "HEAD")
        self.assertEqual(got, {"ref": "HEAD", "commit": self.rev("HEAD")})
        self.assertEqual(len(got["commit"]), 40)

    def test_an_annotated_tag_answers_with_the_commit_it_tags(self):
        self.assertEqual(clone_ref(self.clone, "v2026.09.04")["commit"],
                         self.rev("layout-addons"))
        self.assertNotEqual(clone_ref(self.clone, "v2026.09.04")["commit"],
                            self.rev("v2026.09.04"))

    def test_a_ref_naming_nothing_is_none(self):
        self.assertIsNone(clone_ref(self.clone, "origin/main"))
        self.assertIsNone(clone_ref(self.clone, "--all"))
        self.assertIsNone(clone_ref(self.clone, ""))

    def test_a_folder_that_is_no_repository_is_none(self):
        with tempfile.TemporaryDirectory() as bare:
            self.assertIsNone(clone_ref(bare, "HEAD"))


class CloneRead(CloneCase):

    def test_a_file_reads_as_its_committed_bytes_not_a_decode(self):
        self.assertEqual(clone_read(self.clone, "HEAD", "addons/sales/crlf.txt"),
                         b"caf\xe9\r\nline\r\n")

    def test_an_older_ref_reads_the_path_it_carried(self):
        path = "flavors/real-estate/.claude/rules/property-dossier.md"
        self.assertIn(b"2026.08", clone_read(self.clone, "layout-flavors", path))
        self.assertIsNone(clone_read(self.clone, "HEAD", path))

    def test_a_folder_is_no_file(self):
        # `git show <ref>:<folder>` exits 0 with a listing that would read back as content.
        self.assertIsNone(clone_read(self.clone, "HEAD", "addons/sales"))
        self.assertIsNone(clone_read(self.clone, "HEAD", "addons/sales", worktree=True))

    def test_a_missing_path_or_ref_is_none(self):
        self.assertIsNone(clone_read(self.clone, "HEAD", "base/no-such-file.md"))
        self.assertIsNone(clone_read(self.clone, "no-such-ref", "base/CLAUDE.md.template"))

    def test_a_ref_read_never_sees_the_working_tree(self):
        self.assertIn(b"2026.09.04", clone_read(self.clone, "HEAD", "base/CLAUDE.md.template"))

    def test_worktree_reads_the_unstaged_edit(self):
        self.assertIn(b"2026.09.05", clone_read(self.clone, "HEAD", "base/CLAUDE.md.template",
                                                worktree=True))

    def test_worktree_reads_the_disk_never_the_index(self):
        path = DOSSIER
        staged = subprocess.run(["git", "show", f":{path}"], cwd=self.clone, check=True,
                                capture_output=True).stdout
        self.assertIn(b"2026.09.06", staged)   # the premise: the index holds another edit
        got = clone_read(self.clone, "HEAD", path, worktree=True)
        self.assertIn(b"2026.09.07", got)
        self.assertNotIn(b"2026.09.06", got)

    def test_a_path_is_read_the_same_whichever_way_it_is_spelled(self):
        want = clone_read(self.clone, "HEAD", "addons/sales/crlf.txt")
        self.assertEqual(clone_read(self.clone, "HEAD", "./addons\\sales/crlf.txt"), want)
        self.assertEqual(clone_read(self.clone, "HEAD", Path("addons/sales/crlf.txt")), want)

    def test_the_clone_root_is_no_file(self):
        for path in ("", ".", "/", "./"):
            self.assertIsNone(clone_read(self.clone, "HEAD", path), path)
            self.assertIsNone(clone_read(self.clone, "HEAD", path, worktree=True), path)

    def test_a_ref_opening_on_a_dash_is_never_passed_to_git_as_an_option(self):
        with mock.patch("paraos_clone.git_bytes") as git_bytes_spy:
            self.assertIsNone(clone_read(self.clone, "--output=x", "base/CLAUDE.md.template"))
            self.assertIsNone(clone_files(self.clone, "--all", "addons"))
            self.assertIsNone(addon_root(self.clone, "-h", "sales"))
        git_bytes_spy.assert_not_called()


class CloneFiles(CloneCase):

    SALES = ["addons/sales/.claude/rules/deal-brief.md", "addons/sales/README.md",
             "addons/sales/Réunion notes.md", "addons/sales/crlf.txt"]

    def test_a_prefix_lists_its_files_sorted_and_unquoted(self):
        self.assertEqual(clone_files(self.clone, "HEAD", "addons/sales"), self.SALES)

    def test_a_prefix_matches_whole_segments_only(self):
        got = clone_files(self.clone, "HEAD", "addons/sales/")
        self.assertEqual(got, self.SALES)
        self.assertNotIn("addons/sales-extra/README.md", got)

    def test_a_prefix_naming_one_file_answers_with_it(self):
        self.assertEqual(clone_files(self.clone, "HEAD", "base/CLAUDE.md.template"),
                         ["base/CLAUDE.md.template"])

    def test_an_empty_prefix_lists_the_whole_tree(self):
        got = clone_files(self.clone, "layout-flavors", "")
        self.assertEqual(got, ["CHANGELOG.md", "base/CLAUDE.md.template",
                               "flavors/real-estate/.claude/rules/property-dossier.md"])

    def test_nothing_there_is_empty_and_a_bad_ref_is_none(self):
        self.assertEqual(clone_files(self.clone, "layout-flavors", "addons"), [])
        self.assertIsNone(clone_files(self.clone, "no-such-ref", "addons"))

    def test_worktree_is_tracked_on_disk_plus_untracked_never_ignored(self):
        got = clone_files(self.clone, "HEAD", "addons/sales", worktree=True)
        self.assertEqual(got, ["addons/sales/.claude/rules/deal-brief.md",
                               "addons/sales/Réunion notes.md", "addons/sales/crlf.txt",
                               "addons/sales/untracked.md"])


class AddonRoot(CloneCase):

    def test_the_older_layout_kept_a_flavor_under_flavors(self):
        self.assertEqual(addon_root(self.clone, "layout-flavors", "real-estate"),
                         "flavors/real-estate")

    def test_today_every_addon_lives_under_addons(self):
        for name in ("real-estate", "sales"):
            self.assertEqual(addon_root(self.clone, "HEAD", name), f"addons/{name}")
        self.assertIsNone(addon_root(self.clone, "HEAD", "crm"))

    def test_a_ref_holding_addons_never_answers_from_an_older_folder(self):
        self.assertIsNone(addon_root(self.clone, "HEAD", "legacy-kit"))

    def test_a_module_at_a_ref_before_addons_resolves_to_nothing(self):
        self.assertIsNone(addon_root(self.clone, "layout-flavors", "sales"))

    def test_worktree_counts_an_untracked_folder_and_not_one_of_ignored_files(self):
        self.assertEqual(addon_root(self.clone, "HEAD", "northwind-kit", worktree=True),
                         "addons/northwind-kit")
        self.assertIsNone(addon_root(self.clone, "HEAD", "northwind-kit"))
        self.assertTrue((self.clone / "addons/stale/__pycache__").is_dir())
        self.assertIsNone(addon_root(self.clone, "HEAD", "stale", worktree=True))

    def test_a_name_that_is_a_path_is_no_addon(self):
        for name in ("", None, "..", "real-estate/skeleton", "..\\base"):
            self.assertIsNone(addon_root(self.clone, "HEAD", name))


class MasterTemplate(CloneCase):

    def test_every_vault_is_measured_against_base(self):
        self.assertEqual(master_template(self.clone, "HEAD"), {
            "path": "base/CLAUDE.md.template", "marker": "2026.09.04",
            "raw_marker": "2026.09.04", "source": "base"})

    def test_the_legacy_label_comes_back_raw_beside_the_revision_it_became(self):
        got = master_template(self.clone, "layout-flavors")
        self.assertEqual((got["raw_marker"], got["marker"]), ("2026.08", "2026.08.01"))

    def test_worktree_reads_the_templates_on_disk(self):
        got = master_template(self.clone, "HEAD", worktree=True)
        self.assertEqual((got["marker"], got["source"]), ("2026.09.05", "base"))

    def test_a_ref_holding_neither_template_has_no_source(self):
        got = master_template(self.clone, "no-such-ref")
        self.assertEqual((got["source"], got["marker"], got["raw_marker"]), (None, None, None))


class CloneSession(CloneCase):
    """Inside a session the readers answer from one git reader and one listing per ref,
    and must answer exactly as they do outside it."""

    READS = [("HEAD", "addons/sales/crlf.txt"), ("HEAD", "addons/sales/Réunion notes.md"),
             ("HEAD", "addons/sales"), ("HEAD", "base/no-such-file.md"),
             ("no-such-ref", "base/CLAUDE.md.template"), ("HEAD", "./addons\\sales/crlf.txt"),
             ("layout-flavors", "flavors/real-estate/.claude/rules/property-dossier.md"),
             ("v2026.09.04", "base/CLAUDE.md.template"), ("HEAD", ""), ("HEAD", "bad\npath")]
    LISTS = [("HEAD", "addons/sales"), ("HEAD", "addons/sales/"), ("HEAD", ""),
             ("HEAD", "base/CLAUDE.md.template"), ("layout-flavors", "addons"),
             ("no-such-ref", "addons"), ("layout-flavors", "")]

    def answers(self):
        return ([clone_read(self.clone, r, p) for r, p in self.READS],
                [clone_files(self.clone, r, p) for r, p in self.LISTS],
                [clone_ref(self.clone, r) for r in ("HEAD", "v2026.09.04", "origin/main")],
                [addon_root(self.clone, r, n) for r, n in
                 (("HEAD", "sales"), ("HEAD", "legacy-kit"), ("layout-flavors", "real-estate"))],
                master_template(self.clone, "HEAD"),
                clone_read(self.clone, "HEAD", "base/CLAUDE.md.template", worktree=True),
                clone_files(self.clone, "HEAD", "addons/sales", worktree=True))

    def spawned(self):
        """Every process started while the returned patch is active."""
        started = []
        real = subprocess.Popen

        def spy(*args, **kwargs):
            proc = real(*args, **kwargs)
            started.append(proc)
            return proc
        return started, mock.patch("paraos_clone.subprocess.Popen", side_effect=spy)

    def test_every_reader_answers_the_same_inside_a_session(self):
        outside = self.answers()
        with clone_session():
            inside = self.answers()
            again = self.answers()
        self.assertEqual(inside, outside)
        self.assertEqual(again, outside)

    def test_a_session_reads_one_ref_with_a_handful_of_git_processes(self):
        started, spy = self.spawned()
        with spy, clone_session():
            for _ in range(3):
                for path in ("addons/sales/crlf.txt", "addons/sales/README.md", "CHANGELOG.md"):
                    clone_read(self.clone, "HEAD", path)
                for prefix in ("addons/sales", "addons", "base", ""):
                    clone_files(self.clone, "HEAD", prefix)
                addon_root(self.clone, "HEAD", "sales")
                clone_ref(self.clone, "HEAD")
        # one batch reader, one tree listing, one ref resolution
        self.assertEqual(len(started), 3)

    def test_no_git_process_outlives_its_session(self):
        started, spy = self.spawned()
        with spy:
            with clone_session():
                clone_read(self.clone, "HEAD", "CHANGELOG.md")
                with tempfile.TemporaryDirectory() as other:
                    self.assertIsNone(clone_read(other, "HEAD", "CHANGELOG.md"))
                    self.assertIsNone(clone_files(other, "HEAD", ""))
        self.assertTrue(started)
        self.assertTrue(all(proc.poll() is not None for proc in started))

    def test_a_nested_session_leaves_the_outer_one_open(self):
        started, spy = self.spawned()
        with spy, clone_session():
            clone_read(self.clone, "HEAD", "CHANGELOG.md")
            with clone_session():
                clone_read(self.clone, "HEAD", "base/CLAUDE.md.template")
            self.assertEqual(clone_read(self.clone, "HEAD", "addons/sales/crlf.txt"),
                             b"caf\xe9\r\nline\r\n")
        self.assertEqual(len(started), 1)

    def test_worktree_reads_stay_live_inside_a_session(self):
        path = "addons/sales/untracked.md"
        before = (self.clone / path).read_bytes()
        with clone_session():
            self.assertEqual(clone_read(self.clone, "HEAD", path, worktree=True), before)
            write_bytes(self.clone, path, b"# Changed")
            try:
                self.assertEqual(clone_read(self.clone, "HEAD", path, worktree=True),
                                 b"# Changed")
            finally:
                write_bytes(self.clone, path, before)

    def test_a_reader_that_cannot_start_falls_back_to_one_call_per_read(self):
        with clone_session(), mock.patch("paraos_clone._open_batch", return_value=None):
            self.assertEqual(clone_read(self.clone, "HEAD", "addons/sales/crlf.txt"),
                             b"caf\xe9\r\nline\r\n")
            self.assertEqual(addon_root(self.clone, "HEAD", "sales"), "addons/sales")


if __name__ == "__main__":
    unittest.main(verbosity=1)
