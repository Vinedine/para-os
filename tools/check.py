#!/usr/bin/env python3
"""Contract checks for the para-os repo. No dependencies; run it before shipping a revision.

    python3 tools/check.py            # report and exit non-zero on any failure
    python3 tools/check.py -v         # also list every check that passed

What it enforces, and why each one is machinery rather than prose:

  Integration markers   The versioning scheme in integrations/README.md only works if every
                        shipped script carries `para-os-integration: <name> <revision>` and
                        the folder's revision matches its row in the Available table.
                        /para-upgrade compares an installed copy against that marker, so a
                        marker that disagrees with the table sends the wrong answer to every
                        vault, silently.

  Template revisions    base/, each flavor skeleton, and each example vault all stamp a
                        `<!-- para-os-template: -->` marker. They must agree with the newest
                        CHANGELOG entry: a flavor left a revision behind means /para-upgrade
                        reads a stale master and reports "nothing to do" on a vault that
                        genuinely needs migrating.

  Dashes                CLAUDE.md makes this a hard rule for shipped prose, and it is the one
                        style rule a reader notices immediately.

  Colocated tests       Each integration's own suite, run in place: `test_*.py` and `*.test.js`
                        next to the script they cover. Shipping a revision is one command, not
                        three remembered ones. A suite whose runtime is missing FAILS rather
                        than skipping: an integration nobody could verify must not report as a
                        clean bill of health.

  Flavor tracking       Each flavor skeleton file is a derived copy of a base file, shipped
                        whole rather than as a patch. Content cannot be compared - the deltas
                        are the point - so FLAVOR_TRACKING stamps the digest of each base file
                        and this fails when base moves, until someone has reconciled the two.

  Vendor validator      `claude plugin validate` over the same folder, which is a linter and
                        not a distribution step: no manifest, no marketplace, nothing
                        published. It enforces whatever the tool currently requires of a
                        SKILL.md, which moves release to release - the part the checks above
                        cannot keep up with by hand.

  Skill contract        Every skill master keeps its frontmatter contract (name matching its
                        folder, a description, allowed-tools, arg-hint), a `## Strict rules`
                        block, a spine under the line cap, and references that resolve both
                        ways. The spine cap is the load-bearing one: a SKILL.md body loads on
                        every invoke, so a skill that regrows charges every run for procedure
                        it may never reach - which is the 1106 lines the 2026.08.03 split
                        removed, and nothing else stops them coming back.

Deliberately NOT checked: anything requiring judgement (privacy, bloat, whether a rule earns
its words). Those are review, not a script.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # repo root; this file lives in tools/
REVISION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
SCRIPT_SUFFIXES = {".py", ".js", ".ps1", ".sh"}

failures = []
passes = []


def ok(msg):
    passes.append(msg)


def bad(msg):
    failures.append(msg)


def rel(p):
    return p.relative_to(ROOT).as_posix()


def console_safe(s):
    """Drop what a Windows console cannot encode.

    The vendor validator reports with box-drawing and warning glyphs. Quoting them back
    verbatim in a failure message kills the whole run on a cp1252 console: the first FAIL
    line prints, the UnicodeEncodeError lands, and the summary never appears - so a report
    whose job is making failures visible would hide them behind a crash.
    """
    return s.encode("ascii", "replace").decode("ascii")


def run_captured(cmd, timeout):
    """Run a command the way every subprocess-backed check here needs: from ROOT, stdout and
    stderr combined into one string. Raises FileNotFoundError / subprocess.TimeoutExpired,
    same as a bare subprocess.run - callers still handle those per command."""
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, f"{r.stdout or ''}\n{r.stderr or ''}".strip()


def tail(text, n=15, transform=str):
    return "\n".join(f"        {transform(ln)}" for ln in text.splitlines()[-n:])


def is_test_file(p):
    return p.name.startswith("test_") or ".test." in p.name


# --- integrations ----------------------------------------------------------------------

def integration_dirs():
    return sorted(d for d in (ROOT / "integrations").iterdir() if d.is_dir())


def available_table():
    """{folder name: version} from the Available table in integrations/README.md."""
    text = (ROOT / "integrations" / "README.md").read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*\[`([^`/]+)/`\]\([^)]+\)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def check_config_naming(d, scripts):
    """One name for a vault config, across every integration: `<folder>.config.json`.

    The convention is stated in base/resources/scripts/README.md, and it is load-bearing in
    two directions. `<folder>` rather than the script's own basename, because /para-upgrade
    resolves an installed copy by the integration name in its marker, so that is the name a
    reader already has. And `.config.json` rather than the bare `<name>.json`, which is the
    machine-global secret: two files sharing one name across opposite trust zones is how a
    credential ends up inside a folder that syncs. Left to per-integration taste this drifted
    three ways in one revision, which is why it is a check and not a paragraph.
    """
    want = f"{d.name}.config.json"
    referenced = {m for p in scripts
                  for m in re.findall(r"[A-Za-z0-9_.-]+\.config\.json",
                                      p.read_text(encoding="utf-8", errors="ignore"))}
    for wrong in sorted(referenced - {want}):
        bad(f"integrations/{d.name}/ reads a vault config named `{wrong}`; the convention is "
            f"`{want}` (named for the integration, never for the script or the secret)")
    for tmpl in d.glob("*.config.json.template"):
        if tmpl.name != f"{want}.template":
            bad(f"{rel(tmpl)}: template should be `{want}.template`")


def check_integrations():
    table = available_table()
    if not table:
        bad("integrations/README.md: could not parse any row from the Available table")
        return
    folders = integration_dirs()

    for extra in sorted(set(table) - {d.name for d in folders}):
        bad(f"integrations/README.md lists `{extra}/` but no such folder exists")
    for missing in sorted({d.name for d in folders} - set(table)):
        bad(f"integrations/{missing}/ has no row in the Available table")

    for d in folders:
        scripts = [p for p in sorted(d.iterdir())
                   if p.suffix in SCRIPT_SUFFIXES and not is_test_file(p)]
        if not (d / "README.md").exists():
            bad(f"integrations/{d.name}/ has no README.md")
        if not scripts:
            bad(f"integrations/{d.name}/ ships no script")
            continue
        check_config_naming(d, scripts)

        revisions = {}
        for p in scripts:
            head = "\n".join(p.read_text(encoding="utf-8", errors="ignore").splitlines()[:10])
            m = re.search(r"para-os-integration:\s*(\S+)\s+(\S+)", head)
            if not m:
                bad(f"{rel(p)}: no `para-os-integration:` marker in the first 10 lines")
                continue
            name, revision = m.group(1), m.group(2)
            if name != d.name:
                bad(f"{rel(p)}: marker says integration `{name}`, folder is `{d.name}`")
            if not REVISION.match(revision):
                bad(f"{rel(p)}: revision `{revision}` is not YYYY.MM.NN")
            revisions[p] = revision

        distinct = set(revisions.values())
        if len(distinct) > 1:
            listed = ", ".join(f"{p.name}={v}" for p, v in sorted(revisions.items()))
            bad(f"integrations/{d.name}/: scripts disagree on the revision ({listed}). "
                f"The version is per integration, not per file.")
        elif distinct:
            got = distinct.pop()
            want = table.get(d.name)
            if want and got != want:
                bad(f"integrations/{d.name}/: scripts say {got}, "
                    f"Available table says {want}")
            else:
                ok(f"integrations/{d.name}/ at {got}, {len(revisions)} script(s) stamped")


# --- template revisions ----------------------------------------------------------------

def changelog_revisions():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.findall(r"^##\s+(\d{4}\.\d{2}\.\d{2})\s*$", text, re.M)


def template_files():
    files = [ROOT / "base" / "CLAUDE.md.template"]
    files += sorted((ROOT / "flavors").glob("*/skeleton/CLAUDE.md.template"))
    files += sorted(p / "CLAUDE.md" for p in (ROOT / "examples").iterdir()
                    if p.is_dir() and (p / "CLAUDE.md").exists())
    return [f for f in files if f.exists()]


def check_template_revisions():
    revisions = changelog_revisions()
    if not revisions:
        bad("CHANGELOG.md: no `## YYYY.MM.NN` revision headings found")
        return
    if revisions != sorted(revisions, reverse=True):
        bad(f"CHANGELOG.md: revisions are not newest-first ({', '.join(revisions)})")
    if len(set(revisions)) != len(revisions):
        bad("CHANGELOG.md: a revision heading appears twice")
    current = revisions[0]

    for f in template_files():
        m = re.search(r"<!--\s*para-os-template:\s*(\S+)\s*-->",
                      f.read_text(encoding="utf-8", errors="ignore"))
        if not m:
            bad(f"{rel(f)}: no `<!-- para-os-template: -->` marker")
        elif m.group(1) != current:
            bad(f"{rel(f)}: stamped {m.group(1)}, newest changelog revision is {current}")
        else:
            ok(f"{rel(f)} at {current}")


TEMPLATE_MAX_LINES = 120   # a starting point; worst today is base at 117
FINISHED_MAX_LINES = 200   # a populated vault's own CLAUDE.md, at the adherence target


def check_template_size():
    """A vault starts at a template's length and adds its own sections on top.

    The adherence target for a CLAUDE.md is 200 lines. A **template** - base, and every flavor
    skeleton - becomes an adopter's vault CLAUDE.md and is then extended, so it has to leave
    room below that target for what the vault adds. A **finished** vault CLAUDE.md, which is
    what the example is, is held to the target itself: an example over 200 lines contradicts
    the rule it ships. Rules only: procedure belongs to the script or skill that runs it,
    rationale to git history.
    """
    for f in template_files():
        cap = TEMPLATE_MAX_LINES if f.suffix == ".template" else FINISHED_MAX_LINES
        n = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
        if n > cap:
            bad(f"{rel(f)}: {n} lines, cap is {cap}. Cut procedure and rationale, not rules.")
        else:
            ok(f"{rel(f)} at {n} lines (cap {cap})")


# --- style -----------------------------------------------------------------------------

DASHES = ("\u2014", "\u2013")  # em, en: escaped so this file passes its own check.
FENCE = re.compile(r"^\s*```")
CODE_SPAN = re.compile(r"`[^`]*`")


WALK_SKIP_DIRS = {".git", "node_modules", "__pycache__"}
PROSE_SUFFIXES = {".md", ".template", ".py", ".js", ".json", ".ps1"}


def prose_files():
    """Every file in the repo this script may read, with the noise pruned at descent.

    `.git` alone holds roughly eight times as many files as the repo does, so an rglob that
    enumerates it and filters afterwards spends most of its stats on objects no check reads.
    """
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in WALK_SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix in PROSE_SUFFIXES:
                yield p


def check_dashes():
    """The rule is about *prose*, so code is out of scope: a regex that matches an en dash in
    someone's calendar entry, inside a regex character class, is parsing data,
    not writing prose."""
    hits = []
    for p in prose_files():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        in_fence = False
        for n, line in enumerate(text.splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            prose = CODE_SPAN.sub("", line)
            if any(d in prose for d in DASHES):
                hits.append(f"{rel(p)}:{n}")
    if hits:
        shown = ", ".join(hits[:8]) + (f" (+{len(hits) - 8} more)" if len(hits) > 8 else "")
        bad(f"em/en dash in shipped text: {shown}")
    else:
        ok("no em/en dashes in shipped text")


# --- colocated test suites --------------------------------------------------------------

# sys.executable, not "python": the interpreter running this file is known to exist, which
# `python` on a Windows PATH is not. Node has no such trick, so a missing `node` is reported.
RUNNERS = {".py": lambda p: [sys.executable, str(p)],
           ".js": lambda p: ["node", "--test", str(p)]}

# unittest writes "Ran 39 tests" to stderr; node --test writes "pass 35" to stdout. The count
# is reported so a suite that quietly stopped covering anything is visible at a glance. It is
# not a guarantee: `node --test <file>` scores a file with no tests in it as one passing test,
# so only a runner that reports a real 0 (unittest does, and exits non-zero too) is caught.
COUNTS = (re.compile(r"^Ran (\d+) tests?", re.M), re.compile(r"^\D*pass (\d+)$", re.M))


def check_tests():
    suites = [p for d in integration_dirs() for p in sorted(d.iterdir())
              if p.suffix in RUNNERS and is_test_file(p)]
    for d in integration_dirs():
        if not any(p.parent == d for p in suites):
            bad(f"integrations/{d.name}/ ships no test suite")

    for p in suites:
        cmd = RUNNERS[p.suffix](p)
        try:
            # utf-8 explicitly: node --test emits box-drawing and ℹ, which a cp1252 console
            # default cannot decode, and a UnicodeDecodeError here would read as a test failure.
            returncode, combined = run_captured(cmd, timeout=300)
        except FileNotFoundError:
            bad(f"{rel(p)}: cannot run, `{cmd[0]}` is not on PATH. A suite that could not "
                f"run has not passed.")
            continue
        except subprocess.TimeoutExpired:
            bad(f"{rel(p)}: timed out after 300s")
            continue

        count = next((int(m.group(1)) for m in (c.search(combined) for c in COUNTS) if m), None)
        if returncode != 0:
            bad(f"{rel(p)}: suite failed (exit {returncode})\n{tail(combined)}")
        elif count == 0:
            bad(f"{rel(p)}: ran 0 tests - discovery found nothing to run")
        elif count is None:
            ok(f"{rel(p)}: passed, test count not reported")
        else:
            ok(f"{rel(p)}: {count} test(s) passed")


# --- skill masters ---------------------------------------------------------------------

SKILLS_DIR = ROOT / "base" / ".claude" / "skills"
MODULE_DIRS = (ROOT / "multi-vault",)   # optional modules that ship a skill of their own
SKILL_FRONTMATTER = ("name", "description", "allowed-tools", "arg-hint")
SPINE_MAX_LINES = 130      # current worst is 113; the cap catches regrowth, not today's shape
DESCRIPTION_MAX_CHARS = 600


def skill_dirs(parent):
    """The skill folders directly under `parent` - a folder holding a SKILL.md is a skill."""
    return sorted(d for d in parent.iterdir() if (d / "SKILL.md").exists())


def check_skills():
    if not SKILLS_DIR.is_dir():
        bad("base/.claude/skills/ is missing")
        return

    masters = skill_dirs(SKILLS_DIR)
    if not masters:
        bad("base/.claude/skills/ ships no SKILL.md")
        return

    # An optional module ships a skill too, and it is the likeliest one to rot: it sits outside
    # base/, so without this nothing in this file ever looks at it. Same contract, same caps -
    # a skill an adopter installs beside the bundled ones is held to what they are held to.
    # A listed module that is not there FAILS rather than being skipped: a rename would
    # otherwise degrade to a clean pass over a skill nothing looked at.
    # The vendor validator below is deliberately NOT pointed here: it picks its mode from the
    # path, and a skills folder outside .claude/ is read as a plugin directory and fails for
    # having no manifest. That is a tool constraint, not a reason to leave the module unchecked.
    for module in MODULE_DIRS:
        if module.is_dir():
            masters += skill_dirs(module)
        else:
            bad(f"{rel(module)}/ is in MODULE_DIRS but does not exist. Drop the entry, or "
                f"restore the folder - as it stands its skill is checked by nothing.")

    for d in masters:
        sk = d / "SKILL.md"
        text = sk.read_text(encoding="utf-8")
        before = len(failures)

        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            bad(f"{rel(sk)}: no YAML frontmatter")
            continue
        fm = m.group(1)
        fields = {k: v.strip() for k, v in re.findall(r"^([\w-]+):\s*(.*)$", fm, re.M)}

        for key in SKILL_FRONTMATTER:
            if key not in fields:
                bad(f"{rel(sk)}: frontmatter is missing `{key}:`")

        name = fields.get("name")
        if name and name != d.name:
            bad(f"{rel(sk)}: frontmatter name `{name}` does not match folder `{d.name}`. "
                f"The frontmatter name is what the skill is invoked as.")

        desc = fields.get("description")
        if desc and len(desc) > DESCRIPTION_MAX_CHARS:
            bad(f"{rel(sk)}: description is {len(desc)} chars "
                f"(cap {DESCRIPTION_MAX_CHARS}). It sits in context every turn.")

        lines = text.count("\n") + 1
        if lines > SPINE_MAX_LINES:
            bad(f"{rel(sk)}: {lines} lines (cap {SPINE_MAX_LINES}). A SKILL.md is a loader "
                f"spine; per-step procedure belongs in references/.")

        if not re.search(r"^##\s+Strict rules\s*$", text, re.M):
            bad(f"{rel(sk)}: no `## Strict rules` section. A skill has to say what it must "
                f"never do, not only what it does.")

        refs = d / "references"
        on_disk = {p.name for p in refs.glob("*.md")} if refs.is_dir() else set()
        linked = set(re.findall(r"references/([A-Za-z0-9_.-]+\.md)", text))
        for orphan in sorted(on_disk - linked):
            bad(f"{rel(refs / orphan)}: on disk but never linked from SKILL.md, so no step "
                f"ever loads it")
        for dangling in sorted(linked - on_disk):
            bad(f"{rel(sk)}: links references/{dangling}, which does not exist")

        if len(failures) == before:
            ok(f"{rel(d)}/ contract holds ({lines} spine lines, {len(on_disk)} reference(s))")


# --- flavor skeletons track base ------------------------------------------------------

# What each flavor skeleton file is a derived copy of, and the digest of that master as of
# the last time a human reconciled the two. The digests live HERE rather than stamped in the
# flavor files themselves because those files ship: the flavor CLAUDE.md.template becomes an
# adopter's vault CLAUDE.md, read every session, and a repo-maintenance hash has no business
# being a permanent line in it. Add a row when a flavor gains a file that derives from base.
FLAVOR_TRACKING = {
    "flavors/readonly-ipad/skeleton/CLAUDE.md.template": ("base/CLAUDE.md.template", "984951188550"),
    "flavors/readonly-ipad/skeleton/README.md.template": ("base/README.md.template", "43113ab61151"),
    "flavors/readonly-ipad/skeleton/.gitignore":         ("base/.gitignore",          "92d77ba2543f"),
}


def base_digest(p):
    """Content hash, line endings normalized: a CRLF checkout must hash the same as an LF one,
    or this check would fire on every machine that clones the repo rather than on a real edit."""
    text = "\n".join(p.read_bytes().decode("utf-8", "replace").splitlines())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def check_flavor_tracking():
    """A flavor skeleton file is a derived copy of a base file, and nothing else notices it rot.

    `flavors/*/skeleton/` ships whole files, not patches, so each is 39% to 67% a verbatim copy
    of its base counterpart with a handful of deliberate deltas. The convention has been a
    header comment reading "if base changes, propagate here" - the same unenforced promise that
    let installed integration scripts drift for a revision, in the one place /para-upgrade reads
    as a master. Base moves, the flavor keeps the old paragraph, and every vault on that flavor
    is migrated to a rule the product no longer states.

    Comparing content cannot work: the deltas are the point, so a content rule either passes on
    everything or fails on the deltas forever. What CAN be checked is whether the master has
    moved since a human last looked. Re-stamping after reviewing a base diff and changing
    nothing is a legitimate outcome, and is the whole point: it records that someone looked.
    """
    for flavor_path, (base_path, stamped) in sorted(FLAVOR_TRACKING.items()):
        f, m = ROOT / flavor_path, ROOT / base_path
        if not f.exists():
            bad(f"{flavor_path}: listed in FLAVOR_TRACKING but does not exist. Drop the row, "
                f"or restore the file.")
            continue
        if not m.exists():
            bad(f"{flavor_path}: tracks `{base_path}`, which does not exist")
            continue
        want = base_digest(m)
        if stamped != want:
            bad(f"{base_path} changed ({stamped} -> {want}); {flavor_path} derives from it and "
                f"may now be stale. Review the diff, apply what the flavor needs, then update "
                f"the digest in tools/check.py FLAVOR_TRACKING. Re-stamping with no edit to the "
                f"flavor is fine - it records that someone looked.")
        else:
            ok(f"{flavor_path} reconciled against {base_path} @ {want}")


def check_skill_validator():
    """Run the vendor's own validator over the skills directory.

    Deliberately not a plugin step: `claude plugin validate <dir>` reads a plain folder of
    skills, needs no manifest and no marketplace, and publishes nothing. It complements the
    checks above rather than repeating them - those enforce this repo's conventions, this one
    enforces whatever the tool currently requires of a SKILL.md, which moves release to release
    and is the part a hand-written check cannot keep up with.

    Two things the tool does that this wrapper has to correct for, both measured rather than
    assumed. It picks its mode from the path - a folder under .claude/ validates as components,
    the same folder elsewhere is treated as a plugin directory and fails for having no manifest -
    so the run is only meaningful once the output says which mode it chose. And it exits 0 on
    warnings: a SKILL.md with a malformed name and no description reports "passed with warnings"
    and returns success. Keying on the exit code alone would be a check that runs, passes, and
    measures nothing.
    """
    claude = shutil.which("claude")
    if not claude:
        bad("`claude` is not on PATH, so the vendor's skill validator could not run. A check "
            "that could not run has not passed.")
        return
    try:
        returncode, out = run_captured([claude, "plugin", "validate", str(SKILLS_DIR)],
                                        timeout=120)
    except subprocess.TimeoutExpired:
        bad("claude plugin validate: timed out after 120s")
        return

    out_tail = tail(out, transform=console_safe)

    if "early access" in out.lower():
        bad(f"claude plugin validate: refused, {console_safe(out.splitlines()[0])}")
        return
    if "Validating components in" not in out:
        bad(f"claude plugin validate: did not validate {rel(SKILLS_DIR)}/ as a skills folder. "
            f"It picks its mode from the path, so this reports on the wrong thing rather than "
            f"failing outright.\n{out_tail}")
        return

    found = re.findall(r"Found (\d+) (error|warning)", out)
    counts = ", ".join(f"{n} {kind}(s)" for n, kind in found)

    # The CLI's own pass/fail phrasing is the closer thing to a stable contract; "Found N" is
    # supporting detail. Fail CLOSED on anything that isn't a recognized clean pass: a future
    # wording change must read as "could not confirm clean", never as "nothing to report".
    if returncode != 0 or "Validation failed" in out:
        bad(f"claude plugin validate: failed (exit {returncode})"
            f"{': ' + counts if counts else ''}\n{out_tail}")
    elif "Validation passed with warnings" in out or found:
        bad(f"claude plugin validate: {counts or 'passed with warnings'}. It exits 0 on "
            f"warnings, so these are caught here rather than by the exit code.\n{out_tail}")
    elif "Validation passed" in out:
        ok(f"claude plugin validate: {rel(SKILLS_DIR)}/ clean, no errors or warnings")
    else:
        bad(f"claude plugin validate: output did not match a recognized pass/fail shape "
            f"(exit {returncode}). Treating as failed rather than silently reporting "
            f"clean - the vendor CLI's wording may have changed.\n{out_tail}")


def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    check_integrations()
    check_template_revisions()
    check_template_size()
    check_dashes()
    check_flavor_tracking()
    check_skills()
    check_skill_validator()
    check_tests()

    if verbose:
        for line in passes:
            print(f"  ok    {line}")
    for line in failures:
        print(f"  FAIL  {line}")

    if failures:
        print(f"\n{len(failures)} failure(s), {len(passes)} check(s) passed.")
        return 1
    print(f"All {len(passes)} contract check(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
