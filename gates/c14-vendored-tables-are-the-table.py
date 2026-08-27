#!/usr/bin/env python3
"""C14: a vendored cross-language table is the table, byte for byte.

WHY

Some rules cannot be shared. `agent-stack-go/chain` holds what the RECORD
accepts of a delegation chain; `agent-stack-go/delegation` is a door that
`deps-layering.sh` forbids from importing it; `tokenfuse/crates/delegation` is
a third implementation in another language with no seam to either. The rules
exist three times by construction.

Three of them were found disagreeing on 2026-08-27, in one afternoon. Prose did
not hold them, and a gate reading source text could not: a regex over two
languages says a rule is MENTIONED, never that it ANSWERS. The answer was a
TABLE each implementation runs, which a comment cannot satisfy.

WHAT THIS GATE IS FOR

A table only holds while every copy of it is the same table. Let one drift and
each implementation passes its own copy, and the estate is back where it
started with a green check on top.

HOW THE SUBJECTS ARE FOUND

By `$source`, which every canonical table carries and which names its own path.
A copy is any file carrying the same `$source` at a different path, so a new
language vendoring the table is checked from the day it lands rather than the
day somebody remembers this file. C6 does the same job for the hash vectors
through a hand-written COPIES list; this is that check with the list taken out,
which is the defect shape this estate found nine times in two days.

A COPY NOBODY RUNS IS A COPY THAT PROVES NOTHING

Byte-identical copies of a table nobody reads are four files that agree about
nothing. So every copy must also be REFERENCED from a file that carries a test
marker in its own language: `#[test]`, `func Test`, `def test_`.

That is evidence a suite reaches the file, and it is deliberately not a claim
that the suite asserts on every vector. Nothing a read-only gate can do reaches
that far: it would have to run another repository's tests, and this suite reads
`git show` and builds nothing. The distance between "a test file opens it" and
"a test asserts every case in it" is real, is left, and is stated here rather
than implied away.

What it does close is the shape that actually happens: a table vendored during
a migration, wired to nothing, kept byte-perfect by this very gate, and read by
a reviewer as proof of agreement it never had.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

MARKER = "$source"

#: What a file that RUNS something looks like, per language. Deliberately the
#: test-declaration form and not the word "test": a path called `tests/` proves
#: where a file sits, and a declaration proves a suite enters it.
TEST_MARKERS = ("#[test]", "func Test", "def test_", "@Test", "it(", "describe(")

#: Suffixes worth searching for a reference. A copy referenced only from a
#: README is not run by anything.
SOURCE_SUFFIXES = (".rs", ".go", ".py", ".ts", ".js", ".java", ".rb")


def tables(
    estate: E.Estate,
) -> tuple[dict[str, list[tuple[str, str, str]]], dict[str, str]]:
    """Every JSON file carrying a `$source`, grouped by the path it names.

    Also returns the repositories that could not be read. A repo skipped in
    silence is the failure this suite exists to deny one level down: it would
    let a copy drift inside a repository nobody could open and report clean
    about the ones that answered.
    """
    found: dict[str, list[tuple[str, str, str]]] = {}
    unread: dict[str, str] = {}
    for repo in estate.repos:
        try:
            hits = estate.grep_files(repo, MARKER)
        except E.Unavailable as u:
            unread[repo] = str(u)
            continue
        except E.Missing:
            continue
        for relpath in hits:
            if not relpath.endswith(".json"):
                continue
            try:
                text = estate.read_text(repo, relpath)
                doc = json.loads(text)
            except (E.Unavailable, E.Missing, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            source = doc.get(MARKER)
            if isinstance(source, str) and source:
                found.setdefault(source, []).append((repo, relpath, text))
    return found, unread


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C14", "a vendored cross-language table is the table", estate)

    found, unread = tables(estate)
    for repo, why in sorted(unread.items()):
        c.unavailable(f"c14.unreadable:{repo}", why)
    if not found and not unread:
        c.missing(
            "c14.no-tables",
            f"no JSON file in the estate carries a `{MARKER}`, so this gate "
            "measured nothing. Either the convention moved or this script's "
            "discovery broke; both need a person, and neither is a pass.",
        )
        return c

    for source, copies in sorted(found.items()):
        canonical = [(r, p, t) for r, p, t in copies if f"{r}/{p}" == source]
        if not canonical:
            c.drift(
                f"c14.canonical-missing:{source}",
                f"{len(copies)} file(s) name `{source}` as their source and "
                "nothing is AT that path",
                [f"{r}/{p}" for r, p, _ in copies]
                + [
                    "A copy whose canonical is gone is a copy nothing can be "
                    "compared against, and every implementation then passes "
                    "its own reading of a table that no longer exists.",
                ],
            )
            continue

        _, _, want = canonical[0]
        others = [(r, p, t) for r, p, t in copies if f"{r}/{p}" != source]
        if not others:
            c.ok(f"c14.copies:{source}", "canonical only, no vendored copy yet")
            continue

        # Every copy, canonical included, must be reached by a suite. A
        # byte-perfect copy nobody runs is a file that agrees about nothing,
        # and this gate keeping it byte-perfect is what makes it look otherwise.
        for repo, relpath, _ in copies:
            name = pathlib.PurePath(relpath).name
            exercised = False
            try:
                refs = estate.grep_files(repo, name)
            except (E.Unavailable, E.Missing):
                refs = []
            for ref in refs:
                if ref == relpath or not ref.endswith(SOURCE_SUFFIXES):
                    continue
                try:
                    body = estate.read_text(repo, ref)
                except (E.Unavailable, E.Missing):
                    continue
                # The name, and not a name that merely STARTS with it.
                # `chain-verdict-vectors.json.disabled` contains the file name
                # as a substring, so a grep alone reads a disabled reference as
                # a live one. The harness caught exactly that: the mutation
                # that renamed the reference stayed silent.
                if not re.search(
                    re.escape(name) + r"(?![A-Za-z0-9._-])", body
                ):
                    continue
                if any(m in body for m in TEST_MARKERS):
                    exercised = True
                    break
            if exercised:
                c.ok(f"c14.exercised:{repo}", f"{relpath} is read by a suite")
            else:
                c.drift(
                    f"c14.copy-unexercised:{repo}",
                    f"{repo}/{relpath} is a table no suite in that repository reads",
                    [
                        "Byte-identical copies of a table nobody runs are files "
                        "that agree about nothing, and this gate keeping them "
                        "byte-perfect is what makes that look like agreement.",
                        "Some file with a test declaration in it has to name "
                        f"`{name}`.",
                    ],
                )

        drifted = [(r, p) for r, p, t in others if t != want]
        if drifted:
            c.drift(
                f"c14.copy-drifted:{source}",
                f"{len(drifted)} of {len(others)} vendored copy/copies of "
                f"`{source}` differ from it",
                [f"{r}/{p}" for r, p in drifted]
                + [
                    "A table only holds while every copy is the same table. "
                    "Let one drift and each implementation passes its own copy "
                    "and the estate is back where it started, with a green "
                    "check on top.",
                ],
            )
        else:
            c.ok(
                f"c14.copies:{source}",
                f"{len(others)} vendored copy/copies, byte for byte",
            )
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
