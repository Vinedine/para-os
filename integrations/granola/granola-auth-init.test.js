// granola-auth-init.test.js - the token-store decryption and the sign-in it feeds, off any real
// Granola install, Keychain, DPAPI or network.
// Run: node --test   (from integrations/granola/)
//
// The fixtures are built here with the same Chromium schemes the app uses, so what is pinned is
// that each layer unwraps what that scheme wraps. Whether a given Granola release still uses
// them is only checkable against the app itself.

const test = require("node:test");
const assert = require("node:assert");
const path = require("path");
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");
const { spawnSync } = require("child_process");
const { gcm, macKey, macDecrypt, decrypt } = require("./granola-auth-init.js");

const STORE = { workos_tokens: JSON.stringify({ access_token: "a.b.c", refresh_token: "r1" }) };

// Chromium's macOS scheme: "v10", then AES-128-CBC under PBKDF2(password), IV of 16 spaces.
function macEncrypt(plain, password) {
  const c = crypto.createCipheriv("aes-128-cbc", macKey(password), Buffer.alloc(16, " "));
  return Buffer.concat([Buffer.from("v10"), c.update(plain), c.final()]);
}
// Granola's store layer: an optional "v10", a 12-byte nonce, AES-256-GCM ciphertext, 16-byte tag.
function gcmEncrypt(plain, key, prefix) {
  const nonce = crypto.randomBytes(12), c = crypto.createCipheriv("aes-256-gcm", key, nonce);
  const ct = Buffer.concat([c.update(plain), c.final()]);
  return Buffer.concat([Buffer.from(prefix), nonce, ct, c.getAuthTag()]);
}

test("macOS: the Keychain password unwraps storage.dek, whose key opens the store", () => {
  const dek = crypto.randomBytes(32);
  const dekBlob = macEncrypt(Buffer.from(dek.toString("base64")), "keychain-secret");
  const storeBlob = gcmEncrypt(Buffer.from(JSON.stringify(STORE)), dek, "v10");
  const unwrapped = Buffer.from(macDecrypt(dekBlob, macKey("keychain-secret")).toString(), "base64");
  assert.deepStrictEqual(unwrapped, dek);
  assert.deepStrictEqual(JSON.parse(decrypt(storeBlob, unwrapped).toString()), STORE);
});

test("macOS: a wrong Keychain password fails rather than returning garbage", () => {
  const dekBlob = macEncrypt(Buffer.from(crypto.randomBytes(32).toString("base64")), "right");
  assert.throws(() => macDecrypt(dekBlob, macKey("wrong")));
});

test("macOS: a blob without Chromium's version prefix is refused by name", () => {
  assert.throws(() => macDecrypt(Buffer.from("xyz0123456789abcdef"), macKey("p")), /not a Chromium-encrypted blob/);
});

test("Windows: the GCM layer opens a store written with or without the version prefix", () => {
  const key = crypto.randomBytes(32), plain = Buffer.from("hello");
  assert.strictEqual(gcm(gcmEncrypt(plain, key, "v10"), key, 3).toString(), "hello");
  assert.strictEqual(decrypt(gcmEncrypt(plain, key, ""), key).toString(), "hello");
});

function runWith(env, code) {
  return spawnSync(process.execPath, ["-e", code], { env: { ...env, PATH: process.env.PATH }, encoding: "utf8" });
}

test("an older app's plain supabase.json is read as it is", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "granola-app-"));
  fs.writeFileSync(path.join(dir, "supabase.json"), JSON.stringify(STORE));
  const r = runWith({ GRANOLA_APP_DIR: dir },
    `process.stdout.write(JSON.stringify(require(${JSON.stringify(path.join(__dirname, "granola-auth-init.js"))}).readStore()))`);
  assert.strictEqual(r.status, 0, r.stderr);
  assert.deepStrictEqual(JSON.parse(r.stdout), STORE);
});

test("a missing token store names the folder it looked in", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "granola-app-"));
  const r = runWith({ GRANOLA_APP_DIR: dir },
    `require(${JSON.stringify(path.join(__dirname, "granola-auth-init.js"))}).readStore()`);
  assert.notStrictEqual(r.status, 0);
  assert.match(r.stderr, /no Granola token store in/);
});

test("the module loads with no APPDATA, USERPROFILE or HOME-derived override set", () => {
  const r = runWith({}, `require(${JSON.stringify(path.join(__dirname, "granola-auth-init.js"))})`);
  assert.strictEqual(r.status, 0, r.stderr);
});

test("a store that the data key does not open is refused by name", () => {
  const blob = gcmEncrypt(Buffer.from(JSON.stringify(STORE)), crypto.randomBytes(32), "v10");
  assert.throws(() => decrypt(blob, crypto.randomBytes(32)), /could not decrypt supabase\.json\.enc/);
});


// --- the sign-in, end to end ------------------------------------------------------------
// granola-auth-init.js run for real on a plain supabase.json in a throwaway app folder, with the
// secret under a temporary PARAOS_HOME. The preload stubs fetch, logs every request, and sets
// process.platform: past the platform check, main() is the same on Windows and macOS, so these
// run on every OS.

const AUTH_INIT = path.join(__dirname, "granola-auth-init.js");
const TEMP = [];
process.on("exit", () => {
  for (const d of TEMP) { try { fs.rmSync(d, { recursive: true, force: true }); } catch {} }
});
// Resolved, as Node resolves a script's own folder: macOS spells its temp folder two ways.
const TMP = fs.realpathSync(os.tmpdir());
const tempDir = () => { const d = fs.mkdtempSync(path.join(TMP, "granola-init-")); TEMP.push(d); return d; };

const PRELOAD = path.join(tempDir(), "preload.js");
fs.writeFileSync(PRELOAD, `
const fs = require("fs");
if (process.env.GRANOLA_TEST_PLATFORM) Object.defineProperty(process, "platform", { value: process.env.GRANOLA_TEST_PLATFORM });
const responses = JSON.parse(process.env.GRANOLA_TEST_RESPONSES || "{}");
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  fs.appendFileSync(process.env.GRANOLA_TEST_LOG, JSON.stringify({ url, auth: (init.headers || {}).Authorization || null,
    body: init.body ? JSON.parse(init.body) : null }) + "\\n");
  const hit = Object.keys(responses).find(k => url.endsWith(k));
  const { status = 200, body = {}, raw } = hit ? responses[hit] : {};
  // \`raw\` serves a body that is not JSON, as a proxy's HTML error page is.
  if (raw !== undefined) return { ok: status < 300, status, json: async () => JSON.parse(raw), text: async () => raw };
  return { ok: status < 300, status, json: async () => body, text: async () => JSON.stringify(body) };
};
`);

// WorkOS access tokens: the payload's issuer ends in the client id, and exp is read for expiry.
const NOW_S = Math.floor(Date.now() / 1000);
const jwt = claims => `h.${Buffer.from(JSON.stringify(claims)).toString("base64")}.s`;
const ISS = "https://api.workos.com/user_management/client_01ABC";
const LIVE = jwt({ iss: ISS, exp: NOW_S + 3600 });
const EXPIRED = jwt({ iss: ISS, exp: NOW_S - 60 });
const FRESH = jwt({ exp: NOW_S + 7200 });
const tokens = access => ({ workos_tokens: JSON.stringify({ access_token: access, refresh_token: "r1" }) });
const NEWEST = { "/get-documents": { body: { docs: [{ title: "Kickoff", created_at: "2026-07-28T09:11:00Z" }] } } };
const refreshGives = body => ({ ...NEWEST, "/authenticate": { body: { access_token: FRESH, ...body } } });

function signIn(store, { responses = NEWEST, platform = "darwin" } = {}) {
  const dir = tempDir(), app = path.join(dir, "app"), home = path.join(dir, "paraos");
  const log = path.join(dir, "requests.jsonl"), secret = path.join(home, "secrets", "granola.json");
  fs.mkdirSync(app);
  fs.writeFileSync(path.join(app, "supabase.json"), JSON.stringify(store));
  const r = spawnSync(process.execPath, ["--require", PRELOAD, AUTH_INIT], {
    encoding: "utf8",
    env: { ...process.env, GRANOLA_APP_DIR: app, PARAOS_HOME: home, GRANOLA_TEST_PLATFORM: platform,
           GRANOLA_TEST_RESPONSES: JSON.stringify(responses), GRANOLA_TEST_LOG: log },
  });
  return {
    status: r.status, stdout: r.stdout, stderr: r.stderr,
    secret: fs.existsSync(secret) ? JSON.parse(fs.readFileSync(secret, "utf8")) : null,
    secretMode: () => fs.statSync(secret).mode & 0o777,
    requests: fs.existsSync(log) ? fs.readFileSync(log, "utf8").trim().split("\n").map(l => JSON.parse(l)) : [],
  };
}

test("off Windows and macOS it refuses by name, before reading or writing anything", () => {
  const r = signIn(tokens(LIVE), { platform: "linux" });
  assert.strictEqual(r.status, 1);
  assert.match(r.stderr, /runs on Windows and macOS/);
  assert.strictEqual(r.secret, null);
  assert.deepStrictEqual(r.requests, []);
});

test("a live token is saved as it is, with the client id taken from its issuer", () => {
  const r = signIn(tokens(LIVE));
  assert.strictEqual(r.status, 0, r.stderr);
  assert.deepStrictEqual(r.secret,
    { client_id: "client_01ABC", refresh_token: "r1", access_token: LIVE, access_expires: NOW_S + 3600 });
  assert.ok(!r.requests.some(q => q.url.endsWith("/authenticate")), "a live token needs no refresh");
});

test("the sanity check lists one meeting with the saved token and names the newest", () => {
  const r = signIn(tokens(LIVE));
  const check = r.requests.find(q => q.url.endsWith("/get-documents"));
  assert.strictEqual(check.auth, `Bearer ${LIVE}`);
  assert.deepStrictEqual(check.body, { limit: 1, offset: 0 });
  assert.match(r.stdout, /newest meeting: Kickoff \(2026-07-28\)/);
  assert.match(r.stdout, /Done\. You can now run granola\.js\./);
});

test("an account with no meetings yet says so", () => {
  const r = signIn(tokens(LIVE), { responses: { "/get-documents": { body: { docs: [] } } } });
  assert.strictEqual(r.status, 0, r.stderr);
  assert.match(r.stdout, /newest meeting: \(none\)/);
});

test("workos_tokens stored as an object is read the same as one stored as a JSON string", () => {
  const r = signIn({ workos_tokens: { access_token: LIVE, refresh_token: "r1" } });
  assert.strictEqual(r.status, 0, r.stderr);
  assert.strictEqual(r.secret.client_id, "client_01ABC");
  assert.strictEqual(r.secret.access_token, LIVE);
});

test("an expired token is refreshed before it is saved, and the check uses the new one", () => {
  const r = signIn(tokens(EXPIRED), { responses: refreshGives({ refresh_token: "r2" }) });
  assert.strictEqual(r.status, 0, r.stderr);
  const [refresh] = r.requests;
  assert.match(refresh.url, /\/authenticate$/);
  assert.deepStrictEqual(refresh.body, { grant_type: "refresh_token", client_id: "client_01ABC", refresh_token: "r1" });
  assert.deepStrictEqual(r.secret,
    { client_id: "client_01ABC", refresh_token: "r2", access_token: FRESH, access_expires: NOW_S + 7200 });
  assert.strictEqual(r.requests.find(q => q.url.endsWith("/get-documents")).auth, `Bearer ${FRESH}`);
});

test("a refresh that returns no new refresh token keeps the old one", () => {
  const r = signIn(tokens(EXPIRED), { responses: refreshGives({}) });
  assert.strictEqual(r.status, 0, r.stderr);
  assert.strictEqual(r.secret.refresh_token, "r1");
  assert.strictEqual(r.secret.access_token, FRESH);
});

test("a failed refresh stops with its status and the server's reason, and saves nothing", () => {
  const r = signIn(tokens(EXPIRED), { responses: { "/authenticate": { status: 400, body: { error: "invalid_grant" } } } });
  assert.strictEqual(r.status, 1);
  assert.match(r.stderr, /refresh failed 400 .*invalid_grant/);
  assert.strictEqual(r.secret, null);
});

test("a refresh refused with a body that is not JSON still reports its status", () => {
  const r = signIn(tokens(EXPIRED), { responses: { "/authenticate": { status: 502, raw: "<html>Bad gateway</html>" } } });
  assert.strictEqual(r.status, 1);
  assert.match(r.stderr, /refresh failed 502 .*Bad gateway/);
  assert.strictEqual(r.secret, null);
});

test("an API that rejects the token is reported, and the token is still saved", () => {
  const r = signIn(tokens(LIVE), { responses: { "/get-documents": { status: 401, body: { message: "Unauthorized" } } } });
  assert.match(r.stdout, /\[x\] API returned HTTP 401 - .*Unauthorized/);
  assert.doesNotMatch(r.stdout, /Done\./);
  assert.strictEqual(r.secret.access_token, LIVE);
});

test("the saved secret is readable by its owner only",
     { skip: process.platform === "win32" && "Windows has no POSIX file modes" }, () => {
  const r = signIn(tokens(LIVE));
  assert.strictEqual(r.status, 0, r.stderr);
  assert.strictEqual(r.secretMode().toString(8), "600");
});


// --- the encrypted store, through the OS secret store -------------------------------------
// `security` and `powershell.exe` are replaced by scripts first on PATH that answer only the
// question the real tool would be asked, so the real Keychain and DPAPI are never reached.
// POSIX only: Windows will not run a script in place of an .exe.

const NO_FAKE_EXE = process.platform === "win32" && "a script cannot stand in for an .exe on Windows";

function fakeTool(name, script) {
  const bin = tempDir();
  fs.writeFileSync(path.join(bin, name), "#!/bin/sh\n" + script, { mode: 0o755 });
  return bin;
}

// An app folder holding an encrypted store, its data key wrapped by `wrapDek`, plus `extra` files.
function encryptedApp(wrapDek, extra = {}) {
  const app = tempDir(), dek = crypto.randomBytes(32);
  fs.writeFileSync(path.join(app, "storage.dek"), wrapDek(Buffer.from(dek.toString("base64"))));
  fs.writeFileSync(path.join(app, "supabase.json.enc"), gcmEncrypt(Buffer.from(JSON.stringify(STORE)), dek, "v10"));
  for (const [name, body] of Object.entries(extra)) fs.writeFileSync(path.join(app, name), body);
  return app;
}

function readStoreIn(app, bin, platform) {
  return spawnSync(process.execPath,
    ["--require", PRELOAD, "-e", `process.stdout.write(JSON.stringify(require(${JSON.stringify(AUTH_INIT)}).readStore()))`],
    { encoding: "utf8", env: { ...process.env, GRANOLA_APP_DIR: app, GRANOLA_TEST_PLATFORM: platform,
                               PATH: bin + path.delimiter + process.env.PATH } });
}

test("macOS: the Keychain password opens the encrypted store, which wins over a plain one", { skip: NO_FAKE_EXE }, () => {
  const bin = fakeTool("security",
    '[ "$1 $2 $3 $4" = "find-generic-password -w -s Granola Safe Storage" ] && { echo keychain-secret; exit 0; }\nexit 44\n');
  const app = encryptedApp(b => macEncrypt(b, "keychain-secret"), { "supabase.json": JSON.stringify({ stale: true }) });
  const r = readStoreIn(app, bin, "darwin");
  assert.strictEqual(r.status, 0, r.stderr);
  assert.deepStrictEqual(JSON.parse(r.stdout), STORE);
});

test("macOS: an app whose Keychain item is named in lower case is found too", { skip: NO_FAKE_EXE }, () => {
  const bin = fakeTool("security", '[ "$4" = "granola Safe Storage" ] && { echo keychain-secret; exit 0; }\nexit 44\n');
  const r = readStoreIn(encryptedApp(b => macEncrypt(b, "keychain-secret")), bin, "darwin");
  assert.strictEqual(r.status, 0, r.stderr);
  assert.deepStrictEqual(JSON.parse(r.stdout), STORE);
});

test("macOS: with no Keychain item it names both items it looked for", { skip: NO_FAKE_EXE }, () => {
  const r = readStoreIn(encryptedApp(b => macEncrypt(b, "keychain-secret")), fakeTool("security", "exit 44\n"), "darwin");
  assert.notStrictEqual(r.status, 0);
  assert.match(r.stderr, /no Keychain item named "Granola Safe Storage" or "granola Safe Storage"/);
});

test("Windows: DPAPI unwraps Local State's key, which opens storage.dek, whose key opens the store",
     { skip: NO_FAKE_EXE }, () => {
  const master = crypto.randomBytes(32);
  const wrapped = Buffer.concat([Buffer.from("DPAPI"), crypto.randomBytes(24)]).toString("base64");
  // Answers only when handed Local State's key, the one blob DPAPI would unwrap.
  const bin = fakeTool("powershell.exe",
    `case "$3" in *"FromBase64String('${wrapped}')"*) echo ${master.toString("base64")}; exit 0;; esac\nexit 3\n`);
  const app = encryptedApp(b => gcmEncrypt(b, master, "v10"),
                           { "Local State": JSON.stringify({ os_crypt: { encrypted_key: wrapped } }) });
  const r = readStoreIn(app, bin, "win32");
  assert.strictEqual(r.status, 0, r.stderr);
  assert.deepStrictEqual(JSON.parse(r.stdout), STORE);
});
