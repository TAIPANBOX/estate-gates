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

WHY A SHARED ConfigMap's KEYS ARE NOT SUBJECTS

The first version of this check counted every key of `stack-wiring` as
delivered and reported seven findings. Three were wrong, and all three for the
same reason: a shared ConfigMap is not a service's environment.

`TOKENFUSE_CLOUD_EVENTS_PATH` is the clearest. It is a KEY, and the container
receives its value under a different NAME:

    - name: TOKENFUSE_EVENTS_PATH
      valueFrom: { configMapKeyRef: { name: stack-wiring, key: TOKENFUSE_CLOUD_EVENTS_PATH } }

tokenfuse declares and reads `TOKENFUSE_EVENTS_PATH`. Nothing was wrong, and a
check that called it dead would have argued for breaking a working deployment.
`IDRYX_URL` is the same shape, and `TRAILRYX_TRUST_DOMAIN` is a third: stack-k8s
interpolates it into a `--trust-domain` argument in a CronJob it writes itself,
and trailryx's own suite deliberately keeps it OUT of its manifest, saying so in
as many words. Three repositories were right and the check was wrong.

So the subject is delivery to ONE service: a container's own `env:` entry, a
compose service's own `environment:` mapping, a shell command prefix. A key
that lands in ten containers by `envFrom` and is read by one of them is not a
finding, it is how a shared wiring map works.

That is also the shape the defect this check exists for actually had.
`WARDRYX_DSN` was in the wardryx service's own `environment:` block.

WHEN THE READER IS A FLAG AND NOT THE ENVIRONMENT

Kubernetes expands `$(NAME)` inside a container's `command` and `args` from that
container's own `env`, and the launchers use it deliberately, so that one
ConfigMap key reaches an argument without being written twice:

    args:
      - "-stack-host"
      - "$(TRAILRYX_TRUST_DOMAIN)"
    env:
      - name: TRAILRYX_TRUST_DOMAIN
        valueFrom: { configMapKeyRef: { name: stack-wiring, key: TRAILRYX_TRUST_DOMAIN } }

The variable really is in that container's own `env`, so it is a subject by the
rule above, and the process really does read it, as `-stack-host`. Asking
whether any repository declares an ENVIRONMENT variable of that name is then the
wrong question, and it has no right answer: the reading repository declares a
FLAG, because a flag is what its binary defines.

The prose above already recorded this shape once, about
`TRAILRYX_TRUST_DOMAIN`, and called the check wrong for firing on it. It came
back on 2026-09-01 when the finops plane put the same value in a container's own
`env` block rather than in a CronJob's, which is the form this check does watch.

So a subject whose value is substituted into an argument is answered by the
FLAG it lands on, and BOTH questions are asked: a repository may declare the
environment name, or the flag, and either is a reader. Asking only the flag
would drop the case where a process genuinely reads the variable as well.

**This narrows nothing.** A variable substituted into a flag NOBODY declares is
still a finding, and that is not hypothetical: `COSTCREW_CEILING` reached
`costcrew-run`'s `-ceiling`, the flag existed, and costcrew's manifest declared
no flags for that binary at all. The `-live` run refuses to start without it, so
the one figure between a crew of agents and a provider account had no declared
reader anywhere in the estate. That is the finding this change keeps and the
false pair it drops.

THE LIMIT, AND IT IS A REAL ONE

A variable delivered by a form not listed below is invisible here, and nothing
would say so. The mitigation is that the forms are read from the launchers
rather than imagined, and the narrowing above cost coverage on purpose: three
false findings buy a check somebody still reads at the tenth run.

The substitution reader is read the same narrow way: a `$(NAME)` is attributed
to a flag only when a flag token immediately precedes it, as the next list item
or on the same line. Anything looser would let any nearby hyphenated word answer
for a variable, which is how a `why` field nearly became a place findings could
be dismissed by accident. Where no flag precedes it, nothing is attributed and
the subject is judged exactly as before.

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

#: The forms by which a launcher hands a variable to ONE service. Read off the
#: launchers themselves, not invented here.
DELIVERY = [
    # k8s block env entry:      - name: WARDRYX_KEYS
    (re.compile(r"^\s*-\s*name:\s*([A-Z][A-Z0-9_]+)\s*$", re.M), "a container env entry"),
    # k8s flow env entry:       - { name: TOKENFUSE_ADDR, value: "..." }
    (re.compile(r"\{\s*name:\s*([A-Z][A-Z0-9_]+)\s*,", re.M), "a container env entry"),
    # shell command prefix:     WARDRYX_KEYS="" \
    (re.compile(r"^\s*([A-Z][A-Z0-9_]+)=\S.*\\\s*$", re.M), "a shell command prefix"),
]

#: A compose service's own `environment:` mapping, which is the fourth form and
#: needs the block's indentation rather than a single line to recognise.
_ENVIRONMENT = re.compile(r"^(\s*)environment:\s*$", re.M)
_ENV_KEY = re.compile(r"^(\s*)([A-Z][A-Z0-9_]+):")


def compose_environment(text: str) -> set[str]:
    """Keys under a service's `environment:`, and nothing else in the file."""
    out: set[str] = set()
    inside = 0
    for line in text.splitlines():
        opened = _ENVIRONMENT.match(line)
        if opened:
            inside = len(opened.group(1)) + 1
            continue
        if not inside:
            continue
        key = _ENV_KEY.match(line)
        if key and len(key.group(1)) >= inside:
            out.add(key.group(2))
            continue
        if line.strip() and not line.startswith(" " * inside):
            inside = 0
    return out


_COMMENT = re.compile(r"(^|\s)#.*$", re.M)


def strip_comments(text: str) -> str:
    """Prose about a variable is not a delivery of it."""
    return _COMMENT.sub("", text)


def declarations(estate: E.Estate) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]], list[str], list[str]]:
    """Every env name and flag any repository declares, who declared it, and what could not be read.

    `unreachable` is kept apart from `unreadable` on purpose. A repository this
    run could not fetch makes the answer INCOMPLETE, which is a different
    verdict from an answer that is genuinely empty, and collapsing the two is
    how a partial run comes to look like a finding.
    """
    names: dict[str, set[str]] = {}
    flags: dict[str, set[str]] = {}
    accounted: dict[str, set[str]] = {}
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
        for name in flag_names(doc):
            flags.setdefault(name, set()).add(repo)
        for name in named_in_a_declared_reason(doc):
            accounted.setdefault(name, set()).add(repo)
    return names, flags, accounted, unreadable, unreachable


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


def flag_names(node) -> set[str]:
    """Every key under any `flags` block, at any depth of the manifest.

    The mirror of `env_names`. A repository configured by flags rather than by
    the environment declares them here, proved against its own `flag.String`
    call sites by its own suite, exactly as the env block is.
    """
    out: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "flags" and isinstance(value, dict):
                out.update(value)
            else:
                out |= flag_names(value)
    elif isinstance(node, list):
        for value in node:
            out |= flag_names(value)
    return out


#: `$(NAME)`, which is how Kubernetes reaches a container's own env from its
#: args. The launchers write it in two shapes and only two.
_SUBST = re.compile(r"\$\(([A-Z][A-Z0-9_]+)\)")
#: A flag token, quoted or bare, at the end of what precedes a substitution.
#: Anchored at the end on purpose: a flag three tokens back is not this
#: variable's flag, and guessing one would answer for a finding by accident.
_FLAG_BEFORE = re.compile(
    r"(?:^|[\s\[\{,])[\"\']?(-{1,2}([a-z][a-z0-9-]*))[\"\']?"
    r"(?:[\s,\]\}]*|=)\s*$"
)


def substituted_into_flags(text: str) -> dict[str, set[str]]:
    """Variables whose value is substituted into a command-line flag, and which.

    Two shapes, both read off the launchers rather than imagined:

        - "-stack-host"          a YAML list item, the flag on the line before
        - "$(TRAILRYX_TRUST_DOMAIN)"

        --trust-domain "$(TRAILRYX_TRUST_DOMAIN)"     one line, and the `=` form

    Attribution requires the flag to be the LAST thing before the substitution,
    so a hyphenated word earlier in the file cannot answer for a variable.
    """
    out: dict[str, set[str]] = {}
    for m in _SUBST.finditer(text):
        before = text[max(0, m.start() - 200):m.start()]
        # The previous list item counts as adjacent: strip one line break and
        # the indentation, dash and opening quote of a YAML sequence entry.
        # The quote is not optional to handle: every arg list in this estate is
        # quoted, and without it nothing matched at all.
        candidate = re.sub(r"\n\s*-\s*[\"\']?$", " ", before)
        hit = _FLAG_BEFORE.search(candidate)
        if hit:
            out.setdefault(m.group(1), set()).add(hit.group(2))
    return out


def named_in_a_declared_reason(doc) -> set[str]:
    """Names a manifest's `declared` prose accounts for.

    C15's vocabulary already separates what a repository can prove from what it
    can only state with a reason, and a variable read INDIRECTLY is the second
    kind. genaryx reads `GENARYX_COPILOT_API_KEY_REF=env:<NAME>` and then
    whatever variable that reference points at, so the name is the deployment's
    choice and no check inside genaryx can see it. Its manifest says exactly
    that, under a `why`, and naming `GENARYX_COPILOT_KEY` in the sentence.

    Reading those sentences is the same move C12 makes when it accepts a member
    the record plane's own prose argues belongs in the payload plane: the rule
    is that an ANSWER exists, never which answer it is.
    """
    out: set[str] = set()
    if isinstance(doc, dict):
        for key, value in doc.items():
            if key == "declared" and isinstance(value, dict):
                for entry in value.values():
                    if not isinstance(entry, dict):
                        continue
                    # An entry whose VALUE is exactly a variable name answers
                    # for that name. This is the tight form: a repository saying
                    # "I read this and my own suite cannot prove it" in the one
                    # field that cannot be satisfied by accident. genaryx uses it
                    # for three foreign-prefixed reads whose names its own
                    # prefix-scoped scan structurally cannot see.
                    value = str(entry.get("value", ""))
                    if re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", value):
                        out.add(value)

                    text = f"{value} {entry.get('why', '')}"
                    # And only an entry documenting an environment INDIRECTION can
                    # answer for a name. Without this the rule was any prose
                    # mentioning any uppercase token, which today masks exactly
                    # one finding and tomorrow masks whichever one somebody
                    # happens to name in a sentence. A `why` is written to be
                    # read by a person; it must not become a place a finding
                    # can be dismissed by accident.
                    if "env:" not in text:
                        continue
                    out.update(re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", text))
            else:
                out |= named_in_a_declared_reason(value)
    elif isinstance(doc, list):
        for value in doc:
            out |= named_in_a_declared_reason(value)
    return out


def delivered(estate: E.Estate, repo: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Every variable this launcher hands to a process, where, and any flag it feeds.

    Both come off the same comment-stripped text, so prose showing a
    substitution is no more a delivery than prose naming a variable is.
    """
    where, suffix = LAUNCHERS[repo]
    paths = (
        [p for p in estate.list_files(repo, suffix) if p.startswith(where)]
        if suffix
        else [where]
    )
    out: dict[str, set[str]] = {}
    subst: dict[str, set[str]] = {}
    for path in paths:
        text = strip_comments(estate.read_text(repo, path))
        for pattern, _form in DELIVERY:
            for match in pattern.finditer(text):
                out.setdefault(match.group(1), set()).add(path)
        for name in compose_environment(text):
            out.setdefault(name, set()).add(path)
        for name, flags in substituted_into_flags(text).items():
            subst.setdefault(name, set()).update(flags)
    return out, subst


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C16", "a launcher's environment reaches a reader", estate)

    declared, declared_flags, accounted, unreadable, unreachable = declarations(estate)
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
    feeds: dict[str, set[str]] = {}
    for repo in LAUNCHERS:
        try:
            found, subst = delivered(estate, repo)
        except E.Unavailable as u:
            c.unavailable(f"c16.launcher-unavailable:{repo}", str(u))
            launchers_unreachable = True
            continue
        except E.Missing as m:
            c.missing(f"c16.launcher-unreadable:{repo}", str(m))
            continue
        for name, flags in subst.items():
            feeds.setdefault(name, set()).update(flags)
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
        elif feeds.get(name, set()) & set(declared_flags):
            reached = sorted(feeds[name] & set(declared_flags))
            who = sorted({r for f in reached for r in declared_flags[f]})
            c.ok(
                f"c16.reaches:{name}",
                f"substituted into -{', -'.join(reached)}, declared by {', '.join(who)}",
            )
        elif name in accounted:
            c.ok(
                f"c16.reaches:{name}",
                f"read indirectly, and {', '.join(sorted(accounted[name]))} says so "
                "under a declared reason",
            )
        else:
            c.drift(
                f"c16.no-reader:{name}",
                f"`{name}` is handed to a process and no repository declares reading it",
                [
                    f"Set in {where}.",
                    (f"Its value is substituted into -{', -'.join(sorted(feeds[name]))}, "
                     "and no repository declares that flag either."
                     if feeds.get(name) else
                     "No argument substitutes it either, so a flag is not the reader."),
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
