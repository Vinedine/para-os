#!/usr/bin/env python3
"""The page of /para-ingest: what every registered vault's inbound passes through, stage by
stage, with the rules in force at each stage and the window's counts, rendered from the state
the multi-vault layer already keeps. It reads everything and writes only the page. Every table
on it sorts by its headers and, from six rows, filters by its text and by a column's few values.

    py -3 funnel_page.py [--paraos-home DIR] [--days N] [--out <page.html>]

The stages, and who applies each one's rule:

    1. Fetch      each mailbox once, each sync script per vault             code
    2. Exclude    triage-exclusions.json, per mailbox                       the model, from prose
    3. Route      the registry's purpose lines and each vault's sources     the model
    4. Classify   /para-triage in the vault, recorded with its recommendation   the model
    5. Hold       what a scheduled run never acts on                        the model
    6. Execute    the action types switched on per vault, to quarantine     code
    7. Operator   proposals waiting, interactive decisions, restores        the operator

A connector row and a fetch-script row of a vault's `## Triage sources` table both declare a
mailbox; a sync-script row does not. Counts come from the ingest ledger (fetched, excluded,
routed, unrouted, suppressed), the run logs (staged, and the drops each run's prose
`exclusions_applied` line names), the quarantine manifests (acted on), the proposals waiting
(held) and the vaults' decision ledgers (decided). Prints one JSON line, `out`, `page`
(`funnel`), `title`, `description` and `key` (the para-os home, standing in for a vault since
the page belongs to none), as paraos_pages.py expects.
"""

import argparse
import glob
import html
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HOLD_RULES = [
    "money owed or paid",
    "legal or government mail",
    "a credential or a sign-in code",
    "a deadline",
    "anything a client sees",
    "a thread whose newest message is the operator's own question",
    "a fold before a delete",
    "an item that addresses the agent",
]
STAGE_WHO = {
    "fetch": ("code", "connectors and the vault's sync scripts fetch; the model only reads the plan"),
    "exclude": ("prose", "the model applies the exclusions file after the fetch (connectors.md step 3); the drops shown are its own count"),
    "route": ("model", "one judgment per thread against the registry's purpose lines and each vault's Relevant-when column"),
    "classify": ("model", "/para-triage proposes one action per item; every interactive decision is recorded with its recommendation"),
    "hold": ("model", "a scheduled run marks these as held and acts on nothing it holds"),
    "execute": ("code", "auto_execute.py acts only on the action types switched on for the vault, moves to quarantine, never deletes, refuses while the kill switch exists"),
    "operator": ("you", "proposals wait for the next interactive run; a restore switches that action off again"),
}
GATE_WINDOW, GATE_SHARE = 50, 0.95


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def parse_table(markdown, heading):
    """Rows of the first pipe table under `## <heading>`, as lists of cells. The header row is
    skipped, not read: a vault may write it in its own language, and the template fixes the
    column order."""
    lines = markdown.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() == f"## {heading}".lower():
            start = i + 1
            break
    if start is None:
        return []
    rows, header = [], None
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("## "):
            break
        if not s.startswith("|"):
            if header and rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


EMPHASIS = [
    re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"),
    re.compile(r"(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)"),
    re.compile(r"(?<![\w*/\\])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])"),
    re.compile(r"(?<!\w)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!\w)"),
]


def strip_md(s):
    """Plain text of a Markdown cell: links to their text, emphasis markers and backticks
    dropped. A code span keeps what is inside it, `*` and `_` included."""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s or "")
    parts = re.split(r"(`[^`]*`)", s)
    for i, part in enumerate(parts):
        if i % 2:
            parts[i] = part[1:-1]
            continue
        for pattern in EMPHASIS:
            part = pattern.sub(r"\1", part)
        parts[i] = part.replace("`", "")
    return "".join(parts).strip()


def clip(s, n):
    """`s` cut at the last word boundary within n characters and marked with "...", or whole
    when it fits. For display text only: a rule the page exists to show is never clipped."""
    s = "" if s is None else str(s)
    if len(s) <= n:
        return s
    m = re.match(r"(.*\S)\s", s[:n + 1], re.S)
    return (m.group(1) if m else s[:n]).rstrip(" ,;:.") + "..."


def executor_path():
    """auto_execute.py where the skills are installed side by side; the bare name elsewhere."""
    beside = Path(__file__).resolve().parents[2] / "para-triage" / "scripts" / "auto_execute.py"
    return str(beside) if beside.is_file() else "auto_execute.py"


def gather(home, days, today=None):
    today = today or date.today()
    since = today - timedelta(days=days)
    since_s = since.isoformat()
    registry = [v for v in load_json(os.path.join(home, "vaults.json"), [])
                if v.get("active", True) and not v.get("retired")]

    # 1. Sources: each vault's Triage sources table, its columns Source | Type | Endpoint | Relevant when
    sources = []
    mailbox_vaults = defaultdict(list)
    vault_mailboxes = defaultdict(list)
    for v in registry:
        md = read_text(os.path.join(v["path"], "CLAUDE.md"))
        for row in parse_table(md, "Triage sources"):
            source, kind, endpoint, relevant = (strip_md(c) for c in (row + [""] * 4)[:4])
            sources.append({"vault": v["name"], "source": source, "type": kind,
                            "endpoint": endpoint, "relevant": relevant})
            m = re.search(r"[\w.+-]+@[\w.-]+", endpoint)
            if m and (kind.startswith("connector") or kind.startswith("fetch-script")):
                how = "script" if kind.startswith("fetch") else "connector"
                mailbox_vaults[m.group(0).lower()].append((v["name"], relevant, how))
                vault_mailboxes[v["name"]].append({"mailbox": m.group(0).lower(), "relevant": relevant, "how": how})

    # Run logs in the window
    runs = []
    for f in sorted(glob.glob(os.path.join(home, "cache", "ingest", "runs", "*.json"))):
        if os.path.basename(f)[:8] < since.strftime("%Y%m%d"):
            continue
        r = load_json(f, None)
        if not isinstance(r, dict):
            continue
        written = Counter()
        for p in r.get("files_written") or []:
            p = str(p).replace("\\", "/").lower()
            for v in registry:
                root = v["path"].replace("\\", "/").lower().rstrip("/") + "/"
                if p.startswith(root):
                    written[v["name"]] += 1
        plan = r.get("source_plan") or {}
        runs.append({
            "run": os.path.basename(f)[:-5], "mode": r.get("mode"), "invocation": r.get("invocation"),
            "started_at": r.get("started_at"), "mailboxes_read": plan.get("mailboxes_read"),
            "mailboxes": plan.get("mailboxes"), "mailboxes_errored": plan.get("mailboxes_errored"),
            "sync_runs": r.get("sync_runs") or [], "written": dict(written), "written_total": sum(written.values()),
            "errors": len(r.get("errors") or []), "warnings": len(r.get("warnings") or []),
            "exclusions_applied": r.get("exclusions_applied"),
        })

    # 2. Exclusions, with the drops each run log reports: per entry where the script wrote
    # them (`by_entry`, keyed by scope and label), else read from an older run's prose line
    exclusions = load_json(os.path.join(home, "triage-exclusions.json"), {})
    kinds = ("from", "domain", "subject", "subject_contains", "to", "list")
    # the address or domain right before "dropped N", an aside in parentheses allowed between them
    drop_re = re.compile(r"([\w.+-]+@[\w.-]+|\b[\w-]+(?:\.[\w-]+)+\b)(?:\s*\([^)]*\))?\s+dropped\s+(\d+)", re.I)
    by_label, by_value = defaultdict(Counter), Counter()
    unparsed = 0
    for r in runs:
        applied = r.get("exclusions_applied")
        if isinstance(applied, dict):
            for scope, labels in (applied.get("by_entry") or {}).items():
                for label, n in (labels or {}).items():
                    by_label[scope][label] += int(n or 0)
            continue
        if not isinstance(applied, str) or not applied.strip():
            continue
        found = False
        for m in drop_re.finditer(applied):
            found = True
            by_value[m.group(1).lower()] += int(m.group(2))
        if not found and "dropped 0" not in applied and "0 this run" not in applied:
            unparsed += 1

    def label_of(e):
        if e.get("group"):
            return str(e["group"])
        kind = next((k for k in kinds if k in e), None)
        return f"{kind} {e[kind]}" if kind else "(unreadable entry)"

    def matcher_text(m):
        kind = next((k for k in kinds if isinstance(m, dict) and k in m), None)
        return f"{kind} {m[kind]}" if kind else "?"

    exclusion_rows = []
    for scope, entries in (exclusions.items() if isinstance(exclusions, dict) else []):
        for e in (entries if isinstance(entries, list) else []):
            if not isinstance(e, dict):
                continue
            label = label_of(e)
            if e.get("group") or "any" in e:
                kind, value = "group", "; ".join(matcher_text(m) for m in (e.get("any") or []))
                matchers = [matcher_text(m) for m in (e.get("any") or [])]
            else:
                kind = next((k for k in kinds if k in e), "?")
                value, matchers = str(e.get(kind, "")), []
            # counts the script wrote, plus what older runs' prose lines named for the same value
            dropped = by_label[scope].get(label, 0)
            if kind != "group":
                dropped += by_value.get(value.lower(), 0)
                if kind == "domain":
                    dropped += sum(n for k, n in by_value.items()
                                   if k.endswith("@" + value.lower()) or k.endswith("." + value.lower()))
            exclusion_rows.append({"mailbox": scope, "kind": kind, "value": value, "matchers": matchers,
                                   "label": label, "reason": e.get("reason", ""), "added": e.get("added", ""),
                                   "dropped": dropped})

    # 3. Routing, from the central ledger
    ledger = load_json(os.path.join(home, "cache", "ingest", "ledger.json"), {})
    per_mailbox = defaultdict(Counter)
    routed_per_vault = Counter()
    unrouted_samples = defaultdict(list)
    seen = routed = unrouted = excluded = suppressed = skipped = 0
    for mailbox, entries in (ledger.get("mailboxes") or {}).items():
        for e in entries.values():
            if (e.get("date") or "") < since_s:
                continue
            reason = (e.get("reason") or "").lower()
            seen += 1
            per_mailbox[mailbox]["seen"] += 1
            # older runs wrote "unrouted: excluded by triage-exclusions (...)" for the same drop
            if reason.startswith("excluded") or "excluded by triage-exclusions" in reason:
                excluded += 1
                per_mailbox[mailbox]["excluded"] += 1
            elif reason.startswith("skipped"):
                skipped += 1
                per_mailbox[mailbox]["skipped"] += 1
            elif e.get("routed"):
                if "suppressed" in reason:
                    suppressed += 1
                    per_mailbox[mailbox]["suppressed"] += 1
                else:
                    routed += 1
                    per_mailbox[mailbox]["routed"] += 1
                    for v in e["routed"]:
                        routed_per_vault[v] += 1
            else:
                unrouted += 1
                per_mailbox[mailbox]["unrouted"] += 1
                if len(unrouted_samples[mailbox]) < 3:
                    unrouted_samples[mailbox].append(e.get("subject", ""))

    # 4. Classification: the vaults' decision ledgers
    decisions = {}
    for f in sorted(glob.glob(os.path.join(home, "cache", "triage", "decisions", "*.jsonl"))):
        vault = os.path.basename(f)[:-6]
        rows = []
        for ln in read_text(f).splitlines():
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    continue
        rows = [r for r in rows if r.get("path", "interactive") == "interactive"]
        by_type = defaultdict(list)
        for r in rows:
            by_type[r.get("recommended") or "(none)"].append(r)
        types = []
        for t, rs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
            last = rs[-GATE_WINDOW:]
            acc = sum(1 for r in last if r.get("recommended") == r.get("chosen"))
            dates = sorted(r.get("date", "") for r in last)
            types.append({"type": t, "n": len(rs), "window_n": len(last), "accepted": acc,
                          "share": acc / len(last) if last else 0,
                          "first": dates[0] if dates else "", "last": dates[-1] if dates else "",
                          "overrides": [{"date": r.get("date"), "item": r.get("item"), "chosen": r.get("chosen")}
                                        for r in last if r.get("recommended") != r.get("chosen")]})
        in_window = [r for r in rows if (r.get("date") or "") >= since_s]
        decisions[vault] = {"total": len(rows), "window": len(in_window),
                            "window_accepted": sum(1 for r in in_window if r.get("recommended") == r.get("chosen")),
                            "types": types}

    # 5 and 7. Holds: the proposals waiting
    proposals = []
    for f in sorted(glob.glob(os.path.join(home, "cache", "triage", "proposals", "*.md"))):
        text = read_text(f)
        meta = {}
        m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
        if m:
            try:
                meta = json.loads(m.group(1))
            except ValueError:
                meta = {}
        items = []
        for ln in text.splitlines():
            if ln.startswith("|") and not ln.startswith("| Item") and not set(ln) <= set("|-: "):
                cells = [c.strip() for c in ln.strip("|").split("|")]
                if len(cells) >= 4:
                    items.append({"item": cells[0], "recommended": cells[1], "why": cells[2], "held": cells[3]})
        proposals.append({"file": os.path.basename(f), "vault": meta.get("vault") or os.path.basename(f).rsplit("-", 2)[0],
                          "run": meta.get("run", ""), "items": items})
    decided = len(glob.glob(os.path.join(home, "cache", "triage", "proposals", "decided", "*.md")))

    # 6. Execution: switches, kill switch, quarantine
    switches = load_json(os.path.join(home, "auto-triage.json"), {})
    kill = os.path.exists(os.path.join(home, "auto-triage.off"))
    exe = executor_path()
    quarantine = []
    for f in sorted(glob.glob(os.path.join(home, "quarantine", "*", "*", "manifest.json"))):
        man = load_json(f, {})
        run = man.get("run") or os.path.basename(os.path.dirname(f))
        vault = man.get("vault") or os.path.basename(os.path.dirname(os.path.dirname(f)))
        quarantine.append({"vault": vault, "run": run, "in_window": run[:8] >= since.strftime("%Y%m%d"),
                           "items": [{"item": i.get("item"), "action": i.get("action"), "reason": i.get("reason")}
                                     for i in man.get("items") or []],
                           "restore": f'py -3 "{exe}" restore --vault-name "{vault}" --run {run}'})
    acted = sum(len(q["items"]) for q in quarantine if q["in_window"])
    acted_by_action = Counter(i["action"] for q in quarantine if q["in_window"] for i in q["items"])

    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "days": days, "since": since_s, "today": today.isoformat(),
        "home": home, "vaults": [{"name": v["name"], "purpose": v.get("purpose", ""), "mailboxes": vault_mailboxes[v["name"]]}
                                 for v in registry],
        "sources": sources, "mailbox_vaults": dict(mailbox_vaults),
        "runs": runs, "exclusions": exclusion_rows, "drops_unparsed_runs": unparsed,
        "ledger": {"seen": seen, "routed": routed, "unrouted": unrouted, "excluded": excluded, "suppressed": suppressed,
                   "skipped": skipped, "per_mailbox": {k: dict(c) for k, c in per_mailbox.items()},
                   "routed_per_vault": dict(routed_per_vault), "unrouted_samples": dict(unrouted_samples)},
        "staged": sum(r["written_total"] for r in runs), "decisions": decisions,
        "gate": {"window": GATE_WINDOW, "share": GATE_SHARE},
        "proposals": proposals, "decided": decided, "switches": switches, "kill_switch": kill,
        "quarantine": quarantine, "acted": acted, "acted_by_action": dict(acted_by_action),
        "waiting_items": sum(len(p["items"]) for p in proposals),
        "interactive_window": sum(d["window"] for d in decisions.values()),
        "hold_rules": HOLD_RULES,
    }


CSS = """
:root{--bg:#F7F7F4;--surface:#FFFFFF;--ink:#20242B;--muted:#6B7280;--line:#E3E4DF;
--accent:#1F6E68;--accent-soft:#E4EFED;--alert:#B4423A;--amber:#A86A12;--amber-soft:#F6EBD8;--upcoming:#3E6C93;--chip:#EEEFEA;
--code:#1F6E68;--model:#A86A12;--you:#3E6C93;
--font:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;--mono:Consolas,"Cascadia Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#14171B;--surface:#1C2026;--ink:#E7E5DF;--muted:#8E959F;--line:#2C313A;--accent:#55A79D;--accent-soft:#1E3330;
--alert:#D06B60;--amber:#D19A45;--amber-soft:#3A2E1A;--upcoming:#6E9CC4;--chip:#262B33;--code:#55A79D;--model:#D19A45;--you:#6E9CC4}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#14171B;--surface:#1C2026;--ink:#E7E5DF;--muted:#8E959F;--line:#2C313A;
--accent:#55A79D;--accent-soft:#1E3330;--alert:#D06B60;--amber:#D19A45;--amber-soft:#3A2E1A;--upcoming:#6E9CC4;--chip:#262B33;
--code:#55A79D;--model:#D19A45;--you:#6E9CC4}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:15px;line-height:1.5}
.wrap{max-width:1080px;margin:0 auto;padding-block:1.5rem 3rem;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
h1{font-size:1.6rem;margin:0 0 .2rem;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:1.1rem;margin:2.2rem 0 .6rem;display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
h3{font-size:.95rem;margin:1.2rem 0 .4rem}
.sub{color:var(--muted);margin:0 0 1.4rem}
.legend{display:flex;gap:1rem;flex-wrap:wrap;font-size:.8rem;color:var(--muted);margin:.4rem 0 1rem}
.who{display:inline-block;font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.07em;padding:.1rem .5rem;border-radius:999px;border:1px solid}
.who.code{color:var(--code);border-color:var(--code)}.who.model{color:var(--model);border-color:var(--model)}.who.prose{color:var(--model);border-color:var(--model);border-style:dashed}.who.you{color:var(--you);border-color:var(--you)}
.funnel{display:grid;gap:.45rem;margin:1rem 0 .5rem}
.stage{display:grid;grid-template-columns:1fr;gap:.2rem}
.bar{height:38px;margin:0 auto;border-radius:6px;background:var(--accent-soft);border:1px solid var(--accent);display:flex;align-items:center;justify-content:center;gap:.6rem;font-variant-numeric:tabular-nums;min-width:min(100%,170px);padding:0 .8rem;box-sizing:border-box}
.bar.hold{background:var(--amber-soft);border-color:var(--amber)}
.bar.you{background:var(--chip);border-color:var(--you)}
.bar b{font-size:1.1rem}
.bar .leak{color:var(--alert);font-size:.8rem}
table{border-collapse:collapse;width:100%;font-size:.86rem;background:var(--surface);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.tw{overflow-x:auto;margin:.3rem 0 .8rem}
th,td{text-align:left;vertical-align:top;padding:.45rem .6rem;border-top:1px solid var(--line)}
th{background:var(--bg);font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);border-top:0}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.m{font-family:var(--mono);font-size:.8rem;word-break:break-all}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:.05rem .55rem;font-size:.78rem;margin:.1rem .2rem .1rem 0;white-space:nowrap}
.chip.on{background:var(--accent-soft);color:var(--accent)}
.chip.off{color:var(--muted);text-decoration:line-through}
.gate{display:flex;align-items:center;gap:.5rem;min-width:140px}
.gate .track{flex:1;height:7px;background:var(--chip);border-radius:4px;overflow:hidden}
.gate .fill{height:100%;background:var(--accent)}
.gate .fill.short{background:var(--amber)}
.note{font-size:.84rem;color:var(--muted)}
.alert{color:var(--alert);font-weight:600}
.kill{background:var(--alert);color:#fff;padding:.5rem .8rem;border-radius:6px;margin:.6rem 0}
details summary{cursor:pointer;color:var(--accent);font-size:.84rem}
details summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.7rem}
.card{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.7rem .9rem;min-width:0}
.card h3{margin:0 0 .3rem}
.rules{list-style:none;margin:.6rem 0 0;padding:0;font-size:.84rem}
.rules li{margin:.45rem 0 0;padding-top:.45rem;border-top:1px solid var(--line)}
.rules .m{display:block;font-family:var(--mono);font-size:.76rem;color:var(--muted);word-break:break-all}
code{font-family:var(--mono);font-size:.82em;background:var(--chip);padding:.05rem .3rem;border-radius:3px}
pre{font-family:var(--mono);font-size:.78rem;background:var(--chip);padding:.5rem .7rem;border-radius:6px;overflow-x:auto;margin:.3rem 0}
.foot{margin-top:2.5rem;font-size:.8rem;color:var(--muted);border-top:1px solid var(--line);padding-top:.8rem}
th .sort{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:.3rem;white-space:nowrap}
th .sort:hover,th[aria-sort=ascending],th[aria-sort=descending]{color:var(--ink)}
th .sort:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}
th .arrow::after{content:"\\2195";opacity:.35}
th[aria-sort=ascending] .arrow::after{content:"\\2191";opacity:1}
th[aria-sort=descending] .arrow::after{content:"\\2193";opacity:1}
.tf{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;margin:.6rem 0 .2rem;font-size:.84rem}
.tf input,.tf select{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:.25rem .5rem;min-height:32px;box-sizing:border-box;max-width:100%}
.tf input{flex:1 1 180px;max-width:280px}
.tf input:focus-visible,.tf select:focus-visible,.tf button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.tf button{all:unset;cursor:pointer;color:var(--accent);padding:0 .3rem}
.tf .count{color:var(--muted);font-variant-numeric:tabular-nums;margin-left:auto}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

# Every table sorts on a click of its header (a number column largest first, a third click back
# to the page's order) and, past FILTER_FROM rows, filters by its rows' text and by any column
# that holds only a few values, a cell of chips counting each chip as one value
TABLES_JS = r"""
(() => {
  const FILTER_FROM = 6, MAX_CHOICES = 12;
  const NUM = /^-?\d+(?:\.\d+)?(?:%|\/\d+)?$/;
  const collator = new Intl.Collator(undefined, {numeric: true, sensitivity: "base"});
  const text = el => {
    const out = [], walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) out.push(walk.currentNode.data);
    return out.join(" ").replace(/\s+/g, " ").trim();
  };
  const blank = s => s === "" || s === "-";
  const values = td => {
    const chips = td ? td.querySelectorAll(".chip") : [];
    return chips.length ? [...chips].map(text) : [td ? text(td) : ""];
  };
  document.querySelectorAll(".tw > table").forEach(table => {
    const head = table.rows[0];
    if (!head || !head.cells.length || head.cells[0].tagName !== "TH") return;
    const body = head.parentNode, rows = [...table.rows].slice(1), cols = [...head.cells];
    const cell = (r, c) => r.cells[c] ? text(r.cells[c]) : "";
    const numeric = cols.map((_, c) => {
      const filled = rows.map(r => cell(r, c)).filter(s => !blank(s));
      return filled.length > 0 && filled.every(s => NUM.test(s));
    });
    let col = -1, dir = 0;
    const sort = () => {
      const ordered = rows.slice().sort((a, b) => {
        if (col < 0) return rows.indexOf(a) - rows.indexOf(b);
        const x = cell(a, col), y = cell(b, col);
        if (blank(x) !== blank(y)) return blank(x) ? 1 : -1;
        const cmp = numeric[col] ? parseFloat(x) - parseFloat(y) : collator.compare(x, y);
        return cmp * dir || rows.indexOf(a) - rows.indexOf(b);
      });
      ordered.forEach(r => body.appendChild(r));
      cols.forEach((th, c) => th.setAttribute("aria-sort", c !== col ? "none" : dir > 0 ? "ascending" : "descending"));
    };
    cols.forEach((th, c) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "sort";
      button.title = "Sort by this column";
      button.append(...th.childNodes);
      const arrow = document.createElement("span");
      arrow.className = "arrow";
      arrow.setAttribute("aria-hidden", "true");
      button.append(arrow);
      th.append(button);
      th.setAttribute("aria-sort", "none");
      button.addEventListener("click", () => {
        const first = numeric[c] ? -1 : 1;
        if (col !== c) { col = c; dir = first; }
        else if (dir === first) dir = -first;
        else { col = -1; dir = 0; }
        sort();
      });
    });
    if (rows.length < FILTER_FROM) return;
    const bar = document.createElement("div");
    bar.className = "tf";
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Filter rows";
    search.setAttribute("aria-label", "Filter the rows of this table");
    bar.append(search);
    const selects = [];
    cols.forEach((th, c) => {
      if (numeric[c]) return;
      const seen = new Set();
      rows.forEach(r => values(r.cells[c]).forEach(v => { if (!blank(v)) seen.add(v); }));
      if (seen.size < 2 || seen.size > MAX_CHOICES || seen.size >= rows.length) return;
      const name = text(th), select = document.createElement("select");
      select.setAttribute("aria-label", name);
      select.append(new Option(name + ": all", ""));
      [...seen].sort(collator.compare).forEach(v => select.append(new Option(v, v)));
      selects.push([c, select]);
      bar.append(select);
    });
    const count = document.createElement("span");
    count.className = "count";
    count.setAttribute("aria-live", "polite");
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "Clear";
    clear.hidden = true;
    bar.append(clear, count);
    const haystack = new Map(rows.map(r => [r, text(r).toLowerCase()]));
    const filter = () => {
      const terms = search.value.toLowerCase().split(/\s+/).filter(Boolean);
      let shown = 0;
      rows.forEach(r => {
        const hit = terms.every(t => haystack.get(r).includes(t))
          && selects.every(([c, s]) => !s.value || values(r.cells[c]).includes(s.value));
        r.hidden = !hit;
        shown += hit;
      });
      clear.hidden = !terms.length && selects.every(([, s]) => !s.value);
      count.textContent = shown === rows.length ? rows.length + " rows" : shown + " of " + rows.length + " rows";
    };
    search.addEventListener("input", filter);
    selects.forEach(([, s]) => s.addEventListener("change", filter));
    clear.addEventListener("click", () => { search.value = ""; selects.forEach(([, s]) => { s.value = ""; }); filter(); search.focus(); });
    table.parentNode.before(bar);
    filter();
  });
})();
"""


def who(stage):
    kind, text = STAGE_WHO[stage]
    label = {"code": "code", "model": "model", "prose": "model, from prose", "you": "you"}[kind]
    return f'<span class="who {kind}" title="{esc(text)}">{label}</span>'


def bar(label, count, width, cls="", leak=""):
    w = max(22, min(100, width))
    leak_html = f'<span class="leak">{esc(leak)}</span>' if leak else ""
    return f'<div class="stage"><div class="bar {cls}" style="width:{w:.0f}%"><span>{esc(label)}</span><b>{count}</b>{leak_html}</div></div>'


def render(d):
    L = d["ledger"]
    top = max(1, L["seen"])

    def pct(n):
        return 100 * n / top

    parts = [f'<title>Triage funnel</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>{CSS}</style>',
             '<div class="wrap">', '<h1>Triage funnel</h1>',
             f'<p class="sub">Every mailbox and sync script of {len(d["vaults"])} vaults, through exclusion, routing, classification, holds and execution. '
             f'Counts are the last {d["days"]} days ({d["since"]} to {d["today"]}); the rules are what applies right now. Generated {d["generated"]} from the state under <code>{esc(d["home"])}</code>.</p>',
             '<div class="legend"><span><span class="who code">code</span> a script applies the rule</span>'
             '<span><span class="who model">model</span> the agent judges</span>'
             '<span><span class="who prose">model, from prose</span> the agent follows a written rule, not enforced</span>'
             '<span><span class="who you">you</span> waits for the operator</span></div>']
    if d["kill_switch"]:
        parts.append('<div class="kill">Kill switch on: auto-triage.off exists, every unattended run acts on nothing.</div>')

    parts.append('<div class="funnel">')
    parts.append(bar("Fetched threads", L["seen"], 100, leak=f'{L["skipped"]} already known' if L["skipped"] else ""))
    after = L["seen"] - L["excluded"]
    parts.append(bar("After exclusions", after, pct(after), leak=f'{L["excluded"]} excluded' if L["excluded"] else ""))
    parts.append(bar("Routed to a vault", L["routed"], pct(L["routed"]), leak=f'{L["unrouted"]} unrouted, {L["suppressed"]} suppressed'))
    parts.append(bar("Staged as notes", d["staged"], pct(d["staged"])))
    parts.append(bar("Acted on unattended", d["acted"], pct(d["acted"])))
    parts.append(bar("Held for you", d["waiting_items"], pct(d["waiting_items"]), cls="hold"))
    parts.append(bar("Decided by you", d["interactive_window"], pct(d["interactive_window"]), cls="you"))
    parts.append('</div>')
    parts.append('<p class="note">Fetched, excluded, routed and unrouted come from the ingest ledger; staged from the run logs; acted from the quarantine manifests; held from the proposals waiting; decided from the vaults\' decision ledgers. '
                 'A thread routed to two vaults counts once here and once per vault below.</p>')

    # 1. Fetch
    parts.append(f'<h2>1. Fetch {who("fetch")}</h2>')
    parts.append('<p class="note">Each mailbox is read once per run, however many vaults declare it; a sync script writes straight into its vault\'s triage and is not routed. '
                 'What each vault wants from a mailbox is on that vault\'s card under 3. Route.</p>')
    parts.append('<div class="tw"><table><tr><th>Mailbox</th><th>Read by</th><th>Declared by</th><th class="n">Seen</th><th class="n">Routed</th><th class="n">Unrouted</th><th class="n">Excluded</th></tr>')
    for mb in sorted(set(d["mailbox_vaults"]) | set(L["per_mailbox"])):
        c = L["per_mailbox"].get(mb, {})
        decl = d["mailbox_vaults"].get(mb, [])
        via = sorted({how for _, _, how in decl})
        parts.append(f'<tr><td class="m">{esc(mb)}</td><td>{"".join(f"<span class=chip>{esc(h)}</span>" for h in via) or "<span class=note>?</span>"}</td>'
                     f'<td>{"".join(f"<span class=chip>{esc(v)}</span>" for v, _, _ in decl) or "<span class=note>not declared</span>"}</td>'
                     f'<td class="n">{c.get("seen", 0)}</td><td class="n">{c.get("routed", 0)}</td><td class="n">{c.get("unrouted", 0)}</td><td class="n">{c.get("excluded", 0)}</td></tr>')
    parts.append('</table></div>')
    parts.append('<p class="note">"connector" is a mailbox the agent reads through a connector; "script" is one a vault script reads and prints candidates from, writing nothing. Both are fetched once per run and routed the same way.</p>')
    scripts = [s for s in d["sources"] if s["type"].startswith("sync-script")]
    if scripts:
        written = Counter()
        for r in d["runs"]:
            for s in r["sync_runs"]:
                written[(s.get("vault"), (s.get("script") or "").split("/")[-1])] += s.get("written") or 0
        parts.append('<div class="tw"><table><tr><th>Sync script</th><th>Vault</th><th>Relevant when</th><th class="n">Written</th></tr>')
        for s in scripts:
            key = next((k for k in written if k[0] == s["vault"] and k[1] and k[1] in s["endpoint"]), None)
            parts.append(f'<tr><td class="m">{esc(s["source"])}</td><td>{esc(s["vault"])}</td><td>{esc(s["relevant"])}</td><td class="n">{written.get(key, 0) if key else "-"}</td></tr>')
        parts.append('</table></div>')
    parts.append('<details><summary>Runs in the window</summary><div class="tw"><table><tr><th>Run</th><th>Invocation</th><th class="n">Mailboxes read</th><th class="n">Staged</th><th class="n">Errors</th><th class="n">Warnings</th></tr>')
    for r in reversed(d["runs"]):
        parts.append(f'<tr><td class="m">{esc(r["run"])}</td><td>{esc(r["invocation"])}</td><td class="n">{r["mailboxes_read"]}/{r["mailboxes"]}</td><td class="n">{r["written_total"]}</td>'
                     f'<td class="n">{"<span class=alert>" + str(r["errors"]) + "</span>" if r["errors"] else 0}</td><td class="n">{r["warnings"]}</td></tr>')
    parts.append('</table></div></details>')

    # 2. Exclude
    parts.append(f'<h2>2. Exclude {who("exclude")}</h2>')
    parts.append(f'<p class="note">{len(d["exclusions"])} entries in <code>triage-exclusions.json</code>, matched after the fetch, never as a query. An entry under "every mailbox" applies to all of them; a group drops a thread when any of its matchers fits. '
                 f'"Dropped" is what each run\'s log reports per entry; {d["drops_unparsed_runs"]} run(s) in the window had only a prose line this page could not read.</p>')
    parts.append('<div class="tw"><table><tr><th>Mailbox</th><th>Match</th><th>Value</th><th>Why</th><th>Added</th><th class="n">Dropped</th></tr>')
    for e in sorted(d["exclusions"], key=lambda e: (e["mailbox"] != "*", e["mailbox"], e["kind"] != "group", e["kind"], e["value"])):
        scope = '<span class="chip on">every mailbox</span>' if e["mailbox"] == "*" else f'<span class="m">{esc(e["mailbox"])}</span>'
        value = ("<b>" + esc(e["label"]) + "</b><br>" + "".join(f'<span class="chip">{esc(m)}</span>' for m in e["matchers"])) if e["kind"] == "group" else f'<span class="m">{esc(e["value"])}</span>'
        parts.append(f'<tr><td>{scope}</td><td><span class="chip">{esc(e["kind"])}</span></td><td>{value}</td>'
                     f'<td>{esc(clip(e["reason"], 140))}</td><td>{esc(e["added"])}</td><td class="n">{e["dropped"]}</td></tr>')
    parts.append('</table></div>')

    # 3. Route
    parts.append(f'<h2>3. Route {who("route")}</h2>')
    parts.append('<p class="note">Each card shows a vault\'s purpose line and, under it, its Relevant-when rule for every mailbox it declares. A thread goes to the vault they fit, or to none. '
                 'Routing decides only which vault; what an item means is decided inside the vault.</p>')
    parts.append('<div class="cards">')
    for v in d["vaults"]:
        n = L["routed_per_vault"].get(v["name"], 0)
        rules = "".join(f'<li><span class="m">{esc(r["mailbox"])}</span>{esc(r["relevant"]) or "<span class=note>no rule written</span>"}</li>'
                        for r in v["mailboxes"])
        parts.append(f'<div class="card"><h3>{esc(v["name"])} <span class="chip">{n} routed</span></h3><p class="note" style="margin:0">{esc(v["purpose"])}</p>'
                     + (f'<ul class="rules">{rules}</ul>' if rules else '<p class="note">No mailbox declared.</p>') + '</div>')
    parts.append('</div>')
    if L["unrouted_samples"]:
        parts.append('<details><summary>Unrouted, by mailbox (latest three subjects each)</summary><div class="tw"><table><tr><th>Mailbox</th><th class="n">Unrouted</th><th>Examples</th></tr>')
        for mb, subs in L["unrouted_samples"].items():
            parts.append(f'<tr><td class="m">{esc(mb)}</td><td class="n">{L["per_mailbox"][mb].get("unrouted", 0)}</td><td>{"<br>".join(esc(clip(s, 90)) for s in subs)}</td></tr>')
        parts.append('</table></div></details>')

    # 4. Classify
    g = d["gate"]
    parts.append(f'<h2>4. Classify {who("classify")}</h2>')
    parts.append(f'<p class="note">Every interactive decision is recorded with the action the agent recommended and the one you chose. An action type is offered for unattended runs once its last {g["window"]} decisions in a vault were at least {int(g["share"] * 100)}% the recommendation unchanged.</p>')
    parts.append('<div class="tw"><table><tr><th>Vault</th><th>Action type</th><th class="n">Decisions</th><th class="n">Last window</th><th>Accepted unchanged</th><th>Window</th><th>Switched on</th></tr>')
    for vault, dd in sorted(d["decisions"].items()):
        on = set((d["switches"].get(vault) or {}).get("on") or [])
        for t in dd["types"]:
            fill = "short" if t["share"] < g["share"] else ""
            state = ('<span class="chip on">on</span>' if t["type"] in on
                     else ("<span class=note>eligible</span>" if t["type"].startswith(("Delete (", "Dismiss (")) else "<span class=note>never automated</span>"))
            parts.append(f'<tr><td>{esc(vault)}</td><td>{esc(t["type"])}</td><td class="n">{t["n"]}</td><td class="n">{t["accepted"]}/{t["window_n"]}</td>'
                         f'<td><div class="gate"><div class="track"><div class="fill {fill}" style="width:{int(t["share"] * 100)}%"></div></div><span>{int(t["share"] * 100)}%</span></div></td>'
                         f'<td class="note">{esc(t["first"])} to {esc(t["last"])}</td><td>{state}</td></tr>')
    parts.append('</table></div>')
    overrides = [(v, t, o) for v, dd in d["decisions"].items() for t in dd["types"] for o in t["overrides"]]
    if overrides:
        parts.append(f'<details><summary>The {len(overrides)} overrides in the windows</summary><div class="tw"><table><tr><th>Vault</th><th>Recommended</th><th>Chosen</th><th>Item</th><th>Date</th></tr>')
        for v, t, o in sorted(overrides, key=lambda x: x[2]["date"] or "", reverse=True):
            parts.append(f'<tr><td>{esc(v)}</td><td>{esc(t["type"])}</td><td>{esc(o["chosen"])}</td><td>{esc(clip(o["item"], 80))}</td><td>{esc(o["date"])}</td></tr>')
        parts.append('</table></div></details>')

    # 5. Hold
    parts.append(f'<h2>5. Hold {who("hold")}</h2>')
    parts.append('<p class="note">A scheduled run never acts on an item that is:</p><ul>' + "".join(f"<li>{esc(h)}</li>" for h in d["hold_rules"]) + '</ul>')
    if d["proposals"]:
        parts.append(f'<p class="note">{d["waiting_items"]} item(s) in {len(d["proposals"])} proposal(s) waiting for your next interactive run; {d["decided"]} proposals decided so far.</p>')
        for p in d["proposals"]:
            parts.append(f'<h3>{esc(p["vault"])} <span class="chip">{esc(p["run"])}</span></h3><div class="tw"><table><tr><th>Item</th><th>Recommended</th><th>Held because</th></tr>')
            for i in p["items"]:
                parts.append(f'<tr><td>{esc(clip(i["item"], 90))}</td><td>{esc(i["recommended"])}</td><td>{esc(i["held"])}</td></tr>')
            parts.append('</table></div>')
    else:
        parts.append('<p class="note">Nothing is waiting.</p>')

    # 6. Execute
    parts.append(f'<h2>6. Execute {who("execute")}</h2>')
    parts.append('<p class="note">Only these action types run unattended, per vault; everything else is proposed. What a run takes goes to the quarantine outside the vault, never deleted; one restore brings it back and switches that type off again.</p>')
    parts.append('<div class="cards">')
    for v in d["vaults"]:
        sw = d["switches"].get(v["name"]) or {}
        chips = "".join(f'<span class="chip on">{esc(a)}</span>' for a in sw.get("on") or []) or '<span class="note">nothing switched on: every item is proposed</span>'
        chips += "".join(f'<span class="chip off">{esc(a if isinstance(a, str) else a.get("action", a))}</span>' for a in sw.get("demoted") or [])
        acted = sum(len(q["items"]) for q in d["quarantine"] if q["vault"] == v["name"] and q["in_window"])
        parts.append(f'<div class="card"><h3>{esc(v["name"])} <span class="chip">{acted} acted this window</span></h3>{chips}</div>')
    parts.append('</div>')
    if d["quarantine"]:
        parts.append('<h3>Quarantine runs</h3>')
        for q in reversed(d["quarantine"]):
            parts.append(f'<details><summary>{esc(q["vault"])} {esc(q["run"])}: {len(q["items"])} item(s){"" if q["in_window"] else " (older than the window)"}</summary>'
                         '<div class="tw"><table><tr><th>Item</th><th>Action</th><th>Why</th></tr>')
            for i in q["items"]:
                parts.append(f'<tr><td>{esc(clip(i["item"], 90))}</td><td>{esc(i["action"])}</td><td>{esc(clip(i["reason"], 200))}</td></tr>')
            parts.append(f'</table></div><p class="note">Restore:</p><pre>{esc(q["restore"])}</pre></details>')

    # 7. Operator
    parts.append(f'<h2>7. You {who("operator")}</h2>')
    acted_text = ", ".join(f"{n} {esc(a)}" for a, n in sorted(d["acted_by_action"].items()))
    parts.append(f'<p class="note">In the window you took {d["interactive_window"]} interactive decisions, '
                 f'{sum(x["window_accepted"] for x in d["decisions"].values())} of them the recommendation unchanged; {d["waiting_items"]} item(s) wait in proposals; {d["acted"]} were taken unattended'
                 + (": " + acted_text if acted_text else "") + '.</p>')
    parts.append('<div class="foot">Read from <code>vaults.json</code>, each vault\'s <code>## Triage sources</code>, <code>triage-exclusions.json</code>, <code>cache/ingest/ledger.json</code> and <code>cache/ingest/runs/</code>, '
                 '<code>cache/triage/decisions/</code>, <code>cache/triage/proposals/</code>, <code>auto-triage.json</code>, <code>auto-triage.off</code> and <code>quarantine/</code>. Nothing on this page was written by hand.</div>')
    parts.append('</div>')
    data = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    parts.append(f'<script id="data" type="application/json">{data}</script>')
    parts.append("<script>" + TABLES_JS + "</script>")
    return "\n".join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--paraos-home", default=os.environ.get("PARAOS_HOME") or os.path.expanduser("~/.paraos"))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    home = os.path.normpath(args.paraos_home)
    data = gather(home, args.days)
    out = args.out or os.path.join(home, "cache", "funnel", "funnel.html")
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render(data))
    print(json.dumps({"out": out, "page": "funnel", "title": "Triage funnel",
                      "description": f"What every vault's inbound passes through, stage by stage, with the rules at each stage and the last {args.days} days' counts.",
                      "key": home}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
