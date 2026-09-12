#!/usr/bin/env python3
"""C19: a repository at 1.0 declares its compatibility surface, and the
surface is held by a gate the repository runs.

WHY

SemVer 2.0.0 item 5: "Version 1.0.0 defines the public API." A 1.0 tag is a
promise about a surface, and a promise nobody can point at is a mood. The
estate's first two 1.0 tags, both cut 2026-09-12, each came with the surface
written down and a gate that fails when it moves: agent-passport's SPEC.md
section 10 held by `scripts/version-compatibility.sh`, agent-stack-go's
`api/surface.txt` held by `scripts/api-surface.sh`. This gate is what stops a
third 1.0 from being cut without either half.

WHAT IS DECLARED, AND WHERE

`estate.json` carries, per repository, an optional `major` (an integer, the
major version the repository promises) and an optional `compat` object:

  "major": 1,
  "compat": {"manifest": "compat/1.0.json", "gate": "scripts/compat-surface.sh"}

The two paths default to `compat/1.0.json` and `scripts/compat-surface.sh`
(RELEASE-1.0-PLAN 4.2); a repository whose surface has another shape names its
own, as the two above do. `"compat": {"exempt": "<reason>"}` records a
repository that carries a major past 0 without a manifest, with the reason
written where this gate reads it; engram, versioned past 1.0 before the estate
had a compat surface at all, is the case. An exemption is printed on every
run, so it cannot become invisible.

WHAT COUNTS AS A FAILURE

  c19.manifest-missing   the declared manifest is not in the repository
  c19.gate-missing       the declared gate script is not in the repository
  c19.gate-not-in-ci     no workflow under .github/workflows names the gate,
                         so the surface is checked only when somebody
                         remembers to
  c19.tag-major-mismatch the newest v* tag's major is below the declared one:
                         the promise is written and the release that makes it
                         has not been cut, or the declaration is wrong
  c19.no-tags            a major is declared and no v* tag exists at all
  c19.undeclared-major   the newest v* tag is 1.0.0 or above and estate.json
                         declares no major for the repository: a 1.0 was cut
                         with no written surface behind it, the failure this
                         gate exists for
  c19.no-subjects        no repository declares a major or carries a tag at
                         1.0.0 or above, so this gate measured nothing; the
                         estate has two, so measuring none means this check
                         read the wrong thing

For a repository at 0.x with no declaration nothing is required: a 0.x tag
promises nothing under SemVer, and this gate does not invent an obligation.

WHAT IT DOES NOT CATCH

Whether the manifest is TRUE. That is the repository's own gate's job, run in
its own CI: this one checks the manifest and the gate exist and the gate is
wired, the same limit C18 states about the decisions table. It does not read
the manifest's contents or run anything.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

DEFAULT_MANIFEST = "compat/1.0.json"
DEFAULT_GATE = "scripts/compat-surface.sh"
_WORKFLOW = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")


def newest_tag(estate: E.Estate, repo: str) -> tuple[str, tuple[int, int, int]] | None:
    """The highest v* tag by semver, or None when the repository has none."""
    best = None
    for tag in estate.tags(repo):
        v = E.semver(tag)
        if v is None:
            continue
        if best is None or v > best[1]:
            best = (tag, v)
    return best


def gate_wired(estate: E.Estate, repo: str, gate: str) -> bool:
    """True when some workflow's text names the gate script."""
    for path in estate.list_files(repo, ".yml") + estate.list_files(repo, ".yaml"):
        if not _WORKFLOW.match(path):
            continue
        try:
            if gate in estate.read_text(repo, path):
                return True
        except E.Missing:
            continue
    return False


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C19", "a repository at 1.0 declares its compatibility surface", estate)
    subjects = 0

    for repo in sorted(estate.repos):
        entry = estate.repos[repo]
        declared = entry.get("major")
        compat = entry.get("compat") or {}
        try:
            newest = newest_tag(estate, repo)
        except E.Unavailable as u:
            c.unavailable(f"c19.repo-unavailable:{repo}", str(u))
            continue
        except E.Missing as m:
            c.unavailable(f"c19.repo-unavailable:{repo}", str(m))
            continue

        if declared is None:
            if compat.get("exempt"):
                subjects += 1
                c.ok(
                    f"c19.exempt:{repo}",
                    f"{repo} carries no compat manifest by recorded exemption: {compat['exempt']}",
                )
                continue
            if newest is not None and newest[1][0] >= 1:
                subjects += 1
                c.drift(
                    "c19.undeclared-major",
                    f"{repo}'s newest tag is {newest[0]} and estate.json declares no major for it.",
                    [
                        f"  tag:    {newest[0]} in {estate.where(repo, '')}",
                        "A 1.0 is a promise about a surface. Declare `major` and `compat` in",
                        "estate.json and write the manifest and the gate, or record an",
                        "exemption with its reason.",
                    ],
                )
            continue

        subjects += 1
        manifest = compat.get("manifest", DEFAULT_MANIFEST)
        gate = compat.get("gate", DEFAULT_GATE)
        detail = [f"  declared: major {declared}, manifest {manifest}, gate {gate}"]

        if newest is None:
            c.missing(
                "c19.no-tags",
                f"{repo} declares major {declared} and has no v* tag at all.",
                detail + ["A declaration ahead of every release is a plan, not a promise."],
            )
        elif newest[1][0] < declared:
            c.drift(
                "c19.tag-major-mismatch",
                f"{repo} declares major {declared} and its newest tag is {newest[0]}.",
                detail
                + [
                    "Either the release that makes the promise has not been cut, or the",
                    "declaration is ahead of the repository. Both are red: a reader of",
                    "estate.json would believe a surface is frozen that is not.",
                ],
            )
        else:
            c.ok(f"c19.tag:{repo}", f"{repo} declares major {declared}; newest tag {newest[0]}.")

        if not estate.exists(repo, manifest):
            c.missing(
                "c19.manifest-missing",
                f"{repo} declares its compatibility manifest at {manifest}, which is not there.",
                detail + [f"  looked at: {estate.where(repo, manifest)}"],
            )
        else:
            c.ok(f"c19.manifest:{repo}", f"{repo}: {manifest} exists.")

        if not estate.exists(repo, gate):
            c.missing(
                "c19.gate-missing",
                f"{repo} declares the gate that holds its surface at {gate}, which is not there.",
                detail + [f"  looked at: {estate.where(repo, gate)}"],
            )
            continue
        c.ok(f"c19.gate:{repo}", f"{repo}: {gate} exists.")

        try:
            wired = gate_wired(estate, repo, gate)
        except E.Missing as m:
            c.unavailable(f"c19.repo-unavailable:{repo}", str(m))
            continue
        if wired:
            c.ok(f"c19.wired:{repo}", f"{repo}: a workflow under .github/workflows names {gate}.")
        else:
            c.drift(
                "c19.gate-not-in-ci",
                f"{repo}'s surface gate {gate} is named by no workflow under .github/workflows.",
                detail
                + [
                    "A gate nobody runs on every push holds nothing. Name it in the CI",
                    "workflow beside the repository's other gates.",
                ],
            )

    if subjects == 0:
        c.missing(
            "c19.no-subjects",
            "no repository in estate.json declares a major or carries a tag at 1.0.0 or "
            "above, so this gate measured nothing. The estate has two such repositories, "
            "so finding none means this check read the wrong thing rather than that "
            "nothing is promised.",
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
