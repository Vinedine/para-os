// granola-auth-init.js  (ONE-TIME / re-login bootstrap - run this once before your first sync)
//   node granola-auth-init.js
// Extracts the Granola login token from the local Granola desktop app and writes it to the paraos
// secret (~/.paraos/secrets/granola.json), then does a quick API sanity check. Run it again only if
// the refresh token ever dies (you logged out / back in to the Granola app). Normal syncing never
// needs this - granola-sync.js refreshes the token itself.
//
// PLATFORM: Windows only. It reads the Granola app's encrypted token store via Windows DPAPI
// (through PowerShell). macOS/Linux are not supported by this script - see the README.
//
// Integration state lives under ~/.paraos (override with PARAOS_HOME); see ~/.paraos/README.md.

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execFileSync } = require("child_process");

const DIR = path.join(process.env.APPDATA, "Granola"); // the local Granola app's encrypted store
const PARAOS_HOME = process.env.PARAOS_HOME || path.join(process.env.USERPROFILE, ".paraos");
const AUTH_FILE = path.join(PARAOS_HOME, "secrets", "granola.json");

function masterKey() {
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
function decrypt(file, dek) {
  const buf = fs.readFileSync(path.join(DIR, file));
  for (const off of [0, 3]) { try { return gcm(buf, dek, off); } catch {} }
  throw new Error("could not decrypt " + file);
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
  const mk = masterKey();
  const dek = Buffer.from(gcm(fs.readFileSync(path.join(DIR, "storage.dek")), mk, 3).toString(), "base64");
  const store = JSON.parse(decrypt("supabase.json.enc", dek).toString());
  const wt = JSON.parse(store.workos_tokens);
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
  fs.writeFileSync(AUTH_FILE, JSON.stringify({ client_id: clientId, refresh_token: refreshTok, access_token: access, access_expires: exp }, null, 2));
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
    console.log("\nDone. You can now run granola-sync.js.");
  } else {
    console.log("[x] API returned HTTP", res.status, "-", (await res.text()).slice(0, 200));
  }
}
main().catch(e => console.log("[x]", e.message));
