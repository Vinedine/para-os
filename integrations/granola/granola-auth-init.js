// granola-auth-init.js  (ONE-TIME / re-login bootstrap - run this once before your first sync)
// para-os-integration: granola 2026.09.05 - see CHANGELOG.md; /para-upgrade reports drift against this line.
//   node granola-auth-init.js
// Extracts the Granola login token from the local Granola desktop app and writes it to the paraos
// secret (~/.paraos/secrets/granola.json), then does a quick API sanity check. Run it again only if
// the refresh token ever dies (you logged out / back in to the Granola app). Normal syncing never
// needs this - granola.js refreshes the token itself.
//
// PLATFORM: Windows and macOS. Granola is an Electron app and encrypts its token store with the
// OS's secret store: on Windows the key is DPAPI-protected (read through PowerShell), on macOS it
// is the "Granola Safe Storage" Keychain item (read with `security`, which asks once for access).
// An older app that left a plain supabase.json is read as it is. Linux has no Granola app.
//
// Integration state lives under ~/.paraos (override with PARAOS_HOME); see ~/.paraos/README.md.

const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { execFileSync } = require("child_process");

const WIN = process.platform === "win32", MAC = process.platform === "darwin";
// The local Granola app's store: %APPDATA%\Granola on Windows, ~/Library/Application Support/Granola on macOS.
const DIR = process.env.GRANOLA_APP_DIR || (WIN ? path.join(process.env.APPDATA || "", "Granola")
  : path.join(os.homedir(), "Library", "Application Support", "Granola"));
const PARAOS_HOME = process.env.PARAOS_HOME || path.join(process.env.USERPROFILE || os.homedir(), ".paraos");
const AUTH_FILE = path.join(PARAOS_HOME, "secrets", "granola.json");
// Electron names the Keychain item "<app name> Safe Storage".
const KEYCHAIN_SERVICES = ["Granola Safe Storage", "granola Safe Storage"];

// ---- Windows: Chromium os_crypt, AES-256-GCM under a DPAPI-protected key ----
function windowsMasterKey() {
  const ls = JSON.parse(fs.readFileSync(path.join(DIR, "Local State"), "utf8"));
  const b64 = ls.os_crypt.encrypted_key;
  const ps = `Add-Type -AssemblyName System.Security
$enc=[Convert]::FromBase64String('${b64}')
$k=[System.Security.Cryptography.ProtectedData]::Unprotect($enc[5..($enc.Length-1)],$null,'CurrentUser')
[Convert]::ToBase64String($k)`;
  return Buffer.from(execFileSync("powershell.exe", ["-NoProfile", "-Command", ps]).toString().trim(), "base64");
}
function gcm(buf, key, off) {
  const nonce = buf.slice(off, off + 12), tag = buf.slice(buf.length - 16), ct = buf.slice(off + 12, buf.length - 16);
  const d = crypto.createDecipheriv("aes-256-gcm", key, nonce); d.setAuthTag(tag);
  return Buffer.concat([d.update(ct), d.final()]);
}

// ---- macOS: Chromium os_crypt, AES-128-CBC under a key derived from the Keychain password ----
// The fixed salt, iteration count and all-spaces IV are Chromium's, not secrets.
function macKey(password) {
  return crypto.pbkdf2Sync(Buffer.from(password, "utf8"), "saltysalt", 1003, 16, "sha1");
}
function macDecrypt(buf, key) {
  const prefix = buf.slice(0, 3).toString("latin1");
  if (prefix !== "v10" && prefix !== "v11") throw new Error("not a Chromium-encrypted blob (prefix " + JSON.stringify(prefix) + ")");
  const d = crypto.createDecipheriv("aes-128-cbc", key, Buffer.alloc(16, " "));
  return Buffer.concat([d.update(buf.slice(3)), d.final()]);
}
function keychainPassword() {
  for (const service of KEYCHAIN_SERVICES) {
    try { return execFileSync("security", ["find-generic-password", "-w", "-s", service], { stdio: ["ignore", "pipe", "ignore"] }).toString().trim(); }
    catch {}
  }
  throw new Error(`no Keychain item named ${KEYCHAIN_SERVICES.map(s => JSON.stringify(s)).join(" or ")}: `
    + "is the Granola app installed and signed in on this Mac? If macOS asked for Keychain access, allow it and run this again.");
}

// The data key that encrypts supabase.json.enc, from storage.dek, per platform.
function dataKey() {
  const dek = fs.readFileSync(path.join(DIR, "storage.dek"));
  const b64 = WIN ? gcm(dek, windowsMasterKey(), 3) : macDecrypt(dek, macKey(keychainPassword()));
  return Buffer.from(b64.toString(), "base64");
}
function decrypt(buf, dek) {
  for (const off of [0, 3]) { try { return gcm(buf, dek, off); } catch {} }
  throw new Error("could not decrypt supabase.json.enc");
}
// Granola's token store: the encrypted one current apps write, or the plain one older apps left.
function readStore() {
  const enc = path.join(DIR, "supabase.json.enc"), plain = path.join(DIR, "supabase.json");
  if (fs.existsSync(enc)) return JSON.parse(decrypt(fs.readFileSync(enc), dataKey()).toString());
  if (fs.existsSync(plain)) return JSON.parse(fs.readFileSync(plain, "utf8"));
  throw new Error(`no Granola token store in ${DIR}: is the Granola app installed and signed in?`);
}

async function refresh(clientId, refreshToken) {
  const r = await fetch("https://api.workos.com/user_management/authenticate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ grant_type: "refresh_token", client_id: clientId, refresh_token: refreshToken }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error("refresh failed " + r.status + " " + JSON.stringify(j).slice(0, 200));
  return j;
}

async function main() {
  if (!WIN && !MAC) {
    console.error("granola-auth-init.js runs on Windows and macOS, where the Granola app runs. See integrations/granola/README.md.");
    process.exitCode = 1; return;
  }
  const store = readStore();
  const wt = typeof store.workos_tokens === "string" ? JSON.parse(store.workos_tokens) : store.workos_tokens;
  const payload = JSON.parse(Buffer.from(wt.access_token.split(".")[1], "base64").toString());
  const clientId = payload.iss.split("/").pop();
  const now = Math.floor(Date.now() / 1000);

  let access = wt.access_token, refreshTok = wt.refresh_token, exp = payload.exp;
  console.log("[i] client:", clientId, "| token expired:", exp < now);
  if (exp < now) {
    console.log("[i] refreshing to get a live token...");
    const j = await refresh(clientId, refreshTok);
    access = j.access_token; refreshTok = j.refresh_token || refreshTok;
    exp = JSON.parse(Buffer.from(access.split(".")[1], "base64").toString()).exp;
    console.log("[ok] refreshed");
  }

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
  fs.writeFileSync(AUTH_FILE, JSON.stringify({ client_id: clientId, refresh_token: refreshTok, access_token: access, access_expires: exp }, null, 2), { mode: 0o600 });
  console.log("[ok] wrote token to:", AUTH_FILE);

  // quick sanity check
  const res = await fetch("https://api.granola.ai/v2/get-documents", {
    method: "POST",
    headers: { "Authorization": "Bearer " + access, "Content-Type": "application/json", "User-Agent": "Granola/6.0.0", "X-Client-Version": "6.0.0" },
    body: JSON.stringify({ limit: 1, offset: 0 }),
  });
  if (res.ok) {
    const docs = (await res.json()).docs || [];
    console.log("[ok] API reachable - newest meeting:", docs[0] ? `${docs[0].title} (${(docs[0].created_at || "").slice(0, 10)})` : "(none)");
    console.log("\nDone. You can now run granola.js.");
  } else {
    console.log("[x] API returned HTTP", res.status, "-", (await res.text()).slice(0, 200));
  }
}
// Run only when invoked directly, so the tests can require() the decryption helpers.
if (require.main === module) main().catch(e => { console.error("[x]", e.message); process.exitCode = 1; });

module.exports = { gcm, macKey, macDecrypt, decrypt, readStore };
