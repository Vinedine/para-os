#!/usr/bin/env python3
"""Tests for paraos_vault.py, the shared vault library.

    python3 test_paraos_vault.py
    py -3 test_paraos_vault.py

Standard library only, so a vault that runs the skills can run their tests. Every fixture
is a throwaway vault in a temporary directory: nothing reads or writes a real vault, and
nothing calls a model.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from paraos_vault import (
    abspath, action_files, add_months, addon_root, arrived, cadence_days, changed, contact_names,
    changelog_entries, clone_files, clone_read, clone_ref, clone_session, closed_tasks,
    dangling_links,
    declarations, duplicates, entries_between, extract_links, field_ci, file_dates,
    find_clone, first_link, git, git_blame_line_date, git_bytes, git_last_commit_date, git_modified,
    git_untracked, hashes, header_fields,
    inbound_references, ingest_ledger, ingest_logs, integration_markers,
    contact_card_level, headline, lifecycles, live_lines, log_instant, main,
    master_template, misplaced_checkboxes, next_occurrence, open_items,
    match_encoding, move_plan, norm, normalised, note_name_parts, notice_date, open_tasks,
    over_grown_briefs,
    parse_markers, register_rows, registered_vault, registry,
    registry_holding, rel_posix, resolve_entity, resolve_link, scope_of, snapshot, split_lines,
    stage_line, stage_of, strip_code, table_cells, template_marker, thread_hash, triage_items, triage_sources, vault_root,
    watermark, written_under,
)

SCRIPT = Path(__file__).resolve().parent / "paraos_vault.py"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class VaultCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def aliased_vault(self):
        """(vault, link): a real vault folder and a symlink to it, the two spellings macOS's
        /var and a Windows short name give one folder. Skips where no symlink can be made
        (Windows without Developer Mode)."""
        vault = self.root / "vault"
        vault.mkdir()
        link = self.root / "vault-link"
        try:
            os.symlink(vault, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("this platform cannot create a symlink here")
        return vault.resolve(), link


class Names(VaultCase):

    def test_norm_folds_every_separator(self):
        self.assertEqual(norm("Para OS 2026.09.04"), "para-os-2026-09-04")
        self.assertEqual(norm("para_os 2026.09.04"), "para-os-2026-09-04")
        self.assertEqual(norm("  Acme   Website  "), "acme-website")

    def test_dots_in_a_name_resolve_to_the_folder(self):
        # A release-style name reaches its folder. Folding spaces alone left it unresolved.
        write(self.root, "projects/para-os-2026-09-04/actions.md", "# x\n\n- [ ] one\n")
        got = resolve_entity(self.root, "Para OS 2026.09.04")
        self.assertEqual(got["status"], "resolved")
        self.assertEqual(got["match"]["path"], "projects/para-os-2026-09-04")

    def test_exact_match_wins_over_a_longer_neighbour(self):
        write(self.root, "projects/acme-website/actions.md", "# a\n")
        write(self.root, "projects/acme-website-v2/actions.md", "# b\n")
        self.assertEqual(resolve_entity(self.root, "acme-website")["match"]["path"],
                         "projects/acme-website")

    def test_two_partial_matches_are_never_picked_between(self):
        write(self.root, "projects/acme-website-v2/actions.md", "# b\n")
        write(self.root, "projects/acme-website-v3/actions.md", "# c\n")
        got = resolve_entity(self.root, "acme")
        self.assertEqual(got["status"], "ambiguous")
        self.assertIsNone(got["match"])
        self.assertEqual(len(got["candidates"]), 2)

    def test_an_archived_entity_is_reported_where_it_lives(self):
        write(self.root, "archive/projects/para-os-2026-09-03/brief.md", "# shipped\n")
        got = resolve_entity(self.root, "para os 2026.09.03")
        self.assertEqual(got["status"], "elsewhere")
        self.assertEqual(got["elsewhere"][0],
                         {"kind": "archived", "path": "archive/projects/para-os-2026-09-03"})

    def test_an_idea_is_reported_as_an_idea(self):
        write(self.root, "resources/ideas/northwind-installers/brief.md", "# idea\n")
        got = resolve_entity(self.root, "Northwind Installers")
        self.assertEqual(got["elsewhere"][0]["kind"], "idea")

    def test_a_name_matching_nothing_offers_the_nearest(self):
        write(self.root, "projects/acme-website/actions.md", "# a\n")
        got = resolve_entity(self.root, "acme-webshop")
        self.assertEqual(got["status"], "unresolved")
        self.assertEqual(got["nearest"], ["projects/acme-website"])

    def test_a_stray_file_in_a_bucket_is_never_an_entity(self):
        write(self.root, "projects/acme.md", "# a loose note, not a project\n")
        write(self.root, "projects/acme-website/actions.md", "# a\n")
        got = resolve_entity(self.root, "acme")
        self.assertEqual(got["status"], "resolved")
        self.assertEqual(got["match"]["path"], "projects/acme-website")


class IdeasInResolution(VaultCase):

    def test_an_idea_resolves_exactly_when_ideas_are_a_bucket(self):
        write(self.root, "resources/ideas/northwind-installers/brief.md", "# idea\n")
        got = resolve_entity(self.root, "Northwind Installers",
                             buckets=("projects", "resources/ideas", "areas"))
        self.assertEqual(got["status"], "resolved")
        self.assertEqual(got["match"], {"bucket": "I", "label": "northwind-installers",
                                        "path": "resources/ideas/northwind-installers",
                                        "key": "northwind-installers"})

    def test_default_buckets_are_unchanged_and_still_report_an_idea_as_elsewhere(self):
        write(self.root, "resources/ideas/northwind-installers/brief.md", "# idea\n")
        got = resolve_entity(self.root, "Northwind Installers")
        self.assertEqual(got["status"], "elsewhere")
        self.assertEqual(got["elsewhere"][0]["kind"], "idea")

    def test_elsewhere_is_not_searched_a_second_time_once_ideas_are_a_bucket(self):
        write(self.root, "resources/ideas/unrelated-thing/brief.md", "# idea\n")
        got = resolve_entity(self.root, "nonexistent-query",
                             buckets=("projects", "resources/ideas", "areas"))
        self.assertEqual(got["status"], "unresolved")
        self.assertEqual(got["elsewhere"], [])

    def test_a_partial_match_works_across_all_three_buckets(self):
        write(self.root, "resources/ideas/acme-website-v2/brief.md", "# idea\n")
        write(self.root, "projects/acme-website-v3/actions.md", "# a\n")
        got = resolve_entity(self.root, "acme",
                             buckets=("projects", "resources/ideas", "areas"))
        self.assertEqual(got["status"], "ambiguous")
        self.assertEqual(set(got["candidates"]),
                         {"resources/ideas/acme-website-v2", "projects/acme-website-v3"})


class Reading(VaultCase):

    def test_a_fenced_line_is_never_live(self):
        lines = ["- [ ] Real", "```", "- [ ] Sample", "```", "- [ ] Also real"]
        self.assertEqual([t for _, t in live_lines(lines)],
                         ["- [ ] Real", "- [ ] Also real"])

    def test_a_tilde_fence_closes_only_on_its_own_token(self):
        lines = ["~~~", "- [ ] Inside", "```", "- [ ] Still inside", "~~~", "- [ ] Out"]
        self.assertEqual([t for _, t in live_lines(lines)], ["- [ ] Out"])

    def test_a_four_backtick_fence_is_not_closed_by_a_three_backtick_line(self):
        lines = ["````", "```", "- [ ] Sample inside", "```", "````", "- [ ] Real"]
        self.assertEqual([t for _, t in live_lines(lines)], ["- [ ] Real"])

    def test_a_line_opening_on_inline_triple_backticks_is_not_a_fence(self):
        lines = ["```npm ci``` fails on CI", "- [ ] Fix the build", "- [ ] Tell the team"]
        self.assertEqual([t for _, t in live_lines(lines)], lines)

    def test_a_fence_line_with_an_info_string_does_not_close_an_open_fence(self):
        # CommonMark: a closing fence carries nothing but whitespace after its run.
        lines = ["```", "```python", "- [ ] Sample inside", "```", "- [ ] Real"]
        self.assertEqual([t for _, t in live_lines(lines)], ["- [ ] Real"])

    def test_lines_break_on_newline_alone(self):
        # \u2028 and \x0c are characters in a line, not line breaks, to git and an editor.
        path = self.root / "actions.md"
        path.write_bytes("Intro\u2028still intro\x0c\r\n- [ ] Task\n".encode("utf-8"))
        self.assertEqual([t["line"] for t in open_tasks(path)], [2])
        self.assertEqual(split_lines("a\u2028b\r\nc\n"), ["a\u2028b", "c"])
        self.assertEqual(split_lines("a\nb"), ["a", "b"])
        self.assertEqual(split_lines(""), [])

    def test_a_byte_order_mark_does_not_hide_the_first_line(self):
        path = self.root / "actions.md"
        path.write_bytes("- [ ] First\n- [ ] Second\n".encode("utf-8-sig"))
        self.assertEqual([t["text"] for t in open_tasks(path)], ["First", "Second"])

    def test_only_a_top_level_dash_checkbox_is_a_task(self):
        # Deliberate, by operator ruling: sub-task and starred checkboxes are not counted,
        # so they never inflate open-item counts or the grooming threshold.
        path = write(self.root, "actions.md",
                     "- [ ] Parent\n  - [ ] Child 📅 2026-01-01\n* [ ] Star\n+ [x] Done\n")
        self.assertEqual([t["text"] for t in open_tasks(path)], ["Parent"])
        self.assertEqual(closed_tasks(path), [])

    def test_markers_come_back_parsed_and_the_text_comes_back_clean(self):
        got = parse_markers("Renew the domain 🔺 🛫 2026-01-01 📅 2026-09-01")
        self.assertEqual(got["text"], "Renew the domain")
        self.assertEqual(got["due"], "2026-09-01")
        self.assertEqual(got["start"], "2026-01-01")
        self.assertEqual(got["priority"], "🔺")
        self.assertFalse(got["malformed_date"])

    def test_a_marker_written_first_is_read_and_kept_out_of_the_text(self):
        got = parse_markers("🔺 **Send the lease.** Then call 📅 2026-09-01")
        self.assertEqual(got["text"], "**Send the lease.** Then call")
        self.assertEqual(got["priority"], "🔺")
        self.assertEqual(got["due"], "2026-09-01")
        self.assertEqual(parse_markers("🔺 Send the lease | the copy")["text"],
                         "Send the lease | the copy")
        got = parse_markers("📅 2026-09-01 🔼 Send the lease")
        self.assertEqual(got["text"], "Send the lease")
        self.assertEqual(got["due"], "2026-09-01")

    def test_a_date_shaped_string_that_is_no_date_says_so(self):
        got = parse_markers("Broken 📅 2026-13-45")
        self.assertIsNone(got["due"])
        self.assertTrue(got["malformed_date"])

    def test_a_malformed_marker_beside_a_valid_one_is_still_flagged(self):
        got = parse_markers("Call back 📅 2026-10-01 ⏳ tomorrow")
        self.assertEqual(got["due"], "2026-10-01")
        self.assertTrue(got["malformed_date"])

    def test_a_recurrence_stops_at_a_done_created_or_cancelled_marker(self):
        for marker in ("✅", "➕", "❌"):
            got = parse_markers(f"Pay rent 🔁 every month {marker} 2026-09-01")
            self.assertEqual(got["recurring"], "every month")

    def test_an_emoji_variation_selector_does_not_hide_the_date(self):
        got = parse_markers("Do it ⏳️ 2026-10-01 📅️ 2026-10-05")
        self.assertEqual(got["scheduled"], "2026-10-01")
        self.assertEqual(got["due"], "2026-10-05")
        self.assertFalse(got["malformed_date"])

    def test_a_task_carries_the_heading_it_sits_under(self):
        path = write(self.root, "projects/x/actions.md",
                     "# x - Actions\n\n## Build\n- [ ] One\n\n## Next actions\n- [ ] Two\n")
        tasks = open_tasks(path)
        self.assertEqual(tasks[0]["section"], "Build")
        self.assertEqual(tasks[1]["section"], "x - Actions")

    def test_completed_items_are_history(self):
        path = write(self.root, "projects/x/actions.md", "# x\n\n- [ ] Open\n- [x] Closed\n")
        self.assertEqual([t["text"] for t in open_tasks(path)], ["Open"])

    def test_cadence_reads_a_count_and_a_unit(self):
        self.assertEqual(cadence_days("every week"), 7)
        self.assertEqual(cadence_days("every 2 weeks"), 14)
        self.assertEqual(cadence_days("every 10 days"), 10)
        self.assertIsNone(cadence_days("every blue moon"))

    def test_a_task_that_does_not_recur_has_no_cadence(self):
        self.assertIsNone(cadence_days(parse_markers("Call Jan 📅 2026-09-22")["recurring"]))
        self.assertIsNone(cadence_days(""))


class ClosedTasks(VaultCase):

    def test_a_closed_checkbox_is_read_with_its_section_and_a_completion_date(self):
        path = write(self.root, "projects/x/actions.md",
                     "# x\n\n## Build\n- [x] Shipped the thing ✅ 2026-09-01\n- [ ] Open one\n")
        got = closed_tasks(path)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["text"], "Shipped the thing")
        self.assertEqual(got[0]["section"], "Build")
        self.assertEqual(got[0]["done"], "2026-09-01")

    def test_an_uppercase_x_also_counts(self):
        path = write(self.root, "projects/x/actions.md", "# x\n\n- [X] Done\n")
        self.assertEqual(len(closed_tasks(path)), 1)

    def test_a_closed_item_with_no_done_marker_has_none(self):
        path = write(self.root, "projects/x/actions.md", "# x\n\n- [x] Done, no marker\n")
        self.assertIsNone(closed_tasks(path)[0]["done"])

    def test_a_fenced_sample_closed_box_is_not_counted(self):
        path = write(self.root, "projects/x/actions.md", "# x\n\n```\n- [x] Sample\n```\n")
        self.assertEqual(closed_tasks(path), [])

    def test_open_tasks_shape_is_unchanged_by_sharing_the_reader_with_closed_tasks(self):
        path = write(self.root, "projects/x/actions.md",
                     "# x - Actions\n\n## Build\n- [ ] One\n\n## Next actions\n- [ ] Two\n")
        tasks = open_tasks(path)
        self.assertEqual(tasks[0]["section"], "Build")
        self.assertEqual(tasks[1]["section"], "x - Actions")
        self.assertEqual(set(tasks[0]), {"line", "section", "text", "due", "scheduled",
                                         "start", "recurring", "priority", "malformed_date",
                                         "first_link"})


class FieldCI(VaultCase):

    def test_a_field_is_found_regardless_of_case(self):
        self.assertEqual(field_ci({"Stage": "Qualified"}, "stage"), "Qualified")

    def test_a_missing_field_is_none(self):
        self.assertIsNone(field_ci({"Stage": "Qualified"}, "signer"))


class ContactNames(VaultCase):

    def test_the_h1_then_every_alias_either_line_lists(self):
        card = write(self.root, "areas/network/marten-van-oost.md", "\n".join([
            "# Marten Van Oost", "",
            "**Aliases:** Marten Vanoost; M. Van Oost", "",
            "Also: Tinus", "",
            "# A second heading is not a name", ""]))
        self.assertEqual(contact_names(card),
                         ["Marten Van Oost", "Marten Vanoost", "M. Van Oost", "Tinus"])

    def test_a_name_inside_a_fence_is_a_sample(self):
        card = write(self.root, "areas/network/a.md",
                     "```\n# Sample Person\n**Aliases:** Sample\n```\n\n# Ann Peeters\n")
        self.assertEqual(contact_names(card), ["Ann Peeters"])


class Git(VaultCase):

    def test_stdout_decodes_as_utf8_regardless_of_the_console_codepage(self):
        # subprocess.run(..., text=True) with no explicit encoding decodes with the
        # console's own locale codec, which raises on a non-UTF-8 Windows console faced
        # with non-ASCII git output. Raw bytes, decoded here as UTF-8, sidestep that.
        completed = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="café".encode("utf-8"), stderr=b"")
        with mock.patch("paraos_vault.subprocess.run", return_value=completed):
            self.assertEqual(git(self.root, ["log", "-1"]), "café")

    def test_bytes_come_back_as_git_wrote_them_and_git_is_their_decode(self):
        # A master read from a commit is compared byte for byte: a byte outside UTF-8
        # survives git_bytes, and only git() turns it into a replacement character.
        completed = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout=b"caf\xe9\r\n", stderr=b"")
        with mock.patch("paraos_vault.subprocess.run", return_value=completed):
            self.assertEqual(git_bytes(self.root, ["show", "HEAD:x"]), b"caf\xe9\r\n")
            self.assertEqual(git(self.root, ["show", "HEAD:x"]), "caf�\r\n")

    def test_a_non_zero_exit_is_none_from_both(self):
        completed = subprocess.CompletedProcess(
            args=["git"], returncode=128, stdout=b"", stderr=b"fatal: bad revision")
        with mock.patch("paraos_vault.subprocess.run", return_value=completed):
            self.assertIsNone(git_bytes(self.root, ["show", "nope:x"]))
            self.assertIsNone(git(self.root, ["show", "nope:x"]))

    def test_no_git_on_path_is_none_from_both(self):
        with mock.patch("paraos_vault.subprocess.run", side_effect=FileNotFoundError("git")):
            self.assertIsNone(git_bytes(self.root, ["status"]))
            self.assertIsNone(git(self.root, ["status"]))

    @unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
    def test_input_reaches_stdin_so_one_batch_answers_several_blobs(self):
        git_init(self.root)
        write(self.root, "a.txt", "alpha\n")
        write(self.root, "b.txt", "beta\n")
        git_commit_at(self.root, "2026-01-01")
        out = git_bytes(self.root, ["cat-file", "--batch"], input=b"HEAD:a.txt\nHEAD:b.txt\n")
        self.assertIn(b"\nalpha\n", out)
        self.assertIn(b"\nbeta\n", out)
        self.assertEqual(out.count(b" blob "), 2)


def git_init(root):
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    # No auto maintenance: its detached run writes into .git while a test reads or deletes it.
    subprocess.run(["git", "config", "gc.auto", "0"], cwd=root, check=True)
    subprocess.run(["git", "config", "maintenance.auto", "false"], cwd=root, check=True)


def git_commit_at(root, date_str, message="commit"):
    env = dict(os.environ, GIT_AUTHOR_DATE=f"{date_str}T00:00:00",
              GIT_COMMITTER_DATE=f"{date_str}T00:00:00")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=root, check=True, env=env)


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class GitBlameLineDate(VaultCase):

    def test_a_line_shifted_downward_by_an_uncommitted_insert_still_dates_by_its_own_edit(self):
        # The commit a git-log-by-line-number query would lose: a first commit writes the
        # line, a second commit edits it, then an uncommitted insert above it shifts its
        # line number without touching its content. Blame follows the content, not the
        # number, so the date returned is the second commit's.
        git_init(self.root)
        path = write(self.root, "projects/orchard-lane/actions.md", "# a\n\n- [ ] Task one\n")
        git_commit_at(self.root, "2026-01-01", "first")
        write(self.root, "projects/orchard-lane/actions.md", "# a\n\n- [ ] Task one, revised\n")
        git_commit_at(self.root, "2026-06-19", "second")
        write(self.root, "projects/orchard-lane/actions.md",
              "# a\n\n- [ ] A new line inserted above, never committed\n- [ ] Task one, revised\n")
        self.assertEqual(git_blame_line_date(self.root, path, 4), "2026-06-19")

    def test_a_line_never_committed_reports_uncommitted_not_a_date(self):
        git_init(self.root)
        path = write(self.root, "projects/orchard-lane/actions.md", "# a\n\n- [ ] Task one\n")
        git_commit_at(self.root, "2026-01-01", "first")
        write(self.root, "projects/orchard-lane/actions.md",
              "# a\n\n- [ ] A brand new uncommitted task\n- [ ] Task one\n")
        self.assertEqual(git_blame_line_date(self.root, path, 3), "uncommitted")


class GitDatesWithNoAnswer(VaultCase):
    """None, never a guess, where git cannot date a file: no git needed to show it."""

    def test_a_file_outside_the_vault_has_no_commit_date_and_no_line_date(self):
        vault = self.root / "vault"
        vault.mkdir()
        outside = write(self.root, "elsewhere/actions.md", "# x\n\n- [ ] One\n")
        self.assertIsNone(git_last_commit_date(vault, outside))
        self.assertIsNone(git_blame_line_date(vault, outside, 3))

    def test_a_vault_that_is_no_repository_has_no_line_date(self):
        path = write(self.root, "projects/x/actions.md", "# x\n\n- [ ] One\n")
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root.parent)}):
            self.assertIsNone(git_blame_line_date(self.root, path, 3))
            self.assertIsNone(git_last_commit_date(self.root, path))


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class GitUntracked(VaultCase):

    def test_an_untracked_file_under_the_given_folder_is_reported(self):
        git_init(self.root)
        write(self.root, "projects/x/actions.md", "# x\n")
        git_commit_at(self.root, "2026-01-01")
        write(self.root, "archive/projects/x/brief.md", "# x, archived\n")
        self.assertEqual(git_untracked(self.root, "archive"),
                         ["archive/projects/x/brief.md"])

    def test_a_name_outside_ascii_comes_back_as_written_not_octal_escaped(self):
        git_init(self.root)
        write(self.root, "projects/x/actions.md", "# x\n")
        git_commit_at(self.root, "2026-01-01")
        write(self.root, "archive/meetings/20260801 Mats Jørgen Øyan - Call.md", "# call\n")
        self.assertEqual(git_untracked(self.root, "archive"),
                         ["archive/meetings/20260801 Mats Jørgen Øyan - Call.md"])

    def test_nothing_untracked_is_an_empty_list_not_none(self):
        git_init(self.root)
        write(self.root, "projects/x/actions.md", "# x\n")
        git_commit_at(self.root, "2026-01-01")
        self.assertEqual(git_untracked(self.root, "."), [])

    def test_no_repo_answers_none_not_an_empty_list(self):
        write(self.root, "projects/x/actions.md", "# x\n")
        self.assertIsNone(git_untracked(self.root, "."))

    def test_a_vault_below_its_repo_root_gets_vault_relative_paths(self):
        git_init(self.root)
        vault = self.root / "vault"
        write(vault, "projects/x/actions.md", "# x\n")
        write(self.root, "elsewhere.md", "# not the vault\n")
        git_commit_at(self.root, "2026-01-01")
        write(vault, "archive/projects/x/brief.md", "# x, archived\n")
        write(self.root, "loose.md", "# outside the vault\n")
        self.assertEqual(git_untracked(vault, "archive"), ["archive/projects/x/brief.md"])
        self.assertEqual(git_untracked(vault, "."), ["archive/projects/x/brief.md"])

    def test_a_modified_file_in_a_nested_vault_resolves_to_itself(self):
        git_init(self.root)
        vault = self.root / "vault"
        path = write(vault, "projects/x/actions.md", "# x\n")
        git_commit_at(self.root, "2026-01-01")
        path.write_text("# x, edited\n", encoding="utf-8")
        self.assertEqual(git_modified(vault), {path.resolve()})

    def test_a_staged_rename_is_named_by_its_new_path(self):
        git_init(self.root)
        write(self.root, "projects/x/notes.md", "# x\n")
        git_commit_at(self.root, "2026-01-01")
        subprocess.run(["git", "mv", "projects/x/notes.md", "projects/x/brief.md"],
                       cwd=self.root, check=True)
        self.assertEqual(git_modified(self.root),
                         {(self.root / "projects/x/brief.md").resolve()})


class WhereThingsLive(VaultCase):

    def test_action_files_skip_archive_and_resources(self):
        write(self.root, "projects/live/actions.md", "# live\n\n- [ ] One\n")
        write(self.root, "areas/network/jan-janssen.md", "# Jan\n\n- [ ] Two\n")
        write(self.root, "archive/projects/old/actions.md", "# old\n\n- [ ] Three\n")
        write(self.root, "resources/playbook/actions.md", "# p\n\n- [ ] Four\n")
        found = {p.relative_to(self.root).as_posix() for p in action_files(self.root)}
        self.assertEqual(found, {"projects/live/actions.md", "areas/network/jan-janssen.md"})

    def test_contact_files_report_as_one_scope(self):
        path = write(self.root, "areas/network/jan-janssen.md", "# Jan\n")
        self.assertEqual(scope_of(self.root, path), ("A", "network"))

    def test_a_project_reports_its_own_folder(self):
        path = write(self.root, "projects/acme-website/actions.md", "# a\n")
        self.assertEqual(scope_of(self.root, path), ("P", "acme-website"))

    def test_an_area_reports_its_own_folder_and_a_bucket_level_file_the_bucket(self):
        self.assertEqual(scope_of(self.root, write(self.root, "areas/business/actions.md", "#\n")),
                         ("A", "business"))
        self.assertEqual(scope_of(self.root, write(self.root, "areas/actions.md", "#\n")),
                         ("A", "areas"))

    def test_a_contacts_or_people_file_aggregates_to_network(self):
        for folder in ("contacts", "people"):
            path = write(self.root, f"{folder}/jan-janssen.md", "# Jan\n")
            self.assertEqual(scope_of(self.root, path), ("A", "network"), folder)

    def test_a_file_outside_every_bucket_is_unknown_scope(self):
        path = write(self.root, "resources/playbook/actions.md", "# p\n")
        self.assertEqual(scope_of(self.root, path), ("?", "resources/playbook"))
        self.assertEqual(scope_of(self.root, write(self.root, "actions.md", "# root\n")),
                         ("?", "actions.md"))


class VaultRootCheck(VaultCase):

    def test_a_full_vault_root_passes_with_nothing_missing(self):
        write(self.root, "CLAUDE.md", "# v\n")
        (self.root / "projects").mkdir()
        (self.root / "areas").mkdir()
        self.assertEqual(vault_root(self.root), {"root": True, "missing": []})

    def test_archive_alone_satisfies_the_areas_or_archive_half(self):
        write(self.root, "CLAUDE.md", "# v\n")
        (self.root / "projects").mkdir()
        (self.root / "archive").mkdir()
        self.assertTrue(vault_root(self.root)["root"])

    def test_a_bare_folder_reports_everything_it_lacks(self):
        got = vault_root(self.root)
        self.assertFalse(got["root"])
        self.assertEqual(set(got["missing"]),
                         {"projects/", "areas/ or archive/", "CLAUDE.md"})

    def test_projects_with_no_areas_or_archive_is_not_a_root(self):
        (self.root / "projects").mkdir()
        write(self.root, "CLAUDE.md", "# v\n")
        got = vault_root(self.root)
        self.assertFalse(got["root"])
        self.assertEqual(got["missing"], ["areas/ or archive/"])


class Registry(VaultCase):

    def write_registry(self, entries):
        write(self.root, "vaults.json", json.dumps(entries))

    def test_entries_come_back_as_written(self):
        entries = [{"name": "BF", "path": "C:/vaults/BF", "kind": "personal",
                    "purpose": "x", "active": True}]
        self.write_registry(entries)
        self.assertEqual(registry(self.root), entries)

    def test_a_missing_file_is_no_entries_not_an_exception(self):
        self.assertEqual(registry(self.root), [])

    def test_unparseable_json_is_no_entries_not_an_exception(self):
        write(self.root, "vaults.json", "not json")
        self.assertEqual(registry(self.root), [])

    def test_paraos_home_env_var_is_read_when_none_is_passed(self):
        self.write_registry([{"name": "BF", "path": "x"}])
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.root)}):
            self.assertEqual(registry()[0]["name"], "BF")

    def test_falls_back_to_the_home_paraos_folder_when_unset(self):
        write(self.root, ".paraos/vaults.json", json.dumps([{"name": "BF", "path": "x"}]))
        with mock.patch.dict(os.environ, {"PARAOS_HOME": ""}), \
             mock.patch("paraos_vault.Path.home", return_value=self.root):
            self.assertEqual(registry()[0]["name"], "BF")


class FindClone(VaultCase):

    def test_an_explicit_clone_is_taken_as_given(self):
        (self.root / "para-os").mkdir()
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.root)}):
            self.assertEqual(find_clone(self.root / "mine"), (self.root / "mine", "explicit"))

    def test_the_default_is_para_os_under_paraos_home(self):
        (self.root / "para-os").mkdir()
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.root)}):
            self.assertEqual(find_clone(None), (self.root / "para-os", "default"))
        self.assertEqual(find_clone(None, self.root), (self.root / "para-os", "default"))

    def test_the_default_falls_back_to_the_home_paraos_folder(self):
        (self.root / ".paraos" / "para-os").mkdir(parents=True)
        with mock.patch.dict(os.environ, {"PARAOS_HOME": ""}), \
             mock.patch("paraos_vault.Path.home", return_value=self.root):
            self.assertEqual(find_clone(None), (self.root / ".paraos" / "para-os", "default"))

    def test_no_clone_anywhere_is_not_found(self):
        self.assertEqual(find_clone(None, self.root), (None, None))


class RegisteredVaultCheck(VaultCase):

    def test_the_exact_path_matches(self):
        entries = [{"name": "BF", "path": str(self.root)}]
        self.assertEqual(registered_vault(entries, self.root)["name"], "BF")

    def test_a_subfolder_matches_its_containing_vault(self):
        entries = [{"name": "BF", "path": str(self.root)}]
        got = registered_vault(entries, self.root / "projects" / "x")
        self.assertEqual(got["name"], "BF")

    def test_a_forward_slash_entry_matches_the_native_path(self):
        entries = [{"name": "BF", "path": str(self.root).replace(os.sep, "/")}]
        self.assertEqual(registered_vault(entries, self.root)["name"], "BF")

    def test_case_does_not_matter_where_the_platform_folds_it(self):
        if os.path.normcase("A") == "A":
            self.skipTest("this platform's normcase is case-sensitive")
        entries = [{"name": "BF", "path": str(self.root).upper()}]
        self.assertEqual(registered_vault(entries, self.root)["name"], "BF")

    def test_an_entry_missing_a_path_is_skipped_not_a_crash(self):
        entries = [{"name": "Broken"}, {"name": "BF", "path": str(self.root)}]
        self.assertEqual(registered_vault(entries, self.root)["name"], "BF")

    def test_an_unregistered_folder_matches_nothing(self):
        entries = [{"name": "BF", "path": str(self.root / "elsewhere")}]
        self.assertIsNone(registered_vault(entries, self.root))

    def test_an_entry_written_through_a_symlink_matches_the_resolved_vault(self):
        # The scan scripts resolve the vault they are pointed at; the registry keeps the
        # spelling the operator wrote. Both name one folder, so they must match.
        vault, link = self.aliased_vault()
        entries = [{"name": "BF", "path": str(link)}]
        self.assertEqual(registered_vault(entries, vault)["name"], "BF")
        self.assertEqual(registered_vault(entries, vault / "projects" / "x")["name"], "BF")

    def test_a_resolved_entry_matches_a_vault_reached_through_a_symlink(self):
        vault, link = self.aliased_vault()
        entries = [{"name": "BF", "path": str(vault)}]
        self.assertEqual(registered_vault(entries, link)["name"], "BF")

    def test_a_vault_registered_at_the_filesystem_root_holds_everything_under_it(self):
        fs_root = Path(abspath(self.root).anchor)
        entries = [{"name": "Root", "path": str(fs_root)}]
        self.assertEqual(registered_vault(entries, self.root)["name"], "Root")


class RegistryHolding(VaultCase):

    def test_a_project_in_another_registered_vault_is_found(self):
        other = self.root / "other-vault"
        write(other, "projects/acme-website/actions.md", "# a\n")
        entries = [{"name": "Other", "path": str(other)}]
        got = registry_holding(entries, "Acme Website")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["vault"], "Other")
        self.assertEqual(got[0]["path"], "projects/acme-website")
        self.assertEqual(got[0]["kind"], "project")
        self.assertEqual(Path(got[0]["root"]), abspath(other))

    def test_an_idea_and_an_archived_entity_are_labelled_by_kind(self):
        other = self.root / "other-vault"
        write(other, "resources/ideas/acme-website/brief.md", "# idea\n")
        write(other, "archive/projects/acme-website-old/brief.md", "# old\n")
        entries = [{"name": "Other", "path": str(other)}]
        idea_hit = registry_holding(entries, "acme-website")
        self.assertEqual(idea_hit[0]["kind"], "idea")
        archived_hit = registry_holding(entries, "acme-website-old")
        self.assertEqual(archived_hit[0]["kind"], "archived")
        self.assertEqual(archived_hit[0]["path"], "archive/projects/acme-website-old")

    def test_the_excluded_vault_is_never_reported(self):
        write(self.root, "projects/acme-website/actions.md", "# a\n")
        entries = [{"name": "Mine", "path": str(self.root)}]
        got = registry_holding(entries, "acme-website", exclude=self.root)
        self.assertEqual(got, [])

    def test_the_excluded_vault_is_skipped_under_another_spelling_of_its_folder(self):
        vault, link = self.aliased_vault()
        write(vault, "projects/acme-website/actions.md", "# a\n")
        entries = [{"name": "Mine", "path": str(link)}]
        self.assertEqual(registry_holding(entries, "acme-website", exclude=vault), [])

    def test_a_reported_root_keeps_the_registry_spelling(self):
        vault, link = self.aliased_vault()
        write(vault, "projects/acme-website/actions.md", "# a\n")
        got = registry_holding([{"name": "Other", "path": str(link)}], "acme-website")
        self.assertEqual(Path(got[0]["root"]), abspath(link))

    def test_a_vault_whose_path_no_longer_exists_is_unreadable_not_skipped(self):
        entries = [{"name": "Gone", "path": str(self.root / "does-not-exist")}]
        got = registry_holding(entries, "anything")
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["unreadable"])
        self.assertEqual(got[0]["vault"], "Gone")

    def test_no_match_anywhere_is_an_empty_list(self):
        other = self.root / "other-vault"
        write(other, "projects/unrelated/actions.md", "# a\n")
        entries = [{"name": "Other", "path": str(other)}]
        self.assertEqual(registry_holding(entries, "acme-website"), [])

    def test_an_entry_missing_a_path_is_skipped_not_a_crash(self):
        other = self.root / "other-vault"
        write(other, "projects/acme-website/actions.md", "# a\n")
        entries = [{"name": "No path"}, {"name": "Empty", "path": ""},
                   {"name": "Other", "path": str(other)}]
        self.assertEqual([h["vault"] for h in registry_holding(entries, "acme-website")],
                         ["Other"])


class FileDates(VaultCase):

    def test_a_files_own_mtime_is_used_when_it_stands_alone(self):
        path = write(self.root, "projects/x/actions.md", "# x\n")
        old = time.time() - 90 * 86400
        os.utime(path, (old, old))
        self.assertEqual(file_dates(self.root, [path])[path],
                         date.fromtimestamp(old).isoformat())

    def test_a_bulk_write_does_not_make_every_file_look_touched_today(self):
        # Three files written in one moment is a checkout or a sync, not three edits. With
        # no git to ask, the mtime still stands, so this pins the shape of the answer.
        paths = [write(self.root, f"projects/x/{n}.md", "# x\n") for n in range(3)]
        stamped = time.time()
        for p in paths:
            os.utime(p, (stamped, stamped))
        got = file_dates(self.root, paths)
        self.assertEqual(len(got), 3)
        self.assertTrue(all(v for v in got.values()))

    def test_an_uncommitted_edit_named_by_a_relative_path_keeps_its_mtime(self):
        if shutil.which("git") is None:
            self.skipTest("git is not on PATH")
        env = dict(os.environ, GIT_AUTHOR_DATE="2020-01-01T12:00:00",
                   GIT_COMMITTER_DATE="2020-01-01T12:00:00")
        run = lambda *a: subprocess.run(["git", "-C", str(self.root), *a], env=env,
                                        check=True, capture_output=True)
        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        run("config", "gc.auto", "0")
        run("config", "maintenance.auto", "false")
        for n in range(3):
            write(self.root, f"projects/x/{n}.md", "# x\n")
        run("add", "-A")
        run("commit", "-q", "-m", "init")
        write(self.root, "projects/x/0.md", "# x, edited\n")
        stamped = time.time()
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        paths = [Path(f"projects/x/{n}.md") for n in range(3)]
        for p in paths:
            os.utime(p, (stamped, stamped))
        got = file_dates(".", paths)
        self.assertEqual(got[paths[0]], date.fromtimestamp(stamped).isoformat())
        self.assertEqual(got[paths[1]], "2020-01-01")

    def test_a_bulk_write_followed_by_a_later_edit_dates_each_by_its_own_evidence(self):
        if shutil.which("git") is None:
            self.skipTest("git is not on PATH")
        git_init(self.root)
        paths = [write(self.root, f"projects/x/{n}.md", f"# {n}\n") for n in range(4)]
        git_commit_at(self.root, "2020-01-01")
        bulk, later = time.time() - 7200, time.time()
        for p in paths[:3]:
            os.utime(p, (bulk, bulk))
        os.utime(paths[3], (later, later))
        got = file_dates(self.root, paths)
        self.assertEqual([got[p] for p in paths[:3]], ["2020-01-01"] * 3)
        self.assertEqual(got[paths[3]], date.fromtimestamp(later).isoformat())

    def test_a_path_that_does_not_exist_has_no_date(self):
        missing = self.root / "projects/x/gone.md"
        self.assertEqual(file_dates(self.root, [missing]), {missing: None})


class EntityState(VaultCase):

    def test_a_stage_label_is_read_from_its_line(self):
        path = write(self.root, "brief.md", "# thing\n\n**Stage:** Taste\n\nProse.\n")
        self.assertEqual(stage_line(path), "Taste")

    def test_a_stage_in_a_status_table_is_read_from_its_row(self):
        path = write(self.root, "brief.md", "\n".join([
            "# thing", "", "## Status", "", "| Detail | Value |", "|---|---|",
            "| Stage | Proposal |", "",
        ]) + "\n")
        self.assertEqual(stage_line(path), "Proposal")

    def test_a_brief_with_no_stage_falls_back_to_its_first_prose_line(self):
        path = write(self.root, "brief.md", "# thing\n\nAn installer who wants a rebuild.\n")
        self.assertEqual(stage_line(path), "An installer who wants a rebuild.")

    def test_a_document_of_headings_alone_has_no_stage(self):
        path = write(self.root, "brief.md", "# thing\n\n## Status\n\n## Notes\n")
        self.assertIsNone(stage_line(path))

    def test_prose_under_a_status_heading_wins_over_the_first_prose_line(self):
        path = write(self.root, "brief.md", "\n".join([
            "# thing", "", "An installer who wants a rebuild.", "",
            "## Status", "", "Shipped, awaiting the final invoice.", "",
        ]) + "\n")
        self.assertEqual(stage_line(path), "Shipped, awaiting the final invoice.")

    def test_a_status_section_with_no_stage_row_ends_at_the_next_heading(self):
        path = write(self.root, "brief.md", "\n".join([
            "# thing", "", "An installer who wants a rebuild.", "",
            "## Status", "", "| Detail | Value |", "|---|---|", "| Owner | Alex |", "",
            "## Next", "", "Send the quote.", "",
        ]) + "\n")
        self.assertEqual(stage_line(path), "An installer who wants a rebuild.")


class EndOfWork(VaultCase):

    def test_open_items_are_gathered_per_entity_a_file_belongs_to(self):
        write(self.root, "projects/acme/actions.md",
              "# a\n\n- [ ] Send the deck 📅 2026-10-09\n- [x] Call ✅ 2026-10-01\n\n"
              "## Backlog\n\n- Rebuild the site, once the host replies\n")
        write(self.root, "projects/acme/sources/20261007 Call.md", "# Call\n")
        write(self.root, "areas/network/ann-smet.md", "# Ann\n\n## Next actions\n\n- [ ] Thank Ann\n")
        write(self.root, "resources/playbook.md", "# p\n")
        got = open_items(self.root, [self.root / "projects/acme/sources/20261007 Call.md",
                                     self.root / "areas/network/ann-smet.md",
                                     self.root / "resources/playbook.md"])
        self.assertEqual([g["entity"] for g in got],
                         ["areas/network/ann-smet.md", "projects/acme"])
        acme = got[1]
        self.assertEqual([t["text"] for t in acme["open"]], ["Send the deck"])
        self.assertEqual(acme["backlog"], [{"line": 8,
                                            "text": "Rebuild the site, once the host replies"}])

    def test_a_ticked_recurring_item_rolls_one_cadence_from_its_due_date(self):
        got = next_occurrence("- [ ] Pay rent 🔁 every month 📅 2026-10-01", date(2026, 10, 7))
        self.assertEqual(got["closed"], "- [x] Pay rent 🔁 every month 📅 2026-10-01 ✅ 2026-10-07")
        self.assertEqual(got["next"], "- [ ] Pay rent 🔁 every month 📅 2026-11-01")

    def test_when_done_or_no_due_date_counts_from_today(self):
        for line in ("- [ ] Water 🔁 every 2 weeks when done 📅 2026-09-01",
                     "- [ ] Water 🔁 every 2 weeks"):
            self.assertEqual(next_occurrence(line, date(2026, 10, 7))["due"], "2026-10-21", line)

    def test_a_cadence_that_cannot_be_counted_is_refused(self):
        with self.assertRaises(ValueError):
            next_occurrence("- [ ] Review 🔁 every weekday 📅 2026-10-07", date(2026, 10, 7))
        with self.assertRaises(ValueError):
            next_occurrence("- [ ] Not recurring 📅 2026-10-07", date(2026, 10, 7))

    def test_the_headline_is_the_bold_lead_or_the_whole_text(self):
        self.assertEqual(headline("**Send the deck** with the figures"), "Send the deck")
        self.assertEqual(headline("Send the deck with the figures"),
                         "Send the deck with the figures")


class Hygiene(VaultCase):

    def test_open_checkboxes_are_counted_where_they_are_forbidden(self):
        write(self.root, "archive/projects/old/actions.md", "# old\n\n- [ ] One\n- [ ] Two\n")
        write(self.root, "resources/playbook/notes.md", "# p\n\n- [ ] Three\n")
        got = misplaced_checkboxes(self.root)
        self.assertEqual(got["archive"][0]["open"], 2)
        self.assertEqual(got["resources"][0]["open"], 1)

    def test_a_frozen_record_is_left_alone(self):
        write(self.root, "archive/meetings/20260101 Notes.md", "\n".join([
            "# Notes", "", "> A point-in-time record of the meeting, not live work.", "",
            "- [ ] Something the room agreed", "",
        ]) + "\n")
        self.assertEqual(misplaced_checkboxes(self.root)["archive"], [])

    def test_a_plain_prose_marker_is_honoured_with_no_blockquote(self):
        write(self.root, "archive/meetings/20260102 Notes.md", "\n".join([
            "# Notes", "", "This is a frozen record, kept as generated; boxes never ticked.", "",
            "- [ ] Something the room agreed", "",
        ]) + "\n")
        self.assertEqual(misplaced_checkboxes(self.root)["archive"], [])

    def test_an_unrelated_blockquote_with_no_marker_text_is_still_exempt(self):
        write(self.root, "archive/meetings/20260103 Notes.md", "\n".join([
            "# Notes", "", "> Someone quoted in the room, nothing about being frozen.", "",
            "- [ ] Something the room agreed", "",
        ]) + "\n")
        self.assertEqual(misplaced_checkboxes(self.root)["archive"], [])

    def test_neither_trigger_present_is_flagged_as_before(self):
        write(self.root, "archive/meetings/20260104 Notes.md", "\n".join([
            "# Notes", "", "Plain prose, no marker and no blockquote.", "",
            "- [ ] Something the room agreed", "",
        ]) + "\n")
        self.assertEqual(len(misplaced_checkboxes(self.root)["archive"]), 1)

    def test_an_over_grown_brief_is_named_with_its_length(self):
        write(self.root, "projects/wordy/brief.md", "# wordy\n" + ("line\n" * 600))
        got = over_grown_briefs(self.root)
        self.assertEqual(got[0]["file"], "projects/wordy/brief.md")
        self.assertEqual(got[0]["lines"], 601)

    def test_a_brief_at_the_cap_is_not_over_grown(self):
        write(self.root, "projects/wordy/brief.md", "# wordy\n" + ("line\n" * 600))
        write(self.root, "areas/tidy/README.md", "# tidy\n" + ("line\n" * 499))
        self.assertEqual([r["file"] for r in over_grown_briefs(self.root)],
                         ["projects/wordy/brief.md"])

    def test_a_file_under_archive_with_only_closed_checkboxes_is_not_flagged(self):
        write(self.root, "archive/projects/old/actions.md", "# old\n\n- [x] Done\n")
        self.assertEqual(misplaced_checkboxes(self.root), {"archive": [], "resources": []})

    def network_row(self, level, roster=False):
        rows = ["| `projects/`, `areas/` | yes | open + closed |"]
        if level:
            rows.append(f"| `areas/network/` | {level} | what a card may hold |")
        write(self.root, "CLAUDE.md", "\n".join([
            "# V", "", "## Actions", "", "### Where a checkbox may live", "",
            "| Bucket | `actions.md` | State |", "|---|---|---|", *rows, "",
            *(["## Who writes this vault", "", "| Person | Lane |", "|---|---|"] if roster
              else []), ""]))
        write(self.root, "areas/network/jan-peeters.md", "\n".join([
            "# Jan Peeters", "", "## Next actions", "",
            "- [ ] Send Jan the deck", "- [x] Thank Jan ✅ 2026-09-01", ""]))

    def test_the_network_row_sets_the_contact_card_level(self):
        for row, level in (("yes", "yes"), ("**never**", "never"),
                           ("relationship only", "relationship only")):
            self.network_row(row)
            self.assertEqual(contact_card_level(self.root), level, row)

    def test_no_row_is_yes_unless_a_roster_implies_never(self):
        self.network_row(None)
        self.assertEqual(contact_card_level(self.root), "yes")
        self.network_row(None, roster=True)
        self.assertEqual(contact_card_level(self.root), "never")
        self.network_row("yes", roster=True)
        self.assertEqual(contact_card_level(self.root), "yes")

    def test_at_never_open_and_closed_card_checkboxes_are_reported_apart(self):
        self.network_row("**never**")
        got = misplaced_checkboxes(self.root, with_closed=True)
        self.assertEqual(got["areas/network"],
                         [{"file": "areas/network/jan-peeters.md", "open": 1}])
        self.assertEqual(got["closed"]["areas/network"],
                         [{"file": "areas/network/jan-peeters.md", "closed": 1}])
        self.assertNotIn("closed", misplaced_checkboxes(self.root))

    def test_at_yes_or_with_no_row_card_checkboxes_are_not_reported(self):
        for level in ("yes", None):
            self.network_row(level)
            got = misplaced_checkboxes(self.root, with_closed=True)
            self.assertNotIn("areas/network", got)
            self.assertEqual(got["closed"], {})

    def test_a_folder_the_table_declares_never_is_checked_like_resources(self):
        write(self.root, "CLAUDE.md", "# V\n\n### Where a checkbox may live\n\n"
              "| Bucket | `actions.md` | State |\n|---|---|---|\n"
              "| `areas/tickets/` | **never** | the tracker holds this work |\n")
        write(self.root, "areas/tickets/actions.md", "# t\n\n- [ ] Re-created by hand\n")
        self.assertEqual(misplaced_checkboxes(self.root)["areas/tickets"],
                         [{"file": "areas/tickets/actions.md", "open": 1}])

    def test_no_triage_folder_is_no_items(self):
        self.assertEqual(triage_items(self.root), [])

    def test_triage_counts_files_not_the_gitkeep(self):
        write(self.root, "triage/.gitkeep", "")
        write(self.root, "triage/20260919 Something - Note.md", "note\n")
        self.assertEqual(triage_items(self.root), ["20260919 Something - Note.md"])

    def test_a_pdf_and_its_markdown_twin_are_one_item(self):
        write(self.root, "triage/20260919 Deed - Scan.pdf", "%PDF-1.4\n")
        write(self.root, "triage/20260919 Deed - Scan.md", "extracted text\n")
        self.assertEqual(triage_items(self.root), ["20260919 Deed - Scan.pdf"])


DEAL_LIFECYCLE = "\n".join([
    "# Orchard Vault", "",
    "## Deal lifecycle", "",
    "A deal's PARA home follows its stage.", "",
    "| Stage | Exit criterion | PARA home |",
    "|---|---|---|",
    "| Lead | A first conversation has been held | `areas/business/leads.md` (row) |",
    "| Qualified | The signer is named | `resources/ideas/<company>/` |",
    "| Goal | First paid phase agreed | `projects/<company>/` |",
    "| Lost | Reason recorded | `archive/ideas/<company>/` |", "",
    "## Filing", "",
])


class Lifecycles(VaultCase):

    def test_a_declared_lifecycle_comes_back_with_its_noun_and_its_stages(self):
        write(self.root, "CLAUDE.md", DEAL_LIFECYCLE)
        got = lifecycles(self.root)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["heading"], "Deal lifecycle")
        self.assertEqual(got[0]["noun"], "deal")
        self.assertEqual([s["name"] for s in got[0]["stages"]],
                         ["Lead", "Qualified", "Goal", "Lost"])

    def test_a_row_home_is_flagged_and_loses_its_suffix(self):
        write(self.root, "CLAUDE.md", DEAL_LIFECYCLE)
        lead = lifecycles(self.root)[0]["stages"][0]
        self.assertEqual(lead["home"], "areas/business/leads.md")
        self.assertTrue(lead["row"])

    def test_a_home_under_archive_is_terminal_and_no_other_is(self):
        write(self.root, "CLAUDE.md", DEAL_LIFECYCLE)
        stages = {s["name"]: s for s in lifecycles(self.root)[0]["stages"]}
        self.assertTrue(stages["Lost"]["terminal"])
        self.assertFalse(stages["Goal"]["terminal"])
        self.assertFalse(stages["Goal"]["row"])
        self.assertEqual(stages["Qualified"]["home"], "resources/ideas/<company>/")

    def test_every_other_column_is_kept_as_free_text(self):
        write(self.root, "CLAUDE.md", DEAL_LIFECYCLE)
        lead = lifecycles(self.root)[0]["stages"][0]
        self.assertEqual(lead["columns"], {"Exit criterion": "A first conversation has been held"})

    def test_one_cell_naming_several_stages_yields_one_entry_each(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# v", "", "## Property lifecycle", "",
            "| Stage | PARA home |", "|---|---|",
            "| _Viewing, Bidding_: while an offer is live | `resources/ideas/<property>/` |", "",
        ]) + "\n")
        stages = lifecycles(self.root)[0]["stages"]
        self.assertEqual([s["name"] for s in stages], ["Viewing", "Bidding"])
        self.assertEqual({s["home"] for s in stages}, {"resources/ideas/<property>/"})

    def test_a_table_above_the_declaration_is_not_the_declaration(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# v", "", "## Deal lifecycle", "",
            "| Bucket | Meaning |", "|---|---|", "| projects | committed work |", "",
            "| Stage | PARA home |", "|---|---|", "| Lead | `areas/business/leads.md` (row) |", "",
        ]) + "\n")
        self.assertEqual([s["name"] for s in lifecycles(self.root)[0]["stages"]], ["Lead"])

    def test_a_fenced_table_declares_nothing(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# v", "", "## Deal lifecycle", "", "```",
            "| Stage | PARA home |", "|---|---|", "| Lead | `areas/business/leads.md` |",
            "```", "",
        ]) + "\n")
        self.assertEqual(lifecycles(self.root), [])

    def test_a_heading_with_no_noun_before_it_reports_none(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# v", "", "### Lifecycle", "",
            "| Stage | PARA home |", "|---|---|", "| Held | `areas/<name>/` |", "",
        ]) + "\n")
        self.assertIsNone(lifecycles(self.root)[0]["noun"])

    def test_a_vault_declaring_none_has_none(self):
        write(self.root, "CLAUDE.md", "# v\n\n## Filing\n\nProse.\n")
        self.assertEqual(lifecycles(self.root), [])

    def test_a_table_under_the_next_heading_is_not_the_declaration(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# v", "", "## Deal lifecycle", "", "Declared below, some day.", "",
            "## Filing", "", "| Stage | PARA home |", "|---|---|",
            "| Lead | `areas/business/leads.md` (row) |", "",
        ]) + "\n")
        self.assertEqual(lifecycles(self.root), [])


class StageOf(VaultCase):

    def test_a_stage_line_comes_back_in_its_parts(self):
        path = write(self.root, "brief.md", "\n".join([
            "# Orchard Labs", "",
            "**Stage:** Proposal (since 2026-01-01; prices hold to 2026-02-01)", "",
        ]) + "\n")
        got = stage_of(path)
        self.assertEqual(got["name"], "Proposal")
        self.assertEqual(got["since"], "2026-01-01")
        self.assertEqual(got["dated_facts"], [("prices hold to 2026-02-01", "2026-02-01")])
        self.assertIn("**Stage:**", got["raw"])

    def test_a_trailing_clause_is_not_part_of_the_name(self):
        path = write(self.root, "brief.md", "# Orchard Labs\n\n_Stage: Acquiring - a key date_\n")
        got = stage_of(path)
        self.assertEqual(got["name"], "Acquiring")
        self.assertEqual(got["qualifier"], "a key date")
        self.assertIsNone(got["since"])

    def test_a_stage_with_no_qualifier_has_no_dates(self):
        path = write(self.root, "brief.md", "# Orchard Labs\n\n**Stage:** Qualified\n")
        got = stage_of(path)
        self.assertEqual(got["name"], "Qualified")
        self.assertEqual(got["dated_facts"], [])
        self.assertIsNone(got["since"])

    def test_a_document_with_no_stage_line_has_no_stage(self):
        path = write(self.root, "brief.md", "# Orchard Labs\n\nAn installer who wants a rebuild.\n")
        self.assertIsNone(stage_of(path))


class HeaderBlock(VaultCase):

    def test_the_bold_led_lines_come_back_in_order(self):
        path = write(self.root, "brief.md", "\n".join([
            "# Orchard Labs", "",
            "**Stage:** Qualified (since 2026-01-01)",
            "**Opened:** 2026-01-01",
            "**Signer:** unknown", "",
            "**Not a header field:** this sits below the block", "",
        ]) + "\n")
        got = header_fields(path)
        self.assertEqual(list(got), ["Stage", "Opened", "Signer"])
        self.assertEqual(got["Signer"], "unknown")

    def test_a_link_survives_the_read_and_first_link_takes_its_target(self):
        path = write(self.root, "brief.md", "\n".join([
            "# Orchard Labs", "",
            "**Champion:** [Jan Janssen](../../areas/network/jan-janssen.md)", "",
        ]) + "\n")
        got = header_fields(path)
        self.assertIn("[Jan Janssen]", got["Champion"])
        self.assertEqual(first_link(got["Champion"]), "../../areas/network/jan-janssen.md")

    def test_a_field_with_no_link_has_no_target(self):
        self.assertIsNone(first_link("referral from a neighbour, network"))

    def test_first_link_keeps_a_target_carrying_parentheses_whole(self):
        self.assertEqual(first_link("see [w](https://en.wikipedia.org/wiki/Foo_(bar)) ok"),
                         "https://en.wikipedia.org/wiki/Foo_(bar)")
        self.assertEqual(first_link("[a]() then [b](b.md)"), "b.md")

    def test_an_escaped_pipe_stays_inside_its_cell(self):
        self.assertEqual(table_cells("| [[jan-janssen\\|Jan]] | lead |"),
                         ["[[jan-janssen\\|Jan]]", "lead"])
        self.assertEqual(table_cells("| a | b |"), ["a", "b"])

    def test_a_document_opening_on_prose_has_no_header(self):
        path = write(self.root, "brief.md", "# Orchard Labs\n\nProse, then nothing bold.\n")
        self.assertEqual(header_fields(path), {})

    def test_a_comment_line_between_the_title_and_the_fields_is_skipped_not_a_stop(self):
        path = write(self.root, "CLAUDE.md", "\n".join([
            "# Vault Conventions", "",
            "<!-- para-os-template: 2026.09.03 -->",
            "**Type:** vault",
            "**Flavor:** sales", "",
        ]) + "\n")
        got = header_fields(path)
        self.assertEqual(got["Type"], "vault")
        self.assertEqual(got["Flavor"], "sales")


class Register(VaultCase):

    def test_a_row_carries_its_columns_its_section_and_its_line(self):
        path = write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Stage | Next step |", "|---|---|---|",
            "| Orchard Labs | Lead | Call back 2026-01-01 |", "",
            "## Closed", "",
            "| Company | Stage | Outcome |", "|---|---|---|",
            "| Riverbend Foods | Lead | no reply |", "",
        ]) + "\n")
        rows = register_rows(path)
        self.assertEqual([r["name"] for r in rows], ["Orchard Labs", "Riverbend Foods"])
        self.assertEqual(rows[0]["Stage"], "Lead")
        self.assertEqual(rows[0]["section"], "Open")
        self.assertEqual(rows[0]["line"], 7)
        self.assertEqual(rows[1]["section"], "Closed")
        self.assertEqual(rows[1]["Outcome"], "no reply")

    def test_bold_and_backticks_are_off_the_keys(self):
        path = write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "| **Company** | `Stage` |", "|---|---|",
            "| Orchard Labs | Lead |", "",
        ]) + "\n")
        self.assertEqual(register_rows(path)[0]["Stage"], "Lead")

    def test_a_short_row_reports_its_own_cell_count(self):
        path = write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "## Open", "",
            "| Company | Contact | Stage |", "|---|---|---|",
            "| Orchard Labs | Kim |", "",
        ]) + "\n")
        row = register_rows(path)[0]
        self.assertEqual(row["cells"], 2)
        self.assertEqual(row["Stage"], "")

    def test_a_fenced_table_holds_no_rows(self):
        path = write(self.root, "areas/business/leads.md", "\n".join([
            "# Leads", "", "```", "| Company | Stage |", "|---|---|",
            "| Sample Co | Lead |", "```", "",
        ]) + "\n")
        self.assertEqual(register_rows(path), [])


class TaskLinks(VaultCase):

    def test_a_task_carries_the_target_of_its_first_link(self):
        path = write(self.root, "areas/business/actions.md", "\n".join([
            "# Business - Actions", "",
            "- [ ] Revisit [Orchard Labs](../../resources/ideas/orchard-labs/brief.md) 📅 2026-01-01",
            "- [ ] Nothing linked here", "",
        ]) + "\n")
        tasks = open_tasks(path)
        self.assertEqual(tasks[0]["first_link"], "../../resources/ideas/orchard-labs/brief.md")
        self.assertIsNone(tasks[1]["first_link"])


class Code(VaultCase):

    def test_a_fenced_block_is_blanked_and_the_lines_still_line_up(self):
        text = "A [real](a.md)\n```\n[sample](b.md)\n```\nB [real](c.md)\n"
        got = strip_code(text)
        self.assertEqual(len(got.splitlines()), 5)
        self.assertEqual([len(a) for a in got.splitlines()],
                         [len(a) for a in text.splitlines()])
        self.assertEqual([href for _, href, _ in extract_links(got)], ["a.md", "c.md"])

    def test_a_longer_fence_keeps_the_shorter_ones_inside_it(self):
        text = "````\n```\n[sample](a.md)\n```\n````\n[real](b.md)\n"
        self.assertEqual([href for _, href, _ in extract_links(strip_code(text))], ["b.md"])

    def test_an_inline_span_is_blanked_and_a_lone_backtick_is_prose(self):
        text = "Write `[a](x.md)` to link. A 2` measurement [b](y.md).\n"
        got = strip_code(text)
        self.assertEqual(len(got), len(text))
        self.assertEqual([href for _, href, _ in extract_links(got)], ["y.md"])

    def test_a_double_backtick_span_closes_only_on_two(self):
        self.assertEqual(strip_code("a ``x ` y`` b"), "a           b")

    def test_a_line_separator_character_does_not_start_a_line(self):
        # "```" after a \u2028 sits mid-line to git and an editor, so it opens no fence.
        text = "Intro\u2028```\r\n[a](a.md)\n"
        got = strip_code(text)
        self.assertEqual(got, text)
        self.assertEqual([line for line, _, _ in extract_links(got)], [2])


class Links(VaultCase):

    def test_a_target_with_parentheses_comes_back_whole(self):
        got = extract_links("[VAT](../resources/Orchard VAT (Notes).md) and after")
        self.assertEqual(got, [(1, "../resources/Orchard VAT (Notes).md",
                                "../resources/Orchard VAT (Notes).md")])

    def test_an_encoded_space_is_decoded_and_the_raw_href_survives(self):
        line, href, raw = extract_links("[Note](../archive/meetings/A%20Note.md)")[0]
        self.assertEqual(href, "../archive/meetings/A Note.md")
        self.assertEqual(raw, "../archive/meetings/A%20Note.md")
        self.assertEqual(line, 1)

    def test_a_fragment_is_dropped_before_the_target(self):
        self.assertEqual(extract_links("[x](brief.md#the-shape)")[0][1], "brief.md")

    def test_a_query_is_dropped_and_a_query_only_link_is_no_file(self):
        # A Google Docs export links its own headings as `(?tab=t.0#heading=h.abc)`.
        text = "[00:12](?tab=t.0#heading=h.abc) and [x](brief.md?v=2#top)"
        self.assertEqual(extract_links(text), [(1, "brief.md", "brief.md?v=2#top")])

    def test_an_angle_bracket_target_comes_back_without_its_brackets(self):
        got = extract_links("[x](<projects/my file.md>)")
        self.assertEqual(got, [(1, "projects/my file.md", "<projects/my file.md>")])

    def test_a_placeholder_in_angle_brackets_is_still_not_a_path(self):
        self.assertEqual(extract_links("[x](<path>) and [y](projects/<name>/brief.md)"), [])

    def test_a_link_title_is_not_part_of_the_target(self):
        self.assertEqual(extract_links('[y](a.md "The title")'), [(1, "a.md", "a.md")])
        self.assertEqual(extract_links("[y](<b c.md> 'T')"), [(1, "b c.md", "<b c.md>")])

    def test_anything_carrying_a_scheme_is_not_a_vault_path(self):
        text = "\n".join(["[a](https://example.test/x)", "[b](http://example.test/x)",
                          "[c](mailto:someone@example.test)", "[d](tel:12345)",
                          "[e](file:///C:/notes/x.md)", "[f](C:/notes/x.md)",
                          "[g](brief.md)"])
        self.assertEqual([href for _, href, _ in extract_links(text)], ["brief.md"])

    def test_a_placeholder_href_is_a_template_quoted_in_prose(self):
        text = "[x](projects/<name>/brief.md) and [y](projects/real/brief.md)"
        self.assertEqual([href for _, href, _ in extract_links(text)],
                         ["projects/real/brief.md"])

    def test_a_link_reports_the_line_it_sits_on(self):
        self.assertEqual(extract_links("one\ntwo\n[x](a.md)\n")[0][0], 3)

    def test_a_link_resolves_from_its_own_folder_not_the_vault_root(self):
        card = write(self.root, "areas/network/jan-janssen.md", "# Jan\n")
        got = resolve_link(card, "../../projects/orchard-lane/brief.md")
        self.assertEqual(got, self.root / "projects" / "orchard-lane" / "brief.md")

    def test_a_target_never_closed_is_no_link(self):
        self.assertEqual(extract_links("[x](projects/a.md and [y](b (c).md"), [])

    def test_a_target_with_no_label_before_it_is_no_first_link(self):
        self.assertIsNone(first_link("Stray ](projects/a.md) with no label"))
        self.assertEqual(first_link("Stray ](x.md), then [the brief](projects/a.md)"),
                         "projects/a.md")

    def test_a_path_outside_the_vault_keeps_its_absolute_form(self):
        vault = self.root / "vault"
        inside = self.root / "vault" / "projects" / "x" / "brief.md"
        outside = self.root / "elsewhere" / "brief.md"
        self.assertEqual(rel_posix(vault, inside), "projects/x/brief.md")
        self.assertEqual(rel_posix(vault, outside), abspath(outside).as_posix())


class Dangling(VaultCase):

    def test_a_link_to_a_missing_file_is_reported_and_a_live_one_is_not(self):
        write(self.root, "projects/orchard-lane/brief.md", "\n".join([
            "# Orchard Lane", "",
            "See [actions](actions.md) and [the card](../../areas/network/jan-janssen.md).",
            "Also [gone](../../areas/network/no-one.md).", "",
        ]) + "\n")
        write(self.root, "projects/orchard-lane/actions.md", "# a\n")
        write(self.root, "areas/network/jan-janssen.md", "# Jan\n")
        got = dangling_links(self.root)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["href"], "../../areas/network/no-one.md")
        self.assertEqual(got[0]["file"], "projects/orchard-lane/brief.md")
        self.assertEqual(got[0]["line"], 4)
        self.assertEqual(got[0]["resolved"], "areas/network/no-one.md")

    def test_an_encoded_target_that_exists_is_not_dangling(self):
        write(self.root, "resources/Orchard VAT (Notes).md", "# vat\n")
        write(self.root, "README.md", "[VAT](resources/Orchard%20VAT%20(Notes).md)\n")
        self.assertEqual(dangling_links(self.root), [])

    def test_a_broken_link_inside_a_fence_is_a_sample(self):
        write(self.root, "README.md", "```\n[x](projects/nothing/brief.md)\n```\n")
        self.assertEqual(dangling_links(self.root), [])

    def test_the_archive_is_out_of_the_default_scan_and_a_caller_widens_it(self):
        write(self.root, "archive/projects/old/brief.md", "[x](../../../gone.md)\n")
        self.assertEqual(dangling_links(self.root), [])
        self.assertEqual(len(dangling_links(self.root, roots=("archive",))), 1)


class Inbound(VaultCase):

    def test_each_way_of_writing_a_path_comes_back_with_its_shape(self):
        write(self.root, "areas/network/jan-janssen.md", "\n".join([
            "# Jan Janssen", "",
            "Bought [the house](../../projects/orchard-lane/brief.md).",
            "Listed as [projects/orchard-lane](../../projects/x/brief.md).",
            "Sources sit in `projects/orchard-lane/sources/`.",
            "He asked about projects/orchard-lane last week.",
            "Nothing to do with it here.", "",
        ]) + "\n")
        got = inbound_references(self.root, "orchard-lane")
        self.assertEqual([h["shape"] for h in got],
                         ["link_target", "link_text", "backtick", "prose"])
        self.assertEqual([h["line"] for h in got], [3, 4, 5, 6])
        self.assertFalse(any(h["in_sources"] for h in got))

    def test_an_encoded_reference_is_found_and_the_line_comes_back_as_written(self):
        write(self.root, "README.md", "[deed](archive/meetings/Orchard%20Lane%20Deed.md)\n")
        got = inbound_references(self.root, "Orchard Lane Deed")
        self.assertEqual(len(got), 1)
        self.assertIn("%20", got[0]["text"])
        self.assertEqual(got[0]["shape"], "link_target")

    def test_a_third_party_document_is_marked_rather_than_dropped(self):
        write(self.root, "projects/orchard-lane/sources/20260101 Deed - Scan.md",
              "The seller named orchard-lane in the deed.\n")
        got = inbound_references(self.root, "orchard-lane")
        self.assertTrue(got[0]["in_sources"])

    def test_git_internals_and_installed_skills_are_not_vault_content(self):
        write(self.root, ".claude/skills/para-archive/SKILL.md", "Sample: projects/orchard-lane\n")
        write(self.root, ".git/notes.md", "orchard-lane\n")
        write(self.root, "areas/business/actions.md", "- [ ] Call orchard-lane\n")
        got = inbound_references(self.root, "orchard-lane")
        self.assertEqual([h["file"] for h in got], ["areas/business/actions.md"])

    def test_a_fenced_mention_is_a_sample(self):
        write(self.root, "README.md", "```\nprojects/orchard-lane/brief.md\n```\n")
        self.assertEqual(inbound_references(self.root, "orchard-lane"), [])

    def test_a_longer_name_ending_in_the_same_name_is_not_a_reference(self):
        write(self.root, "areas/x/actions.md",
              "- [ ] Read [minutes](../../projects/p/sources/meeting-notes.md)\n")
        self.assertEqual(inbound_references(self.root, "notes.md", parent="triage"), [])

    def test_a_path_under_another_folder_is_not_a_reference_to_this_one(self):
        write(self.root, "areas/x/actions.md", "\n".join([
            "- [ ] See [the project](../../projects/p/README.md)",
            "- [ ] See [the item](../../triage/README.md)",
            "- [ ] Mentioned as README.md in prose", ""]))
        got = inbound_references(self.root, "README.md", parent="triage")
        self.assertEqual([h["line"] for h in got], [2, 3])

    def test_the_shape_is_read_from_the_link_that_holds_the_mention(self):
        write(self.root, "areas/network/jan-janssen.md",
              "See [the card](../x.md) and [the house](../../projects/orchard-lane/brief.md).\n")
        got = inbound_references(self.root, "orchard-lane")
        self.assertEqual([h["shape"] for h in got], ["link_target"])


class MovePlan(VaultCase):

    def build(self):
        write(self.root, "areas/properties/orchard-lane/brief.md", "\n".join([
            "# Orchard Lane", "",
            "Owner [Jan Janssen](../../network/jan-janssen.md).",
            "Its own [actions](actions.md) and [a source](sources/20260101 Deed - Scan.md).",
            "The [VAT note](../../../resources/Orchard VAT (Notes).md).", "",
        ]) + "\n")
        write(self.root, "areas/properties/orchard-lane/actions.md", "# a\n")
        write(self.root, "areas/properties/orchard-lane/sources/20260101 Deed - Scan.md", "d\n")
        write(self.root, "areas/network/jan-janssen.md", "\n".join([
            "# Jan Janssen", "",
            "Owns [Orchard Lane](../properties/orchard-lane/brief.md).", "",
        ]) + "\n")
        write(self.root, "resources/Orchard VAT (Notes).md", "# vat\n")

    def test_a_link_out_of_the_moved_folder_is_rewritten_for_the_new_depth(self):
        self.build()
        plan = move_plan(self.root, "areas/properties/orchard-lane",
                         "archive/properties/orchard-lane")
        out = {h["href"]: h["new_href"] for h in plan["inside"]}
        self.assertEqual(out["../../network/jan-janssen.md"],
                         "../../../areas/network/jan-janssen.md")
        self.assertEqual(out["../../../resources/Orchard VAT (Notes).md"],
                         "../../../resources/Orchard VAT (Notes).md")

    def test_a_link_travelling_with_the_folder_keeps_its_href(self):
        self.build()
        plan = move_plan(self.root, "areas/properties/orchard-lane",
                         "archive/properties/orchard-lane")
        self.assertNotIn("actions.md", [h["href"] for h in plan["inside"]])
        self.assertNotIn("sources/20260101 Deed - Scan.md",
                         [h["href"] for h in plan["inside"]])

    def test_an_inbound_link_gets_the_href_it_must_become(self):
        self.build()
        plan = move_plan(self.root, "areas/properties/orchard-lane",
                         "archive/properties/orchard-lane")
        self.assertEqual(len(plan["inbound"]), 1)
        hit = plan["inbound"][0]
        self.assertEqual(hit["file"], "areas/network/jan-janssen.md")
        self.assertEqual(hit["resolved"], "areas/properties/orchard-lane/brief.md")
        self.assertEqual(hit["new_href"],
                         "../../archive/properties/orchard-lane/brief.md")

    def test_the_new_href_is_encoded_the_way_the_old_one_was(self):
        write(self.root, "projects/orchard-lane/brief.md",
              "[VAT](../../resources/Orchard%20VAT%20(Notes).md)\n")
        write(self.root, "resources/Orchard VAT (Notes).md", "# vat\n")
        plan = move_plan(self.root, "projects/orchard-lane",
                         "archive/projects/orchard-lane")
        self.assertEqual(plan["inside"][0]["new_href"],
                         "../../../resources/Orchard%20VAT%20(Notes).md")

    def test_a_fragment_survives_the_rewrite(self):
        write(self.root, "projects/orchard-lane/brief.md",
              "[shape](../../resources/playbook.md#the-shape)\n")
        write(self.root, "resources/playbook.md", "# p\n\n## The shape\n")
        plan = move_plan(self.root, "projects/orchard-lane",
                         "archive/projects/orchard-lane")
        self.assertEqual(plan["inside"][0]["new_href"],
                         "../../../resources/playbook.md#the-shape")

    def test_a_link_inside_the_folder_to_itself_is_in_neither_list(self):
        self.build()
        write(self.root, "areas/properties/orchard-lane/actions.md",
              "# a\n\nSee [the brief](../orchard-lane/brief.md).\n")
        plan = move_plan(self.root, "areas/properties/orchard-lane",
                         "archive/properties/orchard-lane")
        self.assertNotIn("../orchard-lane/brief.md", [h["href"] for h in plan["inside"]])
        self.assertEqual([h["file"] for h in plan["inbound"]], ["areas/network/jan-janssen.md"])

    def test_a_line_naming_the_folder_but_linking_elsewhere_has_no_href_to_rewrite(self):
        self.build()
        write(self.root, "areas/business/notes.md", "# Notes\n")
        write(self.root, "areas/network/piet.md",
              "Visited orchard-lane, see [the notes](../business/notes.md).\n")
        plan = move_plan(self.root, "areas/properties/orchard-lane",
                         "archive/properties/orchard-lane")
        self.assertEqual([h["file"] for h in plan["inbound"]], ["areas/network/jan-janssen.md"])

    def test_a_folder_link_keeps_its_trailing_slash(self):
        self.build()
        write(self.root, "areas/network/piet.md",
              "# Piet\n\nThe [orchard-lane folder](../properties/orchard-lane/).\n")
        plan = move_plan(self.root, "areas/properties/orchard-lane",
                         "archive/properties/orchard-lane")
        hrefs = {h["file"]: h["new_href"] for h in plan["inbound"]}
        self.assertEqual(hrefs["areas/network/piet.md"],
                         "../../archive/properties/orchard-lane/")

    def test_a_space_the_old_href_never_had_is_encoded_in_the_new_one(self):
        # A bare space ends a link target, so it is encoded even though the old href had
        # none to say how; inside <...> a space is legal and stays.
        self.assertEqual(match_encoding("../a/b.md#x", "../New Home/b.md"),
                         "../New%20Home/b.md#x")
        self.assertEqual(match_encoding("<../a/b.md>", "../New Home/b.md"),
                         "<../New Home/b.md>")
        self.assertEqual(match_encoding("../a/b.md?v=2#x", "../New Home/b.md"),
                         "../New%20Home/b.md?v=2#x")


class FileContents(VaultCase):

    def body(self, word):
        return (word + " ") * 60 + "\n"

    def test_two_files_holding_the_same_bytes_are_one_group(self):
        write(self.root, "projects/a/brief.md", self.body("one"))
        write(self.root, "archive/projects/a/brief.md", self.body("one"))
        write(self.root, "projects/b/brief.md", self.body("two"))
        got = hashes(self.root)
        self.assertEqual(len(got["files"]), 3)
        self.assertEqual(duplicates(got),
                         [["archive/projects/a/brief.md", "projects/a/brief.md"]])

    def test_a_file_under_the_floor_is_not_weighed_against_the_others(self):
        write(self.root, "projects/a/stub.md", "# a\n")
        write(self.root, "projects/b/stub.md", "# b\n")
        self.assertEqual(hashes(self.root)["files"], {})

    def test_a_skipped_folder_is_named_rather_than_dropped(self):
        write(self.root, "projects/a/photos/front.txt", self.body("image"))
        write(self.root, "projects/a/brief.md", self.body("one"))
        got = hashes(self.root)
        self.assertEqual(got["skipped"], ["projects/a/photos/front.txt"])
        self.assertEqual(list(got["files"]), ["projects/a/brief.md"])

    def test_a_build_folder_is_set_aside_too(self):
        # Two archived decks each carry their own styles/index.css to build: not a
        # filing duplicate (20260923-1124 para-deep-clean TT, finding 7).
        write(self.root, "archive/projects/a/styles/index.css", self.body("css"))
        write(self.root, "archive/projects/b/styles/index.css", self.body("css"))
        write(self.root, "archive/projects/b/public/logo.txt", self.body("logo"))
        got = hashes(self.root)
        self.assertEqual(duplicates(got), [])
        self.assertEqual(got["skipped"], ["archive/projects/a/styles/index.css",
                                          "archive/projects/b/public/logo.txt",
                                          "archive/projects/b/styles/index.css"])

    def test_git_internals_are_never_hashed(self):
        write(self.root, ".git/objects/pack/notes.md", self.body("one"))
        write(self.root, "projects/a/brief.md", self.body("one"))
        got = hashes(self.root)
        self.assertEqual(list(got["files"]), ["projects/a/brief.md"])
        self.assertEqual(got["skipped"], [])

    def test_duplicates_reads_a_plain_digest_map_too(self):
        self.assertEqual(duplicates({"a.md": "x", "b.md": "x", "c.md": "y"}),
                         [["a.md", "b.md"]])

    def test_a_file_edited_after_the_snapshot_is_caught_before_the_write(self):
        path = write(self.root, "projects/a/brief.md", "# a\n")
        before = snapshot([path])
        self.assertEqual(changed(before), [])
        path.write_text("# a, edited elsewhere\n", encoding="utf-8")
        self.assertEqual(changed(before), [str(path)])

    def test_a_file_that_has_since_gone_counts_as_changed(self):
        path = write(self.root, "projects/a/brief.md", "# a\n")
        before = snapshot([path])
        path.unlink()
        self.assertEqual(changed(before), [str(path)])


class Normalised(VaultCase):

    def test_crlf_and_a_lone_cr_both_read_as_lf(self):
        self.assertEqual(normalised(b"a\r\nb\rc\n"), b"a\nb\nc\n")

    def test_a_leading_bom_is_dropped_and_one_anywhere_else_is_kept(self):
        self.assertEqual(normalised(b"\xef\xbb\xbfa\r\n"), b"a\n")
        self.assertEqual(normalised(b"a\xef\xbb\xbfb\n"), b"a\xef\xbb\xbfb\n")

    def test_a_copy_differing_by_line_endings_and_a_bom_alone_reads_identical(self):
        master = "# Northwind\n\nOne line.\n".encode("utf-8")
        copy = b"\xef\xbb\xbf" + master.replace(b"\n", b"\r\n")
        self.assertNotEqual(copy, master)
        self.assertEqual(normalised(copy), normalised(master))

    def test_a_str_reads_as_its_utf8_bytes(self):
        self.assertEqual(normalised("﻿café\r\n"), "café\n".encode("utf-8"))

    def test_trailing_whitespace_counts_as_a_difference_unless_asked(self):
        copy, master = b"a  \n\tb\t\n", b"a\n\tb\n"
        self.assertNotEqual(normalised(copy), normalised(master))
        self.assertEqual(normalised(copy, trailing_ws=True),
                         normalised(master, trailing_ws=True))

    def test_trailing_blank_lines_and_a_missing_final_newline_are_whitespace(self):
        self.assertEqual(normalised(b"a\n\nb\n \n\n", trailing_ws=True), b"a\n\nb\n")
        self.assertEqual(normalised(b"a\n\nb", trailing_ws=True), b"a\n\nb\n")
        self.assertEqual(normalised(b" \r\n\t\n", trailing_ws=True), b"")

    def test_snapshot_still_sees_a_line_ending_change(self):
        # A write-time check has to see every byte a writer changed.
        path = write_bytes(self.root, "projects/a/brief.md", b"# a\n")
        before = snapshot([path])
        path.write_bytes(b"# a\r\n")
        self.assertEqual(changed(before), [str(path)])

    def test_anything_but_bytes_or_str_is_refused(self):
        with self.assertRaises(TypeError):
            normalised(None)


CHANGELOG = "\n".join([
    "# Changelog", "", "Prose about the scheme.", "", "---", "",
    "## 2026.09.02", "", "The newest entry. Reaction: re-sync.", "", "---", "",
    "## 2026.09.01", "", "The one before it.", "",
    "## 2026.08.01", "", "The first.", "",
])


class Markers(VaultCase):

    def test_a_stamped_document_reports_its_revision(self):
        self.assertEqual(template_marker("# v\n\n<!-- para-os-template: 2026.09.02 -->\n"),
                         "2026.09.02")

    def test_the_legacy_label_reads_as_the_revision_it_became(self):
        self.assertEqual(template_marker("<!-- para-os-template: 2026.08 -->"), "2026.08.01")

    def test_an_unstamped_document_has_no_revision(self):
        self.assertIsNone(template_marker("# v\n\nNo marker here.\n"))

    def test_raw_returns_the_label_as_the_comment_writes_it(self):
        # What a history search has to look for: 2026.08.01 was never written into a
        # template that carried 2026.08.
        self.assertEqual(template_marker("<!-- para-os-template: 2026.08 -->", raw=True),
                         "2026.08")
        self.assertEqual(template_marker("<!--para-os-template: 2026.09.02-->", raw=True),
                         "2026.09.02")
        self.assertIsNone(template_marker("# v\n\nNo marker here.\n", raw=True))

    def test_every_installed_script_is_found_wherever_it_was_installed(self):
        write(self.root, "resources/scripts/granola.py",
              '#!/usr/bin/env python3\n"""para-os-integration: granola 2026.08.02"""\n')
        write(self.root, "sync.ps1", "# para-os-integration: sync 2026.09.01\n")
        write(self.root, "resources/scripts/local.py", "# a script of this vault's own\n")
        got = integration_markers(self.root)
        self.assertEqual([(h["file"], h["name"], h["revision"]) for h in got],
                         [("resources/scripts/granola.py", "granola", "2026.08.02"),
                          ("sync.ps1", "sync", "2026.09.01")])

    def test_every_shipped_script_is_found_where_its_marker_sits(self):
        # A script carrying its marker below a help block, past the first 40 lines, was
        # reported unmarked.
        repo = SCRIPT.parents[5]
        shipped = [p for d in ("integrations", "addons") if (repo / d).is_dir()
                   for p in sorted((repo / d).rglob("*"))
                   if p.is_file() and "para-os-integration:" in p.read_text("utf-8", "replace")
                   and p.suffix in (".py", ".js", ".mjs", ".ps1", ".sh")]
        if not shipped:
            self.skipTest("not in a para-os clone")
        for p in shipped:
            write(self.root, p.name, p.read_text("utf-8"))
        found = {h["file"] for h in integration_markers(self.root)}
        self.assertEqual(sorted(p.name for p in shipped if p.name not in found), [])

    def test_an_installed_skill_copy_is_not_an_integration(self):
        write(self.root, ".claude/skills/para-new/scripts/granola.py",
              '"""para-os-integration: granola 2026.08.02"""\n')
        self.assertEqual(integration_markers(self.root), [])

    def test_an_entry_ends_at_the_next_heading_that_is_no_revision(self):
        text = "\n".join(["# Changelog", "", "## 2026.09.02", "", "Real.", "",
                          "## How to read this file", "", "Not part of any entry.", ""])
        self.assertEqual([(e["revision"], e["body"]) for e in changelog_entries(text)],
                         [("2026.09.02", "Real.")])

    def test_each_entry_comes_back_with_its_body_in_the_order_written(self):
        got = changelog_entries(CHANGELOG)
        self.assertEqual([e["revision"] for e in got],
                         ["2026.09.02", "2026.09.01", "2026.08.01"])
        self.assertEqual(got[0]["body"], "The newest entry. Reaction: re-sync.")

    def test_each_entry_carries_the_line_of_its_own_heading(self):
        got = changelog_entries(CHANGELOG)
        self.assertEqual([e["line"] for e in got], [7, 13, 17])
        lines = CHANGELOG.splitlines()
        for entry in got:
            self.assertEqual(lines[entry["line"] - 1], f"## {entry['revision']}")

    def test_a_fenced_lookalike_heading_is_no_entry_and_shifts_no_line(self):
        # CHANGELOG.md quotes a revision heading inside a code fence; it is a sample, and
        # the fence lines still count toward the real headings' line numbers.
        text = "\n".join(["# Changelog", "```", "## 2026.12.01", "```", "",
                          "## 2026.09.02", "", "Real.", ""])
        got = changelog_entries(text)
        self.assertEqual([(e["revision"], e["line"]) for e in got], [("2026.09.02", 6)])

    def test_a_vault_is_offered_only_the_entries_after_its_own_marker(self):
        got = entries_between(changelog_entries(CHANGELOG), "2026.08.01", "2026.09.02")
        self.assertEqual([e["revision"] for e in got], ["2026.09.02", "2026.09.01"])

    def test_a_vault_on_the_newest_revision_is_offered_nothing(self):
        got = entries_between(changelog_entries(CHANGELOG), "2026.09.02", "2026.09.02")
        self.assertEqual(got, [])

    def test_an_unstamped_vault_is_offered_every_entry(self):
        got = entries_between(changelog_entries(CHANGELOG), None, "2026.09.01")
        self.assertEqual([e["revision"] for e in got], ["2026.09.01", "2026.08.01"])


class NoticeDates(unittest.TestCase):
    """The last day to give notice on a renewing agreement, which operating-discipline.md
    dates such an item on instead of on the renewal."""

    def test_a_month_back_crosses_into_the_year_before(self):
        self.assertEqual(add_months(date(2027, 1, 1), -3), date(2026, 10, 1))

    def test_a_day_past_the_end_of_a_shorter_month_clamps_to_its_last_day(self):
        self.assertEqual(add_months(date(2027, 5, 31), -3), date(2027, 2, 28))
        self.assertEqual(add_months(date(2028, 5, 31), -3), date(2028, 2, 29))
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_twelve_months_is_the_same_day_a_year_on(self):
        self.assertEqual(add_months(date(2026, 3, 15), 12), date(2027, 3, 15))
        self.assertEqual(add_months(date(2026, 3, 15), 0), date(2026, 3, 15))

    def test_three_months_notice_on_a_new_year_renewal_falls_on_the_first_of_october(self):
        got = notice_date(date(2027, 1, 1), "3 months", today=date(2026, 9, 1))
        self.assertEqual(got, {"renewal": "2027-01-01", "notice": "3 months", "term": None,
                               "notice_date": "2026-10-01", "passed": False})

    def test_a_notice_period_in_days_weeks_or_years_counts_in_that_unit(self):
        today = date(2026, 1, 1)
        for period, want in (("30 days", "2026-12-02"), ("6 weeks", "2026-11-20"),
                             ("1 year", "2026-01-01"), ("1 Month", "2026-12-01"),
                             ("2 months", "2026-11-01")):
            with self.subTest(period=period):
                self.assertEqual(
                    notice_date(date(2027, 1, 1), period, today=today)["notice_date"], want)

    def test_a_notice_date_already_behind_today_is_passed(self):
        got = notice_date(date(2027, 1, 1), "3 months", today=date(2026, 10, 6))
        self.assertEqual((got["notice_date"], got["passed"]), ("2026-10-01", True))
        same_day = notice_date(date(2027, 1, 1), "3 months", today=date(2026, 10, 1))
        self.assertFalse(same_day["passed"])

    def test_a_term_rolls_a_past_renewal_to_the_first_whose_notice_is_still_open(self):
        # Signed years ago, renewing each 1 March: the 2027 renewal's notice day is behind
        # today, so the next one still open is the 2028 renewal.
        got = notice_date(date(2020, 3, 1), "3 months", term="1 year",
                          today=date(2026, 12, 15))
        self.assertEqual((got["renewal"], got["notice_date"], got["passed"]),
                         ("2028-03-01", "2027-12-01", False))

    def test_a_term_counts_from_the_renewal_given_so_a_clamped_month_does_not_drift(self):
        # Stepping month by month from the 31st would carry February's 28th forward.
        got = notice_date(date(2026, 1, 31), "10 days", term="1 month",
                          today=date(2026, 3, 25))
        self.assertEqual((got["renewal"], got["notice_date"]), ("2026-04-30", "2026-04-20"))

    def test_a_term_leaves_a_renewal_whose_notice_is_still_open_where_it_is(self):
        got = notice_date(date(2027, 1, 1), "3 months", term="1 year", today=date(2026, 9, 1))
        self.assertEqual((got["renewal"], got["notice_date"]), ("2027-01-01", "2026-10-01"))

    def test_a_period_in_words_or_a_zero_term_is_refused(self):
        for notice, term in (("three months", None), ("3 fortnights", None), ("", None),
                             ("3 months", "0 years")):
            with self.subTest(notice=notice, term=term):
                with self.assertRaises(ValueError):
                    notice_date(date(2027, 1, 1), notice, term=term, today=date(2026, 1, 1))

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_the_command_prints_the_notice_date_with_its_inputs(self):
        code, out = self.run_main(["notice-date", "2027-01-01", "3 months",
                                   "--today", "2026-09-01"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["notice_date"], "2026-10-01")

    def test_the_command_rolls_forward_by_its_term(self):
        code, out = self.run_main(["notice-date", "2020-03-01", "3 months", "--term", "1 year",
                                   "--today", "2026-12-15"])
        self.assertEqual((code, json.loads(out)["renewal"]), (0, "2028-03-01"))

    def test_the_command_refuses_what_it_cannot_read_with_exit_2(self):
        for argv in (["notice-date", "1 January", "3 months"],
                     ["notice-date", "2027-01-01", "three months"],
                     ["notice-date", "2027-01-01", "3 months", "--today", "soon"]):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()), \
                        self.assertRaises(SystemExit) as stop:
                    self.run_main(argv)
                self.assertEqual(stop.exception.code, 2)


class ChangedCLI(VaultCase):
    """The `changed` command a writing skill calls right before each delete or move,
    per operating-discipline.md's rule to re-check a snapshot at write time."""

    def write_json(self, rel, data):
        path = self.root / rel
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def run_main(self, argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return main(argv)

    def test_a_bare_snapshot_with_nothing_changed_exits_0(self):
        target = write(self.root, "projects/x/actions.md", "# x\n")
        snap_file = self.write_json("snap.json", snapshot([target]))
        self.assertEqual(self.run_main(["changed", str(snap_file)]), 0)

    def test_a_bare_snapshot_with_something_changed_exits_1(self):
        target = write(self.root, "projects/x/actions.md", "# x\n")
        before = snapshot([target])
        target.write_text("# x, edited\n", encoding="utf-8")
        snap_file = self.write_json("snap.json", before)
        self.assertEqual(self.run_main(["changed", str(snap_file)]), 1)

    def test_a_scan_outputs_top_level_snapshot_key_is_read_too(self):
        target = write(self.root, "projects/x/actions.md", "# x\n")
        before = snapshot([target])
        target.write_text("# x, edited\n", encoding="utf-8")
        scan_file = self.write_json("scan.json", {"other": "stuff", "snapshot": before})
        self.assertEqual(self.run_main(["changed", str(scan_file)]), 1)

    def test_a_snapshot_nested_under_a_phase_key_is_read(self):
        # clean_scan.py nests its snapshot under the phase it ran; read at the top level
        # alone, every deep-clean run reported a false "changed".
        target = write(self.root, "projects/x/actions.md", "# x\n")
        scan = {"phase": "1", "vault": {"root": "."}, "phase1": {"snapshot": snapshot([target])}}
        scan_file = self.write_json("scan.json", scan)
        self.assertEqual(self.run_main(["changed", str(scan_file)]), 0)
        target.write_text("# x, edited\n", encoding="utf-8")
        self.assertEqual(self.run_main(["changed", str(scan_file)]), 1)

    def test_a_document_with_no_snapshot_is_refused_not_read_as_all_changed(self):
        scan_file = self.write_json("scan.json", {"phase": "1", "phase1": {"rows": []}})
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
            self.run_main(["changed", str(scan_file)])
        self.assertEqual(exit.exception.code, 2)

    def test_the_changed_paths_are_printed_as_a_json_list(self):
        target = write(self.root, "projects/x/actions.md", "# x\n")
        before = snapshot([target])
        target.write_text("# x, edited\n", encoding="utf-8")
        snap_file = self.write_json("snap.json", before)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(["changed", str(snap_file)])
        self.assertEqual(json.loads(out.getvalue()), {"changed": [str(target)], "arrived": []})

    def arrival_scan(self):
        folder = self.root / "triage"
        seen = write(self.root, "triage/seen.md", "# seen\n")
        write(self.root, "triage/.gitkeep", "")
        scan = {"snapshot": snapshot([abspath(seen)]), "snapshot_folders": [str(abspath(folder))]}
        return self.write_json("scan.json", scan)

    def test_a_file_arriving_in_a_snapshot_folder_exits_1_under_its_own_key(self):
        scan_file = self.arrival_scan()
        self.assertEqual(self.run_main(["changed", str(scan_file)]), 0)
        late = write(self.root, "triage/late.md", "# late\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["changed", str(scan_file)]), 1)
        self.assertEqual(json.loads(out.getvalue()),
                         {"changed": [], "arrived": [str(abspath(late))]})

    def test_a_file_arriving_in_a_subfolder_or_outside_is_not_an_arrival(self):
        scan_file = self.arrival_scan()
        write(self.root, "triage/inbox/late.md", "# late\n")
        write(self.root, "projects/x/late.md", "# late\n")
        self.assertEqual(self.run_main(["changed", str(scan_file)]), 0)

    def test_a_snapshot_folder_since_removed_holds_no_arrivals(self):
        self.assertEqual(arrived({}, [str(self.root / "triage")]), [])

    def test_snapshot_folders_under_a_phase_key_are_read(self):
        folder = self.root / "triage"
        folder.mkdir()
        scan = {"phase1": {"snapshot": {}, "snapshot_folders": [str(abspath(folder))]}}
        scan_file = self.write_json("scan.json", scan)
        write(self.root, "triage/late.md", "# late\n")
        self.assertEqual(self.run_main(["changed", str(scan_file)]), 1)


class RegistryCLI(VaultCase):

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_no_name_prints_the_whole_registry(self):
        entries = [{"name": "BF", "path": "C:/vaults/BF"}]
        write(self.root, "vaults.json", json.dumps(entries))
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.root)}):
            code, out = self.run_main(["registry"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), entries)

    def test_a_name_looks_it_up_in_every_other_registered_vault(self):
        other = self.root / "other-vault"
        write(other, "projects/acme-website/actions.md", "# a\n")
        home = self.root / "home"
        write(home, "vaults.json", json.dumps([{"name": "Other", "path": str(other)}]))
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(home)}):
            code, out = self.run_main(["registry", "acme-website", "--vault", str(self.root)])
        self.assertEqual(code, 0)
        got = json.loads(out)
        self.assertEqual(got[0]["vault"], "Other")
        self.assertEqual(got[0]["path"], "projects/acme-website")


TRIAGE_LINES = [
    "# V",                                                                                # 1
    "",                                                                                    # 2
    "## Triage sources",                                                                   # 3
    "",                                                                                    # 4
    "| Source | Type | Endpoint | Relevant when |",                                       # 5
    "|---|---|---|---|",                                                                   # 6
    "| granola | sync-script | `resources/scripts/granola.js` (writes meeting notes to "
    "`triage/`) | Meeting carries the `BF` title prefix (the script's own routing). |",     # 7
    "| workspace-primary | connector: `google-workspace` | `alex.rivera@example-work.com` "
    "| Primary work mailbox. |",                                                            # 8
    "| gmail-personal | connector: claude.ai Gmail | `alex.rivera@example.com` | Threads "
    "that arrived at the personal address. |",                                              # 9
    "| outlook-partner | fetch-script | `partner@example-mail.com` via "
    "`resources/scripts/outlook.py fetch` (no MCP connector for this mailbox; the script "
    "reads it and prints candidates, writing nothing) | Household mail. |",                   # 10
    "| biz-info | fetch-script | **Shared mailbox.** `info@example-biz.com` via "
    "`resources/scripts/outlook.py`, read through `owner@example-biz.com`'s token "
    "using delegated `Mail.Read.Shared`. | Shared inbox. |",               # 11
    "| biz-partner | fetch-script | `partner@example-biz.com` via `outlook.py` | The "
    "primary mailbox for this business. |",                                                 # 12
    "",                                                                                    # 13
    "## Agenda sources",                                                                    # 14
    "",                                                                                    # 15
]


class TriageSourcesTable(VaultCase):

    def write_claude(self, lines):
        return write(self.root, "CLAUDE.md", "\n".join(lines) + "\n")

    def test_no_claude_md_is_not_declared(self):
        self.assertEqual(triage_sources(self.root), {"declared": False, "rows": []})

    def test_a_claude_md_with_no_section_is_not_declared(self):
        self.write_claude(["# V", "", "## Filing", "", "Prose."])
        self.assertEqual(triage_sources(self.root), {"declared": False, "rows": []})

    def test_a_full_table_reads_every_row(self):
        self.write_claude(TRIAGE_LINES)
        got = triage_sources(self.root)
        self.assertTrue(got["declared"])
        self.assertEqual(len(got["rows"]), 6)

    def test_a_sync_script_row(self):
        self.write_claude(TRIAGE_LINES)
        row = triage_sources(self.root)["rows"][0]
        self.assertEqual(row["line"], 7)
        self.assertEqual(row["source"], "granola")
        self.assertEqual(row["kind"], "sync-script")
        self.assertEqual(row["type"], "sync-script")
        self.assertIsNone(row["connector"])
        self.assertEqual(row["path"], "resources/scripts/granola.js")
        self.assertIsNone(row["mailbox"])
        self.assertIsNone(row["drive_id"])
        self.assertEqual(row["endpoint"],
                         "resources/scripts/granola.js (writes meeting notes to triage/)")
        self.assertIn("Meeting carries the `BF` title prefix", row["relevant_when"])

    def test_a_google_workspace_connector_row(self):
        self.write_claude(TRIAGE_LINES)
        row = triage_sources(self.root)["rows"][1]
        self.assertEqual(row["kind"], "connector")
        self.assertEqual(row["connector"], "google-workspace")
        self.assertEqual(row["mailbox"], "alex.rivera@example-work.com")
        self.assertIsNone(row["path"])

    def test_a_claude_ai_gmail_connector_row_is_normalized(self):
        self.write_claude(TRIAGE_LINES)
        row = triage_sources(self.root)["rows"][2]
        self.assertEqual(row["kind"], "connector")
        self.assertEqual(row["connector"], "claude_ai_Gmail")
        self.assertEqual(row["mailbox"], "alex.rivera@example.com")

    def test_a_fetch_script_row_takes_the_qualifying_backtick_span(self):
        self.write_claude(TRIAGE_LINES)
        row = triage_sources(self.root)["rows"][3]
        self.assertEqual(row["kind"], "fetch-script")
        self.assertEqual(row["path"], "resources/scripts/outlook.py")
        self.assertEqual(row["mailbox"], "partner@example-mail.com")

    def test_a_shared_mailbox_row_skips_the_mailbox_backtick_for_the_script_one(self):
        self.write_claude(TRIAGE_LINES)
        row = triage_sources(self.root)["rows"][4]
        self.assertEqual(row["path"], "resources/scripts/outlook.py")
        self.assertEqual(row["mailbox"], "info@example-biz.com")

    def test_a_short_fetch_script_row(self):
        self.write_claude(TRIAGE_LINES)
        row = triage_sources(self.root)["rows"][5]
        self.assertEqual(row["path"], "outlook.py")
        self.assertEqual(row["mailbox"], "partner@example-biz.com")

    def test_a_french_header_falls_back_to_position(self):
        self.write_claude([
            "# V", "", "## Triage sources", "",
            "| Source | Type | Endpoint | Pertinent quand |", "|---|---|---|---|",
            "| granola | sync-script | `resources/scripts/granola.js` | "
            "Le titre commence par BF. |",
            "", "## Filing", "",
        ])
        row = triage_sources(self.root)["rows"][0]
        self.assertEqual(row["relevant_when"], "Le titre commence par BF.")

    def test_a_drive_row(self):
        self.write_claude([
            "# V", "", "## Triage sources", "",
            "| Source | Type | Endpoint | Relevant when |", "|---|---|---|---|",
            "| gdrive-mirror | drive | `0AKq7pXpF123abc` shared drive backing the mirror | "
            "Resolves a Google-native stub already staged in triage/. |",
            "", "## Filing", "",
        ])
        row = triage_sources(self.root)["rows"][0]
        self.assertEqual(row["kind"], "drive")
        self.assertEqual(row["drive_id"], "0AKq7pXpF123abc")
        self.assertIsNone(row["path"])
        self.assertIsNone(row["mailbox"])

    def test_a_table_inside_a_fence_is_not_read(self):
        self.write_claude([
            "# V", "", "## Triage sources", "", "Example shape:", "", "```",
            "| Source | Type | Endpoint | Relevant when |", "|---|---|---|---|",
            "| sample | sync-script | `x.py` | not real |", "```", "",
            "| Source | Type | Endpoint | Relevant when |", "|---|---|---|---|",
            "| granola | sync-script | `resources/scripts/granola.js` | Real row. |",
            "", "## Agenda sources", "",
        ])
        got = triage_sources(self.root)
        self.assertEqual(len(got["rows"]), 1)
        self.assertEqual(got["rows"][0]["source"], "granola")

    def rows(self, *rows):
        self.write_claude(["# V", "", "## Triage sources", "",
                           "| Source | Type | Endpoint | Relevant when |", "|---|---|---|---|",
                           *rows, "", "## Filing", ""])
        return triage_sources(self.root)["rows"]

    def test_a_script_path_written_bare_is_found_without_backticks(self):
        got = self.rows(
            "| notes | sync-script | resources/scripts/notes-sync.py --write | Meetings. |",
            "| bold | sync-script | **resources/scripts/Notes-Sync.PS1** (writes to triage/) "
            "| Meetings. |",
            "| shared | fetch-script | `info@example-biz.com` via resources/scripts/outlook.py "
            "| Shared inbox. |")
        self.assertEqual([r["path"] for r in got],
                         ["resources/scripts/notes-sync.py", "resources/scripts/Notes-Sync.PS1",
                          "resources/scripts/outlook.py"])
        self.assertEqual(got[2]["mailbox"], "info@example-biz.com")

    def test_a_cadence_hint_is_read_and_leaves_the_kind_alone(self):
        got = self.rows(
            "| granola | sync-script 🔁 every 2 weeks | `resources/scripts/granola.js` | Meetings. |",
            "| work | connector: google-workspace | `ann@example.com` | Clients. |")
        self.assertEqual([(r["kind"], r["cadence"]) for r in got],
                         [("sync-script", "every 2 weeks"), ("connector", None)])

    def test_a_script_row_naming_no_script_has_no_path(self):
        got = self.rows("| mail | fetch-script | ask Alex which script, `TBD` | Leads. |",
                        "| notes | sync-script | | Meetings. |")
        self.assertEqual([r["path"] for r in got], [None, None])

    def test_a_drive_id_with_no_backticks_is_the_endpoints_first_word(self):
        got = self.rows(
            "| mirror | drive | 0AKq7pXpF123abc shared drive backing the mirror | Stubs. |",
            "| bold | drive | **0AKq7pXpF456def** (the shared drive) | Stubs. |",
            "| none | drive | | Stubs. |")
        self.assertEqual([r["drive_id"] for r in got],
                         ["0AKq7pXpF123abc", "0AKq7pXpF456def", None])

    def test_another_connector_keeps_its_own_name_and_an_unknown_type_says_so(self):
        got = self.rows("| partner | connector: outlook-mcp | partner@example-mail.com | Mail. |",
                        "| loft | carrier pigeon | the roof | Whatever lands. |")
        self.assertEqual([(r["kind"], r["connector"]) for r in got],
                         [("connector", "outlook-mcp"), ("unknown", None)])
        self.assertEqual([r["path"] for r in got], [None, None])


class IngestLogsReading(VaultCase):

    def write_run(self, name, data):
        write(self.root, f"cache/ingest/runs/{name}", json.dumps(data, ensure_ascii=False))

    def test_a_missing_runs_folder_is_an_empty_list(self):
        self.assertEqual(ingest_logs(self.root), [])

    def test_started_at_wins_over_started_and_the_filename(self):
        self.write_run("20260906-211458.json",
                       {"mode": "write", "started_at": "2026-09-06T21:14:58+02:00",
                        "started": "2026-01-01T00:00:00Z"})
        got = ingest_logs(self.root)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["started_from"], "started_at")
        self.assertEqual(got[0]["started_at"], "2026-09-06T21:14:58+02:00")

    def test_started_is_read_when_started_at_is_absent(self):
        self.write_run("20260908-061849.json",
                       {"mode": "write", "started": "2026-09-08T06:00:00Z"})
        got = ingest_logs(self.root)[0]
        self.assertEqual(got["started_from"], "started")
        self.assertEqual(got["started_at"], "2026-09-08T06:00:00+00:00")

    def test_the_filename_stamp_is_the_last_resort(self):
        self.write_run("20260906-225301.json", {"mode": "write"})
        got = ingest_logs(self.root)[0]
        self.assertEqual(got["started_from"], "filename")
        # The instant's own local wall-clock reading matches the filename, whatever this
        # machine's offset happens to be - never a hard-coded offset.
        naive = datetime.fromisoformat(got["started_at"]).replace(tzinfo=None)
        self.assertEqual(naive, datetime(2026, 9, 6, 22, 53, 1))

    def test_a_file_that_fails_to_parse_is_a_record_not_dropped(self):
        path = self.root / "cache" / "ingest" / "runs" / "20260906-211458.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        got = ingest_logs(self.root)
        self.assertEqual(len(got), 1)
        self.assertIsNotNone(got[0]["load_error"])
        self.assertEqual(got[0]["started_from"], "filename")
        self.assertIsNone(got[0]["mode"])

    def test_a_log_holding_no_object_is_a_record_with_its_error(self):
        self.write_run("20260906-211458.json", ["write"])
        got = ingest_logs(self.root)
        self.assertEqual([(r["load_error"], r["mode"], r["started_from"]) for r in got],
                         [("not a JSON object", None, "filename")])

    def test_an_unreadable_log_named_off_the_stamp_has_no_instant_and_sorts_last(self):
        runs = self.root / "cache" / "ingest" / "runs"
        runs.mkdir(parents=True)
        for name in ("latest.json", "20261345-990000.json"):  # no stamp; no real instant
            (runs / name).write_text("not json", encoding="utf-8")
        self.write_run("20260906-211458.json",
                       {"mode": "write", "started_at": "2026-09-06T21:14:58+02:00"})
        got = ingest_logs(self.root)
        self.assertEqual([(r["file"], r["started_at"]) for r in got],
                         [("20260906-211458.json", "2026-09-06T21:14:58+02:00"),
                          ("latest.json", None), ("20261345-990000.json", None)])

    def test_counts_per_vault_is_read_first(self):
        self.write_run("20260912-094319.json",
                       {"mode": "write", "started_at": "2026-09-12T09:43:19+02:00",
                        "counts": {"per_vault": {"BF": 1}}, "staged_per_vault": {"BF": 99}})
        got = ingest_logs(self.root)[0]
        self.assertEqual(got["per_vault"], {"BF": 1})

    def test_staged_per_vault_is_the_fallback(self):
        self.write_run("20260906-225301.json",
                       {"mode": "write", "started_at": "2026-09-06T22:53:01+02:00",
                        "staged_per_vault": {"BF": 1, "Household": 2}})
        got = ingest_logs(self.root)[0]
        self.assertEqual(got["per_vault"], {"BF": 1, "Household": 2})

    def test_neither_counts_nor_staged_per_vault_is_none(self):
        self.write_run("20260906-225301.json",
                       {"mode": "write", "started_at": "2026-09-06T22:53:01+02:00"})
        got = ingest_logs(self.root)[0]
        self.assertIsNone(got["per_vault"])

    def test_declaring_vaults_comes_from_source_plan(self):
        self.write_run("20260918-161013.json", {
            "mode": "write", "started_at": "2026-09-18T16:10:13+02:00",
            "source_plan": {"declaring_vaults":
                            {"alex.rivera@example-work.com": ["BF", "Alpha"]}},
        })
        got = ingest_logs(self.root)[0]
        self.assertEqual(got["declaring_vaults"],
                         {"alex.rivera@example-work.com": ["BF", "Alpha"]})

    def test_files_written_absent_is_none_not_empty(self):
        self.write_run("20260906-225301.json",
                       {"mode": "write", "started_at": "2026-09-06T22:53:01+02:00"})
        self.assertIsNone(ingest_logs(self.root)[0]["files_written"])

    def test_files_written_empty_list_stands_for_wrote_nothing(self):
        self.write_run("20260906-225301.json",
                       {"mode": "write", "started_at": "2026-09-06T22:53:01+02:00",
                        "files_written": []})
        self.assertEqual(ingest_logs(self.root)[0]["files_written"], [])

    def test_errors_absent_is_an_empty_list(self):
        self.write_run("20260906-225301.json",
                       {"mode": "write", "started_at": "2026-09-06T22:53:01+02:00"})
        self.assertEqual(ingest_logs(self.root)[0]["errors"], [])

    def test_newest_first_by_instant_not_by_filename(self):
        self.write_run("20260906-211458.json",
                       {"mode": "write", "started_at": "2026-09-06T21:14:58+02:00"})
        self.write_run("20260918-161013.json",
                       {"mode": "write", "started_at": "2026-09-18T16:10:13+02:00"})
        got = ingest_logs(self.root)
        self.assertEqual([r["file"] for r in got],
                         ["20260918-161013.json", "20260906-211458.json"])

    def test_log_instant_is_the_aware_datetime(self):
        self.write_run("20260918-161013.json",
                       {"mode": "write", "started_at": "2026-09-18T16:10:13+02:00"})
        record = ingest_logs(self.root)[0]
        self.assertEqual(log_instant(record).isoformat(), "2026-09-18T16:10:13+02:00")

    def test_paraos_home_env_var_is_read_when_none_is_passed(self):
        self.write_run("20260918-161013.json",
                       {"mode": "write", "started_at": "2026-09-18T16:10:13+02:00"})
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.root)}):
            self.assertEqual(len(ingest_logs()), 1)


class IngestLedger(VaultCase):

    def write_ledger(self, data):
        path = self.root / "cache" / "ingest" / "ledger.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_missing_file_is_exists_false_with_empty_maps(self):
        got = ingest_ledger(self.root)
        self.assertEqual(got, {"exists": False, "mailboxes": {}, "by_message_id": {},
                              "load_error": None})

    def test_a_real_ledger_is_read_through(self):
        self.write_ledger({
            "mailboxes": {"alex@example-work.com": {
                "840140deadbeef": {"routed": ["Alpha"], "reason": "contact: alex@example.com",
                                  "date": "2026-09-17", "subject": "Invoice",
                                  "seen_through": "<msg-1>",
                                  "seen_date": "2026-09-17T10:00:00+02:00"},
            }},
            "by_message_id": {"<msg-1>": ["Alpha"]},
        })
        got = ingest_ledger(self.root)
        self.assertTrue(got["exists"])
        self.assertIsNone(got["load_error"])
        self.assertEqual(got["mailboxes"]["alex@example-work.com"]["840140deadbeef"]["routed"],
                         ["Alpha"])
        self.assertEqual(got["by_message_id"], {"<msg-1>": ["Alpha"]})

    def test_a_file_that_fails_to_parse_reports_the_error_with_empty_maps(self):
        path = self.root / "cache" / "ingest" / "ledger.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        got = ingest_ledger(self.root)
        self.assertTrue(got["exists"])
        self.assertIsNotNone(got["load_error"])
        self.assertEqual(got["mailboxes"], {})
        self.assertEqual(got["by_message_id"], {})

    def test_a_non_object_ledger_is_a_load_error_too(self):
        self.write_ledger(["not", "an", "object"])
        got = ingest_ledger(self.root)
        self.assertIsNotNone(got["load_error"])

    def test_paraos_home_env_var_is_read_when_none_is_passed(self):
        self.write_ledger({"mailboxes": {"a@example.com": {}}, "by_message_id": {}})
        with mock.patch.dict(os.environ, {"PARAOS_HOME": str(self.root)}):
            self.assertTrue(ingest_ledger()["exists"])


class WrittenUnder(VaultCase):

    def test_a_plain_path_under_the_folder_matches(self):
        folder = self.root / "BF" / "triage"
        entry = str(self.root / "BF" / "triage" / "20260918 Note 96cd6b.md")
        self.assertTrue(written_under(entry, folder))

    def test_a_forward_slash_entry_matches_a_native_folder(self):
        folder = self.root / "BF" / "triage"
        entry = str(self.root).replace(os.sep, "/") + "/BF/triage/20260918 Note 96cd6b.md"
        self.assertTrue(written_under(entry, folder))

    def test_a_sibling_folder_with_a_shared_prefix_does_not_match(self):
        folder = self.root / "BF" / "triage"
        entry = str(self.root / "BF" / "triage-old" / "x.md")
        self.assertFalse(written_under(entry, folder))

    def test_a_trailing_annotation_is_stripped(self):
        folder = self.root / ".paraos" / "cache" / "ingest"
        entry = str(self.root / ".paraos" / "cache" / "ingest" / "ledger.json") + \
            " (2 new unrouted entries on alex.rivera@example.com)"
        self.assertTrue(written_under(entry, folder))

    def test_a_leading_tilde_is_expanded(self):
        with mock.patch.dict(os.environ, {"USERPROFILE": str(self.root), "HOME": str(self.root)}):
            folder = self.root / ".paraos" / "cache"
            entry = "~/.paraos/cache/ingest/ledger.json (2 new entries)"
            self.assertTrue(written_under(entry, folder))

    def test_mojibake_in_the_filename_does_not_break_the_match(self):
        folder = self.root / "Garden" / "triage"
        entry = str(self.root / "Garden" / "triage") + "/20260918 Caf� Notice 3c227e.md"
        self.assertTrue(written_under(entry, folder))

    def test_a_filename_ending_in_a_real_parenthetical_is_not_stripped(self):
        folder = self.root / "Home" / "triage"
        entry = str(self.root / "Home" / "triage" /
                    "20260908 Book your appointment (Ref. 100200300) a6253e.md")
        self.assertTrue(written_under(entry, folder))

    def test_an_entry_logged_through_a_symlink_matches_the_resolved_folder(self):
        # Ingest logs the path it wrote through the registry's spelling of the vault, and
        # triage asks about its own resolved root.
        vault, link = self.aliased_vault()
        entry = str(link / "triage" / "20260918 Note 96cd6b.md")
        self.assertTrue(written_under(entry, vault / "triage"))
        self.assertFalse(written_under(entry, vault / "projects"))

    def test_a_backslash_entry_matches_on_any_platform(self):
        folder = self.root / "BF" / "triage"
        entry = str(self.root).replace(os.sep, "\\") + "\\BF\\triage\\20260918 Note 96cd6b.md"
        self.assertTrue(written_under(entry, folder))


class NoteNaming(VaultCase):

    def test_thread_hash_matches_the_verified_pairs(self):
        pairs = {
            "1a0c556d2559b07c": "88604c", "1a0c35e1b79985dc": "47ace9",
            "1a0b69b16daafb30": "6d5d7f", "199910ff2d3ed765": "ed0a10",
            "1a0b3c024b5cc425": "ffc5cd",
        }
        for thread_id, expected in pairs.items():
            self.assertEqual(thread_hash(thread_id), expected)

    def test_a_plain_note_name(self):
        got = note_name_parts("20260921 Accepted AI Chat 88604c.md")
        self.assertEqual(got, {"date": "20260921", "subject": "Accepted AI Chat",
                               "hash": "88604c", "copy": None})

    def test_a_same_day_collision_carries_its_copy_number(self):
        got = note_name_parts("20260921 Accepted AI Chat 88604c 2.md")
        self.assertEqual(got["copy"], 2)
        self.assertEqual(got["subject"], "Accepted AI Chat")
        self.assertEqual(got["hash"], "88604c")

    def test_a_name_with_no_hash_shaped_token_is_not_this_shape(self):
        self.assertIsNone(note_name_parts("20260912 Claude survival guide weekly.md"))

    def test_a_subject_ending_in_a_hex_looking_word_still_yields_the_real_trailing_hash(self):
        got = note_name_parts("20260921 Something deadbe 88604c.md")
        self.assertEqual(got["hash"], "88604c")
        self.assertEqual(got["subject"], "Something deadbe")

    def test_an_all_digit_hash_is_not_read_as_a_copy_number(self):
        got = note_name_parts("20260101 Invoice 202601 123456.md")
        self.assertEqual(got, {"date": "20260101", "subject": "Invoice 202601",
                               "hash": "123456", "copy": None})

    def test_a_non_md_file_is_not_this_shape(self):
        self.assertIsNone(note_name_parts("20260921 Accepted AI Chat 88604c.pdf"))

    def test_a_name_with_no_date_prefix_is_not_this_shape(self):
        self.assertIsNone(note_name_parts("Accepted AI Chat 88604c.md"))

    def test_a_name_with_no_subject_is_not_this_shape(self):
        self.assertIsNone(note_name_parts("20260921 88604c.md"))
        self.assertIsNone(note_name_parts("20260921 88604c 2.md"))


class Watermark(VaultCase):

    def test_no_entry_is_new(self):
        self.assertEqual(watermark(None),
                         {"verdict": "new", "legacy": False, "watermark": None})

    def test_a_full_entry_with_the_same_key_is_seen(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "2026-09-10T01:00:00+02:00"}
        got = watermark(entry, newest_key="<msg-1>")
        self.assertEqual(got["verdict"], "seen")
        self.assertFalse(got["legacy"])

    def test_a_full_entry_with_a_different_key_has_grown(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "2026-09-10T01:00:00+02:00"}
        got = watermark(entry, newest_key="<msg-2>")
        self.assertEqual(got["verdict"], "grown")

    def test_the_key_wins_even_when_a_date_would_disagree(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "2026-09-10T01:00:00+02:00"}
        got = watermark(entry, newest_date="2026-09-01T00:00:00+00:00", newest_key="<msg-2>")
        self.assertEqual(got["verdict"], "grown")

    def test_a_full_entry_is_seen_when_the_newest_date_is_no_later(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "2026-09-10T01:00:00+02:00"}
        got = watermark(entry, newest_date="2026-09-10T01:00:00+02:00")
        self.assertEqual(got["verdict"], "seen")

    def test_a_full_entry_carries_forward_when_the_newest_date_is_later(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "2026-09-10T01:00:00+02:00"}
        got = watermark(entry, newest_date="2026-09-11T00:00:00+00:00")
        self.assertEqual(got["verdict"], "carry")

    def test_a_legacy_entry_is_seen_only_before_its_day_starts(self):
        entry = {"seen_date": "2026-09-10"}
        got = watermark(entry, newest_date="2026-09-09T23:59:00+00:00")
        self.assertEqual(got["verdict"], "seen")
        self.assertTrue(got["legacy"])
        self.assertEqual(got["watermark"], "2026-09-10T00:00:00+00:00")

    def test_a_legacy_entry_grows_for_anything_later_that_same_day(self):
        # connectors.md: a legacy watermark reads as the start of its day, and anything
        # later - even the same afternoon - resurfaces rather than being dropped.
        entry = {"seen_date": "2026-09-10"}
        got = watermark(entry, newest_date="2026-09-10T08:00:00+00:00")
        self.assertEqual(got["verdict"], "grown")

    def test_a_legacy_entry_with_no_seen_date_falls_back_to_the_plain_date_field(self):
        entry = {"date": "2026-09-10"}
        got = watermark(entry, newest_date="2026-09-11T00:00:01+00:00")
        self.assertTrue(got["legacy"])
        self.assertEqual(got["verdict"], "grown")

    def test_no_newest_date_and_no_key_carries(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "2026-09-10T01:00:00+02:00"}
        self.assertEqual(watermark(entry)["verdict"], "carry")

    def test_an_unparseable_newest_date_carries_never_seen(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "2026-09-10T01:00:00+02:00"}
        got = watermark(entry, newest_date="not-a-date")
        self.assertEqual(got["verdict"], "carry")

    def test_an_unparseable_watermark_carries_never_seen(self):
        entry = {"seen_through": "<msg-1>", "seen_date": "not-a-date"}
        got = watermark(entry, newest_date="2026-09-10T00:00:00+00:00")
        self.assertEqual(got["verdict"], "carry")


class HashesNarrowing(VaultCase):

    def body(self, word, times=60):
        return (word + " ") * times + "\n"

    def test_sizes_only_reads_files_of_a_matching_size(self):
        # Both files clear the min_bytes floor on their own, so it is the sizes filter -
        # not that floor - proving out which one gets read.
        write(self.root, "projects/a/small.md", self.body("x", 110))
        big = write(self.root, "projects/a/big.md", self.body("y", 200))
        got = hashes(self.root, sizes={big.stat().st_size})
        self.assertEqual(list(got["files"]), ["projects/a/big.md"])
        self.assertEqual(got["skipped"], [])

    def test_within_only_considers_files_under_a_named_folder(self):
        write(self.root, "projects/a/brief.md", self.body("one"))
        write(self.root, "projects/a/sources/20260101 Deed.md", self.body("one"))
        got = hashes(self.root, within=("sources",))
        self.assertEqual(list(got["files"]), ["projects/a/sources/20260101 Deed.md"])

    def test_sizes_and_within_combine(self):
        keep = write(self.root, "projects/a/sources/keep.md", self.body("one"))
        write(self.root, "projects/a/sources/skip.md", self.body("two", 80))
        got = hashes(self.root, sizes={keep.stat().st_size}, within=("sources",))
        self.assertEqual(list(got["files"]), ["projects/a/sources/keep.md"])

    def test_defaults_are_unchanged(self):
        write(self.root, "projects/a/brief.md", self.body("one"))
        write(self.root, "projects/a/photos/front.txt", self.body("image"))
        got = hashes(self.root)
        self.assertEqual(got["skipped"], ["projects/a/photos/front.txt"])
        self.assertEqual(list(got["files"]), ["projects/a/brief.md"])

    def test_a_folder_matching_by_within_still_respects_skip(self):
        write(self.root, "projects/a/sources/photos/front.txt", self.body("image"))
        got = hashes(self.root, within=("sources",))
        self.assertEqual(got["skipped"], ["projects/a/sources/photos/front.txt"])


class SourcesCLI(VaultCase):

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_sources_prints_the_declared_rows(self):
        write(self.root, "CLAUDE.md", "\n".join([
            "# V", "", "## Triage sources", "",
            "| Source | Type | Endpoint | Relevant when |", "|---|---|---|---|",
            "| granola | sync-script | `resources/scripts/granola.js` | Meeting. |", "",
        ]) + "\n")
        code, out = self.run_main(["sources", "--vault", str(self.root)])
        self.assertEqual(code, 0)
        got = json.loads(out)
        self.assertTrue(got["declared"])
        self.assertEqual(got["rows"][0]["source"], "granola")


class IngestLogsCLI(VaultCase):

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_ingest_logs_prints_every_run_newest_first(self):
        write(self.root, "cache/ingest/runs/20260906-211458.json",
             json.dumps({"mode": "write", "started_at": "2026-09-06T21:14:58+02:00"}))
        write(self.root, "cache/ingest/runs/20260918-161013.json",
             json.dumps({"mode": "write", "started_at": "2026-09-18T16:10:13+02:00"}))
        code, out = self.run_main(["ingest-logs", "--paraos-home", str(self.root)])
        self.assertEqual(code, 0)
        got = json.loads(out)
        self.assertEqual([r["file"] for r in got],
                         ["20260918-161013.json", "20260906-211458.json"])


class QuestionsCLI(VaultCase):
    """The one-off questions the module docstring lists, each answered as one JSON document
    from the same function a skill's own scan imports."""

    def setUp(self):
        super().setUp()
        write(self.root, "CLAUDE.md", DEAL_LIFECYCLE)
        write(self.root, "projects/orchard-lane/brief.md",
              "# Orchard Lane\n\nOwner [Jan](../../areas/network/jan-janssen.md).\n")
        write(self.root, "areas/network/jan-janssen.md",
              "# Jan\n\nBought [the house](../../projects/orchard-lane/brief.md).\n"
              "Also [a lost page](../../projects/orchard-lane/gone.md).\n")
        write(self.root, "archive/projects/old/brief.md", "[gone](../../../nowhere.md)\n")

    def ask(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([*argv, "--vault", str(self.root)])
        self.assertEqual(code, 0)
        return json.loads(out.getvalue())

    def test_resolve_prints_where_one_entity_lives(self):
        got = self.ask("resolve", "Orchard Lane")
        self.assertEqual((got["status"], got["match"]["path"]),
                         ("resolved", "projects/orchard-lane"))

    def test_lifecycles_prints_every_declared_lifecycle(self):
        got = self.ask("lifecycles")
        self.assertEqual([(lc["heading"], [s["name"] for s in lc["stages"]]) for lc in got],
                         [("Deal lifecycle", ["Lead", "Qualified", "Goal", "Lost"])])

    def test_move_plan_prints_both_halves_of_the_rewrite(self):
        got = self.ask("move-plan", "projects/orchard-lane", "archive/projects/orchard-lane")
        self.assertEqual([h["new_href"] for h in got["inside"]],
                         ["../../../areas/network/jan-janssen.md"])
        self.assertEqual([h["new_href"] for h in got["inbound"]],
                         ["../../archive/projects/orchard-lane/brief.md",
                          "../../archive/projects/orchard-lane/gone.md"])

    def test_hashes_prints_the_digests_and_what_was_skipped(self):
        write(self.root, "projects/orchard-lane/photos/front.md", "x" * 300)
        write(self.root, "projects/orchard-lane/notes.md", "y" * 300)
        got = self.ask("hashes")
        self.assertEqual(list(got["files"]), ["CLAUDE.md", "projects/orchard-lane/notes.md"])
        self.assertEqual(got["skipped"], ["projects/orchard-lane/photos/front.md"])

    def test_links_inbound_prints_every_line_naming_the_entity(self):
        got = self.ask("links", "inbound", "orchard-lane")
        self.assertEqual([(h["file"], h["line"]) for h in got],
                         [("areas/network/jan-janssen.md", 3), ("areas/network/jan-janssen.md", 4)])

    def test_links_dangling_reads_the_live_buckets_unless_given_roots(self):
        self.assertEqual([h["resolved"] for h in self.ask("links", "dangling")],
                         ["projects/orchard-lane/gone.md"])
        got = self.ask("links", "dangling", "--root", "archive", "--root", "areas")
        self.assertEqual([h["file"] for h in got],
                         ["archive/projects/old/brief.md", "areas/network/jan-janssen.md"])

    def test_a_vault_that_is_no_folder_is_a_usage_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            main(["resolve", "orchard-lane", "--vault", str(self.root / "no-such-vault")])
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("no such vault", err.getvalue())

    def test_a_changed_file_that_cannot_be_read_or_holds_a_list_is_a_usage_error(self):
        listed = write(self.root, "list.json", json.dumps([str(self.root / "CLAUDE.md")]))
        for path, message in ((self.root / "no-such-snapshot.json", "cannot read"),
                              (write(self.root, "broken.json", "{not json"), "cannot read"),
                              (listed, "holds no snapshot")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
                main(["changed", str(path)])
            self.assertEqual(stop.exception.code, 2, path)
            self.assertIn(message, err.getvalue())


class RunAsAScript(VaultCase):
    """scripts.md's own call, `paraos_vault.py changed <scan output>`, and a question, run
    as the file itself from a folder that is not the vault."""

    def run_script(self, *argv):
        # A Windows pipe defaults to a codepage that cannot encode a vault's own names; an
        # ASCII stdout stands in for it on every platform.
        return subprocess.run([sys.executable, str(SCRIPT), *argv], cwd=self.root,
                              capture_output=True, timeout=60,
                              env=dict(os.environ, PYTHONIOENCODING="ascii"))

    def test_a_question_prints_utf8_json_whatever_the_console_encoding(self):
        vault = self.root / "vault"
        write(vault, "projects/Øresund-bridge/brief.md", "# Øresund\n")
        result = self.run_script("resolve", "resund-bridge", "--vault", str(vault))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(json.loads(result.stdout.decode("utf-8"))["match"]["path"],
                         "projects/Øresund-bridge")

    def test_changed_exits_1_when_a_file_in_the_scan_output_changed(self):
        target = write(self.root, "vault/projects/x/actions.md", "# x\n")
        scan = write(self.root, "scan.json", json.dumps({"snapshot": snapshot([target])}))
        self.assertEqual(self.run_script("changed", str(scan)).returncode, 0)
        target.write_text("# x, edited\n", encoding="utf-8")
        result = self.run_script("changed", str(scan))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout.decode("utf-8")),
                         {"changed": [str(target)], "arrived": []})


# ------------------------------------------------------------------ what a vault declares

def conventions(*fields, marker="2026.09.04"):
    """A vault CLAUDE.md: title, the marker comment, the given header lines, then prose."""
    return "\n".join(["# Northwind Vault Conventions", "",
                      f"<!-- para-os-template: {marker} -->", *fields, "",
                      "Per-vault guidance.", ""])


class Declarations(VaultCase):

    def test_every_line_under_the_title_is_read(self):
        write(self.root, "CLAUDE.md", conventions(
            "**Type:** vault", "**Flavor:** real-estate", "**Modules:** sales, crm"))
        self.assertEqual(declarations(self.root), {
            "type": "vault", "flavor": "real-estate", "modules": ["sales", "crm"]})

    def test_modules_keep_the_order_written_and_drop_empties(self):
        write(self.root, "CLAUDE.md", conventions("**Type:** x", "**Modules:** crm, , sales,"))
        self.assertEqual(declarations(self.root)["modules"], ["crm", "sales"])

    def test_a_vault_declaring_nothing_answers_with_nothing(self):
        write(self.root, "CLAUDE.md", conventions("**Type:** vault"))
        got = declarations(self.root)
        self.assertEqual((got["flavor"], got["modules"]), (None, []))

    def test_a_bold_line_below_the_header_block_is_not_a_declaration(self):
        write(self.root, "CLAUDE.md", conventions("**Type:** x") +
              "\n**Flavor:** real-estate\n")
        self.assertIsNone(declarations(self.root)["flavor"])

    def test_markdown_marks_around_a_value_are_not_part_of_the_name(self):
        write(self.root, "CLAUDE.md", conventions("**Type:** x", "**Flavor:** `real-estate`",
                                                  "**Modules:** `sales`, **crm**"))
        got = declarations(self.root)
        self.assertEqual((got["flavor"], got["modules"]), ("real-estate", ["sales", "crm"]))

    def test_a_folder_with_no_claude_md_answers_rather_than_raising(self):
        self.assertEqual(declarations(self.root), {"type": None, "flavor": None, "modules": []})


# ------------------------------------------------------------------- a para-os clone

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
        with mock.patch("paraos_vault.git_bytes") as git_bytes_spy:
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
        return started, mock.patch("paraos_vault.subprocess.Popen", side_effect=spy)

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
        with clone_session(), mock.patch("paraos_vault._open_batch", return_value=None):
            self.assertEqual(clone_read(self.clone, "HEAD", "addons/sales/crlf.txt"),
                             b"caf\xe9\r\nline\r\n")
            self.assertEqual(addon_root(self.clone, "HEAD", "sales"), "addons/sales")

if __name__ == "__main__":
    unittest.main(verbosity=1)
