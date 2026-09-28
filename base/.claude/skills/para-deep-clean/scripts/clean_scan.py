#!/usr/bin/env python3
"""The mechanical half of /para-deep-clean, as a script instead of instructions.

    py -3 clean_scan.py --vault <path> --phase 1|3|4 [--today YYYY-MM-DD] [--ref <git-ref>]
                         [--clone <path>] [--templates-dir <dir>]... [--dated-pattern <regex>]
                         [--next-steps-heading <heading>]... [--generated-dir <dir>]...
                         [--name-only-column <file>:<column>]... [--indent N]
    python3 clean_scan.py --vault <path> --phase 1

Prints one JSON document on stdout: the preconditions every phase checks, plus the
candidate findings for the phase asked for. It never writes to the vault - not even the
phase-3 file it reads for staleness - and never judges a candidate: exclusions for
third-party verbatim content, frozen records, or a vault's own declared contract are the
skill's job, per references/phase1-structural.md, phase3-open-items.md and
phase4-audit.md. Phase 2 has no script: README normalisation is judgment start to finish.

Why a script. The preconditions and the housekeeping scan are a mechanical read of the
vault - which folder holds a figure, whether a link resolves, whether an open item carries
a date - and two correct runs have to agree, which instructions re-derived per run do not.
This pins the rules the same way pipeline_scan.py pins /para-pipeline's.

Reading the vault's primitives - fenced-block-aware line scanning, link extraction and
resolution, content hashing, the checkbox and staleness thresholds - is not this script's
own work: para-shared/scripts/paraos_vault.py holds it. What lives here is what this
skill alone decides: which files are in scope for a placeholder or figure scan, how a
contact's citations are counted, what an "entity folder" is under archive/, and how a
stale item's date is measured.

What it deliberately does NOT do, so the skill keeps owning it: decide whether a finding
is a real defect or an exempt third-party file, propose a fix, ask a question, or write
anything. Every list here is candidates for the skill to judge.
"""

import argparse
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        BRIEF_LINE_CAP, CollectedVault, FALSELY_OVERDUE_DAYS, FROZEN_MARKER_RE, H1_RE,
        STALE_FILE_DAYS,
        LINK_ROOTS, WIP_THRESHOLD, abspath, action_files, clone_ref, dangling_links, declarations,
        duplicates, find_clone,
        extract_links, git, git_blame_line_date, hashes, inbound_references, is_separator_row,
        iso, link_files, link_spans, live_lines, master_template, misplaced_checkboxes, norm,
        open_tasks, over_grown_briefs, parse_date, read_lines, read_text, reference_shape,
        refuse_if_collected, resolve_link, snapshot, strip_code, table_cells,
        template_marker, triage_items,
    )
except ImportError as missing:  # the skill falls back to scanning by hand
    print(f"clean_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or scan "
          f"by hand with the phase's own reference", file=sys.stderr)
    sys.exit(2)


DEFAULT_DATED_PATTERN = r"^\d{8} "
DEFAULT_NEXT_STEPS_HEADINGS = ("Next steps", "Open items")
ENTITY_BASES = ("projects", "areas", "resources/ideas")
LIVE_ROOTS = ("projects", "areas", "resources", "triage")  # archive/ is history, not live
# A link target inside archive/ is still a path that must resolve; only prose there is history.
DANGLING_ROOTS = LINK_ROOTS + ("archive",)


def in_live_scope(rel):
    """Whether a vault-relative path sits in a live bucket: a root-level file (the root
    README, CLAUDE.md), or under projects/areas/resources/triage - the same roots
    dangling_links() and link_files() default to. archive/ is never live."""
    return "/" not in rel or rel.split("/", 1)[0] in LIVE_ROOTS


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*-\s+(.*)$")
ALIASES_RE = re.compile(r"^\*\*Aliases:\*\*\s*(.+)$", re.IGNORECASE)
ALSO_RE = re.compile(r"^Also:\s*(.+)$", re.IGNORECASE)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")
# A figure ends on a digit, a `k` or a `%` - never on the space or the sentence's own
# `.`/`,` after it - so "€1,200 total" and "€1,200." read as the same figure.
MONEY_RE = re.compile(r"(?:[€$]|EUR)\s?-?\d(?:[\d.,]*\d)?(?:\s?[kK]\b)?"
                      r"|-?\d(?:[\d.,]*\d)?\s?(?:%|[kK]\b)")
LEDGER_EXEMPT_RE = re.compile(
    r"(?:^|[-_. ])(?:log|usage|review|digest|ledger|transcript)s?(?:[-_. ]|$)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d ./]{6,}\d")
ISO_DATE_SHAPE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
COMPACT_DATE_SHAPE_RE = re.compile(r"^\d{8}$")


def whole_word(name):
    """`name` as a whole word: no letter, digit, underscore or hyphen either side, so a
    contact "Mark" is not named by "Marketing" and an entity `acme` is not named by
    `acme-website-v2` - the boundary brief_scan.mentions_elsewhere() uses."""
    return re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])")


def link_targets_stripped(line):
    """One line with every `[label](target)` target blanked - the label stays, the path
    does not - then percent-decoded. A figure, a phone or an entity name that only exists
    inside an href is not a mention of anything: shared by figure_pairs() and
    inline_contact_details(), per phase1-structural.md and phase3-open-items.md's own
    read of "never inside a path"."""
    out = list(line)
    for start, end, _ in link_spans(line):
        for i in range(start, end):
            out[i] = " "
    return unquote("".join(out))


def links_stripped(line):
    """One line with every `[label](target)` blanked whole - label and target both - then
    percent-decoded. A person named only in a link's text (a meeting record's filename) or
    only in its target is not a prose mention of them: uncited_contacts() counts what is
    left, per phase1-structural.md."""
    out = list(line)
    for start, end, label_at in link_spans(line):
        for i in range(start - 2 if label_at is None else label_at, end + 1):
            out[i] = " "
    return unquote("".join(out))


def is_ledger_exempt(rel):
    """The mechanical proxy phase1-structural.md states for "analytical and ledger records
    that are evidence in all but folder name": any path segment (a folder name or the
    filename itself, stem included) carrying "log", "usage", "review", "digest", "ledger"
    or "transcript" as a whole word, case-insensitively: `technologies` and `reviewer`
    carry none of them."""
    return any(LEDGER_EXEMPT_RE.search(part) for part in Path(rel).parts)


def under_any(rel, folders):
    return any(rel == f or rel.startswith(f + "/") for f in (d.strip("/") for d in folders))


def is_frozen_record(path):
    """The frozen-record marker phase1-structural.md Step 1.2b names, as plain text in the
    file's first fifteen live lines; an HTML comment carries it without rendering it."""
    return any(FROZEN_MARKER_RE.search(t) for _, t in live_lines(read_lines(path)[:15]))


def name_only_lines(path, columns):
    """{line: row text with every cell under one of `columns` blanked}, for each table row
    in `path`: a column its rule file declares a name, not a link."""
    wanted = {c.strip().lower() for c in columns}
    out, header = {}, None
    for lineno, text in live_lines(read_lines(path)):
        stripped = text.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = table_cells(stripped)
        if header is None:
            header = [c.strip("*_ ").lower() for c in cells]
            continue
        if is_separator_row(cells):
            continue
        out[lineno] = "| " + " | ".join(
            "" if i < len(header) and header[i] in wanted else c
            for i, c in enumerate(cells)) + " |"
    return out


def phone_matches(text):
    """Phone-shaped runs in `text`: a leading `+`, or at least eight digits separated only
    by spaces, dots or slashes - never a `YYYY-MM-DD` or `YYYYMMDD` date shape. Run on the
    href-stripped, percent-decoded line link_targets_stripped() produces, so a date or a
    path segment sitting inside a link target is never mistaken for a phone."""
    out = []
    for m in PHONE_CANDIDATE_RE.finditer(text):
        candidate = m.group(0)
        digits = re.sub(r"\D", "", candidate)
        if ISO_DATE_SHAPE_RE.search(candidate) or COMPACT_DATE_SHAPE_RE.match(digits):
            continue
        if candidate.strip().startswith("+") or len(digits) >= 8:
            out.append(candidate)
    return out


# --------------------------------------------------------------------------- preconditions

def triage_precondition(vault):
    items = triage_items(vault)
    return {"triage_loose": sorted(i for i in items if i != "README.md"),
            "triage_readme": "README.md" in items}


def marker_precondition(vault, clone, ref):
    """The vault's template marker against the master's at a committed ref. Which master
    that is (a declared or detected delivery's skeleton, in whichever layout the ref
    carries, else base) is the library's `declarations` and `master_template`, the same
    reading /para-upgrade makes, so the two skills never measure one vault against two
    templates. `ref_missing` is a clone whose ref does not resolve: one made before
    releases moved to `stable`, where the ref is the default."""
    decl = declarations(vault)
    vault_marker = template_marker(read_text(vault / "CLAUDE.md"))
    master_marker, delivery_fallback = None, None
    clone, clone_source = find_clone(clone)

    if clone:
        master = master_template(clone, ref, decl)
        master_marker, delivery_fallback = master["marker"], master["fallback"]

    if clone is None:
        verdict = "no_clone"
    elif master_marker is None or vault_marker is None:
        verdict = "unverified"
    elif vault_marker == master_marker:
        verdict = "equal"
    elif vault_marker < master_marker:
        verdict = "behind"
    else:
        verdict = "ahead"

    out = {"vault": vault_marker, "master": master_marker, "verdict": verdict,
           "clone": clone.as_posix() if clone else None, "clone_source": clone_source,
           "ref": ref, "ref_missing": bool(clone) and clone_ref(clone, ref) is None,
           "delivery": decl["delivery"], "delivery_source": decl["delivery_source"]}
    if delivery_fallback:
        out["delivery_fallback"] = delivery_fallback
    return out


def preconditions(vault, clone, ref):
    return {**triage_precondition(vault), "template_marker": marker_precondition(vault, clone, ref)}


# ------------------------------------------------------------------------------------ map

def empty_leaf_dirs(vault):
    out = []
    for d in sorted(vault.rglob("*")):
        if not d.is_dir() or ".git" in d.parts:
            continue
        try:
            if not any(d.iterdir()):
                out.append(d.relative_to(vault).as_posix())
        except OSError:
            continue
    return out


def phase1_map(vault):
    top = sorted(p.name for p in vault.iterdir() if p.is_dir() and p.name != ".git")
    counts = {}
    for bucket in ("projects", "areas", "resources/ideas"):
        base = vault / bucket
        counts[bucket] = len([d for d in base.iterdir() if d.is_dir()]) if base.is_dir() else 0
    return {"top_level": top, "entity_counts": counts, "empty_leaf_dirs": empty_leaf_dirs(vault)}


# --------------------------------------------------------------------------- placeholders

def placeholder_files(vault, templates_dirs):
    """The root README, CLAUDE.md, every entity brief/README, and every actions.md - the
    files the bootstrap actually writes - minus resources/prompts/ and any vault-declared
    template folder."""
    exclude = {"resources/prompts", *templates_dirs}
    candidates = [vault / "README.md", vault / "CLAUDE.md"]
    for bucket in ("projects", "areas", "resources/ideas", "archive"):
        for name in ("brief.md", "README.md"):
            candidates += vault.glob(f"{bucket}/**/{name}")
    candidates += vault.rglob("actions.md")

    seen, out = set(), []
    for f in candidates:
        if not f.is_file():
            continue
        rel = f.relative_to(vault).as_posix()
        if rel in seen or under_any(rel, exclude):
            continue
        seen.add(rel)
        out.append(f)
    return sorted(out)


def find_placeholders_in(files, vault):
    out = []
    for f in files:
        text = strip_code(read_text(f))
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "{{" in line:
                out.append({"file": f.relative_to(vault).as_posix(), "line": lineno,
                            "text": line.strip()})
    return out


# ------------------------------------------------------------------------- checker check

def checker_verified():
    """extract_links()/dangling_links() run once against a fixture carrying a known-good
    link with spaces and parentheses, a deliberately broken one, and one inside a fence -
    the three-direction self-check phase1-structural.md Step 1.2 requires before the
    dangling-link verdict is trusted."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "target (NL).md").write_text("target\n", encoding="utf-8")
        (tmp / "source.md").write_text("\n".join([
            "[good](target%20(NL).md)",
            "[broken](missing.md)",
            "```",
            "[fenced](also-missing.md)",
            "```",
        ]) + "\n", encoding="utf-8")
        found = {h["href"] for h in dangling_links(tmp)}
        return {"good_link_passes": "target%20(NL).md" not in found,
                "broken_link_caught": "missing.md" in found,
                "fenced_link_skipped": "also-missing.md" not in found}


# --------------------------------------------------------------------------- wikilinks

def build_md_index(vault):
    """{norm(filename): [paths]} - folded the way norm() folds a folder name, so a wikilink
    written as the note's display title ([[Jan Claes]]) resolves against a kebab-case
    filename (jan-claes.md) the way the vault's own naming convention expects."""
    index = {}
    for p in vault.rglob("*.md"):
        index.setdefault(norm(p.stem), []).append(p)
    return index


def wikilink_matches(vault, index, target):
    """The notes a wikilink target names. A bare name resolves by filename stem through
    the index; a path form ([[projects/acme/brief]], with or without `.md`) is
    vault-relative, and a partial one ([[acme/brief]]) names any note whose path ends in
    it, the way Obsidian resolves its shortest-unique form."""
    target = target.replace("\\", "/").strip("/")
    stem = target[:-3] if target.lower().endswith(".md") else target
    candidates = index.get(norm(stem.rsplit("/", 1)[-1])) or []
    if "/" not in stem:
        return candidates
    tail = "/" + stem.lower() + ".md"
    return [p for p in candidates
            if ("/" + p.relative_to(vault).as_posix().lower()).endswith(tail)]


def find_wikilinks(vault, roots=("projects", "areas", "resources", "triage")):
    index = build_md_index(vault)
    out = []
    for path in link_files(vault, roots):
        text = strip_code(read_text(path))
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in WIKILINK_RE.finditer(line):
                target = m.group(1).strip()
                display = m.group(2).strip() if m.group(2) else None
                matches = wikilink_matches(vault, index, target)
                resolved = sorted(matches)[0].relative_to(vault).as_posix() if matches else None
                out.append({"file": path.relative_to(vault).as_posix(), "line": lineno,
                            "target": target, "display": display, "resolved": resolved})
    return out


# ------------------------------------------------------------------------ contact cards

def contact_names(card):
    """The card's H1 name, plus every alias a `**Aliases:**` or `Also:` line lists -
    scan.md-style name recovery, generalised to a contact card."""
    lines = [t for _, t in live_lines(read_lines(card))]
    names = []
    for t in lines:
        m = H1_RE.match(t.strip())
        if m:
            names.append(m.group(1).strip())
            break
    for t in lines:
        m = ALIASES_RE.match(t.strip()) or ALSO_RE.match(t.strip())
        if m:
            names += [a.strip() for a in re.split(r"[,;]", m.group(1)) if a.strip()]
    return names


def mention_links_card(path, line_text, card_target):
    for _, href, _ in extract_links(strip_code(line_text)):
        if resolve_link(path, href) == card_target:
            return True
    return False


def identity_section(readme):
    lines, in_identity = [], False
    for _, text in live_lines(read_lines(readme)):
        m = HEADING_RE.match(text.strip())
        if m:
            in_identity = m.group(2).strip().lower() == "identity"
            continue
        if in_identity:
            lines.append(text)
    return "\n".join(lines)


def is_principal(vault, card_rel):
    readme = vault / "README.md"
    if not readme.is_file():
        return False
    card_target = abspath(vault / card_rel)
    for _, href, _ in extract_links(strip_code(identity_section(readme))):
        if resolve_link(readme, href) == card_target:
            return True
    return False


def top_level_area_readme(vault, card_rel):
    parts = Path(card_rel).parts
    if len(parts) >= 2:
        candidate = vault / parts[0] / parts[1] / "README.md"
        if candidate.is_file():
            return candidate.relative_to(vault).as_posix()
    return "README.md"


def uncited_contacts(vault, excluded_dirs=(), name_only_columns=()):
    """Every carded person named in a live file with no link to their card, minus what
    phase1-structural.md exempts: resources/prompts/ and `excluded_dirs` (declared template
    and sync-output folders), a file carrying the frozen-record marker, and a cell under a
    declared name-only column (`<file>:<column>`). Returns (cards, exempt): `cards` is the
    finding, one entry per card with the files that named it uncited; `exempt` is every
    file a mention was found in but dropped as a ledger record, so the skill can override
    the proxy."""
    network_dir = vault / "areas" / "network"
    if not network_dir.is_dir():
        return [], []
    excluded = ("resources/prompts", *excluded_dirs)
    columns = {}
    for spec in name_only_columns:
        rel, _, column = spec.rpartition(":")
        columns.setdefault(rel.strip("/"), []).append(column)
    blanked = {rel: name_only_lines(vault / rel, cols) for rel, cols in columns.items()
               if (vault / rel).is_file()}
    frozen = {}
    out, exempt = [], set()
    for card in sorted(network_dir.glob("*.md")):
        card_rel = card.relative_to(vault).as_posix()
        names = contact_names(card)
        if not names:
            continue
        principal = is_principal(vault, card_rel)
        allowed = {top_level_area_readme(vault, card_rel)} if principal else None
        card_target = abspath(card)

        per_file = {}
        for name in names:
            pattern = whole_word(name)
            for hit in inbound_references(vault, name):
                if hit["file"] == card_rel or hit["in_sources"] or not in_live_scope(hit["file"]) \
                        or under_any(hit["file"], excluded):
                    continue
                if hit["file"] not in frozen:
                    frozen[hit["file"]] = is_frozen_record(vault / hit["file"])
                if frozen[hit["file"]]:
                    continue
                text = blanked.get(hit["file"], {}).get(hit["line"], hit["text"])
                # inbound_references() without a parent is a bare substring find, so the
                # name is re-matched as a whole word.
                if not pattern.search(unquote(text)):
                    continue
                if allowed is not None and hit["file"] not in allowed:
                    continue
                # Only a prose mention counts. A name quoted inside backticks - a path, a
                # code sample - is not a mention of the person, per "a quoted syntax is not
                # a used syntax", and neither is one inside a link's text or target (a
                # linked source filename, a percent-decoded href).
                prose = links_stripped(text)
                mentioned = any(reference_shape(prose, m.start(), m.end()) == "prose"
                                for m in pattern.finditer(prose))
                if is_ledger_exempt(hit["file"]):
                    if mentioned:
                        exempt.add(hit["file"])
                    continue
                entry = per_file.setdefault(hit["file"], {"mentions": 0, "linked": False})
                if mentioned:
                    entry["mentions"] += 1
                # The name's own shape on this line (label, target, prose) says nothing
                # about whether the line links to the card - a normal citation reads
                # [Name](path), where the name is link_text and the card path is the
                # target - so every hit line is checked for a resolving link, the ones
                # naming the person only inside a link included.
                if mention_links_card(vault / hit["file"], hit["text"], card_target):
                    entry["linked"] = True

        uncited = [{"file": f, "mentions": e["mentions"]}
                   for f, e in sorted(per_file.items()) if e["mentions"] and not e["linked"]]
        if uncited:
            out.append({"card": card_rel, "name": names[0], "principal": principal,
                        "files": uncited})
    return out, sorted(exempt)


def inline_contact_details(vault):
    """Every email or phone detail on a live line naming at least one carded person,
    reported once per detail with every carded name on the line and no attribution -
    phase1-structural.md forbids assigning a detail to whoever shares its line, so this
    reports `names_on_line` and `attribution: "unresolved"` and leaves the assignment to
    the skill. Matched on the line with inline code spans blanked and every link target
    stripped and percent-decoded, so a path or a code sample never reads as a detail."""
    network_dir = vault / "areas" / "network"
    if not network_dir.is_dir():
        return []
    names_by_card, patterns = {}, {}
    for card in sorted(network_dir.glob("*.md")):
        card_rel = card.relative_to(vault).as_posix()
        for name in contact_names(card):
            names_by_card[name] = card_rel
            patterns[name] = whole_word(name)

    out = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        if "sources" in Path(rel).parts[:-1] or not in_live_scope(rel):
            continue
        raw_lines = read_lines(path)
        code_stripped = strip_code(read_text(path)).splitlines()
        for lineno, text in live_lines(raw_lines):
            uncoded = code_stripped[lineno - 1] if lineno - 1 < len(code_stripped) else text
            clean = link_targets_stripped(uncoded)
            names_on_line = sorted({n for n, c in names_by_card.items()
                                    if c != rel and patterns[n].search(clean)})
            if not names_on_line:
                continue
            details = [(m.group(0), "email") for m in EMAIL_RE.finditer(clean)]
            details += [(d, "phone") for d in phone_matches(clean)]
            for detail, kind in details:
                out.append({"file": rel, "line": lineno, "text": text.strip(),
                            "names_on_line": names_on_line, "detail": detail.strip(),
                            "kind": kind, "attribution": "unresolved"})
    return out


# ------------------------------------------------------------------------------ duplicates

def entity_of_path(rel):
    parts = Path(rel).parts
    if not parts:
        return rel
    if parts[0] == "archive" and len(parts) >= 3:
        return "/".join(parts[:3])
    if parts[0] == "resources" and len(parts) >= 3 and parts[1] == "ideas":
        return "/".join(parts[:3])
    if parts[0] in ("projects", "areas") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def duplicate_report(vault):
    digests = hashes(vault)
    groups = duplicates(digests)
    out = [{"files": g, "cross_entity": len({entity_of_path(p) for p in g}) > 1} for g in groups]
    return {"groups": out, "skipped": digests["skipped"]}


# --------------------------------------------------------------------------- figure pairs

def figures_in_line(line):
    return sorted(set(MONEY_RE.findall(line)))


def entity_names(vault):
    names = set()
    for bucket in ENTITY_BASES:
        base = vault / bucket
        if base.is_dir():
            names.update(d.name for d in base.iterdir() if d.is_dir())
    return sorted(names)


def pick_doc(folder):
    readme, brief = folder / "README.md", folder / "brief.md"
    if readme.is_file():
        return readme
    if brief.is_file():
        return brief
    return None


def rollup_files(vault):
    files = [vault / "README.md"]
    for bucket in ("projects", "areas", "resources", "archive"):
        p = vault / bucket / "README.md"
        if p.is_file():
            files.append(p)
    for path in vault.rglob("*.md"):
        if path.stem.lower() in ("dashboard", "overview"):
            files.append(path)
    return sorted({f for f in files if f.is_file()})


def figure_pairs(vault):
    """Candidate pairs only, never resolved: a rollup line naming an entity, carrying a
    figure the entity's own brief does not carry anywhere, where that brief states a figure
    of its own. Which value is right is the skill's question and a source document's answer.

    Matched on the line with every link target stripped and percent-decoded, on both
    sides - the rollup line and the entity's own brief - and the entity name matched as a
    whole word, hyphens included - a figure or a name that exists only inside an href, or
    a name that is part of a longer one (`acme` in `acme-website-v2`), is never a match."""
    names = entity_names(vault)
    name_patterns = {n: whole_word(n) for n in names}
    brief_cache = {}

    def brief_figures(name):
        if name not in brief_cache:
            figs = None
            for bucket in ENTITY_BASES:
                folder = vault / bucket / name
                if folder.is_dir():
                    doc = pick_doc(folder)
                    if doc:
                        figs = set()
                        for line in strip_code(read_text(doc)).splitlines():
                            figs.update(figures_in_line(link_targets_stripped(line)))
                    break
            brief_cache[name] = figs
        return brief_cache[name]

    out = []
    for path in rollup_files(vault):
        text = strip_code(read_text(path))
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            clean = link_targets_stripped(raw_line)
            for name in names:
                if not name_patterns[name].search(clean):
                    continue
                line_figs = figures_in_line(clean)
                if not line_figs:
                    continue
                bfigs = brief_figures(name)
                # No brief, or a brief stating no figure at all: one figure in one file is
                # not two values for the same number.
                if not bfigs or set(line_figs) <= bfigs:
                    continue
                out.append({"entity": name, "rollup_file": path.relative_to(vault).as_posix(),
                            "rollup_line": lineno, "rollup_figures": line_figs,
                            "brief_figures": sorted(bfigs)})
    return out


# -------------------------------------------------------------------------------- archive

def archive_findings(vault, dated_pattern):
    archive = vault / "archive"
    loose_root_files, meetings_naming, missing_record = [], [], []
    if archive.is_dir():
        loose_root_files = sorted(p.relative_to(vault).as_posix()
                                  for p in archive.iterdir() if p.is_file())
        meetings = archive / "meetings"
        if meetings.is_dir():
            pattern = re.compile(dated_pattern)
            meetings_naming = sorted(p.relative_to(vault).as_posix()
                                     for p in meetings.iterdir()
                                     if p.is_file() and not pattern.match(p.name))
        for bucket_dir in sorted(d for d in archive.iterdir() if d.is_dir() and d.name != "meetings"):
            for entity_dir in sorted(d for d in bucket_dir.iterdir() if d.is_dir()):
                if not (entity_dir / "brief.md").is_file() and not (entity_dir / "README.md").is_file():
                    missing_record.append(entity_dir.relative_to(vault).as_posix())
    return {"loose_root_files": loose_root_files, "meetings_naming": meetings_naming,
            "missing_record": missing_record, "misplaced_checkboxes": misplaced_checkboxes(vault)}


def stale_drafts(vault):
    out = []
    for path in sorted(vault.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".doc", ".docx"):
            pdf = path.with_suffix(".pdf")
            if pdf.is_file():
                out.append({"draft": path.relative_to(vault).as_posix(),
                            "pdf": pdf.relative_to(vault).as_posix()})
    return out


# ----------------------------------------------------------------------------------- phase 1

def phase1(vault, templates_dirs, dated_pattern, generated_dirs=(), name_only_columns=()):
    touched = set()

    map_ = phase1_map(vault)

    ph_files = placeholder_files(vault, templates_dirs)
    placeholders = find_placeholders_in(ph_files, vault)
    touched |= set(ph_files)

    dangling = dangling_links(vault, DANGLING_ROOTS)
    touched |= {vault / d["file"] for d in dangling}

    checker = checker_verified()

    wikilinks = find_wikilinks(vault)
    touched |= {vault / w["file"] for w in wikilinks}

    uncited, uncited_exempt = uncited_contacts(vault, (*templates_dirs, *generated_dirs),
                                               name_only_columns)
    touched |= {vault / c["card"] for c in uncited}
    touched |= {vault / f["file"] for c in uncited for f in c["files"]}
    touched |= {vault / f for f in uncited_exempt}

    inline_details = inline_contact_details(vault)
    touched |= {vault / d["file"] for d in inline_details}

    dup = duplicate_report(vault)
    touched |= {vault / f for g in dup["groups"] for f in g["files"]}

    figs = figure_pairs(vault)
    touched |= {vault / f["rollup_file"] for f in figs}

    archive = archive_findings(vault, dated_pattern)
    touched |= {vault / f for f in archive["loose_root_files"]}
    touched |= {vault / f for f in archive["meetings_naming"]}
    touched |= {vault / f for f in archive["missing_record"]}
    touched |= {vault / r["file"] for rows in archive["misplaced_checkboxes"].values() for r in rows}

    drafts = stale_drafts(vault)
    touched |= {vault / d["draft"] for d in drafts}

    return {"map": map_, "placeholders": placeholders, "dangling": dangling,
            "checker_verified": checker, "wikilinks": wikilinks, "uncited_contacts": uncited,
            "uncited_exempt": uncited_exempt, "inline_contact_details": inline_details,
            "duplicates": dup, "figure_pairs": figs, "archive": archive,
            "stale_drafts": drafts, "snapshot": snapshot(sorted(touched, key=str))}


# ----------------------------------------------------------------------------------- phase 3

def over_threshold_from(files, vault):
    out = [{"file": f.relative_to(vault).as_posix(), "open": len(open_tasks(f))} for f in files]
    out = [r for r in out if r["open"] >= WIP_THRESHOLD]
    return sorted(out, key=lambda r: -r["open"])


def other_checkbox_paths(vault):
    """Every `.md` under `projects/` and `areas/` that is not an action file or a contact
    file (action_files() already covers both) and carries at least one open checkbox -
    phase3-open-items.md Step 3.4's "every other file ... that carries open checkboxes",
    not only actions.md."""
    vault = Path(vault)
    action_set = set(action_files(vault))
    out = []
    for bucket in ("projects", "areas"):
        base = vault / bucket
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path in action_set or path.name == "actions.md":
                continue
            if open_tasks(path):
                out.append(path)
    return out


def other_checkbox_files(vault, paths):
    """`other_checkbox_paths()` as the report: a count per file, `declares_contract`
    always null here since whether the file states its own shape is the skill's read of
    its header, never this script's."""
    return [{"file": p.relative_to(vault).as_posix(), "open": len(open_tasks(p)),
             "declares_contract": None} for p in paths]


def stale_undated_from(vault, files, today):
    """Each open, undated item untouched for STALE_FILE_DAYS, measured on its own line by
    `git blame -L`, which follows the line's content through history rather than its
    current line number - a `git log -L` query loses a more recent edit once something
    else in the file shifts where the item sits - where the file is tracked, else the
    file's mtime, else unmeasurable, said per item, never for the whole run, so a git-less
    vault still gets a real answer for the files whose mtime is trustworthy. A line git
    blame reports as still uncommitted is its own `measured_by`, "uncommitted", and counts
    as unmeasurable rather than as a fabricated date."""
    out = {}
    for f in files:
        rel = f.relative_to(vault).as_posix()
        tracked = git(vault, ["ls-files", "--error-unmatch", rel]) is not None
        items = []
        for t in open_tasks(f):
            if t["due"] or t["scheduled"] or t["start"]:
                continue
            entry = {"line": t["line"], "text": t["text"]}
            date_str, reason, measured_by = None, None, None
            if tracked:
                blame = git_blame_line_date(vault, f, t["line"])
                if blame == "uncommitted":
                    entry.update(measured_by="uncommitted",
                                 unmeasurable="line not yet committed")
                    items.append(entry)
                    continue
                if blame:
                    date_str, measured_by = blame, "git_blame_line"
                else:
                    reason = "tracked, but git blame returned no date for this line"
            else:
                try:
                    date_str, measured_by = date.fromtimestamp(f.stat().st_mtime).isoformat(), "mtime"
                except OSError:
                    reason = "untracked, and the file's mtime could not be read"
            if date_str:
                days = (today - parse_date(date_str)).days
                if days >= STALE_FILE_DAYS:
                    entry.update(days=days, measured_by=measured_by)
                    items.append(entry)
            else:
                entry["unmeasurable"] = reason
                items.append(entry)
        if items:
            out[rel] = items
    return out


def aspirational_from(files, vault, today):
    out = {}
    for f in files:
        rel = f.relative_to(vault).as_posix()
        items = []
        for t in open_tasks(f):
            d = parse_date(t["due"]) or parse_date(t["scheduled"])
            if d and (today - d).days > FALSELY_OVERDUE_DAYS:
                items.append({"line": t["line"], "text": t["text"], "date": iso(d),
                             "days_overdue": (today - d).days})
        if items:
            out[rel] = items
    return out


def live_briefs(vault):
    files = []
    for bucket in ENTITY_BASES:
        for name in ("brief.md", "README.md"):
            files += vault.glob(f"{bucket}/*/{name}")
    return sorted({f for f in files if f.is_file()})


def bullets_under_headings(path, headings, vault):
    """Every bullet in a section under one of `headings`, sub-headings included: a deeper
    heading groups the section's bullets, and only one at the section's level or above
    ends it."""
    wanted = {h.strip().lower() for h in headings}
    out, active_level = [], None
    for lineno, text in live_lines(read_lines(path)):
        m = HEADING_RE.match(text.strip())
        if m:
            level, title = len(m.group(1)), m.group(2).strip().lower()
            if active_level is not None and level > active_level:
                continue
            active_level = level if title in wanted else None
            continue
        bm = BULLET_RE.match(text) if active_level is not None else None
        if bm:
            out.append({"file": path.relative_to(vault).as_posix(), "line": lineno,
                        "text": bm.group(1).strip()})
    return out


def prose_next_steps(vault, headings):
    """For a vault with no actions.md at all, the bullets under the vault's declared
    next-steps headings in every live brief - the read-only iPad delivery's own next-step
    channel, per operating-discipline.md."""
    if any(True for _ in vault.rglob("actions.md")):
        return {"applicable": False, "items": []}
    items = []
    for f in live_briefs(vault):
        items += bullets_under_headings(f, headings, vault)
    return {"applicable": True, "items": items}


def phase3(vault, today, headings):
    files = action_files(vault)
    other_paths = other_checkbox_paths(vault)
    over_threshold = over_threshold_from(files + other_paths, vault)
    other_files = other_checkbox_files(vault, other_paths)
    stale_undated = stale_undated_from(vault, files + other_paths, today)
    aspirational = aspirational_from(files + other_paths, vault, today)
    prose = prose_next_steps(vault, headings)
    briefs_to_read = over_grown_briefs(vault, limit=None)

    touched = set(files) | set(other_paths)
    touched |= {vault / b["file"] for b in briefs_to_read}
    if prose["applicable"]:
        touched |= {vault / it["file"] for it in prose["items"]}

    return {"over_threshold": over_threshold, "other_checkbox_files": other_files,
            "stale_undated": stale_undated, "aspirational": aspirational,
            "prose_next_steps": prose, "briefs_to_read": briefs_to_read,
            "snapshot": snapshot(sorted(touched, key=str))}


# ----------------------------------------------------------------------------------- phase 4

def phase4(vault, templates_dirs, dated_pattern, today, generated_dirs=(),
           name_only_columns=()):
    touched, rows = set(), []

    mc = misplaced_checkboxes(vault)
    touched |= {vault / r["file"] for r in mc["archive"]}
    rows.append({"check": "archived_open_items", "pass": not mc["archive"], "detail": mc["archive"]})

    tri = triage_precondition(vault)
    triage_ok = not tri["triage_loose"] and not tri["triage_readme"]
    rows.append({"check": "triage_empty", "pass": triage_ok, "detail": tri})

    empties = empty_leaf_dirs(vault)
    rows.append({"check": "no_empty_leaf_dirs", "pass": not empties, "detail": empties})

    arch = archive_findings(vault, dated_pattern)
    archive_clean = not (arch["loose_root_files"] or arch["meetings_naming"] or arch["missing_record"])
    touched |= {vault / f for f in arch["loose_root_files"] + arch["meetings_naming"] + arch["missing_record"]}
    touched |= {vault / r["file"] for rows_ in arch["misplaced_checkboxes"].values() for r in rows_}
    rows.append({"check": "archive_clean", "pass": archive_clean, "detail": arch})

    dangling = dangling_links(vault, DANGLING_ROOTS)
    touched |= {vault / d["file"] for d in dangling}
    rows.append({"check": "dangling_links", "pass": not dangling, "detail": dangling})

    ph_files = placeholder_files(vault, templates_dirs)
    placeholders = find_placeholders_in(ph_files, vault)
    touched |= set(ph_files)
    rows.append({"check": "placeholders", "pass": not placeholders, "detail": placeholders})

    # The files Phase 3 grooms. An action file over the threshold fails; any other checkbox
    # file over it is pass: None, since whether it declares its own contract is the skill's.
    files = action_files(vault)
    other_paths = other_checkbox_paths(vault)
    over_threshold = over_threshold_from(files + other_paths, vault)
    touched |= set(files) | set(other_paths)
    action_rels = {f.relative_to(vault).as_posix() for f in files}
    if any(r["file"] in action_rels for r in over_threshold):
        over_pass = False
    else:
        over_pass = None if over_threshold else True
    rows.append({"check": "over_threshold_files", "pass": over_pass, "detail": over_threshold})

    aspirational = aspirational_from(files, vault, today)
    rows.append({"check": "aspirational_dates", "pass": not aspirational, "detail": aspirational})

    # Candidates only, pass: None - phase4-audit.md lists contact citation and detail
    # attribution among what this phase re-verifies, and the verdict (real defect, or a
    # legitimate exemption) is the skill's, not this script's.
    uncited, uncited_exempt = uncited_contacts(vault, (*templates_dirs, *generated_dirs),
                                               name_only_columns)
    touched |= {vault / c["card"] for c in uncited}
    touched |= {vault / f["file"] for c in uncited for f in c["files"]}
    touched |= {vault / f for f in uncited_exempt}
    rows.append({"check": "uncited_contacts", "pass": None,
                 "detail": {"cards": len(uncited),
                            "card_files": sum(len(c["files"]) for c in uncited)}})

    inline_details = inline_contact_details(vault)
    touched |= {vault / d["file"] for d in inline_details}
    rows.append({"check": "inline_contact_details", "pass": None, "detail": len(inline_details)})

    return {"rows": rows, "snapshot": snapshot(sorted(touched, key=str))}


# ------------------------------------------------------------------------------- the report

def scan(vault, today, phase, ref, clone, templates_dirs, dated_pattern, headings,
         generated_dirs=(), name_only_columns=()):
    vault = Path(vault).resolve()
    refuse_if_collected(vault)
    report = {"vault": vault.as_posix(), "today": today.isoformat(), "phase": phase,
              "preconditions": preconditions(vault, clone, ref)}
    if phase == "1":
        report["phase1"] = phase1(vault, templates_dirs, dated_pattern, generated_dirs,
                                  name_only_columns)
    elif phase == "3":
        report["phase3"] = phase3(vault, today, headings)
    elif phase == "4":
        report["phase4"] = phase4(vault, templates_dirs, dated_pattern, today, generated_dirs,
                                  name_only_columns)
    return report, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan a vault for /para-deep-clean's mechanical checks.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--phase", required=True, choices=["1", "3", "4"], help="which phase to scan")
    ap.add_argument("--today", help="date to measure against (default: the system date)")
    ap.add_argument("--ref", default="origin/stable",
                    help="committed para-os ref for the template-marker precondition")
    ap.add_argument("--clone", help="path to a local para-os clone, for the template-marker "
                                     "precondition (default: $PARAOS_HOME/para-os)")
    ap.add_argument("--templates-dir", action="append", default=[], metavar="DIR",
                    help="a folder the vault names as holding templates, excluded from the "
                         "placeholder and uncited-contact scans (repeatable)")
    ap.add_argument("--generated-dir", action="append", default=[], metavar="DIR",
                    help="a folder the vault names as a sync script's output, excluded from "
                         "the uncited-contact scan (repeatable)")
    ap.add_argument("--name-only-column", action="append", default=[], metavar="FILE:COLUMN",
                    help="a register column its rule file declares a name, not a link, "
                         "excluded from the uncited-contact scan (repeatable)")
    ap.add_argument("--dated-pattern", default=DEFAULT_DATED_PATTERN,
                    help=f"naming pattern archive/meetings/ files must match "
                         f"(default: {DEFAULT_DATED_PATTERN!r})")
    ap.add_argument("--next-steps-heading", action="append", default=[], metavar="HEADING",
                    help="a heading whose bullets count as prose next steps for a vault with "
                         "no actions.md (repeatable, default: Next steps, Open items)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    args = ap.parse_args(argv)

    # A Windows console and a Windows pipe both default to a codepage that cannot encode a
    # task marker, and the traceback lands where the JSON was meant to be.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    today = parse_date(args.today) if args.today else date.today()
    if args.today and not today:
        ap.error("--today wants YYYY-MM-DD")
    root = Path(args.vault)
    if not root.is_dir():
        ap.error(f"no such vault: {root}")
    headings = args.next_steps_heading or list(DEFAULT_NEXT_STEPS_HEADINGS)

    try:
        report, code = scan(root, today, args.phase, args.ref, args.clone,
                            args.templates_dir, args.dated_pattern, headings,
                            args.generated_dir, args.name_only_column)
    except CollectedVault as refused:
        print(f"clean_scan: {refused}", file=sys.stderr)
        return 2

    json.dump(report, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
