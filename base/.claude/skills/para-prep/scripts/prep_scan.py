#!/usr/bin/env python3
"""The mechanical half of /para-prep, as a script instead of instructions.

    py -3 prep_scan.py --vault <path> --person <who> [--person <who>]... [--today YYYY-MM-DD]
                       [--indent N]
    python3 prep_scan.py --vault <path> --person "Jan Janssen <jan@example.com>"

`<who>` is a name, an email address, or both the way a calendar writes them
(`Name <address>`). A parenthetical is dropped (`Ann Peeters (Acme)`), and `Last, First`
reads as one name.

Prints one JSON document: for each person, the contact card they match and how, the open
items on that card, the open items naming them in any other action file, the newest records
naming them and the register rows naming them; and once for every entity a matched card
links, or whose brief links the card, its stage against the vault's declared lifecycles, its
header, its do-not-raise list, its open count and its newest source. It never writes to the
vault, never words anything an operator reads, and never decides what matters for a meeting:
that stays with the skill, per references/gather.md and references/output.md.

Reading the vault's primitives (a card's names, header fields, Stage lines, lifecycle
tables, register rows, open tasks, links) is para-shared/scripts/paraos_vault.py's. What
lives here is what this skill alone decides: which card a person is, which entities and
records belong to them, and which open items name them.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

SHARED_DIR = Path(__file__).resolve().parents[2] / "para-shared" / "scripts"
if SHARED_DIR.is_dir() and str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    from paraos_vault import (  # noqa: E402
        EMAIL_RE, H1_RE, HEADING_RE, abspath, action_files, contact_card_level, contact_names,
        extract_links, field_ci, header_fields, lifecycles, live_lines, open_tasks, parse_date,
        read_lines,
        read_text, register_rows, rel_posix, resolve_link, stage_of, stage_parts, strip_code,
        vault_root,
    )
except ImportError as missing:  # the skill falls back to gathering by hand
    print(f"prep_scan: {missing}. The shared vault library belongs at "
          f"{SHARED_DIR}/paraos_vault.py: install para-shared beside this skill, or gather "
          f"by hand with references/gather.md", file=sys.stderr)
    sys.exit(2)

CARD_DIR = ("areas", "network")
NOT_CARDS = {"readme.md", "actions.md"}
ENTITY_BUCKETS = ("projects", "areas", "resources/ideas")
TEXT_SUFFIXES = {".md", ".txt", ".eml"}
RECORDS_SHOWN = 5        # newest first; the total says how many more there are
SHORT_NAME_MIN = 3       # a shorter word is an initial or a particle, never a name
DATE_PREFIX_RE = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})(?!\d)")
DO_NOT_RAISE_RE = re.compile(r"\bdo\s+not\s+raise\b", re.IGNORECASE)
LABEL_RE = re.compile(r"^\*\*\s*do\s+not\s+raise\s*:?\s*\*\*\s*:?\s*(.*)$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
NAME_SEP = r"[\s,.'-]+"


# --------------------------------------------------------------------------------- names

def fold(text):
    """Lowercase with the accents dropped, so `Desiree` finds `Désirée`."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def tokens(name):
    return re.findall(r"[^\W_]+", fold(name))


def name_key(name):
    """A name with its word order dropped: `Claes, Jan`, `Claes Jan` and `Jan Claes` are one."""
    return tuple(sorted(tokens(name)))


def parse_person(raw):
    """A --person value as (name, email), either None where the value does not carry it."""
    found = EMAIL_RE.search(raw)
    email = found.group(0).lower() if found else None
    name = re.sub(r"\([^)]*\)", " ", EMAIL_RE.sub(" ", raw))
    name = " ".join(re.sub(r'[<>"]', " ", name).split()).strip(" ,;")
    return (name or None), email


def name_pattern(name):
    """A whole name in folded text, in any rotation of its words, so a card titled
    `Pieter De Ryck` is found written `De Ryck, Pieter`. None for a one-word name."""
    words = tokens(name)
    if len(words) < 2:
        return None
    forms = [NAME_SEP.join(map(re.escape, words[i:] + words[:i])) for i in range(len(words))]
    return re.compile(r"(?<![\w-])(?:" + "|".join(forms) + r")(?![\w-])")


def title(path):
    for _, text in live_lines(read_lines(path)):
        m = H1_RE.match(text.strip())
        if m:
            return m.group(1).strip()
    return None


def same_target(path):
    return os.path.normcase(str(abspath(path)))


# --------------------------------------------------------------------------------- cards

def read_cards(vault):
    """Every contact card under areas/network/, with the names it answers to: its H1, its
    aliases, and its file name read as words, which is how a card named last-name first, or
    titled with a first name alone, still answers to the whole name."""
    base = vault.joinpath(*CARD_DIR)
    if not base.is_dir():
        return []
    cards = []
    for path in sorted(base.rglob("*.md")):
        if path.name.lower() in NOT_CARDS:
            continue
        h1 = title(path)
        aliases = [n for n in contact_names(path) if n != h1]
        names, seen = [], set()
        for n, by in ([(h1, "name")] if h1 else []) + [(a, "alias") for a in aliases] + \
                [(path.stem.replace("-", " ").replace("_", " "), "name")]:
            if name_key(n) and name_key(n) not in seen:
                seen.add(name_key(n))
                names.append((n, by))
        text = "\n".join(t for _, t in live_lines(read_lines(path)))
        cards.append({"path": path, "rel": rel_posix(vault, path), "name": h1 or path.stem,
                      "aliases": aliases, "names": names,
                      "emails": sorted({e.lower() for e in EMAIL_RE.findall(text)})})
    return cards


def verdict(hits, by):
    unique = list({c["rel"]: c for c in hits}.values())
    if len(unique) == 1:
        return {"status": "matched", "matched_by": by, "card": unique[0]}
    return {"status": "ambiguous", "matched_by": by,
            "candidates": sorted(c["rel"] for c in unique)}


def match_card(name, email, cards):
    """The card a person is: by an address the card carries; else by a whole name in either
    order, or an alias; else by every word of the name sitting in one card's names; else by
    the name an address's local part spells. Two cards at the first rung that finds any are
    ambiguous, never chosen between."""
    if email:
        hits = [c for c in cards if email in c["emails"]]
        if hits:
            return verdict(hits, "email")
    if name and tokens(name):
        key = name_key(name)
        exact = [(c, by) for c in cards for n, by in c["names"] if name_key(n) == key]
        if exact:
            names_only = [c for c, by in exact if by == "name"]
            return verdict(names_only or [c for c, _ in exact],
                           "name" if names_only else "alias")
        want = set(tokens(name))
        partial = [c for c in cards if any(want <= set(tokens(n)) for n, _ in c["names"])]
        if partial:
            return verdict(partial, "partial")
    if email:
        local = tokens(email.split("@")[0])
        if len(local) >= 2:
            key = tuple(sorted(local))
            hits = [c for c in cards if any(name_key(n) == key for n, _ in c["names"])]
            if hits:
                return verdict(hits, "email_name")
    return {"status": "no_card", "matched_by": None}


def short_names(cards):
    """{card rel: [word]}: the first and last word of a card's title and each one-word alias,
    kept where no other card carries that word in any of its names, and three letters or
    more. Written as on the card, and matched that way, case and all."""
    owners = {}
    for c in cards:
        for n, _ in c["names"]:
            for w in tokens(n):
                owners.setdefault(w, set()).add(c["rel"])
    out = {}
    for c in cards:
        words = c["name"].replace(",", " ").split()
        candidates = {words[0], words[-1]} if words else set()
        candidates |= {a for a in c["aliases"] if len(a.split()) == 1}
        out[c["rel"]] = sorted(w for w in candidates
                               if len(tokens(w)) == 1 and len(w) >= SHORT_NAME_MIN
                               and owners.get(tokens(w)[0]) == {c["rel"]})
    return out


class Who:
    """What says a line is about one person: a link to their card, an address, a whole name
    or alias, or, in an open item only, a one-word name no other card carries."""

    def __init__(self, card_path=None, names=(), emails=(), short=()):
        self.card = same_target(card_path) if card_path else None
        self.full = [(p, by) for p, by in ((name_pattern(n), by) for n, by in names) if p]
        self.emails = list(emails)
        self.short = [re.compile(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])(?!\s+\d)")
                      for w in short]

    @property
    def searchable(self):
        return bool(self.card or self.full or self.emails)

    def by(self, text, from_file, short=True):
        if self.card:
            for _, href, _ in extract_links(text):
                if same_target(resolve_link(from_file, href)) == self.card:
                    return "link"
        folded = fold(text)
        if any(e in folded for e in self.emails):
            return "email"
        for pattern, kind in self.full:
            if pattern.search(folded):
                return kind
        if short and any(p.search(text) for p in self.short):
            return "short name"
        return None


# ------------------------------------------------------------------------------ entities

def entity_of(vault, target):
    """The entity folder a resolved link points into: `projects/<x>`, `areas/<x>` (never
    the network area itself) or `resources/ideas/<x>`. None for anything else."""
    parts = rel_posix(vault, target).split("/")
    if parts[0] == "projects" and len(parts) >= 2:
        rel = "/".join(parts[:2])
    elif parts[0] == "areas" and len(parts) >= 2 and parts[1] != CARD_DIR[1]:
        rel = "/".join(parts[:2])
    elif parts[:2] == ["resources", "ideas"] and len(parts) >= 3:
        rel = "/".join(parts[:3])
    else:
        return None
    return rel if (vault / rel).is_dir() else None


def pick_doc(folder):
    """README.md over brief.md where a folder holds both, the rule /para-pipeline reads by."""
    for name in ("README.md", "brief.md"):
        if (folder / name).is_file():
            return folder / name
    return None


def entity_folders(vault):
    out = []
    for bucket in ENTITY_BUCKETS:
        base = vault / bucket
        if base.is_dir():
            out += [d for d in sorted(base.iterdir())
                    if d.is_dir() and not (bucket == "areas" and d.name == CARD_DIR[1])]
    return out


def linked_entities(vault, card, folders):
    """[(entity path, via)] for the entities the card links and the entities whose brief or
    README links the card back, `via` being `card`, `entity` or `both`."""
    via = {}
    for _, href, _ in extract_links(strip_code(read_text(card["path"]))):
        rel = entity_of(vault, resolve_link(card["path"], href))
        if rel:
            via[rel] = {"card"}
    target = same_target(card["path"])
    for folder in folders:
        doc = pick_doc(folder)
        if doc and any(same_target(resolve_link(doc, href)) == target
                       for _, href, _ in extract_links(strip_code(read_text(doc)))):
            via.setdefault(rel_posix(vault, folder), set()).add("entity")
    return [(rel, "both" if len(v) == 2 else v.pop()) for rel, v in sorted(via.items())]


def home_pattern(home):
    rest = re.sub(r"<[^>]*>", "\0", home.strip().rstrip("/"))
    return re.compile(re.escape(rest).replace("\0", "[^/]+") + r"/?")


def stage_out(parts, lc, stage, today):
    since = parse_date(parts["since"])
    return {
        "lifecycle": lc["heading"], "name": stage["name"], "qualifier": parts["qualifier"],
        "since": parts["since"], "days_in_stage": (today - since).days if since else None,
        "dated_facts": [{"clause": clause, "date": d, "days_ahead": (parse_date(d) - today).days}
                        for clause, d in parts["dated_facts"]],
        "terminal": stage["terminal"], "columns": stage["columns"],
    }


def entity_stage(doc, rel, declared, today):
    """The entity's stage where its Stage line names a declared one, with that stage's row of
    the lifecycle table as written. A name two lifecycles share is read against the one whose
    home holds the entity. None where the line is missing or names no declared stage."""
    parts = stage_of(doc)
    if not parts:
        return None
    hits = [(lc, s) for lc in declared for s in lc["stages"]
            if s["name"].lower() == parts["name"].lower()]
    if not hits:
        return None
    homed = [(lc, s) for lc, s in hits if home_pattern(s["home"]).fullmatch(rel)]
    lc, stage = (homed or hits)[0]
    return stage_out(parts, lc, stage, today)


def do_not_raise(doc):
    """What a brief keeps under a `Do not raise` label: the text after a bold-led label and
    the list directly under it, or everything under a heading of that name."""
    out, mode, level, listed = [], None, 0, 0
    for _, text in live_lines(read_lines(doc)):
        stripped = text.strip()
        heading = HEADING_RE.match(stripped)
        if heading:
            if mode == "heading" and len(heading.group(1)) > level:
                continue
            mode = "heading" if DO_NOT_RAISE_RE.search(heading.group(2)) else None
            level = len(heading.group(1))
            continue
        bullet = BULLET_RE.match(text)
        body = bullet.group(1).strip() if bullet else stripped
        label = LABEL_RE.match(body)
        if label:
            mode, listed = "label", int(bool(label.group(1).strip()))
            if listed:
                out.append(label.group(1).strip())
            continue
        if mode == "label" and (not bullet and stripped or not stripped and listed):
            mode = None
        if mode and body:
            out.append(body)
            listed += 1
    return out


def file_date(path):
    m = DATE_PREFIX_RE.match(path.name)
    return parse_date("-".join(m.groups())) if m else None


def newest_source(vault, folder, today):
    """The newest file in an entity's sources/ by the date its name opens on."""
    src = folder / "sources"
    if not src.is_dir():
        return None
    dated = [(file_date(p), p.name, p) for p in src.rglob("*") if p.is_file() and file_date(p)]
    if not dated:
        return None
    day, _, path = max(dated)
    return {"path": rel_posix(vault, path), "date": day.isoformat(),
            "days_ago": (today - day).days}


def earliest(tasks):
    dated = [t for t in tasks if t["due"] or t["scheduled"]]
    if not dated:
        return None
    t = min(dated, key=lambda t: (t["due"] or t["scheduled"], t["line"]))
    return {"line": t["line"], "text": t["text"], "due": t["due"] or t["scheduled"]}


def entity_block(vault, rel, declared, today):
    folder = vault / rel
    doc = pick_doc(folder)
    fields = header_fields(doc) if doc else {}
    actions = folder / "actions.md"
    tasks = open_tasks(actions) if actions.is_file() else None
    return {
        "path": rel, "document": rel_posix(vault, doc) if doc else None,
        "title": (title(doc) if doc else None) or folder.name,
        "stage": entity_stage(doc, rel, declared, today) if doc else None,
        "header": fields,
        "unknown": [k for k, v in fields.items() if v.strip().lower().startswith("unknown")],
        "do_not_raise": do_not_raise(doc) if doc else [],
        "actions": None if tasks is None else {
            "path": rel_posix(vault, actions), "open": len(tasks), "next": earliest(tasks)},
        "newest_source": newest_source(vault, folder, today),
    }


# ------------------------------------------------------------------- what names a person

def task_out(task):
    """An open item as the skill reads it: its marker fields, without the link the
    shared reader keeps for other callers, and `malformed_date` only where it is true."""
    return {k: v for k, v in task.items()
            if k != "first_link" and not (k == "malformed_date" and not v)}


def mentions(vault, tasks, who, card_path=None):
    """Open items in any action file but the person's own card that name them."""
    own = same_target(card_path) if card_path else None
    out = []
    for path, task in tasks:
        if own and same_target(path) == own:
            continue
        by = who.by(task["text"], path)
        if by:
            out.append({"file": rel_posix(vault, path), **task_out(task), "by": by})
    return out


def record_files(vault, roots=None):
    """Every file in a live entity's sources/, and everything under archive/meetings/; or
    every file under the folders `roots` names instead."""
    if roots is None:
        roots = [d for bucket in ENTITY_BUCKETS if (vault / bucket).is_dir()
                 for d in sorted((vault / bucket).rglob("sources")) if d.is_dir()]
        roots += [vault / "archive" / "meetings"]
    files = {p for root in roots if root.is_dir() for p in root.rglob("*")
             if p.is_file() and p.name != ".gitkeep"}
    return [{"path": p, "date": file_date(p),
             "text": strip_code(read_text(p)) if p.suffix.lower() in TEXT_SUFFIXES else ""}
            for p in sorted(files)]


def naming(files, who):
    """(file, by) for each file naming the person: a whole name in its file name, or a link
    to the card, an address, or a whole name or alias inside a text file."""
    found = []
    for f in files:
        by = ("file name" if who.by(f["path"].stem, f["path"], short=False)
              else who.by(f["text"], f["path"], short=False))
        if by:
            found.append((f, by))
    return found


def records(vault, files, who, today):
    """The newest records naming the person, dated by their file names, and how many there
    are in all."""
    found = sorted(naming(files, who), reverse=True,
                   key=lambda fb: (fb[0]["date"] or date.min, fb[0]["path"].name))
    return [{"path": rel_posix(vault, f["path"]), "date": f["date"] and f["date"].isoformat(),
             "days_ago": (today - f["date"]).days if f["date"] else None, "by": by}
            for f, by in found[:RECORDS_SHOWN]], len(found)


def register_hits(vault, declared, who, today):
    """Every row of a declared register that names the person, with its stage as the
    lifecycle table states it."""
    out = []
    for lc in declared:
        homes = []
        for s in lc["stages"]:
            if s["row"] and s["home"] not in homes:
                homes.append(s["home"])
        for home in homes:
            path = vault / home
            if not path.is_file():
                continue
            lines = read_lines(path)
            for row in register_rows(path):
                by = who.by(lines[row["line"] - 1], path, short=False)
                if not by:
                    continue
                stage_text = field_ci(row, "Stage") or ""
                parts = stage_parts(re.sub(r"[*_]", "", stage_text).strip(), stage_text)
                stage = next((s for s in lc["stages"]
                              if s["name"].lower() == parts["name"].lower()), None)
                out.append({
                    "register": rel_posix(vault, path), "line": row["line"],
                    "section": row["section"], "name": row["name"],
                    "closed": (row["section"] or "").strip().lower() == "closed",
                    "stage": stage_out(parts, lc, stage, today) if stage else None,
                    "cells": {k: v for k, v in row.items()
                              if k not in ("name", "section", "line", "cells")},
                    "by": by})
    return out


# ------------------------------------------------------------------------------ the scan

def card_out(card):
    fields = header_fields(card["path"])
    return {"path": card["rel"], "name": card["name"], "aliases": card["aliases"],
            "kind": field_ci(fields, "Kind"), "header": fields, "emails": card["emails"],
            "items": [task_out(t) for t in open_tasks(card["path"])]}


def scan(vault, people, today):
    vault = Path(vault).resolve()
    declared = lifecycles(vault)
    cards = read_cards(vault)
    short = short_names(cards)
    folders = entity_folders(vault)
    tasks = [(path, t) for path in action_files(vault) for t in open_tasks(path)]
    files = record_files(vault)
    unfiled = record_files(vault, [vault / "triage"])
    entities, out = {}, []
    for raw in dict.fromkeys(people):
        name, email = parse_person(raw)
        match = match_card(name, email, cards)
        card = match.pop("card", None)
        person = {"query": raw, "name": name, "email": email, **match}
        if card:
            who = Who(card["path"], card["names"], card["emails"], short[card["rel"]])
            person["card"] = card_out(card)
            person["entities"] = []
            for rel, via in linked_entities(vault, card, folders):
                if rel not in entities:
                    entities[rel] = entity_block(vault, rel, declared, today)
                person["entities"].append({"path": rel, "via": via})
        else:
            who = Who(names=[(name, "name")] if name else (), emails=[email] if email else ())
        # None is "not searched": an ambiguous name, or a one-word name with no card.
        person.update(mentions=None, records=None, records_total=None, unfiled=None, rows=None)
        if match["status"] != "ambiguous" and who.searchable:
            person["mentions"] = mentions(vault, tasks, who, card and card["path"])
            person["records"], person["records_total"] = records(vault, files, who, today)
            person["unfiled"] = [{"path": rel_posix(vault, f["path"]), "by": by}
                                 for f, by in naming(unfiled, who)]
            person["rows"] = register_hits(vault, declared, who, today)
        out.append(person)
    return {"vault": vault.as_posix(), "today": today.isoformat(), "root": vault_root(vault),
            "lifecycles": [lc["heading"] for lc in declared],
            "cards_hold": contact_card_level(vault), "people": out,
            "entities": [entities[k] for k in sorted(entities)]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gather what a vault holds on a meeting's people.")
    ap.add_argument("--vault", default=".", help="vault root (default: current directory)")
    ap.add_argument("--person", action="append", required=True,
                    help="a name, an address, or `Name <address>`; repeat for each attendee")
    ap.add_argument("--today", help="date to measure against (default: the system date)")
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

    json.dump(scan(root, args.person, today), sys.stdout, ensure_ascii=False,
              indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
