#!/usr/bin/env python3
"""C27: the tool hold is one block, in both stacks.

WHY

`@decided 2026-11-07`, paraphrased: a tool call nothing grants is held for a
person on a default install of either stack, a model call passes, and only an
explicit grant lifts the hold. The rule and the grants the stacks need for their
own checks are written by a shell function in each: stack-single's install.sh into
policy.yaml, stack-k8s's lib/tool-hold.sh into the ConfigMap wardryx-tool-hold.
Each repository's own gate holds its copy, line by line, against itself. Neither
can see the other.

This estate has been here once: the starter policy of stack-single and of stack-k8s
drifted onto two different fire-drill domains, `drill.local` and `mockryx.local`,
with both suites green, and a fire drill stopped reaching the rule written for it.
A grant that exists on one stack and not the other is the same defect with a worse
face: an agent that works on a box and waits for a person on a cluster, or the
other way round, and no check that can say so. So the comparison lives here.

WHAT IS READ

  stack-single  install.sh         the functions tool_hold_block, tool_hold_sources
  stack-k8s     lib/tool-hold.sh   the same two functions

A function runs from the line that opens it to the first line that is only `}`,
and a shell comment inside it is not part of it. The one line allowed to differ is
the begin marker, which names its own file and invariant number: it is read as
`# tool-hold: begin` and it has to be there. Everything else in the body is compared
line by line, the conditional around grant-operator-web included, because a rule
that one stack writes under another condition is a rule that one stack does not
write.

tool_hold_sources is compared by the identity lists it can print. The body says
`$(tool_hold_sources)`, so two identical bodies can still render two different
grants. Its code differs on purpose: stack-single reads .env for a box that named
its agents as static, stack-k8s has no .env.

WHAT COUNTS AS A FAILURE

  c27.block-differs    a line of one body is not the line of the other, or one
                       body ends first; the finding names both, with their lines
  c27.sources-differ   the two functions can print different identity lists
  c27.no-floor         the bodies agree and neither writes the floor, which is
                       agreement about nothing
  c27.marker-missing   a body has no begin marker of the shape the stacks render
                       and remove by; a block nothing can find is not managed
  c27.anchor-missing   a function is not in its file
  c27.file-missing     a file is gone

WHAT IT DOES NOT CATCH

  - That wardryx reads what the block says. Each stack's tool-hold-is-seeded.sh
    serves the block on the pinned image.
  - Whether a stack calls the function. The same gates hold the order of the calls.
  - stack-up. Its block goes with --typed-risk-signal and carries a grant for its
    own printed example, so it is a different block on purpose; its own
    scripts/tool-hold-is-seeded.sh holds it.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

SIDES = (("stack-single", "install.sh"), ("stack-k8s", "lib/tool-hold.sh"))
BLOCK = "tool_hold_block"
SOURCES = "tool_hold_sources"

# The line both stacks render, remove and count by. Only the file and the invariant
# number may differ between them, because each names its own.
_MARKER = re.compile(r"'# tool-hold: begin \(managed by [^;']+; TOOL_HOLD, invariant \d+\)'")
_MARKER_NORMAL = "'# tool-hold: begin'"
_FLOOR = "'  when_no_grant: hold'"
_PRINTED = re.compile(r"printf '([^'%]+)'")


def _function(text: str, name: str) -> list[tuple[int, str]] | None:
    """The body of `name() {`, as (line number, stripped line), comments left out."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{name}() {{"):
            body = []
            for n in range(i + 1, len(lines)):
                if lines[n] == "}":
                    return body
                stripped = lines[n].strip()
                if stripped and not stripped.startswith("#"):
                    body.append((n + 1, stripped))
            return None
    return None


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C27", "the tool hold is one block in both stacks", estate)
    blocks: dict[str, list[tuple[int, str]]] = {}
    sources: dict[str, set[str]] = {}

    for repo, path in SIDES:
        where = estate.where(repo, path)
        try:
            text = estate.read_text(repo, path)
        except E.Missing:
            c.missing(
                "c27.file-missing",
                f"{where} is gone, so the tool hold of {repo} was not compared with anything.",
            )
            continue
        except E.Unavailable as u:
            c.unavailable(f"c27.unavailable:{repo}", str(u))
            continue
        block = _function(text, BLOCK)
        printed = _function(text, SOURCES)
        if block is None or printed is None:
            name = BLOCK if block is None else SOURCES
            c.missing(
                "c27.anchor-missing",
                f"{where} has no function {name}, so the tool hold of {repo} was not compared with anything.",
            )
            continue
        marked = []
        found = False
        for n, line in block:
            normal = _MARKER.sub(_MARKER_NORMAL, line)
            found = found or normal != line
            marked.append((n, normal))
        if not found:
            c.missing(
                "c27.marker-missing",
                f"{where}: {BLOCK} writes no line of the shape "
                f"'# tool-hold: begin (managed by <file>; TOOL_HOLD, invariant <n>)', "
                f"so what a stack renders and removes by is gone.",
            )
            continue
        lists = {m for _, line in printed for m in _PRINTED.findall(line)}
        if not lists:
            c.missing(
                "c27.anchor-missing",
                f"{where}: {SOURCES} prints no identity list this check can read, so two empty lists "
                f"would read as agreement.",
            )
            continue
        blocks[repo] = marked
        sources[repo] = lists

    # Every side that was not read has said why, above.
    if len(blocks) < 2:
        return c

    (one, a), (two, b) = blocks.items()
    place_one, place_two = estate.where(one, SIDES[0][1]), estate.where(two, SIDES[1][1])
    differ = [
        (x, y)
        for x, y in zip(a + [(0, "(the body ends here)")] * len(b), b + [(0, "(the body ends here)")] * len(a))
        if x[1] != y[1]
    ]
    if differ:
        (na, la), (nb, lb) = differ[0]
        c.drift(
            "c27.block-differs",
            f"the tool hold differs between the stacks, at the first of {len(differ)} line(s): an agent "
            f"the two would treat alike is treated differently.",
            [f"  {place_one} line {na}: {la}", f"  {place_two} line {nb}: {lb}"],
        )
    else:
        c.ok("c27.block", f"{len(a)} lines of {BLOCK} agree between {one} and {two}.")
        if not any(line == _FLOOR + " \\" for _, line in a):
            c.drift(
                "c27.no-floor",
                f"{place_one} and {place_two} agree and neither writes `when_no_grant: hold`, so they "
                f"agree on a hold that is not there.",
                [f"  {place_one}", f"  {place_two}"],
            )

    if sources[one] != sources[two]:
        c.drift(
            "c27.sources-differ",
            f"{SOURCES} can print different identity lists, so one body renders two different grants.",
            [f"  {place_one}: {sorted(sources[one])}", f"  {place_two}: {sorted(sources[two])}"],
        )
    else:
        c.ok("c27.sources", f"{SOURCES} prints the same {len(sources[one])} identity lists in {one} and {two}.")
    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
