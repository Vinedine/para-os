#!/usr/bin/env python3
"""Fold the changelog.d/ fragments into CHANGELOG.md and RELEASES.md under one revision.

    python3 fold_changelog.py <label>
    py -3 fold_changelog.py <label>

A pull request adds one fragment, `changelog.d/<issue>.md`, instead of editing the two files,
so branches open at the same time never conflict over them. The format is in
changelog.d/README.md. The fold:

- appends each fragment's `## Changelog` lines to the end of the `## <label>` section of
  CHANGELOG.md, a `- ` line ending on ` (#<issue>)` where the fragment's name is a number and
  the line names none, and opens that section above the newest one when the label is new;
- appends its one bullet under the `### ` section of the same revision in RELEASES.md that
  the fragment names, and its `## What to do` steps to that revision's numbered list, a step
  opening on `Before you upgrade` above the `/para-upgrade` step and any other below it;
- deletes every fragment it folded. README.md stays.

A RELEASES.md revision is `### ` sections only, in a fixed order (`### Highlights` first,
which the maintainer writes, `### What to do` last), then the link to CHANGELOG.md at the tag.

Every line of a fragment's `## Changelog`, and of a CHANGELOG.md entry, is a `- ` Reaction line
or a `Retired:` line naming backticked paths; `tools/check.py` holds both to that.

Fragments fold in the order git added them on the current branch, which on `main` is the
order their pull requests merged; a fragment not yet committed folds last, by name. Nothing
is written unless every fragment parses and the label is the newest revision in both files or
newer than it.

Standard library only.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]   # .claude/skills/release/scripts/ -> repo root
REVISION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
HEADING = re.compile(r"^##[ \t]+(\d{4}\.\d{2}\.\d{2})[ \t]*$", re.M)
SECTION = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.M)
REACTION = re.compile(r"^- \S")
RETIRED = re.compile(r"^Retired:.*`[^`]+`")
CITES = re.compile(r"\(#\d+\)$")

SUBSECTION = re.compile(r"^###[ \t]+(.+?)[ \t]*$", re.M)
BULLET = re.compile(r"^- \*\*[^*\n]+\*\*")
STEP = re.compile(r"^\d+\. (.*)$")

CHANGELOG = "Changelog"
NOTES = ("Safer by default", "Also new", "Fixes", "Removed")
TODO = "What to do"
SECTIONS = (CHANGELOG, *NOTES, TODO)
ORDER = ("Highlights", *NOTES)       # a section neither names sits after these
UPGRADE = "Run `/para-upgrade`."
BEFORE = "Before you upgrade"
CLOSING = re.compile(r"^Full details: .*$", re.M)


def closing(label):
    return (f"Full details: [CHANGELOG.md at this tag]"
            f"(https://github.com/Vinedine/para-os/blob/{label}/CHANGELOG.md).")


class FoldError(Exception):
    pass


def line_problems(body, where):
    """[problem] for each non-blank line of `body` that is neither a Reaction nor a Retired line."""
    problems = []
    for n, line in enumerate(body.splitlines(), start=1):
        if line.strip() and not (REACTION.match(line) or RETIRED.match(line)):
            quoted = line if len(line) <= 60 else line[:60] + "..."
            problems.append(f"{where} line {n} is neither a `- ` Reaction line nor a `Retired:` "
                            f"line naming a backticked path: `{quoted}`")
    return problems


def changelog_problems(text):
    """line_problems() for every `## YYYY.MM.NN` entry of a changelog; the preamble is none."""
    headings = list(HEADING.finditer(text))
    ends = [h.start() for h in headings[1:]] + [len(text)]
    return [problem for h, end in zip(headings, ends)
            for problem in line_problems(text[h.end():end].strip("\n"), f"`## {h.group(1)}`")]


def parse_fragment(text):
    """({section: body}, [problem]) for one fragment. A body is stripped of its blank edges."""
    parts = SECTION.split(text)
    sections, problems = {}, []
    if parts[0].strip():
        problems.append("text before the first `## ` section")
    for name, body in zip(parts[1::2], parts[2::2]):
        if name not in SECTIONS:
            problems.append(f"unknown section `## {name}`; the sections are "
                            + ", ".join(f"`## {s}`" for s in SECTIONS))
        elif name in sections:
            problems.append(f"`## {name}` appears twice")
        else:
            sections[name] = body.strip()
    named = [n for n in NOTES if n in sections]
    if not named:
        problems.append("no release-notes section: name one of "
                        + ", ".join(f"`## {n}`" for n in NOTES))
    elif len(named) > 1:
        problems.append("two release-notes sections, "
                        + " and ".join(f"`## {n}`" for n in named) + "; a fragment names one")
    problems += [f"`## {n}` is not one `- **Lead.** text` bullet" for n in named
                 if "\n" in sections[n] or not BULLET.match(sections[n])]
    for n, line in enumerate(sections.get(TODO, "").splitlines(), start=1):
        if line.strip() and not line.startswith("- "):
            problems.append(f"`## {TODO}` line {n} is not a `- ` step: `{line}`")
    problems += line_problems(sections.get(CHANGELOG, ""), f"`## {CHANGELOG}`")
    return sections, problems


def fragment_paths(root):
    """Every fragment in changelog.d/, unordered. README.md is the folder's format, not one."""
    folder = root / "changelog.d"
    if not folder.is_dir():
        return []
    return [p for p in folder.glob("*.md") if p.name != "README.md"]


def merge_order(root, paths):
    """`paths` oldest-added first, by the branch's history; untracked ones last, by name."""
    try:
        r = subprocess.run(["git", "log", "--reverse", "--diff-filter=A", "--name-only",
                            "--format=", "--", "changelog.d"],
                           cwd=root, capture_output=True, text=True, encoding="utf-8")
        added = r.stdout.splitlines() if r.returncode == 0 else []
    except FileNotFoundError:
        added = []
    # A name added, folded away and added again sorts by its latest add.
    rank = {Path(name).name: i for i, name in enumerate(added) if name.strip()}
    return sorted(paths, key=lambda p: (0, rank[p.name], "") if p.name in rank
                  else (1, 0, p.name))


def lines_of(path, body):
    """A fragment's changelog lines, each `- ` line citing the fragment's number."""
    lines = [line.rstrip() for line in body.splitlines() if line.strip()]
    if not path.stem.isdigit():
        return lines
    return [f"{line} (#{path.stem})" if REACTION.match(line) and not CITES.search(line)
            else line for line in lines]


def newest(text, name):
    m = HEADING.search(text)
    if not m:
        raise FoldError(f"{name} has no `## YYYY.MM.NN` revision heading")
    return m


def section_span(text, heading):
    """(start, end) of the body under `heading`, up to the next revision heading or the end."""
    following = HEADING.search(text, heading.end())
    return heading.end(), following.start() if following else len(text)


def fold_changelog(text, label, lines):
    top = newest(text, "CHANGELOG.md")
    block = "".join(f"{line}\n" for line in lines)
    if top.group(1) != label:
        gap = "\n" if block else ""
        return f"{text[:top.start()]}## {label}\n\n{block}{gap}{text[top.start():]}"
    if not block:
        return text
    start, end = section_span(text, top)
    body, tail = text[start:end].rstrip(), text[end:]   # body is "" for an entry with no line
    head = text[:start] + body + ("\n" if body else "\n\n")
    return head + block + ("\n" + tail if tail else "")


def with_steps(text, before, after):
    """A `### What to do` body with the steps added and renumbered. Its numbered list comes
    first; what the maintainer wrote below it stays below it."""
    lines = text.splitlines()
    count = next((i for i, line in enumerate(lines) if not STEP.match(line)), len(lines))
    steps = [STEP.match(line).group(1) for line in lines[:count]] or [UPGRADE]
    at = next((i for i, step in enumerate(steps) if "/para-upgrade" in step), 0)
    steps = steps[:at] + before + steps[at:] + after
    rest = "\n".join(lines[count:]).strip()
    numbered = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, start=1))
    return numbered + (f"\n\n{rest}" if rest else "")


def fold_releases(text, label, notes, before, after):
    top = newest(text, "RELEASES.md")
    is_new = top.group(1) != label
    start, end = (top.start(), top.start()) if is_new else section_span(text, top)
    parts = SUBSECTION.split(CLOSING.sub("", text[start:end]))
    if parts[0].strip():
        raise FoldError(f"RELEASES.md `## {label}` has text outside its `### ` sections")
    sections = {name: body.strip() for name, body in zip(parts[1::2], parts[2::2])}
    for name, bullet in notes:
        sections[name] = f"{sections.get(name, '')}\n{bullet}".strip()
    sections[TODO] = with_steps(sections.get(TODO, ""), before, after)
    names = [n for n in ORDER if n in sections] + \
        [n for n in sections if n not in ORDER and n != TODO] + [TODO]
    body = "".join(f"### {n}\n\n{sections[n]}\n\n" for n in names if sections[n])
    body += closing(label) + ("\n\n" if is_new or end < len(text) else "\n")
    head = f"{text[:start]}## {label}\n\n" if is_new else f"{text[:start]}\n\n"
    return head + body + text[end:]


def fold(root, label):
    """Fold every fragment under `root` into `label`; return the fragments folded, in order.
    Raises FoldError, having written nothing, when the fold cannot be made whole."""
    if not REVISION.match(label):
        raise FoldError(f"`{label}` is not a YYYY.MM.NN revision label")
    paths = merge_order(root, fragment_paths(root))
    if not paths:
        return []

    parsed, problems = [], []
    for p in paths:
        sections, found = parse_fragment(p.read_text(encoding="utf-8"))
        problems += [f"changelog.d/{p.name}: {problem}" for problem in found]
        parsed.append(sections)
    if problems:
        raise FoldError("\n".join(problems))

    changelog_path, releases_path = root / "CHANGELOG.md", root / "RELEASES.md"
    changelog = changelog_path.read_text(encoding="utf-8")
    releases = releases_path.read_text(encoding="utf-8")
    current = newest(changelog, "CHANGELOG.md").group(1)
    if newest(releases, "RELEASES.md").group(1) != current:
        raise FoldError("CHANGELOG.md and RELEASES.md disagree on the newest revision; "
                        "run tools/check.py")
    if label < current:
        raise FoldError(f"`{label}` is older than the newest revision, `{current}`")

    lines = [line for p, s in zip(paths, parsed) for line in lines_of(p, s.get(CHANGELOG, ""))]
    notes = [(n, s[n]) for s in parsed for n in NOTES if n in s]
    steps = [line[2:].strip() for s in parsed for line in s.get(TODO, "").splitlines()
             if line.strip() and line[2:].strip() != UPGRADE]
    releases = fold_releases(releases, label, notes,
                             [st for st in steps if st.startswith(BEFORE)],
                             [st for st in steps if not st.startswith(BEFORE)])
    changelog = fold_changelog(changelog, label, lines)

    # Bytes, not text mode: Windows would write CRLF, and both files are LF.
    changelog_path.write_bytes(changelog.encode("utf-8"))
    releases_path.write_bytes(releases.encode("utf-8"))
    for p in paths:
        p.unlink()
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("label", help="the revision to fold into, YYYY.MM.NN")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        folded = fold(args.root, args.label)
    except FoldError as e:
        print(f"fold_changelog: {e}", file=sys.stderr)
        return 1
    if not folded:
        print("No fragments in changelog.d/; nothing to fold.")
    else:
        print(f"Folded {len(folded)} fragment(s) into {args.label}: "
              + ", ".join(p.name for p in folded))
    return 0


if __name__ == "__main__":
    sys.exit(main())
