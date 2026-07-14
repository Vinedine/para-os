// granola-sync.js - pull recent Granola meetings (enhanced notes + transcript) into a vault's triage/.
// Drop this file in <vault>/resources/scripts/ and run it there. By default every recent meeting is
// written to THIS vault's triage/ as a dated Markdown note, ready for /para-triage to file.
//   node granola-sync.js            # DRY RUN: shows what it would write, touches nothing
//   node granola-sync.js --write    # actually create the notes
//   node granola-sync.js --days 14  # override the 30-day look-back window
//
// Auth: reads ~/.paraos/secrets/granola.json (run granola-auth-init.js once to create it).
// The sync refreshes the access token itself and writes the rotated token back.
// See integrations/granola/README.md for setup, prerequisites, and the multi-vault routing config.

const fs = require("fs");
const path = require("path");

// ─── CONFIG · edit this block ────────────────────────────────────────────────
// Where synced meetings land inside the vault (relative to the vault root).
const MEETINGS_SUBDIR = "triage";

// Multi-vault routing (advanced, optional). Leave empty ({}) if you run a single
// vault: every meeting then goes to THIS vault's triage/.
// To fan meetings out across several sibling vaults by a title prefix - e.g. a
// meeting titled "Acme - Kickoff" into the sibling "acme-client" vault - map each
// prefix to its vault folder name. Sibling vaults must share one parent directory.
//   const ROUTE = { Acme: "acme-client", Home: "family", Side: "side-project" };
const ROUTE = {};
// ─── end config ──────────────────────────────────────────────────────────────

// Integration state lives under ~/.paraos (override with PARAOS_HOME); see ~/.paraos/README.md.
const PARAOS_HOME = process.env.PARAOS_HOME || path.join(process.env.USERPROFILE, ".paraos");
const AUTH = path.join(PARAOS_HOME, "secrets", "granola.json");
const STATE = path.join(PARAOS_HOME, "cache", "granola", "synced.json");

const WRITE = process.argv.includes("--write");
const ALL = process.argv.includes("--all"); // multi-vault: write every routed vault, not just this one
const DAYS = (() => { const i = process.argv.indexOf("--days"); return i > -1 ? parseInt(process.argv[i + 1], 10) : 30; })();
const VAULT_ARG = (() => { const i = process.argv.indexOf("--vault"); return i > -1 ? process.argv[i + 1] : null; })(); // target-vault override

// This copy lives in <vault>/resources/scripts/, so the vault root is two levels up.
const VAULT_ROOT = path.resolve(__dirname, "..", "..");
const VAULT_NAME = path.basename(VAULT_ROOT);
const PARENT = path.dirname(VAULT_ROOT); // shared parent of sibling vaults (multi-vault mode)
const MULTI = Object.keys(ROUTE).length > 0;
const ONLY_VAULT = VAULT_ARG || (ALL ? null : VAULT_NAME); // in multi-vault mode, default to this vault

const H = t => ({ "Authorization": "Bearer " + t, "Content-Type": "application/json", "User-Agent": "Granola/6.0.0", "X-Client-Version": "6.0.0" });
const exp = t => JSON.parse(Buffer.from(t.split(".")[1], "base64").toString()).exp;

async function token() {
  const a = JSON.parse(fs.readFileSync(AUTH, "utf8"));
  if (a.access_token && (a.access_expires || exp(a.access_token)) > Math.floor(Date.now() / 1000) + 30) return a.access_token;
  const r = await fetch("https://api.workos.com/user_management/authenticate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ grant_type: "refresh_token", client_id: a.client_id, refresh_token: a.refresh_token }) });
  const j = await r.json(); if (!r.ok) throw new Error("refresh failed " + r.status);
  a.access_token = j.access_token; if (j.refresh_token) a.refresh_token = j.refresh_token; a.access_expires = exp(a.access_token);
  fs.writeFileSync(AUTH, JSON.stringify(a, null, 2)); return a.access_token;
}
async function post(p, t, b) {
  const r = await fetch("https://api.granola.ai" + p, { method: "POST", headers: H(t), body: JSON.stringify(b || {}) });
  const txt = await r.text(); let j = null; try { j = JSON.parse(txt); } catch {}
  return { s: r.status, j, txt };
}

// ---- ProseMirror -> Markdown ----
function marks(text, ms) {
  if (!ms) return text;
  for (const m of ms) { if (m.type === "bold" || m.type === "strong") text = `**${text}**`; else if (m.type === "italic" || m.type === "em") text = `*${text}*`; else if (m.type === "code") text = "`" + text + "`"; }
  return text;
}
function inline(node) {
  if (!node) return "";
  if (node.type === "text") return marks(node.text || "", node.marks);
  if (node.type === "hardBreak") return "\n";
  return (node.content || []).map(inline).join("");
}
function pmToMd(node, depth = 0) {
  if (!node) return "";
  const kids = node.content || [];
  switch (node.type) {
    case "doc": return kids.map(k => pmToMd(k)).join("\n").replace(/\n{3,}/g, "\n\n").trim();
    case "heading": return "#".repeat(Math.min(6, (node.attrs && node.attrs.level) || 2)) + " " + kids.map(inline).join("");
    case "paragraph": return kids.map(inline).join("");
    case "bulletList": return kids.map(li => pmToMd(li, depth)).join("\n");
    case "orderedList": return kids.map((li, i) => pmToMd(li, depth, i + 1)).join("\n");
    case "listItem": {
      const bullet = "  ".repeat(depth) + "- ";
      const parts = kids.map(k => (k.type === "bulletList" || k.type === "orderedList") ? pmToMd(k, depth + 1) : pmToMd(k, depth));
      return bullet + parts.join("\n").replace(/^\n/, "");
    }
    case "blockquote": return kids.map(k => "> " + pmToMd(k, depth)).join("\n");
    default: return kids.map(k => pmToMd(k, depth)).join("\n");
  }
}

function transcriptMd(segs) {
  if (!Array.isArray(segs) || !segs.length) return "";
  const lines = []; let curSpk = null, buf = [];
  const flush = () => { if (buf.length) lines.push((curSpk ? `**${curSpk}:** ` : "") + buf.join(" ")); buf = []; };
  for (const s of segs) {
    const spk = s.detected_speaker_name || s.speaker || (s.source === "microphone" ? "Me" : "Them");
    if (spk !== curSpk) { flush(); curSpk = spk; }
    if (s.text) buf.push(s.text.trim());
  }
  flush();
  return lines.join("\n\n");
}

const sanitize = s => String(s).replace(/[\\/:*?"<>|]/g, "").replace(/\s+/g, " ").trim().slice(0, 80);

// Renumber panel heading levels to consecutive, starting at ### so they nest under "## Summary".
function demote(md, base = 3) {
  const levels = [...md.matchAll(/^(#{1,6}) /gm)].map(m => m[1].length);
  if (!levels.length) return md;
  const uniq = [...new Set(levels)].sort((a, b) => a - b);
  const map = new Map(uniq.map((l, i) => [l, Math.min(6, base + i)]));
  return md.replace(/^(#{1,6}) /gm, (_, h) => "#".repeat(map.get(h.length)) + " ");
}

// Decide which vault (and folder) a meeting belongs to.
// Single-vault mode (ROUTE empty): everything into this vault. Multi-vault: by title prefix.
function resolveDest(d) {
  const date = d.created_at.slice(0, 10);
  if (!MULTI) {
    return { vault: VAULT_NAME, dir: path.join(VAULT_ROOT, MEETINGS_SUBDIR), date, desc: sanitize(d.title) || "untitled" };
  }
  const m = String(d.title || "").match(/^\s*([A-Za-z0-9]+)\s*-/);
  const prefix = m && m[1];
  const vault = prefix && ROUTE[prefix];
  if (!vault) return { unrouted: true, prefix: prefix || "none" };
  if (ONLY_VAULT && vault !== ONLY_VAULT) return { skip: true };
  const desc = sanitize(String(d.title).replace(/^\s*[A-Za-z0-9]+\s*-\s*/, "")) || sanitize(d.title);
  return { vault, dir: path.join(PARENT, vault, MEETINGS_SUBDIR), date, desc };
}

async function main() {
  const t = await token();
  const state = fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, "utf8")) : {};
  const cutoff = Date.now() - DAYS * 86400000;

  // recent documents
  const docs = [];
  for (let off = 0; off < 500; off += 100) {
    const r = await post("/v2/get-documents", t, { limit: 100, offset: off });
    const b = (r.j && r.j.docs) || []; docs.push(...b);
    if (b.length < 100 || new Date(b[b.length - 1].created_at).getTime() < cutoff) break;
  }
  const recent = docs.filter(d => new Date(d.created_at).getTime() >= cutoff && !d.deleted_at);
  console.log(`${WRITE ? "WRITE" : "DRY RUN"} · last ${DAYS} days · ${recent.length} meetings${MULTI ? ` · routing ${ONLY_VAULT ? "-> " + ONLY_VAULT : "all vaults"}` : ""}\n`);

  let written = 0, skipped = 0, unrouted = 0;
  for (const d of recent.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))) {
    const r = resolveDest(d);
    const label = `${d.created_at.slice(0, 10)}  ${String(d.title || "(untitled)").slice(0, 34).padEnd(35)}`;

    if (r.skip) continue; // multi-vault filter: another vault's meeting, skip silently
    if (r.unrouted) { console.log("  ??  " + label + "-> UNROUTED (prefix: " + r.prefix + ")"); unrouted++; continue; }

    const fname = `${r.date.replace(/-/g, "")} ${r.desc}.md`;
    const dest = path.join(r.dir, fname);
    if (state[d.id] || fs.existsSync(dest)) { console.log("  ==  " + label + "-> " + r.vault + "/" + MEETINGS_SUBDIR + " (exists, skip)"); skipped++; continue; }

    // enhanced notes (the "Summary" panel Granola generates)
    const pr = await post("/v1/get-document-panels", t, { document_id: d.id });
    const panels = Array.isArray(pr.j) ? pr.j : ((pr.j && (pr.j.panels || pr.j.document_panels)) || []);
    const summary = panels.find(p => /summary/i.test(p.title || "")) || panels[0];
    const render = c => !c ? "" : (typeof c === "string" ? c.trim() : pmToMd(c));
    let minutes = "";
    if (summary) for (const c of [summary.content, summary.original_content, summary.content_json]) { minutes = render(c); if (minutes) break; }
    if (minutes) minutes = demote(minutes);

    // transcript
    const tr = await post("/v1/get-document-transcript", t, { document_id: d.id });
    const segs = Array.isArray(tr.j) ? tr.j : (tr.j && tr.j.transcript) || [];
    const transcript = transcriptMd(segs);

    const peopleArr = Array.isArray(d.people) ? d.people : (d.people && typeof d.people === "object" ? Object.values(d.people) : []);
    const people = peopleArr.map(p => (p && (p.name || p.email)) || null).filter(Boolean).join(", ");
    const md = [
      "---",
      `title: ${d.title}`,
      `date: ${r.date}`,
      `granola_id: ${d.id}`,
      `source: granola`,
      people ? `attendees: ${people}` : null,
      "---",
      "",
      `# ${d.title}`,
      `_${d.created_at.slice(0, 16).replace("T", " ")}_`,
      "",
      "## Summary",
      minutes || "_(no enhanced notes available)_",
      "",
      "## Transcript",
      transcript || "_(no transcript available)_",
      "",
    ].filter(x => x !== null).join("\n");

    console.log(`  ${WRITE ? "->" : "+ "}  ${label}-> ${r.vault}/${MEETINGS_SUBDIR}/${fname}  [min ${minutes.length}c · tr ${transcript.length}c]`);
    if (WRITE) {
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.writeFileSync(dest, md);
      state[d.id] = dest; written++;
    } else { written++; }
  }

  if (WRITE) { fs.mkdirSync(path.dirname(STATE), { recursive: true }); fs.writeFileSync(STATE, JSON.stringify(state, null, 2)); }
  console.log(`\n${WRITE ? "wrote" : "would write"}: ${written} · skipped(exists): ${skipped}${MULTI ? ` · unrouted: ${unrouted}` : ""}`);
  if (!WRITE) console.log("Re-run with --write to create the files.");
}
main().catch(e => console.log("[x]", e.message));
