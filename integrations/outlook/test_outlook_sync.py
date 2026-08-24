#!/usr/bin/env python3
"""Unit tests for outlook_sync.py. Pure functions and filesystem behaviour only - no network,
no mailbox, no credentials, and no `requests` install needed (it is stubbed at import).

Run from anywhere:
    python3 integrations/outlook/test_outlook_sync.py

Scope: the parts that can be wrong without Microsoft being involved. The OAuth device-code
flow and the Graph queries are deliberately NOT covered - mocking them would assert that the
mock behaves, which is not the risk. Their correctness is established by running the thing.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "outlook_sync.py"

# Stub `requests` so the suite runs on a bare interpreter. Nothing under test calls it; any
# test that reached the network would fail loudly on the missing attribute rather than
# silently hitting Microsoft.
sys.modules.setdefault("requests", types.ModuleType("requests"))

spec = importlib.util.spec_from_file_location("outlook_sync", SCRIPT)
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

    def test_filename_matches_the_vault_convention(self):
        p = osync.write_triage(self.root, "me@h.com", self.msg(), "contact")
        self.assertRegex(p.name, TRIAGE_NAME)
        self.assertTrue(p.name.startswith("20260728 "), p.name)

    def test_null_from_does_not_crash(self):
        # Graph sends "from": null for drafts and some system-generated mail.
        p = osync.write_triage(self.root, "me@h.com", self.msg(**{"from": None}), "contact")
        self.assertIn("- **From:**  <>", p.read_text(encoding="utf-8"))

    def test_null_body_preview_and_weblink_do_not_crash(self):
        p = osync.write_triage(self.root, "me@h.com",
                               self.msg(bodyPreview=None, webLink=None), "keyword:invoice")
        self.assertIn("- **Link:** \n", p.read_text(encoding="utf-8"))

    def test_missing_received_date_still_yields_a_usable_name(self):
        p = osync.write_triage(self.root, "me@h.com", self.msg(receivedDateTime=None), "contact")
        self.assertFalse(p.name.startswith(" "), f"leading space in {p.name!r}")
        self.assertFalse(p.name.startswith("."), f"hidden file: {p.name!r}")

    def test_same_message_twice_is_one_file(self):
        a = osync.write_triage(self.root, "me@h.com", self.msg(), "contact")
        b = osync.write_triage(self.root, "me@h.com", self.msg(), "contact")
        self.assertEqual(a, b)
        self.assertEqual(len(list((self.root / "triage").iterdir())), 1)

    def test_thread_replies_sharing_a_subject_get_distinct_files(self):
        a = osync.write_triage(self.root, "me@h.com", self.msg(id="one"), "contact")
        b = osync.write_triage(self.root, "me@h.com", self.msg(id="two"), "contact")
        self.assertNotEqual(a.name, b.name)

    def test_body_is_the_preview_stripped(self):
        p = osync.write_triage(self.root, "me@h.com", self.msg(), "contact")
        self.assertTrue(p.read_text(encoding="utf-8").endswith("hello\n"))


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

    def test_save_token_keeps_a_concurrent_runs_rotation(self):
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
            osync.save_token(stale, "a@h.com", "a-NEW")
            on_disk = json.loads(self.f.read_text(encoding="utf-8"))["accounts"]
            self.assertEqual(on_disk["a@h.com"]["refresh_token"], "a-NEW")
            self.assertEqual(on_disk["b@h.com"]["refresh_token"], "b-NEW")
        finally:
            osync.CONFIG_FILE = original

    def test_save_token_preserves_other_fields_on_the_account(self):
        original = osync.CONFIG_FILE
        osync.CONFIG_FILE = self.f
        try:
            cfg = {"client_id": "x", "accounts": {"a@h.com": {"refresh_token": "old",
                                                              "self": ["a@icloud.com"]}}}
            osync.write_json_atomic(self.f, cfg)
            osync.save_token(cfg, "a@h.com", "new")
            acct = json.loads(self.f.read_text(encoding="utf-8"))["accounts"]["a@h.com"]
            self.assertEqual(acct["self"], ["a@icloud.com"])
            self.assertEqual(acct["refresh_token"], "new")
        finally:
            osync.CONFIG_FILE = original


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
