#!/usr/bin/env python3
"""C13: the delegation depth cap, from every side, reduced to one number.

WHY

agent-passport SPEC 5.1 reads "Maximum chain depth is 32 entries", and SPEC
section 5 calls the members of `on_behalf_of` entries: the root, usually a
human, is the first of them. So the bound belongs to the assembled chain.

The producers build that chain out of an RFC 8693 token, where the subject is
deliberately NOT an actor, so SPEC 5.3's mapping is `[sub] + reverse(act)`. Two
quantities, one sentence, and every side of the estate was free to decide which
one the sentence meant.

Measured 2026-08-27 with agent-conform against a real emitted line: tokenfuse's
`MAX_DEPTH` and agent-stack-go's `delegation.MaxDepth` both bounded the ACTOR
list at 32 and then prepended the subject, while the v0.2 and v0.3 envelope
schemas, `chain.Validate` and `agent-conform -chain` all bound the CHAIN at 32.
A token with 32 actors verified at the door and every record it produced was
refused:

    maxItems: got 33, want 32
    chain: exceeds max depth: 33 entries, max 32

Every number in the estate read 32. Every repository was internally consistent
and every suite was green. The disagreement was not in a value, it was in the
UNIT, and no repository could see it, because none of them may read another.

WHAT IS COMPARED

  the SPEC      section 5.1's sentence, parsed for the number AND for the unit
                word. A sentence that stops saying "entries" is a finding here
                and not a silent re-reading, because the unit is the whole of
                what went wrong.
  the schemas   every JSON Schema in the estate that DECLARES `on_behalf_of`,
                found by searching each repository for the member rather than
                by naming files, so a vendored copy is a subject the day it is
                committed. Each must bound it, and bound it at the SPEC's
                number. A schema that declares the member and no `maxItems` is
                a validating consumer that accepts what the SPEC forbids.
  the code      every cap constant declared under a path that names the chain
                or the delegation, classified by its name into one of the two
                units. An entries cap must equal the SPEC's number; an actors
                cap must equal it minus one AND be written as a derivation of
                the entries cap rather than as a second literal that happens to
                agree today.

AND THE ONE THAT WOULD HAVE FIRED

A file that maps an RFC 8693 `act` claim into the chain bounds two quantities
and must therefore state two numbers. One number in that file is a bound
applied to whichever quantity its author had in mind, and nothing downstream
can ask which. That is exactly how the estate spent a day emitting records
nothing would accept, and it is the finding to read first.

ANCHORS, NOT COMPILERS

The subjects are discovered: every repository in `estate.json`, every tracked
file, no list of paths anywhere. What is written down is the SHAPE of a cap
constant's name and the shape of an `Act` declaration, and every anchor that
matches nothing at all is a red naming what it could not find.

WHERE IT SAYS NOTHING, and both limits are the same anchor seen from two sides

**The path filter is crude on purpose.** The estate holds four other constants
whose names look like this one (`MAX_CHAIN_DEPTH` on tokenfuse's raft ledger,
`MAX_DEPTH` on its parent-run walk, `MAX_DEPTH` in two trailryx parsers), none
of which is this rule, and every one of them lives outside a `chain/` or
`delegation/` path. A gate that fired on a raft ledger would be deleted by
whoever was unblocking CI, so the filter errs towards seeing less.

**A cap named for neither unit is not seen at all.** `_CAP_NAME` admits a name
only if it carries one of four words, so a bound called `MaxChain` or `Ceiling`
is invisible here. Widening the anchor to every `max*` was measured against the
real estate on 2026-08-27 and pulls in `MaxSnapshotBytes` and `maxAge` from
`agent-stack-go/delegation/revocations.go`, neither of which bounds anything
this check is about. What covers that hole where it matters is the mapping
finding, which does not depend on finding a cap at all: a file that maps `act`
into a chain and states no actor bound is red whatever its constants are
called. A record-side file with a renamed cap and no `act` would go quiet, and
that one is not covered.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

SPEC_REPO = "agent-passport"
SPEC_PATH = "SPEC.md"

#: SPEC 5.1's sentence. The unit word is captured rather than assumed.
_CAP_SENTENCE = re.compile(r"Maximum chain depth is (\d+) ([a-z]+)", re.I)

#: The unit words this check knows how to act on.
ENTRIES, ACTORS = "entries", "actors"

#: A constant whose name looks like a bound on a chain. Filtered by path
#: before it is applied; see ANCHORS above.
_CAP_NAME = re.compile(r"(?i)^max_?(chain_?)?(depth|entries|actors|hops)[a-z_]*$")

#: `pub const NAME: usize = ...;`
_RUST_CONST = re.compile(
    r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*:"
    r"\s*[^=]+=\s*([^;]+);"
)
#: `const Name = ...`, and a bare `Name = ...` inside a Go const block or a
#: Python module. Filtered by _CAP_NAME, so its looseness is bounded.
_ASSIGN = re.compile(
    r"(?m)^[ \t]*(?:const[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*([^\n/]+?)[ \t]*$"
)

#: The RFC 8693 actor claim, declared. Go `type Act struct` and Rust
#: `struct Act`.
_ACT_DECL = re.compile(r"(?m)^\s*(?:pub\s+)?(?:type\s+Act\s+struct|struct\s+Act\b)")

SOURCE_SUFFIXES = (".go", ".rs", ".py")
PATH_WORDS = ("chain", "delegation")


# --------------------------------------------------------------- the SPEC


def spec_cap(spec: str) -> tuple[int, str]:
    """SPEC 5.1's number and the unit it is counted in."""
    heading = re.search(r"(?m)^#{2,4}\s*5\.1\b", spec)
    if not heading:
        raise E.Missing(
            f"{SPEC_REPO}:{SPEC_PATH} has no `5.1` heading, which is where the "
            f"normative chain cap lives. Every other side of this comparison is "
            f"measured against that sentence, so its absence leaves this check "
            f"with nothing to compare anything to"
        )
    rest = spec[heading.end() :]
    nxt = re.search(r"(?m)^#{1,4}\s", rest)
    section = rest[: nxt.start() if nxt else len(rest)]
    # Whitespace collapsed BEFORE matching. The real sentence is wrapped across
    # two lines ("Maximum chain\ndepth is 32 entries."), and a needle that
    # cannot cross a line break reports the sentence as gone: this gate's first
    # run against the published SPEC did exactly that, which is the split-needle
    # trap the estate hit in a teeth harness the day before.
    section = re.sub(r"\s+", " ", section)

    found = _CAP_SENTENCE.findall(section)
    if not found:
        raise E.Missing(
            f"{SPEC_REPO}:{SPEC_PATH} section 5.1 no longer says 'Maximum chain "
            f"depth is N <unit>'. The sentence this whole check is anchored on "
            f"was reworded, so the estate's cap now has no stated source"
        )
    if len(found) > 1:
        raise E.Missing(
            f"{SPEC_REPO}:{SPEC_PATH} section 5.1 states the cap {len(found)} "
            f"times ({found}). Two statements of one bound is the drift this "
            f"check exists to find, inside the document that settles it"
        )
    number, unit = found[0]
    return int(number), unit.lower()


# ------------------------------------------------------------- the schemas


def declared_bounds(text: str) -> list[tuple[str, object]]:
    """Every `on_behalf_of` property in a JSON Schema, with its `maxItems`.

    A file that merely MENTIONS the member is not a subject: the estate holds
    three (chain vectors, a published constants artifact, a record schema), and
    none of them decides what a consumer accepts.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    out: list[tuple[str, object]] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict) and isinstance(props.get("on_behalf_of"), dict):
                out.append(
                    (f"{path}/properties/on_behalf_of", props["on_behalf_of"].get("maxItems"))
                )
            for k, v in node.items():
                walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}")

    walk(data, "")
    return out


# ---------------------------------------------------------------- the code


class Cap:
    """One declared bound: where it is, what it counts, and what it says."""

    def __init__(self, repo: str, path: str, name: str, raw: str):
        self.repo = repo
        self.path = path
        self.name = name
        self.raw = raw.strip()
        self.value: int | None = None
        self.derived_from: str | None = None

    @property
    def unit(self) -> str:
        """Which of SPEC 5.1's two quantities this constant counts.

        Total rather than optional, and that is a property of the anchor:
        `_CAP_NAME` admits a name only if it carries one of the four words
        below, so every discovered cap classifies. A cap whose name says
        NEITHER is not discovered at all, which is the anchor's honest limit
        and is covered from the other side by the mapping check: a file that
        maps `act` into a chain and states no actor bound is a red whatever
        its constants are called.
        """
        low = self.name.lower()
        if "actor" in low:
            return ACTORS
        return ENTRIES

    def where(self) -> str:
        return f"{self.repo}/{self.path}: {self.name}"


_LITERAL = re.compile(r"^(\d[\d_]*)$")
#: `OTHER - 1`, and the bare `OTHER`, which is the shape the 2026-08-27 defect
#: takes when somebody derives the actor bound and forgets the arithmetic.
_DERIVED = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:([+-])\s*(\d+))?$")


def caps_in(repo: str, path: str, text: str) -> list[Cap]:
    """Cap-shaped constants declared in one source file."""
    seen: dict[str, Cap] = {}
    for pattern in (_RUST_CONST, _ASSIGN):
        for name, raw in pattern.findall(text):
            if not _CAP_NAME.match(name):
                continue
            seen.setdefault(name, Cap(repo, path, name, raw))
    return list(seen.values())


def resolve(caps: list[Cap]) -> list[Cap]:
    """Give each cap a value, resolving a derivation against its own file.

    A cap this cannot evaluate keeps `value = None`, which the caller turns
    into a red. Guessing would be the one thing worse than not reading it.
    """
    by_file: dict[tuple[str, str], dict[str, Cap]] = {}
    for c in caps:
        by_file.setdefault((c.repo, c.path), {})[c.name] = c
    for c in caps:
        m = _LITERAL.match(c.raw)
        if m:
            c.value = int(m.group(1).replace("_", ""))
            continue
        m = _DERIVED.match(c.raw)
        if m:
            base = by_file[(c.repo, c.path)].get(m.group(1))
            if base is not None and _LITERAL.match(base.raw):
                literal = int(base.raw.replace("_", ""))
                delta = int(m.group(3)) if m.group(3) else 0
                c.value = literal + delta if m.group(2) == "+" else literal - delta
                c.derived_from = m.group(1)
    return caps


# ------------------------------------------------------------------- run


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C13", "the delegation depth cap counts one thing", estate)

    # -- the SPEC, which is what everything else is measured against --------
    try:
        spec = estate.read_text(SPEC_REPO, SPEC_PATH)
    except E.Unavailable as u:
        c.unavailable(
            "c13.spec-unavailable",
            f"{SPEC_REPO} could not be read in this run ({u.reason}), so nothing "
            f"was compared: the normative cap is the only thing that makes the "
            f"other numbers right or wrong.",
        )
        return c
    except E.Missing as m:
        c.missing("c13.spec-cap-gone", str(m))
        return c

    try:
        cap, unit = spec_cap(spec)
    except E.Missing as m:
        c.missing("c13.spec-cap-gone", str(m))
        return c

    if unit != ENTRIES:
        c.missing(
            "c13.spec-unit-unknown",
            f"{estate.where(SPEC_REPO, SPEC_PATH)} section 5.1 now caps the chain "
            f"at {cap} {unit!r}, and this check only knows how to compare a cap "
            f"counted in {ENTRIES!r}. The unit is the whole of what this check "
            f"holds: an estate that read one sentence two ways emitted records "
            f"nothing would accept for a day. Comparing numbers whose unit has "
            f"changed underneath is how that happens again.",
        )
        return c

    c.note(
        f"SPEC 5.1: the chain is capped at {cap} {unit}, so a chain that names a "
        f"subject has room for {cap - 1} RFC 8693 actors (SPEC 5.3)."
    )

    # -- the schemas --------------------------------------------------------
    schema_subjects = 0
    for repo in sorted(estate.repos):
        try:
            files = estate.grep_files(repo, "on_behalf_of")
        except E.Unavailable as u:
            c.unavailable(
                f"c13.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so neither "
                f"its schemas nor its cap constants were compared.",
            )
            continue
        except E.Missing as m:
            c.missing("c13.schema-search-failed", str(m))
            continue

        for relpath in files:
            if not relpath.endswith(".json"):
                continue
            try:
                text = estate.read_text(repo, relpath)
            except E.Missing:
                continue
            for where, max_items in declared_bounds(text):
                schema_subjects += 1
                if max_items is None:
                    c.drift(
                        "c13.schema-unbounded",
                        f"{repo} declares `on_behalf_of` with no `maxItems`, so "
                        f"this consumer accepts a chain the SPEC forbids.",
                        [
                            f"  spec:   {estate.where(SPEC_REPO, SPEC_PATH)} 5.1 caps it at {cap} {unit}",
                            f"  schema: {estate.where(repo, relpath)}{where}",
                            "  Depth is the half of SPEC 5.1 that JSON Schema CAN",
                            "  express, and a schema that declines to express it is a",
                            "  door that opens on nothing having been checked.",
                        ],
                    )
                elif max_items != cap:
                    c.drift(
                        "c13.schema-cap-differs",
                        f"{repo} bounds `on_behalf_of` at {max_items} and the SPEC "
                        f"caps it at {cap}.",
                        [
                            f"  spec:   {estate.where(SPEC_REPO, SPEC_PATH)} 5.1",
                            f"  schema: {estate.where(repo, relpath)}{where}",
                            "  A validating consumer refuses what a producer built, or",
                            "  accepts what the record cannot hold. Which of the two",
                            "  depends on the sign, and both are silent at the producer.",
                        ],
                    )
                else:
                    c.ok(
                        "c13.schema-agrees",
                        f"{repo}/{relpath} bounds `on_behalf_of` at {cap}.",
                    )

    if schema_subjects == 0:
        c.missing(
            "c13.no-schema-bounds",
            f"no schema anywhere in the estate declares an `on_behalf_of` "
            f"property, so the consumer half of this comparison measured nothing. "
            f"The member is what SPEC 5.1 bounds; a search that finds none of it "
            f"has stopped reading rather than found agreement.",
        )

    # -- the code -----------------------------------------------------------
    caps: list[Cap] = []
    mapping_files: list[tuple[str, str]] = []

    for repo in sorted(estate.repos):
        try:
            files = estate.list_files(repo)
        except E.Unavailable:
            continue  # already reported above
        except E.Missing as m:
            c.missing("c13.source-listing-failed", str(m))
            continue

        for relpath in files:
            low = relpath.lower()
            if not low.endswith(SOURCE_SUFFIXES):
                continue
            if not any(w in low for w in PATH_WORDS):
                continue
            try:
                text = estate.read_text(repo, relpath)
            except E.Missing:
                continue
            caps.extend(caps_in(repo, relpath, text))
            # Deliberately not conditional on having found a cap here. A file
            # that maps `act` into a chain and declares no bound this check can
            # see is the worst of the three cases, not an absent subject, and
            # tying the subject to the anchor would let a rename switch this
            # check off for that file in silence.
            if _ACT_DECL.search(text):
                mapping_files.append((repo, relpath))

    if not caps:
        c.missing(
            "c13.no-code-caps",
            f"no cap constant was found under any `chain` or `delegation` path in "
            f"the estate. The producers are the side this check exists for, and "
            f"finding none of them is an anchor that stopped matching, not an "
            f"estate that agrees.",
        )
        return c

    resolve(caps)

    for cap_const in sorted(caps, key=lambda x: (x.repo, x.path, x.name)):
        if cap_const.value is None:
            c.missing(
                "c13.cap-unparsed",
                f"{cap_const.where()} is set to `{cap_const.raw}` and this check "
                f"cannot evaluate that. A bound it cannot read is one it is not "
                f"comparing, and reporting agreement on an unread number is the "
                f"failure this repository exists to prevent.",
                [f"  {estate.where(cap_const.repo, cap_const.path)}"],
            )
            continue

        if cap_const.unit == ENTRIES:
            if cap_const.value != cap:
                c.drift(
                    "c13.entry-cap-differs",
                    f"{cap_const.where()} caps the chain at {cap_const.value} "
                    f"entries and the SPEC caps it at {cap}.",
                    [
                        f"  cap:  {estate.where(cap_const.repo, cap_const.path)}",
                        f"  spec: {estate.where(SPEC_REPO, SPEC_PATH)} 5.1",
                        "  This is what a door accepts, measured against what the",
                        "  document says it may accept.",
                    ],
                )
            else:
                c.ok(
                    "c13.entry-cap-agrees",
                    f"{cap_const.where()} = {cap} entries, as SPEC 5.1 says.",
                )
            continue

        # actors
        want = cap - 1
        if cap_const.value != want:
            c.drift(
                "c13.actor-cap-differs",
                f"{cap_const.where()} allows {cap_const.value} actors where a "
                f"chain of {cap} entries leaves room for {want}.",
                [
                    f"  cap:  {estate.where(cap_const.repo, cap_const.path)}",
                    f"  spec: {estate.where(SPEC_REPO, SPEC_PATH)} 5.1 and 5.3",
                    f"  `on_behalf_of = [sub] + reverse(act)`: the subject is the",
                    f"  chain's first ENTRY, so {cap} entries is {want} actors and one",
                    f"  root. A door that allows {cap_const.value} emits a chain of",
                    f"  {cap_const.value + 1}, which every validating consumer refuses.",
                ],
            )
        elif cap_const.derived_from is None:
            c.drift(
                "c13.actor-cap-retyped",
                f"{cap_const.where()} is written as the literal `{cap_const.raw}` "
                f"rather than derived from the entries cap beside it.",
                [
                    f"  cap: {estate.where(cap_const.repo, cap_const.path)}",
                    "  The two numbers are one rule. A second literal agrees today",
                    "  and is what a later change to the first one walks past: this",
                    "  estate has spent eleven days on exactly that shape once",
                    "  already, with verdryx's copy of nine wire strings.",
                ],
            )
        else:
            c.ok(
                "c13.actor-cap-agrees",
                f"{cap_const.where()} = {cap_const.derived_from} - 1 = {want} "
                f"actors, derived rather than retyped.",
            )

    # -- the finding this check was written for -----------------------------
    if not mapping_files:
        c.missing(
            "c13.no-mapping-found",
            f"no file under a `chain` or `delegation` path declares an RFC 8693 "
            f"`Act` claim, so this check could not find the place where the two "
            f"units meet. That is the only place the off-by-one can live, and an "
            f"anchor that matches nothing has stopped looking for it.",
        )
    for repo, relpath in sorted(mapping_files):
        here = [x for x in caps if x.repo == repo and x.path == relpath]
        if any(x.unit == ACTORS for x in here):
            c.ok(
                "c13.mapping-states-both",
                f"{repo}/{relpath} maps `act` into the chain and states both "
                f"units.",
            )
            continue
        stated = ", ".join(sorted(x.name for x in here)) or "no bound this check can read"
        c.drift(
            "c13.no-actor-cap",
            f"{repo}/{relpath} builds the chain from an RFC 8693 `act` claim and "
            f"states {stated}, with nothing counting the actors.",
            [
                f"  producer: {estate.where(repo, relpath)}",
                f"  spec:     {estate.where(SPEC_REPO, SPEC_PATH)} 5.1 and 5.3",
                "  `on_behalf_of = [sub] + reverse(act)` is a list and a",
                "  list-plus-its-head, so this file bounds two quantities that are",
                "  one apart and names only one of them. Whichever the author had",
                "  in mind, nothing here says which, and nothing downstream can ask.",
                "  Measured 2026-08-27: both producers in this estate had bounded",
                "  the actors, so a full token verified at the door and every",
                "  record it produced was refused as 33 entries.",
            ],
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
