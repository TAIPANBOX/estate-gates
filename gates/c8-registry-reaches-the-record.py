#!/usr/bin/env python3
"""C8: every registered event type is a DECISION at the record plane, not a hole.

WHY

C4 holds SPEC 6.2 against the producers: a registered type somebody emits, and
an emitted type somebody registered. It says nothing about what happens to the
event after it is written, and one consumer's silence there costs more than
the others'.

trailryx is the record plane. Its ingest door maps an envelope type onto a
record type, and a type it does not know is refused as `UnknownType` and
counted. That refusal is the right behaviour and it is not the problem: the
problem is that "we decided this does not belong in the record" and "nobody
got to it" produce exactly the same refusal, the same counter, and the same
silence, and only one of them is a decision somebody made.

trailryx already writes the decision down. Its `trailryx-agentevent` module
doc carries a list of the types it refuses BY NAME, with the reason stated
once for the group: each is a finding or an observation about infrastructure
rather than a decision an agent took. What nothing checked is whether that
list has kept up with the registry.

WHAT IT FOUND WHEN IT WAS WRITTEN

`policy_updated`, wardryx's admin type, registered in 6.2 at severity `high`
and emitted whenever an operator changes a policy through the policy-as-code
API. trailryx neither mapped it nor named it, so the record plane silently
dropped the event that says somebody changed the rules. For a store whose
claim is that it holds what happened in a form nobody can quietly alter, that
is a conspicuous thing to be missing, and it went missing by omission rather
than by anyone deciding it should.

THE CHECK IS ABOUT COVERAGE, NEVER ABOUT WHICH ANSWER

It does not require a type to be mapped. Refusing is a legitimate and common
answer, and trailryx's record vocabulary is deliberately small: eleven types
that are things an agent did, plus two admitted since. Requiring a mapping per
registered type would push the record plane toward a vocabulary as wide as the
bus, which is the opposite of what it is for.

So the rule is only this: every registered type appears on ONE of the two
lists. A reader of trailryx can then ask "what does the record plane do with
this event" and get an answer for every type, rather than an answer for most
of them and silence for the rest.

WHAT IT DOES NOT CATCH

Whether a mapping is CORRECT. `slo_burn` mapped onto a budget check would pass
this happily, and would be wrong in the way trailryx's own doc calls worse than
a missing record, because it is believed. Nothing mechanical can ask that
question; the check asks whether an answer exists, not whether it is a good
one.

It also reads the refused list out of a doc comment, which is prose. A type
mentioned in that passage for some other reason would read as refused. The
extractor narrows to the one paragraph that names the list rather than
scanning the module doc, and it fails loudly if that paragraph stops matching,
which is the shape this suite uses everywhere: an anchor that stops matching
is a finding and never a skip.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

SPEC_REPO = "agent-passport"
SPEC_PATH = "SPEC.md"
RECORD_REPO = "trailryx"
MAPPER_PATH = "crates/trailryx-agentevent/src/lib.rs"

#: Where the mapping arms are. `mapping_for` is the one function that turns a
#: wire type into a record type; anchoring on the function rather than on the
#: file keeps a string that merely appears somewhere else out of the answer.
MAPPER_FN = "fn mapping_for"

#: The doc-comment passage that lists what is refused on purpose. Anchored on
#: its own opening words, which trailryx wrote as a sentence rather than as a
#: heading, so this is the strongest name available.
REFUSED_ANCHOR = "Refused today"
REFUSED_END = "# The one that got a type of its own"


def mapped_types(text: str) -> set[str]:
    """The wire types `mapping_for` has an arm for.

    Read from the function body between its opening and its `_ => None`
    fallback, so a string constant elsewhere in the file cannot be mistaken
    for an arm.
    """
    start = text.find(MAPPER_FN)
    if start < 0:
        raise E.Missing(
            f"{MAPPER_PATH} has no `{MAPPER_FN}`, which is how this check knows "
            f"which types the record plane maps. Either the function was renamed "
            f"or the mapper moved, and the two need different fixes"
        )
    end = text.find("_ => None", start)
    if end < 0:
        raise E.Missing(
            f"{MAPPER_PATH}: `{MAPPER_FN}` has no `_ => None` fallback arm, which "
            f"is where this check stops reading. Without it the extractor would "
            f"run past the function and report types it never maps"
        )
    body = text[start:end]
    found = set(re.findall(r'"([a-z0-9_]+)"', body))
    if not found:
        raise E.Missing(
            f"{MAPPER_PATH}: `{MAPPER_FN}` matched no quoted wire types between "
            f"the function and its fallback arm. The mapper's shape changed and "
            f"this check is comparing against an empty set"
        )
    return found


def refused_types(text: str) -> set[str]:
    """The wire types the module doc names as refused on purpose."""
    start = text.find(REFUSED_ANCHOR)
    if start < 0:
        raise E.Missing(
            f"{MAPPER_PATH}: the module doc no longer contains `{REFUSED_ANCHOR}`, "
            f"which is the passage naming what the record plane refuses "
            f"deliberately. Without it this check cannot tell a decision from an "
            f"omission, which is the only thing it does"
        )
    end = text.find(REFUSED_END, start)
    section = text[start : end if end > start else start + 4000]
    found = set(re.findall(r"`([a-z0-9_]+)`", section))
    if not found:
        raise E.Missing(
            f"{MAPPER_PATH}: the `{REFUSED_ANCHOR}` passage names no types. Either "
            f"the list emptied or its formatting changed, and a check reading an "
            f"empty refusal list would report every registered type as a hole"
        )
    return found


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C8", "every registered type is answered by the record plane", estate)

    try:
        registry, reserved = E.parse_registry(estate.read_text(SPEC_REPO, SPEC_PATH))
    except E.Unavailable as u:
        c.unavailable(
            "c8.spec-unavailable",
            f"{SPEC_REPO} could not be read in this run ({u.reason}), so there was "
            f"no registry to compare the record plane against.",
        )
        return c
    except E.Missing as m:
        c.missing("c8.registry-unparsed", str(m))
        return c

    try:
        mapper = estate.read_text(RECORD_REPO, MAPPER_PATH)
    except E.Unavailable as u:
        c.unavailable(
            "c8.record-unavailable",
            f"{RECORD_REPO} could not be read in this run ({u.reason}), so what the "
            f"record plane does with each registered type is unmeasured here.",
        )
        return c
    except E.Missing as m:
        c.missing(
            "c8.mapper-file-gone",
            f"{RECORD_REPO} is recorded here as mapping the shared envelope from "
            f"{MAPPER_PATH}, and that file is not there: {m}. Either the mapper "
            f"moved or the record plane stopped reading the bus, and those need "
            f"different fixes.",
        )
        return c

    try:
        mapped = mapped_types(mapper)
        refused = refused_types(mapper)
    except E.Missing as m:
        c.missing("c8.mapper-unreadable", f"{RECORD_REPO}: {m}")
        return c

    # Reserved rows claim nothing is emitted, so there is nothing for the
    # record plane to have an answer about. C4 owns that claim.
    all_types: set[str] = set()
    for source, types in registry.items():
        if source in reserved:
            continue
        all_types |= types

    c.note(
        f"SPEC 6.2 registers {len(all_types)} emitted type(s); "
        f"{RECORD_REPO} maps {len(mapped)} and names {len(refused)} as refused "
        f"on purpose."
    )

    unanswered = sorted(all_types - mapped - refused)
    if unanswered:
        c.drift(
            "c8.type-unanswered",
            f"{len(unanswered)} registered type(s) the record plane neither maps "
            f"nor names as refused: {', '.join(unanswered)}.",
            [
                f"  registry: {estate.where(SPEC_REPO, SPEC_PATH)} section 6.2",
                f"  record:   {estate.where(RECORD_REPO, MAPPER_PATH)}",
                "Each is refused as UnknownType at the ingest door and counted,",
                "which is indistinguishable from a refusal somebody decided on.",
                "Map it, or name it in the refused list with the reason.",
            ],
        )
    else:
        c.ok(
            "c8.every-type-answered",
            f"every one of the {len(all_types)} emitted types 6.2 registers is "
            f"either mapped by {RECORD_REPO} or named in its refused list.",
        )

    # The other direction: a type the record plane has an opinion about that
    # nobody registers. Weaker than the first, because trailryx legitimately
    # keeps names for types that were registered once, so this reports rather
    # than fails. It is here because the alternative is that the refusal list
    # silently accumulates names for events that no longer exist, and a reader
    # cannot tell those from current ones.
    stale = sorted((mapped | refused) - all_types)
    if stale:
        c.note(
            f"{RECORD_REPO} has an opinion about {len(stale)} type(s) 6.2 does not "
            f"register: {', '.join(stale)}. Not a failure: a name kept after a "
            f"producer stopped emitting is how a reader learns the type existed."
        )

    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
