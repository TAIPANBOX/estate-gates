#!/usr/bin/env python3
"""Run every cross-repo gate and summarise.

Each gate is also runnable on its own (`./gates/c4-event-registry.py`). This
runner exists for two reasons beyond convenience: it shares one Estate across
the six, so `--mode clone` clones each repository once rather than six times,
and it is the only place that decides what an INCOMPLETE run means.

EXIT CODES, and why there are four of them

  0  every subject was measured and every comparison agrees.
  1  at least one comparison disagrees. The estate drifted.
  2  nothing disagrees, but a repository that SHOULD have been reachable was
     not. An unread repository is not a clean one, and this is the code that
     says so.
  3  nothing disagrees, and the only unread repositories are the ones
     estate.json records as having no public remote (taipan, bank-in-a-box).
     CI treats 3 as success and prints what went unmeasured. It is a separate
     code rather than a quiet 0 so that nobody can mistake a partial run for a
     complete one by reading the exit status alone.

No check ever reports OK for a subject it could not read. That is enforced in
_estate.Check.verdict, not here.
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "gates"))

import _estate as E  # noqa: E402

GATES = [
    "c1-pin-currency.py",
    "c2-vendored-schemas.py",
    "c3-mirrored-constants.py",
    "c4-event-registry.py",
    "c5-deployment-parity.py",
    "c6-chain-vectors.py",
]

EXIT_PARTIAL_EXPECTED = 3


def load_gate(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise E.Missing(f"{path} could not be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise E.Missing(f"{path} has no run(estate) function")
    return module


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    p.add_argument(
        "--only",
        action="append",
        help="run only the gates whose file name contains this (repeatable)",
    )
    args = p.parse_args()

    gates_dir = pathlib.Path(__file__).resolve().parent / "gates"
    chosen = [
        gates_dir / g
        for g in GATES
        if not args.only or any(o in g for o in args.only)
    ]
    missing = [g for g in chosen if not g.is_file()]
    if missing or not chosen:
        for g in missing:
            print(f"FAIL: {g} is listed in run-gates.py and is not there.")
        if not chosen:
            print("FAIL: no gate matched --only, so this run measured nothing.")
        return E.EXIT_DRIFT

    estate = E.estate_from_args(args)

    print("=" * 78)
    print("TAIPANBOX estate gates")
    print(f"Source: {estate.label()}")
    print("=" * 78)
    print()

    results: list[tuple[str, str, int]] = []
    started = time.time()
    for path in chosen:
        module = load_gate(path)
        check = module.run(estate)
        code = check.render()
        results.append((check.key, check.verdict(), code))
        print("-" * 78)
        print()

    unread = estate.unavailable_repos()
    expected_unread = {
        r: why
        for r, why in unread.items()
        if not estate.repos.get(r, {}).get("github")
    }
    unexpected_unread = {r: why for r, why in unread.items() if r not in expected_unread}

    reds = [k for k, v, _ in results if v in (E.DRIFT, E.MISSING)]
    partials = [k for k, v, _ in results if v == E.UNAVAILABLE]

    print("=" * 78)
    print(f"SUMMARY  ({time.time() - started:.1f}s)")
    for key, verdict, _ in results:
        label = {
            E.OK: "clean",
            E.DRIFT: "DRIFT",
            E.MISSING: "DRIFT",
            E.UNAVAILABLE: "partial, something went unmeasured",
        }[verdict]
        print(f"  {key}  {label}")
    print()

    if unread:
        print("Repositories this run could not read:")
        for repo, why in sorted(unread.items()):
            print(f"  {repo}: {why}")
        print()

    if reds:
        print(f"{len(reds)} of {len(results)} gates found the estate drifted: "
              f"{', '.join(reds)}.")
        print("Each finding above names both sides and the file to open. A red")
        print("badge on this repository means the estate drifted, not that this")
        print("repository is broken.")
        return E.EXIT_DRIFT

    if unexpected_unread:
        print(f"No gate found a disagreement, and {len(unexpected_unread)} "
              f"repository/ies that should have been reachable were not.")
        print("Nothing here reports clean about a repository it never opened.")
        return E.EXIT_INCOMPLETE

    if partials:
        print(f"No gate found a disagreement. {len(partials)} gate(s) are PARTIAL: "
              f"{', '.join(partials)}.")
        print("The only unread repositories are the ones estate.json records as")
        print("having no public remote, so this is the expected shape of a CI run,")
        print("and it is still not a statement about what went unmeasured.")
        return EXIT_PARTIAL_EXPECTED

    print(f"All {len(results)} gates clean, and every subject was measured.")
    return E.EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
