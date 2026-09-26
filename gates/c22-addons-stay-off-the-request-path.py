#!/usr/bin/env python3
"""C22: an optional add-on stays off the path every agent request takes.

WHY

@decided 2026-09-26: an optional add-on (typryx is the first) is integrated
beside the core, never inside it. The repositories every agent request passes
through, the money plane and the policy plane, carry no code, configuration or
documentation naming the add-on. A stack that never installs the add-on runs
exactly as it did, and a stack that does install it cannot slow down or fail a
request because the add-on is slow or down. The add-on reaches the rest of the
stack through the shared event bus by default, and any direct link a consumer
adds is optional, off by default and fails open.

The last two halves live in the consumers' own suites. This gate holds the
first, because it is the one only a cross-repository reader can see: every
repository is free to mention every other one, and nothing inside tokenfuse or
wardryx could tell that a mention of typryx is the start of a dependency on
the request path.

WHERE THE SUBJECTS COME FROM

The registry, never a list here. `estate.json` marks an add-on with
`"addon": true` and a repository on every request's path with
`"request_path": true`. An add-on's names are its registry key and every
component its `runs` field names, so a component added later is a subject the
day it lands. No add-on marked, or no request-path repository marked, is
`missing`: a check with nothing on one side would report agreement over an
empty set.

WHAT IT READS

Every tracked file in each request-path repository, in any case, as a fixed
string, then confirmed per line against a word boundary so `typryxfoo` would
not count while `typryx-keys` and `typryx:v0.2.0` would. Code, docs and configuration alike, because the decision covers all
three: a docs paragraph describing how to wire the add-on into the core is how
the core starts to grow a seam for it.

WHAT IT DOES NOT CATCH

A dependency that never spells the name: a hard-coded address, port or URL of
the add-on inside the core. The estate has one such shape to worry about
(typryx listens on 4320) and nothing in the core names that port today; a
check for it would be a guess about how a future mistake would be spelled.
Launchers are deliberately NOT request-path repositories: they are where an
add-on is supposed to be wired, by configuration.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402


def _names(repo: str, entry: dict) -> list[str]:
    """The strings that name an add-on: its registry key and its components."""
    names = {repo}
    names.update(k for k in entry.get("runs", []) if isinstance(k, str) and k)
    return sorted(names)


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C22", "an optional add-on stays off the path every agent request takes", estate)

    addons = {r: e for r, e in sorted(estate.repos.items()) if e.get("addon") is True}
    core = sorted(r for r, e in estate.repos.items() if e.get("request_path") is True)

    if not addons:
        c.missing(
            "c22.no-addons",
            "estate.json marks no repository `\"addon\": true`, so there is no add-on "
            "to keep off the request path and this check has nothing to measure. "
            "typryx is the estate's add-on; its registry entry lost the marker.",
        )
    if not core:
        c.missing(
            "c22.no-request-path",
            "estate.json marks no repository `\"request_path\": true`, so there is "
            "no core to keep an add-on out of and this check has nothing to "
            "measure. tokenfuse and wardryx are on every agent request's path.",
        )
    if not addons or not core:
        return c

    c.note(
        f"add-ons: {', '.join(addons)}; request path: {', '.join(core)} "
        f"(both from estate.json)."
    )

    for repo in core:
        try:
            estate.dir_of(repo)
        except E.Unavailable as u:
            c.unavailable(
                f"c22.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so whether it "
                f"names an add-on is unmeasured here.",
            )
            continue

        hits: list[tuple[str, str, int, str]] = []
        for addon, entry in addons.items():
            for name in _names(addon, entry):
                word = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", re.IGNORECASE)
                for path in estate.grep_files(repo, name, ignore_case=True):
                    try:
                        text = estate.read_text(repo, path)
                    except (E.Missing, UnicodeDecodeError):
                        continue
                    for n, line in enumerate(text.splitlines(), 1):
                        if word.search(line):
                            hits.append((addon, path, n, line.strip()))

        if hits:
            detail = []
            for addon, path, n, line in hits[:20]:
                detail.append(f"  {estate.where(repo, path)}:{n}  (names {addon})")
                detail.append(f"      {line[:96]}")
            if len(hits) > 20:
                detail.append(f"  ... and {len(hits) - 20} more line(s)")
            detail.append(
                "The add-on and the request path are both marked in this repository's estate.json."
            )
            detail.append(
                "An add-on is wired by configuration in the launchers and talks to the"
            )
            detail.append(
                "core through the event bus; the core names none of it."
            )
            c.drift(
                "c22.core-names-an-addon",
                f"{repo} is on every agent request's path and names an optional "
                f"add-on in {len(hits)} line(s).",
                detail,
            )
        else:
            c.ok(
                "c22.core-free-of-addons",
                f"{repo} names none of: "
                + ", ".join(n for a, e in addons.items() for n in _names(a, e))
                + ".",
            )

    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
