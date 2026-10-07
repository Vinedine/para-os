#!/usr/bin/env python3
"""Unit tests for plaud.py. No network, no Plaud account, no real ~/.paraos: PARAOS_HOME points at
a temporary directory before the module loads, HTTP is faked at urllib.request.urlopen (an
unfaked call fails the test), and the sign-in's loopback server listens on a free local port.

Run from the repo root:
    py -m unittest integrations/plaud/test_plaud.py
"""
import base64
import contextlib
import email.utils
import http.client
import importlib.util
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HOME = tempfile.TemporaryDirectory()
os.environ["PARAOS_HOME"] = HOME.name
for var in ("PLAUD_API_BASE", "PLAUD_CLIENT_ID"):
    os.environ.pop(var, None)

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("plaud", HERE / "plaud.py")
plaud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plaud)
REAL_POST_FORM = plaud.post_form  # SignIn and Tokens replace it; one test calls the real one


def tearDownModule():
    HOME.cleanup()


def http_error(url, code, headers=None, body=b"boom"):
    return urllib.error.HTTPError(url, code, "error", headers or {}, io.BytesIO(body))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Offline(unittest.TestCase):
    """Every test starts with urlopen and the browser refusing: a test that needs either fakes it."""

    def setUp(self):
        def no_network(req, *a, **k):
            raise AssertionError(f"unfaked network call: {getattr(req, 'full_url', req)}")
        self.patch(plaud.urllib.request, "urlopen", side_effect=no_network)
        self.patch(plaud.webbrowser, "open", side_effect=AssertionError("unfaked browser"))
        self.sleep = self.patch(plaud.time, "sleep")

    def patch(self, target, name, **kwargs):
        p = mock.patch.object(target, name, **kwargs)
        self.addCleanup(p.stop)
        return p.start()

    def use_home(self):
        """AUTH and STATE under a fresh temporary PARAOS_HOME, restored afterwards."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name)
        self.patch(plaud, "AUTH", new=home / "secrets" / "plaud.json")
        self.patch(plaud, "STATE", new=home / "data" / "plaud" / "synced.json")
        return home


class Paths(unittest.TestCase):
    def test_state_lives_under_the_temporary_paraos_home(self):
        self.assertEqual(plaud.AUTH, Path(HOME.name) / "secrets" / "plaud.json")
        self.assertEqual(plaud.STATE.parts[-3:], ("data", "plaud", "synced.json"))


class Sanitize(unittest.TestCase):
    def test_illegal_characters_become_spaces(self):
        self.assertEqual(plaud.sanitize('Q3/Q4 plan: "go"'), "Q3 Q4 plan go")

    def test_edges_trimmed_after_truncation(self):
        self.assertEqual(plaud.sanitize("  ..Review.  "), "Review")
        self.assertFalse(plaud.sanitize("a" * 79 + " .b").endswith((" ", ".")))


class Dates(unittest.TestCase):
    def test_z_offsets_long_fractions_and_no_offset(self):
        a = plaud.parse_when("2030-01-15T22:30:00.123456789Z")
        self.assertEqual((a.hour, a.microsecond, a.utcoffset()), (22, 123456, timedelta(0)))
        self.assertEqual(plaud.parse_when("2030-01-15T10:00:00+0200").utcoffset(), timedelta(hours=2))
        self.assertEqual(plaud.parse_when("2030-01-15 10:00:00").utcoffset(), timedelta(0))

    def test_garbage_is_none(self):
        for s in ("yesterday", None, "", "2030-01-15"):
            self.assertIsNone(plaud.parse_when(s), s)


class Transcript(unittest.TestCase):
    def test_turns_merge_one_speaker_and_open_on_their_timestamp(self):
        segs = [{"start_time": 0, "end_time": 4000, "speaker": "Speaker 1", "content": "Welcome."},
                {"start_time": 4500, "end_time": 9000, "speaker": "Speaker 1", "content": "Roof first."},
                {"start_time": 3725000, "end_time": 3730000, "speaker": "Speaker 2", "content": "Agreed."}]
        self.assertEqual(plaud.transcript_md(json.dumps(segs)),
                         "[00:00] **Speaker 1:** Welcome. Roof first.\n\n[1:02:05] **Speaker 2:** Agreed.")

    def test_unlabelled_segments_stay_separate(self):
        segs = [{"start_time": 1000, "content": "One."}, {"start_time": 2000, "content": "Two."}]
        self.assertEqual(plaud.transcript_md(json.dumps(segs)), "[00:01] One.\n\n[00:02] Two.")

    def test_blank_segments_and_odd_items_are_skipped(self):
        segs = [{"content": "  "}, "stray", 7, {"start_time": True, "speaker": "", "content": "Kept."}]
        self.assertEqual(plaud.transcript_md(json.dumps(segs)), "Kept.")

    def test_plain_text_passes_through(self):
        self.assertEqual(plaud.transcript_md("  Just words.  "), "Just words.")

    def test_empty_is_empty_and_an_unknown_json_shape_is_none(self):
        self.assertEqual(plaud.transcript_md(""), "")
        self.assertEqual(plaud.transcript_md("[]"), "")
        self.assertIsNone(plaud.transcript_md('{"segments": [{"content": "hello"}]}'))


class Blocks(Offline):
    def test_inline_content_wins_and_the_link_is_fetched_without_the_bearer(self):
        seen = []

        def fake(req, timeout=None):
            seen.append(req)
            return io.BytesIO("# Points\n- one".encode("utf-8"))
        self.patch(plaud.urllib.request, "urlopen", side_effect=fake)
        self.assertEqual(plaud.block_text({"data_content": "inline", "data_link": "https://x.test/a"}), "inline")
        self.assertEqual(seen, [])
        self.assertEqual(plaud.block_text({"data_content": "", "data_link": "https://files.example.test/s"}),
                         "# Points\n- one")
        self.assertIsNone(seen[0].get_header("Authorization"))
        self.assertEqual(seen[0].get_header("User-agent"), plaud.UA)

    def test_only_an_https_link_is_followed(self):
        for link in ("file:///etc/hosts", "http://files.example.test/s"):
            with self.assertRaisesRegex(plaud.PlaudError, "not an https URL"):
                plaud.block_text({"data_link": link})

    def test_a_failed_link_is_a_plaud_error(self):
        self.patch(plaud.urllib.request, "urlopen", side_effect=http_error("u", 403))
        with self.assertRaisesRegex(plaud.PlaudError, "files.example.test"):
            plaud.block_text({"data_link": "https://files.example.test/s?X-Signature=secret"})

    def test_nothing_is_empty(self):
        self.assertEqual(plaud.block_text(None), "")
        self.assertEqual(plaud.block_text({"data_type": "transaction"}), "")

    def test_summaries_are_the_auto_sum_notes_only(self):
        detail = {"note_list": [
            {"data_type": "auto_sum_note", "data_title": "Meeting notes", "data_content": "# Core\n- point"},
            {"data_type": "auto_sum_note", "data_title": " ", "data_content": "Second."},
            {"data_type": "auto_sum_note", "data_content": "   "},
            {"data_type": "mark_memo", "data_content": "A memo."}, "stray"]}
        self.assertEqual(plaud.summaries(detail), [("Meeting notes", "# Core\n- point"), (None, "Second.")])
        self.assertEqual(plaud.summaries({}), [])


class Render(unittest.TestCase):
    WHEN = datetime(2030, 1, 15, 11, 0)

    def test_one_summary_nests_under_its_heading(self):
        md = plaud.render_note('Site: "roof"', self.WHEN, "f1", 2, [("Notes", "# Points\n- one")], "[00:00] Hi.")
        self.assertIn('title: "Site: \\"roof\\""', md)
        self.assertIn("plaud_id: f1\nsource: plaud\nduration_min: 2", md)
        self.assertIn("_2030-01-15 11:00 · 2 min_", md)
        self.assertIn("## Summary\n\n### Points\n- one", md)
        self.assertLess(md.index("## Summary"), md.index("## Transcript"))

    def test_several_summaries_each_get_a_title(self):
        md = plaud.render_note("T", self.WHEN, "f1", None, [("One", "# H"), (None, "y")], "t")
        self.assertIn("### One\n\n#### H", md)
        self.assertIn("### Summary\n\ny", md)
        self.assertNotIn("duration_min", md)

    def test_missing_parts_say_so(self):
        md = plaud.render_note("T", self.WHEN, "f1", None, [], "")
        self.assertIn("_(no summary available)_", md)
        self.assertIn("_(no transcript available)_", md)


class SignIn(Offline):
    def setUp(self):
        super().setUp()
        self.use_home()
        self.port = free_port()
        self.pages, self.threads = [], []
        self.exchange = self.patch(plaud, "post_form", return_value={
            "access_token": "a1", "refresh_token": "r1", "expires_in": 3600})

    def browser(self, answer, paths=("/auth/callback",)):
        """A fake browser: reads the authorize URL, then visits each loopback path with `answer`'s query."""
        def open_browser(url):
            self.authorize = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            query = urllib.parse.urlencode(answer(self.authorize))

            def visit():
                for path in paths:
                    conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
                    conn.request("GET", f"{path}?{query}")
                    resp = conn.getresponse()
                    self.pages.append((resp.status, resp.read().decode("utf-8")))
                    conn.close()
            t = threading.Thread(target=visit, daemon=True)
            t.start()
            self.threads.append(t)
        return open_browser

    def login(self, answer, **kw):
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                plaud.login(port=self.port, open_browser=self.browser(answer, **kw), timeout=10)
        finally:
            for t in self.threads:
                t.join(10)
        return out.getvalue()

    def test_pkce_challenge_matches_rfc_7636(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        self.assertEqual(plaud.pkce_pair(verifier), (verifier, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"))
        fresh, _ = plaud.pkce_pair()
        self.assertTrue(43 <= len(fresh) <= 128)

    def test_authorize_url_asks_for_a_code_with_s256(self):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(plaud.authorize_url("ch", "st")).query))
        self.assertEqual(q, {"client_id": plaud.CLIENT_ID, "redirect_uri": "http://localhost:8199/auth/callback",
                             "response_type": "code", "code_challenge": "ch", "code_challenge_method": "S256",
                             "state": "st"})

    def test_login_exchanges_the_code_with_its_verifier_and_saves_the_tokens(self):
        out = self.login(lambda q: {"code": "c0de", "state": q["state"]})
        [(url, fields), kwargs] = self.exchange.call_args
        self.assertEqual(url, plaud.TOKEN_URL)
        self.assertEqual(kwargs, {"basic": True})
        self.assertEqual(fields["code"], "c0de")
        self.assertEqual(fields["redirect_uri"], plaud.REDIRECT_URI)
        self.assertEqual(fields["state"], self.authorize["state"])
        self.assertEqual(plaud.pkce_pair(fields["code_verifier"])[1], self.authorize["code_challenge"])
        tok = json.loads(plaud.AUTH.read_text(encoding="utf-8"))
        self.assertEqual((tok["access_token"], tok["refresh_token"]), ("a1", "r1"))
        self.assertAlmostEqual(tok["expires_at"], time.time() + 3600, delta=60)
        self.assertEqual(self.pages, [(200, "<p>Sign-in received. You can close this window and return to the "
                                            "terminal.</p>")])
        self.assertIn("Signed in", out)

    def test_a_stray_request_gets_a_404_and_the_wait_goes_on(self):
        self.login(lambda q: {"code": "c0de", "state": q["state"]}, paths=("/favicon.ico", "/auth/callback"))
        self.assertEqual([status for status, _ in self.pages], [404, 200])
        self.assertTrue(plaud.AUTH.exists())

    def test_a_foreign_state_is_refused_before_any_exchange(self):
        with self.assertRaises(SystemExit) as stop:
            self.login(lambda q: {"code": "c0de", "state": "someone-else"})
        self.assertIn("state mismatch", str(stop.exception.code))
        self.exchange.assert_not_called()
        self.assertFalse(plaud.AUTH.exists())
        self.assertIn("Sign-in failed", self.pages[0][1])

    def test_a_denied_sign_in_names_the_reason(self):
        with self.assertRaises(SystemExit) as stop:
            self.login(lambda q: {"error": "access_denied", "state": q["state"]})
        self.assertIn("access_denied", str(stop.exception.code))
        self.exchange.assert_not_called()

    def test_no_answer_times_out(self):
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()):
            plaud.login(port=self.port, open_browser=lambda url: None, timeout=0)
        self.assertIn("timed out", str(stop.exception.code))

    def test_a_refused_exchange_stops_with_the_status(self):
        self.exchange.side_effect = http_error("u", 400, body=b"invalid_grant")
        with self.assertRaises(SystemExit) as stop:
            self.login(lambda q: {"code": "c0de", "state": q["state"]})
        self.assertIn("HTTP 400 invalid_grant", str(stop.exception.code))
        self.assertFalse(plaud.AUTH.exists())

    def test_post_form_sends_the_public_client_as_basic_auth(self):
        seen = []

        def fake(req, timeout=None):
            seen.append(req)
            return io.BytesIO(b'{"access_token": "a1"}')
        self.patch(plaud.urllib.request, "urlopen", side_effect=fake)
        self.assertEqual(REAL_POST_FORM(plaud.TOKEN_URL, {"code": "c", "state": "s"}, basic=True),
                         {"access_token": "a1"})
        [req] = seen
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"),
                         "Basic " + base64.b64encode(f"{plaud.CLIENT_ID}:".encode()).decode())
        self.assertEqual(urllib.parse.parse_qs(req.data.decode()), {"code": ["c"], "state": ["s"]})
        self.assertEqual(req.get_header("User-agent"), plaud.UA)



class Tokens(Offline):
    def setUp(self):
        super().setUp()
        self.use_home()
        self.refresh = self.patch(plaud, "post_form", return_value={"access_token": "a2", "expires_in": 3600})

    def save(self, **tok):
        plaud.AUTH.parent.mkdir(parents=True, exist_ok=True)
        plaud.AUTH.write_text(json.dumps(tok), encoding="utf-8")

    def test_not_signed_in_stops_naming_login(self):
        with self.assertRaises(SystemExit) as stop:
            plaud.access_token()
        self.assertIn("login", str(stop.exception.code))

    def test_a_live_token_is_used_as_it_is(self):
        self.save(access_token="a1", refresh_token="r1", expires_at=time.time() + 3600)
        self.assertEqual(plaud.access_token(), "a1")
        self.refresh.assert_not_called()

    def test_an_expiring_token_is_refreshed_and_keeps_its_refresh_token(self):
        self.save(access_token="a1", refresh_token="r1", expires_at=time.time() + 30)
        self.assertEqual(plaud.access_token(), "a2")
        self.refresh.assert_called_once_with(plaud.REFRESH_URL, {"refresh_token": "r1"})
        tok = json.loads(plaud.AUTH.read_text(encoding="utf-8"))
        self.assertEqual((tok["access_token"], tok["refresh_token"]), ("a2", "r1"))
        self.assertGreater(tok["expires_at"], time.time() + 3000)

    def test_a_refused_refresh_stops_and_leaves_the_tokens(self):
        self.save(access_token="a1", refresh_token="r1", expires_at=time.time() - 10)
        before = plaud.AUTH.read_bytes()
        self.refresh.side_effect = http_error("u", 401)
        with self.assertRaises(SystemExit) as stop:
            plaud.access_token()
        self.assertIn("refused the token refresh (HTTP 401)", str(stop.exception.code))
        self.assertIn("login", str(stop.exception.code))
        self.assertEqual(plaud.AUTH.read_bytes(), before)

    def test_an_unreachable_refresh_stops_without_blaming_the_sign_in(self):
        self.save(access_token="a1", refresh_token="r1", expires_at=time.time() - 10)
        self.refresh.side_effect = urllib.error.URLError("unreachable")
        with self.assertRaises(SystemExit) as stop:
            plaud.access_token()
        self.assertIn("unreachable", str(stop.exception.code))

    def test_expired_with_no_refresh_token_stops(self):
        self.save(access_token="a1", expires_at=time.time() - 10)
        with self.assertRaises(SystemExit):
            plaud.access_token()
        self.refresh.assert_not_called()

    def test_an_unreadable_token_file_or_response_stops(self):
        plaud.AUTH.parent.mkdir(parents=True)
        for text in ("{half", "[]", '{"refresh_token": "r1"}'):
            plaud.AUTH.write_text(text, encoding="utf-8")
            with self.assertRaises(SystemExit):
                plaud.access_token()
        for data in (None, {}, {"access_token": ""}):
            with self.assertRaises(SystemExit):
                plaud.save_tokens(data)


class RetryAfter(unittest.TestCase):
    def test_seconds_date_and_garbage(self):
        self.assertEqual(plaud.retry_after("7", 2), 7)
        self.assertEqual(plaud.retry_after("600", 2), 60)
        soon = email.utils.format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
        self.assertTrue(20 <= plaud.retry_after(soon, 2) <= 30)
        self.assertEqual(plaud.retry_after("soon", 2), 2)
        self.assertEqual(plaud.retry_after(None, 4), 4)


class ApiGet(Offline):
    """api_get against a faked urlopen."""

    def urlopen(self, *outcomes):
        """Each call takes the next outcome: an exception to raise, or bytes to return."""
        calls = iter(outcomes)
        self.requests = []

        def fake(req, timeout=None):
            self.requests.append(req)
            out = next(calls)
            if isinstance(out, BaseException):
                raise out
            return io.BytesIO(out)
        return self.patch(plaud.urllib.request, "urlopen", side_effect=fake)

    def test_sends_the_bearer_and_an_agent_cloudflare_accepts(self):
        self.urlopen(b'{"data": []}')
        self.assertEqual(plaud.api_get("tok", "/p", {"page": 1}), {"data": []})
        [req] = self.requests
        self.assertEqual(req.full_url, plaud.API + "/p?page=1")
        self.assertEqual(req.get_header("Authorization"), "Bearer tok")
        self.assertEqual(req.get_header("User-agent"), "para-os-plaud/1.0")

    def test_server_error_and_rate_limit_are_retried(self):
        m = self.urlopen(http_error("u", 503), http_error("u", 429, {"Retry-After": "7"}), b'{"ok": 1}')
        self.assertEqual(plaud.api_get("tok", "/p"), {"ok": 1})
        self.assertEqual(m.call_count, 3)
        self.assertEqual(self.sleep.call_args_list[-1], mock.call(7))

    def test_network_failures_become_plaud_errors_after_retries(self):
        for exc in (urllib.error.URLError("unreachable"), TimeoutError("timed out"), ConnectionResetError()):
            m = self.urlopen(*[exc] * 10)
            with self.assertRaises(plaud.PlaudError):
                plaud.api_get("tok", "/p")
            self.assertEqual(m.call_count, plaud.RETRIES + 1)

    def test_not_found_is_not_retried(self):
        m = self.urlopen(http_error("u", 404, body=b"no such file"), b"{}")
        with self.assertRaisesRegex(plaud.PlaudError, "HTTP 404: no such file"):
            plaud.api_get("tok", "/p")
        self.assertEqual(m.call_count, 1)

    def test_non_json_is_a_plaud_error(self):
        self.urlopen(b"<html>Cloudflare</html>")
        with self.assertRaisesRegex(plaud.PlaudError, "not JSON"):
            plaud.api_get("tok", "/p")

    def test_a_refused_token_stops_naming_login(self):
        self.urlopen(http_error("u", 401))
        with self.assertRaises(SystemExit) as stop:
            plaud.api_get("tok", "/p")
        self.assertIn("login", str(stop.exception.code))


class Listing(Offline):
    def setUp(self):
        super().setUp()
        self.now = datetime.now(timezone.utc)
        self.cutoff = self.now - timedelta(days=30)
        self.patch(plaud, "PAGE_SIZE", new=2)

    def files(self, *days_ago):
        return [{"id": f"f{d}", "created_at": (self.now - timedelta(days=d)).isoformat()} for d in days_ago]

    def serve(self, *pages):
        bodies = list(pages)
        return self.patch(plaud, "api_get", side_effect=lambda token, path, params: bodies[params["page"] - 1])

    def test_reads_pages_until_a_short_one(self):
        m = self.serve({"data": self.files(1, 2)}, {"data": self.files(3, 4)}, {"data": self.files(5)})
        self.assertEqual([f["id"] for f in plaud.list_files("tok", self.cutoff)], ["f1", "f2", "f3", "f4", "f5"])
        self.assertEqual([c.args[2] for c in m.call_args_list],
                         [{"page": p, "page_size": 2} for p in (1, 2, 3)])

    def test_stops_at_the_page_that_reaches_past_the_cutoff(self):
        m = self.serve({"data": self.files(1, 40)}, {"data": self.files(50, 60)})
        self.assertEqual(len(plaud.list_files("tok", self.cutoff)), 2)
        self.assertEqual(m.call_count, 1)

    def test_the_page_cap_warns(self):
        self.patch(plaud, "MAX_PAGES", new=3)
        self.serve(*[{"data": self.files(1, 2)}] * 3)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(len(plaud.list_files("tok", self.cutoff)), 6)
        self.assertIn("stopped after 3 pages", err.getvalue())

    def test_a_listing_or_file_of_the_wrong_shape_is_a_plaud_error(self):
        self.serve({"data": {"id": "not a list"}})
        with self.assertRaisesRegex(plaud.PlaudError, "no list of recordings"):
            plaud.list_files("tok", self.cutoff)
        self.patch(plaud, "api_get", return_value={"data": ["f1"]})
        with self.assertRaisesRegex(plaud.PlaudError, "no recording object"):
            plaud.get_file("tok", "f1")


class Routing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name)
        self.root = self.parent / "Acme"
        (self.parent / "Home").mkdir()
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_vault_takes_everything_under_its_full_title(self):
        for title in ("ACME - Review", "Untitled walk", ""):
            self.assertEqual(plaud.resolve(title, {}, self.root, "Acme", "triage"),
                             {"vault": "Acme", "dir": self.root / "triage", "desc": title})

    def test_self_and_sibling_case_insensitive(self):
        routes, warnings = plaud.build_routes({"ACME": ".", "HOME": "Home"}, "Acme", self.parent)
        self.assertEqual(warnings, [])
        self.assertEqual(plaud.resolve("acme - Review with counsel", routes, self.root, "Acme", "triage"),
                         {"vault": "Acme", "dir": self.root / "triage", "desc": "Review with counsel"})
        self.assertEqual(plaud.resolve("HOME - Plumber", routes, self.root, "Acme", "triage"), {"elsewhere": True})
        self.assertEqual(plaud.resolve("HOME-Plumber", routes, self.root, None, "triage")["dir"],
                         self.parent / "Home" / "triage")

    def test_the_prefix_is_granolas_and_pockets_rule(self):
        routes, _ = plaud.build_routes({"ACME": "."}, "Acme", self.parent)
        self.assertEqual(plaud.resolve("ACME Review", routes, self.root, "Acme", "triage"), {"unrouted": "none"})
        self.assertEqual(plaud.resolve("ACME: Review", routes, self.root, "Acme", "triage"), {"unrouted": "none"})
        self.assertEqual(plaud.resolve("Acmeville - trip", routes, self.root, "Acme", "triage"),
                         {"unrouted": "Acmeville"})
        self.assertEqual(plaud.PREFIX.pattern, r"^\s*([A-Za-z0-9]+)\s*-\s*")

    def test_literal_own_name_on_another_machine_warns(self):
        _, warnings = plaud.build_routes({"Acme": "Acme - Documents"}, "Acme", self.parent)
        self.assertEqual(len(warnings), 1)
        self.assertIn('Use "."', warnings[0])


class Config(unittest.TestCase):
    def test_missing_is_single_vault(self):
        self.assertEqual(plaud.load_config(Path(tempfile.gettempdir()) / "nope" / "plaud.config.json"), {})

    def test_malformed_or_wrong_shape_stops(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "plaud.config.json"
            for text in ("{not json", "[]", '{"route": ["Acme"]}'):
                p.write_text(text, encoding="utf-8")
                with self.assertRaises(SystemExit):
                    plaud.load_config(p)

    def test_the_template_parses_and_routes(self):
        cfg = plaud.load_config(HERE / "plaud.config.json.template")
        self.assertEqual(cfg["meetings_subdir"], "triage")
        self.assertIn(".", cfg["route"].values())


class Files(unittest.TestCase):
    def test_same_recording_is_detected_other_recording_gets_suffix(self):
        when = datetime(2030, 1, 15, 10, 0)
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            path, exists = plaud.pick_path(folder, when, "Project sync: status", "aaaa1111")
            self.assertEqual((path.name, exists), ("20300115 Project sync status.md", False))
            path.write_text(plaud.render_note("Project sync: status", when, "aaaa1111", None, [], "t"),
                            encoding="utf-8")
            self.assertEqual(plaud.pick_path(folder, when, "Project sync: status", "aaaa1111"), (path, True))
            other, exists = plaud.pick_path(folder, when, "Project sync: status", "bbbb2222")
            self.assertEqual((other.name, exists), ("20300115 Project sync status (bbbb22).md", False))


class Ledger(Offline):
    def setUp(self):
        super().setUp()
        self.use_home()

    def test_record_merges_what_another_run_saved(self):
        plaud.record("one@Acme", "a.md")
        on_disk = json.loads(plaud.STATE.read_text(encoding="utf-8"))
        plaud.STATE.write_text(json.dumps({**on_disk, "two@Home": "b.md"}), encoding="utf-8")
        plaud.record("three@Acme", "c.md")
        self.assertEqual(json.loads(plaud.STATE.read_text(encoding="utf-8")),
                         {"one@Acme": "a.md", "two@Home": "b.md", "three@Acme": "c.md"})

    def test_unreadable_ledger_stops_rather_than_being_overwritten(self):
        plaud.STATE.parent.mkdir(parents=True)
        for text in ("{half", "[]"):
            plaud.STATE.write_text(text, encoding="utf-8")
            with self.assertRaises(SystemExit):
                plaud.record("one@Acme", "a.md")
            self.assertEqual(plaud.STATE.read_text(encoding="utf-8"), text)


TRANSCRIPT = json.dumps([
    {"start_time": 0, "end_time": 4000, "speaker": "Speaker 1", "content": "Welcome to the site."},
    {"start_time": 4500, "end_time": 9000, "speaker": "Speaker 1", "content": "The roof comes first."},
    {"start_time": 65000, "end_time": 70000, "speaker": "Speaker 2", "content": "Agreed."}])
LINK = "https://files.example.test/"


class MainLoop(Offline):
    """The sync loop end to end, with the API and the pre-signed links faked at urlopen."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.vault = base / "Acme"
        (self.vault / "resources" / "scripts").mkdir(parents=True)
        config = self.vault / "resources" / "scripts" / "plaud.config.json"
        config.write_text('{"route": {"Acme": "."}}', encoding="utf-8")
        home = self.use_home()
        self.patch(plaud, "VAULT_ROOT", new=self.vault)
        self.patch(plaud, "CONFIG_PATH", new=config)
        plaud.AUTH.parent.mkdir(parents=True)
        plaud.AUTH.write_text(json.dumps({"access_token": "tok_test", "refresh_token": "r1",
                                          "expires_at": time.time() + 3600}), encoding="utf-8")
        self.home = home
        self.now = datetime.now(timezone.utc)
        self.list = [
            {"id": "ready1", "name": "acme - Site visit", "created_at": self.ago(hours=3), "duration": 125000},
            {"id": "busy22", "name": "ACME - Just recorded", "created_at": self.ago(hours=2)},
            {"id": "other3", "name": "Project review", "created_at": self.ago(days=3)},
            {"id": "old444", "name": "Acme - Old", "created_at": self.ago(days=90)},
        ]
        self.start = (self.now - timedelta(hours=4)).replace(microsecond=0)
        self.detail = {
            "ready1": {"id": "ready1", "start_at": self.start.isoformat(),
                       "source_list": [{"data_type": "transaction", "data_content": TRANSCRIPT},
                                       {"data_type": "outline", "data_content": "Not the transcript."}],
                       "note_list": [{"data_type": "auto_sum_note", "data_title": "Site visit",
                                      "data_link": LINK + "sum-ready1.md?sig=x"}]},
            "busy22": {"id": "busy22", "source_list": [], "note_list": []},
            "other3": {"id": "other3", "source_list": [{"data_type": "transaction_polish",
                                                        "data_content": "Polished words only."}],
                       "note_list": [{"data_type": "auto_sum_note", "data_content": "A review."}]},
        }
        self.links = {LINK + "sum-ready1.md?sig=x": "# Key points\n- Roof first"}
        self.errors = {}  # API path or link -> exception raised instead of answering
        self.patch(plaud.urllib.request, "urlopen", side_effect=self.fake_urlopen)

    def ago(self, days=0, hours=0):
        return (self.now - timedelta(days=days, hours=hours)).isoformat()

    def fake_urlopen(self, req, timeout=None):
        if req.full_url.startswith(LINK):
            self.assertIsNone(req.get_header("Authorization"))
            if req.full_url in self.errors:
                raise self.errors[req.full_url]
            return io.BytesIO(self.links[req.full_url].encode("utf-8"))
        self.assertEqual(req.get_header("Authorization"), "Bearer tok_test")
        self.assertEqual(req.get_header("User-agent"), plaud.UA)
        url = urllib.parse.urlsplit(req.full_url)
        path = url.path[len("/developer/api"):]
        if path in self.errors:
            raise self.errors[path]
        if path == "/open/third-party/files/":
            page = int(dict(urllib.parse.parse_qsl(url.query))["page"])
            body = {"data": self.list if page == 1 else [], "page": page}
        else:
            body = {"status": 0, "data": self.detail[path.rsplit("/", 1)[1]]}
        return io.BytesIO(json.dumps(body).encode("utf-8"))

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            plaud.main(list(argv))
        self.stderr = err.getvalue()
        return out.getvalue()

    def triage(self, vault=None):
        folder = (vault or self.vault) / "triage"
        return sorted(p.name for p in folder.iterdir()) if folder.exists() else []

    def ledger(self):
        return sorted(json.loads(plaud.STATE.read_text(encoding="utf-8"))) if plaud.STATE.exists() else []

    def test_dry_run_writes_nothing(self):
        out = self.run_main()
        self.assertIn("DRY RUN · last 30 days · 3 recordings · routing -> Acme", out)
        self.assertIn("UNROUTED (prefix: none)", out)
        self.assertIn("HELD, no transcript or summary yet", out)
        self.assertIn("would write: 1 · skipped(exists): 0 · held(pending): 1 · held(unreadable): 0 · "
                      "failed: 0 · undated: 0 · unrouted: 1 · other vaults: 0", out)
        self.assertEqual(self.triage(), [])
        self.assertFalse(plaud.STATE.exists())

    def test_write_makes_one_dated_note_with_summary_and_transcript_then_skips_it(self):
        out = self.run_main("--write")
        self.assertIn("wrote: 1", out)
        when = plaud.parse_when(self.start.isoformat()).astimezone()
        self.assertEqual(self.triage(), [f"{when:%Y%m%d} Site visit.md"])  # dated by start_at, prefix dropped
        note = (self.vault / "triage" / self.triage()[0]).read_text(encoding="utf-8")
        self.assertIn('title: "acme - Site visit"', note)
        self.assertIn("plaud_id: ready1\nsource: plaud\nduration_min: 2", note)
        self.assertIn("## Summary\n\n### Key points\n- Roof first", note)
        self.assertIn("## Transcript\n\n[00:00] **Speaker 1:** Welcome to the site. The roof comes first.\n\n"
                      "[01:05] **Speaker 2:** Agreed.", note)
        self.assertNotIn("Not the transcript.", note)
        self.assertEqual(self.ledger(), ["ready1@Acme"])
        self.assertEqual(json.loads(plaud.STATE.read_text(encoding="utf-8"))["ready1@Acme"],
                         str(self.vault / "triage" / self.triage()[0]))

        out = self.run_main("--write")
        self.assertIn("wrote: 0 · skipped(exists): 1 · held(pending): 1", out)
        self.assertEqual(len(self.triage()), 1)

    def test_a_ledgered_recording_whose_note_has_left_triage_is_not_reimported(self):
        self.run_main("--write")
        for p in (self.vault / "triage").iterdir():
            p.unlink()   # /para-triage filed it elsewhere
        out = self.run_main("--write")
        self.assertIn("skipped(exists): 1", out)
        self.assertEqual(self.triage(), [])

    def test_hold_then_write_after_the_cap(self):
        self.list = [self.list[1]]
        out = self.run_main("--write")
        self.assertIn("HELD, no transcript or summary yet - retried next run", out)
        self.assertEqual((self.triage(), self.ledger()), ([], []))

        self.list[0]["created_at"] = self.ago(hours=plaud.HOLD_HOURS + 1)
        out = self.run_main("--write")
        self.assertIn("wrote: 1", out)
        [name] = self.triage()
        self.assertTrue(name.endswith(" Just recorded.md"), name)  # no start_at: dated by created_at
        note = (self.vault / "triage" / name).read_text(encoding="utf-8")
        self.assertIn("_(no summary available)_", note)
        self.assertIn("_(no transcript available)_", note)
        self.assertEqual(self.ledger(), ["busy22@Acme"])

    def test_a_transcript_without_its_summary_holds_until_the_cap(self):
        self.list = [self.list[1]]
        self.detail["busy22"]["source_list"] = [{"data_type": "transaction", "data_content": TRANSCRIPT}]
        out = self.run_main("--write")
        self.assertIn("HELD, no summary yet", out)
        self.assertEqual(self.triage(), [])

        self.list[0]["created_at"] = self.ago(hours=plaud.HOLD_HOURS + 1)
        self.run_main("--write")
        [name] = self.triage()
        note = (self.vault / "triage" / name).read_text(encoding="utf-8")
        self.assertIn("_(no summary available)_", note)
        self.assertIn("**Speaker 2:** Agreed.", note)

    def test_an_unreadable_transcript_holds_past_the_cap_and_points_at_dump(self):
        self.detail["ready1"]["source_list"] = [{"data_type": "transaction",
                                                 "data_content": '{"segments": [{"content": "hello"}]}'}]
        self.list[0]["created_at"] = self.ago(days=3)
        out = self.run_main("--write")
        self.assertIn("HELD, unreadable", out)
        self.assertIn("py plaud.py --dump ready1", out)
        self.assertIn("held(unreadable): 1", out)
        self.assertEqual((self.triage(), self.ledger()), ([], []))

    def test_single_vault_mode_takes_every_recording(self):
        plaud.CONFIG_PATH.unlink()
        out = self.run_main("--write")
        self.assertNotIn("routing", out)
        self.assertNotIn("unrouted", out)
        self.assertIn("wrote: 2", out)
        names = [name[9:] for name in self.triage()]
        self.assertEqual(names, ["Project review.md", "acme - Site visit.md"])  # full titles, prefix kept
        note = next((self.vault / "triage").glob("* Project review.md")).read_text(encoding="utf-8")
        self.assertIn("Polished words only.", note)  # the polished copy when there is no raw one
        self.assertEqual(self.ledger(), ["other3@Acme", "ready1@Acme"])

    def test_one_failed_recording_does_not_stop_the_run(self):
        self.list.insert(0, {"id": "down55", "name": "ACME - Flaky", "created_at": self.ago(hours=5)})
        self.errors["/open/third-party/files/down55"] = http_error("u", 502)
        self.errors[LINK + "sum-ready1.md?sig=x"] = http_error("u", 403)
        out = self.run_main("--write")
        self.assertIn("FAILED (GET /open/third-party/files/down55 -> HTTP 502", out)
        self.assertIn("FAILED (GET data_link at files.example.test", out)
        self.assertIn("wrote: 0 · skipped(exists): 0 · held(pending): 1 · held(unreadable): 0 · failed: 2", out)
        self.assertEqual(self.ledger(), [])

        self.errors.clear()
        self.detail["down55"] = self.detail["ready1"]
        out = self.run_main("--write")
        self.assertIn("wrote: 2", out)
        self.assertEqual(self.ledger(), ["down55@Acme", "ready1@Acme"])

    def test_listing_failure_stops_cleanly(self):
        self.errors["/open/third-party/files/"] = urllib.error.URLError("unreachable")
        with self.assertRaises(SystemExit) as stop:
            self.run_main("--write")
        self.assertIn("unreachable", str(stop.exception.code))
        self.assertFalse(plaud.STATE.exists())

    def test_an_expired_token_is_refreshed_before_the_run(self):
        plaud.AUTH.write_text(json.dumps({"access_token": "old", "refresh_token": "r1",
                                          "expires_at": time.time() - 5}), encoding="utf-8")
        with mock.patch.object(plaud, "post_form", return_value={"access_token": "tok_test", "expires_in": 60}):
            out = self.run_main()
        self.assertIn("would write: 1", out)

    def test_a_note_left_unledgered_by_a_crash_is_recorded_not_rewritten(self):
        when = plaud.parse_when(self.start.isoformat()).astimezone()
        note = self.vault / "triage" / f"{when:%Y%m%d} Site visit.md"
        plaud.write_atomic(note, plaud.render_note("acme - Site visit", when, "ready1", None, [], "t"))
        before = note.read_bytes()

        out = self.run_main()
        self.assertIn("(exists, would record)", out)
        self.assertFalse(plaud.STATE.exists())

        out = self.run_main("--write")
        self.assertIn("wrote: 0 · recorded: 1 · skipped(exists): 0", out)
        self.assertEqual(self.ledger(), ["ready1@Acme"])
        self.assertEqual(note.read_bytes(), before)

    def test_undated_recordings_are_counted(self):
        self.list.append({"id": "nodate7", "name": "ACME - Undated", "created_at": "soon"})
        out = self.run_main()
        self.assertIn("· 4 recordings", out)
        self.assertIn("UNDATED", out)
        self.assertIn("--dump nodate7", out)
        self.assertIn("undated: 1", out)

    def test_unknown_vault_flag_stops(self):
        with self.assertRaises(SystemExit):
            self.run_main("--vault", "Other")

    def test_vault_flag_without_routes_is_ignored_out_loud(self):
        plaud.CONFIG_PATH.write_text("{}", encoding="utf-8")
        self.list = self.list[:1]
        out = self.run_main("--vault", "Home")
        self.assertIn('--vault "Home" ignored', self.stderr)
        self.assertIn("would write: 1", out)

    def routed_home(self):
        """Route "Home - ..." to a sibling vault and add one such recording."""
        (self.vault.parent / "Home").mkdir()
        plaud.CONFIG_PATH.write_text('{"route": {"Acme": ".", "Home": "Home"}}', encoding="utf-8")
        self.list.append({"id": "home55", "name": "HOME - Plumber", "created_at": self.ago(hours=6)})
        self.detail["home55"] = self.detail["other3"]
        return self.vault.parent / "Home"

    def test_another_vaults_recording_is_counted_here_and_written_by_vault_flag(self):
        home = self.routed_home()
        out = self.run_main("--write")
        self.assertNotIn("Plumber", out)
        self.assertIn("other vaults: 1", out)
        self.assertEqual(self.triage(home), [])

        out = self.run_main("--write", "--vault", "Home")
        self.assertIn("routing -> Home", out)
        self.assertEqual([name[9:] for name in self.triage(home)], ["Plumber.md"])
        self.assertIn("home55@Home", self.ledger())

    def test_all_writes_every_routed_vault_in_one_pass(self):
        home = self.routed_home()
        out = self.run_main("--write", "--all")
        self.assertIn("routing all vaults", out)
        self.assertIn("wrote: 2", out)
        self.assertEqual([name[9:] for name in self.triage(home)], ["Plumber.md"])
        self.assertEqual(len(self.triage()), 1)
        self.assertEqual(self.ledger(), ["home55@Home", "ready1@Acme"])

    def test_dump_prints_the_raw_recording_and_writes_nothing(self):
        out = self.run_main("--dump", "ready1", "--write")
        self.assertEqual(json.loads(out), {"status": 0, "data": self.detail["ready1"]})
        self.assertEqual(self.triage(), [])
        self.assertFalse(plaud.STATE.exists())

    def test_login_is_dispatched_before_any_config_or_token(self):
        plaud.CONFIG_PATH.write_text("{half", encoding="utf-8")
        with mock.patch.object(plaud, "login") as login:
            self.run_main("login")
        login.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
