#!/usr/bin/env python3
"""C12: every envelope member the SPEC defines has a decision at the record plane.

WHY THIS IS NOT C8 ONE LEVEL DOWN

C8 asks the question about event TYPES: is there an answer for each of them.
This asks it about the envelope's MEMBERS, and the failure mode is different
and worse, because a member has no refusal path at all.

trailryx's mapper partitions every member of a line into exactly two planes.
`CONSUMED` goes to typed metadata, which is kept; everything else goes to the
payload plane, which is what a per-event key ERASES. Its own rule says so:
"a member this version has never seen is by definition something this version
cannot classify". So an unknown member is not refused and not counted. It is
silently filed in the erasable half, and the store reports nothing.

WHAT IT FOUND WHEN IT WAS WRITTEN

`delegation_proof`, agent-passport SPEC 5.2, in the v0.2 and v0.3 envelopes and
emitted by tokenfuse since 2026-08-26. It records that the `on_behalf_of` chain
was PROVED by an RFC 8693 token. `CONSUMED` does not name it and trailryx does
not mention it anywhere.

That puts the chain in the kept plane and its proof in the erasable one. SPEC
5.2 reads a chain with no proof beside it as NOT proven, so a routine payload
erasure turns a proven chain into an unproven one, silently, in the store whose
whole claim is that it holds what happened in a form nobody can quietly alter.
5.2 spends a MUST on exactly that downgrade.

The same argument was made INSIDE tokenfuse on the same day, against putting the
proof in `data`, and it was accepted there. Nobody checked whether the store one
repository over made the identical mistake for the identical reason. That is the
gap between two repos, which is what this suite exists for.

THE CHECK IS ABOUT COVERAGE, NEVER ABOUT WHICH ANSWER

Payload is a legitimate answer for most members, and for `data` it is the only
correct one. The rule is only that the answer EXISTS: a spec member is either
consumed into typed metadata, or named in the mapper's own prose as one that
belongs in the payload plane and why. A reader can then ask "what does the store
do with this member" and get an answer for every one of them.

HOW THE SUBJECTS ARE FOUND

From the SCHEMA files, never from a list in this script. Every version of the
envelope schema is read and its `properties` unioned, so a member added in a
newer version is a subject the day it lands rather than the day somebody
remembers to add it here. A run that finds no schema, or no members, says it
measured nothing and fails; that is not a pass.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

SCHEMA_REPO = "agent-stack-go"
SCHEMA_DIR = "cmd/agent-conform/schemas"
RECORD_REPO = "trailryx"
MAPPER_PATH = "crates/trailryx-agentevent/src/lib.rs"

#: The mapper's own list of what it reads into typed fields.
CONSUMED_ANCHOR = "const CONSUMED: &[&str] = &["

#: The module doc's plane-boundary passage, which is where a member that
#: belongs in the payload plane is named and argued. Anchored on its heading.
PAYLOAD_ANCHOR = "# Rule one: the plane boundary"
PAYLOAD_END = "# Rule two"


def envelope_members(estate: E.Estate) -> dict[str, set[str]]:
    """Every property name in every version of the event envelope schema."""
    out: dict[str, set[str]] = {}
    for path in estate.list_files(SCHEMA_REPO, ".json"):
        if not path.startswith(SCHEMA_DIR) or "agent-event" not in path:
            continue
        doc = json.loads(estate.read_text(SCHEMA_REPO, path))
        props = doc.get("properties")
        if not isinstance(props, dict):
            continue
        for name in props:
            out.setdefault(name, set()).add(pathlib.PurePath(path).name)
    return out


def consumed(src: str) -> set[str]:
    i = src.find(CONSUMED_ANCHOR)
    if i < 0:
        raise E.Missing(
            f"{MAPPER_PATH} has no `{CONSUMED_ANCHOR}`, so this gate cannot tell "
            "which members reach typed metadata"
        )
    j = src.index("];", i)
    return set(re.findall(r'"([a-z_]+)"', src[i:j]))


def payload_prose(src: str) -> str:
    i = src.find(PAYLOAD_ANCHOR)
    if i < 0:
        raise E.Missing(
            f"{MAPPER_PATH} no longer carries the `{PAYLOAD_ANCHOR}` passage, "
            "which is where a member that belongs in the payload plane is argued"
        )
    j = src.find(PAYLOAD_END, i)
    return src[i : j if j > 0 else i + 4000]


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C12", "every envelope member has a plane at the record", estate)

    try:
        members = envelope_members(estate)
    except E.Unavailable as u:
        c.unavailable("c12.schemas-unavailable", str(u))
        return c
    if not members:
        c.missing(
            "c12.schemas",
            f"no envelope schema with `properties` was found in "
            f"{SCHEMA_REPO}/{SCHEMA_DIR}, so this gate measured nothing",
        )
        return c

    try:
        src = estate.read_text(RECORD_REPO, MAPPER_PATH)
    except E.Unavailable as u:
        c.unavailable("c12.record-unavailable", str(u))
        return c
    except E.Missing as m:
        c.missing("c12.mapper-unreadable", str(m))
        return c
    try:
        kept = consumed(src)
        prose = payload_prose(src)
    except E.Missing as m:
        c.missing("c12.mapper-unreadable", str(m))
        return c

    for name in sorted(members):
        where = ", ".join(sorted(members[name]))
        if name in kept:
            c.ok(f"c12.member:{name}", f"typed metadata ({where})")
        elif re.search(rf"`{re.escape(name)}`", prose):
            c.ok(f"c12.member:{name}", f"payload plane, argued in the mapper doc ({where})")
        else:
            c.drift(
                f"c12.member:{name}",
                f"`{name}` is an envelope member ({where}) and the record plane "
                f"has no decision about it",
                [
                    f"{RECORD_REPO}/{MAPPER_PATH} neither consumes it into typed "
                    "metadata nor names it in the plane-boundary passage.",
                    "An unnamed member is not refused and not counted: it goes to "
                    "the payload plane, which a per-event key ERASES, and the store "
                    "says nothing about having done so.",
                    "Consume it, or name it in that passage with the reason it "
                    "belongs in the erasable half.",
                ],
            )
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
