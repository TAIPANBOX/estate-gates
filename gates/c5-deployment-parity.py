#!/usr/bin/env python3
"""C5: the three deployments of the same stack, and every difference between
them either written down or red.

WHY

stack-up, stack-single and stack-k8s install the same product three ways. They
disagree today on which governance routines run, on the severity floor the
notifier uses, and on which components come up at all. Some of those
differences are deliberate and good. None of them was written down anywhere a
reader could find, so an operator moving between two of them meets the
difference as a surprise, and nobody can tell a decision from an omission.

THE MECHANISM: AN EXPECTATIONS FILE, NOT A TOLERANCE

This check does not decide which divergences are acceptable. It computes every
divergence from the agreed value, and fails on any one that
`expectations/deployment-parity.json` does not record with a reason. Recording
one is cheap, takes a sentence, and converts an unstated difference into a
decision somebody had to write down and sign a date to.

It fails the other way too. An expectation recorded for a divergence that no
longer exists is also red, because a file of stale allowances is how a gate
becomes a formality. That property is borrowed from bank-in-a-box's selftest,
where a mutation left behind for a deleted check fails the script.

THREE SYNTAXES FOR EVERY FACT

The same setting is a shell variable in one repo, a compose interpolation in
the second and a Kubernetes flow mapping in the third. There is no parser that
reads all three by accident, so every anchor below is declared per deployment,
beside a comment saying what it is anchored on. An anchor that matches nothing
is a FAIL naming the anchor: a deployment this check could not read is not a
deployment that agrees.

WHAT IT DOES NOT CATCH

Values an operator supplies at install time. stack-single's severity floor is
overridable through `ALERT_MIN_SEVERITY` in a generated `.env`; this check
reads the DEFAULT, which is the only thing in the repository. What a given box
is actually running is not a property of the source, and this repository only
reads source.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

DEPLOYMENTS = ["stack-up", "stack-single", "stack-k8s"]


def expectations_path() -> pathlib.Path:
    """Where the recorded divergences live.

    Overridable only so `selftest.py` can point this check at the fixture
    estate's own expectations. Nothing in a normal run sets it.
    """
    override = os.environ.get("ESTATE_GATES_EXPECTATIONS")
    if override:
        return pathlib.Path(override)
    return E.REPO_ROOT / "expectations" / "deployment-parity.json"


# ---------------------------------------------------------------- name maps
#
# Each deployment names the same thing differently. These maps are the one
# place that knowledge lives. A local name absent from a map is a FAIL, not a
# skip: an unmapped routine is one this check silently would not compare.

ROUTINE_KIND = {
    # stack-up (routines.sh ROUTINE_NAMES)
    "focus-export": "focus-export",
    "qryx-trend": "qryx-trend",
    "verdryx-drift": "verdryx-drift",
    "idryx-detect": "idryx-detect",
    "mockryx-drill": "mockryx-drill",
    # trailryx-node events over the shared event directory, sealing what the
    # routines above and the rest of the stack did into an offline-verifiable
    # record. Its own kind rather than one of the five: it governs nothing and
    # produces no finding, it writes down what happened. stack-up runs it last
    # in the hour on purpose, after the one other routine that can still emit
    # an event that day.
    "trailryx-seal": "trailryx-seal",
    # stack-k8s (CronJob metadata.name)
    "crypto-trend": "qryx-trend",
    "identity-sweep": "idryx-detect",
    "quality-drift": "verdryx-drift",
    "drills": "mockryx-drill",
}

SERVICE_KIND = {
    # stack-up (register <name>)
    "gateway": "tokenfuse-gateway",
    "cloud": "tokenfuse-cloud",
    "dashboard": "dashboard",
    "wardryx": "wardryx",
    "idryx": "idryx",
    "heraldyx": "heraldyx",
    # stack-single (compose service keys)
    "tokenfuse-gateway": "tokenfuse-gateway",
    "tokenfuse-cloud": "tokenfuse-cloud",
    "policy-db": "policy-db",
    "console": "console",
    "wg": "wg",
    "caddy": "caddy",
    "init-volumes": "init-volumes",
    # stack-k8s (Deployment / StatefulSet metadata.name)
    "genaryx-console": "console",
    # All three call it `scopyx`, so this maps to itself. Listed anyway,
    # because membership of this dict is what tells the check a name is one it
    # knows: a component absent from here is refused rather than defaulted, so
    # a new plane cannot be silently compared against nothing.
    "scopyx": "scopyx",
    # stack-single ships the same plane twice, under two compose profiles that
    # its own file says are mutually exclusive: `egress` runs the 15 MB image
    # and `egress-browser` runs the one with Chromium in it, and both bind the
    # network alias `scopyx`, because the rest of the box reaches it by that
    # name whichever profile the operator chose.
    #
    # So this is one component with two backends, not two components, and the
    # kind is `scopyx`. The services comparison folds a deployment's names into
    # a SET, so collapsing both onto one kind cannot double-count: a box running
    # either profile brings up scopyx, which is exactly what the other two
    # deployments do.
    #
    # What this deliberately does NOT do is compare the two backends. Whether a
    # box renders JavaScript is a property of the profile an operator picks at
    # install time, and this check reads source rather than a running box (see
    # the module docstring's last paragraph).
    "scopyx-browser": "scopyx",
}


# --------------------------------------------------------------- extractors


def _one_value(hits: list[tuple[str, str]], name: str, where: str) -> str:
    """One value, or a loud failure. Two different values in one deployment is
    a finding about that deployment before it is one about the estate."""
    if not hits:
        raise E.Missing(
            f"{where}: no assignment of {name} matched any shape this check "
            f"knows. The setting is either gone or written a new way, and both "
            f"need a person"
        )
    values = {v for _, v in hits}
    if len(values) > 1:
        sites = "; ".join(f"{f} -> {v}" for f, v in hits)
        raise E.Missing(
            f"{where}: {name} is set to more than one value in the same "
            f"deployment ({sites}). Nothing here can say which one the box uses"
        )
    return hits[0][1]


# HERALDYX_MIN_SEVERITY, in the four shapes the estate writes it in.
_SEV_SHAPES = [
    # shell: HERALDYX_MIN_SEVERITY="medium" \
    re.compile(r"HERALDYX_MIN_SEVERITY\s*=\s*\"?([a-z]+)\"?"),
    # compose: HERALDYX_MIN_SEVERITY: ${ALERT_MIN_SEVERITY:-high}
    re.compile(r"HERALDYX_MIN_SEVERITY\s*:\s*\$\{[A-Z_]+:-([a-z]+)\}"),
    # compose, plain: HERALDYX_MIN_SEVERITY: high
    re.compile(r"HERALDYX_MIN_SEVERITY\s*:\s*\"?([a-z]+)\"?\s*$"),
    # k8s flow mapping: - { name: HERALDYX_MIN_SEVERITY, value: "high" }
    re.compile(r"name:\s*HERALDYX_MIN_SEVERITY\s*,\s*value:\s*\"?([a-z]+)\"?"),
    # k8s block form: - name: HERALDYX_MIN_SEVERITY \n value: "high"
    re.compile(r"name:\s*HERALDYX_MIN_SEVERITY\s*\n\s*value:\s*\"?([a-z]+)\"?"),
]


def min_severity(estate: E.Estate, repo: str, files: list[str]) -> str:
    hits: list[tuple[str, str]] = []
    unrecognised: list[str] = []
    for f in files:
        try:
            text = estate.read_text(repo, f)
        except E.Missing:
            raise E.Missing(
                f"{repo}:{f} is where this check reads HERALDYX_MIN_SEVERITY and "
                f"it is not there"
            ) from None
        if "HERALDYX_MIN_SEVERITY" not in text:
            continue
        # The block form spans two lines, so try the whole text first.
        for shape in _SEV_SHAPES[3:]:
            for m in shape.finditer(text):
                hits.append((f, m.group(1)))
        for line in text.splitlines():
            stripped = line.strip()
            if "HERALDYX_MIN_SEVERITY" not in stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            for shape in _SEV_SHAPES:
                m = shape.search(stripped)
                if m:
                    hits.append((f, m.group(1)))
                    break
            else:
                unrecognised.append(f"{f}: {stripped}")
    if unrecognised and not hits:
        raise E.Missing(
            f"{repo}: HERALDYX_MIN_SEVERITY appears in "
            f"{len(unrecognised)} place(s) and no shape this check knows "
            f"matched any of them: {unrecognised[0]}"
        )
    # De-duplicate: the whole-text pass and the per-line pass can both match.
    hits = sorted(set(hits))
    return _one_value(hits, "HERALDYX_MIN_SEVERITY", repo)


def sh_array(text: str, name: str, where: str) -> list[str]:
    m = re.search(re.escape(name) + r"=\(([^)]*)\)", text)
    if not m:
        raise E.Missing(f"{where}: no `{name}=( ... )` array matched")
    items = m.group(1).split()
    if not items:
        raise E.Missing(f"{where}: `{name}` is an empty array")
    return items


def yaml_docs(text: str) -> list[str]:
    """Split a multi-document YAML file. Line-oriented on purpose: this is not
    a YAML parser and does not pretend to be one."""
    docs, current = [], []
    for line in text.splitlines():
        if line.strip() == "---":
            docs.append("\n".join(current))
            current = []
        else:
            current.append(line)
    docs.append("\n".join(current))
    return [d for d in docs if d.strip()]


_KIND = re.compile(r"^kind:\s*(\w+)\s*$", re.MULTILINE)
_META_BLOCK = re.compile(r"^metadata:\s*\n(?:\s+\w+:.*\n)*?\s+name:\s*([\w.-]+)", re.MULTILINE)
_META_FLOW = re.compile(r"^metadata:\s*\{[^}]*\bname:\s*([\w.-]+)", re.MULTILINE)


# The kinds this check reads. A document of any other kind is skipped BY KIND,
# which is a decision recorded here, not a parse that gave up: kustomization.yaml
# declares `kind: Kustomization` and has no metadata name, and demanding one
# would make the check red about a file it does not care about.
K8S_KINDS = ("CronJob", "Deployment", "StatefulSet", "DaemonSet", "Service")


def k8s_objects(text: str, where: str) -> list[tuple[str, str, str]]:
    """(kind, name, document body) for every object this check reads."""
    out = []
    for doc in yaml_docs(text):
        k = _KIND.search(doc)
        if not k or k.group(1) not in K8S_KINDS:
            continue
        n = _META_BLOCK.search(doc) or _META_FLOW.search(doc)
        if not n:
            raise E.Missing(
                f"{where}: a `kind: {k.group(1)}` document has no metadata name "
                f"this check could read, in either block or flow form"
            )
        out.append((k.group(1), n.group(1), doc))
    return out


# ------------------------------------------------- per-deployment observers


def observe_stack_up(estate: E.Estate) -> dict:
    routines_sh = estate.read_text("stack-up", "routines.sh")
    up_sh = estate.read_text("stack-up", "up.sh")

    names = sh_array(routines_sh, "ROUTINE_NAMES", "stack-up/routines.sh")
    default = set(sh_array(routines_sh, "DEFAULT_ROUTINES", "stack-up/routines.sh"))

    # `register <name> "$!" SIGNAL` is how up.sh records a started process.
    services = re.findall(r"^\s*register\s+([a-z][\w-]*)\s", up_sh, re.MULTILINE)
    if not services:
        raise E.Missing(
            "stack-up/up.sh: no `register <name>` call matched, and that call is "
            "how this check knows which processes come up"
        )

    # The fixed port block near the top of up.sh.
    portvars = {
        "GATEWAY_PORT": "tokenfuse-gateway",
        "CLOUD_PORT": "tokenfuse-cloud",
        "DASH_PORT": "dashboard",
        "WARDRYX_PORT": "wardryx",
        "IDRYX_PORT": "idryx",
    }
    ports = {}
    for var, service in portvars.items():
        m = re.search(rf"^{var}=(\d+)\s*$", up_sh, re.MULTILINE)
        if not m:
            raise E.Missing(f"stack-up/up.sh: no `{var}=<port>` line matched")
        ports[service] = int(m.group(1))

    return {
        "routines": {n: (n in default) for n in names},
        "services": services,
        # Console scripts installed into ~/.taipan/bin rather than supervised.
        # `engram-mcp` is a stdio MCP server a harness launches on demand, so
        # it is neither a service nor a routine, and calling it either would be
        # a false statement in the one file the coverage check trusts.
        "tools": re.findall(r"^\s*install_py_tool\s+\S+\s+([a-z][\w-]*)", up_sh, re.MULTILINE),
        "ports": ports,
        "min_severity": min_severity(estate, "stack-up", ["up.sh"]),
    }


def observe_stack_single(estate: E.Estate) -> dict:
    compose = estate.read_text("stack-single", "compose.yaml")

    # Service keys are the two-space-indented mapping keys under `services:`.
    services: list[str] = []
    in_services = False
    for line in compose.splitlines():
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if in_services:
            if line and not line[0].isspace():
                break
            m = re.match(r"^  ([a-z][\w-]*):\s*$", line)
            if m:
                services.append(m.group(1))
    if not services:
        raise E.Missing(
            "stack-single/compose.yaml: no service keys were found under "
            "`services:`, so this check read no components at all"
        )

    # Ports, one declared anchor per component, because compose says it four
    # different ways: a published mapping, a listen address in `command`, a
    # PORT env, and an upstream. Each of these is exact; any that stops
    # matching is a FAIL below rather than a component quietly dropping out.
    anchors = {
        "tokenfuse-gateway": r"TOKENFUSE_ADDR:\s*[\d.]+:(\d+)",
        "tokenfuse-cloud": r"PORT:\s*\"(\d+)\"",
        "wardryx": r"-\s*0\.0\.0\.0:(\d+)",
        "idryx": r"--addr\s*\n\s*-\s*0\.0\.0\.0:(\d+)",
        "console": r"-\s*\"127\.0\.0\.1:(\d+):\d+\"",
    }
    ports = {}
    for service, pattern in anchors.items():
        m = re.search(pattern, compose)
        if not m:
            raise E.Missing(
                f"stack-single/compose.yaml: the port anchor for {service} "
                f"(/{pattern}/) matched nothing"
            )
        ports[service] = int(m.group(1))

    # Routines: the claim is that there are none. Verified by looking, not by
    # assuming. Anything matching a scheduler word in the shipped files is a
    # routine this check would otherwise have missed.
    scheduler = re.compile(r"\b(cron|crontab|systemd|\.timer|OnCalendar|launchd)\b", re.I)
    found = []
    for f in ("compose.yaml", "install.sh"):
        text = estate.read_text("stack-single", f)
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if scheduler.search(stripped):
                found.append(f"{f}:{i}: {stripped[:70]}")

    return {
        "routines": {},
        "routine_scheduler_hits": found,
        "services": services,
        "tools": [],  # neither deployment installs a console script

        "ports": ports,
        "min_severity": min_severity(
            estate, "stack-single", ["compose.yaml", "install.sh"]
        ),
    }


def observe_stack_k8s(estate: E.Estate) -> dict:
    manifests = [
        f
        for f in estate.list_files("stack-k8s")
        if f.startswith("manifests/") and f.endswith(".yaml") and "example" not in f
    ]
    if not manifests:
        raise E.Missing(
            "stack-k8s: no manifests/*.yaml were found, so no workload, port or "
            "CronJob was read"
        )

    routines: dict[str, bool] = {}
    services: list[str] = []
    ports: dict[str, int] = {}
    for f in sorted(manifests):
        text = estate.read_text("stack-k8s", f)
        for kind, name, doc in k8s_objects(text, f"stack-k8s/{f}"):
            if kind == "CronJob":
                suspended = re.search(r"^\s*suspend:\s*true\s*$", doc, re.MULTILINE)
                if not re.search(r"^\s*schedule:\s*\"", doc, re.MULTILINE):
                    raise E.Missing(
                        f"stack-k8s/{f}: CronJob {name} has no `schedule: \"...\"` "
                        f"this check could read"
                    )
                routines[name] = not suspended
            elif kind in ("Deployment", "StatefulSet", "DaemonSet"):
                services.append(name)
            elif kind == "Service":
                m = re.search(r"\bport:\s*(\d+)", doc)
                if not m:
                    raise E.Missing(
                        f"stack-k8s/{f}: Service {name} has no `port:` this check "
                        f"could read"
                    )
                ports[name] = int(m.group(1))
    if not services:
        raise E.Missing(
            "stack-k8s: no Deployment or StatefulSet was found in manifests/"
        )

    return {
        "routines": routines,
        "services": services,
        "tools": [],  # neither deployment installs a console script

        "ports": ports,
        "min_severity": min_severity(
            estate, "stack-k8s", ["manifests/45-heraldyx.yaml"]
        ),
    }


OBSERVERS = {
    "stack-up": observe_stack_up,
    "stack-single": observe_stack_single,
    "stack-k8s": observe_stack_k8s,
}


# ------------------------------------------------------------- the compare


def load_expectations() -> dict:
    path = expectations_path()
    if not path.is_file():
        raise E.Missing(
            f"{path} is not there. Without it every difference between the three "
            f"deployments is unrecorded, and this check cannot tell a decision "
            f"from an omission"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C5", "deployment parity across stack-up, stack-single, stack-k8s", estate)

    try:
        expectations = load_expectations()
    except E.Missing as m:
        c.missing("c5.expectations-gone", str(m))
        return c

    observed: dict[str, dict] = {}
    unreachable = 0
    for name in DEPLOYMENTS:
        try:
            estate.dir_of(name)
        except E.Unavailable as u:
            unreachable += 1
            c.unavailable(
                f"c5.deployment-unavailable:{name}",
                f"{name} could not be read in this run ({u.reason}), so it was "
                f"compared with nothing.",
            )
            continue
        try:
            observed[name] = OBSERVERS[name](estate)
        except E.Missing as m:
            c.missing(
                "c5.deployment-unreadable",
                f"{name}: {m}. This deployment was not compared at all, which is "
                f"not the same as it agreeing.",
            )
    if len(observed) < 2:
        if len(observed) + unreachable < 2:
            # The shortfall is real: deployments this run COULD open and could
            # not read. That is a finding about the estate.
            c.missing(
                "c5.too-few-deployments",
                f"only {len(observed)} deployment(s) could be read, and parity "
                f"between fewer than two is not a thing that exists.",
            )
        else:
            # The shortfall is this run's reach, not the estate's state. Red
            # here would say the estate is broken when the truth is that
            # nothing looked, and the two send a reader to different places.
            c.unavailable(
                "c5.too-few-reachable",
                f"only {len(observed)} of the three deployments were reachable in "
                f"this run, so no parity comparison was made at all.",
            )
        return c

    c.note(
        "Deployments read: " + ", ".join(sorted(observed)) + ". Agreed values come "
        "from expectations/deployment-parity.json."
    )

    divergences: dict[str, str] = {}  # key -> one-line human description

    # -- routines ----------------------------------------------------------
    agreed_routines = set(expectations["families"]["routines"]["agreed"])
    for name, obs in sorted(observed.items()):
        kinds: dict[str, bool] = {}
        for local, enabled in obs["routines"].items():
            kind = ROUTINE_KIND.get(local)
            if kind is None:
                c.missing(
                    "c5.routine-unmapped",
                    f"{name} installs a routine called `{local}` and this check has "
                    f"no mapping for that name, so it cannot say which of the five "
                    f"governance routines it is (or whether it is a sixth). Add it "
                    f"to ROUTINE_KIND in this file.",
                )
                continue
            kinds[kind] = enabled
        for kind in sorted(agreed_routines - set(kinds)):
            divergences[f"routines:{name}:absent:{kind}"] = (
                f"{name} does not install the `{kind}` governance routine"
            )
        for kind in sorted(set(kinds) - agreed_routines):
            divergences[f"routines:{name}:extra:{kind}"] = (
                f"{name} installs `{kind}`, which is not in the agreed set"
            )
        for kind in sorted(k for k, on in kinds.items() if not on):
            divergences[f"routines:{name}:disabled:{kind}"] = (
                f"{name} ships `{kind}` switched off by default"
            )
        c.ok(
            "c5.routines-read",
            f"{name}: {len(kinds)} governance routine(s) read "
            f"({', '.join(sorted(kinds)) or 'none'}).",
        )
        if name == "stack-single" and obs.get("routine_scheduler_hits"):
            c.drift(
                "c5.unread-scheduler",
                f"stack-single ships no routine this check can read, and yet "
                f"{len(obs['routine_scheduler_hits'])} line(s) mention a scheduler.",
                ["  " + h for h in obs["routine_scheduler_hits"][:5]]
                + [
                    "Either it does schedule something this check is blind to, or",
                    "the mention is prose. Both need a person to look once.",
                ],
            )

    # -- min severity -------------------------------------------------------
    agreed_sev = expectations["families"]["min_severity"]["agreed"]
    for name, obs in sorted(observed.items()):
        got = obs["min_severity"]
        if got != agreed_sev:
            divergences[f"min_severity:{name}:{got}"] = (
                f"{name} sets HERALDYX_MIN_SEVERITY to `{got}` where the agreed "
                f"value is `{agreed_sev}`"
            )
        else:
            c.ok(
                "c5.severity-agrees",
                f"{name} sets HERALDYX_MIN_SEVERITY to the agreed `{agreed_sev}`.",
            )

    # -- ports --------------------------------------------------------------
    agreed_ports = expectations["families"]["ports"]["agreed"]
    for name, obs in sorted(observed.items()):
        for local, port in sorted(obs["ports"].items()):
            service = SERVICE_KIND.get(local, local)
            want = agreed_ports.get(service)
            if want is None:
                divergences[f"ports:{name}:unagreed:{service}={port}"] = (
                    f"{name} publishes {service} on {port} and the agreed port map "
                    f"has no entry for {service}"
                )
            elif port != want:
                divergences[f"ports:{name}:{service}={port}"] = (
                    f"{name} puts {service} on port {port}, the agreed map says {want}"
                )
            else:
                c.ok(
                    "c5.port-agrees",
                    f"{name} puts {service} on the agreed port {port}.",
                )

    # -- services -----------------------------------------------------------
    agreed_services = set(expectations["families"]["services"]["agreed"])
    for name, obs in sorted(observed.items()):
        kinds = set()
        for local in obs["services"]:
            kind = SERVICE_KIND.get(local)
            if kind is None:
                c.missing(
                    "c5.service-unmapped",
                    f"{name} brings up a component called `{local}` and this check "
                    f"has no mapping for that name, so it cannot compare it with "
                    f"the other two deployments. Add it to SERVICE_KIND in this "
                    f"file.",
                )
                continue
            kinds.add(kind)
        for service in sorted(agreed_services - kinds):
            divergences[f"services:{name}:absent:{service}"] = (
                f"{name} does not bring up {service}"
            )
        for service in sorted(kinds - agreed_services):
            divergences[f"services:{name}:extra:{service}"] = (
                f"{name} brings up {service}, which is not in the agreed set"
            )
        c.ok(
            "c5.services-read",
            f"{name}: {len(kinds)} component(s) read.",
        )

    # -- coverage: a runnable piece no deployment installs -------------------
    #
    # The three families above compare the deployments WITH EACH OTHER. They
    # cannot see a component that is absent from all three at once, because
    # the subject list they compare against was written by hand and only ever
    # held what somebody remembered to add. vouchryx entered the estate on
    # 2026-08-26, installable by nothing, and every family above stayed green.
    #
    # So the subjects here are DISCOVERED from the registry's `runs` field
    # rather than declared in this file, and a repository that does not say
    # what it runs is a FAIL and not a skip.
    installable: set[str] = set()
    for obs in observed.values():
        for local in obs["services"]:
            kind = SERVICE_KIND.get(local)
            if kind is not None:
                installable.add(kind)
        for local in obs["routines"]:
            kind = ROUTINE_KIND.get(local)
            if kind is not None:
                installable.add(kind)
        installable.update(obs["tools"])

    for repo in sorted(estate.repos):
        entry = estate.repos[repo]
        if "runs" not in entry:
            c.missing(
                "c5.runs-undeclared",
                f"the registry entry for `{repo}` has no `runs` field, so this "
                f"check cannot tell whether it is a component that ought to be "
                f"installable or a library that ought not to be.",
                [
                    f"  add it in: {E.REPO_ROOT / 'estate.json'}",
                    "An empty list is a valid and common answer. No answer is not,",
                    "because a repository nobody classified is one this check",
                    "silently passes over, which is the state that let a service",
                    "reach the estate installable by nothing.",
                ],
            )
            continue
        for kind in entry["runs"]:
            if kind in installable:
                c.ok(
                    "c5.component-installable",
                    f"{repo} contributes `{kind}`, and at least one deployment "
                    f"installs it.",
                )
            else:
                divergences[f"coverage:{kind}:installable-by-nothing"] = (
                    f"{repo} contributes the component `{kind}` and not one of "
                    f"the {len(DEPLOYMENTS)} deployments installs it"
                )

    # -- the expectations file ----------------------------------------------
    recorded = {}
    for family in expectations["families"].values():
        recorded.update(family.get("divergences", {}))

    for key in sorted(divergences):
        entry = recorded.get(key)
        if entry is None:
            c.drift(
                "c5.unrecorded-divergence",
                f"{divergences[key]}, and nothing records that as a decision.",
                [
                    f"  key:      {key}",
                    f"  record it in: {expectations_path()}",
                    "A divergence with a reason beside it is a decision. Without one",
                    "nobody downstream can tell it from an oversight, which is the",
                    "state all three of these repositories were in.",
                ],
            )
        else:
            c.ok(
                "c5.recorded-divergence",
                f"{divergences[key]}. Recorded {entry.get('recorded', '(no date)')} "
                f"{entry.get('provenance', '')}: {entry.get('why', '(no reason)')}",
            )

    for key in sorted(recorded):
        if key not in divergences:
            c.drift(
                "c5.stale-expectation",
                f"expectations/deployment-parity.json records `{key}` as a known "
                f"divergence and it is not one today.",
                [
                    f"  file: {expectations_path()}",
                    f"  reason it carries: {recorded[key].get('why', '(none)')}",
                    "Either the divergence was fixed and this entry should go, or",
                    "the check stopped seeing it. A file of allowances nobody prunes",
                    "is how a gate becomes a formality.",
                ],
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
