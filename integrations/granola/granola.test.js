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

const SOURCE = require("fs").readFileSync(path.join(__dirname, "granola.js"), "utf8");

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
