#!/usr/bin/env python3
"""Unit tests for outlook.py. No network, no mailbox, no browser, no credentials, and no
`requests` install needed (it is stubbed at import).

Run from anywhere:
    python3 integrations/outlook/test_outlook.py

Scope: the parts that can be wrong without Microsoft being involved. Where a test reaches the
OAuth flows or a Graph read, the HTTP session is a mock and the assertions are about this
script's side of the exchange: what it sends (a PKCE verifier that hashes to the challenge it
sent), what it keeps (a rotated refresh token that must reach disk), and how it fails (an exit
that carries the diagnosis). Whether Microsoft accepts any of it is established by running the
thing.
"""
import argparse
import base64
import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "outlook.py"

# Stub `requests` so the suite runs on a bare interpreter. Nothing under test calls it; any
# test that reached the network would fail loudly on the missing attribute rather than
# silently hitting Microsoft.
_requests_stub = types.ModuleType("requests")
_requests_stub.Session = lambda: None      # built at import; a test that reaches it patches SESSION


class _HTTPError(Exception):
    """Stands in for requests.HTTPError, which fetch_messages catches to tell a mailbox
    that lacks one of FETCH_FOLDERS from a real failure. Carries `response` the way the
    real one does, since that is the attribute the handler reads."""

    def __init__(self, *args, response=None):
        super().__init__(*args)
        self.response = response


_requests_stub.HTTPError = _HTTPError
sys.modules.setdefault("requests", _requests_stub)

spec = importlib.util.spec_from_file_location("outlook", SCRIPT)
osync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(osync)


def vault(tmp, marker=True, triage=False):
    """A minimal directory that require_vault() should accept."""
    root = Path(tmp) / "myvault"
    (root / "resources" / "scripts").mkdir(parents=True)
    if marker:
        (root / "CLAUDE.md").write_text("<!-- para-os-template: 2026.08.02 -->", encoding="utf-8")
    if triage:
        (root / "triage").mkdir()
    return root


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
            # device_code=True on purpose: this test is about the long login wait, and the
            # default flow is now the browser one, which would bind a socket and sit for
            # five minutes waiting for a redirect that no test is going to send it.
            args = argparse.Namespace(email="v@corp.be", client_id="WORK", authority="tenant",
                                      shared=False, device_code=True)
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


class LoadConfigFiles(unittest.TestCase):
    """Where each config is read from. The vault config was renamed together with the script,
    so a copy updated without its config must still find the old name, and say so: a copy
    that silently reads no config looks configured and reads nothing."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.current = self.dir / "outlook.config.json"
        self.legacy = self.dir / "outlook_sync.json"
        for name, path in (("VAULT_CONFIG", self.current), ("LEGACY_VAULT_CONFIG", self.legacy)):
            patcher = mock.patch.object(osync, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def load(self, **kwargs):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            vc = osync.load_vault_config(**kwargs)
        return vc, err.getvalue()

    def test_the_current_name_is_read_without_a_notice(self):
        self.current.write_text('{"accounts": ["a@h.com"]}', encoding="utf-8")
        self.assertEqual(self.load(), ({"accounts": ["a@h.com"]}, ""))

    def test_the_legacy_name_is_read_with_a_notice_naming_both_files(self):
        self.legacy.write_text('{"accounts": ["old@h.com"]}', encoding="utf-8")
        vc, err = self.load()
        self.assertEqual(vc, {"accounts": ["old@h.com"]})
        self.assertIn("outlook_sync.json", err)
        self.assertIn("Rename it to outlook.config.json", err)

    def test_the_current_name_wins_when_both_exist(self):
        # A rename done by copying rather than moving: the new file is the one being edited.
        self.current.write_text('{"accounts": ["new@h.com"]}', encoding="utf-8")
        self.legacy.write_text('{"accounts": ["old@h.com"]}', encoding="utf-8")
        self.assertEqual(self.load(), ({"accounts": ["new@h.com"]}, ""))

    def test_a_missing_config_is_empty_where_it_is_optional(self):
        # `accounts` and `search` still have something to show without one.
        self.assertEqual(self.load(required=False), ({}, ""))

    def test_a_missing_config_exits_with_the_shape_to_create_where_it_is_required(self):
        with self.assertRaises(SystemExit) as e:
            self.load()
        self.assertIn(str(self.current), str(e.exception))
        self.assertIn('{"accounts": [', str(e.exception))

    def test_the_secrets_file_is_required_and_read_as_json(self):
        secrets = self.dir / "secrets" / "outlook.json"
        with mock.patch.object(osync, "CONFIG_FILE", secrets):
            with self.assertRaises(SystemExit) as e:
                osync.load_config()
            self.assertIn(str(secrets), str(e.exception))
            secrets.parent.mkdir()
            secrets.write_text('{"client_id": "X", "accounts": {}}', encoding="utf-8")
            self.assertEqual(osync.load_config(), {"client_id": "X", "accounts": {}})


class CommandRouting(unittest.TestCase):
    """`sync` is the default subcommand. Exercised through the real CLI, since the rewrite
    happens in main() against sys.argv."""

    def run_cli(self, *args, home=None):
        env = dict(os.environ, PARAOS_HOME=home or str(Path(tempfile.mkdtemp()) / "state"))
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_top_level_help_lists_every_subcommand(self):
        out = self.run_cli("--help").stdout
        for cmd in ("accounts", "login", "fetch", "search", "raw"):
            self.assertIn(cmd, out, f"{cmd} missing from --help")

    def test_short_help_flag_also_reaches_the_top_level(self):
        self.assertIn("login", self.run_cli("-h").stdout)

    def test_a_bare_invocation_asks_for_a_subcommand(self):
        # There used to be a default (`sync`), so `outlook.py --write` did something. Nothing
        # should quietly pick a behaviour for a script that reads mailboxes.
        r = self.run_cli()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("required", (r.stdout + r.stderr).lower())

    def test_the_removed_write_path_is_not_reachable_from_the_cli(self):
        r = self.run_cli("sync", "--write")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("invalid choice", (r.stdout + r.stderr).lower())

    def test_a_real_subcommand_is_not_rewritten(self):
        r = self.run_cli("accounts")
        self.assertNotIn("unrecognized arguments", r.stdout + r.stderr)

    def test_search_accepts_the_all_mailboxes_flag(self):
        self.assertIn("--all-mailboxes", self.run_cli("search", "--help").stdout)

    def test_login_accepts_the_work_account_flags(self):
        out = self.run_cli("login", "--help").stdout
        self.assertIn("--client-id", out)
        self.assertIn("--authority", out)
        self.assertIn("--shared", out)

    def test_a_subcommand_reads_the_secrets_file_under_paraos_home(self):
        # PARAOS_HOME is how a second machine profile, and every test, keeps its hands off
        # the real ~/.paraos. A subcommand that ignored it would read someone's live tokens.
        home = Path(tempfile.mkdtemp()) / "state"
        (home / "secrets").mkdir(parents=True)
        (home / "secrets" / "outlook.json").write_text(json.dumps(
            {"client_id": "X", "accounts": {"a@h.com": {"refresh_token": "t"}}}), encoding="utf-8")
        r = self.run_cli("accounts", home=str(home))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("a@h.com", r.stdout)
        self.assertIn("[logged in]", r.stdout)


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
        self.assertEqual(osync.token_url("11111111-2222-3333-4444-555555555555"),
                         "https://login.microsoftonline.com/"
                         "11111111-2222-3333-4444-555555555555/oauth2/v2.0")


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

    CFG = {"client_id": "GLOBAL", "accounts": {
        "me@corp.com": {"refresh_token": "t", "authority": "tenant-guid"},
        "info@corp.com": {"via": "me@corp.com"},
        "new@h.com": {},
        "home@h.com": {"refresh_token": "t"},
    }}

    def listing(self, cfg, feeds=()):
        """cmd_accounts output as {email: its line}, with this vault's feeds stubbed."""
        out = io.StringIO()
        with mock.patch.object(osync, "load_vault_config", return_value={"accounts": list(feeds)}), \
                contextlib.redirect_stdout(out):
            osync.cmd_accounts(cfg, argparse.Namespace())
        lines = {}
        for line in out.getvalue().splitlines():
            words = line.replace("*", " ").split()
            if words and words[0] in cfg.get("accounts", {}):
                lines[words[0]] = line
        return lines, out.getvalue()

    def test_an_empty_config_says_so_rather_than_printing_nothing(self):
        _, text = self.listing({"client_id": "X", "accounts": {}})
        self.assertIn("No accounts configured yet.", text)

    def test_a_shared_mailbox_reads_as_shared_not_as_a_login_still_to_do(self):
        # It has no sign-in of its own, so "NOT logged in" would name a step nobody can take.
        lines, _ = self.listing(self.CFG)
        self.assertIn("[shared, read via me@corp.com]", lines["info@corp.com"])
        self.assertNotIn("NOT logged in", lines["info@corp.com"])
        self.assertIn("NOT logged in (run login)", lines["new@h.com"])
        self.assertIn("[logged in]", lines["home@h.com"])

    def test_the_one_account_asking_for_the_wider_scope_is_marked(self):
        # It is the only account that can fail with AADSTS65001; hiding which one it is makes
        # that failure look like it came from nowhere.
        lines, _ = self.listing(self.CFG)
        self.assertIn("+Mail.Read.Shared", lines["me@corp.com"])
        self.assertNotIn("+Mail.Read.Shared", lines["home@h.com"])

    def test_this_vaults_feeds_are_starred_and_a_foreign_tenant_is_shown(self):
        lines, text = self.listing(self.CFG, feeds=["me@corp.com"])
        self.assertTrue(lines["me@corp.com"].lstrip().startswith("*"))
        self.assertFalse(lines["home@h.com"].lstrip().startswith("*"))
        self.assertIn("via tenant-guid", lines["me@corp.com"])
        self.assertNotIn("via", lines["home@h.com"])
        self.assertIn("(* = feeds this vault", text)


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


class SearchMessages(unittest.TestCase):
    """`quote` is shared with fetch_messages from the module imports rather than imported inside
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


class FetchMessagesFolderScope(unittest.TestCase):
    """`fetch` used to read /me/messages, which is the whole mailbox: Junk Email, Deleted
    Items and Sent Items included. It re-surfaced mail the spam filter had caught and mail
    the operator had thrown away, and offered it back as a candidate to triage (README.md
    has the measurement).

    Nothing failed when it regressed - the run simply looked productive - so the scope is
    pinned here rather than left to the docstring."""

    def paths(self, folders=None):
        """fetch_messages against a stubbed graph_get; returns the request paths it built."""
        with mock.patch.object(osync, "graph_get", return_value={"value": []}) as g:
            if folders is not None:
                with mock.patch.object(osync, "FETCH_FOLDERS", folders):
                    osync.fetch_messages("tok", 2)
            else:
                osync.fetch_messages("tok", 2)
        return [c.args[1] for c in g.call_args_list]

    def test_it_reads_the_inbox_and_the_archive(self):
        self.assertEqual(
            [p.split("?")[0] for p in self.paths()],
            ["/me/mailFolders/inbox/messages", "/me/mailFolders/archive/messages"])

    def test_it_never_reads_the_whole_mailbox(self):
        for p in self.paths():
            self.assertFalse(p.startswith("/me/messages"), p)

    def test_it_never_reads_a_disposal_folder(self):
        joined = " ".join(self.paths())
        for folder in ("junkemail", "deleteditems", "sentitems", "drafts"):
            self.assertNotIn(folder, joined)

    def test_a_missing_folder_does_not_cost_the_run_the_other_folders(self):
        # A mailbox with no archive must still yield its inbox.
        resp = mock.Mock(status_code=404)

        def get(_tok, path, *a, **k):
            if "archive" in path:
                raise osync.requests.HTTPError(response=resp)
            return {"value": [{"id": "1", "receivedDateTime": "2026-09-08T00:00:00Z"}]}

        with mock.patch.object(osync, "graph_get", side_effect=get):
            self.assertEqual(len(osync.fetch_messages("tok", 2)), 1)

    def test_a_non_404_error_is_still_fatal(self):
        resp = mock.Mock(status_code=500)
        with mock.patch.object(osync, "graph_get",
                               side_effect=osync.requests.HTTPError(response=resp)):
            with self.assertRaises(osync.requests.HTTPError):
                osync.fetch_messages("tok", 2)

    def test_a_message_in_two_folders_is_returned_once(self):
        page = {"value": [{"id": "dup", "receivedDateTime": "2026-09-08T00:00:00Z"}]}
        with mock.patch.object(osync, "graph_get", return_value=page):
            self.assertEqual(len(osync.fetch_messages("tok", 2)), 1)

    def test_it_stops_at_the_message_cap_and_says_so(self):
        # `search` has always had --limit; this is the same bound for the path that pages a
        # whole window. A run that dies of its own size has fetched everything and emitted
        # nothing, so the truncation is reported rather than left silent.
        def get(_tok, _path, *a, **k):
            get.page += 1
            return {"value": [{"id": f"p{get.page}-{i}",
                               "receivedDateTime": "2026-09-08T00:00:00Z"} for i in range(50)],
                    "@odata.nextLink": "https://graph.example/next"}

        get.page = 0
        err = io.StringIO()
        with mock.patch.object(osync, "graph_get", side_effect=get), \
                contextlib.redirect_stderr(err):
            got = osync.fetch_messages("tok", 2, limit=120)
        self.assertEqual(len(got), 300)          # per folder: the page that crossed the cap, then stop
        self.assertIn("inbox: stopped at 120", err.getvalue())
        self.assertIn("archive: stopped at 120", err.getvalue())
        self.assertIn("window not fully covered", err.getvalue())

    def test_a_full_inbox_does_not_cost_the_run_its_archive(self):
        # The cap used to be shared: an inbox of exactly `limit` messages with no next page
        # left the archive unread, and nothing was printed because the inbox was not truncated.
        def get(_tok, path, *a, **k):
            folder = "inbox" if "inbox" in path else "archive"
            n = 100 if folder == "inbox" else 3
            return {"value": [{"id": f"{folder}-{i}", "receivedDateTime": "2026-09-08T00:00:00Z"}
                              for i in range(n)]}

        err = io.StringIO()
        with mock.patch.object(osync, "graph_get", side_effect=get), \
                contextlib.redirect_stderr(err):
            got = osync.fetch_messages("tok", 2, limit=100)
        self.assertEqual(sum(m["id"].startswith("archive-") for m in got), 3)
        self.assertEqual(err.getvalue(), "")

    def test_the_merged_result_is_newest_first(self):
        # Each folder is sorted on its own, so the concatenation is not.
        def get(_tok, path, *a, **k):
            when = "2026-09-01T00:00:00Z" if "inbox" in path else "2026-09-08T00:00:00Z"
            return {"value": [{"id": path[:24], "receivedDateTime": when}]}

        with mock.patch.object(osync, "graph_get", side_effect=get):
            got = [m["receivedDateTime"] for m in osync.fetch_messages("tok", 2)]
        self.assertEqual(got, sorted(got, reverse=True))


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

    def test_prefer_header_is_sent_when_asked_for(self):
        session = self.get("tok", "/me/messages", prefer='outlook.body-content-type="text"')
        headers = session.get.call_args.kwargs["headers"]
        self.assertEqual(headers["Prefer"], 'outlook.body-content-type="text"')
        self.assertEqual(headers["Authorization"], "Bearer tok")

    def test_a_relative_path_is_joined_to_graph_and_a_next_link_is_used_verbatim(self):
        # Paging hands back an absolute @odata.nextLink; prefixing it with GRAPH again would
        # turn the second page of every fetch into a 404.
        self.assertEqual(self.get("tok", "/me/messages").get.call_args.args[0],
                         f"{osync.GRAPH}/me/messages")
        next_link = "https://graph.microsoft.com/v1.0/me/messages?$skip=100"
        self.assertEqual(self.get("tok", next_link).get.call_args.args[0], next_link)

    def test_reads_go_through_one_pooled_session(self):
        # fetch_messages makes this one call per filed message. Through `requests.get` each would
        # build and discard its own session, paying a fresh DNS + TCP + TLS handshake.
        self.assertIsInstance(osync.SESSION, object)
        session = self.get("tok", "/me/messages")
        session.get.assert_called_once()

    @staticmethod
    def _throttled(retry_after="2"):
        return mock.Mock(status_code=429, headers={"Retry-After": retry_after})

    @staticmethod
    def _ok(body=None):
        return mock.Mock(status_code=200, headers={}, json=lambda: body or {},
                         raise_for_status=lambda: None)

    def throttle_run(self, responses):
        session = mock.Mock()
        session.get.side_effect = responses
        with mock.patch.object(osync, "SESSION", session), \
                mock.patch.object(osync.time, "sleep") as slept, \
                contextlib.redirect_stderr(io.StringIO()):
            try:
                result = osync.graph_get("tok", "/me/messages")
            except osync.requests.HTTPError:
                result = None
        return result, session, slept

    def test_a_throttled_read_waits_and_retries(self):
        # Graph answers a caller that pages hard with 429. Unhandled, that landed partway
        # through a run and discarded every message already fetched.
        result, session, slept = self.throttle_run([self._throttled(), self._ok({"value": []})])
        self.assertEqual(result, {"value": []})
        self.assertEqual(session.get.call_count, 2)
        slept.assert_called_once_with(2)

    def test_an_absurd_retry_after_is_capped(self):
        # A wait longer than the cap is worse than failing: nothing is watching a hung run.
        _, _, slept = self.throttle_run([self._throttled("86400"), self._ok()])
        slept.assert_called_once_with(osync.THROTTLE_MAX_WAIT)

    def test_a_persistent_throttle_gives_up_rather_than_hanging(self):
        stuck = self._throttled()
        stuck.raise_for_status.side_effect = osync.requests.HTTPError(response=stuck)
        result, session, _ = self.throttle_run([stuck] * (osync.THROTTLE_RETRIES + 1))
        self.assertIsNone(result)
        self.assertEqual(session.get.call_count, osync.THROTTLE_RETRIES + 1)

    def test_a_retry_after_that_is_not_seconds_backs_off_by_attempt(self):
        # Retry-After may be an HTTP date, or absent on a 503. Neither may crash the read.
        unavailable = mock.Mock(status_code=503, headers={})
        _, session, slept = self.throttle_run(
            [self._throttled("Wed, 21 Oct 2015 07:28:00 GMT"), unavailable, self._ok()])
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual([c.args[0] for c in slept.call_args_list], [5, 10])


class HasUnsubscribe(unittest.TestCase):
    """The one mechanical cut `fetch` makes before a skill judges anything.

    Tested for what it must NOT do: a rule that quietly drops real correspondence would
    defeat the point of fetching for judgment in the first place.
    """

    @staticmethod
    def _msg(*header_names):
        return {"internetMessageHeaders": [{"name": n, "value": "x"} for n in header_names]}

    def test_a_list_unsubscribe_header_is_bulk(self):
        self.assertTrue(osync.has_unsubscribe(self._msg("From", "List-Unsubscribe")))

    def test_the_post_variant_counts_too(self):
        self.assertTrue(osync.has_unsubscribe(self._msg("List-Unsubscribe-Post")))

    def test_the_header_name_is_matched_case_insensitively(self):
        # Graph returns whatever casing the sender used; RFC 2369 names are not case-fixed.
        self.assertTrue(osync.has_unsubscribe(self._msg("list-unsubscribe")))
        self.assertTrue(osync.has_unsubscribe(self._msg("LIST-UNSUBSCRIBE")))

    def test_ordinary_correspondence_is_not_bulk(self):
        self.assertFalse(osync.has_unsubscribe(self._msg("From", "To", "Subject")))

    def test_a_message_with_no_headers_at_all_is_not_bulk(self):
        # The $select could stop returning the block; that must fail toward judging, never
        # toward dropping.
        self.assertFalse(osync.has_unsubscribe({}))
        self.assertFalse(osync.has_unsubscribe({"internetMessageHeaders": None}))

    def test_a_noreply_sender_is_not_bulk_on_its_own(self):
        # The exclusion connectors.md forbids by default: a domain-expiry notice, a tax
        # filing alert, an invoice and a booking confirmation all come from noreply@, and
        # dropping them on the sender name loses exactly the mail the vault exists to catch.
        for addr in ("noreply@registrar.example", "donotreply@tax.gov",
                     "notifications@invoicing.com", "newsletter@brand.fr"):
            self.assertFalse(osync.has_unsubscribe({"from": {"emailAddress":
                                                             {"address": addr}}}), addr)

    def test_the_module_keeps_no_sender_name_blocklist(self):
        # Pinned, not merely absent: re-adding one is how the forbidden pattern comes back.
        self.assertFalse(hasattr(osync, "is_bulk"))
        self.assertFalse(hasattr(osync, "BULK_TOKENS"))


class MailboxRoute(unittest.TestCase):
    """Which account's token reads one feed address, and where Graph is addressed.

    A shared mailbox has no sign-in of its own, so it is read THROUGH a user holding Full
    Access on it. Every branch matters: the wrong one reads the wrong mailbox.
    """

    CFG = {"accounts": {"me@corp.com": {"refresh_token": "t"},
                        "info@corp.com": {"via": "me@corp.com"}}}

    def test_an_ordinary_mailbox_resolves_to_itself_and_me(self):
        self.assertEqual(osync.mailbox_route(self.CFG, "me@corp.com"), ("me@corp.com", "/me"))

    def test_a_shared_mailbox_borrows_its_via_users_token(self):
        self.assertEqual(osync.mailbox_route(self.CFG, "info@corp.com"),
                         ("me@corp.com", "/users/info@corp.com"))

    def test_an_account_absent_from_the_config_still_resolves_to_itself(self):
        # `login` needs a route before the entry exists.
        self.assertEqual(osync.mailbox_route(self.CFG, "new@corp.com"), ("new@corp.com", "/me"))

    def test_a_via_user_absent_from_this_machine_exits(self):
        cfg = {"accounts": {"info@corp.com": {"via": "elsewhere@corp.com"}}}
        with self.assertRaises(SystemExit) as e:
            osync.mailbox_route(cfg, "info@corp.com")
        self.assertIn("elsewhere@corp.com", str(e.exception))


class AccountScope(unittest.TestCase):
    """Which scope ONE account's token is asked for.

    This is the regression that took every work mailbox on a live machine offline at once,
    so the tests pin the asymmetry rather than the string: a refresh may ask for less than
    was consented but never more, so asking every account for Mail.Read.Shared turns a
    scope the caller chose into an authentication failure it cannot log its way out of.
    Personal accounts hid it - `consumers` drops the extra silently - which is exactly why
    a test has to hold the line instead of a live run.
    """

    CFG = {"accounts": {"me@corp.com": {"refresh_token": "t"},
                        "other@corp.com": {"refresh_token": "t"},
                        "info@corp.com": {"via": "me@corp.com"}}}

    def test_an_ordinary_account_is_asked_for_mail_read_only(self):
        scope = osync.account_scope(self.CFG, "other@corp.com")
        self.assertIn(osync.READ_SCOPE, scope)
        self.assertNotIn(osync.SHARED_SCOPE, scope)
        self.assertIn(osync.OFFLINE_SCOPE, scope)

    def test_the_via_user_of_a_shared_mailbox_gets_the_wider_scope(self):
        self.assertIn(osync.SHARED_SCOPE, osync.account_scope(self.CFG, "me@corp.com"))

    def test_an_explicit_shared_flag_widens_before_any_via_line_exists(self):
        # login --shared, so the consent is in place before the shared entry is added.
        cfg = {"accounts": {"me@corp.com": {"refresh_token": "t", "shared": True}}}
        self.assertIn(osync.SHARED_SCOPE, osync.account_scope(cfg, "me@corp.com"))

    def test_the_shared_mailbox_itself_is_never_asked_for_anything_wider(self):
        # It holds no token; the scope that matters is its `via` user's.
        self.assertNotIn(osync.SHARED_SCOPE, osync.account_scope(self.CFG, "info@corp.com"))

    def test_an_account_absent_from_the_config_gets_the_narrow_scope(self):
        # `login` resolves a scope before the entry exists, and a first login must not ask
        # for a permission the tenant may refuse to consent to.
        self.assertNotIn(osync.SHARED_SCOPE, osync.account_scope(self.CFG, "new@corp.com"))

    def test_no_module_wide_scope_constant_survives(self):
        # A single SCOPE is what made one mailbox's needs everyone's problem. If it comes
        # back, every call site silently reverts to the widest scope any account needs.
        self.assertFalse(hasattr(osync, "SCOPE"),
                         "scope must be resolved per account, not as one constant")


class AuthFailure(unittest.TestCase):
    """What a failed token exchange tells you.

    It used to print the OAuth error class and "re-run login" - advice that is wrong for a
    consent gap (needs a different scope) and impossible for a tenant policy block (needs
    an admin), so the only instruction offered sent you round a loop with no exit. The
    AADSTS code is the diagnosis, so these pin that it survives into the message.
    """

    def _msg(self, codes, desc="AADSTS%s: something" , scope=None):
        body = {"error": "invalid_grant", "error_codes": list(codes),
                "error_description": (desc % codes[0]) if "%s" in desc else desc}
        return osync.auth_failure("v@corp.be", scope or osync.READ_SCOPE,
                                  "tenant-guid", "app-guid", body)

    def test_the_aadsts_code_is_quoted_rather_than_swallowed(self):
        self.assertIn("AADSTS65001", self._msg([65001]))

    def test_a_consent_gap_on_the_wide_scope_points_at_login_shared(self):
        m = self._msg([65001], scope=f"{osync.READ_SCOPE} {osync.SHARED_SCOPE} offline_access")
        self.assertIn("--shared", m)
        self.assertIn("Mail.Read.Shared", m)

    def test_a_consent_gap_on_the_narrow_scope_does_not_suggest_shared(self):
        self.assertNotIn("--shared", self._msg([65001]))

    def test_a_tenant_policy_block_quotes_the_code_and_names_the_admin_route(self):
        m = self._msg([530035], desc="AADSTS530035: Access has been blocked by security defaults.")
        self.assertIn("530035", m)
        self.assertIn("admin", m.lower())

    def test_a_tenant_policy_block_does_not_claim_a_re_login_is_futile(self):
        # This assertion used to be the opposite, and the opposite was wrong. Security
        # defaults block device code flow, not the account: a browser sign-in gets through
        # untouched, so telling the operator no login can help sends them to an admin for
        # a change they do not need. The remedy that needs nobody comes first.
        m = self._msg([530035], desc="AADSTS530035: Access has been blocked by security defaults.")
        self.assertNotIn("re-login cannot", m.lower())
        self.assertLess(m.lower().index("needs no admin"), m.lower().index("tenant admin"))

    def test_an_expired_token_still_says_log_in_again(self):
        m = self._msg([700082])
        self.assertIn("login v@corp.be", m)

    def test_an_mfa_challenge_says_a_refresh_cannot_answer_it(self):
        m = self._msg([50076])
        self.assertIn("interactive challenge", m)
        self.assertIn("login v@corp.be", m)

    def test_an_unrecognised_code_still_quotes_the_description(self):
        m = self._msg([999999], desc="AADSTS999999: brand new failure mode")
        self.assertIn("brand new failure mode", m)
        self.assertIn("login v@corp.be", m)

    def test_a_response_with_no_description_still_produces_a_message(self):
        m = osync.auth_failure("v@corp.be", osync.READ_SCOPE, "t", "a", {"error": "invalid_request"})
        self.assertIn("v@corp.be", m)
        self.assertIn("invalid_request", m)



class PkceLogin(unittest.TestCase):
    """The browser sign-in flow. Device code flow is blocked by security defaults, which every
    new Entra tenant now ships with, so this is the flow that has to work. The parts tested are
    the ones that fail silently or unsafely."""

    def test_pkce_challenge_is_s256_of_the_verifier_unpadded(self):
        # A wrong challenge is not a crash: the authorize step succeeds and the token
        # exchange fails much later with an opaque invalid_grant.
        import base64, hashlib
        v = osync._b64url(bytes(32))
        self.assertNotIn("=", v)
        expect = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(osync._b64url(hashlib.sha256(v.encode()).digest()), expect)

    def test_b64url_is_url_safe_and_unpadded(self):
        raw = bytes(range(256))
        out = osync._b64url(raw)
        self.assertNotIn("=", out)
        self.assertNotIn("+", out)
        self.assertNotIn("/", out)

    def test_the_callback_handler_is_a_fresh_class_each_time(self):
        # Shared class state would leak one login's authorization code into the next.
        a, b = osync._callback_handler(), osync._callback_handler()
        self.assertIsNot(a, b)
        a.result = {"code": ["leaked"]}
        self.assertIsNone(b.result)

    def test_device_code_flow_is_still_available(self):
        # It is the only flow that needs nothing registered on the app, so it stays as the
        # escape hatch for an app with no loopback redirect URI.
        self.assertTrue(callable(getattr(osync, "device_login", None)))

    def test_login_defaults_to_pkce_and_the_flag_selects_device_code(self):
        seen = {}
        cfg = {"client_id": "X", "accounts": {}}
        for flag, expect in ((False, "pkce_login"), (True, "device_login")):
            args = argparse.Namespace(email="v@corp.be", client_id=None, authority=None,
                                      shared=False, device_code=flag)
            with mock.patch.object(osync, "pkce_login", lambda *a: seen.setdefault("f", "pkce_login") or "t"),                     mock.patch.object(osync, "device_login", lambda *a: seen.setdefault("f", "device_login") or "t"),                     mock.patch.object(osync, "save_account"),                     contextlib.redirect_stdout(io.StringIO()):
                seen.clear()
                osync.cmd_login(dict(cfg), args)
            self.assertEqual(seen.get("f"), expect)


class AuthFailureRemedies(unittest.TestCase):
    """The 530035 remedy specifically. The first version of this message recommended two
    things that do not exist - excluding one app from security defaults, which are on or
    off with no exceptions, and a Conditional Access policy, which needs Entra ID P1 the
    affected tenant did not have."""

    def _m(self, codes, what="Token refresh"):
        return osync.auth_failure("v@corp.be", osync.READ_SCOPE, "tenant-guid", "app-guid",
                                  {"error": "invalid_request", "error_codes": list(codes),
                                   "error_description": "AADSTS%d: blocked" % codes[0]},
                                  what=what)

    def test_530035_no_longer_claims_an_app_can_be_excluded(self):
        m = self._m([530035])
        self.assertNotIn("exclude this app", m)
        self.assertIn("no per-app exception", m)

    def test_530035_offers_the_browser_login_first_and_needs_no_admin(self):
        m = self._m([530035])
        self.assertIn("needs no admin", m)
        self.assertIn("login v@corp.be", m)
        self.assertIn("PKCE", m)

    def test_530035_still_names_the_admin_route_and_its_licence_cost(self):
        m = self._m([530035])
        self.assertIn("P1", m)
        self.assertIn("Authentication flows", m)

    def test_conditional_access_is_a_separate_code_with_a_separate_remedy(self):
        # 53003 is a real CA policy and 530035 is security defaults; they were one branch
        # and the advice for one is wrong for the other.
        m = self._m([53003])
        self.assertIn("Conditional Access policy", m)
        self.assertIn("Sign-in logs", m)
        self.assertNotIn("PKCE", m)

    def test_the_message_names_what_failed_so_a_login_does_not_say_refresh(self):
        self.assertTrue(self._m([530035], what="Sign-in").startswith("Sign-in for v@corp.be"))


def _response(status=200, body=None):
    """A stand-in for a requests.Response from the token endpoint."""
    return mock.Mock(status_code=status, json=lambda: body if body is not None else {},
                     raise_for_status=lambda: None)


class AccessToken(unittest.TestCase):
    """Trading the stored refresh token for an access token.

    MSA rotates the refresh token on every refresh and the superseded one is dead, so the
    rotation reaching disk is what keeps the next run logged in. The token endpoint is a mock;
    the file it rotates into is real.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.secrets = Path(tmp.name) / "secrets" / "outlook.json"
        self.session = mock.Mock()
        for patcher in (mock.patch.object(osync, "CONFIG_FILE", self.secrets),
                        mock.patch.object(osync, "SESSION", self.session),
                        mock.patch.dict(osync._TOKENS, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def seed(self, cfg):
        """Put `cfg` on disk, compactly, so any rewrite of the file shows up as changed bytes."""
        self.secrets.parent.mkdir(parents=True, exist_ok=True)
        self.secrets.write_text(json.dumps(cfg), encoding="utf-8")
        return json.loads(self.secrets.read_text(encoding="utf-8"))

    def test_the_refresh_goes_to_the_accounts_own_tenant_and_app(self):
        cfg = self.seed({"client_id": "GLOBAL", "accounts": {"v@corp.be": {
            "refresh_token": "old", "client_id": "WORK", "authority": "tenant-guid"}}})
        self.session.post.return_value = _response(body={"access_token": "AT"})
        self.assertEqual(osync.access_token(cfg, "v@corp.be"), "AT")
        call = self.session.post.call_args
        self.assertEqual(call.args[0], "https://login.microsoftonline.com/tenant-guid/oauth2/v2.0/token")
        self.assertEqual(call.kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(call.kwargs["data"]["client_id"], "WORK")
        self.assertEqual(call.kwargs["data"]["refresh_token"], "old")

    def test_the_refresh_asks_for_the_accounts_own_scope(self):
        # Only the via user of a shared mailbox may ask for Mail.Read.Shared; asking any other
        # account for it fails its refresh outright.
        cfg = self.seed({"client_id": "X", "accounts": {
            "me@corp.com": {"refresh_token": "t"}, "other@corp.com": {"refresh_token": "t"},
            "info@corp.com": {"via": "me@corp.com"}}})
        self.session.post.return_value = _response(body={"access_token": "AT"})
        osync.access_token(cfg, "me@corp.com")
        osync.access_token(cfg, "other@corp.com")
        me, other = (c.kwargs["data"]["scope"] for c in self.session.post.call_args_list)
        self.assertIn(osync.SHARED_SCOPE, me)
        self.assertNotIn(osync.SHARED_SCOPE, other)
        self.assertIn(osync.OFFLINE_SCOPE, other)

    def test_a_rotated_refresh_token_is_written_back_to_disk(self):
        cfg = self.seed({"client_id": "X", "accounts": {
            "a@h.com": {"refresh_token": "a-old"}, "b@h.com": {"refresh_token": "b-old"}}})
        self.session.post.return_value = _response(body={"access_token": "AT",
                                                         "refresh_token": "a-NEW"})
        osync.access_token(cfg, "a@h.com")
        on_disk = json.loads(self.secrets.read_text(encoding="utf-8"))["accounts"]
        self.assertEqual(on_disk["a@h.com"]["refresh_token"], "a-NEW")
        self.assertEqual(on_disk["b@h.com"]["refresh_token"], "b-old")
        self.assertEqual(cfg["accounts"]["a@h.com"]["refresh_token"], "a-NEW")

    def test_a_refresh_that_rotates_nothing_leaves_the_secrets_file_alone(self):
        cfg = self.seed({"client_id": "X", "accounts": {"a@h.com": {"refresh_token": "t"}}})
        before = self.secrets.read_bytes()
        self.session.post.return_value = _response(body={"access_token": "AT"})
        osync.access_token(cfg, "a@h.com")
        self.assertEqual(self.secrets.read_bytes(), before)

    def test_a_second_ask_in_one_run_is_served_without_another_refresh(self):
        # A vault fed by an owner and two shared mailboxes asks for one token three times, and
        # each extra refresh would rotate away the token the previous one just stored.
        cfg = self.seed({"client_id": "X", "accounts": {"a@h.com": {"refresh_token": "t"}}})
        self.session.post.return_value = _response(body={"access_token": "AT",
                                                         "refresh_token": "t2"})
        self.assertEqual([osync.access_token(cfg, "a@h.com") for _ in range(3)], ["AT"] * 3)
        self.assertEqual(self.session.post.call_count, 1)

    def test_an_account_with_no_token_exits_with_the_login_command(self):
        cfg = {"client_id": "X", "accounts": {"a@h.com": {}}}
        with self.assertRaises(SystemExit) as e:
            osync.access_token(cfg, "a@h.com")
        self.assertIn("outlook.py login a@h.com", str(e.exception))
        self.session.post.assert_not_called()

    def test_an_account_not_on_this_machine_exits_with_the_login_command(self):
        # `raw --account <address>` for a mailbox never logged in here used to crash with a
        # bare KeyError instead of saying how to fix it.
        cfg = {"client_id": "X", "accounts": {"a@h.com": {"refresh_token": "t"}}}
        with self.assertRaises(SystemExit) as e:
            osync.access_token(cfg, "x@y.com")
        self.assertIn("outlook.py login x@y.com", str(e.exception))
        self.session.post.assert_not_called()

    def test_a_refused_refresh_exits_with_the_diagnosis_and_caches_nothing(self):
        cfg = self.seed({"client_id": "X", "accounts": {"a@h.com": {"refresh_token": "t"}}})
        before = self.secrets.read_bytes()
        self.session.post.return_value = _response(400, {
            "error": "invalid_grant", "error_codes": [700082],
            "error_description": "AADSTS700082: The refresh token has expired."})
        with self.assertRaises(SystemExit) as e:
            osync.access_token(cfg, "a@h.com")
        self.assertTrue(str(e.exception).startswith("Token refresh for a@h.com failed"))
        self.assertIn("AADSTS700082", str(e.exception))
        self.assertEqual(osync._TOKENS, {})
        self.assertEqual(self.secrets.read_bytes(), before)


class _FakeConnection:
    """Just enough of a socket for BaseHTTPRequestHandler: it reads the raw request from
    makefile() and answers through sendall(), so the stdlib parses the request exactly as it
    would off the loopback port."""

    def __init__(self, raw):
        self._rfile = io.BytesIO(raw)
        self.sent = bytearray()

    def makefile(self, *_args, **_kwargs):
        return self._rfile

    def sendall(self, data):
        self.sent += data


class CallbackHandler(unittest.TestCase):
    """The loopback page the browser is redirected to at the end of a sign-in."""

    def hit(self, target):
        Handler = osync._callback_handler()
        conn = _FakeConnection(f"GET {target} HTTP/1.1\r\nHost: localhost\r\n"
                               f"Connection: close\r\n\r\n".encode("ascii"))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            Handler(conn, ("127.0.0.1", 50000), None)
        status = bytes(conn.sent).split(b"\r\n", 1)[0].split()[1]
        return Handler.result, int(status), bytes(conn.sent), err.getvalue()

    def test_the_redirect_carrying_a_code_is_captured_and_answered(self):
        result, status, raw, err = self.hit("/?code=M.C5_abc&state=xyz")
        self.assertEqual(result, {"code": ["M.C5_abc"], "state": ["xyz"]})
        self.assertEqual(status, 200)
        self.assertIn(b"Signed in.", raw)
        self.assertEqual(err, "")        # the default handler logs every hit to stderr

    def test_an_error_redirect_is_captured_so_the_login_can_report_it(self):
        result, status, _, _ = self.hit("/?error=access_denied&error_description=declined")
        self.assertEqual(result["error"], ["access_denied"])
        self.assertEqual(status, 200)

    def test_a_stray_request_is_refused_without_ending_the_wait(self):
        # Browsers ask for /favicon.ico. Taking that as the callback would end the wait with
        # no code in hand.
        result, status, _, _ = self.hit("/favicon.ico")
        self.assertIsNone(result)
        self.assertEqual(status, 404)


class PkceLoginFlow(unittest.TestCase):
    """pkce_login against a fake loopback server and a mock token endpoint.

    What is ours to get wrong: the verifier redeemed must hash to the challenge sent, the
    redirect_uri must be the same in both requests, and a forged or failed redirect must stop
    before any code is redeemed. None of those fail at the step that is wrong - they surface
    later as an opaque invalid_grant, or not at all.
    """

    CFG = {"client_id": "APP", "accounts": {}}

    def run_login(self, redirect, cfg=None, token=None, bind_error=None, browser_fails=False):
        """pkce_login with the browser, the loopback port and the token endpoint faked.

        `redirect` receives the authorize request's parameters and returns the query the
        browser comes back with (in parse_qs shape), or None for no redirect at all.
        Returns (refresh token or the SystemExit, authorize params, token POST mock, stdout).
        """
        opened, bound = [], []

        def open_browser(url):
            opened.append(url)
            if browser_fails:
                raise osync.webbrowser.Error("no display")

        class FakeServer:
            server_port = 53117

            def __init__(self, address, handler):
                if bind_error:
                    raise bind_error
                bound.append(address)
                self.handler = handler

            def handle_request(self):
                params = {k: v[0] for k, v in parse_qs(urlparse(opened[-1]).query).items()}
                self.handler.result = redirect(params)

            def server_close(self):
                pass

        session = mock.Mock()
        session.post.return_value = token or _response(body={"refresh_token": "RT"})
        out = io.StringIO()
        with mock.patch.object(osync, "HTTPServer", FakeServer), \
                mock.patch.object(osync.webbrowser, "open", side_effect=open_browser), \
                mock.patch.object(osync, "SESSION", session), \
                contextlib.redirect_stdout(out):
            try:
                result = osync.pkce_login(cfg or self.CFG, "v@corp.be")
            except SystemExit as e:
                result = e
        self.bound = bound
        params = ({k: v[0] for k, v in parse_qs(urlparse(opened[0]).query).items()}
                  if opened else None)
        self.authorize_url = opened[0] if opened else None
        return result, params, session.post, out.getvalue()

    @staticmethod
    def signed_in(params):
        return {"code": ["CODE"], "state": [params["state"]]}

    def test_the_verifier_redeemed_is_the_one_the_challenge_was_made_from(self):
        result, params, post, _ = self.run_login(self.signed_in)
        self.assertEqual(result, "RT")
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["grant_type"], "authorization_code")
        self.assertEqual(sent["code"], "CODE")
        self.assertEqual(params["code_challenge_method"], "S256")
        expect = base64.urlsafe_b64encode(
            hashlib.sha256(sent["code_verifier"].encode("ascii")).digest()).rstrip(b"=").decode()
        self.assertEqual(params["code_challenge"], expect)

    def test_the_token_request_repeats_the_authorize_redirect_uri(self):
        _, params, post, _ = self.run_login(self.signed_in)
        self.assertEqual(params["redirect_uri"], "http://localhost:53117")
        self.assertEqual(post.call_args.kwargs["data"]["redirect_uri"], params["redirect_uri"])
        self.assertEqual(self.bound, [("127.0.0.1", 0)])   # loopback only, on a port the OS picks

    def test_the_authorize_request_names_the_account_its_app_and_its_scope(self):
        cfg = {"client_id": "GLOBAL", "accounts": {"v@corp.be": {
            "client_id": "WORK", "authority": "tenant-guid", "shared": True}}}
        _, params, post, _ = self.run_login(self.signed_in, cfg=cfg)
        base = osync.token_url("tenant-guid")
        self.assertTrue(self.authorize_url.startswith(f"{base}/authorize?"))
        self.assertEqual(post.call_args.args[0], f"{base}/token")
        self.assertEqual(params["client_id"], "WORK")
        self.assertEqual(params["login_hint"], "v@corp.be")
        self.assertEqual(params["response_type"], "code")
        self.assertEqual(params["scope"], osync.account_scope(cfg, "v@corp.be"))
        self.assertEqual(post.call_args.kwargs["data"]["scope"], params["scope"])

    def test_a_redirect_with_the_wrong_state_is_refused_before_any_code_is_redeemed(self):
        result, _, post, _ = self.run_login(lambda p: {"code": ["CODE"], "state": ["forged"]})
        self.assertIsInstance(result, SystemExit)
        self.assertIn("wrong state", str(result))
        post.assert_not_called()

    def test_an_error_redirect_exits_with_microsofts_reason(self):
        result, _, post, _ = self.run_login(lambda p: {
            "error": ["access_denied"], "error_description": ["The user declined consent."]})
        self.assertIsInstance(result, SystemExit)
        self.assertIn("access_denied", str(result))
        self.assertIn("The user declined consent.", str(result))
        post.assert_not_called()

    def test_a_refused_code_exchange_exits_naming_the_sign_in(self):
        result, _, _, _ = self.run_login(self.signed_in, token=_response(400, {
            "error": "invalid_grant", "error_codes": [65001],
            "error_description": "AADSTS65001: consent required"}))
        self.assertIsInstance(result, SystemExit)
        self.assertTrue(str(result).startswith("Sign-in for v@corp.be failed"))
        self.assertIn("AADSTS65001", str(result))

    def test_no_redirect_times_out_naming_the_missing_reply_address(self):
        # The browser shows AADSTS500113 and never redirects, so this process only ever sees
        # silence. The timeout message is the one place the operator can learn why.
        with mock.patch.object(osync.time, "monotonic", side_effect=itertools.count(0, 400)):
            result, _, post, _ = self.run_login(lambda p: None)
        self.assertIsInstance(result, SystemExit)
        for part in ("AADSTS500113", "http://localhost", "APP", "--device-code"):
            self.assertIn(part, str(result))
        post.assert_not_called()

    def test_a_port_that_cannot_be_opened_points_at_device_code(self):
        result, params, _, _ = self.run_login(self.signed_in, bind_error=OSError("in use"))
        self.assertIsInstance(result, SystemExit)
        self.assertIn("login v@corp.be --device-code", str(result))
        self.assertIsNone(params)        # no browser sent to a port nobody is listening on

    def test_a_machine_with_no_browser_still_gets_the_url_to_paste(self):
        result, _, _, out = self.run_login(self.signed_in, browser_fails=True)
        self.assertEqual(result, "RT")
        self.assertIn(self.authorize_url, out)


class DeviceLoginFlow(unittest.TestCase):
    """device_login's polling loop against a mock token endpoint. time.sleep is patched, so
    the intervals are asserted rather than waited out."""

    DC = {"device_code": "DC", "user_code": "ABCD-1234", "interval": 5, "expires_in": 900,
          "verification_uri": "https://microsoft.com/devicelogin"}

    def run_login(self, polls, dc=None):
        """`polls` is the token endpoint's answers in order, as (status, body)."""
        session = mock.Mock()
        session.post.side_effect = [_response(body=dc or self.DC)] + [
            _response(status, body) for status, body in polls]
        out = io.StringIO()
        cfg = {"client_id": "APP", "accounts": {}}
        with mock.patch.object(osync, "SESSION", session), \
                mock.patch.object(osync.time, "sleep") as slept, \
                contextlib.redirect_stdout(out):
            try:
                result = osync.device_login(cfg, "v@corp.be")
            except SystemExit as e:
                result = e
        return result, session.post, [c.args[0] for c in slept.call_args_list], out.getvalue()

    PENDING = (400, {"error": "authorization_pending"})

    def test_it_waits_out_pending_and_returns_the_refresh_token(self):
        result, post, slept, out = self.run_login([self.PENDING, (200, {"refresh_token": "RT"})])
        self.assertEqual(result, "RT")
        self.assertEqual(slept, [5, 5])
        first, *polls = post.call_args_list
        self.assertTrue(first.args[0].endswith("/consumers/oauth2/v2.0/devicecode"))
        self.assertEqual(first.kwargs["data"]["client_id"], "APP")
        for poll in polls:
            self.assertEqual(poll.kwargs["data"]["device_code"], "DC")
            self.assertEqual(poll.kwargs["data"]["grant_type"],
                             "urn:ietf:params:oauth:grant-type:device_code")
        self.assertIn("https://microsoft.com/devicelogin", out)
        self.assertIn("ABCD-1234", out)

    def test_slow_down_lengthens_every_later_wait(self):
        _, _, slept, _ = self.run_login([(400, {"error": "slow_down"}), self.PENDING,
                                         (200, {"refresh_token": "RT"})])
        self.assertEqual(slept, [5, 10, 10])

    def test_a_declined_login_exits_with_the_reason(self):
        result, _, _, _ = self.run_login([(400, {"error": "authorization_declined",
                                                 "error_description": "The user declined."})])
        self.assertIsInstance(result, SystemExit)
        self.assertIn("authorization_declined: The user declined.", str(result))

    def test_an_expired_code_exits_as_a_timeout_without_polling(self):
        result, post, _, _ = self.run_login([], dc=dict(self.DC, expires_in=0))
        self.assertIsInstance(result, SystemExit)
        self.assertIn("timed out", str(result))
        self.assertEqual(post.call_count, 1)


class CmdFetch(unittest.TestCase):
    """`fetch` reads the same mailbox `sync` reads and writes nothing, handing candidates to
    a caller that judges them. The tests that matter are the ones about NOT writing."""

    MSGS = [
        {"id": "1", "internetMessageId": "<a@x>", "receivedDateTime": "2026-09-01T10:00:00Z",
         "conversationId": "conv-1",
         "subject": "Onze factuur", "bodyPreview": "  beste   collega  ",
         "from": {"emailAddress": {"name": "Zoe", "address": "zoe@acme.be"}},
         "toRecipients": [{"emailAddress": {"address": "k@x.com"}}],
         "ccRecipients": [], "webLink": "https://example/1"},
        {"id": "2", "internetMessageId": "<b@x>", "receivedDateTime": "2026-09-02T10:00:00Z",
         "subject": "10% OFF", "bodyPreview": "sale",
         "from": {"emailAddress": {"name": "Shop", "address": "noreply@shop.com"}},
         "internetMessageHeaders": [{"name": "List-Unsubscribe",
                                     "value": "<https://shop.example/u>"}],
         "toRecipients": [], "ccRecipients": [], "webLink": "https://example/2"},
    ]

    # A registrar notice: machine-sent, from noreply@, and exactly the mail the vault exists
    # to catch. It carries no List-Unsubscribe, so nothing here may drop it.
    TRANSACTIONAL = {
        "id": "3", "internetMessageId": "<c@x>", "receivedDateTime": "2026-09-03T10:00:00Z",
        "subject": "ACTION REQUIRED: domain expires in 7 days", "bodyPreview": "renew",
        "from": {"emailAddress": {"name": "Registrar", "address": "noreply@registrar.example"}},
        "toRecipients": [], "ccRecipients": [], "webLink": "https://example/3"}

    def run_fetch(self, msgs=None, include_bulk=False, cfg=None, feeds=("a@x.com",),
                  token=None):
        """cmd_fetch with its whole dependency surface stubbed; returns (records, stderr).

        Every dependency is patched here rather than per test, because the patch stack is
        what goes stale when the command gains one - and a drifted copy of it still passes
        while quietly testing a mock instead of the real function.
        """
        cfg = cfg or {"accounts": {"a@x.com": {"refresh_token": "t"}}}
        args = argparse.Namespace(account=None, days=7, include_bulk=include_bulk)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(osync, "require_vault"), \
                mock.patch.object(osync, "load_vault_config", return_value={}), \
                mock.patch.object(osync, "vault_accounts", return_value=list(feeds)), \
                mock.patch.object(osync, "access_token",
                                  side_effect=token or (lambda c, e: "tok")), \
                mock.patch.object(osync, "fetch_messages",
                                  return_value=list(self.MSGS if msgs is None else msgs)), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            osync.cmd_fetch(cfg, args)
        return json.loads(out.getvalue()), err.getvalue()

    def test_the_module_has_no_write_path_left_at_all(self):
        # The whole reason the subcommand exists, guarded structurally rather than by
        # asserting a writer was not called: `sync` and everything it wrote with were
        # removed, and this fails the moment one comes back.
        for name in ("cmd_sync", "write_triage", "save_ledger", "load_ledger",
                     "safe_title", "build_allowlist", "account_filter", "is_relevant"):
            self.assertFalse(hasattr(osync, name), f"{name} is back; mail can be filed again")

    def test_stdout_is_parseable_json_and_the_human_lines_go_to_stderr(self):
        records, err = self.run_fetch()
        self.assertIsInstance(records, list)
        self.assertIn("scanned", err)
        self.assertIn("thread", err)
        self.assertIn("nothing was written", err)

    def test_bulk_is_skipped_by_default_and_counted_out_loud(self):
        records, err = self.run_fetch()
        self.assertEqual([r["id"] for r in records], ["1"])
        self.assertIn("1 bulk skipped", err)

    def test_include_bulk_keeps_it(self):
        records, _ = self.run_fetch(include_bulk=True)
        self.assertEqual([r["id"] for r in records], ["1", "2"])

    def test_one_unusable_mailbox_does_not_cost_the_run_the_others(self):
        # mailbox_route and access_token both sys.exit, and nothing is emitted until the end,
        # so an unreachable second mailbox used to discard the first one's messages and print
        # no JSON at all - the failure resolve_feeds is written against, one level down.
        def token(_cfg, email):
            if email == "b@x.com":
                sys.exit(f"{email} has no token yet.")
            return "tok"

        records, err = self.run_fetch(
            cfg={"accounts": {e: {"refresh_token": "t"} for e in ("a@x.com", "b@x.com")}},
            feeds=("a@x.com", "b@x.com"), token=token)
        self.assertEqual([r["id"] for r in records], ["1"])
        self.assertIn("FETCH FAILED", err)
        self.assertIn("1 mailbox(es) failed", err)

    def test_a_noreply_notice_with_no_unsubscribe_header_survives(self):
        # The regression this suite exists to hold: a domain-expiry notice, a tax filing
        # alert, an invoice or a receipt is machine-sent from noreply@ and is the mail the
        # vault most wants. Only List-Unsubscribe may drop anything.
        records, err = self.run_fetch(msgs=[self.TRANSACTIONAL])
        self.assertEqual([r["id"] for r in records], ["3"])
        self.assertIn("0 bulk skipped", err)

    def test_a_record_carries_the_rfc822_message_id(self):
        # The cross-mailbox dedup key: one message reaching two registered mailboxes has two
        # Graph ids and one Message-ID, and only the latter can collapse them.
        records, _ = self.run_fetch()
        self.assertEqual(records[0]["message_id"], "<a@x>")

    def test_a_record_says_whether_the_sender_is_the_mailbox_owner(self):
        # Every message in a mailbox is to or from its owner, so a caller matching on contact
        # identity matches all of it unless it can tell. Measured before this existed: 126 of
        # 220 contact hits on a real mailbox were the owner writing to herself.
        records, _ = self.run_fetch()
        self.assertIs(records[0]["from_owner"], False)

    def test_the_owner_self_list_is_honoured_not_just_the_account_address(self):
        msgs = [{"id": "7", "internetMessageId": "<d@x>", "conversationId": "c7",
                 "subject": "note to self", "bodyPreview": "",
                 "from": {"emailAddress": {"name": "Me", "address": "me@icloud.com"}},
                 "toRecipients": [], "ccRecipients": [],
                 "receivedDateTime": "2026-09-01T10:00:00Z", "webLink": ""}]
        records, _ = self.run_fetch(
            msgs=msgs,
            cfg={"accounts": {"a@x.com": {"refresh_token": "t", "self": ["me@icloud.com"]}}})
        self.assertIs(records[0]["from_owner"], True)

    def test_a_record_carries_the_conversation_id(self):
        # Parity with the connector path, where one conversation is one candidate rather
        # than N. Without it a five-message thread is judged five times.
        records, _ = self.run_fetch()
        self.assertEqual(records[0]["thread_id"], "conv-1")

    # --- grouping: one conversation is one candidate ---------------------------------
    # Carrying conversationId is not the same as grouping on it, and for a long time this
    # class asserted the first while the code did neither (README.md has the measurement).
    # Every extra record is a note in someone's triage/ and a judgment someone has to make.

    THREAD = [
        # Deliberately out of order. Graph returns newest-first, so grouping that leans on
        # input order passes here by luck and fails the day a page boundary reorders it.
        {"id": "t2", "internetMessageId": "<t2@x>", "receivedDateTime": "2026-09-04T09:00:00Z",
         "conversationId": "conv-9", "subject": "RE: opmeting", "bodyPreview": "second",
         "from": {"emailAddress": {"name": "Tom", "address": "tom@partner.example"}},
         "toRecipients": [{"emailAddress": {"address": "a@x.com"}}],
         "ccRecipients": [], "webLink": "https://example/t2"},
        {"id": "t3", "internetMessageId": "<t3@x>", "receivedDateTime": "2026-09-05T09:00:00Z",
         "conversationId": "conv-9", "subject": "RE: opmeting", "bodyPreview": "third, mine",
         "from": {"emailAddress": {"name": "Me", "address": "a@x.com"}},
         "toRecipients": [{"emailAddress": {"address": "tom@partner.example"}}],
         "ccRecipients": [], "webLink": "https://example/t3"},
        {"id": "t1", "internetMessageId": "<t1@x>", "receivedDateTime": "2026-09-03T09:00:00Z",
         "conversationId": "conv-9", "subject": "opmeting", "bodyPreview": "first",
         "from": {"emailAddress": {"name": "Tom", "address": "tom@partner.example"}},
         "toRecipients": [{"emailAddress": {"address": "a@x.com"}}],
         "ccRecipients": [], "webLink": "https://example/t1"},
    ]

    def test_three_messages_on_one_conversation_are_one_record(self):
        records, _ = self.run_fetch(msgs=self.THREAD)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["thread_id"], "conv-9")

    def test_the_record_describes_the_newest_message_in_the_conversation(self):
        # The caller reads the top level to judge; showing it the oldest message of a live
        # thread is how a settled question gets re-asked and a new one gets missed.
        r = self.run_fetch(msgs=self.THREAD)[0][0]
        self.assertEqual(r["id"], "t3")
        self.assertEqual(r["received"], "2026-09-05T09:00:00Z")
        self.assertEqual(r["preview"], "third, mine")

    def test_the_record_keeps_every_message_newest_first(self):
        # Grouping must not lose what it collapses: the caller states in the note it writes
        # how much of the thread stands behind the fragment it quotes.
        r = self.run_fetch(msgs=self.THREAD)[0][0]
        self.assertEqual(r["message_count"], 3)
        self.assertEqual([m["id"] for m in r["messages"]], ["t3", "t2", "t1"])

    def test_participants_span_the_thread_and_exclude_the_owner(self):
        # The routing rule matches on a counterparty. Collapsing to the newest message alone
        # would hide Tom the moment the owner replies last, and the thread would route
        # nowhere for the most ordinary reason there is.
        r = self.run_fetch(msgs=self.THREAD)[0][0]
        self.assertIs(r["from_owner"], True)
        self.assertEqual(r["participants"], ["tom@partner.example"])

    def test_a_single_message_thread_has_the_same_shape(self):
        r = self.run_fetch()[0][0]
        self.assertEqual(r["message_count"], 1)
        self.assertEqual([m["id"] for m in r["messages"]], ["1"])
        self.assertEqual(r["participants"], ["zoe@acme.be"])

    def test_messages_without_a_conversation_id_do_not_collapse_into_one(self):
        # Graph omits conversationId often enough to matter. Keyed on a missing value they
        # all land in one bucket and N unrelated messages become one candidate - the same
        # bug as before, inverted, and far more destructive.
        msgs = [dict(m) for m in self.THREAD]
        for m in msgs:
            m.pop("conversationId")
        records, _ = self.run_fetch(msgs=msgs)
        self.assertEqual(len(records), 3)
        self.assertEqual({r["thread_id"] for r in records}, {"t1", "t2", "t3"})

    def test_the_preview_is_whitespace_normalised(self):
        records, _ = self.run_fetch()
        self.assertEqual(records[0]["preview"], "beste collega")

    def test_a_message_with_no_sender_address_is_still_emitted(self):
        # Judgment can still be made on the subject, and dropping it here would be a silent
        # loss of exactly the kind this subcommand exists to prevent.
        msgs = [{"id": "9", "internetMessageId": "<c@x>", "subject": "no sender",
                 "bodyPreview": "", "from": None, "toRecipients": [], "ccRecipients": [],
                 "receivedDateTime": "2026-09-01T10:00:00Z", "webLink": ""}]
        records, _ = self.run_fetch(msgs=msgs)
        self.assertEqual([r["id"] for r in records], ["9"])

    def test_a_feed_not_logged_in_here_is_named_in_the_closing_counts(self):
        # Skipped rather than fatal, but never silent: the caller must be able to tell a
        # quiet mailbox from one this machine never read.
        tokens = []
        records, err = self.run_fetch(feeds=("a@x.com", "b@x.com"),
                                      token=lambda _c, e: tokens.append(e) or "tok")
        self.assertEqual(tokens, ["a@x.com"])
        self.assertEqual({r["account"] for r in records}, {"a@x.com"})
        self.assertIn("1 mailbox(es) skipped (not logged in here): b@x.com", err)


class FeedResolution(unittest.TestCase):
    """A refresh token lives only on the machine it was granted on. On a vault fed by several
    mailboxes NO machine ever holds every account - not even the machine of whoever added the
    second one - so a missing account is an absence to work around, not a reason to exit
    before touching a single mailbox.

    Tested against resolve_feeds directly. It used to be reached through `sync`, which is
    gone; the behaviour is not, because `fetch` depends on it just as much.
    """

    ACCOUNTS = ["a@x.com", "b@x.com"]

    def resolve(self, cfg_accounts, account=None):
        cfg = {"accounts": {e: {"refresh_token": "t"} for e in cfg_accounts}}
        err = io.StringIO()
        with mock.patch.object(osync, "require_vault"), \
                mock.patch.object(osync, "load_vault_config", return_value={}), \
                mock.patch.object(osync, "vault_accounts", return_value=list(self.ACCOUNTS)), \
                contextlib.redirect_stderr(err):
            feeds, missing = osync.resolve_feeds(cfg, account)
        return feeds, missing, err.getvalue()

    def test_a_missing_account_does_not_block_the_ones_that_are_present(self):
        feeds, missing, err = self.resolve(["a@x.com"])
        self.assertEqual(feeds, ["a@x.com"])
        self.assertEqual(missing, ["b@x.com"])
        self.assertIn("skipping", err)

    def test_every_account_present_resolves_them_all_and_says_nothing(self):
        feeds, missing, err = self.resolve(self.ACCOUNTS)
        self.assertEqual(feeds, self.ACCOUNTS)
        self.assertEqual(missing, [])
        self.assertNotIn("skipping", err)

    def test_no_account_logged_in_here_still_exits(self):
        # Nothing to do and no partial result to report: that is a real stop.
        with self.assertRaises(SystemExit):
            self.resolve([])

    def test_a_named_account_that_is_not_logged_in_exits(self):
        # A direct ask deserves a direct answer. Skipping past it would answer a question
        # the user did not put.
        with self.assertRaises(SystemExit):
            self.resolve(["a@x.com"], account="b@x.com")

    def test_a_named_account_that_does_not_feed_this_vault_exits(self):
        with self.assertRaises(SystemExit):
            self.resolve(self.ACCOUNTS, account="stranger@x.com")

    def test_a_named_account_that_is_logged_in_is_the_whole_answer(self):
        feeds, missing, err = self.resolve(["b@x.com"], account="b@x.com")
        self.assertEqual((feeds, missing, err), (["b@x.com"], [], ""))

    def test_a_vault_config_listing_no_accounts_exits(self):
        with mock.patch.object(osync, "require_vault"), \
                mock.patch.object(osync, "load_vault_config", return_value={"accounts": []}):
            with self.assertRaises(SystemExit) as e:
                osync.resolve_feeds({"accounts": {"a@x.com": {"refresh_token": "t"}}}, None)
        self.assertIn("lists no accounts", str(e.exception))


class CmdSearch(unittest.TestCase):
    """`search` asks one question of whole mailboxes. It prints and never writes, and it reads
    only the mailboxes that feed this vault unless told otherwise, so a work-vault session
    never prints personal mail."""

    CFG = {"client_id": "X", "accounts": {
        "me@corp.com": {"refresh_token": "t"},
        "info@corp.com": {"via": "me@corp.com"},
        "home@h.com": {"refresh_token": "t"}}}

    HIT = {"receivedDateTime": "2026-09-01T10:00:00Z", "subject": "Contract\n   renewal  2027",
           "bodyPreview": "  Dear  team,\n see the attached draft ",
           "from": {"emailAddress": {"name": "Zoe", "address": "zoe@acme.be"}}}

    def run_search(self, account=None, all_mailboxes=False, body=False, limit=50,
                   feeds=("me@corp.com",), hits=None, cfg=None, broken=()):
        """cmd_search with the token and the Graph search stubbed.

        `hits` maps a Graph root to the messages found there. An account in `broken` exits
        the way a refused refresh does. Returns (stdout, stderr, [(token, root, limit)]).
        """
        args = argparse.Namespace(query="contract renewal", account=account,
                                  all_mailboxes=all_mailboxes, body=body, limit=limit)
        calls = []

        def token(_cfg, email):
            if email in broken:
                sys.exit(f"Token refresh for {email} failed (invalid_grant).")
            return f"tok:{email}"

        def search(tok, query, limit, root):
            self.assertEqual(query, "contract renewal")
            calls.append((tok, root, limit))
            return list((hits or {}).get(root, []))

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(osync, "load_vault_config", return_value={"accounts": list(feeds)}), \
                mock.patch.object(osync, "access_token", side_effect=token), \
                mock.patch.object(osync, "search_messages", side_effect=search), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            osync.cmd_search(cfg or self.CFG, args)
        return out.getvalue(), err.getvalue(), calls

    def test_by_default_only_this_vaults_mailboxes_are_searched(self):
        _, _, calls = self.run_search(feeds=("me@corp.com",), limit=5)
        self.assertEqual(calls, [("tok:me@corp.com", "/me", 5)])

    def test_all_mailboxes_widens_to_every_account_on_the_machine(self):
        _, _, calls = self.run_search(all_mailboxes=True)
        self.assertEqual(sorted((t, r) for t, r, _ in calls), [
            ("tok:home@h.com", "/me"), ("tok:me@corp.com", "/me"),
            ("tok:me@corp.com", "/users/info@corp.com")])

    def test_a_named_account_is_searched_alone_even_outside_this_vault(self):
        _, _, calls = self.run_search(account="home@h.com", feeds=("me@corp.com",))
        self.assertEqual([(t, r) for t, r, _ in calls], [("tok:home@h.com", "/me")])

    def test_a_shared_mailbox_is_searched_through_its_via_users_token(self):
        _, _, calls = self.run_search(feeds=("info@corp.com",))
        self.assertEqual([(t, r) for t, r, _ in calls],
                         [("tok:me@corp.com", "/users/info@corp.com")])

    def test_a_vault_listing_no_accounts_exits_naming_the_flags_that_widen_it(self):
        with self.assertRaises(SystemExit) as e:
            self.run_search(feeds=())
        self.assertIn("--account", str(e.exception))
        self.assertIn("--all-mailboxes", str(e.exception))

    def test_all_mailboxes_on_a_machine_with_none_exits(self):
        with self.assertRaises(SystemExit) as e:
            self.run_search(all_mailboxes=True, cfg={"client_id": "X", "accounts": {}})
        self.assertIn("No accounts configured", str(e.exception))

    def test_one_failing_mailbox_does_not_cost_the_others(self):
        out, err, calls = self.run_search(feeds=("home@h.com", "me@corp.com"),
                                          hits={"/me": [self.HIT]}, broken=("home@h.com",))
        self.assertEqual([t for t, _, _ in calls], ["tok:me@corp.com"])
        self.assertIn("home@h.com  SEARCH FAILED", err)
        self.assertIn("me@corp.com  1 hit(s) for 'contract renewal'", out)
        self.assertIn("1 hit(s) total. Read-only: nothing was written.", out)

    def test_a_hit_prints_its_date_sender_and_a_one_line_subject(self):
        out, _, _ = self.run_search(hits={"/me": [self.HIT]})
        self.assertIn("  2026-09-01  zoe@acme.be ", out)
        self.assertIn("Contract renewal 2027", out)
        self.assertNotIn("T10:00", out)
        self.assertNotIn("Dear team", out)        # the preview is --body's to add

    def test_body_adds_one_normalised_preview_line_per_hit_that_has_one(self):
        bare = {"subject": None, "from": None, "bodyPreview": ""}
        out, _, _ = self.run_search(body=True, hits={"/me": [self.HIT, bare]})
        previews = [line for line in out.splitlines()
                    if line.startswith(" " * 14) and line.strip()]
        self.assertEqual([p.strip() for p in previews], ["Dear team, see the attached draft"])
        self.assertIn("(no subject)", out)         # a hit missing both still prints
        self.assertIn("2 hit(s) total", out)

    def test_a_hit_with_a_null_sender_prints_a_question_mark_and_the_rest_still_print(self):
        # A null address used to reach the format string and raise, outside the per-mailbox
        # guard, so every mailbox not yet printed was lost with it.
        null_address = dict(self.HIT, **{"from": {"emailAddress": {"address": None}}})
        null_email = dict(self.HIT, **{"from": {"emailAddress": None}})
        out, err, _ = self.run_search(account=None, all_mailboxes=True,
                                      hits={"/me": [null_address, null_email, self.HIT]})
        self.assertEqual(err, "")
        lines = [ln for ln in out.splitlines() if "Contract renewal 2027" in ln]
        self.assertEqual(len(lines), 3 * 2)   # two mailboxes read /me: me@corp.com, home@h.com
        self.assertTrue(lines[0].split()[1] == "?" and lines[1].split()[1] == "?")
        self.assertIn("zoe@acme.be", lines[2])


class CmdRaw(unittest.TestCase):
    """`raw` is the debugging escape hatch: any Graph path, printed as JSON."""

    CFG = {"client_id": "X", "accounts": {"a@h.com": {"refresh_token": "t"},
                                          "b@h.com": {"refresh_token": "t"}}}

    def run_raw(self, path="/me/messages?$top=1", account=None, cfg=None, body=None):
        out = io.StringIO()
        with mock.patch.object(osync, "access_token", return_value="tok") as token, \
                mock.patch.object(osync, "graph_get", return_value=body or {"value": []}) as get, \
                contextlib.redirect_stdout(out):
            osync.cmd_raw(cfg or self.CFG, argparse.Namespace(path=path, account=account))
        return out.getvalue(), token, get

    def test_the_named_account_reads_the_path_as_given(self):
        _, token, get = self.run_raw(account="b@h.com")
        self.assertEqual(token.call_args.args[1], "b@h.com")
        get.assert_called_once_with("tok", "/me/messages?$top=1")

    def test_without_an_account_the_first_configured_one_is_used(self):
        _, token, _ = self.run_raw()
        self.assertEqual(token.call_args.args[1], "a@h.com")

    def test_no_account_anywhere_exits_asking_for_one(self):
        with self.assertRaises(SystemExit) as e:
            self.run_raw(cfg={"client_id": "X", "accounts": {}})
        self.assertIn("--account", str(e.exception))

    def test_the_answer_is_printed_as_json_with_non_ascii_intact(self):
        body = {"value": [{"subject": "Offerte café Brussel"}]}
        out, _, _ = self.run_raw(body=body)
        self.assertEqual(json.loads(out), body)
        self.assertIn("Offerte café Brussel", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
