#!/usr/bin/env python3
"""Run every skill scan from two refs against the vaults this machine registers, and diff what
they report: where a candidate crashes, and what it says differently from what users run now,
before a session is spent on it. A maintainer tool; nothing here ships.

    py -3 tools/field_test.py [--base origin/stable] [--head origin/main] [--today YYYY-MM-DD]
                              [--vault NAME]... [--skip NAME]... [--no-example]
                              [--paraos-home DIR] [--jobs N] [--keep]

Each ref's base/, addons/ and multi-vault/ are exported with `git archive` and run from there.
Every active vault in the registry is scanned (`--vault` narrows to the ones named, `--skip`
leaves one out), and so is examples/belfoot-vault/ from the working tree, as `example`. Each
side gets its own scratch para-os home holding the COPIED files and a registry of only the
vaults scanned, so a scan's own writes land nowhere real. A vault is only read.

The scans, all on `--today` (default the system date), are VAULT_SCANS per vault and
REGISTRY_SCANS once; upgrade, audit and clean read the kit from this repo at the side's own
ref, and upgrade measures what the vault holds, not this machine's user-level skills, which
would repeat under every vault. clean phase 3 runs last, since the brief and the Command
Center's vault scan read the stamp it writes.
Left out: ingest's prepare, which runs each vault's sync and fetch scripts against live
services, archive, which needs an entity, and prep, which needs a person.

Test a stamped candidate (/release steps 2 to 6): where head still carries base's template
marker over a changed template, upgrade and audit read head's template as each vault's own
revision, and the report says so.

Each output has the scratch paths replaced, then the two are diffed, a list as a multiset of
its items, so a reordering is no change. The report goes to `<paraos home>/data/test-runs/
<YYYYMMDD-HHMM> field-test <base>..<head>.md`, never into the repo, and stdout is one JSON
document with its path and each scan's status. Exit 1 where a scan crashes on `--head` and
not on `--base`, 2 for a ref that does not resolve or no vault to scan, else 0: a change is
for a person to read, not a failure.
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTED = ("base", "addons", "multi-vault")
EXAMPLE = ROOT / "examples" / "belfoot-vault"
# What the scans read from the para-os home: no message text, no quarantined file, no secret.
COPIED = ("*.json", "auto-triage.off", "cache/ingest/ledger.json", "cache/ingest/runs/*.json",
          "cache/triage/**/*", "cache/triage-email/*.json", "cache/*/synced.json",
          "data/*/synced.json", "cache/pages.json", "cache/*/dashboards.json", "data/deep-clean/*",
          "quarantine/*/*/manifest.json")
TIMEOUT = 600
CHANGES_SHOWN = 40
VALUE_CAP = 300

SKILLS = "base/.claude/skills"
VAULT_SCANS = {
    "brief": (f"{SKILLS}/para-daily-brief/scripts/brief_scan.py",
              ["--vault", "{vault}", "--today", "{today}", "--paraos-home", "{home}"]),
    "triage": (f"{SKILLS}/para-triage/scripts/triage_scan.py",
               ["--vault", "{vault}", "--now", "{today}T12:00:00+00:00", "--paraos-home", "{home}"]),
    "pipeline": (f"{SKILLS}/para-pipeline/scripts/pipeline_scan.py",
                 ["--vault", "{vault}", "--today", "{today}"]),
    "clean-1": (f"{SKILLS}/para-deep-clean/scripts/clean_scan.py",
                ["--vault", "{vault}", "--phase", "1", "--today", "{today}", "--clone", "{repo}",
                 "--ref", "{ref}"]),
    "clean-4": (f"{SKILLS}/para-deep-clean/scripts/clean_scan.py",
                ["--vault", "{vault}", "--phase", "4", "--today", "{today}", "--clone", "{repo}",
                 "--ref", "{ref}"]),
    "upgrade": (f"{SKILLS}/para-upgrade/scripts/upgrade_scan.py",
                ["--vault", "{vault}", "--clone", "{repo}", "--ref", "{ref}", "--paraos-home",
                 "{home}", "--user-skills", "{home}/no-user-skills"]),
    "activity": ("addons/activity/.claude/skills/para-activity-review/scripts/review_scan.py",
                 ["--vault", "{vault}", "--today", "{today}"]),
}
REGISTRY_SCANS = {
    "global": ("multi-vault/para-command-center/scripts/global_scan.py",
               ["--today", "{today}", "--paraos-home", "{home}"]),
    "audit": ("multi-vault/para-audit/scripts/audit_scan.py",
              ["--clone", "{repo}", "--ref", "{ref}", "--paraos-home", "{home}"]),
}
LAST_SCANS = {
    "clean-3": (f"{SKILLS}/para-deep-clean/scripts/clean_scan.py",
                ["--vault", "{vault}", "--phase", "3", "--today", "{today}", "--clone", "{repo}",
                 "--ref", "{ref}"]),
}
REGISTRY = "(registry)"
MISSING = object()
IDENTITY = ("name", "file", "path", "check", "source", "skill", "item", "thread_id", "mailbox",
            "vault", "label", "id")
MARKER_RE = re.compile(r"<!-- para-os-template: (\S+) -->")


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, encoding="utf-8",
                          errors="replace")


def resolve(ref):
    done = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return done.stdout.strip() if done.returncode == 0 else None


def unstamped(base_template, head_template):
    """The marker both templates carry where their text differs: head is not stamped yet."""
    marks = [MARKER_RE.search(t or "") for t in (base_template, head_template)]
    same = all(marks) and marks[0].group(1) == marks[1].group(1)
    return marks[0].group(1) if same and base_template != head_template else None


def export(sha, folder):
    data = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", sha, *EXPORTED],
                          capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        try:
            tar.extractall(folder, filter="data")
        except TypeError:  # a Python before the extraction filters
            tar.extractall(folder)


def scratch_home(home, folder, entries):
    """The COPIED files of the para-os home at `folder`, its registry `entries`."""
    folder.mkdir(parents=True)
    for pattern in COPIED if home.is_dir() else ():
        for path in sorted(p for p in home.glob(pattern) if p.is_file()):
            target = folder / path.relative_to(home)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (folder / "vaults.json").write_text(json.dumps(entries, indent=1) + "\n", encoding="utf-8")


def run(command, env):
    """{code, out, error}: `out` the parsed JSON, `error` set only where the scan crashed or
    printed no JSON on a non-zero exit."""
    try:
        done = subprocess.run(command, capture_output=True, env=env, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"code": None, "out": None, "error": f"timed out after {TIMEOUT}s"}
    stdout = done.stdout.decode("utf-8", errors="replace")
    stderr = done.stderr.decode("utf-8", errors="replace").strip()
    try:
        out = json.loads(stdout) if stdout.strip() else None
    except ValueError:
        out = None
    crashed = "Traceback (most recent call last)" in stderr or (done.returncode and out is None)
    last = stderr.splitlines()[-1] if stderr else f"exit {done.returncode}, no output"
    return {"code": done.returncode, "out": out, "error": last if crashed else None}


def swaps(*folders, sha=None):
    """(spelling, placeholder) for every way a scan may write each folder, and the side's
    commit as `<ref>`, longest first."""
    out = {(sha, "<ref>")} if sha else set()
    for folder, placeholder in folders:
        for spelling in {str(folder), folder.as_posix(), os.path.realpath(folder),
                         Path(os.path.realpath(folder)).as_posix()}:
            out |= {(spelling, placeholder), (os.path.normcase(spelling), placeholder)}
    return sorted(out, key=lambda pair: -len(pair[0]))


def normalise(value, pairs):
    if isinstance(value, str):
        for spelling, placeholder in pairs:
            value = value.replace(spelling, placeholder)
        return value
    if isinstance(value, list):
        return [normalise(v, pairs) for v in value]
    if isinstance(value, dict):
        return {normalise(k, pairs): normalise(v, pairs) for k, v in value.items()}
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def identity(a, b):
    """The IDENTITY key every object in both lists carries, once per list, else None."""
    for key in IDENTITY:
        values = [[x.get(key) if isinstance(x, dict) else None for x in xs] for xs in (a, b)]
        if (a or b) and all(isinstance(v, (str, int)) and v is not True and v is not False
                            for vs in values for v in vs) \
                and all(len(set(vs)) == len(vs) for vs in values):
            return key
    return None


def differences(a, b, path="$"):
    """(path, before, after) for each place two JSON values differ: an object key by key, a
    list of objects one IDENTITY names paired on it, any other list as a multiset, each item
    it lost or gained under `<path>[]`; MISSING on the side that lacks it."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            yield from differences(a.get(key, MISSING), b.get(key, MISSING), f"{path}.{key}")
    elif isinstance(a, list) and isinstance(b, list) and identity(a, b):
        key = identity(a, b)
        left, right = {x[key]: x for x in a}, {x[key]: x for x in b}
        for k in sorted(set(left) | set(right), key=str):
            yield from differences(left.get(k, MISSING), right.get(k, MISSING), f"{path}[{key}={k}]")
    elif isinstance(a, list) and isinstance(b, list):
        before, after = Counter(map(canonical, a)), Counter(map(canonical, b))
        for item in sorted((before - after).elements()):
            yield f"{path}[]", json.loads(item), MISSING
        for item in sorted((after - before).elements()):
            yield f"{path}[]", MISSING, json.loads(item)
    elif a is MISSING or b is MISSING or canonical(a) != canonical(b):
        yield path, a, b


def compare(base, head):
    """(status, changes) for one scan run on both sides."""
    if base["error"] and head["error"]:
        return f"crashes on both: {head['error']}", []
    if head["error"]:
        return f"CRASH on head: {head['error']}", []
    if base["error"]:
        return f"fixed: crashed on base ({base['error']})", []
    changes = list(differences({"exit": base["code"], "out": base["out"]},
                               {"exit": head["code"], "out": head["out"]}))
    return (f"{len(changes)} change{'s' * (len(changes) != 1)}" if changes else "same"), changes


def shown(value):
    text = "(absent)" if value is MISSING else canonical(value)
    return text if len(text) <= VALUE_CAP else text[:VALUE_CAP] + "..."


def change_line(path, before, after):
    if before is MISSING:
        return f"- `{path}` gained: {shown(after)}"
    if after is MISSING:
        return f"- `{path}` lost: {shown(before)}"
    return f"- `{path}`: {shown(before)} -> {shown(after)}"


def report(meta, results, columns):
    lines = [f"# Field test {meta['base']} -> {meta['head']}", "",
             f"Run {meta['run']} on `--today {meta['today']}`: base `{meta['base_sha']}`, head "
             f"`{meta['head_sha']}`. Not scanned: {', '.join(meta['skipped']) or 'none'}.", ""]
    if meta["unstamped"]:
        lines += [f"Head still carries base's marker `{meta['unstamped']}` over a changed template, "
                  "so upgrade and audit take head's own template as each vault's baseline and "
                  "report this cycle's template changes as drift. Test a stamped candidate.", ""]
    lines += ["| Vault | " + " | ".join(columns) + " |", "|---|" + "---|" * len(columns)]
    for vault, scans in results.items():
        lines.append(f"| {vault} | " + " | ".join(scans.get(c, ("-", []))[0].split(":")[0]
                                                    for c in columns) + " |")
    for vault, scans in results.items():
        for scan, (status, changes) in scans.items():
            if status == "same" or status == "not mounted":
                continue
            lines += ["", f"## {vault}: {scan}, {status}", ""]
            lines += [change_line(*c) for c in changes[:CHANGES_SHOWN]]
            if len(changes) > CHANGES_SHOWN:
                lines.append(f"- and {len(changes) - CHANGES_SHOWN} more")
    return "\n".join(lines) + "\n"


def selected(entries, names, skip, example):
    active = [e for e in entries if isinstance(e, dict) and e.get("active") is True
              and e.get("name") and e.get("path")]
    chosen = [e for e in active if (not names or e["name"] in names) and e["name"] not in skip]
    if example and "example" not in skip:
        chosen.append({"name": "example", "path": EXAMPLE.as_posix(),
                       "purpose": "The kit's example vault.", "active": True})
    return chosen, sorted(e["name"] for e in active if e not in chosen)


def field_test(args):
    home = Path(args.paraos_home or os.environ.get("PARAOS_HOME") or Path.home() / ".paraos")
    shas = {side: resolve(ref) for side, ref in (("base", args.base), ("head", args.head))}
    for side, sha in shas.items():
        if sha is None:
            raise ValueError(f"{getattr(args, side)} names no commit")
    try:
        entries = json.loads((home / "vaults.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        entries = []
    vaults, skipped = selected(entries if isinstance(entries, list) else [], set(args.vault),
                               set(args.skip), not args.no_example)
    if not vaults:
        raise ValueError("no vault to scan")
    today = args.today or date.today().isoformat()
    tmp = Path(tempfile.mkdtemp(prefix="field-test-"))
    try:
        sides = {}
        for side, sha in shas.items():
            kit, scratch = tmp / side / "kit", tmp / side / "home"
            export(sha, kit)
            scratch_home(home, scratch, vaults)
            env = dict(os.environ, PARAOS_HOME=str(scratch))
            sides[side] = {"kit": kit, "home": scratch, "sha": sha, "env": env}

        def task(side, scan, script, template, vault):
            s = sides[side]
            fill = {"vault": vault["path"] if vault else "", "today": today, "home": str(s["home"]),
                    "repo": str(ROOT), "ref": s["sha"]}
            command = [sys.executable, str(s["kit"] / script)] + [a.format(**fill) for a in template]
            result = run(command, s["env"])
            pairs = swaps((s["kit"], "<kit>"), (s["home"], "<home>"), sha=s["sha"])
            return side, (vault["name"] if vault else REGISTRY), scan, dict(
                result, out=normalise(result["out"], pairs))

        mounted = [v for v in vaults if Path(v["path"]).is_dir()]
        waves = [[(side, scan, *spec, v) for side in sides for v in mounted
                  for scan, spec in VAULT_SCANS.items()]
                 + [(side, scan, *spec, None) for side in sides
                    for scan, spec in REGISTRY_SCANS.items()],
                 [(side, scan, *spec, v) for side in sides for v in mounted
                  for scan, spec in LAST_SCANS.items()]]
        runs = {}
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for wave in waves:
                for side, name, scan, result in pool.map(lambda t: task(*t), wave):
                    runs[side, name, scan] = result
        results = {v["name"]: {scan: ("not mounted", []) for scan in {**VAULT_SCANS, **LAST_SCANS}}
                   for v in vaults if v not in mounted}
        for (side, name, scan) in sorted(k for k in runs if k[0] == "head"):
            results.setdefault(name, {})[scan] = compare(runs["base", name, scan],
                                                         runs["head", name, scan])
    finally:
        if args.keep:
            print(f"field_test: kept {tmp}", file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    columns = [*VAULT_SCANS, *LAST_SCANS, *REGISTRY_SCANS]
    run_at = datetime.now()
    templates = [git("show", f"{shas[side]}:base/.claude/para-os/core.md").stdout
                 or git("show", f"{shas[side]}:base/CLAUDE.md.template").stdout for side in shas]
    meta = {"base": args.base, "head": args.head, "base_sha": shas["base"][:7],
            "head_sha": shas["head"][:7], "today": today, "skipped": skipped,
            "run": run_at.strftime("%Y-%m-%d %H:%M"), "unstamped": unstamped(*templates)}
    label = f"{args.base}..{args.head}".replace("/", "-")
    path = home / "data" / "test-runs" / f"{run_at:%Y%m%d-%H%M} field-test {label}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report(meta, results, columns), encoding="utf-8")
    statuses = {vault: {scan: status for scan, (status, _) in scans.items()}
                for vault, scans in results.items()}
    regressed = sum(status.startswith("CRASH") for scans in statuses.values()
                    for status in scans.values())
    return {"report": path.as_posix(), **meta, "regressions": regressed,
            "statuses": statuses}, 1 if regressed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diff every skill scan between two refs on the "
                                             "registered vaults.")
    ap.add_argument("--base", default="origin/stable", help="what users run (default origin/stable)")
    ap.add_argument("--head", default="origin/main", help="the candidate (default origin/main)")
    ap.add_argument("--today", help="the date every scan runs on (default the system date)")
    ap.add_argument("--vault", action="append", default=[], metavar="NAME",
                    help="scan only this registered vault (repeatable)")
    ap.add_argument("--skip", action="append", default=[], metavar="NAME",
                    help="leave this vault out, `example` included (repeatable)")
    ap.add_argument("--no-example", action="store_true", help="leave the example vault out")
    ap.add_argument("--paraos-home", help="override for $PARAOS_HOME (default ~/.paraos)")
    ap.add_argument("--jobs", type=int, default=4, help="scans run at once (default 4)")
    ap.add_argument("--keep", action="store_true", help="keep the exports and scratch homes")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    try:
        out, code = field_test(args)
    except ValueError as err:
        print(f"field_test: {err}", file=sys.stderr)
        return 2
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
