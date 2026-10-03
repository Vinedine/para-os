#!/usr/bin/env python3
"""Tests for triage_scan.py. Each one pins a rule references/sources.md, references/filing.md
or references/approval.md states in prose.

    python3 test_triage_scan.py
    py -3 test_triage_scan.py

Standard library only. Every fixture is a throwaway vault plus a throwaway paraos_home in a
temporary directory, with fictitious names only: nothing reads or writes a real vault, and
nothing calls a model. `--now` is always passed in, never the clock.

What paraos_vault.py itself decides (the registry, run-log reading, staged-note naming,
watermarks, content hashes, tasks, links, snapshots) is tested beside it, in
para-shared/scripts/test_paraos_vault.py. What is tested here is what this skill alone
decides: a source row's `plan`, how a staged note's two header shapes are read, when its
Content line calls itself incomplete, which registered vaults its Routed line names, and how
a fetched thread folds against an already-staged note.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import triage_scan
from triage_scan import (
    build_loose, build_snapshot, ingest_block, main, note_block, over_threshold_block, plan,
    same_thread_block, seen_ledger_block, subdirectories_block, subdirectories_line,
    vault_block,
    _content_incomplete, _extract_thread_id, _mentioned_vaults, _routed_from_ledger,
)

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "para-shared" / "scripts"))
from paraos_vault import changed, registry, thread_hash  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "triage_scan.py"
NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_run(paraos_home, filename, data):
    path = paraos_home / "cache" / "ingest" / "runs" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def write_registry(paraos_home, entries):
    paraos_home.mkdir(parents=True, exist_ok=True)
    (paraos_home / "vaults.json").write_text(json.dumps(entries), encoding="utf-8")


SOURCES_HEADER = "\n".join([
    "# Vault", "", "**Type:** vault", "",
    "## Triage sources", "",
    "| Source | Type | Endpoint | Relevant when |", "|---|---|---|---|",
]) + "\n"


def sources_claude_md(rows):
    return SOURCES_HEADER + "\n".join(rows) + "\n"


class VaultCase(unittest.TestCase):
    """A throwaway vault root and a throwaway paraos_home, both removed afterwards.

    `resolved` builds both on the temp folder's resolved spelling (macOS's /var is a symlink,
    and a Windows temp folder can carry an 8.3 short name), for a case that needs the
    registry to list this vault without being a test of how that path is matched."""

    resolved = False

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve() if self.resolved else Path(tmp.name)
        self.root = base / "Alpha"
        self.home = base / "paraoshome"
        for d in ("projects", "areas", "archive", "triage"):
            (self.root / d).mkdir(parents=True)
        write(self.root, "CLAUDE.md", "# Vault\n\n**Type:** vault\n")
        write_registry(self.home, [
            {"name": "Alpha", "path": str(self.root), "kind": "personal", "active": True},
        ])

    def plan(self, now=NOW, threads=None):
        return plan(self.root, str(self.home), now, threads)


# --------------------------------------------------------------------------------- the vault

class VaultRoot(unittest.TestCase):

    def test_exit_3_on_a_non_root_names_the_registered_vault_at_the_folded_name(self):
        # A real --test finding: the session opened at the vault's OLD location, which is not
        # a parent of the registry's (new) path, so registered_vault() alone finds nothing -
        # the fallback is an entry whose *name* folds to the checked folder's own name.
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        old_location = base / "old-drive" / "Alpha"
        old_location.mkdir(parents=True)
        new_location = base / "clients" / "Alpha" / "Alpha - Documents"
        for d in ("projects", "areas", "archive", "triage"):
            (new_location / d).mkdir(parents=True)
        write(new_location, "CLAUDE.md", "# Vault\n")
        home = base / "paraoshome"
        write_registry(home, [{"name": "Alpha", "path": str(new_location),
                              "kind": "engagement", "active": True}])

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--vault", str(old_location), "--paraos-home", str(home),
                        "--now", "2026-09-22T12:00:00+00:00"])
        self.assertEqual(code, 3)
        out = json.loads(buf.getvalue())
        self.assertFalse(out["vault"]["root"])
        self.assertEqual(out["vault"]["hint"], {"name": "Alpha", "path": str(new_location)})

    def test_exit_3_names_no_hint_when_the_registry_holds_nothing(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--vault", str(root), "--paraos-home", str(root / "nohome"),
                        "--now", "2026-09-22T12:00:00+00:00"])
        self.assertEqual(code, 3)
        out = json.loads(buf.getvalue())
        self.assertIsNone(out["vault"]["hint"])

    def test_a_vault_root_missing_only_triage_is_not_a_root(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for d in ("projects", "areas", "archive"):
            (root / d).mkdir()
        write(root, "CLAUDE.md", "# Vault\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--vault", str(root), "--now", "2026-09-22T12:00:00+00:00"])
        self.assertEqual(code, 3)
        out = json.loads(buf.getvalue())
        self.assertIn("triage/", out["vault"]["missing"])

    def test_exit_2_on_a_collected_vault(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for d in ("projects", "areas", "archive", "triage"):
            (root / d).mkdir()
        write(root, "CLAUDE.md", "# Vault\n")
        write(root, "resources/mds/projects__acme__brief.md", "# acme\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--vault", str(root), "--now", "2026-09-22T12:00:00+00:00"])
        self.assertEqual(code, 2)

    def test_registered_root_carries_name_and_active_from_the_exact_entry(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Beta"
        for d in ("projects", "areas", "archive", "triage"):
            (root / d).mkdir(parents=True)
        write(root, "CLAUDE.md", "# Vault\n")
        info = vault_block(root, [{"name": "Beta", "path": str(root), "active": True}])
        self.assertTrue(info["root"])
        self.assertEqual(info["name"], "Beta")
        self.assertTrue(info["registered"])
        self.assertTrue(info["active"])

    def test_an_unregistered_root_falls_back_to_the_folder_name(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "SomeFolder"
        for d in ("projects", "areas", "archive", "triage"):
            (root / d).mkdir(parents=True)
        info = vault_block(root, [])
        self.assertEqual(info["name"], "SomeFolder")
        self.assertFalse(info["registered"])
        self.assertFalse(info["active"])

    def test_a_subfolder_of_a_registered_vault_names_that_vault_as_the_hint(self):
        # The session started inside the vault rather than at its root.
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Alpha"
        for d in ("projects", "areas", "archive", "triage"):
            (root / d).mkdir(parents=True)
        write(root, "CLAUDE.md", "# Vault\n")
        info = vault_block(root / "projects", [
            {"name": "Beta", "path": str(Path(tmp.name) / "Beta"), "active": True},
            {"name": "Alpha", "path": str(root), "active": True},
        ])
        self.assertFalse(info["root"])
        self.assertEqual(info["hint"], {"name": "Alpha", "path": str(root)})
        self.assertFalse(info["registered"])  # the subfolder is not the entry's own path
        self.assertEqual(info["name"], "projects")

    def test_the_folded_name_fallback_skips_entries_that_do_not_fold_to_it(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old_location = Path(tmp.name) / "old-drive" / "alpha vault"
        old_location.mkdir(parents=True)
        new_location = str(Path(tmp.name) / "new" / "Alpha Vault")
        info = vault_block(old_location, [
            {"name": "Beta", "path": str(Path(tmp.name) / "Beta")},
            {"name": "Alpha.Vault", "path": new_location},
        ])
        self.assertEqual(info["hint"], {"name": "Alpha.Vault", "path": new_location})


# --------------------------------------------------------------------------- ingest coverage

class IngestCoverage(VaultCase):

    def iso(self, delta_hours=0):
        return (NOW - timedelta(hours=delta_hours)).isoformat()

    def test_a_positive_count_with_files_written_elsewhere_is_not_covered(self):
        # A real --test finding, high: ingest staged notes for a vault of this name at
        # another path.
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": self.iso(1),
            "files_written": ["/some/other/root/triage/20260921 Note 88604c.md"],
            "counts": {"per_vault": {"Alpha": 3}},
        })
        ingest, nw = ingest_block(self.root, registry(str(self.home)), "Alpha",
                                  str(self.home), NOW)
        self.assertFalse(ingest["covered"])
        self.assertEqual(ingest["reason"],
                         "ingest staged 3 for Alpha outside this root - pulled locally")
        self.assertEqual(ingest["count_for_vault"], 3)
        self.assertEqual(ingest["staged_here"], 0)

    def test_an_explicit_zero_count_is_covered(self):
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": self.iso(1), "files_written": [],
            "counts": {"per_vault": {"Alpha": 0}},
        })
        ingest, _ = ingest_block(self.root, registry(str(self.home)), "Alpha",
                                 str(self.home), NOW)
        self.assertTrue(ingest["covered"])

    def test_a_file_written_under_this_root_is_covered(self):
        note = self.root / "triage" / "20260921 Note 88604c.md"
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": self.iso(1), "files_written": [str(note)],
        })
        ingest, _ = ingest_block(self.root, registry(str(self.home)), "Alpha",
                                 str(self.home), NOW)
        self.assertTrue(ingest["covered"])
        self.assertEqual(ingest["staged_here"], 1)

    def test_forty_nine_hours_old_is_not_covered(self):
        write_run(self.home, "20260920-110000.json", {
            "mode": "write", "started_at": self.iso(49), "files_written": [],
            "counts": {"per_vault": {"Alpha": 0}},
        })
        ingest, _ = ingest_block(self.root, registry(str(self.home)), "Alpha",
                                 str(self.home), NOW)
        self.assertFalse(ingest["covered"])
        self.assertEqual(ingest["reason"],
                         f"registry lists this vault, but ingest last staged "
                         f"{self.iso(49)} - pulled locally")

    def test_only_preview_logs_are_not_covered(self):
        write_run(self.home, "20260922-090000.json", {
            "mode": "preview", "started_at": self.iso(1),
        })
        ingest, nw = ingest_block(self.root, registry(str(self.home)), "Alpha",
                                  str(self.home), NOW)
        self.assertFalse(ingest["covered"])
        self.assertEqual(ingest["reason"],
                         "registry lists this vault, but ingest last staged never - "
                         "pulled locally")
        self.assertIsNone(nw)

    def test_an_unregistered_vault_is_not_covered_and_everything_pulls(self):
        write_registry(self.home, [])  # nothing registered at all
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| mail | connector: google-workspace | alex.rivera@example-work.com | New leads. |",
            "| notes | sync-script | `resources/scripts/notes-sync.js` | Meetings. |",
        ]))
        report = self.plan()
        self.assertFalse(report["ingest"]["covered"])
        self.assertEqual(report["ingest"]["reason"], "vault not registered - pulled as normal")
        plans = {r["source"]: r["plan"] for r in report["sources"]["rows"]}
        self.assertEqual(plans["mail"], "pull")
        self.assertEqual(plans["notes"], "run")

    def test_an_inactive_registered_vault_pulls_as_normal(self):
        write_registry(self.home, [
            {"name": "Alpha", "path": str(self.root), "kind": "personal",
             "active": False},
        ])
        report = self.plan()
        self.assertFalse(report["ingest"]["covered"])
        self.assertEqual(report["ingest"]["reason"],
                         "registry lists this vault inactive - pulled as normal")

    def test_a_log_that_fails_to_parse_is_reported_not_swallowed(self):
        path = self.home / "cache" / "ingest" / "runs" / "20260922-090000.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        report = self.plan()
        self.assertEqual(len(report["ingest"]["log_errors"]), 1)
        self.assertEqual(report["ingest"]["log_errors"][0]["file"], "20260922-090000.json")


# ------------------------------------------------------------------------------ row planning

class RowPlanning(VaultCase):

    def test_a_mailbox_absent_from_declaring_vaults_pulls_alone(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| covered | connector: google-workspace | covered@example-work.com | A. |",
            "| missing | connector: google-workspace | missing@example-work.com | B. |",
        ]))
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": (NOW - timedelta(hours=1)).isoformat(),
            "files_written": [str(self.root / "triage" / "x.md")],
            "source_plan": {"declaring_vaults": {"covered@example-work.com": ["Alpha"],
                                                "missing@example-work.com": ["OtherVault"]}},
        })
        report = self.plan()
        plans = {r["source"]: r["plan"] for r in report["sources"]["rows"]}
        self.assertEqual(plans["covered"], "skip")
        self.assertEqual(plans["missing"], "pull")

    def test_a_mailbox_named_in_an_error_pulls(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| clean | connector: google-workspace | clean@example-work.com | A. |",
            "| broken | connector: google-workspace | broken@example-work.com | B. |",
        ]))
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": (NOW - timedelta(hours=1)).isoformat(),
            "files_written": [str(self.root / "triage" / "x.md")],
            "errors": ["auth expired for broken@example-work.com"],
        })
        report = self.plan()
        plans = {r["source"]: r["plan"] for r in report["sources"]["rows"]}
        self.assertEqual(plans["clean"], "skip")
        self.assertEqual(plans["broken"], "pull")

    def test_a_sync_script_the_log_ran_without_error_skips(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| notes | sync-script | `resources/scripts/notes-sync.js` | Meetings. |",
        ]))
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": (NOW - timedelta(hours=1)).isoformat(),
            "files_written": [str(self.root / "triage" / "x.md")],
            "sync_runs": [{"vault": "Alpha", "script": "resources/scripts/notes-sync.js",
                          "written": 0, "error": None}],
        })
        report = self.plan()
        row = report["sources"]["rows"][0]
        self.assertEqual(row["plan"], "skip")

    def test_a_sync_script_with_only_a_count_in_the_log_runs(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| notes | sync-script | `resources/scripts/notes-sync.js` | Meetings. |",
        ]))
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": (NOW - timedelta(hours=1)).isoformat(),
            "files_written": [str(self.root / "triage" / "x.md")],
        })
        report = self.plan()
        row = report["sources"]["rows"][0]
        self.assertEqual(row["plan"], "run")
        self.assertIn("no per-vault sync runs", row["reason"])

    def test_a_sync_script_with_an_errored_run_still_runs(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| notes | sync-script | `resources/scripts/notes-sync.js` | Meetings. |",
        ]))
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": (NOW - timedelta(hours=1)).isoformat(),
            "files_written": [str(self.root / "triage" / "x.md")],
            "sync_runs": [{"vault": "Alpha", "script": "resources/scripts/notes-sync.js",
                          "written": 0, "error": "timed out"}],
        })
        report = self.plan()
        self.assertEqual(report["sources"]["rows"][0]["plan"], "run")

    def test_a_drive_row_always_looks_up_whatever_ingest_says(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| drive | drive | `abcDRIVEID123` | Resolves stubs. |",
        ]))
        report = self.plan()  # nothing covers this vault at all
        self.assertEqual(report["sources"]["rows"][0]["plan"], "lookup")

    def test_an_unrecognised_source_type_is_unknown_never_guessed(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| loft | carrier-pigeon | `the roof` | Whatever lands. |",
        ]))
        row = self.plan()["sources"]["rows"][0]
        self.assertEqual((row["plan"], row["reason"]),
                         ("unknown", "unrecognised source type: carrier-pigeon"))


class RowReasons(VaultCase):
    """The condition that decided a row, named in its `reason` (sources.md). Each case
    needs the registry to list this vault, so it runs on the resolved temp root."""

    resolved = True

    def test_a_vault_not_covered_carries_its_verdict_as_every_rows_reason(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| mail | connector: google-workspace | a@example-work.com | Leads. |",
            "| notes | sync-script | `resources/scripts/notes-sync.js` | Meetings. |",
        ]))
        report = self.plan()  # registered and active, but no ingest log at all
        reason = "registry lists this vault, but ingest last staged never - pulled locally"
        self.assertEqual(report["ingest"]["reason"], reason)
        self.assertEqual([(r["plan"], r["reason"]) for r in report["sources"]["rows"]],
                         [("pull", reason), ("run", reason)])

    def test_a_sync_run_for_another_vault_or_another_script_does_not_count(self):
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| notes | sync-script | `resources/scripts/notes-sync.js` | Meetings. |",
        ]))
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": (NOW - timedelta(hours=1)).isoformat(),
            "files_written": [str(self.root / "triage" / "x.md")],
            "sync_runs": [
                "not a record",
                {"vault": "Beta", "script": "resources/scripts/notes-sync.js", "error": None},
                {"vault": "Alpha", "script": "resources/scripts/other-sync.js", "error": None},
            ],
        })
        row = self.plan()["sources"]["rows"][0]
        self.assertEqual((row["plan"], row["reason"]),
                         ("run", "log records no matching sync run for this script"))

    def test_a_sync_run_matches_its_script_whatever_the_slashes_or_case(self):
        # The log is written on whichever machine ran ingest, with that machine's slashes.
        write(self.root, "CLAUDE.md", sources_claude_md([
            "| notes | sync-script | `resources/scripts/notes-sync.js` | Meetings. |",
        ]))
        write_run(self.home, "20260922-090000.json", {
            "mode": "write", "started_at": (NOW - timedelta(hours=1)).isoformat(),
            "files_written": [str(self.root / "triage" / "x.md")],
            "sync_runs": [{"vault": "Alpha", "script": "Resources\\Scripts\\Notes-Sync.js",
                           "error": None}],
        })
        self.assertEqual(self.plan()["sources"]["rows"][0]["plan"], "skip")


# --------------------------------------------------------------------------------- the note

class NoteShapes(unittest.TestCase):

    def note(self, name, body):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_the_ingest_shape_is_a_mail_note(self):
        path = self.note("20260920 Test subject 88604c.md", "\n".join([
            "# Test subject", "",
            "- **Source:** connector: google-workspace (alex.rivera@example-work.com)",
            "- **From:** Alex Rivera <alex.rivera@example-work.com>",
            "- **Received:** 2026-09-20T10:00:00+02:00",
            "- **Routed:** Beta and Gamma both hold pieces of this",
            "- **Content:** Full body of the message, nothing dropped.",
            "- **Link:** https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "",
            "Snippet body here.", "",
        ]))
        note = note_block(path, [{"name": "Beta"}, {"name": "Gamma"}], "Alpha", {})
        self.assertEqual(note["shape"], "ingest")
        self.assertTrue(note["mail_note"])
        self.assertEqual(note["mailbox"], "alex.rivera@example-work.com")
        self.assertEqual(note["mentioned_vaults"], ["Beta", "Gamma"])
        # no ledger entry for this thread: routed_vaults is null, not an empty guess
        self.assertIsNone(note["routed_vaults"])
        self.assertIsNone(note["routed_from"])
        self.assertIsNone(note["message_id"])
        self.assertIsNone(note["conversation_id"])

    def test_the_message_and_conversation_id_lines_are_read(self):
        path = self.note("20260920 Test subject 88604c.md", "\n".join([
            "# Test subject", "",
            "- **Source:** fetch-script: outlook.py (info@example-work.com)",
            "- **From:** Alex Rivera <alex.rivera@example-work.com>",
            "- **Received:** 2026-09-20T10:00:00+02:00",
            "- **Routed:** contact: alex.rivera@example-work.com",
            "- **Content:** Full body.",
            "- **Link:** https://outlook.example/owa/?ItemID=AAMk%2Fabc",
            "- **Message id:** raw /users/info@example-work.com/messages/AAMk-abc_ "
            "--account me@example-work.com",
            "- **Conversation id:** AAQk-conv", "",
            "Body.", "",
        ]))
        note = note_block(path, [], "Alpha", {})
        self.assertEqual(note["message_id"], "raw /users/info@example-work.com/messages/"
                                             "AAMk-abc_ --account me@example-work.com")
        self.assertEqual(note["conversation_id"], "AAQk-conv")

    def test_a_granola_frontmatter_note_is_not_a_mail_note(self):
        path = self.note("20260920 Standup 88604c.md",
                         "---\nsource: granola\ndate: 2026-09-20\n---\n\nNotes.\n")
        note = note_block(path, [], "Alpha", {})
        self.assertEqual(note["shape"], "frontmatter")
        self.assertFalse(note["mail_note"])

    def test_a_note_to_triage_frontmatter_with_a_thread_id_is_a_mail_note(self):
        path = self.note("20260920 Note 88604c.md", "\n".join([
            "---", "source: google-workspace", "thread_id: 1a0c556d2559b07c",
            "date: 2026-09-20",
            "link: https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "---", "",
            "Short summary.", "",
        ]))
        note = note_block(path, [], "Alpha", {})
        self.assertTrue(note["mail_note"])
        self.assertEqual(note["thread_id"], "1a0c556d2559b07c")

    def test_neither_shape_leaves_every_field_empty(self):
        path = self.note("plain.md", "Just a plain markdown file, no header shape.\n")
        note = note_block(path, [], "Alpha", {})
        self.assertIsNone(note["shape"])
        self.assertFalse(note["mail_note"])
        self.assertEqual(note["fields"], {})

    def test_a_quoted_frontmatter_value_is_read_without_its_quotes(self):
        path = self.note("20260920 Note 88604c.md", "\n".join([
            "---", 'source: "google-workspace (alex@example-work.com)"',
            "tags:", "  - mail", "thread_id: '1a0c556d2559b07c'",
            "link: https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "---", "",
            "Short summary.", "",
        ]))
        note = note_block(path, [], "Alpha", {})
        self.assertEqual(note["shape"], "frontmatter")
        self.assertEqual(note["fields"], {
            "source": "google-workspace (alex@example-work.com)", "tags": "",
            "thread_id": "1a0c556d2559b07c",
            "link": "https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c"})
        self.assertEqual(note["mailbox"], "alex@example-work.com")
        self.assertTrue(note["mail_note"])

    def test_a_frontmatter_block_that_never_closes_is_no_shape(self):
        path = self.note("20260920 Standup 88604c.md",
                         "---\nsource: granola\nthread_id: 1a0c556d2559b07c\n\nNotes.\n")
        note = note_block(path, [], "Alpha", {})
        self.assertIsNone(note["shape"])
        self.assertFalse(note["mail_note"])

    def test_an_ingest_header_with_no_source_or_link_is_not_a_mail_note(self):
        # Blank lines before the title do not hide the header block under it.
        path = self.note("20260920 Forwarded 88604c.md", "\n".join([
            "", "", "# Forwarded", "",
            "- **From:** Alex Rivera <alex@example-work.com>",
            "- **Content:** Snippet only, the body was not read.", "",
            "Snippet body.", "",
        ]))
        note = note_block(path, [{"name": "Beta"}], "Alpha", {})
        self.assertEqual(note["shape"], "ingest")
        self.assertFalse(note["mail_note"])
        self.assertIsNone(note["mailbox"])
        self.assertEqual(note["mentioned_vaults"], [])
        self.assertTrue(note["content_incomplete"])
        self.assertIsNone(note["thread_id"])

    def test_a_ledger_record_that_is_not_an_object_is_passed_over(self):
        ledger_mailboxes = {"alex@example-work.com": {
            "some-thread": "not a record",
            "1a0c556d2559b07c": {"routed": ["Alpha", "Beta"]},
        }}
        self.assertEqual(_routed_from_ledger(ledger_mailboxes, "alex@example-work.com",
                                             "88604c", "Alpha"), (["Beta"], "ledger"))

    def test_mentioned_vaults_excludes_this_vault_and_matches_short_names_case_sensitively(self):
        entries = [{"name": "Beta"}, {"name": "Alpha"}, {"name": "BF"}, {"name": "QZ"}]
        hits = _mentioned_vaults(
            "Filed alongside BF's own copy, a qz reference, and this vault's own Beta note",
            entries, "Alpha")
        self.assertEqual(hits, ["BF", "Beta"])  # sorted; the lowercase qz never matches QZ
        # lowercase "tt" inside another word must not match the short, case-sensitive name
        hits2 = _mentioned_vaults("a note about fitting a mattress", entries, "Alpha")
        self.assertEqual(hits2, [])

    def test_mentioned_vaults_does_not_parse_negation(self):
        # A "Not Beta: ..." line is still a mention of Beta, not a routing decision - the
        # routing decision is routed_vaults, from the ingest ledger, not this text scan.
        entries = [{"name": "Beta"}]
        hits = _mentioned_vaults("Not Beta: a different prospect entirely.", entries, "Alpha")
        self.assertEqual(hits, ["Beta"])

    def test_routed_vaults_comes_from_the_ledger_entry_whose_thread_hashes_to_this_note(self):
        # thread_hash("1a0c556d2559b07c") == "88604c"
        ledger_mailboxes = {"alex@example-work.com": {
            "1a0c556d2559b07c": {"routed": ["Alpha", "Beta"]},
        }}
        routed, source = _routed_from_ledger(ledger_mailboxes, "alex@example-work.com",
                                             "88604c", "Alpha")
        self.assertEqual(routed, ["Beta"])
        self.assertEqual(source, "ledger")

    def test_routed_vaults_is_null_when_the_mailbox_is_unknown_to_the_ledger(self):
        routed, source = _routed_from_ledger({}, "alex@example-work.com", "88604c", "Alpha")
        self.assertIsNone(routed)
        self.assertIsNone(source)

    def test_routed_vaults_is_null_when_no_threads_hash_matches(self):
        ledger_mailboxes = {"alex@example-work.com": {
            "some-other-thread-id": {"routed": ["Alpha"]},
        }}
        routed, source = _routed_from_ledger(ledger_mailboxes, "alex@example-work.com",
                                             "88604c", "Alpha")
        self.assertIsNone(routed)
        self.assertIsNone(source)

    def test_a_six_hex_hash_is_never_searched_across_mailboxes(self):
        # thread_hash("1a0c556d2559b07c") == "88604c" - planted under a DIFFERENT mailbox
        # from the one being looked up, so a cross-mailbox collision must not match.
        ledger_mailboxes = {"other@example-work.com": {
            "1a0c556d2559b07c": {"routed": ["Beta"]},
        }}
        routed, source = _routed_from_ledger(ledger_mailboxes, "alex@example-work.com",
                                             "88604c", "Alpha")
        self.assertIsNone(routed)
        self.assertIsNone(source)

    def test_thread_id_is_kept_only_when_it_matches_the_filename_hash(self):
        # thread_hash("1a0c556d2559b07c") == "88604c" (verified pair, test_paraos_vault.py)
        self.assertEqual(_extract_thread_id(
            "https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "88604c"),
            "1a0c556d2559b07c")

    def test_thread_id_is_rejected_when_it_disagrees_with_the_filename_hash(self):
        # thread_hash("1a0c35e1b79985dc") == "47ace9", which is not "88604c"
        self.assertIsNone(_extract_thread_id(
            "https://mail.google.com/mail/u/0/#inbox/1a0c35e1b79985dc", "88604c"))

    def test_a_claude_ai_gmail_thread_f_link_yields_the_hex_thread_id(self):
        # 1876969071973085308 == 0x1a0c556d2559b07c, the verified pair above in decimal
        self.assertEqual(_extract_thread_id(
            "https://mail.google.com/mail/?authuser=x@example.com#all/thread-f:"
            "1876969071973085308", "88604c"),
            "1a0c556d2559b07c")

    def test_a_link_carrying_no_thread_id_yields_none(self):
        for link in ("https://mail.google.com/mail/u/0/",
                     "https://outlook.office.com/mail/inbox/id/AAQkAGI2"):
            self.assertIsNone(_extract_thread_id(link, "88604c"), link)


class ContentIncomplete(unittest.TestCase):

    def test_snippet_only_gmail_is_incomplete(self):
        got, phrase = _content_incomplete(
            "Snippet only: the ~200-character preview Gmail search returns; the body was "
            "not read.")
        self.assertTrue(got)
        self.assertEqual(phrase, "snippet")

    def test_snippet_only_fetch_script_cut_mid_is_incomplete(self):
        got, _ = _content_incomplete(
            "Snippet only: the preview outlook.py returns for the message (about 250 "
            "characters, cut mid-sentence); full body and the attached receipt not read.")
        self.assertTrue(got)

    def test_opening_lines_only_is_incomplete(self):
        got, phrase = _content_incomplete(
            "The opening lines of the newest message only. The quoted order history and "
            "the attached invoice PDF were not read or copied")
        self.assertTrue(got)
        self.assertEqual(phrase, "opening lines")

    def test_no_readable_body_is_incomplete(self):
        got, phrase = _content_incomplete(
            "No readable body: a calendar acceptance whose only content is an invite.ics "
            "attachment (1.3 KB), not opened, so the meeting date is not in this note.")
        self.assertTrue(got)
        self.assertEqual(phrase, "no readable body")

    def test_plain_text_body_with_an_unopened_linked_document_is_complete(self):
        # The one case the brief calls out by name: an attachment or linked document not
        # read does not make the BODY incomplete.
        got, phrase = _content_incomplete(
            "Plain-text body of the notes email, footer and feedback links dropped; the "
            "linked document (\"Open meeting notes\") was not opened.")
        self.assertFalse(got)
        self.assertEqual(phrase, "plain-text body")

    def test_unread_attachments_beside_a_full_body_are_complete(self):
        got, phrase = _content_incomplete("Full text, 26 image attachments not read")
        self.assertFalse(got)
        self.assertEqual(phrase, "full text")

    def test_an_excerpt_or_a_trimmed_body_is_incomplete(self):
        for line, want in (("Excerpt of the newest message; 3 attachments not read.", "excerpt"),
                           ("Body trimmed to the first paragraph.", "trimmed")):
            got, phrase = _content_incomplete(line)
            self.assertTrue(got, line)
            self.assertEqual(phrase, want)

    def test_a_full_body_without_the_operators_own_messages_is_incomplete(self):
        got, phrase = _content_incomplete(
            "Full body of the two inbound messages; own messages not fetched.")
        self.assertTrue(got)
        self.assertEqual(phrase, "not fetched")

    def test_a_clause_naming_an_attachment_settles_nothing(self):
        got, phrase = _content_incomplete("The attached PDF was not read.")
        self.assertIsNone(got)
        self.assertIsNone(phrase)

    def test_the_word_incomplete_is_not_read_as_complete(self):
        # "complete" is a held phrase and sits inside "incomplete": the line says the body
        # is not held, so it must not read as held.
        for line in ("The body is incomplete.", "Incompletely fetched: the thread's first reply."):
            got, phrase = _content_incomplete(line)
            self.assertTrue(got, line)
            self.assertEqual(phrase, "incomplete")

    def test_complete_on_its_own_still_reads_as_held(self):
        got, phrase = _content_incomplete("Complete message body, signature dropped.")
        self.assertFalse(got)
        self.assertEqual(phrase, "complete")

    def test_no_content_line_is_null(self):
        got, phrase = _content_incomplete(None)
        self.assertIsNone(got)
        self.assertIsNone(phrase)

    def test_unremarkable_text_is_null(self):
        got, _ = _content_incomplete("Routine confirmation, nothing further to say.")
        self.assertIsNone(got)


# --------------------------------------------------------------------------- duplicates etc

class DuplicatesAndCrossVault(VaultCase):

    def body(self, word, times=40):
        return (word + " ") * times + "\n"

    def test_a_byte_identical_file_under_a_different_name_is_flagged(self):
        # A --test run finding: the duplicate check must not key on filename.
        content = self.body("identical-content-marker")
        write(self.root, "areas/wealth/sources/20260908 Original document.md", content)
        write(self.root, "triage/20260920 Duplicate arrival.md", content)
        loose = build_loose(self.root, [], "Alpha", {})
        item = next(i for i in loose if i["name"] == "20260920 Duplicate arrival.md")
        self.assertEqual(item["duplicates"], ["areas/wealth/sources/20260908 Original document.md"])
        self.assertIsNone(item["hash_skipped"])

    def test_a_file_under_min_hash_bytes_is_never_silently_empty(self):
        write(self.root, "triage/tiny.md", "short\n")
        loose = build_loose(self.root, [], "Alpha", {})
        item = next(i for i in loose if i["name"] == "tiny.md")
        self.assertIsNone(item["duplicates"])
        self.assertIsNotNone(item["hash_skipped"])

    def test_cross_vault_finds_a_byte_identical_file_via_a_text_mention_alone(self):
        # No ledger entry for this thread (empty ledger_mailboxes): cross_vault still finds
        # the twin through mentioned_vaults, the Routed line's own text. thread_hash(
        # "1a0c556d2559b07c") == "88604c" (verified pair, test_paraos_vault.py), so the
        # filename's own trailing hash has to spell that for the Link to verify at all.
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        other_root = Path(tmp.name) / "Beta"
        note_text = "\n".join([
            "# A note", "",
            "- **Source:** connector: google-workspace (x@example-work.com)",
            "- **From:** Someone <x@example-work.com>",
            "- **Received:** 2026-09-13T10:00:00+02:00",
            "- **Routed:** also relevant to Beta", "- **Content:** Full body.",
            "- **Link:** https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "",
        ]) + self.body("shared-prospect-note")
        # A byte-identical twin in Beta's own sources/ - the whole note, not just its body,
        # since the duplicate check is a content hash, never a filename or a substring.
        write(other_root, "resources/ideas/some-deal/sources/20260913 Original.md", note_text)
        write(self.root, "triage/20260913 Duplicate 88604c.md", note_text)
        entries = [{"name": "Alpha", "path": str(self.root)},
                  {"name": "Beta", "path": str(other_root)}]
        loose = build_loose(self.root, entries, "Alpha", {})
        item = next(i for i in loose if i["name"] == "20260913 Duplicate 88604c.md")
        self.assertEqual(item["note"]["mentioned_vaults"], ["Beta"])
        self.assertIsNone(item["note"]["routed_vaults"])
        self.assertEqual(item["cross_vault"],
                         [{"vault": "Beta",
                           "path": "resources/ideas/some-deal/sources/20260913 Original.md"}])

    def test_ledger_routed_here_only_but_the_routed_line_still_mentions_a_twin(self):
        # A real --test finding: the ingest ledger says this thread routed only to this vault
        # (Alpha), so routed_vaults is empty - but the note's own Routed line still names a
        # second registered vault holding a byte-identical file in its sources/. cross_vault
        # must catch it through the union, not through the ledger alone.
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        other_root = Path(tmp.name) / "Beta"
        note_text = "\n".join([
            "# A note", "",
            "- **Source:** connector: google-workspace (x@example-work.com)",
            "- **From:** Someone <x@example-work.com>",
            "- **Received:** 2026-09-13T10:00:00+02:00",
            "- **Routed:** relevant here, also touches Beta's own prospect",
            "- **Content:** Full body.",
            "- **Link:** https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "",
        ]) + self.body("cross-vault-prospect-twin")
        write(other_root, "resources/ideas/some-deal/sources/20260913 Original.md", note_text)
        write(self.root, "triage/20260913 Visit debrief 88604c.md", note_text)
        entries = [{"name": "Alpha", "path": str(self.root)},
                  {"name": "Beta", "path": str(other_root)}]
        ledger_mailboxes = {"x@example-work.com": {
            "1a0c556d2559b07c": {"routed": ["Alpha"]},  # routed here only
        }}
        loose = build_loose(self.root, entries, "Alpha", ledger_mailboxes)
        item = next(i for i in loose if i["name"] == "20260913 Visit debrief 88604c.md")
        self.assertEqual(item["note"]["routed_vaults"], [])
        self.assertEqual(item["note"]["routed_from"], "ledger")
        self.assertEqual(item["note"]["mentioned_vaults"], ["Beta"])
        self.assertEqual(item["cross_vault"],
                         [{"vault": "Beta",
                           "path": "resources/ideas/some-deal/sources/20260913 Original.md"}])

    def test_cross_vault_names_an_unreadable_vault_rather_than_dropping_it(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write(self.root, "triage/20260913 Note 91af05.md",
             "\n".join(["# A note", "",
                       "- **Source:** connector: google-workspace (x@example-work.com)",
                       "- **From:** Someone <x@example-work.com>",
                       "- **Received:** 2026-09-13T10:00:00+02:00",
                       "- **Routed:** also relevant to Gamma", "- **Content:** Full body.",
                       "- **Link:** https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c",
                       "", ""]) + self.body("padding-content"))
        missing_root = Path(tmp.name) / "does-not-exist"
        entries = [{"name": "Alpha", "path": str(self.root)},
                  {"name": "Gamma", "path": str(missing_root)}]
        loose = build_loose(self.root, entries, "Alpha", {})
        item = next(i for i in loose if i["name"] == "20260913 Note 91af05.md")
        self.assertEqual(item["cross_vault"], [{"vault": "Gamma", "unreadable": True}])

    def mail_note(self, routed, body_word):
        return "\n".join([
            "# A note", "",
            "- **Source:** connector: google-workspace (x@example-work.com)",
            "- **From:** Someone <x@example-work.com>",
            "- **Received:** 2026-09-13T10:00:00+02:00",
            f"- **Routed:** {routed}", "- **Content:** Full body.",
            "- **Link:** https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "",
        ]) + self.body(body_word)

    def test_a_same_size_file_with_different_bytes_is_no_cross_vault_twin(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        other_root = Path(tmp.name) / "Beta"
        note_text = self.mail_note("also relevant to Beta", "aaaaaaaa")
        write(self.root, "triage/20260913 Note 88604c.md", note_text)
        # Same length, one different byte: content decides, never the size alone.
        write(other_root, "resources/ideas/deal/sources/20260913 Other.md",
              note_text.replace("aaaaaaaa", "aaaaaaab", 1))
        entries = [{"name": "Alpha", "path": str(self.root)},
                   {"name": "Beta", "path": str(other_root)}]
        loose = build_loose(self.root, entries, "Alpha", {})
        self.assertEqual(loose[0]["cross_vault"], [])

    def test_a_mail_note_naming_no_other_vault_checks_none(self):
        # Gamma's path is missing: a walk of it would come back unreadable, so an empty
        # list here shows no vault was walked at all.
        write(self.root, "triage/20260913 Note 88604c.md",
              self.mail_note("this vault only", "solo-note-content"))
        entries = [{"name": "Alpha", "path": str(self.root)},
                   {"name": "Gamma", "path": str(self.root / "no-such-vault")}]
        loose = build_loose(self.root, entries, "Alpha", {})
        self.assertTrue(loose[0]["note"]["mail_note"])
        self.assertEqual(loose[0]["cross_vault"], [])

    def test_a_vault_whose_walk_fails_is_unreadable_not_dropped(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        other_root = Path(tmp.name) / "Beta"
        other_root.mkdir()
        write(self.root, "triage/20260913 Note 88604c.md",
              self.mail_note("also relevant to Beta", "walk-fails-content"))
        entries = [{"name": "Alpha", "path": str(self.root)},
                   {"name": "Beta", "path": str(other_root)}]
        real_hashes = triage_scan.hashes

        def denied_in_other_vaults(root, **kwargs):
            if Path(root) == other_root:
                raise PermissionError("access denied")
            return real_hashes(root, **kwargs)

        with mock.patch("triage_scan.hashes", side_effect=denied_in_other_vaults):
            loose = build_loose(self.root, entries, "Alpha", {})
        self.assertEqual(loose[0]["cross_vault"], [{"vault": "Beta", "unreadable": True}])


# -------------------------------------------------------------------------------- inbound

class Inbound(VaultCase):

    def test_a_percent_encoded_link_to_a_triage_file_is_found(self):
        # A real --test finding: a delete must never break an inbound link, percent-encoding
        # included.
        write(self.root, "triage/20260920 Some Notice.md", self.padding())
        write(self.root, "areas/network/someone.md",
             "# Someone\n\nSee [the notice]"
             "(../../triage/20260920%20Some%20Notice.md) for details.\n")
        loose = build_loose(self.root, [], "Alpha", {})
        item = next(i for i in loose if i["name"] == "20260920 Some Notice.md")
        self.assertEqual(len(item["inbound"]), 1)
        self.assertEqual(item["inbound"][0]["file"], "areas/network/someone.md")

    def test_a_notes_mention_of_its_own_name_is_not_inbound(self):
        write(self.root, "triage/20260920 Some Notice.md",
              "# Some Notice\n\nStaged as `triage/20260920 Some Notice.md`.\n" + self.padding())
        write(self.root, "areas/network/someone.md",
              "# Someone\n\nSee `triage/20260920 Some Notice.md` for details.\n")
        loose = build_loose(self.root, [], "Alpha", {})
        self.assertEqual(loose[0]["inbound"],
                         [{"file": "areas/network/someone.md", "line": 3, "shape": "backtick"}])

    def padding(self):
        return "Body content well past the minimum hash size floor for this test file.\n" * 5


# -------------------------------------------------------------------------- loose item misc

class LooseItemMisc(VaultCase):

    def test_gitkeep_is_ignored(self):
        write(self.root, "triage/.gitkeep", "")
        loose = build_loose(self.root, [], "Alpha", {})
        self.assertEqual(loose, [])

    def test_a_readme_is_flagged(self):
        write(self.root, "triage/README.md", "# Do not keep this here\n")
        loose = build_loose(self.root, [], "Alpha", {})
        item = loose[0]
        self.assertTrue(item["readme"])

    def test_a_pdf_and_its_markdown_twin_are_one_item(self):
        write(self.root, "triage/20260920 Scan 1a2b3c.pdf", "not a real pdf, just bytes\n")
        write(self.root, "triage/20260920 Scan 1a2b3c.md", "Extracted text.\n")
        loose = build_loose(self.root, [], "Alpha", {})
        self.assertEqual(len(loose), 1)
        self.assertEqual(loose[0]["name"], "20260920 Scan 1a2b3c.pdf")
        self.assertEqual(loose[0]["twin"], "20260920 Scan 1a2b3c.md")
        self.assertEqual(loose[0]["kind"], "pdf")

    def test_kind_detection_covers_every_named_category(self):
        names = {
            "invoice.pdf": "pdf", "photo.jpg": "image", "note.md": "markdown",
            "readout.txt": "text", "stub.gdoc": "google-native", "bundle.zip": "archive",
            "mystery.xyz": "other",
        }
        for name, expected in names.items():
            write(self.root, f"triage/{name}", "content\n")
        loose = build_loose(self.root, [], "Alpha", {})
        got = {item["name"]: item["kind"] for item in loose}
        for name, expected in names.items():
            self.assertEqual(got[name], expected, name)

    def test_no_triage_folder_is_no_items_rather_than_an_error(self):
        (self.root / "triage").rmdir()
        self.assertEqual(build_loose(self.root, [], "Alpha", {}), [])
        self.assertEqual(subdirectories_block(self.root), [])


# --------------------------------------------------------------------------- subdirectories

class Subdirectories(VaultCase):

    def test_an_underscore_prefixed_subdirectory_is_flagged_as_handoff(self):
        write(self.root, "triage/_handover/a.pdf", "x\n")
        write(self.root, "triage/_handover/b.pdf", "x\n")
        write(self.root, "triage/normal-batch/c.pdf", "x\n")
        subs = subdirectories_block(self.root)
        by_name = {s["name"]: s for s in subs}
        self.assertTrue(by_name["_handover"]["handoff"])
        self.assertEqual(by_name["_handover"]["files"], 2)
        self.assertFalse(by_name["normal-batch"]["handoff"])

    def test_empty_triage_reports_empty(self):
        report = self.plan()
        self.assertTrue(report["items"]["empty"])
        self.assertFalse(report["items"]["only_subdirectories"])

    def test_only_subdirectories_reports_that_and_not_empty(self):
        write(self.root, "triage/_handover/a.pdf", "x\n")
        report = self.plan()
        self.assertFalse(report["items"]["empty"])
        self.assertTrue(report["items"]["only_subdirectories"])

    def test_the_manifest_line_names_each_subdirectory_with_its_file_count(self):
        # approval.md's manifest line, printed as it stands: runs that worded it themselves
        # dropped the "not asked" a reader relies on.
        write(self.root, "triage/_handover/a.pdf", "x\n")
        write(self.root, "triage/_handover/b.pdf", "x\n")
        write(self.root, "triage/batch/c.pdf", "x\n")
        self.assertEqual(self.plan()["items"]["subdirectories_line"],
                         "Subdirectories, not asked: triage/_handover/ (2 files), "
                         "triage/batch/ (1 file)")

    def test_no_subdirectories_means_no_manifest_line(self):
        self.assertIsNone(subdirectories_line([]))
        self.assertIsNone(self.plan()["items"]["subdirectories_line"])


# ------------------------------------------------------------------------------- same thread

class SameThread(unittest.TestCase):

    def test_two_notes_sharing_a_hash_are_grouped(self):
        items = [
            {"name": "20260920 Subject 88604c.md", "kind": "markdown"},
            {"name": "20260921 Subject 88604c 2.md", "kind": "markdown"},
            {"name": "20260921 Unrelated 47ace9.md", "kind": "markdown"},
        ]
        got = same_thread_block(items)
        self.assertEqual(got, {"88604c": ["20260920 Subject 88604c.md",
                                          "20260921 Subject 88604c 2.md"]})

    def test_only_markdown_in_the_staged_note_shape_is_grouped(self):
        items = [
            {"name": "20260920 Subject 88604c.md", "kind": "markdown"},
            {"name": "20260920 Scan 88604c.pdf", "kind": "pdf"},
            {"name": "88604c.md", "kind": "markdown"},  # no date: not the staged shape
        ]
        self.assertEqual(same_thread_block(items), {})

    def test_two_notes_sharing_a_conversation_id_are_grouped_across_hashes(self):
        # One conversation staged from two mailboxes: two thread ids, so two filename
        # hashes, and only the Conversation id line joins them.
        conv = {"conversation_id": "conv-1"}
        items = [
            {"name": "20260920 Subject 88604c.md", "kind": "markdown", "note": conv},
            {"name": "20260920 Subject 47ace9.md", "kind": "markdown", "note": dict(conv)},
            {"name": "20260921 Subject 47ace9 2.md", "kind": "markdown", "note": None},
            {"name": "20260921 Other 1b2c3d.md", "kind": "markdown",
             "note": {"conversation_id": "conv-2"}},
        ]
        self.assertEqual(same_thread_block(items), {"conv-1": [
            "20260920 Subject 47ace9.md", "20260920 Subject 88604c.md",
            "20260921 Subject 47ace9 2.md"]})


# --------------------------------------------------------------------------- over threshold

class OverThreshold(VaultCase):

    def test_exactly_twelve_open_items_is_flagged(self):
        lines = "\n".join(f"- [ ] Item {n}" for n in range(12))
        write(self.root, "projects/acme/actions.md", f"# Acme - Actions\n\n{lines}\n")
        rows = over_threshold_block(self.root)
        self.assertEqual(rows, [{"file": "projects/acme/actions.md", "open": 12}])

    def test_eleven_open_items_is_not_flagged(self):
        lines = "\n".join(f"- [ ] Item {n}" for n in range(11))
        write(self.root, "projects/acme/actions.md", f"# Acme - Actions\n\n{lines}\n")
        self.assertEqual(over_threshold_block(self.root), [])


# -------------------------------------------------------------------------------- snapshot

class Snapshot(VaultCase):

    def test_the_snapshot_is_read_back_by_the_librarys_changed(self):
        write(self.root, "triage/a.md", "original content\n")
        write(self.root, "triage/b.md", "other content\n")
        snap = build_snapshot(self.root)
        self.assertEqual(changed(snap), [])
        write(self.root, "triage/a.md", "edited content\n")
        diffs = changed(snap)
        self.assertEqual(len(diffs), 1)
        self.assertTrue(diffs[0].endswith("a.md") or "a.md" in diffs[0])

    def test_a_pdfs_markdown_twin_is_held_although_it_is_not_its_own_item(self):
        write(self.root, "triage/scan.pdf", "%PDF\n")
        write(self.root, "triage/scan.md", "extracted\n")
        self.assertEqual(sorted(Path(p).name for p in build_snapshot(self.root)),
                         ["scan.md", "scan.pdf"])


# ---------------------------------------------------------------------------------- ledger

class IngestLedgerBlock(VaultCase):

    def test_a_missing_ingest_ledger_reports_not_exists_with_no_error(self):
        report = self.plan()
        self.assertFalse(report["ingest_ledger"]["exists"])
        self.assertIsNone(report["ingest_ledger"]["load_error"])

    def test_a_malformed_ledger_is_reported_and_routed_vaults_is_null_not_a_guess(self):
        # A malformed ledger dedups against nothing (sources.md's own rule for the seen-
        # ledger applies here too): note.routed_vaults comes back null, never an empty guess
        # that would read as "confirmed nowhere else", and the failure is visible in the
        # scan's own output rather than swallowed.
        path = self.home / "cache" / "ingest" / "ledger.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        write_registry(self.home, [
            {"name": "Alpha", "path": str(self.root), "kind": "personal",
             "active": True},
            {"name": "Beta", "path": str(self.home / "not-read"), "kind": "personal",
             "active": True},
        ])
        write(self.root, "triage/20260920 Note 88604c.md", "\n".join([
            "# Note", "",
            "- **Source:** connector: google-workspace (x@example-work.com)",
            "- **From:** Someone <x@example-work.com>",
            "- **Received:** 2026-09-20T10:00:00+02:00",
            "- **Routed:** also relevant to Beta", "- **Content:** Full body.",
            "- **Link:** https://mail.google.com/mail/u/0/#inbox/1a0c556d2559b07c", "",
        ]) + "Padding well past the minimum hash size floor for this test file.\n" * 5)
        report = self.plan()
        self.assertTrue(report["ingest_ledger"]["exists"])
        self.assertIsNotNone(report["ingest_ledger"]["load_error"])
        note = report["items"]["loose"][0]["note"]
        self.assertIsNone(note["routed_vaults"])
        self.assertIsNone(note["routed_from"])
        self.assertEqual(note["mentioned_vaults"], ["Beta"])  # the text scan is unaffected


class SeenLedger(VaultCase):

    def test_missing_ledger_reports_not_exists(self):
        block = seen_ledger_block(str(self.home), "Alpha")
        self.assertFalse(block["exists"])
        self.assertEqual(block["entries"], 0)

    def test_entries_and_legacy_are_counted(self):
        path = self.home / "cache" / "triage-email" / "Alpha.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "thread-full": {"disposition": "actioned", "date": "2026-09-10",
                            "seen_through": "<msg-1>",
                            "seen_date": "2026-09-10T01:00:00+02:00"},
            "thread-legacy": {"disposition": "noted", "date": "2026-09-01"},
        }), encoding="utf-8")
        block = seen_ledger_block(str(self.home), "Alpha")
        self.assertTrue(block["exists"])
        self.assertEqual(block["entries"], 2)
        self.assertEqual(block["legacy"], 1)

    def test_a_ledger_that_fails_to_parse_is_reported(self):
        path = self.home / "cache" / "triage-email" / "Alpha.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        block = seen_ledger_block(str(self.home), "Alpha")
        self.assertIsNotNone(block["load_error"])

    def test_a_ledger_that_is_not_an_object_is_reported(self):
        path = self.home / "cache" / "triage-email" / "Alpha.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(["1a0c556d2559b07c"]), encoding="utf-8")
        block = seen_ledger_block(str(self.home), "Alpha")
        self.assertEqual((block["exists"], block["entries"], block["load_error"]),
                         (True, 0, "not a JSON object"))


# ---------------------------------------------------------------------------------- threads

class ThreadsFold(VaultCase):

    def test_a_fetched_thread_already_staged_folds_into_that_note(self):
        # A real --test finding: a fetched thread already staged as a note is that note.
        write(self.root, "triage/20260920 Subject 88604c.md", "# Subject\n\nBody.\n")
        threads_data = [{"thread_id": "1a0c556d2559b07c"}]  # thread_hash -> "88604c"
        report = self.plan(threads=threads_data)
        self.assertIn("threads", report)
        entry = report["threads"][0]
        self.assertEqual(entry["thread_hash"], "88604c")
        self.assertEqual(entry["staged_notes"], ["20260920 Subject 88604c.md"])

    def test_a_ledgered_thread_carries_its_watermark_verdict(self):
        ledger_path = self.home / "cache" / "triage-email" / "Alpha.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps({
            "1a0c556d2559b07c": {"seen_through": "<msg-1>",
                                "seen_date": "2026-09-10T01:00:00+02:00"},
        }), encoding="utf-8")
        threads_data = [{"thread_id": "1a0c556d2559b07c", "newest_key": "<msg-1>"}]
        report = self.plan(threads=threads_data)
        self.assertEqual(report["threads"][0]["watermark"]["verdict"], "seen")

    def test_a_grown_thread_is_flagged_grown(self):
        ledger_path = self.home / "cache" / "triage-email" / "Alpha.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps({
            "1a0c556d2559b07c": {"seen_through": "<msg-1>",
                                "seen_date": "2026-09-10T01:00:00+02:00"},
        }), encoding="utf-8")
        threads_data = [{"thread_id": "1a0c556d2559b07c", "newest_key": "<msg-2>"}]
        report = self.plan(threads=threads_data)
        self.assertEqual(report["threads"][0]["watermark"]["verdict"], "grown")

    def test_no_threads_argument_leaves_the_key_out(self):
        report = self.plan()
        self.assertNotIn("threads", report)

    def test_an_unreadable_seen_ledger_folds_every_thread_as_new(self):
        # The failure is reported in seen_ledger; the fold never drops a thread over it.
        ledger_path = self.home / "cache" / "triage-email" / "Alpha.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        for text in ("not json", json.dumps(["1a0c556d2559b07c"])):
            ledger_path.write_text(text, encoding="utf-8")
            report = self.plan(threads=[{"thread_id": "1a0c556d2559b07c",
                                         "newest_key": "<msg-1>"}])
            self.assertIsNotNone(report["seen_ledger"]["load_error"], text)
            self.assertIsNone(report["threads"][0]["ledger"], text)
            self.assertEqual(report["threads"][0]["watermark"]["verdict"], "new", text)

    def test_an_entry_that_is_not_an_object_is_skipped_and_one_with_no_id_kept(self):
        write(self.root, "triage/20260920 Subject 88604c.md", "# Subject\n\nBody.\n")
        report = self.plan(threads=["1a0c556d2559b07c", {"newest_date": "2026-09-20T10:00:00Z"}])
        self.assertEqual(report["threads"], [{
            "thread_id": None, "thread_hash": None, "staged_notes": [], "ledger": None,
            "watermark": {"verdict": "new", "legacy": False, "watermark": None}}])


# ------------------------------------------------------------------------------ command line

class CommandLine(VaultCase):
    """The call scan.md documents: exit codes, `--now`, and a `--threads` file."""

    resolved = True  # main() resolves --vault before it reads the registry

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--vault", str(self.root), "--paraos-home", str(self.home), *argv])
        return code, out.getvalue()

    def usage_error(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            self.run_main(*argv)
        self.assertEqual(stop.exception.code, 2)
        return err.getvalue()

    def threads_file(self, text):
        path = self.home / "threads.json"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_a_vault_root_prints_the_whole_report_and_exits_0(self):
        write(self.root, "triage/20260920 Subject 88604c.md", "# Subject\n\nBody.\n")
        code, out = self.run_main("--now", "2026-09-22T12:00:00+00:00", "--indent", "2")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(set(report), {"vault", "sources", "ingest", "ingest_ledger", "items",
                                       "seen_ledger", "over_threshold", "snapshot",
                                       "snapshot_folders", "saved_to", "save_error"})
        self.assertEqual([i["name"] for i in report["items"]["loose"]],
                         ["20260920 Subject 88604c.md"])
        self.assertEqual(len(report["snapshot"]), 1)

    def test_now_with_a_trailing_z_is_the_instant_every_age_is_measured_from(self):
        write_run(self.home, "20260922-110000.json", {
            "mode": "write", "started_at": "2026-09-22T11:00:00+00:00", "files_written": [],
            "counts": {"per_vault": {"Alpha": 0}},
        })
        _, out = self.run_main("--now", "2026-09-22T12:00:00Z")
        ingest = json.loads(out)["ingest"]
        self.assertEqual(ingest["newest_write"]["age_hours"], 1.0)
        self.assertTrue(ingest["covered"])

    def test_now_with_no_offset_is_read_as_local_time_not_rejected(self):
        # A naive instant compared against a log's aware one would raise, not answer.
        write_run(self.home, "20260922-110000.json", {
            "mode": "write", "started_at": "2026-09-22T11:00:00+00:00", "files_written": [],
        })
        code, out = self.run_main("--now", "2026-09-22T12:00:00")
        self.assertEqual(code, 0)
        self.assertIsInstance(json.loads(out)["ingest"]["newest_write"]["age_hours"], float)

    def test_a_now_that_is_no_instant_is_a_usage_error(self):
        self.assertIn("--now wants an ISO-8601 instant", self.usage_error("--now", "yesterday"))

    def test_a_threads_file_folds_against_the_staged_notes(self):
        write(self.root, "triage/20260920 Subject 88604c.md", "# Subject\n\nBody.\n")
        path = self.threads_file(json.dumps([{"thread_id": "1a0c556d2559b07c"}]))
        _, out = self.run_main("--now", "2026-09-22T12:00:00Z", "--threads", path)
        self.assertEqual(json.loads(out)["threads"][0]["staged_notes"],
                         ["20260920 Subject 88604c.md"])

    def test_a_threads_file_that_cannot_be_read_is_a_usage_error(self):
        missing = str(self.home / "no-such-threads.json")
        self.assertIn("cannot read", self.usage_error("--threads", missing))
        broken = self.threads_file("[{not json")
        self.assertIn("cannot read", self.usage_error("--threads", broken))

    def test_a_threads_file_holding_no_list_is_a_usage_error(self):
        path = self.threads_file(json.dumps({"thread_id": "1a0c556d2559b07c"}))
        self.assertIn("must hold a JSON list", self.usage_error("--threads", path))


class SavedCopy(CommandLine):
    """The copy `paraos_vault.py changed` re-checks before each delete or move, kept by the
    scan itself: runs that were told to redirect the output to a file mostly did not."""

    def test_the_report_is_kept_outside_the_vault_and_matches_what_was_printed(self):
        write(self.root, "triage/note.md", "# Note\n")
        code, out = self.run_main("--now", "2026-09-22T12:00:00Z")
        self.assertEqual(code, 0)
        report = json.loads(out)
        saved = Path(report["saved_to"])
        self.assertIsNone(report["save_error"])
        self.assertEqual(saved.parent, self.home / "data" / "scans")
        self.assertEqual(saved.name, "triage-Alpha-20260922T120000.json")
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), report)
        # The re-check scripts.md names, run as the skill runs it, against the saved path.
        library = SCRIPT.parents[2] / "para-shared" / "scripts" / "paraos_vault.py"
        recheck = [sys.executable, str(library), "changed", str(saved)]
        self.assertEqual(subprocess.run(recheck, capture_output=True, timeout=60).returncode, 0)
        write(self.root, "triage/note.md", "# Note, edited\n")
        self.assertEqual(subprocess.run(recheck, capture_output=True, timeout=60).returncode, 1)

    def test_a_file_arriving_in_triage_after_the_scan_fails_the_recheck(self):
        # Six unapproved notes went to the trash once: they arrived from a concurrent ingest
        # after the scan, and the re-check only looked at the files it had snapshotted.
        write(self.root, "triage/note.md", "# Note\n")
        _, out = self.run_main("--now", "2026-09-22T12:00:00Z")
        library = SCRIPT.parents[2] / "para-shared" / "scripts" / "paraos_vault.py"
        recheck = [sys.executable, str(library), "changed", json.loads(out)["saved_to"]]
        late = write(self.root, "triage/20260922 Late arrival 1f2e3d.md", "# Late\n")
        result = subprocess.run(recheck, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 1)
        got = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(got["changed"], [])
        self.assertEqual([Path(p).name for p in got["arrived"]], [late.name])

    def test_copies_older_than_a_week_are_pruned_and_newer_ones_kept(self):
        folder = self.home / "data" / "scans"
        old = write(folder, "triage-Alpha-20260901T000000.json", "{}\n")
        recent = write(folder, "triage-Alpha-20260921T000000.json", "{}\n")
        instant = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc).timestamp()
        os.utime(old, (instant - 10 * 86400, instant - 10 * 86400))
        os.utime(recent, (instant - 86400, instant - 86400))
        self.run_main("--now", "2026-09-22T12:00:00Z")
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_a_copy_that_would_land_inside_the_vault_is_refused(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--vault", str(self.root), "--paraos-home", str(self.root / ".paraos"),
                         "--now", "2026-09-22T12:00:00Z"])
        report = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertIsNone(report["saved_to"])
        self.assertIn("inside the vault", report["save_error"])
        self.assertFalse((self.root / ".paraos").exists())

    def test_a_copy_that_cannot_be_written_is_reported_and_the_scan_still_answers(self):
        write(self.home, "data/scans", "a file where the folder should be\n")
        code, out = self.run_main("--now", "2026-09-22T12:00:00Z")
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertIsNone(report["saved_to"])
        self.assertIn("cannot write", report["save_error"])

    def test_a_prune_that_fails_leaves_the_scan_answering(self):
        write(self.home, "data/scans/triage-Alpha-20260901T000000.json", "{}\n")
        with mock.patch.object(Path, "unlink", side_effect=OSError("locked")):
            code, out = self.run_main("--now", "2026-09-22T12:00:00Z")
        self.assertEqual(code, 0)
        self.assertIsNone(json.loads(out)["save_error"])


class RunAsAScript(unittest.TestCase):
    """What the skill actually runs: the file itself, from whatever folder the shell is in."""

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)

    def test_run_from_another_folder_it_finds_the_library_and_writes_utf8(self):
        # A Windows pipe defaults to a codepage that cannot encode a vault's own names; an
        # ASCII stdout stands in for it on every platform.
        vault = self.base / "Alpha"
        for d in ("projects", "areas", "archive", "triage"):
            (vault / d).mkdir(parents=True)
        write(vault, "CLAUDE.md", "# Vault\n")
        write(vault, "triage/20260920 Call Øyan 88604c.md", "# Call Øyan\n\nNotes.\n")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(vault), "--now",
             "2026-09-22T12:00:00Z", "--paraos-home", str(self.base / "home")],
            cwd=self.base, capture_output=True, timeout=60,
            env=dict(os.environ, PYTHONIOENCODING="ascii"))
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        report = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual([i["name"] for i in report["items"]["loose"]],
                         ["20260920 Call Øyan 88604c.md"])

    def test_a_missing_shared_library_exits_2_and_names_the_fallback(self):
        # scripts.md: a missing shared library is a by-hand fallback, never a traceback.
        isolated = self.base / "skills" / "para-triage" / "scripts"
        isolated.mkdir(parents=True)
        shutil.copy(SCRIPT, isolated / "triage_scan.py")
        result = subprocess.run([sys.executable, str(isolated / "triage_scan.py"), "--vault", "."],
                                cwd=self.base, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("triage_scan:", result.stderr)
        self.assertIn("scan by hand", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
