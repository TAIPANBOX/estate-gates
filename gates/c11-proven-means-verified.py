#!/usr/bin/env python3
"""C11: nothing tells the PDP a chain was proved unless it verified one.

WHY

wardryx decides on `chain_proven` (`deny_if_chain_unproven`, and the depth and
root rules are only meaningful once something has been proved). Its own comment
at `internal/pdp/pdp.go` states the trust boundary plainly: "a caller that lies
about this is believed. That is not a weakness of this field, it is where the
boundary is."

That boundary is correct and it is exactly why it needs a check on THIS side of
it. The PDP cannot tell a verified `true` from an asserted one. Nobody can,
from inside wardryx. It is visible only to something holding wardryx and every
producer open at once, which is what this repository is for.

The failure it names is the one the 2026-08-25 plan called A5: a proven chain
must not be silently downgraded to an unproven one, and its mirror, an unproven
one must not be silently upgraded. The upgrade is the dangerous half. A
downgrade makes a policy fire that should not have; an upgrade makes one stay
silent, and `deny_if_chain_unproven` staying silent looks exactly like an
estate where every chain is proved.

WHAT IS COMPARED

Every place in the estate that sets `chain_proven` to a LITERAL true, in
non-test code, must sit in a file that also calls a delegation VERIFIER.

The literal is the point and the limit both. This reads text, so it sees
`chain_proven: true` and not `chain_proven: some_bool`. The estate's own two
doors do the latter: they take the value from `chainproof::resolve`, through a
match arm, which is exactly right and invisible here. What the literal catches
is somebody wiring a NEW enforcement point and writing `true` because they mean
"this one is fine", which is the shape a rubber stamp actually takes.

So the "measured nothing" branch counts MENTIONS rather than assertions. The
first version counted assertions, found none, and reported that the PDP was
deciding on a field nobody set, about an estate whose two doors set it
correctly. A gate that says that forever is invariant 1's own failure, and this
gate was it. Not
a proof that the verification is correct: a proof that one was CALLED at all,
which is the difference between an enforcement point and a rubber stamp.

A call and not an import. `use tokenfuse_delegation::verify_delegation;` at the
top of a file that never calls it is what a refactor leaves behind, and
counting it would let this check pass on the wreckage.

The verifiers, and there are three because there are three languages:

  Rust    `chainproof::resolve`, or `verify_delegation` from
          `tokenfuse-delegation` (which was `cloud::delegation` until it was
          cut into its own crate so the gateway could use it).
  Go      `delegation.Verify` / `delegation.VerifyToken` from agent-stack-go.
  Python  no verifier exists yet, so a Python producer setting this is a
          finding by construction and says so in its own words.

WHY A LITERAL AND NOT A DATA FLOW

This reads text, so it sees `chain_proven: true` and not
`chain_proven: some_bool_that_happens_to_be_true`. That is a real limit and it
is stated rather than hidden. The literal is the shape a rubber stamp actually
takes: somebody wiring a new enforcement point writes `true` because they mean
"this one is fine", not because they threaded a variable through.

A TEST IS NOT A PRODUCER. Test code sets this to true constantly and must: that
is how the rules are tested at all. Files under `tests/`, or named `*_test.*`,
`*.test.*`, `test_*.py`, or `*_test.go`, are excluded, and the count of what was
excluded is reported so a producer hiding in a file named like a test is
visible as a number that moved.

IT REFUSES WHEN IT FOUND NOTHING. If no producer sets `chain_proven` anywhere,
this measured nothing: either no enforcement point has been wired yet, or the
field was renamed and this check is now looking for a string that no longer
exists. Both need a person, and both look identical to a clean run.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

FIELD = "chain_proven"

# The literal, in the three languages' spellings. Rust and Go struct literals,
# JSON, and the Rust shorthand `chain_proven,` where a local of that name is
# moved into a struct field are all the same statement.
SETS_TRUE = re.compile(
    r"""chain_proven \s* [:=] \s* true       # rust/go/json/python-ish
      | ChainProven \s* [:=] \s* true        # go field
      | "chain_proven" \s* : \s* true        # json
    """,
    re.X | re.I,
)

# A CALL, not an import. `use tokenfuse_delegation::...` at the top of a file
# that never calls it is exactly what a refactor leaves behind, and counting it
# would make this check pass on the wreckage. The open paren is the whole point.
VERIFIERS = (
    "chainproof::resolve(",
    "verify_delegation(",
    "delegation.Verify(",
    "delegation.VerifyToken(",
    "VerifyWith(",
)

TEST_PATH = re.compile(
    r"(^|/)tests?/ | _test\.(go|rs|py)$ | \.test\.(ts|tsx|js)$ | (^|/)test_[^/]+\.py$",
    re.X,
)

SOURCE_SUFFIXES = (".rs", ".go", ".py", ".ts", ".tsx")


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C11", "a proved chain was proved by something", estate)

    asserted = 0
    mentions = 0
    skipped_tests = 0
    searched = 0

    for repo in sorted(estate.repos):
        try:
            hits = estate.grep_files(repo, FIELD)
        except E.Unavailable as u:
            c.unavailable(
                f"c11.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so nothing in "
                f"it was checked for an asserted `{FIELD}`.",
            )
            continue
        except E.Missing as m:
            c.unavailable(
                f"c11.search-failed:{repo}",
                f"{repo} could not be searched ({m}).",
            )
            continue
        searched += 1

        for relpath in hits:
            if not relpath.endswith(SOURCE_SUFFIXES):
                continue
            if TEST_PATH.search(relpath):
                skipped_tests += 1
                continue
            try:
                text = estate.read_text(repo, relpath)
            except (E.Unavailable, E.Missing):
                continue
            mentions += 1
            if not SETS_TRUE.search(text):
                # The field is alive here and nothing in this file CLAIMS it.
                # That is the ordinary shape: `chain_proven: ctx.chain_proven`
                # passes a value along, and the file that produced the value is
                # the one this check is about.
                continue

            asserted += 1
            if any(v in text for v in VERIFIERS):
                c.ok(
                    "c11.proved-by-something",
                    f"{repo}:{relpath} tells the PDP a chain was proved and reaches "
                    f"a verifier in the same file.",
                )
                continue

            c.drift(
                "c11.asserted-not-verified",
                f"{repo}:{relpath} sets `{FIELD}` true and no delegation verifier "
                f"is reached anywhere in that file.",
                [
                    f"  file: {estate.where(repo, relpath)}",
                    "",
                    "wardryx believes this field. Its own comment says so: `a caller",
                    "that lies about this is believed`. So a `true` written here",
                    "without a verification behind it turns `deny_if_chain_unproven`",
                    "into a rule that never fires, which looks exactly like an estate",
                    "where every chain is proved.",
                    "",
                    "Either call a verifier in this file, or send false and let the",
                    "PDP judge an unproven chain, which is a real and honest answer.",
                    f"A call to one of: {', '.join(VERIFIERS)}",
                ],
            )

    if searched == 0:
        c.unavailable(
            "c11.nothing-searched",
            "no repository could be read in this run, so nothing was checked.",
        )
        return c

    if mentions == 0:
        c.missing(
            "c11.no-producer",
            f"nothing in {searched} repositories mentions `{FIELD}` outside test code.",
            [
                "This check measured nothing, and the two ways that happens need",
                "different people:",
                "  - no enforcement point has been wired yet, so the PDP is deciding",
                "    on a field nobody sets and every chain reaches it unproven;",
                f"  - or the field was renamed and `{FIELD}` is now a string that",
                "    exists nowhere, which makes this check permanently and quietly",
                "    green.",
                "",
                "It counts MENTIONS, not assertions. The first version counted files",
                "writing a literal `true`, and the estate's only real producer sets",
                "the value from a match arm returning a tuple, so the count was zero",
                "and this said `measured nothing` about a working enforcement point.",
                "A check that reports that forever is what invariant 1 is about, and",
                "it was this gate about itself.",
                f"({skipped_tests} test file(s) mentioning it were skipped, which is",
                "correct: a test sets this constantly and must.)",
            ],
        )
        return c

    c.ok(
        "c11.nothing-asserted-unverified",
        f"{mentions} file(s) outside test code carry `{FIELD}` and {asserted} assert "
        f"it as a literal; every assertion, if any, calls a verifier in its own file. "
        f"({skipped_tests} test file(s) skipped, which is correct: a test sets this "
        f"constantly and must.)",
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
