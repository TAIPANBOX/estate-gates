#!/usr/bin/env python3
"""C26: every `cosign sign` of a container image in an estate workflow carries
both legacy bundle flags.

WHY

`@decided 2026-10-19`, paraphrased: the owner decided that image signatures use
the bundle format that policy-controller reads, which is the legacy one. The
current cosign defaults write a newer bundle and read a signing config that
policy-controller does not read, so an image signed with the defaults is
accepted by nothing in a cluster that verifies it. The two flags that keep the
legacy shape are `--new-bundle-format=false` and `--use-signing-config=false`.
A signing step that drops either one signs an image that no verifier here
reads, and nothing fails at signing time: the failure shows up later, at the
admission controller, as an image that will not run.

WHAT IS READ

Every `.github/workflows/*.yml` and `*.yaml` of every repository estate.json
names. A line that runs `cosign sign` is a sign line. The subcommand must end
where `sign` ends, so `cosign sign-blob` (a file, not an image) and
`cosign attest` (an attestation) are not sign lines and are not judged. A line
that is a YAML comment is not read. The command a sign line starts is read with
its continuation lines (a line ending in a backslash joins the next one), and
both flags must appear in that command, written either as `--flag=false` or as
`--flag false`.

WHAT COUNTS AS A FAILURE

  c26.legacy-flag-missing  a sign line whose command lacks one or both flags;
                           the finding names the repository, the file, the
                           line and the flag that is missing
  c26.no-subjects          no workflow in the estate signs an image, so this
                           gate measured nothing; the repositories that publish
                           images do sign them

LIMITS

The flags are read from the command text. A flag supplied some other way is not
seen. A workflow nobody could read is reported as unavailable, never as signed.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

# `cosign sign` as a whole subcommand. The word must end where `sign` ends, so
# `sign-blob` and `attest` do not match, and a longer word cannot match either.
_SIGN = re.compile(r"(?<![\w.-])cosign\s+sign(?![\w-])")

_FLAGS = (
    ("--new-bundle-format=false", re.compile(r"--new-bundle-format(?:=|\s+)false(?![\w-])")),
    ("--use-signing-config=false", re.compile(r"--use-signing-config(?:=|\s+)false(?![\w-])")),
)


def _command(lines: list[str], start: int) -> str:
    """The sign line, and every line it continues onto through a backslash."""
    parts = [lines[start]]
    i = start
    while lines[i].rstrip().endswith("\\") and i + 1 < len(lines):
        i += 1
        parts.append(lines[i])
    return "\n".join(parts)


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C26", "every cosign sign of a container image carries the legacy bundle flags", estate)
    signs = 0
    unread = 0
    for repo in sorted(estate.repos):
        try:
            files = [
                f
                for f in estate.list_files(repo)
                if f.startswith(".github/workflows/") and (f.endswith(".yml") or f.endswith(".yaml"))
            ]
        except E.Missing:
            continue
        except E.Unavailable as u:
            c.unavailable(f"c26.workflows-unavailable:{repo}", str(u))
            unread += 1
            continue
        for f in files:
            try:
                text = estate.read_text(repo, f)
            except E.Missing:
                # Tracked and gone from the tree: nothing to read here.
                continue
            except E.Unavailable as u:
                c.unavailable(f"c26.workflow-unavailable:{repo}:{f}", str(u))
                unread += 1
                continue
            lines = text.splitlines()
            for n, line in enumerate(lines):
                if line.lstrip().startswith("#") or not _SIGN.search(line):
                    continue
                signs += 1
                where = f"{estate.where(repo, f)} line {n + 1}"
                absent = [name for name, rx in _FLAGS if not rx.search(_command(lines, n))]
                if absent:
                    c.drift(
                        "c26.legacy-flag-missing",
                        f"{repo} signs an image at {where} without {' and '.join(absent)}: the signature is "
                        f"written in a bundle format policy-controller does not read, so the image is refused "
                        f"at admission and nothing fails at signing.",
                        [f"  {where}"],
                    )
                else:
                    c.ok(f"c26.signed:{repo}:{n + 1}", f"{repo}: the cosign sign at {where} carries both legacy flags.")
    if signs == 0 and unread == 0:
        c.missing(
            "c26.no-subjects",
            "no workflow in the estate signs an image with cosign, so this gate measured nothing; "
            "the repositories that publish images do sign them.",
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
