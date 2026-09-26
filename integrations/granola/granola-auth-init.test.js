// granola-auth-init.test.js - the token-store decryption, off any real Granola install.
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
