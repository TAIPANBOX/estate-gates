#!/usr/bin/env python3
"""C15: what a repository declares it contributes, and who is allowed to say so.

WHY

This repository already holds a declaration of which components exist: the
`runs` field in `estate.json`, added 2026-08-27, and invariant 18 says of it,
in as many words, that nothing reads a repository to confirm it. C5 asks the
coverage question in both directions and neither direction touches a
repository's source.

That gap cannot be closed from here, and the reason is structural rather than a
matter of effort. The only thing that knows which binaries a repository builds
is the repository. A component that was FORGOTTEN is therefore invisible from
outside by construction: `runs: []` is a valid answer, a common one, and no
central file can contradict it. vouchryx was installable by nothing for
nineteen hours on 2026-08-26 for exactly that reason.

Nor can the checks that matter most be done from here. What separates vouchryx,
which exits 2 without any of three variables, from wardryx, which starts
happily with an empty environment and installs a built-in `devkey` admin key,
is invisible to every source-reading check and obvious to one that STARTS the
binary. This repository has no Go toolchain, no Rust one and no Python one, and
building twenty-two repositories in its CI is a matrix it does not have.

SO THE DIVISION IS: the repository declares and proves, this one reads across.

Each component repository may carry `components.json` at its root. Everything
under a component's `checked` key is asserted by that repository's own suite,
in its own CI, which has the toolchain. Everything under `declared` is a
statement nobody can verify and must carry its own `why`.

WHAT THIS CHECK OWNS

Three things, and it is deliberately modest about them:

1. The manifests agree with `estate.json`. A repository that declares component
   names its own registry entry does not list, or the reverse, is two files
   disagreeing about one fact, which is this repository's entire subject.
2. A `declared` entry with no `why` is refused. A claim wearing the costume of
   a decision is what the two-bucket split exists to prevent, and the producing
   repo's own test enforces it there; this enforces it for every repo at once,
   so a repository that drops its test does not quietly drop the rule.
3. The one comparison a single repository could never make: the health path a
   component declares, against the path each deployment actually polls. Those
   are two facts in two repositories and nothing compared them until now.

WHAT IT DOES NOT DO

It does not read source. It cannot tell a manifest that is complete from one
that is missing a component, which is the whole reason the proving happens in
the component's own repository rather than here.

ADOPTION IS INCREMENTAL AND A REPOSITORY WITHOUT ONE IS NOT A FAILURE. It is
reported as a count, not as drift. What IS a failure is finding none at all,
because then this check is reporting agreement about nothing.

The count is deliberately not written here. This line said twenty-one of
twenty-two had no manifest, which was true for one day: the sweep of
2026-08-28 took it to nineteen of twenty-two carrying one, and the sentence
stayed. A number in a docstring is a claim with no owner, and this repository
exists to find exactly that shape somewhere else.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

MANIFEST = "components.json"
KNOWN_SCHEMA = "taipanbox.dev/components/v1"

# Where each deployment says which path it polls for a component's health.
#
# One entry per deployment, and the anchor is declared beside the reason it is
# that shape, for the same reason C5's are: the same fact is a shell function
# call in one repo and a manifest field in another, and there is no parser that
# reads both by accident.
PROBES = {
    # stack-up: `wait_health <name> <port> <pid> [path]`, path defaulting to
    # /healthz. The name is the component's local name.
    "stack-up": ("up.sh", re.compile(r"wait_health\s+(\S+)\s+\S+\s+\S+\s+\"?([/\w.\-]+)\"?")),
}


def load_manifest(estate: E.Estate, repo: str) -> dict | None:
    """The manifest, or None when this repository has not adopted one."""
    if not estate.exists(repo, MANIFEST):
        return None
    raw = estate.read_text(repo, MANIFEST)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise E.Missing(f"{repo}:{MANIFEST} is not JSON: {exc}") from None


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C15", "a declaration a repository proves, read across the estate", estate)

    found: dict[str, dict] = {}
    unread: list[str] = []
    readable = 0
    for repo in sorted(estate.repos):
        try:
            m = load_manifest(estate, repo)
            readable += 1
        except E.Unavailable as u:
            unread.append(f"{repo}: {u}")
            continue
        except E.Missing as m_err:
            c.missing("c15.manifest-unreadable", str(m_err))
            continue
        if m is not None:
            found[repo] = m

    # A repository nothing could read is not a repository without a manifest,
    # and the difference decides the runner's exit code. On an estate where
    # every checkout is missing, saying "not one carries a manifest" would be a
    # statement about content drawn from an absence of access.
    if readable == 0:
        for line in unread:
            c.unavailable("c15.repo-unavailable", line)
        c.unavailable(
            "c15.nothing-readable",
            f"not one of the {len(estate.repos)} repositories could be read, so "
            f"whether any carries {MANIFEST} is unknown rather than answered.",
        )
        return c

    if not found:
        c.missing(
            "c15.no-manifest-anywhere",
            f"not one repository in the estate carries {MANIFEST}, so this check "
            f"compared nothing. It is not agreement.",
            [
                "The first one is TAIPANBOX/vouchryx. Until a second exists this",
                "check has one subject, and it says so rather than reporting a",
                "clean run over an empty set.",
            ],
        )
        return c

    c.ok(
        "c15.manifests-read",
        f"{len(found)} of {len(estate.repos)} repositories carry {MANIFEST}: "
        f"{', '.join(sorted(found))}. Adoption is incremental and the rest are "
        f"not a finding.",
    )
    for line in unread:
        c.unavailable("c15.repo-unavailable", line)

    # -- 1. the manifest and the registry name the same components -----------
    for repo, m in sorted(found.items()):
        schema = m.get("schema")
        if schema != KNOWN_SCHEMA:
            c.drift(
                "c15.unknown-schema",
                f"{repo}:{MANIFEST} declares schema `{schema}`, and this check "
                f"knows `{KNOWN_SCHEMA}`. A manifest written to a contract this "
                f"reader does not have is one it would misread rather than refuse.",
            )
            continue

        declared_names = {comp.get("name") for comp in m.get("components", [])}
        declared_names.discard(None)
        if not declared_names:
            c.missing(
                "c15.manifest-declares-nothing",
                f"{repo}:{MANIFEST} lists no component, so there was nothing to "
                f"compare against its registry entry.",
            )
            continue

        # A repository's `runs` names only what a DEPLOYMENT installs. A
        # manifest names everything the repository builds, tools included, and
        # the two are deliberately different sets: vouchryx-demo is a component
        # of the repository and not of any stack. So the rule is containment in
        # one direction only, and the direction is the one that catches drift:
        # every name a deployment can install must be a component its own
        # repository admits building.
        runs = set(estate.repos[repo].get("runs", []))
        missing_from_manifest = sorted(runs - declared_names)
        if missing_from_manifest:
            c.drift(
                "c15.registry-names-what-the-repo-does-not",
                f"estate.json says {repo} contributes "
                f"{', '.join('`' + n + '`' for n in missing_from_manifest)}, and "
                f"its own {MANIFEST} declares no such component.",
                [
                    # Not estate.where(): this repository does not list itself
                    # in its own registry, and asking for its path raises.
                    "  registry: " + str(E.REPO_ROOT / "estate.json"),
                    "  manifest: " + estate.where(repo, MANIFEST),
                    "The repository is the one that knows what it builds, so this",
                    "is the registry claiming something its subject denies.",
                ],
            )
        else:
            c.ok(
                "c15.registry-agrees",
                f"{repo}: every component estate.json says it contributes is one "
                f"its own manifest declares.",
            )

    # -- 2. a declared entry carries its reason ------------------------------
    for repo, m in sorted(found.items()):
        bad = []
        for comp in m.get("components", []):
            for key, body in (comp.get("declared") or {}).items():
                if not isinstance(body, dict) or not str(body.get("why", "")).strip():
                    bad.append(f"{comp.get('name')}.{key}")
        if bad:
            c.drift(
                "c15.declared-without-a-reason",
                f"{repo}:{MANIFEST} carries {len(bad)} declared entr(y/ies) with no "
                f"`why`: {', '.join(bad)}.",
                [
                    "`declared` is the bucket nothing can verify. An entry there",
                    "without a reason is a claim wearing the costume of a decision,",
                    "which is the failure the two-bucket split exists to prevent.",
                ],
            )
        else:
            c.ok(
                "c15.declared-carries-reasons",
                f"{repo}: every declared entry states why nothing can check it.",
            )

    # -- 3. the comparison no single repository could make -------------------
    #
    # A component declares the health path it serves. A deployment polls one.
    # Both are facts, they live in different repositories, and until this check
    # existed nothing put them side by side.
    probes: dict[str, dict[str, str]] = {}
    for dep, (rel, pattern) in PROBES.items():
        try:
            text = estate.read_text(dep, rel)
        except (E.Unavailable, E.Missing) as exc:
            c.missing(
                "c15.probe-unreadable",
                f"{dep}:{rel} could not be read ({exc}), so the health paths it "
                f"polls were compared against nothing.",
            )
            continue
        hits = pattern.findall(text)
        if not hits:
            c.missing(
                "c15.probe-anchor-matched-nothing",
                f"{dep}:{rel}: the anchor for what it polls matched no line, so "
                f"this deployment's probes were not read. An anchor that matches "
                f"nothing is a finding, not a clean comparison.",
            )
            continue
        probes[dep] = {name: path for name, path in hits}

    for repo, m in sorted(found.items()):
        for comp in m.get("components", []):
            declared_path = (comp.get("checked") or {}).get("health_path")
            if not declared_path:
                continue
            name = comp.get("name")
            for dep, table in sorted(probes.items()):
                polled = table.get(name)
                if polled is None:
                    continue
                # A `declared` entry naming the polled path IS the reason,
                # and it lives with the component rather than in this
                # repository's expectations file on purpose: the fact is the
                # component's, and a reason kept somewhere else goes stale
                # separately from the thing it explains.
                excused = None
                for key, body in (comp.get("declared") or {}).items():
                    if isinstance(body, dict) and body.get("value") == polled:
                        excused = (key, str(body.get("why", "")))
                        break
                if excused is not None:
                    c.ok(
                        "c15.probe-is-a-recorded-decision",
                        f"{dep} polls {name} at `{polled}` rather than its declared "
                        f"health path `{declared_path}`, and {repo} says why under "
                        f"`declared.{excused[0]}`: {excused[1][:160]}",
                    )
                elif polled == declared_path:
                    c.ok(
                        "c15.probe-agrees",
                        f"{dep} polls {name} at `{polled}`, which is the path its "
                        f"repository declares.",
                    )
                else:
                    c.drift(
                        "c15.probe-disagrees",
                        f"{dep} polls {name} at `{polled}` and {repo} declares its "
                        f"health path as `{declared_path}`.",
                        [
                            "  deployment: " + estate.where(dep, PROBES[dep][0]),
                            "  manifest:   " + estate.where(repo, MANIFEST),
                            "Not automatically a defect: a launcher may deliberately",
                            "probe something that proves more than a health endpoint",
                            "does. If it is deliberate, the manifest's `declared`",
                            "bucket is where the reason goes, and this check then",
                            "reads a decision instead of a disagreement.",
                        ],
                    )

    _nothing_installs_it(c, estate, found)

    return c


# The classes a manifest may put on a component, and what each one PROMISES
# about deployments. This is the whole reason `dev-tool` exists: without a way
# to say "nothing should install this", the check below would report seven right
# answers in trailryx alone and be switched off before it reached a real one.
RUNS_SOMEWHERE = {"service", "daemon"}
RUNS_NOWHERE = {"dev-tool"}
# `tool` is neither. Some are installed by a launcher (verdryx, engram-mcp) and
# some are a command a person types (taipan, engram, the six costcrew tools) or
# are distributed by somebody else's registry entirely (the Terraform provider,
# `pip install engdbram`). A tool nobody installs is not news, so it is not
# judged here rather than being judged wrongly.


def _installed_by_launchers(found: dict[str, dict]) -> tuple[set[str], list[str]]:
    """Everything the launcher manifests say they bring up, and who said so."""
    installed: set[str] = set()
    launchers: list[str] = []
    for repo, m in sorted(found.items()):
        components = m.get("components") or []
        if m.get("kind") != "launcher" and not any(
            comp.get("class") == "launcher" for comp in components
        ):
            continue
        launchers.append(repo)
        for comp in components:
            checked = comp.get("checked") or {}
            for key in ("installs", "installs_services", "installs_python_tools"):
                installed.update(checked.get(key) or [])
            scheduled = checked.get("schedules_routines")
            if isinstance(scheduled, dict):
                # stack-k8s names its CronJobs locally and maps each to the
                # routine the estate means. Both sides count as installed: the
                # local name is what exists there, the routine is what it is.
                installed.update(scheduled)
                installed.update(scheduled.values())
            else:
                installed.update(scheduled or [])
    return installed, launchers


def _nothing_installs_it(c: E.Check, estate: E.Estate, found: dict[str, dict]) -> None:
    """A service or daemon that no launcher in this estate can install.

    THIS IS THE QUESTION THE WHOLE PER-REPO DECLARATION WAS FOR, and until every
    repository carried one it could not be asked: a central registry cannot see a
    component nobody told it about, which is invariant 18's own admission.

    It was asked by hand on 2026-08-28 and found `tokenfuse-cluster`: a
    raft-replicated budget ledger, added 2026-07-02, with three integration
    suites and its own CI job, installable by nothing for fifty-seven days. The
    point of this function is that the next one is found by a run rather than by
    somebody looking.

    A `declared` entry that says so IS the answer, the same way it is for a probe
    path above: the fact belongs to the component, and a reason kept in this
    repository would go stale separately from the thing it explains.
    """
    installed, launchers = _installed_by_launchers(found)
    if not launchers:
        c.missing(
            "c15.no-launcher-manifest",
            "no repository carries a launcher manifest, so whether anything can "
            "install a given component is unknown rather than answered. This "
            "measured NOTHING.",
        )
        return
    if not installed:
        c.missing(
            "c15.launchers-install-nothing",
            f"the launcher manifests ({', '.join(launchers)}) name nothing they "
            f"install, so every component would read as an orphan. That is a "
            f"broken reading, not a finding about the estate.",
        )
        return

    judged = 0
    for repo, m in sorted(found.items()):
        for comp in m.get("components") or []:
            name, klass = comp.get("name"), comp.get("class")
            if klass not in RUNS_SOMEWHERE:
                continue
            judged += 1
            if name in installed:
                continue
            excuse = None
            for key, body in (comp.get("declared") or {}).items():
                if isinstance(body, dict) and (
                    "install" in key or "install" in str(body.get("value", ""))
                ):
                    excuse = (key, str(body.get("why", "")))
                    break
            if excuse is not None:
                c.ok(
                    "c15.uninstallable-is-a-recorded-decision",
                    f"{repo} declares `{name}` as a {klass} and no launcher installs "
                    f"it, and {repo} says why under `declared.{excuse[0]}`: "
                    f"{excuse[1][:200]}",
                )
                continue
            c.drift(
                "c15.nothing-installs-it",
                f"{repo} declares `{name}` as a {klass} and not one of the "
                f"{len(launchers)} launchers installs it.",
                [
                    "  manifest:  " + estate.where(repo, MANIFEST),
                    "  launchers: " + ", ".join(launchers),
                    "A service exists to be run by something. If nothing can install",
                    "it, either a launcher is missing an entry or the component is",
                    "built, tested and reachable by nobody, which is what",
                    "tokenfuse-cluster was for fifty-seven days.",
                    "If it is deliberate, the component's own `declared` bucket is",
                    "where the reason goes, and this check then reads a decision",
                    "instead of a finding. `dev-tool` is the class for something",
                    "nothing should ever install.",
                ],
            )

    if judged == 0:
        c.missing(
            "c15.no-service-to-judge",
            f"not one component across {len(found)} manifest(s) is a "
            f"{' or '.join(sorted(RUNS_SOMEWHERE))}, so this measured NOTHING "
            f"about what can be installed.",
        )
        return

    c.ok(
        "c15.every-service-has-an-installer",
        f"{judged} component(s) of class {' or '.join(sorted(RUNS_SOMEWHERE))} "
        f"judged against what {len(launchers)} launcher(s) install.",
    )
