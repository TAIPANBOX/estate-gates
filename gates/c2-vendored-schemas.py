#!/usr/bin/env python3
"""C2: every vendored copy of a canonical schema is byte-identical to the
original in agent-passport.

WHY

agent-conform advertises full schema validation. Its vendored copy of the
passport schema fell three weeks behind the canonical one, so the two fields
that exist for AI Act code inventory, `filesystem` and `models`, were simply
not part of what it validated. Nothing was broken in either repository. The
tool passed, the schema passed, and the claim between them was false.

A vendored schema is a copy somebody made on a day, and the estate has several
across three languages. Copies are fine. Copies nothing watches are the defect.

DECLARED, AND ALSO DISCOVERED

The list below is written by hand, because each entry carries a sentence saying
what the copy is FOR, and that sentence is most of what makes a failure here
readable. A hand-written list is also, itself, a copy of the truth that nothing
watches, and on 2026-08-26 it was two entries short: agent-stack-go vendors the
v0.3 envelope and a second copy of the passport schema, and neither was named
here, so both drifted in silence while the six copies that WERE named went red.

So the list is no longer the only thing. Every repository is searched for files
carrying a canonical schema's `$id`, and a file found that way and not declared
below is a finding of its own. `$id` rather than the filename, because it is
what the copy CLAIMS to be: it survives a rename, it tells genaryx's
`agent-event.v0.1.schema.json` apart from nothing else, and it is present in a
copy embedded in Rust or Go source as much as in a `.json` file.

What that does not catch is a copy whose `$id` was edited or removed. That copy
has stopped claiming to be the schema, which is a different defect from drift
and not one this check can honestly say it covers.

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
import json
import re
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

CANONICAL_REPO = "agent-passport"

# Every canonical schema's `$id` starts with this. It is the cheap first pass:
# one `git grep` per repository narrows thousands of tracked files to a handful
# of candidates, which are then read and checked properly.
ID_PREFIX = "https://taipanbox.dev/agent-passport/"

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
    "schemas/agent-event.v0.3.schema.json": [
        (
            "agent-stack-go",
            "cmd/agent-conform/schemas/agent-event.v0.3.schema.json",
            "what `agent-conform -schema` validates v0.3 events against",
        ),
    ],
    "schemas/agent-passport.schema.json": [
        (
            "agent-stack-go",
            "cmd/agent-conform/schemas/agent-passport.schema.json",
            "what `agent-conform -passport` validates a passport against",
        ),
        (
            "agent-stack-go",
            "passport/testdata/schema/agent-passport.schema.json",
            "the passport package's own conformance fixture",
        ),
    ],
}


def _id_of(raw: bytes) -> str | None:
    """The `$id` a file CLAIMS, or None if it claims none.

    Parsed as JSON where that works, because that is what the file is. Where it
    does not parse, the same key is looked for as text: a schema embedded in a
    source file, or one a mutation left syntactically broken, still claims an
    identity and is still a copy.
    """
    text = raw.decode("utf-8", "replace")
    try:
        doc = json.loads(text)
        if isinstance(doc, dict) and isinstance(doc.get("$id"), str):
            return doc["$id"]
    except (ValueError, RecursionError):
        pass
    m = re.search(r'"\$id"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _declared_paths() -> dict[str, set[str]]:
    """repo -> the paths this file already says are copies."""
    out: dict[str, set[str]] = {}
    for copies in COPIES.values():
        for repo, relpath, _ in copies:
            out.setdefault(repo, set()).add(relpath)
    return out


def discover(estate: E.Estate, c: E.Check) -> None:
    """Find copies nobody declared.

    The gate above proves that every copy WE KNOW OF matches. This proves there
    is no copy we do not know of, which is the failure the declared list cannot
    catch about itself.
    """
    # The canonical set is DISCOVERED too, and this is not a detail. The first
    # version of this pass read the `$id` of each schema named in COPIES, which
    # meant a canonical schema absent from COPIES had no id registered and every
    # copy of it stayed invisible. That is precisely the v0.3 case it was
    # written to catch, so it would have shipped blind to its own example.
    try:
        canonical_files = [
            f
            for f in estate.list_files(CANONICAL_REPO, ".json")
            if f.startswith("schemas/")
        ]
    except (E.Unavailable, E.Missing) as exc:
        c.unavailable(
            "c2.canonical-unlistable",
            f"the canonical repository {CANONICAL_REPO} could not be listed "
            f"({exc}), so no repository was searched for undeclared copies.",
        )
        return

    canonical_ids: dict[str, str] = {}
    for canonical_path in sorted(canonical_files):
        try:
            raw = estate.read_bytes(CANONICAL_REPO, canonical_path)
        except (E.Unavailable, E.Missing):
            continue
        ident = _id_of(raw)
        if ident is None:
            c.drift(
                "c2.canonical-has-no-id",
                f"the canonical {CANONICAL_REPO}/{canonical_path} carries no `$id`, "
                f"so no copy of it anywhere in the estate can be discovered by one.",
                [
                    f"  canonical: {estate.where(CANONICAL_REPO, canonical_path)}",
                    "Copies of this schema are still compared if they are declared",
                    "above. What is lost is the ability to notice an UNDECLARED one,",
                    "which is how two copies drifted unwatched until 2026-08-26.",
                ],
            )
            continue
        canonical_ids[ident] = canonical_path

    if not canonical_ids:
        c.unavailable(
            "c2.no-canonical-ids",
            "no canonical schema could be read with an `$id`, so no repository "
            "was searched for undeclared copies.",
        )
        return

    declared = _declared_paths()
    canonical_paths = set(canonical_files)
    searched = 0

    for repo in sorted(estate.repos):
        try:
            hits = estate.grep_files(repo, ID_PREFIX)
        except E.Unavailable as u:
            c.unavailable(
                f"c2.search-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so it was not "
                f"searched for undeclared copies of any canonical schema.",
            )
            continue
        except E.Missing as m:
            c.unavailable(
                f"c2.search-failed:{repo}",
                f"{repo} could not be searched for undeclared copies ({m}).",
            )
            continue
        searched += 1

        for relpath in hits:
            if repo == CANONICAL_REPO and relpath in canonical_paths:
                continue  # the original is not a copy of itself
            if relpath in declared.get(repo, ()):
                continue  # declared, and therefore compared above
            try:
                raw = estate.read_bytes(repo, relpath)
            except (E.Unavailable, E.Missing):
                continue
            ident = _id_of(raw)
            if ident not in canonical_ids:
                continue  # mentions the URL, does not claim to BE the schema
            canonical_path = canonical_ids[ident]
            c.drift(
                "c2.copy-unwatched",
                f"{repo}:{relpath} claims to be {canonical_path} and nothing "
                f"compares it to the original.",
                [
                    f"  it declares: $id {ident}",
                    f"  canonical:   {estate.where(CANONICAL_REPO, canonical_path)}",
                    f"  copy:        {estate.where(repo, relpath)}",
                    "",
                    "A copy is not a defect. A copy nothing watches is, and this one",
                    "is absent from COPIES in this file, so it has been drifting",
                    "unnoticed for as long as it has existed.",
                    "Add it to COPIES with a sentence saying what it is FOR, then",
                    "this check will compare it byte for byte like the others.",
                ],
            )

    if searched:
        c.ok(
            "c2.searched",
            f"{searched} repositories searched for files claiming a canonical "
            f"`$id`; every one found is declared above.",
        )


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

    discover(estate, c)
    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
