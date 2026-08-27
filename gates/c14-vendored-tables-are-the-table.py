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

WHAT IT DOES NOT CATCH

Whether an implementation actually RUNS its copy. A vendored file nobody reads
passes this happily. That is a real gap and it is named rather than papered
over: what stops it is the copy sitting in a test fixture directory, which is
convention rather than enforcement.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

MARKER = "$source"


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
