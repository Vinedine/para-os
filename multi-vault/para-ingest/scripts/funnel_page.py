#!/usr/bin/env python3
"""The funnel's model: what every registered vault's inbound passes through, stage by stage,
with the rules in force at each stage and the window's counts, gathered from the state the
multi-vault layer already keeps. /para-command-center's `command_center.py` reads it through
`gather()`. It reads everything and writes nothing.

    py -3 funnel_page.py [--paraos-home DIR] [--days N] [--today YYYY-MM-DD]

The stages, and who applies each one's rule:

    1. Fetch      each mailbox once, each sync script per vault             code
    2. Exclude    triage-exclusions.json, per mailbox and for every one     code
    3. Route      the registry's purpose lines and each vault's sources     the model
    4. Classify   /para-triage in the vault, recorded with its recommendation   the model
    5. Hold       what a scheduled run never acts on                        the model
    6. Execute    the action types switched on per vault, to quarantine     code
    7. Operator   proposals waiting, interactive decisions, restores        the operator

A connector row and a fetch-script row of a vault's `## Triage sources` table both declare a
mailbox; a sync-script row does not. Counts come from the ingest ledger (fetched, excluded,
routed, unrouted, suppressed), the run logs (staged, and the drops each run's
`exclusions_applied` counts), the quarantine manifests (acted on), the proposals waiting
(held) and the vaults' decision ledgers (decided).

Run as a script, it prints `gather()`'s result as one JSON document and exits 0. The window is
the `--days` days (default 7) up to `--today` (default the system date); the para-os home is
`--paraos-home`, else `$PARAOS_HOME`, else `~/.paraos`.
"""

import argparse
import glob
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
GATE_WINDOW, GATE_SHARE = 50, 0.95


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


def executor_path():
    """auto_execute.py where the skills are installed side by side; the bare name elsewhere."""
    beside = Path(__file__).resolve().parents[2] / "para-triage" / "scripts" / "auto_execute.py"
    return str(beside) if beside.is_file() else "auto_execute.py"


def auto_triage_switches(home):
    """Per vault, `{"on", "demoted"}`: the registry entry's `auto_triage` minus the demotions in
    `cache/auto-triage/demoted.json`, else the older `auto-triage.json` for a vault whose entry
    has no `auto_triage`. The same rule `auto_execute.py` acts on."""
    legacy = load_json(os.path.join(home, "auto-triage.json"), {})
    demoted = load_json(os.path.join(home, "cache", "auto-triage", "demoted.json"), {})
    registry = load_json(os.path.join(home, "vaults.json"), [])
    action = lambda d: d.get("action") if isinstance(d, dict) else d
    out = {}
    for e in registry if isinstance(registry, list) else []:
        if isinstance(e, dict) and "auto_triage" in e:
            off = demoted.get(e.get("name"), [])
            names = {action(d) for d in off}
            out[e["name"]] = {"on": [a for a in e.get("auto_triage") or [] if a not in names], "demoted": off}
    for name, row in (legacy.items() if isinstance(legacy, dict) else []):
        if name not in out:
            names = {action(d) for d in demoted.get(name, [])}
            out[name] = {"on": [a for a in row.get("on") or [] if a not in names],
                         "demoted": list(row.get("demoted") or []) + list(demoted.get(name, []))}
    return out


def gather(home, days, today=None):
    today = today or date.today()
    since = today - timedelta(days=days)
    since_s = since.isoformat()
    registry = [v for v in load_json(os.path.join(home, "vaults.json"), [])
                if isinstance(v, dict) and v.get("name") and v.get("path")
                and v.get("active", True) and not v.get("machine")]

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
    switches = auto_triage_switches(home)
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


def day(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a YYYY-MM-DD date")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Print the funnel's model as JSON.")
    ap.add_argument("--paraos-home", default=os.environ.get("PARAOS_HOME") or os.path.expanduser("~/.paraos"))
    ap.add_argument("--days", type=int, default=7, help="the window, in days (default 7)")
    ap.add_argument("--today", type=day, help="the window's last day (default: the system date)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    json.dump(gather(os.path.normpath(args.paraos_home), args.days, args.today), sys.stdout,
              ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
