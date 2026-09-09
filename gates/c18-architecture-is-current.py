#!/usr/bin/env python3
"""C18: every service's architecture file is current against its repository.

WHY

The architecture record (TAIPANBOX/architecture) holds one file per service
saying how it is built and why, checked against a named commit of that
service's main. A file nobody re-checks is the wiki all over again: it reads
as current and is not. This gate is the verdict: the hooks in archguard only
count commits and advise.

WHAT IS CHECKED, PER REGISTRY ENTRY

  - the file exists, or expectations/architecture.json records the service as
    pending with a date and a reason; a pending entry whose file exists is red,
    so the list cannot become a graveyard
  - the frontmatter carries verified_at, a 40-hex commit
  - that commit exists in the repository and is on its main
  - no commit touching code (anything but markdown, docs/ and LICENSE) landed
    on main after it
  - every `scripts/x.sh` the decisions table names as holding a decision exists

WHAT IT CANNOT SEE

Whether the file is TRUE. It proves the file was checked against a commit,
which is what makes reading it worth anything, not that the reading was right.

The architecture record is private, so in --mode clone this gate reports NOT
MEASURED and the run is PARTIAL. It is measured locally, like taipan was.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

ARCH = "architecture"
EXCLUDE = [":(exclude)*.md", ":(exclude)docs", ":(exclude)LICENSE"]
SHA = re.compile(r"^[0-9a-f]{40}$")


def expectations_path(estate: E.Estate) -> pathlib.Path:
    """A case may plant `_architecture-expectations.json` at the estate root;
    the self-test exports the fixture's through the environment; a real run
    reads this repository's own file."""
    override = estate.root / "_architecture-expectations.json"
    if override.exists():
        return override
    env = os.environ.get("ESTATE_GATES_ARCHITECTURE_EXPECTATIONS")
    if env:
        return pathlib.Path(env)
    return E.REPO_ROOT / "expectations" / "architecture.json"


def load_pending(estate: E.Estate) -> dict[str, dict]:
    path = expectations_path(estate)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise E.Missing(f"{path} could not be read ({exc}), so nothing may be called pending")
    pending = doc.get("pending")
    if not isinstance(pending, dict):
        raise E.Missing(f"{path} has no `pending` object")
    return pending


def frontmatter(text: str) -> dict[str, str]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise E.Missing("no frontmatter: the file does not start with ---")
    kv: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        k, sep, v = line.partition(":")
        if sep:
            kv[k.strip()] = v.strip()
    else:
        raise E.Missing("frontmatter is not closed by a second ---")
    for key in ("service", "repo", "verified", "verified_at", "status"):
        if not kv.get(key):
            raise E.Missing(f"frontmatter lacks {key}")
    return kv


def git(directory: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def tip(estate: E.Estate) -> str:
    return estate.ref if estate.mode == "ref" else "HEAD"


def decisions_section(text: str) -> str:
    i = text.find("## 5. Decisions")
    if i < 0:
        return ""
    j = text.find("\n## ", i + 1)
    return text[i : j if j > 0 else len(text)]


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C18", "every architecture file is current against its repository", estate)

    try:
        pending = load_pending(estate)
    except E.Missing as m:
        c.missing("c18.expectations-unreadable", str(m))
        return c

    try:
        paths = estate.list_files(ARCH, ".md")
    except E.Unavailable as u:
        c.unavailable("c18.architecture-unavailable", str(u))
        return c
    # exists() reads the disk, so a file dropped from the tree but still in
    # the index counts as absent, which is what a mutation that unlinks it means.
    have = {
        p[len("services/") : -3]
        for p in paths
        if p.startswith("services/") and p.count("/") == 1 and estate.exists(ARCH, p)
    }
    if not have:
        c.missing("c18.no-files", f"{ARCH} has no services/*.md at all, so this gate measured nothing")
        return c

    for name in sorted(n for n in estate.repos if n != ARCH):
        if name not in have:
            if name in pending:
                p = pending[name]
                c.ok(f"c18.pending:{name}", f"no file yet, recorded pending since {p.get('recorded')}: {p.get('why')}")
            else:
                c.drift(
                    f"c18.file-missing:{name}",
                    f"{ARCH}/services/{name}.md does not exist and expectations/architecture.json does not record {name} as pending",
                    ["Write the file, or record the gap with a date and a reason."],
                )
            continue
        if name in pending:
            c.drift(
                f"c18.stale-pending:{name}",
                f"services/{name}.md exists but expectations/architecture.json still records {name} as pending",
                ["Remove the entry: a pending list with written files in it is a graveyard."],
            )
        rel = f"services/{name}.md"
        try:
            text = estate.read_text(ARCH, rel)
        except E.Missing as m:
            c.missing(f"c18.frontmatter:{name}", f"{estate.where(ARCH, rel)}: {m}")
            continue
        try:
            front = frontmatter(text)
        except E.Missing as m:
            c.missing(f"c18.frontmatter:{name}", f"{estate.where(ARCH, rel)}: {m}")
            continue
        sha = front["verified_at"]
        try:
            directory = estate.dir_of(name)
        except E.Unavailable as u:
            c.unavailable(f"c18.repo-unavailable:{name}", str(u))
            continue
        if not SHA.match(sha) or git(directory, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
            c.missing(
                f"c18.verified-at-unknown:{name}",
                f"{estate.where(ARCH, rel)} says verified_at {sha[:12]}, which is not a commit in {estate.where(name, '')}",
            )
            continue
        if git(directory, "merge-base", "--is-ancestor", sha, tip(estate)).returncode != 0:
            c.drift(
                f"c18.verified-at-unreachable:{name}",
                f"{estate.where(ARCH, rel)}: verified_at {sha[:7]} is not on {name}'s {tip(estate)}",
                ["A branch commit was recorded. verified_at must be the commit on main the file was checked against."],
            )
            continue
        log = git(directory, "log", "--format=%h %s", f"{sha}..{tip(estate)}", "--", ".", *EXCLUDE)
        commits = [l for l in log.stdout.splitlines() if l.strip()]
        if commits:
            c.drift(
                f"c18.stale:{name}",
                f"{len(commits)} code commit(s) on {name}'s {tip(estate)} after verified_at {sha[:7]}; {estate.where(ARCH, rel)} was not re-checked",
                commits[:10] + ["Read them, update the sections they touch or bump verified_at to the new tip."],
            )
        else:
            c.ok(f"c18.current:{name}", f"verified_at {sha[:7]} is {name}'s {tip(estate)}, no code commit since")
        for script in sorted(set(re.findall(r"`(scripts/[A-Za-z0-9._/-]+)`", decisions_section(text)))):
            if not estate.exists(name, script):
                c.drift(
                    f"c18.dangling-gate:{name}",
                    f"{estate.where(ARCH, rel)} says a decision is held by `{script}`, and {estate.where(name, script)} does not exist",
                )
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
