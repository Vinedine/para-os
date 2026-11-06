#!/usr/bin/env python3
"""The mechanical half of /para-deep-clean, as a script instead of instructions.

    py -3 clean_scan.py --vault <path> --phase 1|3|4 [--today YYYY-MM-DD] [--ref <git-ref>]
                         [--clone <path>] [--templates-dir <dir>]... [--dated-pattern <regex>]
                         [--next-steps-heading <heading>]... [--generated-dir <dir>]...
                         [--indent N]
    python3 clean_scan.py --vault <path> --phase 1

Prints one JSON document on stdout: the preconditions every phase checks, plus the
candidate findings for the phase asked for. It never writes to the vault - not even the
phase-3 file it reads for staleness - and never judges a candidate: exclusions for
third-party verbatim content, frozen records, or a vault's own declared contract are the
skill's job, per references/phase1-structural.md, phase3-open-items.md and
SKILL.md's Phase 4. Phase 2 has no script: README normalisation is judgment start to finish.

What it deliberately does NOT do, so the skill keeps owning it: decide whether a finding
is a real defect or an exempt third-party file, propose a fix, ask a question, or write
anything but phase 3's date to `deep_clean_stamp`, outside the vault, which /para-daily-brief
reads. Every list here is candidates for the skill to judge.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        ANY_DATE_RE, CLOSED_TASK_RE, DORMANT_ENTITY_DAYS, FALSELY_OVERDUE_DAYS, FROZEN_MARKER_RE,
        HEADING_RE, LINK_ROOTS, MARKED_SUFFIXES, NOT_CARDS, OPEN_ITEM_CAP, STALE_UNDATED_DAYS,
        TASK_RE, abspath, action_files, cap_count, contact_names, dangling_links, date_arg,
        deep_clean_stamp, duplicates, emit, entity_candidates, entity_doc, extract_links, field_ci,
        find_clone, git, git_blame_line_date, hashes, header_fields, inbound_references_by_name,
        integration_markers, is_separator_row, iso, lifecycles, link_files, link_spans, live_lines,
        log_entries, misplaced_checkboxes, norm, open_tasks, other_checkbox_paths,
        over_grown_briefs, parse_date, read_lines, read_text, reference_shape, rel_posix,
        resolve_entity, resolve_link, snapshot, split_lines, stage_of, strip_code, table_cells,
        template_marker, triage_items, under_any, utf8_stdout, vault_paths,
    )
    from paraos_clone import clone_ref, master_template  # noqa: E402
except ImportError as missing:  # para-shared/scripts.md: the skill stops
    print(f"clean_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill", file=sys.stderr)
    sys.exit(2)


DEFAULT_DATED_PATTERN = r"^\d{8} "
DEFAULT_NEXT_STEPS_HEADINGS = ("Next steps", "Open items")
ENTITY_BASES = ("projects", "areas", "resources/ideas")
GROWN = 1.5     # a brief past this many times its length at the last deep clean is read again
ORPHANS_LISTED = 5  # an entity with more orphans than this is reported as a count
STRUCTURE_FILES = ("README.md", "brief.md", "actions.md")
# A link target inside archive/ is still a path that must resolve; only prose there is history.
# A rule file links into the vault too, from two folders down.
DANGLING_ROOTS = LINK_ROOTS + ("archive", ".claude/rules")


def in_live_scope(rel):
    """Whether a vault-relative path sits in a live bucket: a root-level file (the root
    README, CLAUDE.md), or under projects/areas/resources/triage - the same roots
    dangling_links() and link_files() default to. archive/ is never live."""
    return "/" not in rel or rel.split("/", 1)[0] in LINK_ROOTS


BULLET_RE = re.compile(r"^\s*-\s+(.*)$")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")
# A figure ends on a digit, a `k` or a `%` - never on the space or the sentence's own
# `.`/`,` after it - so "€1,200 total" and "€1,200." read as the same figure.
MONEY_RE = re.compile(r"(?:[€$]|EUR)\s?-?\d(?:[\d.,]*\d)?(?:\s?[kK]\b)?"
                      r"|-?\d(?:[\d.,]*\d)?\s?(?:%|[kK]\b)")
LEDGER_EXEMPT_RE = re.compile(
    r"(?:^|[-_. ])(?:log|usage|review|digest|ledger|transcript)s?(?:[-_. ]|$)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<![\w.,/+-])(?<!\d[ ./-])"
                      r"(?:\+\d{1,3}(?:[ ./-]?\(0\))?(?:[ ./-]?\d+)+|0\d{1,4}(?:[ ./-]\d+)+)"
                      r"(?!\w|[ ./-]\d)")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
REFERENCE_LABEL_RE = re.compile(r"(?:\b(?:r[eé]f|nr|no)\b\.?|n°|#)\s*:?\s*$", re.IGNORECASE)


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


def is_frozen_record(path):
    """The frozen-record marker phase1-structural.md Step 1.2b names, as plain text in the
    file's first fifteen live lines; an HTML comment carries it without rendering it."""
    return any(FROZEN_MARKER_RE.search(t) for _, t in live_lines(read_lines(path)[:15]))


def name_only_lines(path):
    """{line: row text with every cell under a `Contact` column blanked}, for each table row
    in `path`: a lifecycle register's column the sales add-on declares a name, not a link."""
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
            "" if i < len(header) and header[i] == "contact" else c
            for i, c in enumerate(cells)) + " |"
    return out


def phone_matches(text):
    """Phone-shaped runs in `text`: a `+` and 8 to 15 digits, or a trunk `0` and 9 to 11 in
    two groups or more, never part of a longer number (`2000 01234`), an IBAN, or a number
    after a reference label (`ref.`, `nr`, `#`). Run on the line link_targets_stripped()
    produces, so a date or a path segment inside a link target is never a phone."""
    text = IBAN_RE.sub(lambda m: " " * len(m.group(0)), text)
    out = []
    for m in PHONE_RE.finditer(text):
        digits = len(re.sub(r"\D", "", m.group(0)))
        if REFERENCE_LABEL_RE.search(text[:m.start()]):
            continue
        if 8 <= digits <= 15 if m.group(0)[0] == "+" else 9 <= digits <= 11:
            out.append(m.group(0))
    return out


def contact_cards(vault):
    """Every person's card in areas/network/, without the folder's README or actions."""
    return [c for c in sorted((vault / "areas" / "network").glob("*.md"))
            if c.name.lower() not in NOT_CARDS]


# --------------------------------------------------------------------------- preconditions

def triage_precondition(vault):
    items = triage_items(vault)
    return {"triage_loose": sorted(i for i in items if i != "README.md"),
            "triage_readme": "README.md" in items}


def marker_precondition(vault, clone, ref):
    """The vault's template marker against the master's at a committed ref, read through
    the library's `master_template` as /para-upgrade reads it. `ref_missing` is a clone
    whose ref does not resolve: one made before releases moved to `stable`, where the ref
    is the default."""
    vault_marker = template_marker(read_text(vault / "CLAUDE.md"))
    master_marker = None
    clone, _ = find_clone(clone)

    if clone:
        master_marker = master_template(clone, ref)["marker"]

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

    return {"vault": vault_marker, "master": master_marker, "verdict": verdict,
            "ref_missing": bool(clone) and clone_ref(clone, ref) is None}


def preconditions(vault, clone, ref):
    return {**triage_precondition(vault), "template_marker": marker_precondition(vault, clone, ref)}


# ------------------------------------------------------------------------------------ map

def empty_leaf_dirs(vault):
    out = []
    for d in vault_paths(vault):
        if not d.is_dir():
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

def placeholder_files(vault):
    """The root CLAUDE.md and README.md: the only vault files the kit writes `{{...}}` into."""
    return [f for f in (vault / "CLAUDE.md", vault / "README.md") if f.is_file()]


def find_placeholders_in(files, vault):
    out = []
    for f in files:
        text = strip_code(read_text(f))
        for lineno, line in enumerate(split_lines(text), start=1):
            if "{{" in line:
                out.append({"file": f.relative_to(vault).as_posix(), "line": lineno,
                            "text": line.strip()})
    return out


# --------------------------------------------------------------------------- wikilinks

def build_md_index(vault):
    """{norm(filename): [paths]} - folded the way norm() folds a folder name, so a wikilink
    written as the note's display title ([[Jan Claes]]) resolves against a kebab-case
    filename (jan-claes.md) the way the vault's own naming convention expects."""
    index = {}
    for p in vault_paths(vault, "*.md"):
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


def find_wikilinks(vault):
    index = build_md_index(vault)
    out = []
    for path in link_files(vault, LINK_ROOTS):
        text = strip_code(read_text(path))
        for lineno, line in enumerate(split_lines(text), start=1):
            for m in WIKILINK_RE.finditer(line):
                target = m.group(1).strip()
                display = m.group(2).strip() if m.group(2) else None
                matches = wikilink_matches(vault, index, target)
                resolved = sorted(matches)[0].relative_to(vault).as_posix() if matches else None
                out.append({"file": path.relative_to(vault).as_posix(), "line": lineno,
                            "target": target, "display": display, "resolved": resolved})
    return out


# ------------------------------------------------------------------------ contact cards

def link_targets(path):
    """Every file a link anywhere in `path` resolves to: a link to the card cites every
    mention in the file, on whatever line it sits and whatever form of the name it uses."""
    return {resolve_link(path, href) for _, href, _ in extract_links(strip_code(read_text(path)))}


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


def principal_cards(vault):
    """The cards the root README's identity section links to, as absolute paths."""
    readme = vault / "README.md"
    if not readme.is_file():
        return set()
    return {resolve_link(readme, href)
            for _, href, _ in extract_links(strip_code(identity_section(readme)))}


def top_level_area_readme(vault, card_rel):
    parts = Path(card_rel).parts
    if len(parts) >= 2:
        candidate = vault / parts[0] / parts[1] / "README.md"
        if candidate.is_file():
            return candidate.relative_to(vault).as_posix()
    return "README.md"


def uncited_contacts(vault, excluded_dirs=()):
    """Every carded person named in a live file with no link to their card, minus what
    phase1-structural.md exempts: resources/prompts/ and `excluded_dirs` (declared template
    and sync-output folders), a file carrying the frozen-record marker, and a Contact cell
    in a register a declared lifecycle keeps its rows in. Returns (cards, exempt): `cards` is
    the finding, one entry per card with the files that named it uncited; `exempt` is every
    file a mention was found in but dropped as a ledger record, so the skill can override
    the proxy."""
    cards = contact_cards(vault)
    if not cards:
        return [], []
    excluded = ("resources/prompts", *excluded_dirs)
    registers = {s["home"].strip("/") for lc in lifecycles(vault) for s in lc["stages"] if s["row"]}
    blanked = {rel: name_only_lines(vault / rel) for rel in registers if (vault / rel).is_file()}
    frozen, targets = {}, {}
    out, exempt = [], set()
    named_on_card = {card: contact_names(card) for card in cards}
    hits_by_name = inbound_references_by_name(vault, {n for ns in named_on_card.values() for n in ns})
    principals = principal_cards(vault)
    for card, names in named_on_card.items():
        card_rel = card.relative_to(vault).as_posix()
        if not names:
            continue
        card_target = abspath(card)
        allowed = {top_level_area_readme(vault, card_rel)} if card_target in principals else None

        named = set()
        for name in names:
            pattern = whole_word(name)
            for hit in hits_by_name[name]:
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
                if mentioned:
                    named.add(hit["file"])

        uncited = []
        for f in sorted(named):
            if f not in targets:
                targets[f] = link_targets(vault / f)
            if card_target not in targets[f]:
                uncited.append(f)
        if uncited:
            out.append({"card": card_rel, "name": names[0], "files": uncited})
    return out, sorted(exempt)


def inline_contact_details(vault):
    """Every email or phone detail on a live line naming at least one carded person,
    reported once per detail with every carded name on the line: phase1-structural.md
    forbids assigning a detail to whoever shares its line, so this reports `names_on_line`
    and leaves the assignment to the skill. Matched on the line with inline code spans blanked and every link target
    stripped and percent-decoded, so a path or a code sample never reads as a detail."""
    cards = contact_cards(vault)
    if not cards:
        return []
    names_by_card, patterns = {}, {}
    for card in cards:
        card_rel = card.relative_to(vault).as_posix()
        for name in contact_names(card):
            names_by_card[name] = card_rel
            patterns[name] = whole_word(name)

    out = []
    for path in vault_paths(vault, "*.md"):
        rel = path.relative_to(vault).as_posix()
        if "sources" in Path(rel).parts[:-1] or not in_live_scope(rel):
            continue
        body = read_text(path)
        code_stripped = split_lines(strip_code(body))
        for lineno, text in live_lines(split_lines(body)):
            uncoded = code_stripped[lineno - 1] if lineno - 1 < len(code_stripped) else text
            clean = link_targets_stripped(uncoded)
            details = [m.group(0) for m in EMAIL_RE.finditer(clean)] + phone_matches(clean)
            names_on_line = details and sorted({n for n, c in names_by_card.items()
                                                if c != rel and patterns[n].search(clean)})
            for detail in details if names_on_line else ():
                out.append({"file": rel, "line": lineno, "text": text.strip(),
                            "names_on_line": names_on_line, "detail": detail.strip()})
    return out


# ------------------------------------------------------------------------------ duplicates

def archive_entities(vault):
    """Every archived entity folder. One straight under `archive/` is an entity archived
    whole when it holds a `brief.md` or a `README.md` with a `**Status:**` line; any other is
    a bucket whose subfolders are the entities. `meetings/` holds records, not entities."""
    archive, out = vault / "archive", []
    tops = sorted(d for d in archive.iterdir() if d.is_dir()) if archive.is_dir() else []
    for top in (d for d in tops if d.name != "meetings"):
        readme = top / "README.md"
        if (top / "brief.md").is_file() or (readme.is_file()
                                            and field_ci(header_fields(readme), "status")):
            out.append(top)
        else:
            out.extend(sorted(d for d in top.iterdir() if d.is_dir()))
    return out


def entity_of_path(rel, whole=()):
    """`whole` names the folders straight under `archive/` that are one entity each."""
    parts = Path(rel).parts
    if not parts:
        return rel
    if parts[0] == "archive" and len(parts) >= 3:
        return "/".join(parts[:2 if parts[1] in whole else 3])
    if parts[0] == "resources" and len(parts) >= 3 and parts[1] == "ideas":
        return "/".join(parts[:3])
    if parts[0] in ("projects", "areas") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def duplicate_report(vault):
    digests = hashes(vault, shared=True)
    whole = {d.name for d in archive_entities(vault) if d.parent == vault / "archive"}
    groups = duplicates(digests)
    out = [{"files": g, "cross_entity": len({entity_of_path(p, whole) for p in g}) > 1}
           for g in groups]
    return {"groups": out, "skipped": digests["skipped"]}


# --------------------------------------------------------------------------- figure pairs

def figures_in_line(line):
    return sorted(set(MONEY_RE.findall(line)))


def entity_names(vault):
    return sorted({c["label"] for c in entity_candidates(vault, ENTITY_BASES)})


def rollup_files(vault):
    files = [vault / "README.md"]
    for bucket in ("projects", "areas", "resources", "archive"):
        p = vault / bucket / "README.md"
        if p.is_file():
            files.append(p)
    for path in vault_paths(vault, "*.md"):
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
                    doc = entity_doc(folder)
                    if doc:
                        figs = set()
                        for line in split_lines(strip_code(read_text(doc))):
                            figs.update(figures_in_line(link_targets_stripped(line)))
                    break
            brief_cache[name] = figs
        return brief_cache[name]

    out = []
    for path in rollup_files(vault):
        text = strip_code(read_text(path))
        for lineno, raw_line in enumerate(split_lines(text), start=1):
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

def owning_entity(vault, path):
    """The one live entity a meeting record belongs to: its `**Project:**` line, else every
    link into an entity folder naming the same one. None for several or none."""
    project = field_ci(header_fields(path), "project")
    if project and not extract_links(project):
        found = resolve_entity(vault, project)
        return found["match"]["path"] if found["status"] == "resolved" else None
    owners = set()
    for _, href, _ in extract_links(project or read_text(path)):
        entity = entity_of_path(rel_posix(vault, resolve_link(path, href)))
        if entity.startswith(("projects/", "areas/", "resources/ideas/")) \
                and (vault / entity).is_dir():
            owners.add(entity)
    return owners.pop() if len(owners) == 1 else None


def archive_findings(vault, dated_pattern):
    archive = vault / "archive"
    loose_root_files, meetings_naming, missing_record, single_owner = [], [], [], []
    if archive.is_dir():
        loose_root_files = sorted(p.relative_to(vault).as_posix()
                                  for p in archive.iterdir() if p.is_file())
        meetings = archive / "meetings"
        if meetings.is_dir():
            pattern = re.compile(dated_pattern)
            meetings_naming = sorted(p.relative_to(vault).as_posix()
                                     for p in meetings.iterdir()
                                     if p.is_file() and p.name != "README.md" and not pattern.match(p.name))
            for p in sorted(meetings.glob("*.md")):
                owner = p.name != "README.md" and owning_entity(vault, p)
                if owner:
                    single_owner.append({"file": p.relative_to(vault).as_posix(),
                                         "entity": owner})
        missing_record = [d.relative_to(vault).as_posix() for d in archive_entities(vault)
                          if not (d / "brief.md").is_file() and not (d / "README.md").is_file()]
    return {"loose_root_files": loose_root_files, "meetings_naming": meetings_naming,
            "missing_record": missing_record, "single_owner": single_owner,
            "misplaced_checkboxes": misplaced_checkboxes(vault, with_closed=True)}


def misplaced_files(found):
    """Every file the misplaced-checkbox report names, open and closed lists alike."""
    rows = [r for b, rs in found.items() if b != "closed" for r in rs]
    return {r["file"] for r in rows + [r for rs in found.get("closed", {}).values() for r in rs]}


def resources_loose(vault):
    """Files at the resources root beside its index: each belongs in a kind folder or with
    the area or project it serves."""
    root = vault / "resources"
    if not root.is_dir():
        return []
    return sorted(p.relative_to(vault).as_posix() for p in root.iterdir()
                  if p.is_file() and p.name not in ("README.md", ".gitkeep"))


def stale_drafts(vault):
    out = []
    for path in vault_paths(vault):
        if path.is_file() and path.suffix.lower() in (".doc", ".docx"):
            pdf = path.with_suffix(".pdf")
            if pdf.is_file():
                out.append({"draft": path.relative_to(vault).as_posix(),
                            "pdf": pdf.relative_to(vault).as_posix()})
    return out


# `name (1).ext`, a `conflicted copy` in parentheses, and a `.sync-conflict-...` stem suffix.
CONFLICT_RE = re.compile(r" \((?:\d+|[^)]*conflicted copy[^)]*)\)(?=\.[^.]*$|$)"
                         r"|\.sync-conflict-[\w-]+(?=\.[^.]*$|$)", re.IGNORECASE)
# A machine name as a sync client appends it, `-DESKTOP7`: uppercase, so a hyphenated name a
# person chose (`invoice-signed`, `report-v2`) never reads as one.
MACHINE_RE = re.compile(r"[A-Z0-9-]*[A-Z][A-Z0-9-]*")


def unconflicted(folder, name):
    """`name` less its conflict pattern, or None where it carries none. A machine suffix
    counts only beside the file it would leave."""
    clean = CONFLICT_RE.sub("", name)
    if clean != name:
        return clean
    stem, dot, ext = name.rpartition(".") if "." in name else (name, "", "")
    parts = stem.split("-")
    for i in range(1, len(parts)):
        clean = "-".join(parts[:i]) + dot + ext
        if MACHINE_RE.fullmatch("-".join(parts[i:])) and (folder / clean).exists():
            return clean
    return None


def conflict_copies(vault):
    """A sync client's conflict copies anywhere in the vault, as `{copy, survivor, empty}`:
    every file or folder whose name carries a conflict pattern, and every zero-byte file
    under such a folder whose path, less the pattern, is a non-empty file. `survivor` is
    that path where it exists, else None."""
    out = []
    for path in vault_paths(vault):
        rel = path.relative_to(vault)
        clean = []
        for part in rel.parts:
            clean.append(unconflicted(vault.joinpath(*clean), part) or part)
        survivor = vault.joinpath(*clean)
        if survivor == path:
            continue
        empty = path.is_file() and path.stat().st_size == 0
        if clean[-1] != rel.name or (empty and survivor.is_file() and survivor.stat().st_size):
            out.append({"copy": rel.as_posix(),
                        "survivor": survivor.relative_to(vault).as_posix()
                        if survivor.exists() else None, "empty": empty})
    return out


# ----------------------------------------------------------------------------------- phase 1

def unmarked_scripts(vault):
    """Each script under resources/scripts/ that carries no `para-os-integration:` marker,
    beside the marked ones, so the skill can judge whether one reads a source an
    integration or a connector row already covers."""
    marked = integration_markers(vault)
    names = {m["file"] for m in marked}
    folder = vault / "resources" / "scripts"
    unmarked = sorted(rel_posix(vault, p) for p in folder.rglob("*") if p.is_file()
                      and p.suffix.lower() in MARKED_SUFFIXES
                      and rel_posix(vault, p) not in names) if folder.is_dir() else []
    return {"marked": [{"file": m["file"], "name": m["name"]} for m in marked],
            "unmarked": unmarked}


def phase1(vault, templates_dirs, dated_pattern, generated_dirs=()):
    touched = set()

    map_ = phase1_map(vault)

    ph_files = placeholder_files(vault)
    placeholders = find_placeholders_in(ph_files, vault)
    touched |= set(ph_files)

    dangling = dangling_links(vault, DANGLING_ROOTS)
    touched |= {vault / d["file"] for d in dangling}

    wikilinks = find_wikilinks(vault)
    touched |= {vault / w["file"] for w in wikilinks}

    uncited, uncited_exempt = uncited_contacts(vault, (*templates_dirs, *generated_dirs))
    touched |= {vault / c["card"] for c in uncited}
    touched |= {vault / f for c in uncited for f in c["files"]}
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
    touched |= {vault / f for f in misplaced_files(archive["misplaced_checkboxes"])}

    res_loose = resources_loose(vault)
    touched |= {vault / f for f in res_loose}

    drafts = stale_drafts(vault)
    touched |= {vault / d["draft"] for d in drafts}

    conflicts = conflict_copies(vault)
    touched |= {vault / p for c in conflicts for p in (c["copy"], c["survivor"])
                if p and (vault / p).is_file()}

    scripts = unmarked_scripts(vault)
    touched |= {vault / f for f in scripts["unmarked"]}

    return {"map": map_, "placeholders": placeholders, "dangling": dangling,
            "wikilinks": wikilinks, "uncited_contacts": uncited,
            "uncited_exempt": uncited_exempt, "inline_contact_details": inline_details,
            "duplicates": dup, "figure_pairs": figs, "archive": archive,
            "resources_loose": res_loose, "stale_drafts": drafts,
            "conflict_copies": conflicts, "scripts": scripts,
            "snapshot": snapshot(sorted(touched, key=str))}


# ----------------------------------------------------------------------------------- phase 3

def over_threshold_from(files, vault):
    out = [{"file": f.relative_to(vault).as_posix(), "open": cap_count(open_tasks(f))}
           for f in files]
    out = [r for r in out if r["open"] > OPEN_ITEM_CAP]
    return sorted(out, key=lambda r: -r["open"])


def other_checkbox_files(vault, paths):
    """`other_checkbox_paths()` as the report: a count per file. Whether the file states
    its own shape is the skill's read of its header, never this script's."""
    return [{"file": p.relative_to(vault).as_posix(), "open": len(open_tasks(p))}
            for p in paths]


def stale_undated_from(vault, files, today):
    """Each open, undated item untouched for STALE_UNDATED_DAYS, measured on its own line by
    `git blame -L`, which follows the line's content through history rather than its
    current line number - a `git log -L` query loses a more recent edit once something
    else in the file shifts where the item sits - where the file is tracked, else the
    file's mtime, else unmeasurable, said per item, never for the whole run, so a git-less
    vault still gets a real answer for the files whose mtime is trustworthy. A line git
    blame reports as still uncommitted counts as unmeasurable rather than as a fabricated
    date."""
    out = {}
    listed = set((git(vault, ["ls-files", "-z"]) or "").split("\0"))
    for f in files:
        rel = f.relative_to(vault).as_posix()
        tracked = rel in listed
        items = []
        for t in open_tasks(f):
            if t["due"] or t["scheduled"] or t["start"]:
                continue
            entry = {"line": t["line"], "text": t["text"]}
            stamp, reason = line_date(vault, f, t["line"], tracked)
            if not stamp:
                items.append(dict(entry, unmeasurable=reason))
            elif (today - parse_date(stamp)).days >= STALE_UNDATED_DAYS:
                items.append(dict(entry, days=(today - parse_date(stamp)).days))
        if items:
            out[rel] = items
    return out


def line_date(vault, f, line, tracked):
    """(date, why there is none) for one line: blame where the file is tracked, else its mtime."""
    if tracked:
        blame = git_blame_line_date(vault, f, line)
        if blame == "uncommitted":
            return None, "line not yet committed"
        return blame, None if blame else "tracked, but git blame returned no date for this line"
    try:
        return date.fromtimestamp(f.stat().st_mtime).isoformat(), None
    except OSError:
        return None, "untracked, and the file's mtime could not be read"


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


def lines_at(vault, rel, day):
    """A file's line count in the last commit on or before `day`, else None."""
    sha = (git(vault, ["log", "-1", "--format=%H", f"--before={iso(day)}T23:59:59", "--", rel])
           or "").strip()
    text = git(vault, ["show", f"{sha}:{rel}"]) if sha else None
    return None if text is None else len(split_lines(text))


def briefs(vault):
    """(briefs to read, each with its reasons; live briefs skipped; whether growth since the
    last deep clean could be measured). A brief is read when it is over the line cap, has
    grown by more than half since the last deep clean's stamp, or holds more development-log
    entries than its entity has open actions. An area README is read whatever it holds, so
    one is never listed as skipped."""
    stamp = deep_clean_stamp(vault)
    last = parse_date(read_text(stamp).strip()) if stamp.is_file() else None
    growth = "no deep clean on record" if last is None else \
        "measured" if git(vault, ["rev-parse", "--git-dir"]) is not None else "no git history"
    over = {b["file"] for b in over_grown_briefs(vault)}
    read, skipped = [], []
    for path in live_briefs(vault):
        rel = path.relative_to(vault).as_posix()
        lines = len(read_lines(path))
        reasons = ["over_grown"] if rel in over else []
        if growth == "measured" and lines > GROWN * (lines_at(vault, rel, last) or lines):
            reasons.append("grown")
        actions = path.parent / "actions.md"
        if len(log_entries(path)) > len(open_tasks(actions) if actions.is_file() else []):
            reasons.append("log_heavy")
        if reasons:
            read.append({"file": rel, "lines": lines, "reasons": reasons})
        elif not (rel.startswith("areas/") and path.name == "README.md"):
            skipped.append(rel)
    return sorted(read, key=lambda r: -r["lines"]), skipped, growth


def orphans(vault):
    """Files under projects/, areas/ or resources/ that no link anywhere in the vault reaches:
    `files`, percent-decoded, or in `folders` only the count of an entity past ORPHANS_LISTED.
    A README, brief or actions file is reached by its folder, a `sources/` file or a ledger is
    a record, and `scripts/` and `__pycache__` hold code, so none is listed."""
    reached = {abspath(resolve_link(f, href)) for f in link_files(vault, DANGLING_ROOTS)
               for _, href, _ in extract_links(read_text(f))}
    found = {}
    for bucket in ("projects", "areas", "resources"):
        for path in (vault / bucket).rglob("*"):
            rel = path.relative_to(vault)
            if path.is_file() and path.name not in STRUCTURE_FILES \
                    and not {"sources", "scripts", "__pycache__"} & set(rel.parts) \
                    and not any(p.startswith(".") for p in rel.parts) \
                    and not is_ledger_exempt(rel) and abspath(path) not in reached:
                found.setdefault("/".join(rel.parts[:2]), []).append(rel.as_posix())
    listed = [f for files in found.values() if len(files) <= ORPHANS_LISTED for f in files]
    return {"files": sorted(listed), "folders": {entity: len(files) for entity, files
                                                 in sorted(found.items())
                                                 if len(files) > ORPHANS_LISTED}}


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
    next-steps headings in every live brief: such a vault keeps its next steps there."""
    if vault_paths(vault, "actions.md"):
        return {"applicable": False, "items": []}
    items = []
    for f in live_briefs(vault):
        items += bullets_under_headings(f, headings, vault)
    return {"applicable": True, "items": items}


def newest_dated_action(folder):
    """The newest date any checkbox in an entity's folder carries, open or ticked, on any
    marker: a closed item dated last spring is still the last commitment the project made.
    `sources/` is other people's documents, never the project's own commitments."""
    newest = None
    for path in sorted(folder.rglob("*.md")):
        if "sources" in path.relative_to(folder).parts:
            continue
        for _, text in live_lines(read_lines(path)):
            if not (TASK_RE.match(text) or CLOSED_TASK_RE.match(text)):
                continue
            for raw in ANY_DATE_RE.findall(text):
                d = parse_date(raw)
                if d and (newest is None or d > newest):
                    newest = d
    return newest


def demotion_candidates(vault, today):
    """Projects whose newest dated action is DORMANT_ENTITY_DAYS or more old: the Lifecycle
    rule's "no dated commitment left for six months". A project with no dated action at all
    is the sorting test's problem, not this one's, and a staged entity (a deal, a property)
    moves through its lifecycle, never to an area, so neither is listed."""
    declared = {s["name"].lower() for lc in lifecycles(vault) for s in lc["stages"]}
    out = []
    for folder in sorted(p for p in (vault / "projects").glob("*") if p.is_dir()):
        brief = next((folder / n for n in ("brief.md", "README.md") if (folder / n).is_file()), None)
        stage = stage_of(brief) if brief else None
        if stage and stage["name"].lower() in declared:
            continue
        newest = newest_dated_action(folder)
        if newest and (today - newest).days >= DORMANT_ENTITY_DAYS:
            out.append({"project": folder.relative_to(vault).as_posix(),
                        "newest_date": iso(newest)})
    return out


def phase3(vault, today, headings):
    files = action_files(vault)
    other_paths = other_checkbox_paths(vault)
    over_threshold = over_threshold_from(files + other_paths, vault)
    other_files = other_checkbox_files(vault, other_paths)
    stale_undated = stale_undated_from(vault, files + other_paths, today)
    aspirational = aspirational_from(files + other_paths, vault, today)
    prose = prose_next_steps(vault, headings)
    briefs_to_read, briefs_skipped, growth = briefs(vault)

    touched = set(files) | set(other_paths)
    touched |= {vault / b["file"] for b in briefs_to_read}
    if prose["applicable"]:
        touched |= {vault / it["file"] for it in prose["items"]}

    return {"over_threshold": over_threshold, "other_checkbox_files": other_files,
            "stale_undated": stale_undated, "aspirational": aspirational,
            "prose_next_steps": prose, "briefs_to_read": briefs_to_read,
            "briefs_skipped": briefs_skipped, "growth": growth, "orphans": orphans(vault),
            "demotion_candidates": demotion_candidates(vault, today)
            if (vault / "projects").is_dir() else [],
            "snapshot": snapshot(sorted(touched, key=str))}


# ----------------------------------------------------------------------------------- phase 4

def phase4(vault, templates_dirs, dated_pattern, today, generated_dirs=()):
    touched, rows = set(), []

    mc = misplaced_checkboxes(vault, with_closed=True)
    touched |= {vault / f for f in misplaced_files(mc)}
    rows.append({"check": "misplaced_checkboxes", "pass": not misplaced_files(mc), "detail": mc})

    tri = triage_precondition(vault)
    triage_ok = not tri["triage_loose"] and not tri["triage_readme"]
    rows.append({"check": "triage_empty", "pass": triage_ok, "detail": tri})

    empties = empty_leaf_dirs(vault)
    rows.append({"check": "no_empty_leaf_dirs", "pass": not empties, "detail": empties})

    arch = archive_findings(vault, dated_pattern)
    archive_clean = not (arch["loose_root_files"] or arch["meetings_naming"] or arch["missing_record"])
    touched |= {vault / f for f in arch["loose_root_files"] + arch["meetings_naming"] + arch["missing_record"]}
    rows.append({"check": "archive_clean", "pass": archive_clean, "detail": arch})

    res_loose = resources_loose(vault)
    touched |= {vault / f for f in res_loose}
    rows.append({"check": "resources_clean", "pass": not res_loose, "detail": res_loose})

    dangling = dangling_links(vault, DANGLING_ROOTS)
    touched |= {vault / d["file"] for d in dangling}
    rows.append({"check": "dangling_links", "pass": not dangling, "detail": dangling})

    ph_files = placeholder_files(vault)
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

    # Candidates only, pass: None - SKILL.md's Phase 4 lists contact citation and detail
    # attribution among what this phase re-verifies, and the verdict (real defect, or a
    # legitimate exemption) is the skill's, not this script's.
    uncited, uncited_exempt = uncited_contacts(vault, (*templates_dirs, *generated_dirs))
    touched |= {vault / c["card"] for c in uncited}
    touched |= {vault / f for c in uncited for f in c["files"]}
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
         generated_dirs=()):
    vault = Path(vault).resolve()
    report = {"preconditions": preconditions(vault, clone, ref)}
    if phase == "1":
        report["phase1"] = phase1(vault, templates_dirs, dated_pattern, generated_dirs)
    elif phase == "3":
        report["phase3"] = phase3(vault, today, headings)
        stamp = deep_clean_stamp(vault)
        try:
            stamp.parent.mkdir(parents=True, exist_ok=True)
            stamp.write_text(iso(today) + "\n", encoding="utf-8")
        except OSError:
            pass  # the brief then calls the deep clean due, which is the safe side
    elif phase == "4":
        report["phase4"] = phase4(vault, templates_dirs, dated_pattern, today, generated_dirs)
    return report, 0


INVENTORY = ("map/top_level", "uncited_exempt", "duplicates/skipped", "scripts/marked")


def item_count(value, path=""):
    if path in INVENTORY:
        return 0
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(item_count(v, f"{path}/{k}") for k, v in value.items())
    return 0


def finding_counts(block):
    """How many findings each key of a phase's report holds: each Phase 4 check that failed,
    else the items of its lists at any depth, less the INVENTORY Phase 1 reports beside them."""
    rows = (block or {}).get("rows")
    if isinstance(rows, list):
        return {r["check"]: max(1, item_count(r["detail"])) for r in rows if r["pass"] is False}
    counts = {key: item_count(value, key) for key, value in (block or {}).items()}
    return {key: n for key, n in counts.items() if n}


def record_findings(vault, today, phase, report):
    """The phase's findings count beside the deep-clean stamp, `<vault>.audit.json`, for the
    brief's health card; a write that fails is nothing the scan reports on."""
    counts = finding_counts(report.get(f"phase{phase}"))
    record = deep_clean_stamp(vault).with_suffix(".audit.json")
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps({"date": iso(today), "phase": phase, "findings": counts,
                                      "total": sum(counts.values())}) + "\n", encoding="utf-8")
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan a vault for /para-deep-clean's mechanical checks.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--phase", required=True, choices=["1", "3", "4"], help="which phase to scan")
    ap.add_argument("--today", type=date_arg, help="date to measure against (default: the system date)")
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
    ap.add_argument("--dated-pattern", default=DEFAULT_DATED_PATTERN,
                    help=f"naming pattern archive/meetings/ files must match "
                         f"(default: {DEFAULT_DATED_PATTERN!r})")
    ap.add_argument("--next-steps-heading", action="append", default=[], metavar="HEADING",
                    help="a heading whose bullets count as prose next steps for a vault with "
                         "no actions.md (repeatable, default: Next steps, Open items)")
    ap.add_argument("--indent", type=int, default=None, help="pretty-print the JSON")
    ap.add_argument("--record", action="store_true",
                    help="also write the phase's findings count beside the deep-clean stamp "
                         "under $PARAOS_HOME, for the brief's health card")
    args = ap.parse_args(argv)

    utf8_stdout()

    today = args.today or date.today()
    root = Path(args.vault)
    if not root.is_dir():
        ap.error(f"no such vault: {root}")
    headings = args.next_steps_heading or list(DEFAULT_NEXT_STEPS_HEADINGS)

    report, code = scan(root, today, args.phase, args.ref, args.clone,
                        args.templates_dir, args.dated_pattern, headings,
                        args.generated_dir)
    if args.record:
        record_findings(root, today, args.phase, report)

    emit(report, args.indent)
    return code


if __name__ == "__main__":
    sys.exit(main())
