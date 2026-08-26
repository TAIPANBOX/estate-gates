#!/usr/bin/env python3
"""C10: the RFC 8693 mapping produces one chain, in every language that
implements it.

WHY

agent-passport SPEC 5.3 says how an RFC 8693 `act` claim becomes an
`on_behalf_of` chain, and the mapping is the one place in this estate where a
mistake produces something that VERIFIES PERFECTLY and asserts the opposite of
what happened. A signature is over the claims; it says nothing about whether
the reader turned them into the right list.

Two mistakes are available and both were made on 2026-08-26, in the hour the
mapping was first written.

The direction. RFC 8693 4.1 nests `act` current-first: the outermost actor is
the immediate one. SPEC 5 orders `on_behalf_of` root-first. Reverse it wrongly
and the record says the root delegated to nobody and the newest agent
authorised the whole chain.

The head. The RFC keeps the subject OUT of `act`, because the subject is who
the token is FOR and is not an actor. SPEC 5 puts the root INTO the chain. So
the mapping is `[sub] + reverse(act)`, a list and a list-plus-its-head, not a
reversal. Miss that and the chain is written WITH THE HUMAN MISSING FROM IT.
Every token still verifies. Nothing downstream can tell.

WHY IT IS ESTATE-SHAPED RATHER THAN A NOTE IN ONE REPOSITORY

Two implementations exist and neither can see the other:
`agent-stack-go/delegation` for the five Go enforcement points, and
`tokenfuse/crates/delegation/src/lib.rs` for the Rust side, wherever that
file has moved to since. Each holds its
expected chain as a LITERAL in its own suite, retyped by hand. Change one and
the other goes on passing. Both would report green while producing two
different answers about who acted for whom, which is exactly the shape C6
already guards for the canonicalization vectors.

WHAT IS COMPARED

The principals, in order, out of each implementation's mapping test. They are
PINNED VECTORS in C6's sense: the fixture names are part of the comparison, so
renaming one in one suite and not the other is drift and is reported as drift.
That is deliberate. A gate that compared only the shape would pass a rename
that quietly split two suites apart, and the shape is the easy half.

WHAT IT DOES NOT CATCH

It reads the TESTS, not the mapping code. An implementation whose test agrees
and whose code disagrees would pass here and fail its own suite, which is the
right division: this gate exists for drift BETWEEN repositories, and a
repository disagreeing with itself is its own suite's job.

It knows about two implementations. A third, in a language nobody has added
yet, is invisible until somebody adds it here, which is the standing weakness
of every list in this repository and is why the finding names how many it
compared rather than claiming completeness.

And it says nothing about SPEC 5.2's other MUST, that a proven chain must not
be forwarded as an unproven one. Nothing carries `delegation_proof` yet, so
there is no forwarding to check; when a producer does, this is the gate to
widen.
"""

from __future__ import annotations

import argparse
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import _estate as E  # noqa: E402

# Where each implementation's mapping test lives, and the test that holds the
# vector. Named rather than searched: a gate that grepped every file for
# `user://` would find fixtures that are not this vector and report on them.
SOURCES = [
    (
        "agent-stack-go",
        "delegation/chain_test.go",
        "TestTheEstateChainCarriesTheSubjectAndTheRfcsActDoesNot",
    ),
    (
        # The PATH is a hint, not the subject. See `find_subject`.
        "tokenfuse",
        "crates/delegation/src/lib.rs",
        "a_delegation_verifies_and_the_chain_keeps_its_root",
    ),
]

PRINCIPAL = re.compile(r'"((?:user|agent)://[^"]+)"')


def body_of(text: str, fn: str) -> str | None:
    """The source of one test function, from its name to the next top-level
    `func`/`fn` at the same indentation. Crude and deliberately so: the
    alternative is a parser per language, and the vector is a run of string
    literals rather than a structure."""
    i = text.find(fn)
    if i < 0:
        return None
    rest = text[i:]
    stop = re.search(r"\n(?:func |    fn |fn )", rest[1:])
    return rest[: stop.start() + 1] if stop else rest


def find_subject(estate: E.Estate, repo: str, hint: str, fn: str) -> str | None:
    """Where the test named `fn` actually lives in `repo`, or None.

    The path was a fixed string until 2026-08-26, and on that day the Rust
    verifier moved from `crates/cloud/src/delegation.rs` into its own crate so
    the gateway could use it without depending on the control plane. The file
    was gone, this gate said so honestly, and main went red for a rename.

    "Measured nothing" was the RIGHT answer to give and the wrong question to be
    asking. The subject of this comparison is a TEST, not a file: a test that
    moved is still being asserted, and a test that was deleted is the failure
    worth a red. So the hint is tried first, because it is almost always right
    and costs one read, and a search follows when it is not.

    This is the third time today a check has been told where to look instead of
    looking: C2's copies and C4's producers were the other two. The shape is the
    same each time. A hand-written location is a copy of the truth that nothing
    watches, and the fix is to name what the subject IS rather than where it was
    last seen.
    """
    if estate.exists(repo, hint):
        return hint
    try:
        hits = estate.grep_files(repo, fn)
    except (E.Unavailable, E.Missing):
        return None
    for path in hits:
        if path.endswith((".rs", ".go", ".py")):
            return path
    return None


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C10", "the RFC 8693 mapping, in every language", estate)

    chains: dict[str, list[str]] = {}
    for repo, path, fn in SOURCES:
        # A repository this run could not reach is NOT a red finding: the
        # runner's exit codes distinguish "the estate drifted" from "this run
        # could not look", and CI reads the exit code and nothing else. Turning
        # an unreachable checkout into drift would report a disagreement
        # nobody observed.
        try:
            estate.dir_of(repo)
        except E.Unavailable as u:
            c.unavailable(
                f"c10.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so its "
                f"mapping was not compared against the others.",
            )
            continue
        found = find_subject(estate, repo, path, fn)
        if found is None:
            c.missing(
                "c10.no-implementation-to-read",
                f"{repo}: no file holds {fn}, so this comparison measured nothing "
                f"rather than agreeing with itself.",
                [
                    f"  looked at {path} first, then searched the repository.",
                    "A moved test is found; a DELETED one is this finding, and it",
                    "means one language's mapping is asserted nowhere.",
                ],
            )
            continue
        if found != path:
            c.note(f"{repo}: {fn} has moved to {found} (this file expects {path}).")
        path = found
        text = estate.read_text(repo, path)
        body = body_of(text, fn)
        if body is None:
            c.missing(
                "c10.no-vector-to-read",
                f"{repo}: {path} has no {fn}, so the mapping's own vector is "
                f"not being asserted anywhere this gate can see.",
            )
            continue
        # Read from the ASSERTION, not from the whole body, and this is the
        # correction the self-test forced. A body also names the principals
        # that BUILD the token, so taking the last N of everything found the
        # same three whatever the assertion said: dropping the subject from
        # the expected chain left the gate silent, because the subject was
        # still in the line that built the token. The gate could not see the
        # exact failure it exists for.
        #
        # A vector may be written as a slice of literals or as one
        # comma-joined string, and both forms are in use: Go asserts
        # `strings.Join(chain, ",")` against one literal, Rust asserts a
        # `vec![...]`. Anchoring on the assertion reads both without asking
        # either suite to change how it expresses itself.
        anchored = None
        for marker in ("want :=", "want =", "vec!["):
            at = body.rfind(marker)
            if at > (anchored if anchored is not None else -1):
                anchored = at
        if anchored is None:
            c.missing(
                "c10.no-assertion-to-read",
                f"{repo}: {fn} makes no assertion this gate can anchor on "
                f"(`want :=`, `want =` or `vec![`), so the principals it names "
                f"could be the token's rather than the expected chain's.",
            )
            continue
        found: list[str] = []
        for hit in PRINCIPAL.findall(body[anchored:]):
            found.extend(part for part in hit.split(",") if part)
        # The vector is the LAST run of three or more principals in the body:
        # the expected chain is asserted after the token is built, and the
        # token's own literals come first.
        if len(found) != 3:
            c.missing(
                "c10.vector-too-short",
                f"{repo}: {fn} asserts {len(found)} principal(s); this vector "
                f"is a subject and two actors, and one that is not cannot show "
                f"a direction or a missing head.",
            )
            continue
        chains[repo] = found

    if len(chains) < 2:
        c.note(
            "fewer than two implementations were readable, so nothing was "
            "compared across languages."
        )
        return c

    repos = sorted(chains)
    first = repos[0]
    disagreed = False
    for other in repos[1:]:
        if chains[other] != chains[first]:
            disagreed = True
            c.drift(
                "c10.mapping-disagrees-across-languages",
                f"{first} and {other} map one token to two different chains.",
                [
                    f"  {first}: {' -> '.join(chains[first])}",
                    f"  {other}: {' -> '.join(chains[other])}",
                    "SPEC 5.3: on_behalf_of = [sub] + reverse(act), root first.",
                    "A mapping that disagrees still verifies: the signature is",
                    "over the claims and says nothing about how they were read.",
                ],
            )

    root = chains[first][0]
    if not root.startswith("user://"):
        c.drift(
            "c10.vector-has-no-human-at-its-root",
            f"the pinned vector's root is {root!r}, not a user://.",
            [
                "The mapping's worst failure writes the chain with the human",
                "MISSING from it, and a vector rooted at an agent cannot show",
                "the difference. SPEC 5: the first entry is the root, usually a",
                "human.",
            ],
        )
        disagreed = True

    if not disagreed:
        c.ok(
            "c10.mapping-agrees-across-languages",
            f"{len(chains)} implementation(s) map one token to the same chain, "
            f"root first with the subject at its head: {' -> '.join(chains[first])}.",
        )
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    check = E.estate_from_args(args).run_one(run)
    check.render()
    return check.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
