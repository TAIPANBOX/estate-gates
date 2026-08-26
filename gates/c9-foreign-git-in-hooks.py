#!/usr/bin/env python3
"""C9: a git command aimed at another repository clears the hook's environment.

WHY

git runs a hook with `GIT_DIR` set, pointing at the repository being pushed.
`git -C <somewhere else>` changes the working DIRECTORY and does not clear that
variable, so the command reads the other repository's working tree against
THIS repository's index and object database.

Found on 2026-08-26 in trailryx, in a check that asks whether the local
advisory database has untracked files. From a terminal it answered nothing,
correctly. From the pre-push hook it answered 1221 lines, every entry of the
database, and refused the push. Deterministic, and invisible from a terminal,
which is why three sessions in a row retried instead of looking at the
environment: the failure only exists in a context nobody debugs from.

WHY IT IS WORTH A CROSS-REPO CHECK RATHER THAN A NOTE IN ONE README

Two things make it estate-shaped.

The blast radius is not the same in every script, and the worse shape is
quieter than the one that was found. A `status` under the wrong index reports
files that are not untracked, which is loud. A `show <ref>:<path>` under the
wrong object database resolves the ref in the WRONG REPOSITORY, and where the
two repositories hold a file at the same path, it succeeds and returns the
wrong content. A check comparing a vendored copy against its canonical
original would then compare the copy against itself and report agreement.

And the remediation these scripts print is `git -C <path> clean -fd`. In a
terminal it tidies nothing, because nothing is untracked. In the environment
where the message actually appears, it deletes the other repository's working
tree.

WHAT IT LOOKS FOR

A `git` invocation carrying `-C` or `--git-dir` in a file under `scripts/` or
`.githooks/`, in a repository the estate registry knows. The target has to sit
before the subcommand, which is where git requires it, and that single rule is
what keeps `git archive HEAD | tar -x -C "$dir"` out of the answer. Five
repositories write exactly that line, and a check that matched `git` and `-C`
anywhere on a line would have reported all five and been deleted by whoever
read the first finding.

An invocation is fine when it clears the three variables git exports into a
hook, `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C ...`, or when
its target is this repository, which is what `-C "$(git rev-parse
--show-toplevel)"` says.

WHAT IT DOES NOT CATCH, AND THE FIRST ONE IS THE LARGEST

**Only shell, and only under two directories.** A Go, Rust or Python program
that shells out to git with a foreign target is invisible here. So is a script
anywhere else in a repository. The two directories are where the estate's
hook-reachable scripts live, and widening the scan without widening the parser
would trade a real answer for a broad one.

**It does not know whether a hook can reach the script.** Neither of the sites
this check reports today is reachable from a hook, because neither repository
installs one. That is a property of those repositories on this date and not of
the code, and the fix costs one word, so the check reports them anyway. A
script that is safe because of what does not call it yet is one line of
somebody else's convenience away from being unsafe.

**This suite's own Python does the same thing and is out of scope.**
`_estate.list_files` runs `git -C <sibling>` to enumerate a repository, without
clearing anything. It is safe today for the reason the check refuses to rely on
elsewhere: estate-gates installs no hook, so nothing here ever runs with GIT_DIR
set. That is a property of this repository on this date, said here rather than
left for somebody to find and read as an exemption.

**A wrapper is invisible, and correctly so.** trailryx's fix defines a function
that clears the environment and calls plain `git`, then calls the wrapper with
`-C`. The wrapper's own `git` carries no target, so nothing here matches, which
is the right answer for the wrong-looking reason: the check sees git
invocations, not intent.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

#: Directories whose scripts a hook can reach. `.githooks` is the hook itself;
#: `scripts` is what the hooks in this estate call.
SCANNED_DIRS = ("scripts", ".githooks")

#: A `git` invocation whose TARGET comes before the subcommand, which is the
#: only place git accepts one. Leading global flags are allowed, so
#: `git --no-pager -C x` matches. A flag that takes a separate value, as in
#: `git -c key=value -C x`, stops the match and is missed; that form appears
#: nowhere in the estate and the limit is stated rather than papered over.
#:
#: The target is captured as a QUOTED string or a bare word, in that order,
#: because the self-naming form is `git -C "$(git rev-parse --show-toplevel)"`
#: and a bare-word capture stops at the first space inside it. The first
#: version of this check did exactly that and reported the fixture's own
#: self-targeted call as foreign, which is how the case earned its place in
#: the fixture rather than in a comment.
_TARGET = r'(?:"[^"]*"|\'[^\']*\'|\S+)'
GIT_TARGETED = re.compile(
    r"\bgit(?:\s+-\S+)*\s+(?:-C\s+(" + _TARGET + r")|--git-dir[= ]\s*(" + _TARGET + r"))"
)

#: The three variables git exports into a hook. Clearing GIT_DIR alone is
#: enough for the fault that was found, and the check asks for all three
#: because a guard against one member of a family invites the next.
CLEARED = re.compile(r"env(?:\s+-u\s+\S+)*\s+-u\s+GIT_DIR\b")

#: A target that names this repository rather than another one.
SELF_TARGET = re.compile(r"rev-parse\s+--show-toplevel|^\"?\.\"?$")

#: Where a match is text rather than a command.
QUOTED = re.compile(r"\b(echo|printf)\b")


def findings_for(text: str) -> list[tuple[int, str]]:
    """Every foreign-target git invocation in one script, with its line number.

    Skips a line whose match sits inside an `echo` or `printf`, because these
    scripts print the remediation as prose and a check that flagged its own
    advice would teach people to stop writing the advice down.
    """
    out: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = GIT_TARGETED.search(line)
        if not m:
            continue
        if QUOTED.search(line[: m.start()]):
            continue
        target = m.group(1) or m.group(2)
        if SELF_TARGET.search(target) or SELF_TARGET.search(line[m.start() : m.end()]):
            continue
        if CLEARED.search(line):
            continue
        out.append((n, stripped))
    return out


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C9", "a git command aimed elsewhere clears the hook's environment", estate)

    scanned = 0
    repos_read = 0
    findings: list[tuple[str, str, int, str]] = []

    for repo in sorted(estate.repos):
        try:
            estate.dir_of(repo)
        except E.Unavailable as u:
            c.unavailable(
                f"c9.repo-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}), so its scripts "
                f"were not scanned and anything they do with another repository is "
                f"unmeasured here.",
            )
            continue
        repos_read += 1
        try:
            tracked = estate.list_files(repo)
        except E.Missing as m:
            # Present and unreadable in this run, which is what `unavailable`
            # means here and is why this is not a drift: the estate has not
            # disagreed with itself, this run failed to look. It also keeps a
            # FAIL path out of the gate that the fixture cannot produce, and a
            # path nothing can exercise is a label rather than a check.
            c.unavailable(
                f"c9.repo-unlistable:{repo}",
                f"{repo}: {m}. Its scripts were not scanned, so what they do with "
                f"another repository is unmeasured here.",
            )
            continue
        for path in tracked:
            if not path.startswith(tuple(d + "/" for d in SCANNED_DIRS)):
                continue
            if not path.endswith((".sh", "pre-push", "pre-commit", "commit-msg")):
                continue
            try:
                text = estate.read_text(repo, path)
            except E.Missing:
                continue
            scanned += 1
            for line_no, line in findings_for(text):
                findings.append((repo, path, line_no, line))

    if scanned == 0:
        if repos_read == 0:
            # Nothing was readable, so every repository has already said so as
            # UNAVAILABLE and the run is incomplete rather than drifted. Adding
            # a finding on top would say the estate disagrees with itself when
            # the truth is that nothing looked, which is invariant 3, and it
            # would turn the runner's exit 2 into an exit 1. Caught by the
            # self-test's exit-code cases rather than by review.
            return c
        c.missing(
            "c9.nothing-scanned",
            f"{repos_read} repository(ies) were readable and not one shell script "
            f"was found under {' or '.join(SCANNED_DIRS)}. Either the estate stopped "
            f"keeping its gates there or this check's file filter stopped matching, "
            f"and a scan that read nothing must not report agreement.",
        )
        return c

    c.note(f"read {scanned} shell script(s) across {repos_read} repository(ies).")

    if findings:
        by_repo: dict[str, list[tuple[str, int, str]]] = {}
        for repo, path, line_no, line in findings:
            by_repo.setdefault(repo, []).append((path, line_no, line))
        for repo, rows in sorted(by_repo.items()):
            detail = []
            for path, line_no, line in rows:
                detail.append(f"  {estate.where(repo, path)}:{line_no}")
                detail.append(f"      {line[:96]}")
            detail.append(
                "A hook runs with GIT_DIR set to the repository being pushed, and"
            )
            detail.append(
                "`git -C` does not clear it, so this reads the other repository's"
            )
            detail.append(
                "working tree against this one's index and object database."
            )
            detail.append(
                "Fix: env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C ..."
            )
            c.drift(
                "c9.foreign-git-keeps-the-environment",
                f"{repo}: {len(rows)} git invocation(s) aimed at another repository "
                f"without clearing the variables git exports into a hook.",
                detail,
            )
    else:
        c.ok(
            "c9.foreign-git-clears-the-environment",
            f"no git invocation in the {scanned} script(s) read points at another "
            f"repository while keeping a hook's environment.",
        )

    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
