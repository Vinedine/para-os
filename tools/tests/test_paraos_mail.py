"""Tests for paraos_mail.py: mail threads, the triage notes they become, and the ledgers
that track them."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "base" / ".claude" / "skills" / "para-shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from paraos_mail import (  # noqa: E402
    ingest_ledger, ingest_logs, log_instant, note_name_parts, thread_hash, unanswered,
    watermark, written_under,
)


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


class Unanswered(unittest.TestCase):
    """How many working days a sent message has gone unanswered (connectors.md's sent pass)."""

    NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone(timedelta(hours=2)))

    def test_a_message_sent_a_week_ago_with_no_reply_is_waiting(self):
        self.assertEqual(unanswered("2026-10-02T10:00:00+00:00", self.NOW),
                         {"since": "2026-10-02", "working_days": 5, "waiting": True})

    def test_four_working_days_is_not_yet_waiting(self):
        self.assertEqual(unanswered("2026-10-05T10:00:00Z", self.NOW),
                         {"since": "2026-10-05", "working_days": 4, "waiting": False})

    def test_the_day_it_went_out_is_read_in_the_runs_own_timezone(self):
        # 23:30 UTC on Thursday the 1st is already Friday the 2nd at +02:00: four, not five.
        now = self.NOW - timedelta(days=1)
        got = unanswered("2026-10-01T23:30:00+00:00", now)
        self.assertEqual((got["since"], got["working_days"]), ("2026-10-02", 4))

    def test_a_bare_day_is_read_as_that_day(self):
        self.assertEqual(unanswered("2026-10-02", self.NOW)["working_days"], 5)

    def test_a_date_that_does_not_read_is_unknown_never_zero(self):
        for sent in (None, "", "last Friday", "2026-10-02T10:00:00"):
            with self.subTest(sent=sent):
                self.assertEqual(unanswered(sent, self.NOW),
                                 {"since": None, "working_days": None, "waiting": None})


if __name__ == "__main__":
    unittest.main(verbosity=1)
