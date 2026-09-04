#!/usr/bin/env python3
"""Unit tests for outlook.py. Pure functions and filesystem behaviour only - no network,
no mailbox, no credentials, and no `requests` install needed (it is stubbed at import).

Run from anywhere:
    python3 integrations/outlook/test_outlook.py

Scope: the parts that can be wrong without Microsoft being involved. The OAuth device-code
flow and the Graph queries are deliberately NOT covered - mocking them would assert that the
mock behaves, which is not the risk. Their correctness is established by running the thing.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "outlook.py"

# Stub `requests` so the suite runs on a bare interpreter. Nothing under test calls it; any
# test that reached the network would fail loudly on the missing attribute rather than
# silently hitting Microsoft.
_requests_stub = types.ModuleType("requests")
_requests_stub.Session = lambda: None      # outlook.py builds one at import; nothing calls it
sys.modules.setdefault("requests", _requests_stub)

spec = importlib.util.spec_from_file_location("outlook", SCRIPT)
osync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(osync)

# The vault convention, from base/CLAUDE.md.template: `YYYYMMDD Description.ext`. Both shipped
# integrations write into the same triage/ folder, so both must satisfy this. The granola suite
# asserts the same shape against its own filenames.
TRIAGE_NAME = re.compile(r"^\d{8} \S.*\.md$")


def vault(tmp, marker=True, triage=False):
    """A minimal directory that require_vault() should accept."""
    root = Path(tmp) / "myvault"
    (root / "resources" / "scripts").mkdir(parents=True)
    if marker:
        (root / "CLAUDE.md").write_text("<!-- para-os-template: 2026.08.02 -->", encoding="utf-8")
    if triage:
        (root / "triage").mkdir()
    return root


class SafeTitle(unittest.TestCase):
    def test_keeps_words_and_spaces(self):
        self.assertEqual(osync.safe_title("Q3 budget review"), "Q3 budget review")

    def test_strips_filesystem_illegal_characters(self):
        self.assertEqual(osync.safe_title('Re: A/B <test> "x"|y?'), "Re A B test x y")

    def test_collapses_whitespace_including_newlines(self):
        self.assertEqual(osync.safe_title("Re:\n\tQ3   budget"), "Re Q3 budget")

    def test_truncates_to_60_characters(self):
        self.assertEqual(len(osync.safe_title("x" * 200)), 60)

    def test_degenerate_subjects_fall_back(self):
        for bad in (None, "", "   ", "///???", "...", '<>:"|?*'):
            with self.subTest(subject=bad):
                self.assertEqual(osync.safe_title(bad), "no subject")

    def test_never_ends_in_space_or_dot(self):
        # Windows silently strips both from a filename, so a name that ends in one does not
        # round-trip: the file you wrote is not the file you can look up.
        for s in ("trailing dot.", "trailing space   ", "x" * 59 + " y"):
            with self.subTest(subject=s):
                out = osync.safe_title(s)
                self.assertFalse(out.endswith((" ", ".")), out)

    def test_preserves_non_ascii(self):
        self.assertEqual(osync.safe_title("Réunion budget café"), "Réunion budget café")


class WriteTriage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)

    def msg(self, **over):
        m = {"id": "AAMkAD", "receivedDateTime": "2026-07-28T09:11:00Z",
             "subject": "Q3 budget review", "from": {"emailAddress": {"name": "Jan", "address": "jan@x.com"}},
             "bodyPreview": "  hello  ", "webLink": "https://outlook.live.com/x"}
        m.update(over)
        return m

    def write(self, msg=None, reason="contact", body="hello", source="uniqueBody"):
        return osync.write_triage(self.root, "me@h.com", msg or self.msg(), reason, body, source)

    def test_filename_matches_the_vault_convention(self):
        p = self.write()
        self.assertRegex(p.name, TRIAGE_NAME)
        self.assertTrue(p.name.startswith("20260728 "), p.name)

    def test_null_from_does_not_crash(self):
        # Graph sends "from": null for drafts and some system-generated mail.
        p = self.write(self.msg(**{"from": None}))
        self.assertIn("- **From:**  <>", p.read_text(encoding="utf-8"))

    def test_null_body_preview_and_weblink_do_not_crash(self):
        p = self.write(self.msg(bodyPreview=None, webLink=None), "keyword:invoice", body="")
        self.assertIn("- **Link:** \n", p.read_text(encoding="utf-8"))

    def test_missing_received_date_still_yields_a_usable_name(self):
        p = self.write(self.msg(receivedDateTime=None))
        self.assertFalse(p.name.startswith(" "), f"leading space in {p.name!r}")
        self.assertFalse(p.name.startswith("."), f"hidden file: {p.name!r}")

    def test_same_message_twice_is_one_file(self):
        a = self.write()
        b = self.write()
        self.assertEqual(a, b)
        self.assertEqual(len(list((self.root / "triage").iterdir())), 1)

    def test_thread_replies_sharing_a_subject_get_distinct_files(self):
        a = self.write(self.msg(id="one"))
        b = self.write(self.msg(id="two"))
        self.assertNotEqual(a.name, b.name)

    def test_body_is_the_fetched_body_not_the_preview(self):
        # The bug this replaced: bodyPreview went straight into the file, capped by Graph at
        # 255 chars, with nothing in the file saying so. A record that reads as complete and
        # is not is worse than one that fails outright.
        p = self.write(body="the full message, well past what a preview would hold")
        text = p.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("the full message, well past what a preview would hold\n"))
        self.assertNotIn("hello", text)

    def test_a_preview_fallback_says_so_in_the_file(self):
        # The fallback files Graph's 255-char preview. Unmarked it is indistinguishable from
        # the full message - the exact failure fetching the body exists to end - and the
        # ledger entry written straight after means no later run revisits it. So the
        # qualification has to live in the file, where its reader is.
        p = self.write(body="cut off mid-sen", source="preview")
        text = p.read_text(encoding="utf-8")
        self.assertIn("- **Body:** preview only", text)
        self.assertIn("255-character", text)

    def test_a_full_body_carries_no_such_marker(self):
        for source in ("uniqueBody", "body"):
            p = self.write(body="the whole message", source=source)
            self.assertNotIn("- **Body:**", p.read_text(encoding="utf-8"), source)

    def test_the_marker_sits_above_the_link_so_the_body_stays_measurable(self):
        # Everything after the Link line is the message body verbatim. A marker placed below it
        # would add its own characters to the body of every degraded record, so anything that
        # measures body length - a reader judging whether a record is complete, or a tool
        # auditing for truncation - would count the note as part of the message.
        p = self.write(body="x" * 255, source="preview")
        text = p.read_text(encoding="utf-8")
        self.assertLess(text.index("- **Body:**"), text.index("- **Link:**"))
        self.assertEqual(text.split("- **Link:** https://outlook.live.com/x")[1].strip(),
                         "x" * 255)


class Addrs(unittest.TestCase):
    def test_collects_from_to_and_cc_lowercased(self):
        msg = {"from": {"emailAddress": {"address": "A@X.com"}},
               "toRecipients": [{"emailAddress": {"address": "B@X.com"}}],
               "ccRecipients": [{"emailAddress": {"address": "C@X.com"}}]}
        self.assertEqual(osync.addrs(msg), {"a@x.com", "b@x.com", "c@x.com"})

    def test_tolerates_null_and_malformed_entries(self):
        msg = {"from": None, "toRecipients": None,
               "ccRecipients": [None, {}, {"emailAddress": {}}, {"emailAddress": {"address": "d@x.com"}}]}
        self.assertEqual(osync.addrs(msg), {"d@x.com"})


class IsRelevant(unittest.TestCase):
    def test_known_contact_matches(self):
        msg = {"from": {"emailAddress": {"address": "jan@club.be"}}, "subject": "hi"}
        self.assertEqual(osync.is_relevant(msg, {"jan@club.be"}, []), "contact")

    def test_owners_own_addresses_never_count_as_a_counterparty(self):
        # Self-mail hotmail -> icloud: both addresses are the owner's and both sit in the
        # contact files, so without the exclusion every message in the box would match.
        msg = {"from": {"emailAddress": {"address": "me@hotmail.com"}},
               "toRecipients": [{"emailAddress": {"address": "me@icloud.com"}}], "subject": "note"}
        allow = {"me@hotmail.com", "me@icloud.com"}
        selves = {"me@hotmail.com", "me@icloud.com"}
        self.assertIsNone(osync.is_relevant(msg, allow, [], selves))

    def test_contact_still_matches_when_owner_is_also_on_the_thread(self):
        msg = {"from": {"emailAddress": {"address": "jan@club.be"}},
               "toRecipients": [{"emailAddress": {"address": "me@hotmail.com"}}], "subject": "hi"}
        self.assertEqual(
            osync.is_relevant(msg, {"jan@club.be", "me@hotmail.com"}, [], {"me@hotmail.com"}),
            "contact")

    def test_keyword_matches_subject_case_insensitively(self):
        msg = {"from": {"emailAddress": {"address": "nobody@x.com"}}, "subject": "Your INVOICE 42"}
        self.assertEqual(osync.is_relevant(msg, set(), ["invoice"]), "keyword:invoice")

    def test_null_subject_is_not_a_match(self):
        msg = {"from": {"emailAddress": {"address": "nobody@x.com"}}, "subject": None}
        self.assertIsNone(osync.is_relevant(msg, set(), ["invoice"]))

    def test_contact_wins_over_keyword(self):
        msg = {"from": {"emailAddress": {"address": "jan@club.be"}}, "subject": "invoice"}
        self.assertEqual(osync.is_relevant(msg, {"jan@club.be"}, ["invoice"]), "contact")


class BuildAllowlist(unittest.TestCase):
    def test_reads_every_contact_file_and_lowercases(self):
        tmp = Path(tempfile.mkdtemp())
        net = tmp / "areas" / "network"
        net.mkdir(parents=True)
        (net / "jan-claes.md").write_text("CFO, reachable at Jan.Claes@Club.BE", encoding="utf-8")
        (net / "sofie.md").write_text("- mail: sofie@club.be\n- alt: s.v@other.org", encoding="utf-8")
        self.assertEqual(osync.build_allowlist(tmp),
                         {"jan.claes@club.be", "sofie@club.be", "s.v@other.org"})

    def test_missing_network_folder_is_empty_not_an_error(self):
        self.assertEqual(osync.build_allowlist(Path(tempfile.mkdtemp())), set())


class RequireVault(unittest.TestCase):
    def run_guard(self, root):
        """require_vault() reads module-level VAULT_ROOT, so point it at the fixture."""
        original = osync.VAULT_ROOT
        osync.VAULT_ROOT = root
        try:
            osync.require_vault()
            return True
        except SystemExit:
            return False
        finally:
            osync.VAULT_ROOT = original

    def test_accepts_a_vault_with_the_template_marker(self):
        self.assertTrue(self.run_guard(vault(tempfile.mkdtemp())))

    def test_accepts_a_vault_that_only_has_triage(self):
        self.assertTrue(self.run_guard(vault(tempfile.mkdtemp(), marker=False, triage=True)))

    def test_rejects_a_plain_directory(self):
        self.assertFalse(self.run_guard(Path(tempfile.mkdtemp())))

    def test_rejects_a_repo_whose_claude_md_carries_no_marker(self):
        # The para-os repo itself: run in place from integrations/outlook/, the two-levels-up
        # guess lands here, and an existence-only check would happily file mail into the repo.
        root = Path(tempfile.mkdtemp())
        (root / "CLAUDE.md").write_text("# para-os\n\nSome other repo.", encoding="utf-8")
        self.assertFalse(self.run_guard(root))

    def test_rejects_the_real_para_os_repo(self):
        repo = HERE.parents[1]
        if not (repo / "CLAUDE.md").exists():
            self.skipTest("not running inside the para-os repo")
        self.assertFalse(self.run_guard(repo))


class AtomicState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.f = self.tmp / "outlook.json"

    def test_writes_valid_json_and_creates_parents(self):
        target = self.tmp / "secrets" / "outlook.json"
        osync.write_json_atomic(target, {"client_id": "x"})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"client_id": "x"})

    def test_leaves_no_temp_file_behind(self):
        osync.write_json_atomic(self.f, {"a": 1})
        self.assertEqual(list(self.tmp.glob("*.tmp")), [])

    def test_overwrite_replaces_content_wholesale(self):
        osync.write_json_atomic(self.f, {"a": 1, "b": 2})
        osync.write_json_atomic(self.f, {"a": 9})
        self.assertEqual(json.loads(self.f.read_text(encoding="utf-8")), {"a": 9})

    def test_save_account_keeps_a_concurrent_runs_rotation(self):
        # Two vault copies refresh different accounts at once. Writing our whole in-memory cfg
        # back would undo the other's rotation, and the superseded token is already dead.
        original = osync.CONFIG_FILE
        osync.CONFIG_FILE = self.f
        try:
            osync.write_json_atomic(self.f, {"client_id": "x", "accounts": {
                "a@h.com": {"refresh_token": "a-old"}, "b@h.com": {"refresh_token": "b-old"}}})
            stale = {"client_id": "x", "accounts": {
                "a@h.com": {"refresh_token": "a-old"}, "b@h.com": {"refresh_token": "b-old"}}}
            # the other run rotates b while we hold `stale` in memory
            osync.write_json_atomic(self.f, {"client_id": "x", "accounts": {
                "a@h.com": {"refresh_token": "a-old"}, "b@h.com": {"refresh_token": "b-NEW"}}})
            osync.save_account(stale, "a@h.com", refresh_token="a-NEW")
            on_disk = json.loads(self.f.read_text(encoding="utf-8"))["accounts"]
            self.assertEqual(on_disk["a@h.com"]["refresh_token"], "a-NEW")
            self.assertEqual(on_disk["b@h.com"]["refresh_token"], "b-NEW")
        finally:
            osync.CONFIG_FILE = original

    def test_save_account_preserves_other_fields_on_the_account(self):
        original = osync.CONFIG_FILE
        osync.CONFIG_FILE = self.f
        try:
            cfg = {"client_id": "x", "accounts": {"a@h.com": {"refresh_token": "old",
                                                              "self": ["a@icloud.com"]}}}
            osync.write_json_atomic(self.f, cfg)
            osync.save_account(cfg, "a@h.com", refresh_token="new")
            acct = json.loads(self.f.read_text(encoding="utf-8"))["accounts"]["a@h.com"]
            self.assertEqual(acct["self"], ["a@icloud.com"])
            self.assertEqual(acct["refresh_token"], "new")
        finally:
            osync.CONFIG_FILE = original

    def test_rotation_preserves_the_accounts_app_pointer(self):
        # Every refresh rewrites the account. If that write dropped client_id/authority, a work
        # mailbox would silently fall back to the personal-accounts app on the NEXT run and stop
        # authenticating, with a token error that looks like an expired login.
        original = osync.CONFIG_FILE
        osync.CONFIG_FILE = self.f
        try:
            cfg = {"client_id": "GLOBAL", "accounts": {"v@corp.be": {
                "refresh_token": "old", "client_id": "WORK", "authority": "tenant-guid"}}}
            osync.write_json_atomic(self.f, cfg)
            osync.save_account(cfg, "v@corp.be", refresh_token="new")
            on_disk = json.loads(self.f.read_text(encoding="utf-8"))
            self.assertEqual(osync.account_app(on_disk, "v@corp.be"), ("WORK", "tenant-guid"))
        finally:
            osync.CONFIG_FILE = original

    def test_login_merges_rather_than_overwriting_the_whole_file(self):
        # A device-code wait runs for minutes. Another vault's scheduled sync can rotate a
        # token in that window, and a wholesale write of the cfg read before the wait would
        # kill it - a dead token means a full re-login of a mailbox nobody touched.
        original = osync.CONFIG_FILE
        osync.CONFIG_FILE = self.f
        try:
            osync.write_json_atomic(self.f, {"client_id": "GLOBAL", "accounts": {
                "b@h.com": {"refresh_token": "b-old"}}})
            cfg = json.loads(self.f.read_text(encoding="utf-8"))
            # ...the other run rotates b while the device-code flow is still waiting
            osync.write_json_atomic(self.f, {"client_id": "GLOBAL", "accounts": {
                "b@h.com": {"refresh_token": "b-NEW"}}})
            args = argparse.Namespace(email="v@corp.be", client_id="WORK", authority="tenant")
            with mock.patch.object(osync, "device_login", return_value="v-token"), \
                    contextlib.redirect_stdout(io.StringIO()):
                osync.cmd_login(cfg, args)
            on_disk = json.loads(self.f.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["accounts"]["b@h.com"]["refresh_token"], "b-NEW")
            self.assertEqual(osync.account_app(on_disk, "v@corp.be"), ("WORK", "tenant"))
        finally:
            osync.CONFIG_FILE = original


class LoadJson(unittest.TestCase):
    """A malformed vault or machine config must fail cleanly, not with a raw traceback -
    load_config() and load_vault_config() both go through this for every file they read."""

    def test_valid_json_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text('{"a": 1}', encoding="utf-8")
            self.assertEqual(osync._load_json(p), {"a": 1})

    def test_malformed_json_exits_cleanly_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(SystemExit):
                osync._load_json(p)


class CommandRouting(unittest.TestCase):
    """`sync` is the default subcommand. Exercised through the real CLI, since the rewrite
    happens in main() against sys.argv."""

    def run_cli(self, *args, home=None):
        env = dict(os.environ, PARAOS_HOME=home or str(Path(tempfile.mkdtemp()) / "state"))
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_top_level_help_lists_every_subcommand(self):
        out = self.run_cli("--help").stdout
        for cmd in ("accounts", "login", "sync", "search", "raw"):
            self.assertIn(cmd, out, f"{cmd} missing from --help")

    def test_short_help_flag_also_reaches_the_top_level(self):
        self.assertIn("login", self.run_cli("-h").stdout)

    def test_bare_write_flag_routes_to_sync(self):
        # The /para-triage sync-script convention is `<script> --write`.
        r = self.run_cli("--write")
        self.assertIn("No config at", r.stdout + r.stderr)
        self.assertNotIn("unrecognized arguments", r.stdout + r.stderr)

    def test_a_real_subcommand_is_not_rewritten(self):
        r = self.run_cli("accounts")
        self.assertNotIn("unrecognized arguments", r.stdout + r.stderr)

    def test_search_accepts_the_all_mailboxes_flag(self):
        self.assertIn("--all-mailboxes", self.run_cli("search", "--help").stdout)

    def test_login_accepts_the_work_account_flags(self):
        out = self.run_cli("login", "--help").stdout
        self.assertIn("--client-id", out)
        self.assertIn("--authority", out)


class AccountApp(unittest.TestCase):
    """Which Entra app serves which mailbox. A personal and a work mailbox cannot share one
    registration: the "consumers" endpoint refuses org accounts outright, so a work mailbox
    needs its own app in its own tenant while the personal ones keep the machine-wide app."""

    def test_falls_back_to_the_machine_wide_app(self):
        cfg = {"client_id": "GLOBAL", "accounts": {"a@hotmail.com": {"refresh_token": "t"}}}
        self.assertEqual(osync.account_app(cfg, "a@hotmail.com"), ("GLOBAL", "consumers"))

    def test_account_overrides_win(self):
        cfg = {"client_id": "GLOBAL", "authority": "consumers",
               "accounts": {"v@corp.be": {"client_id": "WORK", "authority": "tenant-guid"}}}
        self.assertEqual(osync.account_app(cfg, "v@corp.be"), ("WORK", "tenant-guid"))

    def test_one_override_does_not_drag_the_other(self):
        # The two settings are independent: an app shared across tenants would switch only the
        # authority. Coupling them would silently send a work account at the personal app.
        cfg = {"client_id": "GLOBAL", "accounts": {"v@corp.be": {"authority": "tenant-guid"}}}
        self.assertEqual(osync.account_app(cfg, "v@corp.be"), ("GLOBAL", "tenant-guid"))

    def test_unknown_account_still_resolves(self):
        # `login` resolves the app before the account exists in the file.
        self.assertEqual(osync.account_app({"client_id": "GLOBAL", "accounts": {}}, "new@h.com"),
                         ("GLOBAL", "consumers"))

    def test_missing_client_id_everywhere_exits(self):
        with self.assertRaises(SystemExit):
            osync.account_app({"accounts": {}}, "a@h.com")

    def test_token_url_is_built_from_the_authority(self):
        self.assertEqual(osync.token_url("consumers"),
                         "https://login.microsoftonline.com/consumers/oauth2/v2.0")
        self.assertEqual(osync.token_url("7b70908c-ae16-4dd6-9fcb-5f364b57510b"),
                         "https://login.microsoftonline.com/"
                         "7b70908c-ae16-4dd6-9fcb-5f364b57510b/oauth2/v2.0")


class CmdAccounts(unittest.TestCase):
    """cmd_accounts() lists every configured account; one bad account must not blank the rest."""

    def test_an_account_with_no_resolvable_client_id_does_not_abort_the_listing(self):
        # No top-level client_id and no per-account override for stale@corp.be: account_app()
        # would sys.exit on it. That must not stop the other accounts from being listed.
        cfg = {"accounts": {
            "a@hotmail.com": {"refresh_token": "t", "client_id": "X"},
            "stale@corp.be": {"refresh_token": "t2"},
        }}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            osync.cmd_accounts(cfg, argparse.Namespace())
        text = out.getvalue()
        self.assertIn("a@hotmail.com", text)
        self.assertIn("stale@corp.be", text)


class AccountFilter(unittest.TestCase):
    """Per-account filter resolution. One vault can be fed by mailboxes
    of opposite shapes - a dedicated one where everything is in scope, a shared funnel
    where four figures a week arrive - and one vault-level list cannot serve both."""

    def test_vault_level_keywords_apply_when_accounts_is_a_list(self):
        vc = {"accounts": ["a@h.com"], "keywords": ["Invoice"]}
        self.assertEqual(osync.account_filter(vc, "a@h.com"), (["invoice"], False, True, set()))

    def test_a_per_account_block_overrides_the_vault_default(self):
        vc = {"keywords": ["invoice"],
              "accounts": {"a@h.com": {}, "info@c.com": {"keywords": ["offerte"]}}}
        self.assertEqual(osync.account_filter(vc, "info@c.com")[0], ["offerte"])
        self.assertEqual(osync.account_filter(vc, "a@h.com")[0], ["invoice"])

    def test_settings_fall_back_independently(self):
        # A block that only tightens keywords must keep the vault's match_body choice,
        # not silently revert it to the shipped default.
        vc = {"keywords": ["x"], "match_body": False,
              "accounts": {"a@h.com": {"keywords": ["y"]}}}
        self.assertEqual(osync.account_filter(vc, "a@h.com"), (["y"], False, False, set()))

    def test_match_all_is_per_account(self):
        vc = {"keywords": ["invoice"],
              "accounts": {"dedicated@c.com": {"match_all": True}, "info@c.com": {}}}
        self.assertTrue(osync.account_filter(vc, "dedicated@c.com")[1])
        self.assertFalse(osync.account_filter(vc, "info@c.com")[1])

    def test_an_unlisted_account_gets_the_vault_default(self):
        vc = {"keywords": ["invoice"], "accounts": {"a@h.com": {"match_all": True}}}
        self.assertEqual(osync.account_filter(vc, "other@h.com"), (["invoice"], False, True, set()))

    def test_a_null_override_falls_back_rather_than_crashing(self):
        # JSON `null` on a per-account key is a plausible "no opinion, use the vault
        # default" typo, not an actual empty/false value - `.get(key, default)` doesn't
        # tell those apart on its own, so this must be handled explicitly.
        vc = {"keywords": ["invoice"], "accounts": {"a@h.com": {"keywords": None}}}
        self.assertEqual(osync.account_filter(vc, "a@h.com"), (["invoice"], False, True, set()))

    def test_a_null_match_body_override_falls_back_rather_than_silently_disabling(self):
        vc = {"match_body": True, "accounts": {"a@h.com": {"match_body": None}}}
        self.assertEqual(osync.account_filter(vc, "a@h.com")[2], True)

    def test_a_null_vault_level_default_falls_back_to_the_shipped_default(self):
        vc = {"keywords": None, "accounts": {}}
        self.assertEqual(osync.account_filter(vc, "a@h.com"), ([], False, True, set()))

    def test_subject_only_keywords_default_to_empty_and_are_lowercased(self):
        self.assertEqual(osync.account_filter({"keywords": ["x"]}, "a@h.com")[3], set())
        vc = {"keywords": ["Stationsstraat"], "subject_only_keywords": ["Stationsstraat"]}
        self.assertEqual(osync.account_filter(vc, "a@h.com")[3], {"stationsstraat"})

    def test_subject_only_keywords_resolve_per_account_like_every_other_setting(self):
        vc = {"keywords": ["stationsstraat"], "subject_only_keywords": ["stationsstraat"],
              "accounts": {"a@h.com": {}, "b@h.com": {"subject_only_keywords": []}}}
        self.assertEqual(osync.account_filter(vc, "a@h.com")[3], {"stationsstraat"})
        self.assertEqual(osync.account_filter(vc, "b@h.com")[3], set())

    def test_a_null_subject_only_override_falls_back_rather_than_emptying_the_list(self):
        vc = {"subject_only_keywords": ["stationsstraat"],
              "accounts": {"a@h.com": {"subject_only_keywords": None}}}
        self.assertEqual(osync.account_filter(vc, "a@h.com")[3], {"stationsstraat"})

    def test_vault_accounts_reads_both_config_shapes(self):
        self.assertEqual(osync.vault_accounts({"accounts": ["a@h.com", "b@h.com"]}),
                         ["a@h.com", "b@h.com"])
        self.assertEqual(osync.vault_accounts({"accounts": {"a@h.com": {}, "b@h.com": {}}}),
                         ["a@h.com", "b@h.com"])
        self.assertEqual(osync.vault_accounts({}), [])


class FilterModes(unittest.TestCase):
    """match_all and match_body."""

    def test_match_all_takes_everything(self):
        msg = {"from": {"emailAddress": {"address": "stranger@x.com"}}, "subject": "hallo"}
        self.assertEqual(osync.is_relevant(msg, set(), [], match_all=True), "all")

    def test_emptying_keywords_is_stricter_not_looser(self):
        # The trap match_all exists to close: the obvious guess for "file everything"
        # leaves the contact allowlist as the only gate, which matches less, not more.
        msg = {"from": {"emailAddress": {"address": "stranger@x.com"}}, "subject": "invoice"}
        self.assertIsNone(osync.is_relevant(msg, set(), []))
        self.assertEqual(osync.is_relevant(msg, set(), [], match_all=True), "all")

    def test_body_matching_catches_a_subject_in_another_language(self):
        # The live failure: a real notice dropped because its subject was Dutch, in a
        # Dutch-speaking company, against an English keyword list.
        msg = {"from": {"emailAddress": {"address": "no-reply@sharepoint.com"}},
               "subject": "Documenten gedeeld met u",
               "bodyPreview": "A document was shared with you"}
        self.assertEqual(osync.is_relevant(msg, set(), ["shared"]), "body:shared")

    def test_body_matching_can_be_turned_off(self):
        msg = {"from": {"emailAddress": {"address": "x@y.com"}},
               "subject": "hallo", "bodyPreview": "shared"}
        self.assertIsNone(osync.is_relevant(msg, set(), ["shared"], match_body=False))

    def test_subject_wins_over_body_for_the_stated_reason(self):
        msg = {"from": {"emailAddress": {"address": "x@y.com"}},
               "subject": "invoice", "bodyPreview": "invoice"}
        self.assertEqual(osync.is_relevant(msg, set(), ["invoice"]), "keyword:invoice")

    def test_null_body_preview_does_not_crash(self):
        msg = {"from": {"emailAddress": {"address": "x@y.com"}},
               "subject": None, "bodyPreview": None}
        self.assertIsNone(osync.is_relevant(msg, set(), ["invoice"]))

    def test_contact_still_wins_over_match_all(self):
        # The reason string is what lands in the triage note; "contact" says more than "all".
        msg = {"from": {"emailAddress": {"address": "jan@club.be"}}, "subject": "x"}
        self.assertEqual(osync.is_relevant(msg, {"jan@club.be"}, [], match_all=True), "contact")


class SubjectOnlyKeywords(unittest.TestCase):
    """A keyword that is also a street name doubling as somebody's home or delivery address
    keeps matching parcel and marketing bodies forever. Turning match_body off for the whole
    account closes that at the price of every OTHER keyword's body side - the exact blind
    spot match_body exists to cover - so the opt-out is per keyword."""

    KW = ["stationsstraat", "kerkstraat"]
    SUBJ_ONLY = {"stationsstraat"}

    def rel(self, subject, body):
        msg = {"from": {"emailAddress": {"address": "no-reply@notify.courier.example"}},
               "subject": subject, "bodyPreview": body}
        return osync.is_relevant(msg, set(), self.KW, subject_only=self.SUBJ_ONLY)

    def test_the_courier_false_positive_no_longer_matches(self):
        self.assertIsNone(self.rel("Your parcel has been delivered",
                                   "Delivered at Stationsstraat 12, 1000 Brussel"))

    def test_a_real_subject_hit_on_the_same_keyword_still_matches(self):
        self.assertEqual(self.rel("Re: Stationsstraat dakwerken - factuur", ""),
                         "keyword:stationsstraat")

    def test_every_other_keyword_keeps_its_body_side(self):
        self.assertEqual(self.rel("Offerte", "in bijlage voor Kerkstraat 30"),
                         "body:kerkstraat")

    def test_a_subject_only_keyword_that_is_not_a_keyword_is_inert(self):
        msg = {"from": {"emailAddress": {"address": "x@y.com"}},
               "subject": "stationsstraat", "bodyPreview": ""}
        self.assertIsNone(osync.is_relevant(msg, set(), [], subject_only={"stationsstraat"}))


class VaultConfigNaming(unittest.TestCase):
    """The script/config rename. A half-done migration - script updated, config left behind -
    must be loud, because a copy that reads no config files nothing and looks configured."""

    def test_config_is_not_named_after_the_machine_global_secret(self):
        # ~/.paraos/secrets/outlook.json holds credentials. A vault config sharing that
        # name across opposite trust zones invites the secret-inside-a-vault mistake.
        self.assertEqual(osync.VAULT_CONFIG.name, "outlook.config.json")
        self.assertNotEqual(osync.VAULT_CONFIG.name, osync.CONFIG_FILE.name)

    def test_the_legacy_config_name_is_still_read(self):
        self.assertEqual(osync.LEGACY_VAULT_CONFIG.name, "outlook_sync.json")

    def test_both_config_names_resolve_beside_the_script(self):
        self.assertEqual(osync.VAULT_CONFIG.parent, osync.SCRIPT_DIR)
        self.assertEqual(osync.LEGACY_VAULT_CONFIG.parent, osync.SCRIPT_DIR)


class FetchBody(unittest.TestCase):
    """Filing reads the full body, not the 255-char preview the FILTER reads. The two fields
    are different jobs: a record built from the preview stops mid-sentence while presenting
    itself as a complete one."""

    MSG = {"id": "AAMkAD", "bodyPreview": "preview, capped at 255"}

    def fetch(self, payload, **over):
        """((body, source), the graph_get mock). `over` patches the message, e.g. subject."""
        with mock.patch.object(osync, "graph_get", return_value=payload) as g:
            return osync.fetch_body("tok", dict(self.MSG, **over)), g

    def test_unique_body_wins(self):
        # The reply without the quoted history: a file for the fifth message in a thread
        # should hold that message, not five copies of the thread.
        (body, source), _ = self.fetch({"uniqueBody": {"content": "just my reply"},
                              "body": {"content": "just my reply\n> and 5k of quoted thread"}})
        self.assertEqual(body, "just my reply")
        self.assertEqual(source, "uniqueBody")

    def test_falls_back_to_body_when_unique_body_is_empty(self):
        # Graph cannot always work out the reply boundary and returns an empty uniqueBody.
        (body, source), _ = self.fetch({"uniqueBody": {"content": "  "},
                                        "body": {"content": "whole thread"}})
        self.assertEqual(body, "whole thread")
        self.assertEqual(source, "body")

    def test_falls_back_to_the_preview_when_graph_returns_neither(self):
        (body, source), _ = self.fetch({})
        self.assertEqual(body, "preview, capped at 255")
        self.assertEqual(source, "preview", "the caller cannot mark what it is not told")

    def test_a_failed_fetch_files_the_preview_rather_than_killing_the_sync(self):
        with mock.patch.object(osync, "graph_get", side_effect=RuntimeError("503")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            body, source = osync.fetch_body("tok", dict(self.MSG))
        self.assertEqual(body, "preview, capped at 255")
        self.assertEqual(source, "preview", "a failed fetch must be reported as degraded")
        self.assertIn("body fetch failed", err.getvalue())

    def test_graph_is_asked_for_plain_text_server_side(self):
        # Without the Prefer header the body comes back as HTML and something here would
        # have to parse it. Let Graph do the conversion.
        _, g = self.fetch({"body": {"content": "x"}})
        self.assertEqual(g.call_args.kwargs["prefer"], 'outlook.body-content-type="text"')

    def test_a_forward_files_the_forwarded_content_not_the_covering_note(self):
        # uniqueBody excludes whatever Graph considers quoted, and for a forward that is the
        # forwarded message itself - the reason the mail exists. Taking uniqueBody here cuts
        # the file off at the client's "Begin forwarded message:" line.
        (body, source), _ = self.fetch(
            {"uniqueBody": {"content": "Dag Sofie, in bijlage heb ik de offerte gezet"},
             "body": {"content": "Dag Sofie, in bijlage heb ik de offerte gezet\n\n"
                                 "Begin forwarded message:\n\nTotaal 12.400 EUR"}},
            subject="Fwd: Offerte Kerkstraat en Molenweg")
        self.assertIn("12.400 EUR", body)
        self.assertEqual(source, "body")

    def test_a_forward_with_an_empty_body_still_falls_back_to_unique_body(self):
        got, _ = self.fetch({"body": {"content": "  "},
                             "uniqueBody": {"content": "covering note"}},
                            subject="FW: Offerte")
        self.assertEqual(got, ("covering note", "uniqueBody"))

    def test_a_reply_is_unaffected_and_still_drops_the_quoted_history(self):
        # The negative control: the forward branch must not reach replies, or every reply
        # goes back to being five copies of its own thread.
        got, _ = self.fetch({"uniqueBody": {"content": "Done"},
                             "body": {"content": "Done\n> 600 chars of quoted thread"}},
                            subject="Re: Offerte")
        self.assertEqual(got, ("Done", "uniqueBody"))

    def test_a_message_id_with_url_unsafe_characters_is_escaped(self):
        # Graph ids are base64-derived and can carry "+", "/" and "=". An unescaped "/" splits
        # the path into another segment, Graph 404s, and the message is filed as a preview - a
        # degraded record caused by a URL this script built wrong rather than by the mailbox.
        with mock.patch.object(osync, "graph_get", return_value={"body": {"content": "x"}}) as g:
            osync.fetch_body("tok", {"id": "AA/k+D=", "bodyPreview": ""})
        path = g.call_args.args[1]
        self.assertIn("/me/messages/AA%2Fk%2BD%3D", path)
        self.assertNotIn("AA/k+D=", path)
        self.assertIn("?$select=", path, "only the id is escaped, not the query that follows")

    def test_it_is_a_single_message_get_asking_for_both_fields(self):
        _, g = self.fetch({"body": {"content": "x"}})
        path = g.call_args.args[1]
        self.assertIn("/me/messages/AAMkAD", path)
        self.assertIn("uniqueBody", path)


class IsForward(unittest.TestCase):
    """`uniqueBody` means opposite things for a reply and a forward, and the subject is the
    only thing filing has to tell them apart with."""

    def test_a_forward_is_one_whatever_the_client_wrote(self):
        for s in ("Fwd: Offerte Kerkstraat", "FW: 26.019039 - Rapport lekdetectie",
                  "fwd: lowercase", "  Fw : leading space and a spaced colon"):
            self.assertTrue(osync.is_forward(s), s)

    def test_a_reply_or_a_plain_subject_is_not(self):
        for s in ("Re: Offerte", "Offerte", "", None, "Forwarding you the offer"):
            self.assertFalse(osync.is_forward(s), s)

    def test_a_reply_to_a_forward_is_still_a_forward(self):
        # The Re: chain is on the outside; what decides the body ordering is the Fwd: under it.
        self.assertTrue(osync.is_forward("Re: Fwd: Offerte"))
        self.assertTrue(osync.is_forward("RE: Re: FW: Offerte"))

    def test_a_localised_client_writes_its_own_forward_prefix(self):
        # The subject arrives in the sender's language, not the filter's. Missing one of these
        # is not a cosmetic miss: the reply ordering then takes uniqueBody, which for a forward
        # is the covering note alone, and the forwarded content never reaches the file. Exactly
        # the defect this function was added to prevent, recurring one locale over.
        for s in ("TR: Offre",                    # French
                  "WG: Angebot",                  # German
                  "Doorst: Offerte",              # Dutch
                  "RV: Oferta",                   # Spanish
                  "ENC: Proposta",                # Portuguese
                  "VS: Tilbud",                   # Danish / Norwegian
                  "VB: Offert",                   # Swedish
                  "I: Preventivo"):               # Italian
            self.assertTrue(osync.is_forward(s), s)

    def test_a_localised_reply_prefix_does_not_hide_the_forward_under_it(self):
        # The reply half is not enumerated - any `XX:` token is stepped over - so a German or
        # Dutch reply sitting on top of a forward still resolves to a forward.
        for s in ("AW: Fwd: Offerte", "Antw: FW: Offerte", "SV: VB: Offert",
                  "RIF: WG: Angebot"):
            self.assertTrue(osync.is_forward(s), s)

    def test_an_ordinary_colon_in_a_subject_is_not_a_forward(self):
        # The prefix scan must not turn every colon into a routing decision.
        for s in ("Note: the roof needs doing", "Update: plan v2", "Q3: budget",
                  "Contract renewal: final", "Re: Note: something"):
            self.assertFalse(osync.is_forward(s), s)


class SearchMessages(unittest.TestCase):
    """`quote` is shared with fetch_body from the module imports rather than imported inside
    this function, so the search path needs a guard of its own: an unquoted $search sends the
    user's spaces and punctuation raw and Graph rejects the request."""

    def test_the_query_is_quoted_and_phrase_wrapped(self):
        with mock.patch.object(osync, "graph_get", return_value={"value": []}) as g:
            osync.search_messages("tok", 'contract renewal & co')
        path = g.call_args.args[1]
        self.assertIn("$search=%22contract%20renewal%20%26%20co%22", path)

    def test_it_stops_at_the_limit(self):
        page = {"value": [{"id": str(i)} for i in range(50)], "@odata.nextLink": "http://next"}
        with mock.patch.object(osync, "graph_get", return_value=page):
            self.assertEqual(len(osync.search_messages("tok", "x", limit=20)), 20)


class GraphGet(unittest.TestCase):
    def get(self, *args, **kwargs):
        """graph_get against a stubbed session; returns the session mock."""
        session = mock.Mock()
        session.get.return_value = mock.Mock(json=lambda: {}, raise_for_status=lambda: None)
        with mock.patch.object(osync, "SESSION", session):
            osync.graph_get(*args, **kwargs)
        return session

    def test_prefer_header_is_omitted_unless_asked_for(self):
        session = self.get("tok", "/me/messages")
        self.assertNotIn("Prefer", session.get.call_args.kwargs["headers"])

    def test_reads_go_through_one_pooled_session(self):
        # fetch_body makes this one call per filed message. Through `requests.get` each would
        # build and discard its own session, paying a fresh DNS + TCP + TLS handshake.
        self.assertIsInstance(osync.SESSION, object)
        session = self.get("tok", "/me/messages")
        session.get.assert_called_once()


class SyncAccountPresence(unittest.TestCase):
    """A refresh token lives only on the machine it was granted on. On a vault fed by several
    mailboxes NO machine ever holds every account - not even the machine of whoever added the
    second one - so a missing account is an absence to work around, not a reason to exit
    before touching a single mailbox."""

    ACCOUNTS = ["a@x.com", "b@x.com"]

    def run_sync(self, cfg_accounts, account=None, filt=([], True, True, frozenset()),
                 msgs=(), write=False):
        """cmd_sync with the vault, the ledger and Graph stubbed out.

        Returns (mailboxes read, stdout, stderr) - the per-account scope line and the closing
        summary are on stdout, the per-skip warnings on stderr.
        """
        cfg = {"accounts": {e: {"refresh_token": "t"} for e in cfg_accounts}}
        args = argparse.Namespace(account=account, days=7, write=write)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(osync, "require_vault"), \
                mock.patch.object(osync, "load_vault_config", return_value={}), \
                mock.patch.object(osync, "vault_accounts", return_value=list(self.ACCOUNTS)), \
                mock.patch.object(osync, "load_ledger", return_value={}), \
                mock.patch.object(osync, "save_ledger"), \
                mock.patch.object(osync, "write_triage"), \
                mock.patch.object(osync, "build_allowlist", return_value={"z@x.com"}), \
                mock.patch.object(osync, "account_filter", return_value=filt), \
                mock.patch.object(osync, "access_token", side_effect=lambda c, e: "tok"), \
                mock.patch.object(osync, "fetch_messages", return_value=list(msgs)) as fetched, \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            osync.cmd_sync(cfg, args)
        return fetched.call_count, out.getvalue(), err.getvalue()

    def test_a_missing_account_no_longer_blocks_the_ones_that_are_present(self):
        n, _, err = self.run_sync(["a@x.com"])
        self.assertEqual(n, 1, "the logged-in account was not synced")
        self.assertIn("b@x.com", err)
        self.assertIn("skipping", err)

    def test_every_account_present_syncs_them_all_and_says_nothing(self):
        n, _, err = self.run_sync(self.ACCOUNTS)
        self.assertEqual(n, 2)
        self.assertNotIn("skipping", err)

    def test_no_account_logged_in_here_still_exits(self):
        # Nothing to do and no partial result to report: that is a real stop.
        with self.assertRaises(SystemExit):
            self.run_sync([])

    def test_a_named_account_that_is_not_logged_in_exits(self):
        # A direct ask deserves a direct answer. Skipping past it would answer a question
        # the user did not put.
        with self.assertRaises(SystemExit):
            self.run_sync(["a@x.com"], account="b@x.com")

    def test_a_named_account_that_is_logged_in_syncs_only_that_one(self):
        n, _, _ = self.run_sync(self.ACCOUNTS, account="a@x.com")
        self.assertEqual(n, 1)

    def test_the_scope_line_names_the_subject_only_count(self):
        # With the opt-out resolving per keyword as well as per account, "which filter ran
        # against this mailbox" stops being answerable from the config at a glance.
        _, out, _ = self.run_sync(self.ACCOUNTS, filt=(["a", "b"], False, True, {"a"}))
        self.assertIn("2 keywords (subject+body, 1 subject-only)", out)

    def test_the_scope_line_stays_as_it_was_when_there_are_none(self):
        _, out, _ = self.run_sync(self.ACCOUNTS, filt=(["a", "b"], False, True, set()))
        self.assertIn("2 keywords (subject+body)", out)

    def test_the_scope_line_does_not_claim_a_subject_only_opt_out_that_cannot_apply(self):
        # With match_body off the body loop never runs, so subject_only is inert. Reporting a
        # count for it says "subject only, 1 subject-only" - self-contradictory, and it shows
        # an opt-out as in force when it is doing nothing.
        _, out, _ = self.run_sync(self.ACCOUNTS, filt=(["a", "b"], False, False, {"a"}))
        self.assertIn("2 keywords (subject only)", out)
        self.assertNotIn("subject-only", out)

    def test_the_summary_reports_the_mailboxes_it_could_not_read(self):
        # The per-skip warning goes to stderr at the top and then scrolls off under one line
        # per matched message. Without the summary saying so, a run that never opened half the
        # vault's mail reads exactly like a run that opened all of it.
        _, out, _ = self.run_sync(["a@x.com"])
        self.assertIn("1 mailbox(es) skipped", out)
        self.assertIn("b@x.com", out.rsplit("\n\n", 1)[-1])

    def test_the_summary_reports_records_filed_from_the_preview(self):
        # The per-message stderr warning scrolls off the same way the mailbox skip does, and
        # a degraded record is permanent once the ledger entry lands beside it.
        msgs = [{"id": "1", "subject": "x", "receivedDateTime": "2026-07-28T00:00:00Z",
                 "from": {"emailAddress": {"address": "z@x.com"}}}]
        with mock.patch.object(osync, "fetch_body", return_value=("p", "preview")):
            _, out, _ = self.run_sync(["a@x.com"], account="a@x.com", msgs=msgs, write=True)
        self.assertIn("1 record(s) filed from the preview", out)

    def test_the_summary_stays_quiet_when_every_mailbox_was_read(self):
        _, out, _ = self.run_sync(self.ACCOUNTS)
        self.assertNotIn("skipped", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
