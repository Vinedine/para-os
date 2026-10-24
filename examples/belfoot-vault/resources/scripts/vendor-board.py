#!/usr/bin/env python3
"""The vendor board as a page, the one this vault declares for /para-pipeline (CLAUDE.md, Pages).

    py -3 resources/scripts/vendor-board.py --vault <root> --scan <pipeline scan> --out <page.html>

Reads the scan /para-pipeline already made, writes one self-contained page holding the live
vendors by stage, and prints one JSON line with its title and description. It loads nothing
from the network and never writes inside the vault.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

TITLE = "BelFoot Vendor Board"
DESCRIPTION = "Every vendor in selection, by stage, with its next step and last touch."
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg: #ffffff; --fg: #1d1d1f; --muted: #6b6b70; --line: #e3e3e6; --panel: #f6f6f8; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --bg: #17171a; --fg: #ececf0; --muted: #a0a0a8;
    --line: #2e2e33; --panel: #202024; }}
}}
:root[data-theme="dark"] {{ --bg: #17171a; --fg: #ececf0; --muted: #a0a0a8; --line: #2e2e33;
  --panel: #202024; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 960px; margin: 0 auto; padding: 24px 16px; }}
p {{ color: var(--muted); }}
.wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ background: var(--panel); font-weight: 600; }}
</style></head>
<body><main>
<h1>{title}</h1>
<p>Rebuilt from the vault on {today}.</p>
{sections}
</main></body></html>
"""


def plain(text):
    return LINK_RE.sub(r"\1", text or "").replace("**", "").replace("`", "").strip()


def section(stage, rows):
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>"
        for row in rows)
    return (f"<h2>{html.escape(stage)} ({len(rows)})</h2><div class=\"wrap\"><table>"
            "<tr><th>Vendor</th><th>Workstream</th><th>Days in stage</th><th>Next step</th>"
            f"<th>Last touch</th></tr>{body}</table></div>")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the vendor board page.")
    ap.add_argument("--vault", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--scan", required=True, help="/para-pipeline's scan output")
    ap.add_argument("--out", required=True, help="where to write the page, outside the vault")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    if out.is_relative_to(Path(args.vault).resolve()):
        print("vendor-board: --out is inside the vault", file=sys.stderr)
        return 2
    scan = json.loads(Path(args.scan).read_text(encoding="utf-8"))
    board = next((lc for lc in scan["lifecycles"] if lc["heading"].lower().startswith("vendor")),
                 None)
    if board is None:
        print("vendor-board: the scan holds no Vendor lifecycle", file=sys.stderr)
        return 2
    sections = []
    for stage in board["stages"]:
        rows = [(e["name"], plain(e["fields"].get("Workstream")),
                 "?" if e["days_in_stage"] is None else e["days_in_stage"],
                 plain((e["next_step"] or {}).get("text")) or "none",
                 plain(e["fields"].get("Last touch")))
                for e in board["entities"] if e["live"] and e["stage"] == stage]
        if rows:
            sections.append(section(stage, rows))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PAGE.format(title=html.escape(TITLE), today=html.escape(scan["today"]),
                               sections="\n".join(sections) or "<p>No vendor in selection.</p>"),
                   encoding="utf-8")
    print(json.dumps({"title": TITLE, "description": DESCRIPTION}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
