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
  - the file has a `## 8. Invariants and gates` section at all (a dossier with
    none measures nothing, rather than passing on an empty read)
  - every `scripts/x.sh` a `*(gate: ...)*`/`*(gates: ...)*` marker inside that
    section names exists in the service's own repository

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
GATES_HEADING = "## 8. Invariants and gates"
#: `*(gate: ...)*` or `*(gates: ...)*`, the word case-insensitive so a marker
#: spelled `*(Gate: ...)*` (vouchryx's own invariant 11) is still read. The
#: colon right after the word is what this must not drop: "*(partly gated:
#: ...)*" shares the word "gate" but is the WEAKER marker CLAUDE.md's own
#: vocabulary uses for a check that only catches the crude case, and reading
#: it as an enforced citation would be wrong in the other direction. `.*?`
#: with DOTALL, because a marker's own prose can wrap onto a second physical
#: line before its closing `)*`.
GATE_MARKER = re.compile(r"\*\(\s*[Gg]ates?:.*?\)\*", re.DOTALL)
SCRIPT_REF = re.compile(r"`(scripts/[A-Za-z0-9._/-]+)`")


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


def gates_section(text: str) -> str | None:
    """The text of `## 8. Invariants and gates`, or None if that heading is
    absent.

    Fence-aware the same way architecture/internal/lint/lint.go reads
    headings: a line inside a fenced code block (``` or ~~~) toggles a fence
    flag and is never read as a heading, so an example inside section 8
    cannot end it early, and a heading-shaped line inside an EARLIER fenced
    example (section 2's "gates (CLAUDE.md, verbatim): ..." blocks are the
    common one in this estate) cannot be misread as section 8 starting.

    None and "" mean different things to the caller: None is no section 8 at
    all (c18.no-gates-section, this dossier was not read for its gates);
    "" is a section 8 with nothing scannable in it, which is not a finding,
    only nothing to iterate.

    No real dossier has had a "## 5. Decisions" heading since the rewrite to
    the current twelve-section contract (architecture/internal/lint's
    `Sections`), so the previous version of this function, which looked for
    exactly that heading, matched nothing anywhere in the real estate; see
    the self-test case `c18.dangling-gate` and its 2026-09-17 fixture rewrite.
    """
    lines = text.split("\n")
    in_fence = False
    start: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or not line.startswith("## "):
            continue
        if start is None:
            if line == GATES_HEADING:
                start = i + 1
            continue
        return "\n".join(lines[start:i])
    return None if start is None else "\n".join(lines[start:])


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
        section = gates_section(text)
        if section is None:
            c.missing(
                f"c18.no-gates-section:{name}",
                f"{estate.where(ARCH, rel)} has no `{GATES_HEADING}` heading, so this gate measured nothing about the gates it cites",
            )
        else:
            # Only the gate markers, never every backticked scripts/... in the
            # section: services/vouchryx.md section 8 says, in prose, inside a
            # "*(Gate cited in CLAUDE.md, `scripts/the-algorithm-comes-from-
            # the-key.sh`, does not exist in this repository ...)*"
            # parenthetical, that a script is MISSING. Matching every
            # backticked path in the section would fire on that sentence, and
            # a gate that reads "this does not exist" as a citation would be
            # OVEREAGER: the estate already says the quiet part out loud, and
            # this gate would be wrong to contradict it.
            scripts = sorted(
                {
                    m.group(1)
                    for marker in GATE_MARKER.finditer(section)
                    for m in SCRIPT_REF.finditer(marker.group(0))
                }
            )
            for script in scripts:
                if not estate.exists(name, script):
                    c.drift(
                        f"c18.dangling-gate:{name}",
                        f"{estate.where(ARCH, rel)} says a gate is held by `{script}`, and {estate.where(name, script)} does not exist",
                    )
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
