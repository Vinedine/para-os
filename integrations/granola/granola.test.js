// Unit tests for granola.js. Pure functions only - no Granola API, no token, no writes.
// Uses node:test, built into Node 18+, which this integration already requires. Nothing to install.
//
//   node --test integrations/granola/granola.test.js
//
// Scope: the ProseMirror-to-Markdown conversion, transcript grouping, filename shaping, and
// single-vault routing. The API calls and the DPAPI token extraction are deliberately not
// covered - mocking either would assert that the mock behaves.

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
process.on("exit", () => {
  for (const d of TEMP_VAULTS) { try { fs.rmSync(d, { recursive: true, force: true }); } catch {} }
});

function inVault(config, expr, { vaultName = "myvault", siblings = [], argv = [], allowFailure = false } = {}) {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), "granola-"));
  TEMP_VAULTS.push(parent);
  const scripts = path.join(parent, vaultName, "resources", "scripts");
  fs.mkdirSync(scripts, { recursive: true });
  fs.copyFileSync(path.join(__dirname, "granola.js"), path.join(scripts, "granola.js"));
  if (config) fs.writeFileSync(path.join(scripts, "granola.config.json"), JSON.stringify(config));
  for (const sib of siblings) fs.mkdirSync(path.join(parent, sib, "triage"), { recursive: true });

  const runner = path.join(parent, "run.js");
  fs.writeFileSync(runner,
    `const { resolveDest } = require(${JSON.stringify(path.join(scripts, "granola.js"))});\n`
    + `console.log("<<" + JSON.stringify(${expr}) + ">>");\n`);
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

test("the shipped config template is valid JSON and demonstrates the \".\" shape", () => {
  const tpl = JSON.parse(fs.readFileSync(path.join(__dirname, "granola.config.json.template"), "utf8"));
  assert.ok(Object.values(tpl.route).includes("."),
    'the template must show "." - it is the shape most adopters need and the one nobody guesses');
});
