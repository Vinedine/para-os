#!/usr/bin/env python3
"""Where a skill's page goes, for every skill that ends on one (para-shared/pages.md).

    py -3 paraos_pages.py publish claude|local --page <name> --vault <path>
    py -3 paraos_pages.py remember <url> --page <name> --title <title> --vault <path>
    py -3 paraos_pages.py run --skill <skill> --scan <scan.json> --out-dir <folder> --vault <path>
    py -3 paraos_pages.py refresh --page <name> [--out-dir <folder>] --vault <path>

A page has a name: a skill's own page is named for the skill (`daily-brief`), a page the vault
declares for its script's stem (`vendor-board`). Per vault and page,
`$PARAOS_HOME/cache/<page>/dashboards.json`, keyed by vault path, keeps where the page goes,
`claude` (the default, a claude.ai artifact) or `local` (the file
`$PARAOS_HOME/cache/<page>/<vault folder>.html`, which never leaves the machine), and the
artifact URL and title it was last published under. Deleting the cache only sends the next
publish back to the title match in pages.md, and to the default.

`run` reads the `## Pages` table of the vault's CLAUDE.md, one row per page: the skill it
belongs to (`para-pipeline`, `/para-pipeline`) and its script, a path from the vault root, in
the first two columns or the ones headed Skill and Script. For each row naming `--skill` it
runs `<script> --vault <root> --scan <scan> --out <page>`, `<page>` being the local page for
a `local` choice, else `<out-dir>/<page name>.html`. The script writes the whole page there,
data embedded, and prints one JSON line holding `title` and `description`. `run` prints one
JSON document: `pages`, one entry per row with its `page`, `script`, `out`, `publish`,
`title`, `description`, the remembered `url`, and `error`, null or why the row has no page: a
missing script, an `out` inside the vault, a non-zero exit, or a last line that is not that
JSON.

`refresh` rebuilds one declared page without its skill: it reruns the declaring skill's
`scripts/*_scan.py --vault <root>`, keeps the output beside the page, and runs the page's row
as `run` does, printing that one entry. `--out-dir` defaults to `$PARAOS_HOME/cache/<page>/`.
A page no row builds, a skill with no single scan, or a scan that fails is its `error`.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paraos_vault import (  # noqa: E402
    CELL_MARKS_RE, HEADING_RE, is_separator_row, live_lines, paraos_home_dir, read_lines,
    table_cells,
)

SKILLS_DIR = Path(__file__).resolve().parents[2]
PUBLISH = ("claude", "local")
PAGES_HEADING = "pages"
RUN_TIMEOUT = 300


# ------------------------------------------------------- where a page goes, remembered

def cache_file(page, paraos_home=None):
    return paraos_home_dir(paraos_home) / "cache" / page / "dashboards.json"


def local_page(vault, page, paraos_home=None):
    return paraos_home_dir(paraos_home) / "cache" / page / f"{Path(vault).name}.html"


def vault_key(vault):
    return Path(vault).resolve().as_posix().lower()


def load_cache(page, paraos_home=None):
    try:
        return json.loads(cache_file(page, paraos_home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cached(vault, page, paraos_home=None):
    entry = load_cache(page, paraos_home).get(vault_key(vault))
    return entry if isinstance(entry, dict) else {}


def remembered_url(vault, page, paraos_home=None):
    return cached(vault, page, paraos_home).get("url")


def publish_choice(vault, page, paraos_home=None):
    """`claude` unless the operator chose `local` for this page in this vault."""
    return "local" if cached(vault, page, paraos_home).get("publish") == "local" else "claude"


def store(vault, page, paraos_home=None, **fields):
    path = cache_file(page, paraos_home)
    data = load_cache(page, paraos_home)
    entry = data.get(vault_key(vault)) if isinstance(data.get(vault_key(vault)), dict) else {}
    entry.update(fields)
    data[vault_key(vault)] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def remember(vault, page, url, title, paraos_home=None):
    return store(vault, page, paraos_home, url=url, title=title)


# ------------------------------------------------------------- pages a vault declares

def _skill_name(cell):
    return CELL_MARKS_RE.sub("", cell).strip().lstrip("/").strip()


def declared_pages(vault):
    """The rows of the `## Pages` table in the vault's CLAUDE.md: `line`, `skill`, `script`.
    A table inside a fenced block is a sample and is skipped, as `live_lines` skips it."""
    path = Path(vault) / "CLAUDE.md"
    if not path.is_file():
        return []
    rows, inside, cols = [], False, None
    for lineno, text in live_lines(read_lines(path)):
        heading = HEADING_RE.match(text)
        if heading and len(heading.group(1)) == 2:
            inside, cols = heading.group(2).strip().lower() == PAGES_HEADING, None
            continue
        if not inside or not text.lstrip().startswith("|"):
            continue
        cells = table_cells(text)
        if cols is None:
            names = [CELL_MARKS_RE.sub("", c).strip().lower() for c in cells]
            cols = (names.index("skill") if "skill" in names else 0,
                    names.index("script") if "script" in names else 1)
            continue
        if is_separator_row(cells) or len(cells) <= max(cols):
            continue
        script = CELL_MARKS_RE.sub("", cells[cols[1]]).strip()
        if script:
            rows.append({"line": lineno, "skill": _skill_name(cells[cols[0]]), "script": script})
    return rows


def _page_json(stdout):
    """The script's last non-empty line, read as its {title, description}, else None."""
    lines = [line for line in (stdout or "").splitlines() if line.strip()]
    try:
        out = json.loads(lines[-1]) if lines else None
    except ValueError:
        return None
    return out if isinstance(out, dict) and out.get("title") else None


def run_page(vault, row, scan, out_dir, paraos_home=None):
    vault = Path(vault).resolve()
    script = (vault / row["script"]).resolve()
    page = script.stem
    publish = publish_choice(vault, page, paraos_home)
    out = (local_page(vault, page, paraos_home) if publish == "local"
           else Path(out_dir).resolve() / f"{page}.html")
    entry = {"page": page, "script": row["script"], "out": out.as_posix(), "publish": publish,
             "title": None, "description": None, "url": remembered_url(vault, page, paraos_home),
             "error": None}
    if not script.is_file():
        entry["error"] = f"no script at {row['script']}"
        return entry
    if out.is_relative_to(vault):
        entry["error"] = "the page would be written inside the vault"
        return entry
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        done = subprocess.run([sys.executable, str(script), "--vault", str(vault),
                               "--scan", str(Path(scan).resolve()), "--out", str(out)],
                              cwd=vault, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=RUN_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as failed:
        entry["error"] = f"the script did not run: {failed}"
        return entry
    if done.returncode != 0:
        tail = (done.stderr or "").strip().splitlines()[-1:] or [f"exit {done.returncode}"]
        entry["error"] = f"the script failed: {tail[0]}"
        return entry
    printed = _page_json(done.stdout)
    if printed is None or not out.is_file():
        entry["error"] = "the script printed no {title, description} line or wrote no page"
        return entry
    entry.update(title=printed["title"], description=printed.get("description"))
    return entry


def run(vault, skill, scan, out_dir, paraos_home=None):
    wanted = _skill_name(skill)
    return [run_page(vault, row, scan, out_dir, paraos_home)
            for row in declared_pages(vault) if row["skill"] == wanted]


def refresh(vault, page, out_dir=None, paraos_home=None, skills_dir=SKILLS_DIR):
    vault = Path(vault).resolve()
    row = next((r for r in declared_pages(vault) if Path(r["script"]).stem == page), None)
    if row is None:
        return {"page": page, "error": f"no row under ## Pages builds {page}"}
    scans = sorted((Path(skills_dir) / row["skill"] / "scripts").glob("*_scan.py"))
    if len(scans) != 1:
        return {"page": page, "error": f"no single scan for {row['skill']}"}
    try:
        done = subprocess.run([sys.executable, str(scans[0]), "--vault", str(vault)],
                              cwd=vault, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=RUN_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as failed:
        return {"page": page, "error": f"the scan did not run: {failed}"}
    if done.returncode != 0:
        tail = (done.stderr or "").strip().splitlines()[-1:] or [f"exit {done.returncode}"]
        return {"page": page, "error": f"the scan failed: {tail[0]}"}
    out_dir = Path(out_dir) if out_dir else cache_file(page, paraos_home).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    scan = out_dir / f"{page}.scan.json"
    scan.write_text(done.stdout, encoding="utf-8")
    return run_page(vault, row, scan, out_dir, paraos_home)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Where a skill's page goes.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish", help="record where a page goes for this vault")
    p.add_argument("choice", choices=PUBLISH)
    p.add_argument("--page", required=True)
    p.add_argument("--vault", required=True)
    r = sub.add_parser("remember", help="record the artifact a page was published to")
    r.add_argument("url")
    r.add_argument("--page", required=True)
    r.add_argument("--title", required=True)
    r.add_argument("--vault", required=True)
    g = sub.add_parser("run", help="build the pages a vault declares for a skill")
    g.add_argument("--skill", required=True)
    g.add_argument("--scan", required=True, help="the skill's own scan output")
    g.add_argument("--out-dir", required=True, help="a scratch folder outside the vault")
    g.add_argument("--vault", required=True)
    f = sub.add_parser("refresh", help="rebuild one declared page from a fresh scan")
    f.add_argument("--page", required=True)
    f.add_argument("--out-dir", help="default: the page's cache folder")
    f.add_argument("--vault", required=True)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if args.cmd == "publish":
        path = store(args.vault, args.page, publish=args.choice)
        print(json.dumps({"publish": args.choice, "cache": path.as_posix()}))
    elif args.cmd == "remember":
        path = remember(args.vault, args.page, args.url, args.title)
        print(json.dumps({"remembered": args.url, "cache": path.as_posix()}))
    elif args.cmd == "refresh":
        print(json.dumps(refresh(args.vault, args.page, args.out_dir), ensure_ascii=False))
    else:
        print(json.dumps({"pages": run(args.vault, args.skill, args.scan, args.out_dir)},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
