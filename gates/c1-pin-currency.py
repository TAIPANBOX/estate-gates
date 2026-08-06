#!/usr/bin/env python3
"""C1: every consumer of agent-stack-go is pinned to the version the module
actually is.

WHY

agent-stack-go is the estate's single source of the wire types. A consumer
pinned to an old minor is not slightly behind: it is speaking a different
contract while every document says there is one. idryx sat on v0.3.0 while the
module was at v0.5.1, and the whole delta was the tamper-evidence chain
verifier idryx needed most. Nothing failed. Nothing could: no gate in any
repository can see two repositories at once.

WHAT COUNTS AS A FAILURE, AND WHY THAT LINE

ANY lag fails. The finding ID says which kind it is, and the exit code does
not soften for either:

  c1.minor-behind   a minor or major behind. The module is pre-1.0, so under
                    semver a minor bump is where behaviour and breakage live:
                    v0.5.0 is the release that added the chain verifier. Two
                    consumers a minor apart are two dialects.
  c1.patch-behind   a patch behind. Same contract, missing fixes.
  c1.ahead-of-module   pinned to something no tag names, which usually means a
                    pseudo-version or a replace, and a build that cannot be
                    reproduced from a tag is not a release.

The alternative considered and rejected was making a patch lag a warning that
does not fail the run. A warning nothing enforces is a comment with an exit
code: it accumulates, everyone learns to scroll past it, and the estate is
back where it started. The severity distinction is worth SAYING, which is what
the two IDs do, and is not worth encoding in the exit status.

The other objection is that a fresh minor release turns this red for every
consumer on the day it is cut, before anyone could have adopted it. That is
correct and it is the intended reading: the day after a release is exactly
when the estate is most drifted. A grace period would make this check report
green during the one window it exists to describe. The fix is one line per
consumer, and the failure names every one of them.

WHAT IT DOES NOT CATCH

The go.mod version, not what is vendored or replaced. A `replace` directive
pointing at a local path would pass this cleanly, and go.sum is not read at
all. Both are listed in the README as uncovered.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

MODULE = "github.com/TAIPANBOX/agent-stack-go"
MODULE_REPO = "agent-stack-go"

# `require github.com/... v0.4.0` on its own line, or the same inside a
# require ( ... ) block, with or without a trailing // indirect comment.
_REQUIRE = re.compile(
    r"^\s*(?:require\s+)?" + re.escape(MODULE) + r"\s+(v\S+)", re.MULTILINE
)
_REPLACE = re.compile(r"^\s*replace\s+" + re.escape(MODULE) + r"\s", re.MULTILINE)


def newest_tag(estate: E.Estate) -> tuple[str, tuple[int, int, int]]:
    tags = [t for t in estate.tags(MODULE_REPO) if E.semver(t)]
    if not tags:
        raise E.Missing(
            f"{MODULE_REPO} has no semver tags in this run, so there is nothing "
            f"to compare a pin against. In --mode clone this usually means the "
            f"tag fetch failed; a check that cannot see the newest release must "
            f"not report every consumer current."
        )
    tags.sort(key=lambda t: E.semver(t))  # type: ignore[arg-type]
    return tags[-1], E.semver(tags[-1])  # type: ignore[return-value]


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C1", "pin currency: consumers of agent-stack-go", estate)

    try:
        newest, newest_v = newest_tag(estate)
    except E.Unavailable as u:
        c.unavailable(
            "c1.module-unavailable",
            f"{MODULE_REPO} could not be read in this run ({u.reason}), so no pin "
            f"was compared against anything.",
        )
        return c
    except E.Missing as m:
        c.missing("c1.no-tags", str(m))
        return c

    c.note(f"agent-stack-go's newest tag is {newest}.")

    consumers: list[tuple[str, str, str]] = []
    for repo in sorted(estate.repos):
        if repo == MODULE_REPO:
            continue
        try:
            gomods = [f for f in estate.list_files(repo) if f.endswith("go.mod")]
        except E.Unavailable as u:
            c.unavailable(
                f"c1.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so whether it "
                f"consumes {MODULE} is unknown here.",
            )
            continue
        except E.Missing as m:
            c.missing("c1.repo-unreadable", str(m))
            continue
        for gomod in gomods:
            try:
                text = estate.read_text(repo, gomod)
            except E.Missing as m:
                c.missing("c1.gomod-vanished", str(m))
                continue
            if MODULE not in text:
                continue
            m = _REQUIRE.search(text)
            if not m:
                c.missing(
                    "c1.require-unparsed",
                    f"{estate.where(repo, gomod)} names {MODULE} but no require "
                    f"line for it could be parsed, so its pin is unknown. The "
                    f"anchor this check uses stopped matching; fix the anchor "
                    f"rather than assuming the pin is fine.",
                )
                continue
            consumers.append((repo, gomod, m.group(1)))
            if _REPLACE.search(text):
                c.drift(
                    "c1.replace-directive",
                    f"{estate.where(repo, gomod)} carries a `replace` for {MODULE}, "
                    f"so the version it names is not the version it builds.",
                    [
                        "A replace makes the pin below unenforceable and is invisible",
                        "to every other check in the estate.",
                    ],
                )

    if not consumers:
        c.missing(
            "c1.no-consumers",
            f"no repository in estate.json was found requiring {MODULE}. The "
            f"estate has at least six Go consumers, so finding none means this "
            f"check read the wrong thing rather than that the estate is clean.",
        )
        return c

    for repo, gomod, pin in sorted(consumers):
        pv = E.semver(pin)
        where = estate.where(repo, gomod)
        if pv is None:
            c.drift(
                "c1.unparseable-pin",
                f"{repo} pins {MODULE} at {pin}, which is not a plain vX.Y.Z tag.",
                [
                    f"  consumer: {where}",
                    f"  module:   {estate.where(MODULE_REPO, 'go.mod')}, newest tag {newest}",
                    "A pseudo-version or a +incompatible pin cannot be compared to a",
                    "release, so nobody can say whether this consumer is current.",
                ],
            )
            continue
        if pv > newest_v:
            c.drift(
                "c1.ahead-of-module",
                f"{repo} pins {MODULE} at {pin}, ahead of the module's newest tag "
                f"{newest}.",
                [
                    f"  consumer: {where}",
                    f"  module:   {MODULE_REPO}, newest tag {newest}",
                    "A pin no tag names cannot be reproduced from a checkout.",
                ],
            )
            continue
        if pv == newest_v:
            c.ok("c1.current", f"{repo} pins {pin}, which is the newest tag.")
            continue
        behind_minor = (pv[0], pv[1]) != (newest_v[0], newest_v[1])
        detail = [
            f"  consumer: {where} pins {pin}",
            f"  module:   {MODULE_REPO} newest tag {newest}",
        ]
        if behind_minor:
            c.drift(
                "c1.minor-behind",
                f"{repo} pins {MODULE} at {pin} and the module is at {newest}: "
                f"a minor or more behind.",
                detail
                + [
                    "The module is pre-1.0, so a minor bump is where behaviour and",
                    "breakage live. This consumer is on a different contract from the",
                    "ones that are current.",
                ],
            )
        else:
            c.drift(
                "c1.patch-behind",
                f"{repo} pins {MODULE} at {pin} and the module is at {newest}: "
                f"a patch behind.",
                detail
                + [
                    "Same contract, missing fixes. This is the mild half of C1 and it",
                    "is still red, because a patch nobody adopts is a fix nobody got.",
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
