#!/usr/bin/env python3
"""Unit tests for pocket.py. No network, no Pocket account, no API key: HTTP is faked at
urllib.request.urlopen, and files go to temporary directories.

Run from the repo root:
    py -m unittest integrations/pocket/test_pocket.py
"""
import contextlib
import email.utils
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pocket", HERE / "pocket.py")
pocket = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pocket)

UTC_PLUS_2 = timezone(timedelta(hours=2))


def http_error(url, code, headers=None, body=b"boom"):
    return urllib.error.HTTPError(url, code, "error", headers or {}, io.BytesIO(body))


class Sanitize(unittest.TestCase):
    def test_illegal_characters_become_spaces(self):
        self.assertEqual(pocket.sanitize('Q3/Q4 plan: "go"'), "Q3 Q4 plan go")

    def test_edges_trimmed_after_truncation(self):
        self.assertEqual(pocket.sanitize("  ..Review.  "), "Review")
        self.assertFalse(pocket.sanitize("a" * 79 + " .b").endswith((" ", ".")))
        self.assertLessEqual(len(pocket.sanitize("x" * 200)), 80)

    def test_keeps_diacritics(self):
        self.assertEqual(pocket.sanitize("Naïve café plan"), "Naïve café plan")


class Dates(unittest.TestCase):
    def test_z_and_offsets_and_long_fractions(self):
        a = pocket.parse_when("2026-09-12T22:30:00.123456789Z")
        self.assertEqual((a.hour, a.microsecond, a.utcoffset()), (22, 123456, timedelta(0)))
        b = pocket.parse_when("2026-09-12T10:00:00+02:00")
        self.assertEqual(b.utcoffset(), timedelta(hours=2))
        self.assertEqual(pocket.parse_when("2026-09-12 10:00").utcoffset(), timedelta(0))

    def test_garbage_is_none(self):
        self.assertIsNone(pocket.parse_when("yesterday"))
        self.assertIsNone(pocket.parse_when(None))

    def test_local_date_crosses_midnight(self):
        rec = {"recording_at": "2026-09-12T22:30:00Z", "created_at": "2026-09-13T08:00:00Z"}
        self.assertEqual(f"{pocket.recorded_at(rec, UTC_PLUS_2):%Y%m%d %H:%M}", "20260913 00:30")

    def test_falls_back_to_created_at(self):
        rec = {"recording_at": "", "created_at": "2026-09-13T08:00:00Z"}
        self.assertEqual(pocket.recorded_at(rec, timezone.utc).day, 13)


class Transcript(unittest.TestCase):
    def test_plain_string(self):
        self.assertEqual(pocket.transcript_md("  hello there  "), "hello there")

    def test_segments_merge_consecutive_speakers(self):
        segs = [{"speaker": 0, "text": "So,"}, {"speaker": 0, "text": "next point."},
                {"speaker": {"name": "Alex"}, "text": "Yes."}]
        self.assertEqual(pocket.transcript_md(segs), "**Speaker 0:** So, next point.\n\n**Alex:** Yes.")

    def test_wrapped_segment_list(self):
        self.assertEqual(pocket.transcript_md({"segments": [{"speaker_name": "Sam", "content": "Ok"}]}),
                         "**Sam:** Ok")

    def test_object_with_text(self):
        self.assertEqual(pocket.transcript_md({"id": "t1", "text": "full text"}), "full text")

    def test_unreadable_shape_is_empty_not_a_dump(self):
        self.assertEqual(pocket.transcript_md({"id": "t1", "status": "processing"}), "")
        self.assertEqual(pocket.transcript_md(None), "")

    def test_an_id_or_status_string_is_not_a_transcript(self):
        self.assertEqual(pocket.transcript_md("tr_123"), "")
        self.assertEqual(pocket.transcript_md(["tr_123", "tr_124"]), "")
        self.assertEqual(pocket.transcript_md("processing"), "")


class Summaries(unittest.TestCase):
    def test_id_keyed_object(self):
        s = {"abc": {"title": "Meeting notes", "markdown": "# Core\n• point"}, "def": {"status": "pending"}}
        self.assertEqual(pocket.summaries_md(s), [("Meeting notes", "# Core\n- point")])

    def test_single_object_and_template_name(self):
        self.assertEqual(pocket.summaries_md({"template": {"name": "Default"}, "content": {"text": "x"}}),
                         [("Default", "x")])

    def test_list_and_string(self):
        self.assertEqual(pocket.summaries_md([{"markdown": "a"}, ""]), [(None, "a")])
        self.assertEqual(pocket.summaries_md("A short summary."), [(None, "A short summary.")])

    def test_empty(self):
        self.assertEqual(pocket.summaries_md(None), [])
        self.assertEqual(pocket.summaries_md({}), [])

    def test_a_status_object_is_not_a_summary(self):
        self.assertEqual(pocket.summaries_md({"status": "pending"}), [])

    def test_an_unfinished_summary_object_yields_neither_id_nor_status(self):
        self.assertEqual(pocket.summaries_md({"id": "abc", "processingStatus": "processing"}), [])

    def test_a_list_of_ids_is_not_a_summary(self):
        self.assertEqual(pocket.summaries_md(["sum-0001"]), [])

    def test_id_keyed_string_values_are_not_summaries(self):
        self.assertEqual(pocket.summaries_md({"sum-0001": "sum-0001", "sum-0002": "pending"}), [])

    def test_a_bare_status_string_is_not_a_summary(self):
        self.assertEqual(pocket.summaries_md("pending"), [])


class LiveShape(unittest.TestCase):
    """The payload shape the readers are built on, with synthetic content."""

    REC = {
        "id": "rec-0001", "title": "ACME - Weekly", "duration": 3900, "language": "en", "state": "completed",
        "recording_at": "2030-01-15T09:00:00Z", "tags": [],
        "transcript": {"metadata": {"duration": 3899.5, "source": "asr"},
                       "segments": [{"start": 0.66, "end": 28.84, "text": "First part.", "originalText": "first part"},
                                    {"start": 29.46, "end": 54.14, "text": "Second part.", "originalText": "second"},
                                    {"start": 3725.2, "end": 3730.0, "text": "Last.", "originalText": "last"}],
                       "text": "First part. Second part. Last."},
        "summarizations": {"sum-0001": {
            "id": "item-0001", "summarizationId": "sum-0001", "processingStatus": "completed",
            "v2": {"summary": {"markdown": "The discussion.\n\n## Points\n- one", "version": "1"},
                   "mindMap": {"nodes": [{"node_id": "root", "title": "Map"}], "type": "flow"},
                   "actionItems": {"actions": [
                       {"assignee": "me", "context": "Call the supplier.", "dueDate": None,
                        "isCompleted": False, "label": "Book a call", "priority": "medium"},
                       {"assignee": "Sam", "context": "Request a quote.", "dueDate": "2030-01-20T00:00:00Z",
                        "isCompleted": True, "label": "Quote"}]}},
            "v2SummaryStatus": {"status": "completed"}}},
    }

    def test_summary_found_under_v2(self):
        self.assertEqual(pocket.summaries_md(self.REC["summarizations"]), [(None, "The discussion.\n\n## Points\n- one")])

    def test_pocket_timeline_block_becomes_bullets(self):
        md = ('Before.\n\n<pocket:timeline title="Next steps">\nWeek 1 | Travel | Back on Friday.\n'
              'Week 2 | Supplier\n</pocket:timeline>\n\nAfter.')
        self.assertEqual(pocket.summaries_md(md), [(None, "Before.\n\n**Next steps**\n\n"
                                                         "- **Week 1**: Travel · Back on Friday.\n"
                                                         "- **Week 2**: Supplier\n\nAfter.")])

    def test_unlabelled_segments_stay_separate_paragraphs_with_timestamps(self):
        self.assertEqual(pocket.transcript_md(self.REC["transcript"]),
                         "[00:00] First part.\n\n[00:29] Second part.\n\n[1:02:05] Last.")

    def test_action_items_are_bullets_not_checkboxes(self):
        md = pocket.action_items_md(self.REC["summarizations"])
        self.assertEqual(md, "- **Book a call**: Call the supplier.\n"
                             "- **Quote**: Request a quote. (for Sam, due 2030-01-20, done in Pocket)")
        self.assertNotIn("[ ]", md)

    def test_note_is_written_not_held(self):
        rec = self.REC
        tr, sums = pocket.transcript_md(rec["transcript"]), pocket.summaries_md(rec["summarizations"])
        self.assertIsNone(pocket.readiness(rec, tr, sums))
        md = pocket.render_note(rec, datetime(2030, 1, 15, 11, 0), tr, sums, pocket.action_items_md(rec["summarizations"]))
        self.assertIn("duration_min: 65", md)
        self.assertIn("_2030-01-15 11:00 · 65 min_", md)
        self.assertNotIn("language:", md)
        self.assertIn("### Points", md)
        self.assertLess(md.index("## Summary"), md.index("## Action items"))
        self.assertLess(md.index("## Action items"), md.index("## Transcript"))


class Readiness(unittest.TestCase):
    def test_readable_both_is_written(self):
        self.assertIsNone(pocket.readiness({}, "t", [(None, "s")]))

    def test_reported_errors_write_instead_of_hold(self):
        rec = {"transcript_error": "audio corrupt", "summarizations_errors": ["quota"]}
        self.assertIsNone(pocket.readiness(rec, "", []))
        md = pocket.render_note(rec, datetime(2026, 9, 13, 10, 0), "", [])
        self.assertIn("Pocket reported audio corrupt", md)
        self.assertIn("Pocket reported quota", md)

    def test_still_processing_is_a_processing_hold(self):
        self.assertEqual(pocket.readiness({"state": "processing"}, "", [])[0], "processing")

    def test_a_summary_still_processing_holds_a_finished_recording(self):
        rec = {"state": "completed", "summarizations": {"sum-0001": {"processingStatus": "processing"}}}
        self.assertEqual(pocket.readiness(rec, "t", [])[0], "processing")

    def test_finished_with_blank_fields_is_written_saying_so(self):
        for tr, sm in ((None, None), ({"segments": [], "text": ""}, {}),
                       ({"metadata": {"source": "asr"}, "segments": []},
                        {"sum-0001": {"processingStatus": "completed", "v2": {"summary": {"markdown": ""}}}})):
            rec = {"state": "completed", "transcript": tr, "summarizations": sm}
            self.assertIsNone(pocket.readiness(rec, pocket.transcript_md(tr), pocket.summaries_md(sm)), (tr, sm))
        md = pocket.render_note(rec, datetime(2026, 9, 13, 10, 0), "", [])
        self.assertIn("_(no transcript available)_", md)
        self.assertIn("_(no summary available)_", md)

    def test_words_the_readers_cannot_parse_are_an_unreadable_hold(self):
        rec = {"state": "completed", "transcript": {"utterances_v9": [{"words": "hello there"}]},
               "summarizations": {"sum-0001": {"v3": {"body_md": "The discussion went well."}}}}
        kind, why = pocket.readiness(rec, "", [])
        self.assertEqual(kind, "unreadable")
        self.assertIn("transcript", why)
        self.assertIn("summary", why)

    def test_an_unknown_state_with_a_blank_field_is_an_unreadable_hold(self):
        for state in ("archived", None):
            kind, _ = pocket.readiness({"state": state, "transcript": None}, "", [(None, "s")])
            self.assertEqual(kind, "unreadable", state)

    def test_every_in_progress_spelling_is_a_processing_hold(self):
        for state in ("recording", "new", "created", "waiting", "diarizing", "analyzing", "generating"):
            self.assertEqual(pocket.readiness({"state": state}, "t", [(None, "s")])[0], "processing", state)

    def test_a_summary_still_generating_holds_a_completed_recording(self):
        rec = {"state": "completed", "transcript": {"segments": [{"text": "Hello there."}]},
               "summarizations": {"sum-0001": {"v2SummaryStatus": {"status": "generating"}}}}
        self.assertEqual(pocket.readiness(rec, "Hello there.", [])[0], "processing")

    def test_a_summary_status_in_neither_list_holds_a_blank_summary_as_unreadable(self):
        rec = {"state": "completed", "summarizations": {"sum-0001": {"processingStatus": "reticulating"}}}
        kind, why = pocket.readiness(rec, "t", [])
        self.assertEqual(kind, "unreadable")
        self.assertIn("reticulating", why)

    def test_the_transcript_status_is_observed(self):
        done = {"sum-0001": {"processingStatus": "completed"}}
        busy = {"state": "completed", "transcript": {"status": "diarizing", "segments": []}, "summarizations": done}
        self.assertEqual(pocket.readiness(busy, "", [])[0], "processing")
        odd = {"state": "completed", "transcript": {"speakerStageStatus": "mulling", "segments": []}, "summarizations": done}
        self.assertEqual(pocket.readiness(odd, "", [])[0], "unreadable")
        final = {"state": "completed", "transcript": {"status": "completed", "speakerStageStatus": "skipped",
                                                      "segments": []}, "summarizations": done}
        self.assertIsNone(pocket.readiness(final, "", []))

    def test_an_unknown_status_does_not_hold_a_recording_with_nothing_blank(self):
        rec = {"state": "completed", "summarizations": {"sum-0001": {"processingStatus": "reticulating"}}}
        self.assertIsNone(pocket.readiness(rec, "t", [(None, "s")]))

    def test_names_errors_and_timestamps_are_not_unreadable_text(self):
        tr = {"segments": [], "metadata": {"source": "asr large model"}, "created_at": "2030-01-15 09:00:00",
              "error_message": "Model timed out"}
        sm = {"sum-0001": {"processingStatus": "completed", "title": "Weekly sync", "name": "Default template",
                           "template_name": "Meeting Notes", "templateId": "tpl one", "error": "Model timed out",
                           "message": "Nothing to summarise", "updated_at": "2030-01-15 09:05:00",
                           "v2": {"summary": {"markdown": ""}}}}
        rec = {"state": "completed", "transcript": tr, "summarizations": sm}
        self.assertIsNone(pocket.readiness(rec, pocket.transcript_md(tr), pocket.summaries_md(sm)))

    def test_multi_word_strings_count_only_where_text_is_expected(self):
        self.assertFalse(pocket.has_words({"speaker": "Speaker 1", "participants": ["Alex Smith"]}))
        self.assertFalse(pocket.has_words({"segments": [{"speaker_name": "Alex Smith", "text": ""}]}))
        self.assertTrue(pocket.has_words({"entries_v9": [{"words": "hello there"}]}))
        self.assertTrue(pocket.has_words("hello there"))

    def test_the_one_word_rule_applies_to_bare_strings_only(self):
        self.assertFalse(pocket.has_words("tr_123"))
        self.assertFalse(pocket.has_words({"segments": ["tr_123", "tr_124"]}))
        self.assertTrue(pocket.has_words({"v3": {"body_md": "Fine."}}))


class Demote(unittest.TestCase):
    def test_consecutive_from_base(self):
        self.assertEqual(pocket.demote("# A\n### B\n# C", 3), "### A\n#### B\n### C")
        self.assertEqual(pocket.demote("no headings"), "no headings")


class Routing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name)
        self.root = self.parent / "Acme"
        (self.parent / "Home").mkdir()
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def rec(self, title):
        return {"title": title}

    def test_single_vault_takes_everything_under_its_full_title(self):
        r = pocket.resolve(self.rec("ACME - Review"), {}, self.root, "Acme", "triage")
        self.assertEqual(r, {"vault": "Acme", "dir": self.root / "triage", "desc": "ACME - Review"})

    def test_self_and_sibling_case_insensitive(self):
        routes, warnings = pocket.build_routes({"ACME": ".", "HOME": "Home"}, "Acme", self.parent)
        self.assertEqual(warnings, [])
        self.assertEqual(pocket.resolve(self.rec("acme - Review with counsel"), routes, self.root, "Acme", "triage"),
                         {"vault": "Acme", "dir": self.root / "triage", "desc": "Review with counsel"})
        self.assertEqual(pocket.resolve(self.rec("HOME - Plumber"), routes, self.root, "Acme", "triage"), {"elsewhere": True})
        self.assertEqual(pocket.resolve(self.rec("HOME-Plumber"), routes, self.root, None, "triage")["dir"],
                         self.parent / "Home" / "triage")

    def test_prefix_needs_the_dash_like_granola(self):
        # Granola's rule exactly: an alphanumeric run, then a dash. "ACME Review" and a title
        # merely starting with the letters ("Acmeville - trip") are not prefixed.
        routes, _ = pocket.build_routes({"ACME": "."}, "Acme", self.parent)
        self.assertEqual(pocket.resolve(self.rec("ACME Review"), routes, self.root, "Acme", "triage"), {"unrouted": "none"})
        self.assertEqual(pocket.resolve(self.rec("Acmeville - trip"), routes, self.root, "Acme", "triage"), {"unrouted": "Acmeville"})
        self.assertEqual(pocket.resolve(self.rec("  ACME  -  Site  "), routes, self.root, "Acme", "triage")["desc"], "Site  ")

    def test_unrouted_names_its_prefix(self):
        routes, _ = pocket.build_routes({"ACME": "."}, "Acme", self.parent)
        self.assertEqual(pocket.resolve(self.rec("OPS - Standup"), routes, self.root, "Acme", "triage"), {"unrouted": "OPS"})
        self.assertEqual(pocket.resolve({}, routes, self.root, "Acme", "triage"), {"unrouted": "none"})

    def test_literal_own_name_on_another_machine_warns(self):
        _, warnings = pocket.build_routes({"Acme": "Acme - Documents"}, "Acme", self.parent)
        self.assertEqual(len(warnings), 1)
        self.assertIn('Use "."', warnings[0])


class Config(unittest.TestCase):
    def test_missing_is_single_vault(self):
        self.assertEqual(pocket.load_config(Path(tempfile.gettempdir()) / "nope" / "pocket.config.json"), {})

    def test_malformed_or_wrong_shape_stops(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pocket.config.json"
            for text in ("{not json", "[]", '{"route": ["Acme"]}'):
                p.write_text(text, encoding="utf-8")
                with self.assertRaises(SystemExit):
                    pocket.load_config(p)

    def test_key_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pocket.json"
            with self.assertRaises(SystemExit):
                pocket.load_key(p)
            p.write_text('{"api_key": "sk_wrong"}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                pocket.load_key(p)
            p.write_text('{"api_key": " pk_ok "}', encoding="utf-8")
            self.assertEqual(pocket.load_key(p), "pk_ok")


class Files(unittest.TestCase):
    def test_same_recording_is_detected_other_recording_gets_suffix(self):
        when = datetime(2026, 9, 13, 10, 0)
        rec = {"id": "aaaa1111", "title": "Project sync: status", "tags": [{"name": "Acme"}]}
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            path, exists = pocket.pick_path(folder, when, rec["title"], rec["id"])
            self.assertEqual((path.name, exists), ("20260913 Project sync status.md", False))
            path.write_text(pocket.render_note(rec, when, "t", [(None, "s")]), encoding="utf-8")
            self.assertEqual(pocket.pick_path(folder, when, rec["title"], rec["id"]), (path, True))
            other, exists = pocket.pick_path(folder, when, rec["title"], "bbbb2222")
            self.assertEqual((other.name, exists), ("20260913 Project sync status (bbbb22).md", False))

    def test_a_suffixed_file_of_another_recording_is_suffixed_past(self):
        when = datetime(2026, 9, 13, 10, 0)
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            taken = []
            for rid in ("rec-0001", "rec-0002", "rec-0003"):
                path, exists = pocket.pick_path(folder, when, "Sync", rid)
                self.assertFalse(exists, rid)
                self.assertNotIn(path, taken, rid)
                path.write_text(pocket.render_note({"id": rid, "title": "Sync"}, when, "t", [(None, "s")]),
                                encoding="utf-8")
                taken.append(path)
            for rid, path in zip(("rec-0001", "rec-0002", "rec-0003"), taken):
                self.assertEqual(pocket.pick_path(folder, when, "Sync", rid), (path, True))

    def test_front_matter_quotes_title(self):
        rec = {"id": "x", "title": 'A: "b"', "recorded_by": {"display_name": "Alex"}, "tags": [{"name": "Acme"}]}
        md = pocket.render_note(rec, datetime(2026, 9, 13, 10, 0), "t", [("One", "# H"), ("Two", "y")])
        self.assertIn('title: "A: \\"b\\""', md)
        self.assertIn('tags: ["Acme"]', md)
        self.assertIn("### One\n\n#### H", md)
        self.assertIn("pocket_id: x", md)
        front = md.split("---")[1]
        self.assertEqual(json.loads(front.split("title: ")[1].splitlines()[0]), 'A: "b"')

    def test_atomic_write_leaves_no_partial_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "triage" / "note.md"
            pocket.write_atomic(p, "done")
            self.assertEqual(p.read_text(encoding="utf-8"), "done")
            q = Path(d) / "triage" / "broken.md"
            with self.assertRaises(UnicodeEncodeError):
                pocket.write_atomic(q, "x" * 100000 + "\ud800")
            self.assertFalse(q.exists())
            self.assertEqual(sorted(x.name for x in q.parent.iterdir()), ["note.md"])


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = pocket.STATE
        pocket.STATE = Path(self.tmp.name) / "data" / "pocket" / "synced.json"
        self.legacy = Path(self.tmp.name) / "cache" / "pocket" / "synced.json"

    def tearDown(self):
        pocket.STATE = self.saved
        self.tmp.cleanup()

    def test_ledger_lives_under_data(self):
        self.assertEqual(self.saved.parts[-3:], ("data", "pocket", "synced.json"))

    def test_legacy_cache_ledger_is_merged_and_never_written(self):
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text('{"old@Acme": "a.md", "both@Acme": "legacy.md"}', encoding="utf-8")
        before = self.legacy.read_bytes()
        pocket.STATE.parent.mkdir(parents=True)
        pocket.STATE.write_text('{"both@Acme": "new.md"}', encoding="utf-8")
        self.assertEqual(pocket.load_ledger(), {"old@Acme": "a.md", "both@Acme": "new.md"})
        pocket.record("three@Acme", "c.md")
        self.assertEqual(json.loads(pocket.STATE.read_text(encoding="utf-8")),
                         {"old@Acme": "a.md", "both@Acme": "new.md", "three@Acme": "c.md"})
        self.assertEqual(self.legacy.read_bytes(), before)

    def test_unreadable_legacy_ledger_stops(self):
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text("{half", encoding="utf-8")
        with self.assertRaises(SystemExit):
            pocket.load_ledger()

    def test_record_merges_what_another_run_saved(self):
        pocket.record("one@Acme", "a.md")
        # Another vault's copy saves while this run is going.
        on_disk = json.loads(pocket.STATE.read_text(encoding="utf-8"))
        pocket.STATE.write_text(json.dumps({**on_disk, "two@Home": "b.md"}), encoding="utf-8")
        pocket.record("three@Acme", "c.md")
        self.assertEqual(json.loads(pocket.STATE.read_text(encoding="utf-8")),
                         {"one@Acme": "a.md", "two@Home": "b.md", "three@Acme": "c.md"})
        self.assertEqual([p.name for p in pocket.STATE.parent.iterdir()], ["synced.json"])

    def test_unreadable_ledger_stops_rather_than_being_overwritten(self):
        pocket.STATE.parent.mkdir(parents=True)
        pocket.STATE.write_text("{half", encoding="utf-8")
        with self.assertRaises(SystemExit):
            pocket.record("one@Acme", "a.md")
        self.assertEqual(pocket.STATE.read_text(encoding="utf-8"), "{half")


class RetryAfter(unittest.TestCase):
    def test_seconds_date_and_garbage(self):
        self.assertEqual(pocket.retry_after("7", 2), 7)
        self.assertEqual(pocket.retry_after("600", 2), 60)
        soon = email.utils.format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
        self.assertTrue(20 <= pocket.retry_after(soon, 2) <= 30)
        past = email.utils.format_datetime(datetime.now(timezone.utc) - timedelta(days=1), usegmt=True)
        self.assertEqual(pocket.retry_after(past, 2), 0)
        self.assertEqual(pocket.retry_after("soon", 2), 2)
        self.assertEqual(pocket.retry_after(None, 4), 4)


class ApiGet(unittest.TestCase):
    """api_get against a faked urlopen."""

    def setUp(self):
        self.sleep = mock.patch.object(pocket.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)

    def urlopen(self, *outcomes):
        """Each call takes the next outcome: an exception to raise, or bytes to return."""
        calls = iter(outcomes)

        def fake(req, timeout=None):
            out = next(calls)
            if isinstance(out, BaseException):
                raise out
            return io.BytesIO(out)
        return mock.patch.object(pocket.urllib.request, "urlopen", side_effect=fake)

    def test_server_error_is_retried(self):
        with self.urlopen(http_error("u", 503), b'{"data": 1}') as m:
            self.assertEqual(pocket.api_get("pk_x", "/p"), {"data": 1})
        self.assertEqual(m.call_count, 2)

    def test_retry_after_as_http_date_does_not_crash(self):
        when = email.utils.format_datetime(datetime.now(timezone.utc) + timedelta(seconds=5), usegmt=True)
        with self.urlopen(http_error("u", 429, {"Retry-After": when}), b'{"ok": true}'):
            self.assertEqual(pocket.api_get("pk_x", "/p"), {"ok": True})

    def test_network_failures_become_pocket_errors_after_retries(self):
        for exc in (urllib.error.URLError("unreachable"), TimeoutError("timed out"), ConnectionResetError()):
            with self.urlopen(*[exc] * 10) as m:
                with self.assertRaises(pocket.PocketError):
                    pocket.api_get("pk_x", "/p")
            self.assertEqual(m.call_count, pocket.RETRIES + 1)

    def test_persistent_server_error_is_a_pocket_error(self):
        with self.urlopen(*[http_error("u", 500)] * 10):
            with self.assertRaisesRegex(pocket.PocketError, "HTTP 500"):
                pocket.api_get("pk_x", "/p")

    def test_non_json_ok_response_is_a_pocket_error(self):
        with self.urlopen(b"<html>maintenance</html>"):
            with self.assertRaises(pocket.PocketError):
                pocket.api_get("pk_x", "/p")

    def test_not_found_is_not_retried(self):
        with self.urlopen(http_error("u", 404), b"{}") as m:
            with self.assertRaisesRegex(pocket.PocketError, "HTTP 404"):
                pocket.api_get("pk_x", "/p")
        self.assertEqual(m.call_count, 1)

    def test_refused_key_stops(self):
        with self.urlopen(http_error("u", 401)):
            with self.assertRaises(SystemExit):
                pocket.api_get("pk_x", "/p")


class MainLoop(unittest.TestCase):
    """The sync loop end to end, with HTTP faked at urlopen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.vault = base / "Acme"
        (self.vault / "resources" / "scripts").mkdir(parents=True)
        (self.vault / "resources" / "scripts" / "pocket.config.json").write_text(
            '{"route": {"Acme": "."}}', encoding="utf-8")
        home = base / "paraos"
        (home / "secrets").mkdir(parents=True)
        (home / "secrets" / "pocket.json").write_text('{"api_key": "pk_test"}', encoding="utf-8")
        now = datetime.now(timezone.utc)
        ago = lambda days: (now - timedelta(days=days)).isoformat()  # noqa: E731
        self.list = [
            {"id": "ready1", "title": "acme - Roles and responsibilities", "recording_at": ago(1), "state": "completed"},
            {"id": "busy22", "title": "ACME - Still processing", "recording_at": ago(2), "state": "processing"},
            {"id": "other3", "title": "Project review", "recording_at": ago(3)},
            {"id": "old444", "title": "Acme - Old", "recording_at": ago(90)},
        ]
        self.detail = {
            "ready1": {"transcript": [{"speaker": 0, "text": "So, this is a short recap."}],
                       "summarizations": {"s1": {"title": "Summary", "markdown": "• Split the roles"}}},
            "busy22": {"transcript": None, "summarizations": None},
        }
        self.errors = {}   # path -> exception raised instead of answering
        self.pages = None  # listing: None answers one page; a number keeps has_more true that long
        self.saved = {k: getattr(pocket, k) for k in ("VAULT_ROOT", "CONFIG_PATH", "AUTH", "STATE")}
        pocket.VAULT_ROOT = self.vault
        pocket.CONFIG_PATH = self.vault / "resources" / "scripts" / "pocket.config.json"
        pocket.AUTH = home / "secrets" / "pocket.json"
        pocket.STATE = home / "data" / "pocket" / "synced.json"
        self.legacy = home / "cache" / "pocket" / "synced.json"
        mock.patch.object(pocket.urllib.request, "urlopen", side_effect=self.fake_urlopen).start()
        mock.patch.object(pocket.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(pocket, k, v)
        self.tmp.cleanup()

    def fake_urlopen(self, req, timeout=None):
        self.assertEqual(req.get_header("Authorization"), "Bearer pk_test")
        url = urllib.parse.urlsplit(req.full_url)
        path = url.path[len("/api/v1"):]
        if path in self.errors:
            raise self.errors[path]
        if path == "/public/recordings":
            page = int(dict(urllib.parse.parse_qsl(url.query))["page"])
            more = self.pages is not None and page < self.pages
            body = {"data": self.list if page == 1 else [], "pagination": {"has_more": more}, "success": True}
        else:
            body = {"data": self.detail[path.rsplit("/", 1)[1]], "success": True}
        return io.BytesIO(json.dumps(body).encode("utf-8"))

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            pocket.main(list(argv))
        self.stderr = err.getvalue()
        return out.getvalue()

    def triage(self):
        folder = self.vault / "triage"
        return sorted(p.name for p in folder.iterdir()) if folder.exists() else []

    def ledger(self):
        return sorted(json.loads(pocket.STATE.read_text(encoding="utf-8"))) if pocket.STATE.exists() else []

    def test_dry_run_write_rerun(self):
        out = self.run_main()
        self.assertIn("DRY RUN · last 30 days · 3 recordings", out)
        self.assertIn("UNROUTED (prefix: none)", out)
        self.assertIn("HELD, still processing (processing) - retried next run", out)
        self.assertNotIn("--dump busy22", out)
        self.assertIn("would write: 1 · skipped(exists): 0 · held(processing): 1 · held(unreadable): 0 · "
                      "failed: 0 · undated: 0 · unrouted: 1 · other vaults: 0", out)
        self.assertEqual(self.triage(), [])
        self.assertFalse(pocket.STATE.exists())

        out = self.run_main("--write")
        self.assertIn("wrote: 1", out)
        [name] = self.triage()
        self.assertRegex(name, r"^\d{8} Roles and responsibilities\.md$")  # prefix dropped from the filename
        note = (self.vault / "triage" / name).read_text(encoding="utf-8")
        self.assertIn("**Speaker 0:** So, this is a short recap.", note)
        self.assertIn("- Split the roles", note)
        self.assertEqual(self.ledger(), ["ready1@Acme"])

        out = self.run_main("--write")
        self.assertIn("wrote: 0 · skipped(exists): 1 · held(processing): 1", out)

    def test_legacy_cache_ledger_is_honoured_and_carried_into_data(self):
        # ready1's note has left triage/; only the old cache/ ledger remembers it.
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text('{"ready1@Acme": "filed elsewhere"}', encoding="utf-8")
        before = self.legacy.read_bytes()
        self.list.append({"id": "fresh8", "title": "ACME - Fresh", "recording_at": self.list[0]["recording_at"],
                          "state": "completed"})
        self.detail["fresh8"] = self.detail["ready1"]
        out = self.run_main("--write")
        self.assertIn("wrote: 1 · skipped(exists): 1", out)
        self.assertEqual([name[9:] for name in self.triage()], ["Fresh.md"])
        self.assertEqual(self.ledger(), ["fresh8@Acme", "ready1@Acme"])
        self.assertEqual(self.legacy.read_bytes(), before)

    def test_entries_in_both_ledgers_are_honoured(self):
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text('{"ready1@Acme": "filed elsewhere"}', encoding="utf-8")
        pocket.STATE.parent.mkdir(parents=True)
        pocket.STATE.write_text('{"fresh8@Acme": "filed elsewhere"}', encoding="utf-8")
        self.list.append({"id": "fresh8", "title": "ACME - Fresh", "recording_at": self.list[0]["recording_at"],
                          "state": "completed"})
        out = self.run_main("--write")
        self.assertIn("wrote: 0 · skipped(exists): 2", out)
        self.assertEqual(self.triage(), [])

    def test_unreadable_hold_points_at_dump(self):
        self.detail["ready1"] = {"transcript": {"utterances_v9": [{"words": "hello there"}]},
                                 "summarizations": {"s1": {"title": "Summary", "markdown": "• Split the roles"}}}
        out = self.run_main("--write")
        self.assertIn("HELD, unreadable (transcript present but unreadable)", out)
        self.assertIn("py pocket.py --dump ready1", out)
        self.assertIn("held(processing): 1 · held(unreadable): 1", out)
        self.assertEqual(self.triage(), [])
        self.assertEqual(self.ledger(), [])

    def test_finished_recording_without_speech_is_written(self):
        self.detail["ready1"] = {"transcript": {"segments": [], "text": ""}, "summarizations": None}
        out = self.run_main("--write")
        self.assertIn("wrote: 1", out)
        [name] = self.triage()
        note = (self.vault / "triage" / name).read_text(encoding="utf-8")
        self.assertIn("_(no transcript available)_", note)
        self.assertIn("_(no summary available)_", note)
        self.assertEqual(self.ledger(), ["ready1@Acme"])

    def test_one_failed_recording_does_not_stop_the_run(self):
        self.list.insert(0, {"id": "down55", "title": "ACME - Flaky", "recording_at": self.list[0]["recording_at"],
                             "state": "completed"})
        self.errors["/public/recordings/down55"] = http_error("u", 502)
        out = self.run_main("--write")
        self.assertIn("FAILED (GET /public/recordings/down55 -> HTTP 502", out)
        self.assertIn("wrote: 1 · skipped(exists): 0 · held(processing): 1 · held(unreadable): 0 · failed: 1", out)
        self.assertEqual(self.ledger(), ["ready1@Acme"])

        del self.errors["/public/recordings/down55"]
        self.detail["down55"] = self.detail["ready1"]
        out = self.run_main("--write")
        self.assertIn("wrote: 1 · skipped(exists): 1", out)
        self.assertEqual(self.ledger(), ["down55@Acme", "ready1@Acme"])

    def test_listing_failure_stops_cleanly(self):
        self.errors["/public/recordings"] = urllib.error.URLError("unreachable")
        with self.assertRaises(SystemExit) as stop:
            self.run_main("--write")
        self.assertIn("unreachable", str(stop.exception.code))
        self.assertFalse(pocket.STATE.exists())

    def test_each_note_is_ledgered_as_it_is_written(self):
        self.list.insert(0, {"id": "crash6", "title": "ACME - Second", "recording_at": self.list[0]["recording_at"],
                             "state": "completed"})
        self.list[0]["recording_at"] = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        self.errors["/public/recordings/crash6"] = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_main("--write")
        self.assertEqual(self.ledger(), ["ready1@Acme"])

    def test_undated_recordings_are_counted(self):
        self.list.append({"id": "nodate7", "title": "ACME - Undated", "recording_at": "soon", "created_at": None})
        out = self.run_main()
        self.assertIn("· 4 recordings", out)
        self.assertIn("UNDATED", out)
        self.assertIn("--dump nodate7", out)
        self.assertIn("undated: 1", out)

    def test_page_cap_warns(self):
        self.pages = 10 ** 6
        self.run_main()
        self.assertIn(f"stopped after {pocket.MAX_PAGES} pages", self.stderr)

    def test_a_full_page_without_has_more_warns(self):
        full = {"data": [{"id": str(i)} for i in range(pocket.PAGE_SIZE)], "success": True}
        for body, warned in ((full, True), ({**full, "pagination": {}}, True),
                             ({**full, "pagination": {"has_more": False}}, False),
                             ({"data": [{"id": "1"}], "success": True}, False)):
            err = io.StringIO()
            with mock.patch.object(pocket, "api_get", return_value=body), contextlib.redirect_stderr(err):
                self.assertEqual(len(pocket.list_recordings("pk_test", datetime(2030, 1, 1))), len(body["data"]))
            self.assertEqual("may be truncated" in err.getvalue(), warned, body.get("pagination"))

    def test_a_note_left_unledgered_by_a_crash_is_recorded_not_reimported(self):
        rec = self.list[0]
        when = pocket.recorded_at(rec)
        note = self.vault / "triage" / f"{when:%Y%m%d} Roles and responsibilities.md"
        pocket.write_atomic(note, pocket.render_note(rec, when, "t", [(None, "s")]))
        before = note.read_bytes()

        out = self.run_main()
        self.assertIn("(exists, would record)", out)
        self.assertFalse(pocket.STATE.exists())

        out = self.run_main("--write")
        self.assertIn("(exists, recorded)", out)
        self.assertIn("wrote: 0 · recorded: 1 · skipped(exists): 0", out)
        self.assertEqual(self.ledger(), ["ready1@Acme"])
        self.assertEqual(note.read_bytes(), before)

        out = self.run_main("--write")
        self.assertIn("wrote: 0 · skipped(exists): 1", out)

    def test_unknown_vault_flag_stops(self):
        with self.assertRaises(SystemExit):
            self.run_main("--vault", "Other")


if __name__ == "__main__":
    unittest.main()
