#!/usr/bin/env python3
"""Keep the GitHub traffic numbers that GitHub throws away.

WHY THIS EXISTS

The estate publishes nothing that phones home, which is a selling point and a
measurement handicap: the only evidence a stranger arrived is what GitHub
records about the repositories themselves. GitHub keeps views, unique visitors,
clones and referrers for **fourteen days** and then deletes them. A promotion
push whose effect is read three weeks later is a push nobody can measure.

So this appends today's figures to a file that is not fourteen days old.

WHAT IT IS NOT

It is not a gate: it judges nothing and fails nothing. It is a recorder, and it
prints what it recorded so the person running it can see the day rather than
trust it.

THE RULE THIS ENFORCES ON ITSELF

Subjects come from `estate.json`, the same registry every gate here reads. A
repository added to the estate is snapshotted from the next run without anybody
remembering to add it, and a hand-written list in this file would be the exact
defect the registry exists to prevent.

WHAT IT COSTS

Nothing. It reads the GitHub API with the token `gh` already holds, writes one
local file, and starts no workflow. There is deliberately no scheduled job
here: a cron in a private repository is metered, and that is a decision for
Yurii rather than a default in a script.

USAGE

    ./scripts/traffic-snapshot.py                 # append today, print it
    ./scripts/traffic-snapshot.py --show          # print the file's history
    ./scripts/traffic-snapshot.py --out FILE      # somewhere other than the default

Traffic endpoints need push access to the repository, so a token without it
returns 403 and that repository is recorded as unreadable rather than as zero.
Zero and "not measured" are different answers and this file keeps them apart.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "estate.json"
DEFAULT_OUT = ROOT / "traffic" / "snapshots.ndjson"


def gh_json(path: str) -> tuple[object | None, str | None]:
    """Return (parsed, error). A 403 is an error, not an empty result."""
    p = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, timeout=60
    )
    if p.returncode != 0:
        return None, (p.stderr or p.stdout).strip().splitlines()[0][:120]
    try:
        return json.loads(p.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"unparseable: {exc}"


def subjects() -> list[tuple[str, str]]:
    reg = json.loads(REGISTRY.read_text())
    out = []
    for name, entry in sorted(reg["repos"].items()):
        gh = entry.get("github")
        if gh:
            out.append((name, gh))
    return out


def snapshot(taken: str) -> dict:
    rows = {}
    for name, gh in subjects():
        row: dict[str, object] = {}
        for key, path in (
            ("views", f"repos/{gh}/traffic/views"),
            ("clones", f"repos/{gh}/traffic/clones"),
        ):
            data, err = gh_json(path)
            if err is not None:
                row[key] = {"unreadable": err}
                continue
            assert isinstance(data, dict)
            row[key] = {"count": data.get("count"), "uniques": data.get("uniques")}
        refs, err = gh_json(f"repos/{gh}/traffic/popular/referrers")
        row["referrers"] = (
            {"unreadable": err}
            if err is not None
            else [
                {"from": r.get("referrer"), "count": r.get("count"), "uniques": r.get("uniques")}
                for r in (refs or [])
            ]
        )
        meta, err = gh_json(f"repos/{gh}")
        row["stars"] = None if err else (meta or {}).get("stargazers_count")
        row["forks"] = None if err else (meta or {}).get("forks_count")
        rows[name] = row
    return {"taken": taken, "repos": rows}


def render(snap: dict) -> str:
    lines = [f"# taken {snap['taken']}", ""]
    lines.append(f"{'repo':<28}{'views':>8}{'uniq':>7}{'clones':>8}{'uniq':>7}{'stars':>7}")
    for name, row in snap["repos"].items():
        v, c = row["views"], row["clones"]
        def cell(d: object, key: str) -> str:
            if isinstance(d, dict) and "unreadable" in d:
                return "  n/a"
            return str((d or {}).get(key, "?"))  # type: ignore[union-attr]
        lines.append(
            f"{name:<28}{cell(v,'count'):>8}{cell(v,'uniques'):>7}"
            f"{cell(c,'count'):>8}{cell(c,'uniques'):>7}"
            f"{str(row['stars']):>7}"
        )
    refs = [
        (name, r["from"], r["count"])
        for name, row in snap["repos"].items()
        if isinstance(row["referrers"], list)
        for r in row["referrers"]
    ]
    if refs:
        lines += ["", "referrers seen today:"]
        for name, src, count in sorted(refs, key=lambda x: -x[2])[:15]:
            lines.append(f"  {count:>5}  {src:<32} -> {name}")
    unreadable = [n for n, row in snap["repos"].items() if isinstance(row["views"], dict) and "unreadable" in row["views"]]
    if unreadable:
        lines += ["", f"NOT MEASURED ({len(unreadable)}): " + ", ".join(unreadable)]
        lines.append("  traffic needs push access; these are unreadable, not zero.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--show", action="store_true", help="print the history and exit")
    args = ap.parse_args()

    if args.show:
        if not args.out.exists():
            print(f"no snapshots yet at {args.out}")
            return 0
        for line in args.out.read_text().splitlines():
            snap = json.loads(line)
            print(render(snap))
            print()
        return 0

    taken = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    snap = snapshot(taken)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as fh:
        fh.write(json.dumps(snap, sort_keys=True) + "\n")
    print(render(snap))
    print(f"\nappended to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
