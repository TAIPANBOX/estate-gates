#!/usr/bin/env python3
"""C24: no public repository quotes the owner, or names him as the one who
said, asked, decided or found something.

WHY

A public repository is read by people who are not the owner. A decision the
owner made is still recorded, because a later reader must know it is a decision
and not something to re-derive: it is written as `@decided YYYY-MM-DD` and a
paraphrase in English, and never edited afterwards. What is not written is the
owner's own wording, a provenance marker carrying his first name, or his name
as the one who decided. Nothing mechanical stopped the next such line from
landing, so this gate reads every public repository the registry names for the
four shapes below. The rule is the one the genaryx repository enforces for its
own tree.

FOUR SHAPES ARE REFUSED, each on the line it occurs on

  marker          the old provenance marker: an at-sign followed by the owner's
                  first name, in any case.
  guillemet       a quotation in guillemets on a line that also carries
                  Cyrillic, the shape his quotes took.
  cyrillic-prose  Cyrillic in prose: anywhere in a non-code file, and outside a
                  string literal in a code file. A string literal may carry
                  Cyrillic, because hostile-input tests need non-Latin text, and
                  so may a file under a `testdata/` directory. A comment line
                  is prose whole, quotes and all.
  owner-named     the owner's first name capitalised as a word, on a line that
                  does not say copyright, author or maintainer. The owner as
                  copyright holder, author or maintainer is not a quote and
                  passes.

URLs are blanked before the first, second and fourth shapes run: a name inside
an address is an address.

THE NAME IS ASSEMBLED FROM PARTS, so this file does not refuse itself.

THE OUTPUT NAMES A FILE AND A LINE NUMBER, NEVER THE LINE'S TEXT. A CI log of a
public repository is public too, so printing the quote would publish it again.

WHAT IT DOES NOT CATCH

An English quote of the owner's words in ordinary quotation marks, an
attribution that does not use his name ("the owner said"), and a paraphrase that
is in fact a translation: those are prose a reader judges. In a code file a
quoted Cyrillic phrase in a comment that trails code on the same line passes,
because only a line that opens as a comment is read as prose whole. Cyrillic in
a string that spans several lines is refused, the safe way to be wrong.

WHAT IS READ

Subjects come from estate.json, never from a list here: every repository whose
entry records a public GitHub remote (`github`). A repository recorded as
private (`private_remote`) or with no public remote is skipped, and the output
says so. Each subject's tracked files are read through `_estate.py` in the
run's mode, so `--mode ref` reads the default branch as published and
`--mode clone` reads what CI clones. A subject that cannot be read is
NOT MEASURED, and the run is partial (invariant 3).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

# Assembled, never written whole. The rule must not match its own source.
FIRST = "Y" + "urii"

MARKER = re.compile("@" + FIRST.lower() + r"\b", re.IGNORECASE)
NAME = re.compile(r"\b" + FIRST + r"\b")
AUTHORSHIP = re.compile(
    r"copyright|\(c\)|\bauthors?\b|\bmaintainers?\b|\bmaintained by\b|" + chr(0xA9),
    re.IGNORECASE,
)
GUILLEMET = re.compile("[" + chr(0xAB) + chr(0xBB) + "]")
CYRILLIC = re.compile("[" + chr(0x400) + "-" + chr(0x4FF) + "]")
URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s)\]>\"]+", re.IGNORECASE)

# String literals, one line at a time. Rust and Python raw strings come first:
# their quotes do not escape, so they run to the matching close, not to the next
# quote. Python's triple quotes follow, so a one-line triple-quoted literal is
# consumed whole. A multi-line literal with Cyrillic is refused: the safe way to
# be wrong.
LITERAL = re.compile(
    r'r(#*)".*?"\1'
    r'|"""(?:[^"\\]|\\.|"(?!""))*"""'
    r"|'''(?:[^'\\]|\\.|'(?!''))*'''"
    r'|"(?:[^"\\]|\\.)*"'
    r"|'(?:[^'\\]|\\.)*'"
    r"|`(?:[^`\\]|\\.)*`"
)

# Code files, whose string literals may carry Cyrillic.
CODE = (".rs", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".py")
# Lines that open as a comment, and so are prose whole.
COMMENT_PREFIXES = {".py": ("#",)}
DEFAULT_COMMENT = ("//", "*", "/*")

#: shape -> (what it is, what to write instead)
SHAPES = {
    "marker": (
        "the old provenance marker carrying the owner's first name",
        "write @decided YYYY-MM-DD and a paraphrase in English",
    ),
    "guillemet": (
        "a quotation in guillemets, in the owner's own language",
        "paraphrase the decision in English, without quotation marks",
    ),
    "cyrillic-prose": (
        "Ukrainian prose outside a string literal",
        "paraphrase the decision in English",
    ),
    "owner-named": (
        "the owner named as the one who said, asked, decided or found something",
        "say the decision, not who made it; the owner as author or copyright holder is allowed",
    ),
}


def _detail(estate: E.Estate, found: list[tuple[str, str, int]], fix: str) -> list[str]:
    """Where each hit is, and what to write instead. Never the line's own text."""
    detail = [f"  {estate.where(repo, path)}:{n}" for repo, path, n in found[:25]]
    if len(found) > 25:
        detail.append(f"  ... and {len(found) - 25} more line(s)")
    detail.append(f"  Fix: {fix}. The line itself is not printed here.")
    return detail


def scan_line(path: str, line: str) -> list[str]:
    """The shapes a line of a tracked file falls under. Empty for a clean line."""
    out: list[str] = []
    plain = URL.sub(" ", line)
    if MARKER.search(plain):
        out.append("marker")
    if GUILLEMET.search(plain) and CYRILLIC.search(plain):
        out.append("guillemet")
    if NAME.search(plain) and not AUTHORSHIP.search(plain):
        out.append("owner-named")
    # A testdata/ file may carry Cyrillic as hostile input, as the rule states.
    if "testdata/" not in path and CYRILLIC.search(line):
        ext = pathlib.PurePosixPath(path).suffix
        code = path.endswith(CODE)
        comment = line.lstrip().startswith(COMMENT_PREFIXES.get(ext, DEFAULT_COMMENT))
        rest = LITERAL.sub('""', line) if code and not comment else line
        if CYRILLIC.search(rest):
            out.append("cyrillic-prose")
    return out


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C24", "no owner quotes in any public repository", estate)

    subjects: list[str] = []
    for repo, entry in sorted(estate.repos.items()):
        if entry.get("github"):
            subjects.append(repo)
        elif entry.get("private_remote"):
            c.note(
                f"skipped {repo}: estate.json records it as PRIVATE "
                f"({entry['private_remote']}), so it is not a public repository."
            )
        else:
            c.note(f"skipped {repo}: estate.json records no public remote for it.")

    if not subjects:
        c.missing(
            "c24.no-subjects",
            "estate.json records no public repository, so there is nothing to read "
            "for an owner quote. This check measured nothing.",
        )
        return c

    c.note(f"public repositories read: {', '.join(subjects)}.")

    hits: dict[str, list[tuple[str, str, int]]] = {shape: [] for shape in SHAPES}
    clean: list[tuple[str, int]] = []

    for repo in subjects:
        try:
            estate.dir_of(repo)
            paths = estate.list_files(repo)
        except E.Unavailable as u:
            c.unavailable(
                f"c24.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so whether it "
                f"quotes the owner is unmeasured here.",
            )
            continue
        except E.Missing as m:
            c.unavailable(
                f"c24.repo-unlistable:{repo}",
                f"{repo} could not list the files it tracks ({m}), so whether it "
                f"quotes the owner is unmeasured here.",
            )
            continue

        if not paths:
            c.missing(
                "c24.nothing-scanned",
                f"{repo} tracks no file at all in this run, so there is nothing "
                f"in it that was read.",
            )
            continue

        scanned = 0
        repo_hits = 0
        for path in paths:
            try:
                raw = estate.read_bytes(repo, path)
            except E.Missing as m:
                c.missing(
                    "c24.file-unreadable",
                    f"{estate.where(repo, path)} is tracked but cannot be read ({m}), "
                    f"so its text was not checked.",
                )
                continue
            if b"\0" in raw[:8000]:
                continue  # binary, by git's own heuristic
            scanned += 1
            text = raw.decode("utf-8", "replace")
            for n, line in enumerate(text.split("\n"), 1):
                for shape in scan_line(path, line):
                    hits[shape].append((repo, path, n))
                    repo_hits += 1

        if not scanned:
            c.missing(
                "c24.nothing-scanned",
                f"{repo} tracks files, but none of them is text, so nothing in it "
                f"was read.",
            )
            continue
        if not repo_hits:
            clean.append((repo, scanned))

    # The four drift calls below carry their finding IDs as literals, as every
    # gate does: selftest.py and features-are-bound.sh read the IDs out of these
    # calls, and an ID built at run time would be a finding nothing can see.
    if hits["marker"]:
        c.drift(
            "c24.marker",
            f"{len(hits['marker'])} line(s) carry {SHAPES['marker'][0]}.",
            _detail(estate, hits["marker"], SHAPES["marker"][1]),
        )
    if hits["guillemet"]:
        c.drift(
            "c24.guillemet",
            f"{len(hits['guillemet'])} line(s) carry {SHAPES['guillemet'][0]}.",
            _detail(estate, hits["guillemet"], SHAPES["guillemet"][1]),
        )
    if hits["cyrillic-prose"]:
        c.drift(
            "c24.cyrillic-prose",
            f"{len(hits['cyrillic-prose'])} line(s) carry {SHAPES['cyrillic-prose'][0]}.",
            _detail(estate, hits["cyrillic-prose"], SHAPES["cyrillic-prose"][1]),
        )
    if hits["owner-named"]:
        c.drift(
            "c24.owner-named",
            f"{len(hits['owner-named'])} line(s) carry {SHAPES['owner-named'][0]}.",
            _detail(estate, hits["owner-named"], SHAPES["owner-named"][1]),
        )

    for repo, scanned in clean:
        c.ok(
            f"c24.clean:{repo}",
            f"{repo}: {scanned} tracked text file(s) read, none quotes or names the owner.",
        )

    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    sys.exit(main())
