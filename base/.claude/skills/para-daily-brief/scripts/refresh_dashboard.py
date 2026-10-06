#!/usr/bin/env python3
"""Keep a vault's dashboard current without a model run.

    py -3 refresh_dashboard.py                  # from a hook: re-render in the background if stale
    py -3 refresh_dashboard.py --vault <path>   # the same, for a named vault
    py -3 refresh_dashboard.py --render         # scan and render now, in this process

The page is `render_dashboard.py --mechanical`: the tiles, the per-entity bars, the Later
counts, every fired health flag, ideas, triage and lifecycle counts, with Now ranked by the
brief's own sort. The Next action and the agenda stay model work, so the page says once
that they come from the next `/para-daily-brief` run, which also remains the source of the
published artifact. It is written to `$PARAOS_HOME/cache/daily-brief/<vault folder>.html`,
never inside the vault, beside a stamp of the files it was rendered from and a log of the
last background run.

Without `--render`, the script is the hook: it resolves the vault from `--vault`, else
`$CLAUDE_PROJECT_DIR`, else the working directory, walking up to the vault root, and exits
quietly outside one. It compares the modification times and sizes of the action-bearing
files, `CLAUDE.md`, `triage/` and `resources/ideas/` against the stamp of the last render
and exits when nothing changed; otherwise it starts the scan and the render in a detached
process and returns at once, so the turn never waits. It never exits non-zero in that mode:
a hook that fails must not become the agent's problem.

The hook recipe. An end-of-turn hook rather than one per file edit, because moves and
deletes made through the shell change actions too, and one triage pass edits dozens of
files. In the vault's `.claude/settings.json` on Claude Code, anchored to the vault root
(`py` on Windows, `python3` on macOS and Linux):

    {
      "hooks": {
        "Stop": [{ "hooks": [{ "type": "command",
          "command": "py \\"$CLAUDE_PROJECT_DIR/.claude/skills/para-daily-brief/scripts/refresh_dashboard.py\\"" }] }]
      }
    }

Where the skills live outside the vault, the command names that copy instead. The hook
configuration is the operator's harness settings, not vault content: para-os ships none.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED_DIR = HERE.parents[1] / "para-shared" / "scripts"
for folder in (HERE, SHARED_DIR):
    if folder.is_dir() and str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

WATCHED_FOLDERS = ("projects", "areas", "triage", "resources/ideas")


def find_vault(start):
    """The vault root at or above `start`, by the shared root test, else None."""
    from paraos_vault import vault_root
    path = Path(start).resolve()
    for candidate in (path, *path.parents):
        if vault_root(candidate)["root"]:
            return candidate
    return None


def watched_paths(vault):
    """Everything whose change can move a number on the page: the action-bearing files,
    the folders that gain or lose an entity or a triage item, each idea's brief, and
    `CLAUDE.md`, which names the vault and declares its lifecycles."""
    from paraos_vault import action_files
    paths = set(action_files(vault)) | {vault / "CLAUDE.md"}
    for rel in WATCHED_FOLDERS:
        folder = vault / rel
        if folder.is_dir():
            paths.add(folder)
            paths.update(p for p in folder.iterdir())
    paths.update(vault.glob("resources/ideas/*/brief.md"))
    return sorted(paths)


def fingerprint(vault):
    """{vault-relative path: [mtime, size]} for every watched path that exists."""
    out = {}
    for p in watched_paths(vault):
        try:
            st = p.stat()
        except OSError:
            continue
        out[p.relative_to(vault).as_posix()] = [st.st_mtime, st.st_size]
    return out


def cache_paths(vault, paraos_home=None):
    """The page, its stamp and the background run's log, under the daily-brief cache."""
    from paraos_vault import paraos_home_dir
    base = paraos_home_dir(paraos_home) / "cache" / "daily-brief"
    stem = Path(vault).name
    return base / f"{stem}.html", base / f"{stem}.stamp.json", base / f"{stem}.log"


def is_current(vault, paraos_home=None):
    page, stamp, _ = cache_paths(vault, paraos_home)
    if not page.is_file():
        return False
    try:
        return json.loads(stamp.read_text(encoding="utf-8")) == fingerprint(vault)
    except (OSError, ValueError):
        return False


def render_now(vault, paraos_home=None, today=None):
    """Scan, render the numbers-only page and stamp what it was rendered from. The stamp is
    taken before the scan, so an edit made during the render is caught by the next run."""
    from brief_scan import scan
    from render_dashboard import render
    page, stamp, _ = cache_paths(vault, paraos_home)
    seen = fingerprint(vault)
    report = json.loads(json.dumps(scan(vault, today or date.today())))
    title, html = render(report)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(html, encoding="utf-8")
    stamp.write_text(json.dumps(seen) + "\n", encoding="utf-8")
    return {"out": page.as_posix(), "title": title}


def spawn_render(vault, paraos_home=None):
    """The render in a process of its own, detached from the hook that started it, with
    its stderr in the cache's log so a failure can be read after the fact."""
    _, _, log = cache_paths(vault, paraos_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(HERE / "refresh_dashboard.py"), "--render", "--vault", str(vault)]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0)
                                   | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    else:
        kwargs["start_new_session"] = True
    with open(log, "w", encoding="utf-8") as err:
        subprocess.Popen(cmd, stderr=err, **kwargs)


def resolve_vault(explicit):
    start = explicit or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return find_vault(start)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Re-render the daily-brief dashboard when the "
                                             "vault changed, with no model run.")
    ap.add_argument("--vault", help="vault root or any folder inside it "
                                    "(default: $CLAUDE_PROJECT_DIR, else the working directory)")
    ap.add_argument("--render", action="store_true",
                    help="scan and render now, in this process, instead of in the background")
    ap.add_argument("--today", help="date to bucket against, with --render (default: the system date)")
    args = ap.parse_args(argv)

    if args.render:
        vault = resolve_vault(args.vault)
        if vault is None:
            print(f"refresh_dashboard: no vault at or above {args.vault or os.getcwd()}",
                  file=sys.stderr)
            return 2
        today = date.fromisoformat(args.today) if args.today else None
        print(json.dumps(render_now(vault, today=today), ensure_ascii=False))
        return 0

    # The hook. Nothing it meets is the agent's problem, so every failure is a quiet exit.
    try:
        vault = resolve_vault(args.vault)
        if vault is not None and not is_current(vault):
            spawn_render(vault)
    except Exception:  # noqa: BLE001 - a hook never surfaces its own failure to the turn
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
