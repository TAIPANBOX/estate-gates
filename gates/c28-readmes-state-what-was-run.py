#!/usr/bin/env python3
"""C28: no public README frames the work as not proven.

WHY THIS EXISTS

@decided 2026-11-27, paraphrased: what was built, modelled or run is stated as
done. A README keeps a claim exactly as true as the run behind it ("measured
on kind", "on a stub provider"), keeps a product limit as a fact about the
product ("the root key is a file"), and reports a run that failed as what
happened. What goes is the framing whose only job is to list what was not
proven. On the day of the decision four public READMEs carried a section
headed NOT PROVEN or Not proven, and four more carried the phrase in prose;
it-rat.com had dropped the same framing that day (its invariant 16).

WHAT IT FLAGS, in each public repository's README.md:

  - a heading that names the framing: "## NOT PROVEN", "## Not proven",
    "## What is not proven yet", "## Unproven", "## Not yet measured";
  - the phrase NOT PROVEN in capitals anywhere, which is the section's marker;
  - the phrases that only ever introduce a gap list: "not yet proven",
    "nobody has established", "stops short of", "has not been run",
    "has not been tested", "has not been measured".

WHAT IT DOES NOT FLAG, on purpose

"not proven" in lower case in a sentence, and "unproven" outside a heading,
because the stack's own protocol says it: a delegation chain is proven or not
proven, `chain_proven`, `deny_if_chain_unproven`. Those name what the product
checks, and a gate that fired on them would be switched off. Whether a
rewritten sentence is still true as worded needs a reader.

WHAT IS READ

Subjects come from estate.json: every repository whose entry records a public
GitHub remote (`github`). A private repository or one with no public remote is
skipped and named. A repository with no README.md is noted, not failed. A
subject that cannot be read is NOT MEASURED (invariant 3).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

HEADING = re.compile(
    r"^#{1,6}\s+.*\b(not\s+(yet\s+)?proven|unproven|not\s+yet\s+(measured|tested|established))\b",
    re.IGNORECASE,
)
PHRASES = re.compile(
    r"NOT PROVEN|not yet proven|nobody has established|stops? short of"
    r"|has not been (?:run|tested|measured)",
)


def scan(text: str) -> list[tuple[int, str]]:
    """(line number, what matched) for every line that frames work as not proven."""
    out: list[tuple[int, str]] = []
    for n, line in enumerate(text.split("\n"), 1):
        m = HEADING.search(line)
        if m:
            out.append((n, "heading: " + line.strip()[:80]))
            continue
        for p in PHRASES.finditer(line):
            out.append((n, p.group(0)))
    return out


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C28", "no public README frames the work as not proven", estate)

    subjects: list[str] = []
    for repo, entry in sorted(estate.repos.items()):
        if entry.get("github"):
            subjects.append(repo)
        elif entry.get("private_remote"):
            c.note(f"skipped {repo}: estate.json records it as PRIVATE, so it is not a public repository.")
        else:
            c.note(f"skipped {repo}: estate.json records no public remote for it.")

    if not subjects:
        c.missing(
            "c28.no-subjects",
            "estate.json records no public repository, so there is no README to read. "
            "This check measured nothing.",
        )
        return c

    found: list[tuple[str, int, str]] = []
    clean: list[str] = []
    for repo in subjects:
        try:
            text = estate.read_text(repo, "README.md")
        except E.Unavailable as u:
            c.unavailable(
                f"c28.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so its README is unmeasured here.",
            )
            continue
        except E.Missing:
            c.note(f"{repo} has no README.md, so there is nothing of it to read here.")
            continue
        hits = scan(text)
        if hits:
            found.extend((repo, n, what) for n, what in hits)
        else:
            clean.append(repo)

    if found:
        c.drift(
            "c28.gap-framing",
            f"{len(found)} line(s) in public READMEs frame the work as not proven.",
            [f"  {estate.where(repo, 'README.md')}:{n}: {what}" for repo, n, what in found[:40]]
            + (["  ..."] if len(found) > 40 else [])
            + [
                "  Fix: state what was run, on what, with what result, or the product",
                "  limit as a fact (a 'Limits' section); a failed run stays as an outcome.",
            ],
        )

    for repo in clean:
        c.ok(f"c28.clean:{repo}", f"{repo}: README.md read, no not-proven framing.")

    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    sys.exit(main())
