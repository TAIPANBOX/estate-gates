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
  - every `scripts/x.sh` a "gate:"/"gates:" marker inside that section names
    exists in the service's own repository, however the marker is decorated
    (an asterisk parenthetical, a plain parenthetical, or a table cell; see
    GATE_MARKER's own comment)

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
#: The semantic marker is the bare word "gate:"/"gates:"/"partly gated:";
#: asterisks, parentheses and a table's pipes are three different
#: DECORATIONS the real estate wraps it in, never the thing that makes it a
#: citation:
#:   - wardryx and most:  *(gate: `scripts/x.sh` ...)*
#:   - trailryx section 8:  (gate: `scripts/x.sh`)            (no asterisks)
#:   - costcrew, idryx, tokenfuse section 8: a table cell,
#:     "| ... | gate: `scripts/x.sh` (...) |"
#: `partly gated:` is included, not excluded: idryx.md and genaryx.md each
#: cite a real `scripts/...` gate under it (a check that only catches the
#: crude case is still a check of something, and the script it names still
#: has to exist). `\b` before the word so "delegate:"/"aggregate:" cannot
#: match (no word boundary before their "gate"/"gated").
#:
#: A marker's span can cross ONE OR MORE line breaks, each followed by
#: indentation, because a wrapped list item keeps its continuation lines
#: indented and the estate uses that shape: stack-single.md puts "gate:" at
#: the end of one line and the script on the next, indented, line (lines
#: 352-353 and 356-357; `scripts/build-context-complete.sh` and
#: `scripts/fail-before-half-the-job.sh` are cited nowhere else in that
#: file, so a dangling one there would have been silent). `\n[ \t]+` is the
#: allowed crossing, never a bare `\n`: an UNINDENTED line starts the next
#: numbered item or table row, never a continuation, so the span still ends
#: there rather than swallowing the rest of the section. It still ends at
#: the marker's own close otherwise: the next `)`, `|`, or an unindented end
#: of line, whichever comes first. Every citation observed in the real
#: estate puts its script reference before any parenthetical aside that
#: follows, and a table cell cannot contain a literal `|`, so this never
#: truncates a real script away.
#:
#: Case-INSENSITIVE, though the word is lowercase almost everywhere: two
#: places in one file write it capitalised, both real citations. Vouchryx's
#: section 8 invariant 11 writes "*(Gate:
#: `scripts/every-refusal-reaches-the-operator.sh`, ...)*" (that script
#: exists there); invariant 12, two lines later, writes "*(Gate:
#: `internal/manifest`'s five tests ...)*" (not a scripts/ path, so SCRIPT_REF
#: below still finds nothing there, but the marker itself is exactly as real).
#: What must NOT match is a different sentence three lines above invariant
#: 11, invariant 1's "*(Gate cited in CLAUDE.md, `scripts/the-algorithm-
#: comes-from-the-key.sh`, does not exist in this repository ...)*", which is
#: prose SAYING a script is missing, not citing one that holds something; a
#: gate that fired on "this does not exist" would be OVEREAGER, contradicting
#: the dossier's own sentence instead of reading it. That exclusion is not
#: about case: "Gate cited" has no colon immediately after the word at all,
#: so `\bgates?:` never matches it regardless of how the letter is cased.
#: Matching case-insensitively is what still finds the two real citations
#: rather than dropping them along with the sentence at invariant 1; the
#: citation and the sentence are told apart by the colon, not by the letter.
#:
#: STILL not read, by design, and named rather than silently missed: a
#: marker with the word AFTER the path instead of before it ("Held by:
#: `scripts/x.sh`, ..., *(gate)*", agent-passport.md, nine scripts) and a
#: path that does not start with "scripts/" even when it contains that word
#: ("`.github/scripts/validate_examples.py`", also agent-passport.md); and a
#: comma between the word and its qualifier ("*(gate, signalling half:
#: ...)*", taipan.md:170), which has no colon immediately after "gate"
#: either, the same shape as "Gate cited" above. Bringing those two
#: dossiers' own rows to the "gate:"/"gates:" form the rest of the estate
#: already uses is the next change; it is not a reason to widen this regex
#: further, which would start trading precision for reach the wrong way.
GATE_MARKER = re.compile(r"\b(?:partly gated|gates?):((?:[^)|\n]|\n[ \t]+)*)", re.IGNORECASE)
#: The path only: a script cited with a trailing argument inside the same
#: backtick span ("`scripts/declared-deps.sh list`", trailryx.md:167) still
#: names one real file to check for, and `(?:\s[^`]*)?` reads the argument
#: without capturing it.
SCRIPT_REF = re.compile(r"`(scripts/[A-Za-z0-9._/-]+)(?:\s[^`]*)?`")


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

    # What this half actually read, printed the way C9 prints its own scan
    # count: zero is a legitimate answer for one dossier (sphere-ios cites no
    # script anywhere), so this is a note, not a finding; the finding is
    # c18.no-gates-section, for a dossier this count never reaches at all.
    citations_read = 0
    dossiers_with_gates_section = 0

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
            dossiers_with_gates_section += 1
            # Only what follows a "gate:"/"gates:"/"partly gated:" token,
            # never every backticked scripts/... in the section: see
            # GATE_MARKER's own comment for why, and for the three
            # decorations (asterisk parenthetical, plain parenthetical,
            # table cell) this reads without caring which one a given
            # dossier uses, wrapped onto a second line or not.
            scripts = sorted(
                {
                    m.group(1)
                    for marker in GATE_MARKER.finditer(section)
                    for m in SCRIPT_REF.finditer(marker.group(1))
                }
            )
            citations_read += len(scripts)
            for script in scripts:
                if not estate.exists(name, script):
                    c.drift(
                        f"c18.dangling-gate:{name}",
                        f"{estate.where(ARCH, rel)} says a gate is held by `{script}`, and {estate.where(name, script)} does not exist",
                    )
    c.note(f"read {citations_read} gate citation(s) across {dossiers_with_gates_section} dossier(s) with a gates section.")
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
