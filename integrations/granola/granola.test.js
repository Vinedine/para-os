// Tests for granola.js: its pure helpers, and whole syncs run in a throwaway vault against a
// stubbed fetch. No Granola API, no real token, nothing written outside the OS temp directory.
// Uses node:test, built into Node 18+, which this integration already requires. Nothing to install.
//
//   node --test integrations/granola/granola.test.js
//
// Scope: the ProseMirror-to-Markdown conversion, transcript grouping, filename shaping, the config
// file, routing, token refresh, and the notes a sync writes. The Granola API's own behaviour is
// deliberately not covered - mocking it would assert that the mock behaves. Extracting the token
// from the app is granola-auth-init.test.js's concern.

// Notes are dated in local time, so pin the zone: every date below is then the same on any machine.
process.env.TZ = "UTC";

const test = require("node:test");
const assert = require("node:assert");
const path = require("path");
const fs = require("fs");
const os = require("os");
const { spawnSync } = require("child_process");
const { marks, inline, pmToMd, transcriptMd, sanitize, demote, resolveDest } = require("./granola.js");

// The vault convention, from base/CLAUDE.md.template: `YYYYMMDD Description.ext`. Both shipped
// integrations write into the same triage/ folder, so both must satisfy this. The outlook suite
// asserts the same shape against its own filenames.
const TRIAGE_NAME = /^\d{8} \S.*\.md$/;

const doc = (...content) => ({ type: "doc", content });
const para = (...content) => ({ type: "paragraph", content });
const text = (t, marks) => ({ type: "text", text: t, ...(marks ? { marks } : {}) });

test("marks: applies bold, italic and code", () => {
  assert.equal(marks("x", [{ type: "bold" }]), "**x**");
  assert.equal(marks("x", [{ type: "strong" }]), "**x**");
  assert.equal(marks("x", [{ type: "italic" }]), "*x*");
  assert.equal(marks("x", [{ type: "em" }]), "*x*");
  assert.equal(marks("x", [{ type: "code" }]), "`x`");
});

test("marks: no marks leaves the text alone", () => {
  assert.equal(marks("plain", null), "plain");
  assert.equal(marks("plain", []), "plain");
});

test("marks: unknown mark types are ignored, not dropped", () => {
  assert.equal(marks("x", [{ type: "highlight" }]), "x");
});

test("marks: nested marks compose", () => {
  assert.equal(marks("x", [{ type: "bold" }, { type: "italic" }]), "***x***");
});

test("inline: null node yields empty string", () => {
  assert.equal(inline(null), "");
});

test("inline: hardBreak becomes a newline", () => {
  assert.equal(inline({ type: "hardBreak" }), "\n");
});

test("inline: text node with no text yields empty string", () => {
  assert.equal(inline({ type: "text" }), "");
});

test("inline: recurses into content", () => {
  assert.equal(inline(para(text("a "), text("b", [{ type: "bold" }]))), "a **b**");
});

test("pmToMd: heading uses its level, defaulting to 2", () => {
  assert.equal(pmToMd({ type: "heading", attrs: { level: 3 }, content: [text("Topic")] }), "### Topic");
  assert.equal(pmToMd({ type: "heading", content: [text("Topic")] }), "## Topic");
});

test("pmToMd: heading level is capped at 6", () => {
  assert.equal(pmToMd({ type: "heading", attrs: { level: 9 }, content: [text("Deep")] }), "###### Deep");
});

test("pmToMd: bullet list items become dashes", () => {
  const md = pmToMd(doc({
    type: "bulletList",
    content: [
      { type: "listItem", content: [para(text("one"))] },
      { type: "listItem", content: [para(text("two"))] },
    ],
  }));
  assert.equal(md, "- one\n- two");
});

test("pmToMd: ordered list items keep their numbers", () => {
  const md = pmToMd(doc({
    type: "orderedList",
    content: [
      { type: "listItem", content: [para(text("one"))] },
      { type: "listItem", content: [para(text("two"))] },
    ],
  }));
  assert.equal(md, "1. one\n2. two");
});

test("pmToMd: an ordered list nested in a bullet list numbers only its own items", () => {
  const md = pmToMd(doc({
    type: "bulletList",
    content: [{
      type: "listItem",
      content: [
        para(text("outer")),
        { type: "orderedList", content: [{ type: "listItem", content: [para(text("first"))] },
                                         { type: "listItem", content: [para(text("second"))] }] },
      ],
    }],
  }));
  assert.equal(md, "- outer\n  1. first\n  2. second");
});

test("pmToMd: nested lists indent by two spaces", () => {
  const md = pmToMd(doc({
    type: "bulletList",
    content: [{
      type: "listItem",
      content: [
        para(text("outer")),
        { type: "bulletList", content: [{ type: "listItem", content: [para(text("inner"))] }] },
      ],
    }],
  }));
  assert.equal(md, "- outer\n  - inner");
});

test("pmToMd: blockquote prefixes every line", () => {
  assert.equal(pmToMd({ type: "blockquote", content: [para(text("quoted"))] }), "> quoted");
});

test("pmToMd: doc collapses runs of blank lines and trims", () => {
  const md = pmToMd(doc(para(text("a")), para(), para(), para(text("b"))));
  assert.ok(!/\n{3,}/.test(md), `blank-line run survived: ${JSON.stringify(md)}`);
  assert.equal(md, "a\n\nb");
});

test("pmToMd: null node and unknown types do not throw", () => {
  assert.equal(pmToMd(null), "");
  assert.equal(pmToMd({ type: "mysteryBlock", content: [para(text("kept"))] }), "kept");
});

test("pmToMd: a node with no content array renders empty", () => {
  // ProseMirror's JSON leaves `content` out of an empty node altogether.
  assert.equal(pmToMd({ type: "paragraph" }), "");
  assert.equal(pmToMd(doc({ type: "paragraph" }, para(text("after")))), "after");
  assert.equal(inline({ type: "mention" }), "");
});

test("transcriptMd: empty or non-array input yields empty string", () => {
  assert.equal(transcriptMd([]), "");
  assert.equal(transcriptMd(null), "");
  assert.equal(transcriptMd("nope"), "");
});

test("transcriptMd: consecutive segments from one speaker merge into a paragraph", () => {
  const out = transcriptMd([
    { detected_speaker_name: "Jan", text: "Hello" },
    { detected_speaker_name: "Jan", text: "and welcome" },
    { detected_speaker_name: "Sofie", text: "Thanks" },
  ]);
  assert.equal(out, "**Jan:** Hello and welcome\n\n**Sofie:** Thanks");
});

test("transcriptMd: the final speaker's buffer is flushed", () => {
  const out = transcriptMd([{ detected_speaker_name: "Jan", text: "last word" }]);
  assert.equal(out, "**Jan:** last word");
});

test("transcriptMd: falls back to Me/Them by source", () => {
  const out = transcriptMd([
    { source: "microphone", text: "mine" },
    { source: "system", text: "theirs" },
  ]);
  assert.equal(out, "**Me:** mine\n\n**Them:** theirs");
});

test("transcriptMd: segments with no text do not emit an empty line", () => {
  const out = transcriptMd([
    { detected_speaker_name: "Jan", text: "one" },
    { detected_speaker_name: "Jan" },
    { detected_speaker_name: "Jan", text: "two" },
  ]);
  assert.equal(out, "**Jan:** one two");
});

test("sanitize: replaces characters a filesystem rejects", () => {
  assert.equal(sanitize('Acme: plan/v2 <draft> "x"|y?'), "Acme plan v2 draft x y");
});

test("sanitize: illegal characters do not weld words together", () => {
  // Matches outlook.py's safe_title: both land in the same triage/ folder.
  assert.equal(sanitize("Q3/Q4 plan"), "Q3 Q4 plan");
});

test("sanitize: strips control characters without welding", () => {
  assert.equal(sanitize("Kickoff\n\tcall"), "Kickoff call");
});

test("sanitize: never ends in a space or a dot", () => {
  for (const s of ["trailing dot.", "trailing space   ", "ends in slash/"]) {
    const out = sanitize(s);
    assert.ok(!/[ .]$/.test(out), `${JSON.stringify(s)} -> ${JSON.stringify(out)}`);
  }
});

test("sanitize: a null or undefined title yields empty, not the string null", () => {
  assert.equal(sanitize(null), "");
  assert.equal(sanitize(undefined), "");
});

test("sanitize: collapses whitespace and trims", () => {
  assert.equal(sanitize("  Kickoff   call \n now "), "Kickoff call now");
});

test("sanitize: truncates to 80 characters", () => {
  assert.equal(sanitize("x".repeat(200)).length, 80);
});

test("sanitize: coerces non-strings rather than throwing", () => {
  assert.equal(sanitize(42), "42");
});

test("demote: renumbers heading levels to consecutive from ###", () => {
  assert.equal(demote("# A\n## B\ntext\n# C"), "### A\n#### B\ntext\n### C");
});

test("demote: text with no headings is returned unchanged", () => {
  assert.equal(demote("just prose\nand more"), "just prose\nand more");
});

test("demote: already-deep headings stay within six levels", () => {
  const out = demote("##### A\n###### B");
  assert.ok(/^#{3} A$/m.test(out), out);
  assert.ok(/^#{4} B$/m.test(out), out);
});

test("demote: a hash inside a line is not treated as a heading", () => {
  assert.equal(demote("see issue #42 here"), "see issue #42 here");
});

test("resolveDest: single-vault mode files everything into this vault's triage", () => {
  const d = resolveDest({ created_at: "2026-07-28T09:11:00Z", title: "Acme - Kickoff" });
  assert.equal(d.date, "2026-07-28");
  assert.equal(d.desc, "Acme - Kickoff");
  assert.equal(path.basename(d.dir), "triage");
  assert.ok(!d.unrouted && !d.skip, "single-vault mode never leaves a meeting unrouted");
});

test("resolveDest: an untitled meeting still gets a description", () => {
  for (const title of ["", null, undefined, "   ", "///"]) {
    const d = resolveDest({ created_at: "2026-07-28T09:11:00Z", title });
    assert.equal(d.desc, "untitled", `title ${JSON.stringify(title)} gave ${d.desc}`);
  }
});

test("the filename this integration writes matches the vault convention", () => {
  // granola.js builds `${date.replace(/-/g,"")} ${desc}.md`; the same shape outlook.py
  // must produce, since both land in the same triage/ folder for /para-triage to file.
  for (const title of ["Acme - Kickoff", "", null, "Q3/Q4: planning <call>", "...", "x".repeat(200)]) {
    const d = resolveDest({ created_at: "2026-07-28T09:11:00Z", title });
    const fname = `${d.date.replace(/-/g, "")} ${d.desc}.md`;
    assert.match(fname, TRIAGE_NAME, `bad triage filename for title ${JSON.stringify(title)}: ${fname}`);
  }
});

// --- config contract -------------------------------------------------------------------
// The property this integration guards: the script body holds nothing
// vault-specific, so an installed copy re-syncs by straight file copy. These guard the
// regression that made the old shape dangerous - a routing table living in the code, where
// a two-line diff looked trivial while silently zeroing it and dropping the script out of
// multi-vault mode.

const SOURCE = fs.readFileSync(path.join(__dirname, "granola.js"), "utf8");

test("the script declares no routing table of its own", () => {
  // `const ROUTE = { Acme: ... }` in the body is the old, dangerous shape. ROUTE must be
  // derived from the config file, never assigned an object literal with entries in it.
  const literal = /const\s+ROUTE\s*=\s*\{\s*[^}\s]/.exec(SOURCE);
  assert.equal(literal, null,
    `granola.js assigns ROUTE a populated literal: ${literal && literal[0]}`);
  assert.match(SOURCE, /CONFIG\.route/,
    "ROUTE must come from granola.config.json, not from the script body");
});

test("the config file sits beside the script, not in the vault's state directory", () => {
  // granola.config.json is vault config and belongs next to the copy that reads it. Only
  // credentials and cache go under ~/.paraos - putting config there would make one machine's
  // vaults share a routing table.
  assert.match(SOURCE, /VAULT_CONFIG\s*=\s*path\.join\(__dirname,\s*"granola\.config\.json"\)/,
    "granola.config.json must resolve beside the script");
  assert.doesNotMatch(SOURCE, /PARAOS_HOME[^\n]*granola\.config\.json/,
    "granola.config.json must not resolve under ~/.paraos");
});

test("an unreadable config stops the run instead of falling back to single-vault mode", () => {
  // The dangerous failure: malformed JSON silently yielding {} means MULTI is false, and every
  // other vault's meetings land in this one. Assert the catch path exits rather than defaults.
  const at = SOURCE.indexOf("catch (e)");
  assert.notEqual(at, -1, "config load must have a catch block");
  const catchBody = SOURCE.slice(at, SOURCE.indexOf("})();", at));
  assert.match(catchBody, /process\.exit\(1\)/,
    "a malformed granola.config.json must exit, never fall through to an empty config");
  assert.doesNotMatch(catchBody, /return\s*\{\s*\}/,
    "the catch must not return an empty config - that is single-vault mode by accident");
});

test("a config that parses but is not an object also stops the run", () => {
  // Valid-but-wrong-shape JSON (an array, a string, a bare number) must not slip past the
  // try/catch and land in CONFIG as something CONFIG.route silently can't see - that produces
  // the exact same "every other vault's meetings land in this one" failure as malformed JSON.
  assert.match(SOURCE, /typeof\s+parsed\s*!==\s*"object"/,
    "the config loader must reject a parsed value that is not an object");
  assert.match(SOURCE, /Array\.isArray\(parsed\)/,
    "an array is valid JSON but not a valid config shape, and must be rejected explicitly");
});

test("a silently skipped meeting is counted, not just dropped", () => {
  // The skip stays silent per meeting - naming another vault's meetings one by one is noise -
  // but it must reach a counter, or the closing line cannot add up to the header's count.
  const at = SOURCE.indexOf("if (r.skip)");
  assert.notEqual(at, -1, "the multi-vault skip must still exist");
  const stmt = SOURCE.slice(at, SOURCE.indexOf("\n", at));
  assert.match(stmt, /\+\+/, "a skipped meeting must increment a counter before `continue`");
});

test("the closing summary accounts for meetings routed to other vaults", () => {
  // Without this, a run that dropped every meeting through a misrouted config prints
  // `wrote: 0 · skipped(exists): 0 · unrouted: 0` against a header saying 30 meetings -
  // indistinguishable from a run that genuinely had nothing to do.
  const at = SOURCE.lastIndexOf("skipped(exists)");
  assert.notEqual(at, -1);
  const line = SOURCE.slice(at, SOURCE.indexOf("\n", at));
  assert.match(line, /other vaults/, "the summary must report the other-vaults count");
  assert.match(line, /MULTI \?/, "and only in multi-vault mode, where the number means something");
});


// --- route targets ----------------------------------------------------------------------
// Routing resolves against folder NAMES, and a folder name is machine-local: the OneDrive
// client names a synced SharePoint library in its own display language, so one library is
// "Client Site - Documents" here and "Client Site - Documenten" on a Dutch machine. The
// config is version-controlled and syncs to everyone, so a literal name is right on at most
// one machine - and wrong in the worst way on the rest, since an unmatched target is treated
// as another vault's meeting and dropped in silence while the run still reports success.
//
// These run granola.js inside a throwaway vault, one child process per config, because the
// config is read once at module load and Node caches the module.


// Each case runs granola.js in a throwaway vault; without this they accumulate in the OS temp
// directory, one tree per call, every run. Cleared on exit rather than per test so a failing
// case can still be inspected while the process is alive.
const TEMP_VAULTS = [];
// The OS temp folder has two spellings on macOS (/var is a link to /private/var), and Node hands
// an installed script the resolved one as __dirname. Resolving it here too means a path the
// script reports can be compared with one built from TMP.
const TMP = fs.realpathSync(os.tmpdir());
process.on("exit", () => {
  for (const d of TEMP_VAULTS) { try { fs.rmSync(d, { recursive: true, force: true }); } catch {} }
});

// The source of a script that runs granola.js as if it were installed in `scripts`. Rather than
// copy the file there, it compiles this folder's granola.js under its own filename, so coverage
// is counted against it, and hands it `scripts` as __dirname: the one thing a copy would change.
// With `asMain`, require.main is the module, so the sync runs exactly as `node granola.js` does.
function granolaRunner(scripts, { asMain = false, then = "" } = {}) {
  return [
    'const fs = require("fs"), vm = require("vm");',
    `const file = ${JSON.stringify(path.join(__dirname, "granola.js"))};`,
    'const body = vm.compileFunction(fs.readFileSync(file, "utf8"),',
    '  ["exports", "require", "module", "__filename", "__dirname"], { filename: file });',
    "const mod = { exports: {} };",
    `const req = Object.assign(id => require(id), { main: ${asMain ? "mod" : "require.main"} });`,
    `body.call(mod.exports, mod.exports, req, mod, ${JSON.stringify(path.join(scripts, "granola.js"))}, `
      + `${JSON.stringify(scripts)});`,
    then,
  ].join("\n");
}

// `config` is written as JSON, or as it is when it is a string, so a malformed file can be tested.
function inVault(config, expr, { vaultName = "myvault", siblings = [], argv = [], allowFailure = false } = {}) {
  const parent = fs.mkdtempSync(path.join(TMP, "granola-"));
  TEMP_VAULTS.push(parent);
  const scripts = path.join(parent, vaultName, "resources", "scripts");
  fs.mkdirSync(scripts, { recursive: true });
  if (config != null) {
    fs.writeFileSync(path.join(scripts, "granola.config.json"),
      typeof config === "string" ? config : JSON.stringify(config));
  }
  for (const sib of siblings) fs.mkdirSync(path.join(parent, sib, "triage"), { recursive: true });

  const runner = path.join(parent, "run.js");
  fs.writeFileSync(runner, granolaRunner(scripts, {
    then: `const { resolveDest } = mod.exports;\nconsole.log("<<" + JSON.stringify(${expr}) + ">>");\n` }));
  const r = spawnSync(process.execPath, [runner, ...argv], { encoding: "utf8" });
  const vaultRoot = path.join(parent, vaultName);
  if (allowFailure && r.status !== 0) return { status: r.status, stderr: r.stderr, vaultRoot };
  assert.equal(r.status, 0, `child exited ${r.status}: ${r.stderr}`);
  const out = /<<([\s\S]*)>>/.exec(r.stdout);
  assert.ok(out, `no result printed. stdout=${r.stdout} stderr=${r.stderr}`);
  return { status: 0, result: JSON.parse(out[1]), stderr: r.stderr, vaultRoot };
}

const meeting = title => `resolveDest({ created_at: "2026-07-28T09:11:00Z", title: ${JSON.stringify(title)} })`;

test('route "." means the vault this copy lives in', () => {
  const { result, stderr } = inVault({ route: { Client: "." } }, meeting("Client - Kickoff"));
  assert.ok(!result.skip, 'a "." route must not be treated as another vault');
  assert.equal(path.basename(result.dir), "triage");
  assert.equal(path.basename(path.dirname(result.dir)), "myvault");
  assert.equal(stderr, "", `"." must not warn: ${stderr}`);
});

test('route "." still leaves other prefixes unrouted, unlike single-vault mode', () => {
  // This is the whole point of "." over an absent config: a client-tenant vault wants THIS
  // client's meetings, not every meeting on the account.
  const { result } = inVault({ route: { Client: "." } }, meeting("Acme - Kickoff"));
  assert.ok(result.unrouted, "an unlisted prefix must stay unrouted, not fall into this vault");
});

test('"." and this vault\'s own name resolve to the same directory', () => {
  // Why resolveDest needs no special case for this vault: PARENT is dirname(VAULT_ROOT) and
  // VAULT_NAME is basename(VAULT_ROOT), so joining them back is VAULT_ROOT by construction,
  // and a rename moves both at once. One join covers this vault and every sibling.
  const dot = inVault({ route: { Client: "." } }, meeting("Client - Kickoff"));
  const named = inVault({ route: { Client: "myvault" } }, meeting("Client - Kickoff"));
  assert.equal(dot.result.dir, path.join(dot.vaultRoot, "triage"));
  assert.equal(named.result.dir, path.join(named.vaultRoot, "triage"));
});

test("a literal name for this vault still resolves, on the machine that spells it that way", () => {
  const { result, stderr } = inVault({ route: { Client: "myvault" } }, meeting("Client - Kickoff"));
  assert.ok(!result.skip);
  assert.equal(stderr, "", `an existing target must not warn: ${stderr}`);
});

test("a route target that is neither this vault nor a sibling warns once, at startup", () => {
  // The Dutch-machine config, read on an English machine. Before this warning the meeting
  // vanished through the silent multi-vault skip and the run still reported success.
  const { result, stderr } = inVault({ route: { Client: "Client Site - Documenten" } },
                                     meeting("Client - Kickoff"));
  assert.ok(result.skip, "an unresolvable target still skips - the warning is the fix, not a route");
  assert.match(stderr, /Client Site - Documenten/);
  assert.match(stderr, /route "Client"/,
    "the prefix must be quoted as the config spells it - a lowercased key is not findable there");
  assert.match(stderr, /skipped silently/);
  assert.match(stderr, /Use "\."/, "the warning must name the fix");
});

test("the warning is not fatal: a sibling vault may simply not be synced on this machine", () => {
  const { result } = inVault({ route: { Client: ".", Acme: "acme-client" } }, meeting("Client - Kickoff"));
  assert.ok(!result.skip, "an unresolvable OTHER route must not stop this one from resolving");
});

test("genuine sibling routing is unregressed", () => {
  const { result, stderr } = inVault(
    { route: { Acme: "acme-client" } }, meeting("Acme - Kickoff"),
    { siblings: ["acme-client"], argv: ["--vault", "acme-client"] });
  assert.ok(!result.skip && !result.unrouted, `sibling routing broke: ${JSON.stringify(result)}`);
  assert.equal(path.basename(path.dirname(result.dir)), "acme-client");
  assert.equal(stderr, "", `an existing sibling must not warn: ${stderr}`);
});

test('--vault "." targets this vault', () => {
  const { result, vaultRoot } = inVault(
    { route: { Client: ".", Acme: "acme-client" } }, meeting("Client - Kickoff"),
    { siblings: ["acme-client"], argv: ["--vault", "."] });
  assert.equal(result.dir, path.join(vaultRoot, "triage"));
});

test("--vault naming something no route points to stops the run", () => {
  // The config half of this was already guarded; the CLI half was not, and it fails the same
  // way: every meeting takes the silent multi-vault skip, the summary counts them under
  // "other vaults", and the run reports success having written nothing. A named target is an
  // explicit ask, so it gets an explicit answer - the same call outlook.py makes for
  // --account, and the reason this exits where an unresolvable route only warns.
  const r = inVault({ route: { Client: ".", Acme: "acme-client" } }, meeting("Client - Kickoff"),
                    { siblings: ["acme-client"], argv: ["--vault", "Client Site - Documenten"],
                      allowFailure: true });
  assert.notEqual(r.status, 0, "a --vault nothing routes to must not report success");
  assert.match(r.stderr, /nothing routes there/);
  assert.match(r.stderr, /acme-client/, "the message must list the targets that do work");
});

test("--vault naming a real route target is unaffected", () => {
  const r = inVault({ route: { Client: ".", Acme: "acme-client" } }, meeting("Acme - Kickoff"),
                    { siblings: ["acme-client"], argv: ["--vault", "acme-client"] });
  assert.ok(!r.result.skip && !r.result.unrouted, JSON.stringify(r.result));
});

test("--vault in single-vault mode says it is being ignored rather than pretending", () => {
  // With no route table resolveDest never consults ONLY_VAULT, so the flag silently does
  // nothing. Not fatal - the run is still correct - but it must not look like it applied.
  const r = inVault({}, meeting("Anything at all"), { argv: ["--vault", "elsewhere"] });
  assert.equal(r.status, 0);
  assert.match(r.stderr, /ignored/);
  assert.equal(path.basename(path.dirname(r.result.dir)), "myvault");
});

test("a malformed config stops the run and names the file", () => {
  const r = inVault('{ "route": { "Acme": ', meeting("Acme - Kickoff"), { allowFailure: true });
  assert.equal(r.status, 1, "a malformed config must not fall back to single-vault mode");
  assert.match(r.stderr, /present but unreadable/);
  assert.ok(r.stderr.includes(path.join(r.vaultRoot, "resources", "scripts", "granola.config.json")),
    `the message must name the file to fix: ${r.stderr}`);
});

test("a config that is valid JSON but not an object stops the run", () => {
  for (const [raw, got] of [["[]", /got an array/], ['"Acme"', /got string/], ["42", /got number/], ["null", /got null/]]) {
    const r = inVault(raw, meeting("Acme - Kickoff"), { allowFailure: true });
    assert.equal(r.status, 1, `config ${raw} was accepted`);
    assert.match(r.stderr, /must be a JSON object/);
    if (got) assert.match(r.stderr, got);
  }
});

test("an empty route table is single-vault mode: every meeting lands here, title and all", () => {
  const { result, stderr } = inVault({ route: {} }, meeting("Acme - Kickoff"));
  assert.ok(!result.unrouted && !result.skip, JSON.stringify(result));
  assert.equal(result.desc, "Acme - Kickoff");
  assert.equal(stderr, "");
});

test("route prefixes match case-insensitively, and the prefix is dropped from the filename", () => {
  const { result } = inVault({ route: { Acme: "." } }, meeting("ACME - Kickoff"));
  assert.ok(!result.unrouted && !result.skip, JSON.stringify(result));
  assert.equal(result.desc, "Kickoff");
});

test("a title that is only a routing prefix still gets a description", () => {
  const { result } = inVault({ route: { Acme: "." } }, meeting("Acme -"));
  assert.ok(!result.unrouted && !result.skip, JSON.stringify(result));
  assert.equal(result.desc, "Acme -");
});

test("with routes set, an untitled meeting is unrouted rather than filed anywhere", () => {
  for (const title of [null, ""]) {
    const { result } = inVault({ route: { Acme: "." } }, meeting(title));
    assert.deepEqual(result, { unrouted: true, prefix: "none" }, `title ${JSON.stringify(title)}`);
  }
});

test("the shipped config template is valid JSON and demonstrates the \".\" shape", () => {
  const tpl = JSON.parse(fs.readFileSync(path.join(__dirname, "granola.config.json.template"), "utf8"));
  assert.ok(Object.values(tpl.route).includes("."),
    'the template must show "." - it is the shape most adopters need and the one nobody guesses');
});


// --- the notes a sync writes ------------------------------------------------------------
// granola.js run for real in a throwaway vault with --write: only fetch is stubbed, and the
// token, ledger and notes are real files under a temporary PARAOS_HOME and triage/.

// Serves `docs` a page at a time as the request asks, and logs every request to a file so a test
// can see what was sent and with which token. See syncInVault for what the other variables do.
const FETCH_STUB = `
const fs = require("fs"), path = require("path");
const docs = JSON.parse(process.env.GRANOLA_TEST_DOCS);
const responses = JSON.parse(process.env.GRANOLA_TEST_RESPONSES);
let side = JSON.parse(process.env.GRANOLA_TEST_SIDE);
const block = process.env.GRANOLA_TEST_BLOCK;
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  const sent = init.body ? JSON.parse(init.body) : {};
  fs.appendFileSync(process.env.GRANOLA_TEST_LOG,
    JSON.stringify({ url, auth: (init.headers || {}).Authorization || null, body: sent }) + "\\n");
  if (side && url.endsWith("/get-document-panels")) {
    const f = path.join(process.env.PARAOS_HOME, "data", "granola", "synced.json");
    const l = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : {};
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.writeFileSync(f, JSON.stringify({ ...l, ...side })); side = null;
  }
  if (block && url.endsWith("/get-document-transcript")) fs.mkdirSync(block, { recursive: true });
  const hit = Object.keys(responses).find(k => url.endsWith(k));
  const status = hit ? (responses[hit].status || 200) : 200;
  const body = hit && "body" in responses[hit] ? responses[hit].body
    : url.endsWith("/get-documents") ? { docs: docs.slice(sent.offset, sent.offset + sent.limit) } : [];
  // \`raw\` serves a body that is not JSON, as a proxy's HTML error page is.
  if (hit && "raw" in responses[hit]) {
    const raw = responses[hit].raw;
    return { ok: status < 300, status, text: async () => raw, json: async () => JSON.parse(raw) };
  }
  return { ok: status < 300, status, text: async () => JSON.stringify(body), json: async () => body };
};
`;

// `ledgers` seeds the ledger by bucket, e.g. { cache: {...}, data: {...} }. `responses` overrides
// an endpoint by path suffix, e.g. { "/get-document-panels": { status: 429 } }. `sideEntry` is
// added to the data/ ledger by the stub on the first notes fetch, as a concurrent run would.
// `auth` replaces the stored secret. `block` names a file in triage/ that the stub turns into a
// folder once the note's transcript is fetched, so the note can no longer be put in place.
function syncInVault(docs, { tz = "UTC", notes = {}, ledgers = {}, responses = {}, sideEntry = null, expectStatus = 0,
                             argv = ["--write"], config = null, siblings = [], auth = null, block = null } = {}) {
  const parent = fs.mkdtempSync(path.join(TMP, "granola-"));
  TEMP_VAULTS.push(parent);
  const scripts = path.join(parent, "myvault", "resources", "scripts");
  const triage = path.join(parent, "myvault", "triage");
  fs.mkdirSync(scripts, { recursive: true });
  fs.mkdirSync(triage, { recursive: true });
  if (config) fs.writeFileSync(path.join(scripts, "granola.config.json"), JSON.stringify(config));
  for (const sib of siblings) fs.mkdirSync(path.join(parent, sib, "triage"), { recursive: true });
  for (const [name, body] of Object.entries(notes)) fs.writeFileSync(path.join(triage, name), body);

  const home = path.join(parent, "paraos");
  const secret = path.join(home, "secrets", "granola.json");
  fs.mkdirSync(path.dirname(secret), { recursive: true });
  // Owner-only, as granola-auth-init.js writes it, so a test can see a refresh keep that.
  fs.writeFileSync(secret, JSON.stringify(auth || { access_token: "test", access_expires: Math.floor(Date.now() / 1000) + 3600 }),
    { mode: 0o600 });
  const ledger = bucket => path.join(home, bucket, "granola", "synced.json");
  for (const [bucket, entries] of Object.entries(ledgers)) {
    fs.mkdirSync(path.dirname(ledger(bucket)), { recursive: true });
    fs.writeFileSync(ledger(bucket), JSON.stringify(entries));
  }
  const stub = path.join(parent, "fetch-stub.js");
  fs.writeFileSync(stub, FETCH_STUB);
  const runner = path.join(parent, "run.js");
  fs.writeFileSync(runner, granolaRunner(scripts, { asMain: true }));
  const log = path.join(parent, "requests.jsonl");

  const r = spawnSync(process.execPath, ["--require", stub, runner, ...argv], {
    encoding: "utf8",
    env: { ...process.env, TZ: tz, PARAOS_HOME: home, GRANOLA_TEST_DOCS: JSON.stringify(docs),
           GRANOLA_TEST_RESPONSES: JSON.stringify(responses), GRANOLA_TEST_SIDE: JSON.stringify(sideEntry),
           GRANOLA_TEST_LOG: log, GRANOLA_TEST_BLOCK: block ? path.join(triage, block) : "" },
  });
  assert.equal(r.status, expectStatus, `sync exited ${r.status}: ${r.stdout}${r.stderr}`);
  if (!expectStatus) assert.doesNotMatch(r.stdout + r.stderr, /\[x\]/, `sync failed: ${r.stdout}${r.stderr}`);
  const ls = dir => fs.existsSync(dir) ? fs.readdirSync(dir).sort() : [];
  return {
    stdout: r.stdout, stderr: r.stderr,
    files: ls(triage),
    filesIn: rel => ls(path.join(parent, rel)),
    read: (f, rel) => fs.readFileSync(path.join(rel ? path.join(parent, rel) : triage, f), "utf8"),
    ledger: bucket => fs.existsSync(ledger(bucket)) ? JSON.parse(fs.readFileSync(ledger(bucket), "utf8")) : null,
    secret: () => JSON.parse(fs.readFileSync(secret, "utf8")),
    secretMode: () => fs.statSync(secret).mode & 0o777,
    requests: fs.existsSync(log) ? fs.readFileSync(log, "utf8").trim().split("\n").map(l => JSON.parse(l)) : [],
  };
}

// Inside the default 30-day look-back, whenever the suite runs.
const DAY = new Date(Date.now() - 3 * 86400000).toISOString().slice(0, 10);
const NEXT_DAY = new Date(Date.parse(DAY) + 86400000).toISOString().slice(0, 10);
const compact = iso => iso.replace(/-/g, "");
const ID_A = "aaaaaaaa-1111-4111-8111-111111111111";
const ID_B = "bbbbbbbb-2222-4222-8222-222222222222";
const idsIn = (sync, files) => files.map(f => /^granola_id: (.*)$/m.exec(sync.read(f))[1]).sort();

test("a meeting just after local midnight is dated and named by its local day", () => {
  // 22:30 UTC is 00:30 the next day two hours east of UTC: the day the operator remembers.
  const sync = syncInVault([{ id: ID_A, title: "Kickoff", created_at: `${DAY}T22:30:00.000Z` }],
                           { tz: "Etc/GMT-2" });
  assert.deepEqual(sync.files, [`${compact(NEXT_DAY)} Kickoff.md`]);
  const note = sync.read(sync.files[0]);
  assert.match(note, new RegExp(`^date: ${NEXT_DAY}$`, "m"));
  assert.match(note, new RegExp(`^_${NEXT_DAY} 00:30_$`, "m"), "the time line must be local too");
});

test("two meetings sharing a date and title are both written", () => {
  const sync = syncInVault([
    { id: ID_A, title: "Standup", created_at: `${DAY}T09:00:00.000Z` },
    { id: ID_B, title: "Standup", created_at: `${DAY}T15:00:00.000Z` },
  ]);
  assert.equal(sync.files.length, 2, `the second meeting was dropped: ${sync.files}`);
  assert.deepEqual(idsIn(sync, sync.files), [ID_A, ID_B]);
  for (const f of sync.files) assert.match(f, TRIAGE_NAME);
});

test("notes still in triage are not written again, a suffixed one included", () => {
  // No ledger here: the existing-file check alone must recognise both notes by their id.
  const note = id => `---\ntitle: Standup\ngranola_id: ${id}\nsource: granola\n---\nkept\n`;
  const notes = { [`${compact(DAY)} Standup.md`]: note(ID_B), [`${compact(DAY)} Standup (aaaaaa).md`]: note(ID_A) };
  const sync = syncInVault([
    { id: ID_A, title: "Standup", created_at: `${DAY}T09:00:00.000Z` },
    { id: ID_B, title: "Standup", created_at: `${DAY}T15:00:00.000Z` },
  ], { notes });
  assert.deepEqual(sync.files, Object.keys(notes).sort());
  for (const f of sync.files) assert.match(sync.read(f), /kept/, `${f} was overwritten`);
});

test("a hand-written note that shares the name is kept, and the meeting takes a suffixed name", () => {
  // No granola_id in it, so it cannot be this meeting's note.
  const name = `${compact(DAY)} Standup.md`;
  const sync = syncInVault([{ id: ID_A, title: "Standup", created_at: `${DAY}T09:00:00.000Z` }],
                           { notes: { [name]: "# Standup\nmy own notes\n" } });
  assert.deepEqual(sync.files, [`${compact(DAY)} Standup (aaaaaa).md`, name]);
  assert.equal(sync.read(name), "# Standup\nmy own notes\n");
});

test("the ledger is written under data/, and a ledger left in cache/ is still honoured", () => {
  // Meeting A was filed out of triage/ long ago: only the cache/ ledger remembers it.
  const sync = syncInVault([
    { id: ID_A, title: "Filed", created_at: `${DAY}T09:00:00.000Z` },
    { id: ID_B, title: "Fresh", created_at: `${DAY}T15:00:00.000Z` },
  ], { ledgers: { cache: { [ID_A]: "filed elsewhere" } } });
  assert.deepEqual(sync.files, [`${compact(DAY)} Fresh.md`], "a meeting in the old ledger was re-imported");
  assert.deepEqual(Object.keys(sync.ledger("data") || {}).sort(), [ID_A, ID_B]);
  assert.deepEqual(sync.ledger("cache"), { [ID_A]: "filed elsewhere" }, "the old ledger is read, never written");
});

test("a meeting in either ledger is skipped when both exist", () => {
  // An older copy in another vault on this machine may still be writing the cache/ ledger.
  const sync = syncInVault([
    { id: ID_A, title: "Standup", created_at: `${DAY}T09:00:00.000Z` },
    { id: ID_B, title: "Review", created_at: `${DAY}T15:00:00.000Z` },
  ], { ledgers: { cache: { [ID_A]: "filed elsewhere" }, data: { [ID_B]: "filed elsewhere" } } });
  assert.deepEqual(sync.files, []);
});

// A Summary panel, for meetings recent enough that a note without one would be held.
const PANELS = { "/get-document-panels": { body: [{ title: "Summary", content: "Agreed the plan." }] } };
const NOW = new Date(Date.now() - 3600000).toISOString();

test("a title with a colon, or none at all, still makes valid front-matter", () => {
  const sync = syncInVault([
    { id: ID_A, title: "Acme: Q3 plan", created_at: `${DAY}T09:00:00.000Z`, people: [{ name: "Ann: PM" }] },
    { id: ID_B, created_at: `${DAY}T15:00:00.000Z` },
  ]);
  const colon = sync.read(sync.files.find(f => f.includes("Acme")));
  assert.match(colon, /^title: "Acme: Q3 plan"$/m);
  assert.match(colon, /^attendees: "Ann: PM"$/m);
  assert.match(colon, /^# Acme: Q3 plan$/m);
  const untitled = sync.read(sync.files.find(f => f.includes("untitled")));
  assert.match(untitled, /^title: "\(untitled\)"$/m);
  assert.doesNotMatch(untitled, /undefined/);
});

for (const [endpoint, status] of [["/get-document-panels", 429], ["/get-document-transcript", 503], ["/get-document-panels", 401]]) {
  test(`a ${status} from ${endpoint} writes and ledgers nothing, so the next run retries`, () => {
    const sync = syncInVault([{ id: ID_A, title: "Kickoff", created_at: `${DAY}T09:00:00.000Z` }],
                             { responses: { [endpoint]: { status, body: { error: "nope" } } } });
    assert.deepEqual(sync.files, []);
    assert.deepEqual(sync.ledger("data"), null);
    assert.match(sync.stdout, /FAILED/);
    assert.match(sync.stdout, /failed: 1/);
  });
}

test("a failed listing exits non-zero instead of reporting zero meetings", () => {
  const sync = syncInVault([{ id: ID_A, title: "Kickoff", created_at: `${DAY}T09:00:00.000Z` }],
                           { responses: { "/get-documents": { status: 500 } }, expectStatus: 1 });
  assert.deepEqual(sync.files, []);
  assert.match(sync.stderr, /could not list/);
});

test("a full page cap warns that older meetings were not listed", () => {
  const docs = Array.from({ length: 100 }, (_, i) => ({ id: `id-${i}`, title: `M${i}`, created_at: NOW, deleted_at: "gone" }));
  const sync = syncInVault(docs, { responses: { "/get-documents": { body: { docs } } } });
  assert.match(sync.stderr, /listing stopped at 500/);
});

test("a recent meeting whose notes are not generated yet is held, not ledgered", () => {
  const sync = syncInVault([{ id: ID_A, title: "Just now", created_at: NOW }]);
  assert.deepEqual(sync.files, []);
  assert.equal(sync.ledger("data"), null);
  assert.match(sync.stdout, /HELD/);
});

test("a recent meeting with notes is written", () => {
  const sync = syncInVault([{ id: ID_A, title: "Just now", created_at: NOW }], { responses: PANELS });
  assert.equal(sync.files.length, 1);
  assert.match(sync.read(sync.files[0]), /Agreed the plan\./);
});

test("an older meeting without notes is written rather than held forever", () => {
  const sync = syncInVault([{ id: ID_A, title: "Old", created_at: `${DAY}T09:00:00.000Z` }]);
  assert.equal(sync.files.length, 1);
  assert.match(sync.read(sync.files[0]), /no enhanced notes available/);
});

test("an entry another run ledgers mid-sync is kept, not overwritten", () => {
  const sync = syncInVault([{ id: ID_A, title: "Kickoff", created_at: `${DAY}T09:00:00.000Z` }],
                           { sideEntry: { [ID_B]: "written by another vault's run" } });
  assert.deepEqual(Object.keys(sync.ledger("data")).sort(), [ID_A, ID_B]);
});

test("the module loads without USERPROFILE, so the suite runs off Windows", () => {
  const env = { ...process.env };
  delete env.USERPROFILE; delete env.PARAOS_HOME;
  const r = spawnSync(process.execPath, ["-e", `require(${JSON.stringify(path.join(__dirname, "granola.js"))})`],
                      { encoding: "utf8", env });
  assert.equal(r.status, 0, r.stderr);
});

test("no temp file is left beside a written note or the ledger", () => {
  const sync = syncInVault([{ id: ID_A, title: "Kickoff", created_at: `${DAY}T09:00:00.000Z` }]);
  assert.ok(sync.files.every(f => !f.endsWith(".tmp")), sync.files.join(", "));
});

test("a note that cannot be moved into place leaves no temp file, is not ledgered, and fails the run", () => {
  // Something takes the note's name while the sync is fetching it, so the final rename fails.
  const name = `${compact(DAY)} Kickoff.md`;
  const sync = syncInVault([{ id: ID_A, title: "Kickoff", created_at: `${DAY}T09:00:00.000Z` }],
                           { block: name, expectStatus: 1 });
  assert.deepEqual(sync.files, [name], "only the folder that blocked the note may be there");
  assert.equal(sync.ledger("data"), null, "a note that was never written must not be ledgered");
  assert.match(sync.stderr, /\[x\]/);
});

const ID_C = "cccccccc-3333-4333-8333-333333333333";
const OLD_MEETING = [{ id: ID_A, title: "Kickoff", created_at: `${DAY}T09:00:00.000Z` }];
const daysAgo = n => new Date(Date.now() - n * 86400000).toISOString();
const listed = sync => sync.requests.filter(q => q.url.endsWith("/get-documents")).map(q => q.body.offset);


// --- listing and the dry run ------------------------------------------------------------

test("a dry run reports what it would write and writes nothing", () => {
  const sync = syncInVault(OLD_MEETING, { argv: [] });
  assert.deepEqual(sync.files, []);
  assert.equal(sync.ledger("data"), null);
  assert.match(sync.stdout, /^DRY RUN/m);
  assert.ok(sync.stdout.includes(`-> myvault/triage/${compact(DAY)} Kickoff.md`), sync.stdout);
  assert.match(sync.stdout, /would write: 1/);
  assert.match(sync.stdout, /Re-run with --write/);
});

test("--days narrows the look-back window", () => {
  const docs = [...OLD_MEETING, { id: ID_B, title: "Last week", created_at: daysAgo(8) }];
  const sync = syncInVault(docs, { argv: ["--write", "--days", "5"] });
  assert.deepEqual(sync.files, [`${compact(DAY)} Kickoff.md`]);
  assert.match(sync.stdout, /last 5 days . 1 meetings/);
  assert.equal(syncInVault(docs).files.length, 2, "the default 30-day window takes both");
});

test("a meeting deleted in Granola is not written", () => {
  const sync = syncInVault([{ ...OLD_MEETING[0], deleted_at: daysAgo(1) }]);
  assert.deepEqual(sync.files, []);
  assert.match(sync.stdout, / 0 meetings/);
});

test("listing pages on past the first hundred until a short page", () => {
  // The first hundred were deleted in Granola: listed, then dropped, which keeps the run small.
  const gone = Array.from({ length: 100 }, (_, i) => ({ id: `gone-${i}`, title: `M${i}`,
                                                       created_at: `${DAY}T10:00:00.000Z`, deleted_at: "x" }));
  const sync = syncInVault([...gone, { id: ID_A, title: "Page two", created_at: `${DAY}T09:00:00.000Z` }]);
  assert.deepEqual(listed(sync), [0, 100]);
  assert.deepEqual(sync.files, [`${compact(DAY)} Page two.md`]);
  assert.doesNotMatch(sync.stderr, /listing stopped/);
});

test("listing stops at a page that already reaches past the look-back window", () => {
  const old = Array.from({ length: 99 }, (_, i) => ({ id: `old-${i}`, title: `Old ${i}`, created_at: daysAgo(40) }));
  const sync = syncInVault([...OLD_MEETING, ...old]);
  assert.deepEqual(listed(sync), [0], "a second page can only hold older meetings");
  assert.deepEqual(sync.files, [`${compact(DAY)} Kickoff.md`], "meetings outside the window are not written");
  assert.doesNotMatch(sync.stderr, /listing stopped/);
});


// --- what a note is built from ----------------------------------------------------------

test("the Summary panel is picked by title, and its headings nest under ## Summary", () => {
  const summary = doc({ type: "heading", attrs: { level: 1 }, content: [text("Decisions")] }, para(text("Ship it")));
  const sync = syncInVault(OLD_MEETING, { responses: { "/get-document-panels": { body: { panels: [
    { title: "Action items", content: "Not the summary" },
    { title: "Meeting summary", content: summary },
  ] } } } });
  const note = sync.read(sync.files[0]);
  assert.match(note, /^## Summary\n### Decisions\nShip it$/m);
  assert.doesNotMatch(note, /Not the summary/);
});

test("with no Summary panel the first is used, its empty content falling back in turn", () => {
  const sync = syncInVault(OLD_MEETING, { responses: { "/get-document-panels": { body: { document_panels: [
    { content: null, original_content: "  ", content_json: doc(para(text("Agreed the budget."))) },
    { title: "Other", content: "Not this one" },
  ] } } } });
  const note = sync.read(sync.files[0]);
  assert.match(note, /^## Summary\nAgreed the budget\.$/m);
  assert.doesNotMatch(note, /Not this one/);
});

test("a transcript wrapped in an object is rendered speaker by speaker", () => {
  const sync = syncInVault(OLD_MEETING, { responses: { "/get-document-transcript": { body: { transcript: [
    { source: "microphone", text: "Shall we start?" },
    { detected_speaker_name: "Ann", text: "Yes." },
  ] } } } });
  assert.match(sync.read(sync.files[0]), /^## Transcript\n\*\*Me:\*\* Shall we start\?\n\n\*\*Ann:\*\* Yes\.$/m);
});

test("attendees are listed by name or email, and a meeting with none has no attendees line", () => {
  const sync = syncInVault([
    { ...OLD_MEETING[0], people: { a: { name: "Ann" }, b: { email: "bob@example.com" }, c: null, d: {} } },
    { id: ID_B, title: "Solo", created_at: `${DAY}T15:00:00.000Z` },
  ]);
  assert.match(sync.read(`${compact(DAY)} Kickoff.md`), /^attendees: "Ann, bob@example\.com"$/m);
  assert.doesNotMatch(sync.read(`${compact(DAY)} Solo.md`), /^attendees:/m);
});


// --- multi-vault sync -------------------------------------------------------------------

const ROUTED = [
  { id: ID_A, title: "Client - Kickoff", created_at: `${DAY}T09:00:00.000Z` },
  { id: ID_B, title: "ACME - Steering", created_at: `${DAY}T10:00:00.000Z` },
  { id: ID_C, title: "Dentist", created_at: `${DAY}T11:00:00.000Z` },
];
const ROUTING = { config: { route: { Client: ".", Acme: "acme-client" } }, siblings: ["acme-client"] };

test("by default a routed copy writes only its own vault's meetings, and counts the rest", () => {
  const sync = syncInVault(ROUTED, ROUTING);
  assert.deepEqual(sync.files, [`${compact(DAY)} Kickoff.md`]);
  assert.deepEqual(sync.filesIn(path.join("acme-client", "triage")), []);
  assert.match(sync.stdout, /routing -> myvault/);
  assert.match(sync.stdout, /Dentist.*UNROUTED \(prefix: none\)/);
  assert.match(sync.stdout, /wrote: 1 .*unrouted: 1 . other vaults: 1/);
});

test("--all writes each routed meeting into its own vault", () => {
  const sync = syncInVault(ROUTED, { ...ROUTING, argv: ["--write", "--all"] });
  assert.deepEqual(sync.files, [`${compact(DAY)} Kickoff.md`]);
  const acme = path.join("acme-client", "triage");
  assert.deepEqual(sync.filesIn(acme), [`${compact(DAY)} Steering.md`]);
  assert.match(sync.read(`${compact(DAY)} Steering.md`, acme), /^title: "ACME - Steering"$/m,
    "the note keeps the full title; only the filename drops the prefix");
  assert.match(sync.stdout, /routing all vaults/);
  assert.match(sync.stdout, /wrote: 2 .*unrouted: 1 . other vaults: 0/);
});

test("meetings_subdir sends notes to that folder instead of triage/", () => {
  const sync = syncInVault(OLD_MEETING, { config: { meetings_subdir: "inbox" } });
  assert.deepEqual(sync.files, []);
  assert.deepEqual(sync.filesIn(path.join("myvault", "inbox")), [`${compact(DAY)} Kickoff.md`]);
  assert.ok(sync.stdout.includes("-> myvault/inbox/"), sync.stdout);
});


// --- token refresh ----------------------------------------------------------------------
// The secret holds a WorkOS access token and a single-use refresh token. Only the access
// token's payload `exp` is ever read, so these tokens carry nothing else.

const NOW_S = Math.floor(Date.now() / 1000);
const jwt = claims => `h.${Buffer.from(JSON.stringify(claims)).toString("base64")}.s`;
const REFRESHED = jwt({ exp: NOW_S + 7200 });
const EXPIRING = { client_id: "client_1", refresh_token: "r1", access_token: "stale", access_expires: NOW_S + 10 };
const refreshGives = body => ({ "/authenticate": { body: { access_token: REFRESHED, ...body } } });
const refreshed = sync => sync.requests.some(q => q.url.endsWith("/authenticate"));

test("a live token is used as it is, with no refresh", () => {
  const sync = syncInVault(OLD_MEETING);
  assert.equal(refreshed(sync), false);
  assert.ok(sync.requests.every(q => q.auth === "Bearer test"), JSON.stringify(sync.requests));
});

test("a token expiring within 30 seconds is refreshed first, and the rotated refresh token saved", () => {
  const sync = syncInVault(OLD_MEETING, { auth: EXPIRING, responses: refreshGives({ refresh_token: "r2" }) });
  const [first, ...rest] = sync.requests;
  assert.match(first.url, /\/authenticate$/);
  assert.deepEqual(first.body, { grant_type: "refresh_token", client_id: "client_1", refresh_token: "r1" });
  assert.ok(rest.length && rest.every(q => q.auth === `Bearer ${REFRESHED}`), "every Granola call must use the new token");
  assert.deepEqual(sync.secret(),
    { client_id: "client_1", refresh_token: "r2", access_token: REFRESHED, access_expires: NOW_S + 7200 });
  assert.equal(sync.files.length, 1);
});

test("with no stored expiry, the access token's own exp decides whether to refresh", () => {
  for (const [exp, expected] of [[NOW_S + 3600, false], [NOW_S - 60, true]]) {
    const sync = syncInVault(OLD_MEETING, { auth: { client_id: "c", refresh_token: "r1", access_token: jwt({ exp }) },
                                            responses: refreshGives({}) });
    assert.equal(refreshed(sync), expected, `a token expiring ${exp - NOW_S}s from now`);
  }
});

test("a refresh that returns no new refresh token keeps the old one", () => {
  const sync = syncInVault(OLD_MEETING, { auth: EXPIRING, responses: refreshGives({}) });
  assert.equal(sync.secret().refresh_token, "r1");
  assert.equal(sync.secret().access_token, REFRESHED);
});

test("a failed refresh stops the run before anything is listed, and leaves the secret alone", () => {
  const sync = syncInVault(OLD_MEETING, { auth: EXPIRING, expectStatus: 1,
    responses: { "/authenticate": { status: 401, body: { error: "invalid_grant" } } } });
  assert.match(sync.stderr, /refresh failed 401/);
  assert.deepEqual(sync.secret(), EXPIRING);
  assert.deepEqual(listed(sync), []);
  assert.deepEqual(sync.files, []);
});

test("a refresh refused with a body that is not JSON still reports its status", () => {
  // A proxy's HTML 502 used to surface as a JSON parse error, and the status was lost.
  const sync = syncInVault(OLD_MEETING, { auth: EXPIRING, expectStatus: 1,
    responses: { "/authenticate": { status: 502, raw: "<html>Bad gateway</html>" } } });
  assert.match(sync.stderr, /refresh failed 502/);
  assert.deepEqual(sync.secret(), EXPIRING);
});

test("--days that is not a whole number of days stops the run before anything is fetched", () => {
  for (const bad of [["--days", "abc"], ["--days"], ["--days", "0"], ["--days", "2.5"]]) {
    const sync = syncInVault(OLD_MEETING, { argv: bad, expectStatus: 1 });
    assert.match(sync.stderr, /--days/, `${bad.join(" ")}: ${sync.stderr}`);
    assert.deepEqual(sync.requests, [], `${bad.join(" ")} must not reach the API`);
  }
});

test("a dry run still saves a rotated refresh token, since the old one is already spent", () => {
  const sync = syncInVault(OLD_MEETING, { auth: EXPIRING, argv: [], responses: refreshGives({ refresh_token: "r2" }) });
  assert.deepEqual(sync.files, []);
  assert.equal(sync.secret().refresh_token, "r2");
});

test("a refreshed secret stays readable by its owner only",
     { skip: process.platform === "win32" && "Windows has no POSIX file modes" }, () => {
  const sync = syncInVault(OLD_MEETING, { auth: EXPIRING, responses: refreshGives({ refresh_token: "r2" }) });
  assert.equal(sync.secret().refresh_token, "r2");
  assert.equal(sync.secretMode().toString(8), "600");
});
