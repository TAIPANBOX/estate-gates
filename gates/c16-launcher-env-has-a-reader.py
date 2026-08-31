#!/usr/bin/env python3
"""C16: every environment variable a launcher hands to a service is one some repository reads.

WHY THIS IS NOT C5

C5 compares the three launchers against EACH OTHER: they install the same
product, so a routine present in one and absent in another is drift. That
question has no opinion about whether the thing all three agree on is wired to
anything at all. Three launchers can agree perfectly on a variable nobody reads.

This asks the other question, and it is between a launcher and a BINARY rather
than between two launchers.

WHAT IT FOUND WHEN IT WAS WRITTEN

Two live instances, both the same shape, both found on 2026-08-31.

`stack-single/compose.yaml` passed `WARDRYX_DSN`. wardryx reads `WARDRYX_DB`
and has never read the other name. So the launcher generated a correct DSN,
declared `depends_on: policy-db` with `condition: service_healthy`, WAITED for
that database to come up, and then handed the value over under a name the
process ignores. The database was provisioned, waited on, and never used, which
put policy and approvals in memory: a restart dropped every console-written
policy and unfroze the fleet while the console still showed it stopped.

`stack-k8s` sets `TOKENFUSE_CLOUD_EVENTS_PATH` in `stack-wiring` and wires it
into a container with a `configMapKeyRef`. That name appears nowhere in
tokenfuse. The variable its cloud actually reads is
`TOKENFUSE_CLOUD_REPLAY_EVENTS`, and no launcher sets it, so the replay
endpoint reports `configured:false` in every cluster this repository installs.

Neither is a bug inside a repository. Each is a launcher and a binary
disagreeing about a name, which no single-repo gate can see: the launcher's own
gates cannot read the binary, and the binary's gates cannot read the launcher.

WHY A KEY WITH NO READER IS THE QUIET KIND

Nothing is misspelled and nothing errors. The value is correct, the dependency
is healthy, the service starts and answers. A variable nobody reads is not a
typo, it is a wire that was never connected, and every signal around it says
the opposite.

HOW THE SUBJECTS ARE FOUND, AND HOW THE ANSWER IS

Both sides come from the repositories, never from a list in this script.

The ANSWER is every name under an `env` block in any `components.json` in the
estate. Those declarations are not this suite's word for it: each declaring
repository proves its own manifest against its own source, in its own CI, which
has the toolchain this repository does not (see C15 on why that division is
structural).

The SUBJECTS are the names the launchers DELIVER, by the four forms below. A
name is only a subject when its prefix is one some repository declares, so
`POSTGRES_PASSWORD` and `PORT` are not this check's business.

Delivery, not assignment. `install.sh` holds shell variables like
`WARDRYX_ADMIN_SECRET` that are never passed to any process, and flagging those
would bury the real finding. Comments are stripped first, so prose ABOUT a
variable, including the comment recording the `WARDRYX_DSN` fix, is not a
delivery.

THE LIMIT, AND IT IS A REAL ONE

A ConfigMap key counts as delivered without proving some container mounts it
with `envFrom`, and a shell command prefix is recognised by its line
continuation. Both can over-count, and over-counting here produces a finding
that a human dismisses rather than a silence nobody sees, which is the
direction this suite errs in on purpose. What it cannot do is see a variable a
launcher delivers by a form not listed below; that is a false negative, and the
mitigation is that the forms are read from the launchers rather than imagined.

A run that finds no declarations, or no delivered variables, says it measured
nothing and fails. That is not a pass.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

MANIFEST = "components.json"

#: Where each launcher keeps what it hands to a service.
LAUNCHERS = {
    "stack-k8s": ("manifests/", ".yaml"),
    "stack-single": ("compose.yaml", ""),
    "stack-up": ("up.sh", ""),
}

#: The four forms a launcher in this estate uses to hand a variable to a
#: process. Read off the launchers themselves, not invented here.
DELIVERY = [
    # k8s block env entry:      - name: WARDRYX_KEYS
    (re.compile(r"^\s*-\s*name:\s*([A-Z][A-Z0-9_]+)\s*$", re.M), "a container env entry"),
    # k8s flow env entry:       - { name: TOKENFUSE_ADDR, value: "..." }
    (re.compile(r"\{\s*name:\s*([A-Z][A-Z0-9_]+)\s*,", re.M), "a container env entry"),
    # yaml mapping key:         WARDRYX_DB: ${POLICY_DB_DSN}   (compose, ConfigMap)
    (re.compile(r"^\s{2,}([A-Z][A-Z0-9_]+):\s*\S", re.M), "a compose or ConfigMap key"),
    # shell command prefix:     WARDRYX_KEYS="" \
    (re.compile(r"^\s*([A-Z][A-Z0-9_]+)=\S.*\\\s*$", re.M), "a shell command prefix"),
]

_COMMENT = re.compile(r"(^|\s)#.*$", re.M)


def strip_comments(text: str) -> str:
    """Prose about a variable is not a delivery of it."""
    return _COMMENT.sub("", text)


def declarations(estate: E.Estate) -> tuple[dict[str, set[str]], list[str], list[str]]:
    """Every env name any repository declares, who declared it, and what could not be read.

    `unreachable` is kept apart from `unreadable` on purpose. A repository this
    run could not fetch makes the answer INCOMPLETE, which is a different
    verdict from an answer that is genuinely empty, and collapsing the two is
    how a partial run comes to look like a finding.
    """
    names: dict[str, set[str]] = {}
    unreadable: list[str] = []
    unreachable: list[str] = []
    for repo in sorted(estate.repos):
        try:
            raw = estate.read_text(repo, MANIFEST)
        except E.Unavailable:
            unreachable.append(repo)
            continue
        except E.Missing:
            continue
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            unreadable.append(repo)
            continue
        for name in env_names(doc):
            names.setdefault(name, set()).add(repo)
    return names, unreadable, unreachable


def env_names(node) -> set[str]:
    """Every key under any `env` block, at any depth of the manifest."""
    out: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "env" and isinstance(value, dict):
                out.update(value)
            else:
                out |= env_names(value)
    elif isinstance(node, list):
        for value in node:
            out |= env_names(value)
    return out


def delivered(estate: E.Estate, repo: str) -> dict[str, set[str]]:
    """Every variable this launcher hands to a process, and where."""
    where, suffix = LAUNCHERS[repo]
    paths = (
        [p for p in estate.list_files(repo, suffix) if p.startswith(where)]
        if suffix
        else [where]
    )
    out: dict[str, set[str]] = {}
    for path in paths:
        text = strip_comments(estate.read_text(repo, path))
        for pattern, _form in DELIVERY:
            for match in pattern.finditer(text):
                out.setdefault(match.group(1), set()).add(path)
    return out


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C16", "a launcher's environment reaches a reader", estate)

    declared, unreadable, unreachable = declarations(estate)
    for repo in unreadable:
        c.missing(
            f"c16.manifest-unreadable:{repo}",
            f"{repo}:{MANIFEST} is not JSON, so what that repository reads "
            "cannot be part of the answer this check compares against",
        )
    if not declared and unreachable:
        c.unavailable(
            "c16.declarations-unavailable",
            f"no declaration was read and {len(unreachable)} repositor(y/ies) could "
            f"not be fetched ({', '.join(unreachable)}), so this run is incomplete "
            "rather than a finding",
        )
        return c
    if not declared:
        c.missing(
            "c16.declarations",
            f"no repository declares an `env` block in {MANIFEST}, so this gate "
            "has nothing to compare a launcher against and measured nothing",
        )
        return c

    prefixes = {name.split("_")[0] for name in declared}
    subjects: dict[str, set[str]] = {}

    launchers_unreachable = False
    for repo in LAUNCHERS:
        try:
            found = delivered(estate, repo)
        except E.Unavailable as u:
            c.unavailable(f"c16.launcher-unavailable:{repo}", str(u))
            launchers_unreachable = True
            continue
        except E.Missing as m:
            c.missing(f"c16.launcher-unreadable:{repo}", str(m))
            continue
        for name, paths in found.items():
            if any(name.startswith(p + "_") for p in prefixes):
                subjects.setdefault(name, set()).update(f"{repo}/{p}" for p in paths)

    if not subjects and launchers_unreachable:
        # Nothing was delivered because nothing could be READ. An incomplete
        # run must not wear a finding's clothes: the runner's exit code is the
        # only thing CI reads, and 2 and 1 mean different things to a human.
        return c
    if not subjects:
        c.missing(
            "c16.nothing-delivered",
            "no launcher hands any service-prefixed variable to a process, which "
            f"cannot be true of {len(LAUNCHERS)} launchers that install this "
            "estate: the delivery forms this gate knows have stopped matching",
        )
        return c

    for name in sorted(subjects):
        where = ", ".join(sorted(subjects[name]))
        if name in declared:
            c.ok(f"c16.reaches:{name}", f"read by {', '.join(sorted(declared[name]))}")
        else:
            c.drift(
                f"c16.no-reader:{name}",
                f"`{name}` is handed to a process and no repository declares reading it",
                [
                    f"Set in {where}.",
                    "Either the launcher is wiring nothing, which is silent because "
                    "the value is correct and the service starts and answers, or a "
                    "repository reads it and its own components.json does not say so.",
                    "Both are worth a minute. WARDRYX_DSN was the first kind and "
                    "cost a database that was provisioned, waited on and never used.",
                ],
            )
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    E.add_common_args(parser)
    args = parser.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    raise SystemExit(main())
