#!/usr/bin/env python3
"""C25: each launcher still sets the security postures it sets today.

WHY

The 2026-10-17 review found that the products ship permissive defaults and rely
on their launchers to switch enforcement on (analysis/cross-cutting.md, section
1.1). Waves 0 and 1 changed the launchers so that they do. Nothing read what the
launchers actually set, so the next edit could put a default back and every
suite in every repository would stay green: a product's suite tests the product,
and a launcher's own gates test the launcher against itself. Only this
repository reads the three launchers side by side, so the check lives here.

WHAT IT READS, AND WHERE EACH VALUE IS

  stack-single  compose.yaml: the `tokenfuse-gateway` and `tokenfuse-mcp-broker`
                services and their `environment:` mappings. install.sh: the
                wardryx secret the gateway is given, and the role it gets.
  stack-k8s     manifests/*.yaml: the `tokenfuse-gateway` and
                `tokenfuse-mcp-broker` Deployments and their container env.
                install.sh: the `wardryx_keys` Secret literal, which carries the
                gateway's role.
  stack-up      up.sh: the gateway start that is wired to wardryx (the `if`
                branch, not its `else` fallback), and the broker start, with the
                array of wardryx settings it is handed.

Subjects are read by name from the files, at the ref the run is given, and every
value is taken with the line it came from, so a finding names both sides.

WHAT COUNTS AS HOLDING A POSTURE

A posture is judged on the TEXT a launcher sets, and the rule for each shape is
stated where it is applied:

  required      the value must be refused when absent: compose `${X:?...}`, a
                Kubernetes secretKeyRef that is not `optional`, or in up.sh a
                variable minted with rand_hex and followed by a refusal to start
                when it is empty.
  enforce, closed, block
                the effective value is that word. A compose `${X:-word}` is
                judged by its default, which is what the launcher ships.
  not-devkey    the gateway's policy-plane key is not wardryx's built-in
                `devkey` literal.
  pep-role      install.sh gives the gateway's wardryx secret the role pep, and
                the gateway is handed that secret.

ANCHORS

An anchor that matches nothing is a finding, never a skip: a service, a
Deployment, the wardryx-wired start of up.sh, the broker start or install.sh's
role line that cannot be found is MISSING and reads red, naming what vanished.
A file that is gone is the same. A repository that cannot be read at all is
NOT MEASURED, and the run is partial (invariant 3).

DIVERGENCES

A launcher may lack a posture on purpose. That is recorded in
`expectations/deployment-posture.json` with a reason and a provenance, and is
printed as an exception on every run. It goes red when it is unreasoned, and
when it excuses nothing any more: an entry for a posture the launcher now holds,
or for a cell that does not exist. An undeclared gap is a FAIL.

WHAT IT DOES NOT CATCH

  - That a binary enforces what its launcher sets. The launcher sets the value;
    that the product reads and obeys it is the product's own suite, and C25 says
    so rather than implying it. The stack-k8s wardryx key is the example: C25
    reads the role the launcher mints, and whether wardryx refuses that role at
    run time is a question for an install in CI.
  - Opt-in components are judged on their text, wherever they sit. The broker
    of stack-up is started only with --with-typed, and its wardryx settings
    exist only in the --typed-risk-signal branch, so a default stack-up run has
    no broker policy at all. The text check cannot see the flag.
  - stack-up's `else` fallback, the gateway start used when wardryx cannot run
    (no Go toolchain, or its port is busy). It starts the gateway with no policy
    plane, with a warning. It is not judged here.
  - The opt-in OpenAI door of stack-single (tokenfuse-gateway-openai). It is a
    second metered door with an empty compose default for its client keys,
    refused by install.sh instead. The brief named the one metered door, so it is
    not a subject. A decision about it belongs in the expectations file, made by
    its owner.
  - A value that arrives in .env, or through a file a launcher reads at run time.
    Only what the launcher text states is read.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

LAUNCHERS = ("stack-single", "stack-k8s", "stack-up")

#: Scope names. A scope is the service, Deployment or wardryx-wired start that
#: a posture is read from.
GATEWAY = "gateway"
BROKER = "broker"

#: The environment variable that overrides the expectations file's location.
#: selftest.py sets it so each mutated case reads its own copy.
EXPECTATIONS_ENV = "ESTATE_GATES_POSTURE_EXPECTATIONS"
EXPECTATIONS_DEFAULT = E.REPO_ROOT / "expectations" / "deployment-posture.json"

#: What each posture claims, in words a reader can check against the review.
POSTURES = {
    "client-keys": "the metered door refuses a caller that presents no client key",
    "identity-strict": "a key may speak only as the agents its identity binding names",
    "firewall": "the agent firewall enforces rather than only shadows",
    "pep-mode": "the gateway asks wardryx and enforces the answer",
    "pep-failmode": "the gateway refuses when wardryx cannot answer",
    "pep-key-role": "the gateway's policy-plane key is a pep, never a viewer or the devkey literal",
    "declassify-key": "the declassify endpoint needs its own key",
    "broker-dlp": "the MCP broker blocks secrets carried in tool arguments",
    "broker-scan": "the MCP broker's scan blocks rather than warns",
    "broker-pep-mode": "the MCP broker asks wardryx and enforces the answer",
    "broker-pep-failmode": "the MCP broker refuses when wardryx cannot answer",
    "admin-keys": "the gateway's admin routes need a key",
}

#: (posture, launcher, scope, key, rule). The subjects are these names, found in
#: the launcher files; a service or Deployment that is renamed is an anchor
#: that matches nothing, and reads red.
CELLS = (
    ("client-keys", "stack-single", GATEWAY, "TOKENFUSE_CLIENT_KEYS", "required"),
    ("client-keys", "stack-k8s", GATEWAY, "TOKENFUSE_CLIENT_KEYS", "required"),
    ("client-keys", "stack-up", GATEWAY, "TOKENFUSE_CLIENT_KEYS", "required"),
    ("identity-strict", "stack-single", GATEWAY, "TOKENFUSE_IDENTITY_STRICT", "enforce"),
    ("identity-strict", "stack-k8s", GATEWAY, "TOKENFUSE_IDENTITY_STRICT", "enforce"),
    ("identity-strict", "stack-up", GATEWAY, "TOKENFUSE_IDENTITY_STRICT", "enforce"),
    ("firewall", "stack-single", GATEWAY, "TOKENFUSE_FIREWALL", "enforce"),
    ("firewall", "stack-k8s", GATEWAY, "TOKENFUSE_FIREWALL", "enforce"),
    ("firewall", "stack-up", GATEWAY, "TOKENFUSE_FIREWALL", "enforce"),
    ("pep-mode", "stack-single", GATEWAY, "TOKENFUSE_WARDRYX_MODE", "enforce"),
    ("pep-mode", "stack-k8s", GATEWAY, "TOKENFUSE_WARDRYX_MODE", "enforce"),
    ("pep-mode", "stack-up", GATEWAY, "TOKENFUSE_WARDRYX_MODE", "enforce"),
    ("pep-failmode", "stack-single", GATEWAY, "TOKENFUSE_WARDRYX_FAILMODE", "closed"),
    ("pep-failmode", "stack-k8s", GATEWAY, "TOKENFUSE_WARDRYX_FAILMODE", "closed"),
    ("pep-failmode", "stack-up", GATEWAY, "TOKENFUSE_WARDRYX_FAILMODE", "closed"),
    ("pep-key-role", "stack-single", GATEWAY, "TOKENFUSE_WARDRYX_KEY", "pep-role"),
    ("pep-key-role", "stack-k8s", GATEWAY, "TOKENFUSE_WARDRYX_KEY", "pep-role"),
    ("pep-key-role", "stack-up", GATEWAY, "TOKENFUSE_WARDRYX_KEY", "not-devkey"),
    ("declassify-key", "stack-single", GATEWAY, "TOKENFUSE_DECLASSIFY_KEY", "required"),
    ("declassify-key", "stack-k8s", GATEWAY, "TOKENFUSE_DECLASSIFY_KEY", "required"),
    ("declassify-key", "stack-up", GATEWAY, "TOKENFUSE_DECLASSIFY_KEY", "required"),
    ("broker-dlp", "stack-single", BROKER, "TOKENFUSE_MCP_DLP", "block"),
    ("broker-dlp", "stack-k8s", BROKER, "TOKENFUSE_MCP_DLP", "block"),
    ("broker-dlp", "stack-up", BROKER, "TOKENFUSE_MCP_DLP", "block"),
    ("broker-scan", "stack-single", BROKER, "TOKENFUSE_MCP_SCAN", "block"),
    ("broker-scan", "stack-k8s", BROKER, "TOKENFUSE_MCP_SCAN", "block"),
    ("broker-scan", "stack-up", BROKER, "TOKENFUSE_MCP_SCAN", "block"),
    ("broker-pep-mode", "stack-single", BROKER, "TOKENFUSE_WARDRYX_MODE", "enforce"),
    ("broker-pep-mode", "stack-k8s", BROKER, "TOKENFUSE_WARDRYX_MODE", "enforce"),
    ("broker-pep-mode", "stack-up", BROKER, "TOKENFUSE_WARDRYX_MODE", "enforce"),
    ("broker-pep-failmode", "stack-single", BROKER, "TOKENFUSE_WARDRYX_FAILMODE", "closed"),
    ("broker-pep-failmode", "stack-k8s", BROKER, "TOKENFUSE_WARDRYX_FAILMODE", "closed"),
    ("broker-pep-failmode", "stack-up", BROKER, "TOKENFUSE_WARDRYX_FAILMODE", "closed"),
    ("admin-keys", "stack-single", GATEWAY, "TOKENFUSE_ADMIN_KEYS", "required"),
    ("admin-keys", "stack-k8s", GATEWAY, "TOKENFUSE_ADMIN_KEYS", "required"),
    ("admin-keys", "stack-up", GATEWAY, "TOKENFUSE_ADMIN_KEYS", "required"),
)

#: The name each launcher gives the services and Deployments of a scope.
SCOPE_NAME = {
    "stack-single": {GATEWAY: "tokenfuse-gateway", BROKER: "tokenfuse-mcp-broker"},
    "stack-k8s": {GATEWAY: "tokenfuse-gateway", BROKER: "tokenfuse-mcp-broker"},
}

ROLE = re.compile(r"\$WARDRYX_GATEWAY_SECRET:[A-Za-z0-9_.-]+:([a-z]+)")


class Setting:
    """One variable a launcher sets for one service.

    `value` is the effective literal (a compose default counts), or None when
    the value is a reference that the text cannot resolve. `required` is True
    when the launcher refuses to start without it.
    """

    def __init__(self, key: str, value: str | None, required: bool, where: str, raw: str):
        self.key = key
        self.value = value
        self.required = required
        self.where = where
        self.raw = raw

    def shown(self) -> str:
        """The value as a reader may see it. A reference is named, never resolved
        into text this check cannot vouch for."""
        if self.value is not None:
            return f"`{self.value}`"
        return "a reference the launcher text does not resolve"


class Surface:
    """What one launcher sets, read once per run."""

    def __init__(self, launcher: str):
        self.launcher = launcher
        self.scopes: dict[str, dict[str, Setting]] = {}
        self.anchor_missing: dict[str, str] = {}
        self.where: dict[str, str] = {}
        self.roles: list[tuple[str, str]] | None = None


# ----------------------------------------------------------------- compose

SERVICE = re.compile(r"^  ([a-z][a-z0-9-]*):\s*$")
ENV_HEAD = re.compile(r"^    environment:\s*$")
ENV_KEY = re.compile(r"^      ([A-Z][A-Z0-9_]*):(?:\s+(.*?))?\s*$")
COMPOSE_REQUIRED = re.compile(r"^\$\{([A-Z][A-Z0-9_]*):\?.*\}$")
COMPOSE_DEFAULT = re.compile(r"^\$\{([A-Z][A-Z0-9_]*):-(.*)\}$")


def live(text: str) -> list[tuple[int, str]]:
    """(line number, line) for every line that is not a whole-line comment.

    The numbers are the file's own, so a finding can name the line it came
    from. Every launcher here is shell or YAML, and both comment with `#`.
    """
    return [
        (n, line)
        for n, line in enumerate(text.split("\n"), 1)
        if not line.lstrip().startswith("#")
    ]


def _compose_setting(key: str, raw: str, where: str) -> Setting:
    raw = raw.strip()
    if COMPOSE_REQUIRED.match(raw):
        return Setting(key, None, True, where, raw)
    m = COMPOSE_DEFAULT.match(raw)
    if m:
        # The default is what the launcher ships, so it is the effective value.
        return Setting(key, m.group(2).strip('"'), False, where, raw)
    return Setting(key, raw.strip('"'), False, where, raw)


def parse_compose(path: str, text: str) -> dict[str, dict[str, Setting]]:
    services: dict[str, dict[str, Setting]] = {}
    current: str | None = None
    in_env = False
    for n, line in live(text):
        if not line.strip():
            continue
        if not line.startswith(" "):
            current, in_env = None, False
            continue
        if line.startswith("  ") and not line.startswith("   "):
            m = SERVICE.match(line)
            if m:
                current = m.group(1)
                services.setdefault(current, {})
                in_env = False
            continue
        if current is None:
            continue
        if ENV_HEAD.match(line):
            in_env = True
            continue
        if in_env:
            m = ENV_KEY.match(line)
            if m:
                services[current][m.group(1)] = _compose_setting(
                    m.group(1), m.group(2) or "", f"{path}:{n}"
                )
            elif len(line) - len(line.lstrip()) <= 4:
                in_env = False
    return services


# --------------------------------------------------------------- kubernetes

KIND = re.compile(r"^kind:\s*(\S+)\s*$")
FLOW_ENV = re.compile(
    r'^\s*-\s*\{\s*name:\s*([A-Z][A-Z0-9_]*)\s*,\s*value:\s*"?([^",}]*)"?\s*\}\s*$'
)
BLOCK_ENV = re.compile(r"^\s*-\s*name:\s*([A-Z][A-Z0-9_]*)\s*$")
FLOW_ENV_ANY = re.compile(r"^\s*-\s*\{\s*name:\s*([A-Z][A-Z0-9_]*)\b")
VALUE_FROM = re.compile(
    r"^\s*valueFrom:\s*\{\s*(secretKeyRef|configMapKeyRef):\s*\{([^}]*)\}\s*\}\s*$"
)
VALUE_LINE = re.compile(r'^\s*value:\s*"?([^"]*?)"?\s*$')


def _k8s_docs(lines: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    docs: list[list[tuple[int, str]]] = [[]]
    for n, line in lines:
        if line.rstrip() == "---":
            docs.append([])
        else:
            docs[-1].append((n, line))
    return docs


def _k8s_env(doc: list[tuple[int, str]], path: str) -> dict[str, Setting]:
    env: dict[str, Setting] = {}
    for i, (n, line) in enumerate(doc):
        where = f"{path}:{n}"
        m = FLOW_ENV.match(line)
        if m:
            env[m.group(1)] = Setting(m.group(1), m.group(2).strip(), False, where, line.strip())
            continue
        m = BLOCK_ENV.match(line)
        if m:
            key = m.group(1)
            follow = doc[i + 1][1] if i + 1 < len(doc) else ""
            vf = VALUE_FROM.match(follow)
            if vf:
                # A secretKeyRef or configMapKeyRef the cluster must resolve. It
                # is required unless the reference says `optional: true`.
                required = "optional: true" not in vf.group(2)
                env[key] = Setting(key, None, required, where, follow.strip())
                continue
            vl = VALUE_LINE.match(follow)
            if vl:
                env[key] = Setting(key, vl.group(1).strip(), False, where, follow.strip())
                continue
            env[key] = Setting(key, None, False, where, line.strip())
            continue
        m = FLOW_ENV_ANY.match(line)
        if m:
            # A flow entry this reader does not parse (valueFrom inline). It is
            # recorded as unresolved, so the posture it carries reads as not
            # held, and the text is named in the finding.
            env[m.group(1)] = Setting(m.group(1), None, False, where, line.strip())
    return env


def parse_k8s(path: str, text: str) -> list[tuple[str, dict[str, Setting], str]]:
    """Every Deployment in one manifest file: (name, env, where)."""
    found = []
    for doc in _k8s_docs(live(text)):
        kinds = [KIND.match(line).group(1) for _, line in doc if KIND.match(line)]
        if kinds != ["Deployment"]:
            continue
        name = None
        seen_meta = False
        for _, line in doc:
            if line.startswith("metadata:"):
                seen_meta = True
            elif seen_meta and line.startswith("  name:"):
                name = line.split(":", 1)[1].strip()
                break
        if not name:
            continue
        found.append((name, _k8s_env(doc, path), path))
    return found


# ------------------------------------------------------------------- up.sh

ASSIGN_UP = re.compile(r'^\s*([A-Z][A-Z0-9_]*)="((?:[^"\\]|\\.)*)"\s*\\?\s*$')
COL0_LITERAL = re.compile(r'^([A-Z][A-Z0-9_]*)="([^"$`]*)"\s*$')
COL0_MINTED = re.compile(r'^([A-Z][A-Z0-9_]*)="\$\(rand_hex\b')
ARRAY_OPEN = re.compile(r"^\s*BROKER_WARDRYX_ENV=\(\s*$")
ARRAY_CLOSE = re.compile(r"^\s*\)\s*$")
ARRAY_ITEM = re.compile(r'"([A-Z][A-Z0-9_]*)=([^"]*)"')
GATEWAY_IF = 'if [ -n "$WARDRYX_URL" ]; then'
BROKER_LOG = 'log "starting tokenfuse-mcp-broker'
BROKER_LAUNCH = 'mcp-broker >'


def _up_setting(key: str, raw: str, where: str, defaults: dict, refused: set) -> Setting:
    """A value up.sh hands over. `$NAME` is resolved to the file's own default
    for NAME (its first column-0 literal), and is required when NAME is minted
    and refused when empty."""
    m = re.fullmatch(r"\$([A-Z][A-Z0-9_]*)", raw)
    if m:
        name = m.group(1)
        return Setting(key, defaults.get(name), name in refused, where, f'"${name}"')
    return Setting(key, raw, False, where, f'"{raw}"')


def parse_up_gateway(path: str, lines, defaults, refused) -> dict[str, Setting] | None:
    """The wardryx-wired gateway start: the `if` branch, up to its `else`."""
    start = next((i for i, (_, l) in enumerate(lines) if l.rstrip() == GATEWAY_IF), None)
    if start is None:
        return None
    end = next((j for j in range(start + 1, len(lines)) if lines[j][1].rstrip() == "else"), None)
    if end is None:
        return None
    env: dict[str, Setting] = {}
    for n, line in lines[start + 1 : end]:
        m = ASSIGN_UP.match(line)
        if m:
            env[m.group(1)] = _up_setting(m.group(1), m.group(2), f"{path}:{n}", defaults, refused)
    return env


def parse_up_broker(path: str, lines, defaults, refused) -> dict[str, Setting] | None:
    """The broker start, with the wardryx array it is handed. None if the start
    is missing, or if the start reads an array that is not defined."""
    start = next((i for i, (_, l) in enumerate(lines) if l.lstrip().startswith(BROKER_LOG)), None)
    if start is None:
        return None
    end = next((j for j in range(start, len(lines)) if BROKER_LAUNCH in lines[j][1]), None)
    if end is None:
        return None
    env: dict[str, Setting] = {}
    reads_array = False
    for n, line in lines[start : end + 1]:
        if "BROKER_WARDRYX_ENV[@]" in line:
            reads_array = True
        m = ASSIGN_UP.match(line)
        if m:
            env[m.group(1)] = _up_setting(m.group(1), m.group(2), f"{path}:{n}", defaults, refused)
    if not reads_array:
        return env
    opens = [i for i, (_, l) in enumerate(lines) if ARRAY_OPEN.match(l)]
    if not opens:
        return None
    for n, line in _array_items(lines, opens[-1]):
        for m in ARRAY_ITEM.finditer(line):
            env[m.group(1)] = _up_setting(m.group(1), m.group(2), f"{path}:{n}", defaults, refused)
    return env


def _array_items(lines, opened: int):
    for n, line in lines[opened + 1 :]:
        if ARRAY_CLOSE.match(line):
            return
        yield n, line


def up_defaults(lines) -> dict[str, str]:
    out: dict[str, str] = {}
    for _, line in lines:
        m = COL0_LITERAL.match(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def up_refused(lines) -> set[str]:
    """Variables minted with rand_hex that the launcher refuses to run without."""
    minted = {m.group(1) for _, line in lines for m in [COL0_MINTED.match(line)] if m}
    refused = set()
    for name in minted:
        pattern = re.compile(r'^\[ -n "\$' + name + r'" \]')
        if any(pattern.match(line) for _, line in lines):
            refused.add(name)
    return refused


# ------------------------------------------------------------ install.sh

def gateway_roles(path: str, text: str) -> list[tuple[str, str]]:
    """The role of every entry the installer writes for the gateway's secret."""
    out = []
    for n, line in live(text):
        for m in ROLE.finditer(line):
            out.append((m.group(1), f"{path}:{n}"))
    return out


# ------------------------------------------------------------------ readers


def read_stack_single(estate: E.Estate) -> Surface:
    s = Surface("stack-single")
    compose = "compose.yaml"
    services = parse_compose(compose, estate.read_text("stack-single", compose))
    for scope, name in SCOPE_NAME["stack-single"].items():
        if name in services:
            s.scopes[scope] = services[name]
            s.where[scope] = f"{compose}, service `{name}`"
        else:
            s.anchor_missing[scope] = (
                f"stack-single: {compose} has no `{name}` service, so the {scope} "
                f"posture cannot be read from it"
            )
    install = "install.sh"
    s.roles = gateway_roles(install, estate.read_text("stack-single", install))
    if not s.roles:
        s.anchor_missing["roles"] = (
            f"stack-single: {install} writes no `$WARDRYX_GATEWAY_SECRET:<org>:<role>` "
            f"entry, so the gateway's policy-plane role cannot be read"
        )
    return s


def read_stack_k8s(estate: E.Estate) -> Surface:
    s = Surface("stack-k8s")
    files = sorted(
        p for p in estate.list_files("stack-k8s", ".yaml") if p.startswith("manifests/")
    )
    if not files:
        raise E.Missing("stack-k8s tracks no manifests/*.yaml, so there is nothing to read")
    deployments: dict[str, list[tuple[dict[str, Setting], str]]] = {}
    for path in files:
        for name, env, where in parse_k8s(path, estate.read_text("stack-k8s", path)):
            deployments.setdefault(name, []).append((env, where))
    for scope, name in SCOPE_NAME["stack-k8s"].items():
        hits = deployments.get(name, [])
        if len(hits) == 1:
            s.scopes[scope] = hits[0][0]
            s.where[scope] = f"{hits[0][1]}, Deployment `{name}`"
        elif not hits:
            s.anchor_missing[scope] = (
                f"stack-k8s: no manifest declares a Deployment named `{name}`, so the "
                f"{scope} posture cannot be read from it"
            )
        else:
            s.anchor_missing[scope] = (
                f"stack-k8s: {len(hits)} Deployments are named `{name}`, so the "
                f"{scope} posture is ambiguous and is not read"
            )
    install = "install.sh"
    s.roles = gateway_roles(install, estate.read_text("stack-k8s", install))
    if not s.roles:
        s.anchor_missing["roles"] = (
            f"stack-k8s: {install} writes no `$WARDRYX_GATEWAY_SECRET:<org>:<role>` "
            f"entry, so the gateway's policy-plane role cannot be read"
        )
    return s


def read_stack_up(estate: E.Estate) -> Surface:
    s = Surface("stack-up")
    path = "up.sh"
    text = estate.read_text("stack-up", path)
    lines = live(text)
    defaults = up_defaults(lines)
    refused = up_refused(lines)
    gateway = parse_up_gateway(path, lines, defaults, refused)
    if gateway is None:
        s.anchor_missing[GATEWAY] = (
            f"stack-up: {path} has no wardryx-wired gateway start (`{GATEWAY_IF}` "
            f"... `else`), so the gateway's postures cannot be read from it"
        )
    else:
        s.scopes[GATEWAY] = gateway
        s.where[GATEWAY] = f"{path}, the wardryx-wired gateway start (`{GATEWAY_IF}`)"
    broker = parse_up_broker(path, lines, defaults, refused)
    if broker is None:
        s.anchor_missing[BROKER] = (
            f"stack-up: {path} has no tokenfuse-mcp-broker start that can be read "
            f"(`{BROKER_LOG}` ... `{BROKER_LAUNCH}`), so the broker's postures cannot be read"
        )
    else:
        s.scopes[BROKER] = broker
        s.where[BROKER] = f"{path}, the tokenfuse-mcp-broker start and its wardryx array"
    return s


READERS = {
    "stack-single": read_stack_single,
    "stack-k8s": read_stack_k8s,
    "stack-up": read_stack_up,
}


# ----------------------------------------------------------------- judging


def _judge(rule: str, setting: Setting | None, surf: Surface, scope: str, key: str) -> tuple[bool, str]:
    """Whether a setting holds a posture, and the sentence that says so."""
    absent = f"does not set {key} in {surf.where.get(scope, scope)}"
    if rule == "pep-role":
        if setting is None:
            return False, f"does not set {key} in {surf.where.get(scope, scope)}, so it hands the gateway no policy-plane key"
        if not (setting.required or setting.value):
            return False, f"hands the gateway a key that is not required ({setting.where})"
        bad = [(role, where) for role, where in (surf.roles or []) if role != "pep"]
        if bad:
            role, where = bad[0]
            return False, f"mints the gateway's policy-plane key as `{role}` ({where})"
        return True, "mints the gateway's policy-plane key as a pep"
    if setting is None:
        return False, absent
    if rule == "required":
        if setting.required:
            return True, f"refuses to start without it ({setting.where})"
        return False, f"is set without a refusal when it is empty ({setting.where})"
    if rule == "not-devkey":
        if setting.required or setting.value not in (None, "", "devkey"):
            return True, f"hands wardryx a key other than the devkey literal ({setting.where})"
        return False, f"hands wardryx the built-in `devkey` literal ({setting.where})"
    if setting.value == rule:
        return True, f"is `{rule}` ({setting.where})"
    return False, f"is {setting.shown()}, not `{rule}` ({setting.where})"


def _reasoned(entry) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("why"), str)
        and entry["why"].strip() != ""
        and isinstance(entry.get("provenance"), str)
        and entry["provenance"].strip() != ""
    )


def load_expectations() -> tuple[dict | None, str | None]:
    path = pathlib.Path(os.environ.get(EXPECTATIONS_ENV) or EXPECTATIONS_DEFAULT)
    if not path.is_file():
        return None, f"{path} is not there"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return None, f"{path} is not JSON ({e})"
    divergences = data.get("divergences") if isinstance(data, dict) else None
    if not isinstance(divergences, dict):
        return None, f"{path} has no `divergences` object"
    return divergences, None


def _revision(estate: E.Estate, repo: str) -> str:
    """The commit a launcher was read at, and its date.

    The date is printed so a reader can judge staleness. In ref mode the ref is
    the checkout's LOCAL origin/main, as the last `git fetch` left it, and this
    gate never fetches: a stale checkout reads as stale history. Refresh with
    `git -C <checkout> fetch origin` before running the gate.
    """
    rev = estate.ref if estate.mode == "ref" else "HEAD"
    proc = subprocess.run(
        [
            "git", "-C", str(estate.dir_of(repo)), "log", "-1",
            "--format=%h %cd", "--date=short", rev or "HEAD",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "an unknown revision"
    sha, date = proc.stdout.strip().split(" ", 1)
    return f"{sha} (committed {date})"


def _drift(c: E.Check, posture: str, launcher: str, message: str, detail: list[str]) -> None:
    """One literal finding ID per posture, so selftest.py can see each one.

    The IDs are written out rather than built from the posture name: the
    self-test reads them from this file's calls, and a name built at run time
    is a finding nothing can see. A posture with no branch here stops the run
    rather than passing silently.
    """
    if posture == "client-keys":
        c.drift(f"c25.client-keys:{launcher}", message, detail)
    elif posture == "identity-strict":
        c.drift(f"c25.identity-strict:{launcher}", message, detail)
    elif posture == "firewall":
        c.drift(f"c25.firewall:{launcher}", message, detail)
    elif posture == "pep-mode":
        c.drift(f"c25.pep-mode:{launcher}", message, detail)
    elif posture == "pep-failmode":
        c.drift(f"c25.pep-failmode:{launcher}", message, detail)
    elif posture == "pep-key-role":
        c.drift(f"c25.pep-key-role:{launcher}", message, detail)
    elif posture == "declassify-key":
        c.drift(f"c25.declassify-key:{launcher}", message, detail)
    elif posture == "broker-dlp":
        c.drift(f"c25.broker-dlp:{launcher}", message, detail)
    elif posture == "broker-scan":
        c.drift(f"c25.broker-scan:{launcher}", message, detail)
    elif posture == "broker-pep-mode":
        c.drift(f"c25.broker-pep-mode:{launcher}", message, detail)
    elif posture == "broker-pep-failmode":
        c.drift(f"c25.broker-pep-failmode:{launcher}", message, detail)
    elif posture == "admin-keys":
        c.drift(f"c25.admin-keys:{launcher}", message, detail)
    else:
        raise KeyError(f"no finding ID is written for posture {posture!r}")


# --------------------------------------------------------------------- run


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C25", "each launcher still sets the security postures it sets today", estate)

    expectations, absent = load_expectations()
    if absent is not None:
        c.missing(
            "c25.expectations-missing",
            f"{absent}. Without it no divergence can be excused, and this check "
            f"cannot say what a launcher was decided to lack, so it measured nothing "
            f"about the exceptions.",
        )
        expectations = {}

    if estate.mode == "ref":
        c.note(
            "Each ref is the checkout's local origin/main as its last fetch left it. "
            "This gate does not fetch, so a stale checkout reads as the history it has."
        )

    cell_names = {f"{p}:{launcher}" for p, launcher, *_ in CELLS}
    holding: set[str] = set()

    for launcher in LAUNCHERS:
        cells = [cell for cell in CELLS if cell[1] == launcher]
        try:
            surf = READERS[launcher](estate)
            revision = _revision(estate, launcher)
        except E.Unavailable as u:
            c.unmeasured(
                launcher,
                len(cells),
                f"c25.unmeasured:{launcher}",
                f"{launcher} could not be read in this run ({u.reason}), so its "
                f"{len(cells)} postures are unmeasured here.",
            )
            continue
        except E.Missing as m:
            c.missing(
                f"c25.launcher-missing:{launcher}",
                f"{launcher} is missing a file this check reads: {m}. Its postures "
                f"cannot be measured, which is a red, not a pass.",
            )
            continue

        c.note(f"{launcher} read at {revision}.")
        reported: set[str] = set()
        for posture, _, scope, key, rule in cells:
            name = f"{posture}:{launcher}"
            # The role line is an anchor like any other: a launcher whose
            # install.sh no longer writes it has vanished from this check, which
            # is MISSING, not a posture that is not held.
            anchor = "roles" if rule == "pep-role" else scope
            if anchor in surf.anchor_missing:
                if anchor not in reported:
                    reported.add(anchor)
                    c.missing(f"c25.anchor-missing:{launcher}", surf.anchor_missing[anchor])
                continue
            setting = surf.scopes.get(scope, {}).get(key)
            holds, text = _judge(rule, setting, surf, scope, key)
            if holds:
                holding.add(name)
                c.ok(f"c25.{name}", f"{launcher} {text}; {POSTURES[posture]}.")
                continue
            entry = expectations.get(name)
            if entry is not None and _reasoned(entry):
                c.note(
                    f"DECLARED {name}: {launcher} does not hold this posture "
                    f"({text}). Recorded {entry.get('recorded', 'undated')} as "
                    f"{entry['provenance']}: {entry['why']}"
                )
                continue
            detail = [
                f"  {launcher}: {text}",
                f"  the posture: {POSTURES[posture]}",
                "  fix: set the value in the launcher, or record a reasoned divergence",
                "       in expectations/deployment-posture.json",
            ]
            _drift(c, posture, launcher, f"{launcher} {text}.", detail)

    for name, entry in sorted(expectations.items()):
        if not _reasoned(entry):
            c.drift(
                f"c25.expectation-unreasoned:{name}",
                f"{name} is recorded as a divergence with no reason or no provenance. "
                f"An exception with no reason is a gap nobody wrote down.",
            )
        elif name not in cell_names:
            c.drift(
                f"c25.expectation-stale:{name}",
                f"{name} is recorded, but no posture and launcher pair by that name "
                f"is measured here. Remove it, or fix the name.",
            )
        elif name in holding:
            c.drift(
                f"c25.expectation-stale:{name}",
                f"{name} is recorded as a divergence, but the launcher now holds the "
                f"posture. An exception that excuses nothing is removed, so the file "
                f"cannot become a graveyard.",
            )

    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    return run(E.estate_from_args(args)).render()


if __name__ == "__main__":
    sys.exit(main())
