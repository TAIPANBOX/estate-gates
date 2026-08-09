#!/usr/bin/env python3
"""C2: every vendored copy of a canonical schema is byte-identical to the
original in agent-passport.

WHY

agent-conform advertises full schema validation. Its vendored copy of the
passport schema fell three weeks behind the canonical one, so the two fields
that exist for AI Act code inventory, `filesystem` and `models`, were simply
not part of what it validated. Nothing was broken in either repository. The
tool passed, the schema passed, and the claim between them was false.

A vendored schema is a copy somebody made on a day, and the estate has five of
them across three languages. Copies are fine. Copies nothing watches are the
defect.

BYTE-IDENTICAL, NOT SEMANTICALLY EQUAL

Deliberately strict. Two JSON documents that differ only in whitespace or key
order are the same schema to a validator and a different one to a reader, and
the whole point of a vendored copy is that a HUMAN can open it and see what
the canonical says. Reformatting a vendored copy is a change worth a line in a
diff. `include_str!` and `embed` copies are compiled in as bytes anyway.

The copies are declared below with the canonical each belongs to. A copy that
disappears is a red, not a skip: a vendored schema that vanished is either a
file somebody deleted by mistake or a check that stopped knowing where to look,
and both need a person.

That red fired once and was the second case. engram was recorded here as
vendoring the v0.1 schema at `tests/fixtures/agent-event.schema.json`, and on
2026-08-09 the file was not there. It had not been lost: engram was the last
plane still emitting v0.1, migrated to v0.2 on 2026-08-06 (its PR #31), and
deleted the v0.1 fixture as part of that, which `engram/events.py` says in its
own module docstring. So the record moved to the v0.2 list rather than being
deleted, because engram still vendors a copy and dropping the entry would have
left it watched by nothing. Removing a copy from this file is only ever correct
when the repository stopped vendoring one at all, and that has not happened yet.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

CANONICAL_REPO = "agent-passport"

# canonical relative path -> list of (repo, path, one line on what the copy is for)
COPIES: dict[str, list[tuple[str, str, str]]] = {
    "schemas/agent-event.schema.json": [
        (
            "agent-stack-go",
            "cmd/agent-conform/schemas/agent-event.schema.json",
            "what `agent-conform -schema` validates v0.1 events against",
        ),
        (
            "genaryx",
            "crates/core/src/schemas/agent-event.v0.1.schema.json",
            "compiled into genaryx-core with include_str!, crates/core/src/conform.rs",
        ),
    ],
    "schemas/agent-event.v0.2.schema.json": [
        (
            "agent-stack-go",
            "cmd/agent-conform/schemas/agent-event.v0.2.schema.json",
            "what `agent-conform -schema` validates v0.2 events against",
        ),
        (
            "agent-stack-go",
            "event/testdata/agent-event.v0.2.schema.json",
            "the event package's own conformance fixture",
        ),
        (
            "genaryx",
            "crates/core/src/schemas/agent-event.v0.2.schema.json",
            "compiled into genaryx-core with include_str!, crates/core/src/conform.rs",
        ),
        (
            "verdryx",
            "tests/fixtures/agent-event.v0.2.schema.json",
            "the fixture verdryx's own test suite validates its emitted events against",
        ),
        (
            "engram",
            "tests/fixtures/agent-event.v0.2.schema.json",
            "the fixture engram's own test suite validates its emitted events against",
        ),
    ],
    "schemas/agent-passport.schema.json": [
        (
            "agent-stack-go",
            "cmd/agent-conform/schemas/agent-passport.schema.json",
            "what `agent-conform -passport` validates a passport against",
        ),
    ],
}


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C2", "vendored schemas are byte-identical to agent-passport", estate)

    for canonical_path, copies in sorted(COPIES.items()):
        try:
            canonical = estate.read_bytes(CANONICAL_REPO, canonical_path)
        except E.Unavailable as u:
            c.unavailable(
                "c2.canonical-unavailable",
                f"{CANONICAL_REPO} could not be read in this run ({u.reason}), so "
                f"{len(copies)} vendored copies of {canonical_path} were compared "
                f"against nothing.",
            )
            continue
        except E.Missing as m:
            c.missing(
                "c2.canonical-gone",
                f"the canonical {CANONICAL_REPO}/{canonical_path} is not there "
                f"({m}). {len(copies)} vendored copies claim to mirror it, and "
                f"none of them can be checked while the original is missing.",
            )
            continue

        for repo, relpath, purpose in copies:
            try:
                copy = estate.read_bytes(repo, relpath)
            except E.Unavailable as u:
                c.unavailable(
                    f"c2.copy-unavailable:{repo}",
                    f"{repo} could not be read in this run ({u.reason}), so its "
                    f"copy of {canonical_path} was not compared.",
                )
                continue
            except E.Missing:
                c.missing(
                    "c2.copy-gone",
                    f"{repo} is recorded here as vendoring {canonical_path} at "
                    f"{relpath}, and that file is not there.",
                    [
                        f"  canonical: {estate.where(CANONICAL_REPO, canonical_path)}",
                        f"  copy:      {estate.where(repo, relpath)} (absent)",
                        f"  it is {purpose}.",
                        "Either the copy moved and this check needs the new path, or",
                        "something that used to be validated no longer is.",
                    ],
                )
                continue

            if copy == canonical:
                c.ok(
                    "c2.identical",
                    f"{repo}:{relpath} is byte-identical to "
                    f"{CANONICAL_REPO}/{canonical_path}.",
                )
                continue

            detail = [
                f"  canonical: {estate.where(CANONICAL_REPO, canonical_path)}"
                f" ({len(canonical)} bytes)",
                f"  copy:      {estate.where(repo, relpath)} ({len(copy)} bytes)",
                f"  the copy is {purpose}.",
                "",
            ]
            detail += E.unified_first_difference(
                canonical.decode("utf-8", "replace"),
                copy.decode("utf-8", "replace"),
                f"{CANONICAL_REPO}/{canonical_path}",
                f"{repo}/{relpath}",
            ) or ["(the files differ in bytes but not in any line, check line endings)"]
            c.drift(
                "c2.bytes-differ",
                f"{repo}:{relpath} is not byte-identical to the canonical "
                f"{CANONICAL_REPO}/{canonical_path}.",
                detail,
            )

    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
