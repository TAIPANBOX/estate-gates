"""C15's reader of the health path a launcher polls, against every shape the call takes.

`stack-up` probes a component with `wait_health <name> <port> <pid> [path] [timeout]`,
where the path is optional, starts with `/`, and defaults to `/healthz`. The
reader has to answer one question per call, which path, and it is read out of
shell text, where what follows the third argument is often not an argument at
all: `;`, `then`, `||`, `&&`, a `\\` continuing the line, a comment.

Measured 2026-10-28: stack-up's `if wait_health keyryx "$KEYRYX_PORT" "$!"; then`
was read as a probe of the path `then`, and the scheduled run was red for it
from that day, a finding about a path no launcher ever polled. The calls that
pass no path at all (`|| die`, `|| warn`) were read as not there, so a launcher
polling the default of a component that serves another path was never compared.

WHAT IS PROVED HERE, against the reader the gate uses (`PROBES` and
`read_probes` in gates/c15-component-manifests.py):

  1. every `wait_health` call in stack-up's up.sh as it stood on 2026-10-28 is
     read as the path the launcher polls, 12 calls, no extras;
  2. a missing path is the default, and `;`, `then`, `||`, `&&`, a backslash and
     a trailing comment are never a path, while an explicit path (quoted or
     bare, before a timeout, on a continuation line) is read as written;
  3. what is not a call is not read: the function definition, a comment that
     quotes the signature;
  4. a real wrong path is still a path, so the gate still has something to
     disagree with.
"""

from __future__ import annotations

import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def _load_gate():
    spec = importlib.util.spec_from_file_location("c15_probe_shapes", HERE.parent / "gates" / "c15-component-manifests.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


#: Every `wait_health` call and the lines around the function, verbatim from
#: stack-up's up.sh at 5cff906 (2026-10-28). Long messages after `||` are cut;
#: nothing before them is.
STACK_UP_2026_10_28 = r'''
# wait_health <name> <port> <pid> [path] [timeout]
wait_health() {
  local name="$1" port="$2" pid="$3" path="${4:-/healthz}" timeout="${5:-90}"
}
  if wait_health vouchryx "$VOUCHRYX_PORT" "$!" "/.well-known/jwks.json"; then
wait_health cloud "$CLOUD_PORT" "$!" || die "cloud did not come up."
wait_health gateway "$GATEWAY_PORT" "$!" || die "gateway did not come up."
  if wait_health dashboard "$DASH_PORT" "$!" / 20; then
  if wait_health keyryx "$KEYRYX_PORT" "$!"; then
  wait_health keyryx-witness "$KEYRYX_WITNESS_PORT" "$!" \
    || warn "keyryx witness did not come up; this run's record is not witnessed."
  wait_health wardryx "$WARDRYX_PORT" "$!" || die "wardryx did not come up."
  wait_health idryx "$IDRYX_PORT" "$!" || warn "idryx did not come up. Continuing."
  wait_health costcrew "$COSTCREW_PORT" "$!" "/healthz" || \
    warn "costcrew did not come up; the rest of the stack is unaffected."
  wait_health typryx "$TYPRYX_PORT" "$!" "/healthz" || \
    warn "typryx did not come up; the rest of the stack is unaffected."
  wait_health typryx-wardryx-proxy "$TYPRYX_PROXY_PORT" "$!" "/healthz" \
    || die "typryx wardryx-proxy did not come up."
  wait_health tokenfuse-mcp-broker "$BROKER_PORT" "$!" "/healthz" || \
    warn "tokenfuse-mcp-broker did not come up."
'''

STACK_UP_READS = {
    "vouchryx": "/.well-known/jwks.json",
    "cloud": "/healthz",
    "gateway": "/healthz",
    "dashboard": "/",
    "keyryx": "/healthz",
    "keyryx-witness": "/healthz",
    "wardryx": "/healthz",
    "idryx": "/healthz",
    "costcrew": "/healthz",
    "typryx": "/healthz",
    "typryx-wardryx-proxy": "/healthz",
    "tokenfuse-mcp-broker": "/healthz",
}

#: (what the call looks like, the text, the path it must be read as)
SHAPES = [
    ("an `if` with no path, then `;` and `then`", 'if wait_health x "$P" "$!"; then\n  :\nfi\n', "/healthz"),
    ("a `||` after no path", 'wait_health x "$P" "$!" || die "x did not come up."\n', "/healthz"),
    ("a `&&` after no path", 'wait_health x "$P" "$!" && echo /up\n', "/healthz"),
    ("a bare `;` after no path", 'wait_health x "$P" "$!" ; echo /up\n', "/healthz"),
    ("a backslash continuing onto a `||`", 'wait_health x "$P" "$!" \\\n  || warn "x"\n', "/healthz"),
    ("a trailing comment that holds a path", 'wait_health x "$P" "$!"  # polls /not/a/path\n', "/healthz"),
    ("a comment after `then`", 'if wait_health x "$P" "$!"; then # /not/a/path\n  :\nfi\n', "/healthz"),
    ("the call is the last line, with no newline", 'wait_health x "$P" "$!"', "/healthz"),
    ("a quoted path", 'wait_health x "$P" "$!" "/ready" || warn\n', "/ready"),
    ("a bare path", "wait_health x \"$P\" \"$!\" /ready || warn\n", "/ready"),
    ("a quoted path, then `;`", 'if wait_health x "$P" "$!" "/ready"; then\n', "/ready"),
    ("a single-quoted path", "wait_health x \"$P\" \"$!\" '/ready' || warn\n", "/ready"),
    ("a path, then a timeout", 'wait_health x "$P" "$!" /ready 20 || warn\n', "/ready"),
    ("the root path, then a timeout", 'wait_health x "$P" "$!" / 20 || warn\n', "/"),
    ("a path on the continuation line", 'wait_health x "$P" "$!" \\\n  "/ready" || warn\n', "/ready"),
    ("a path with a dot, a dash and a depth", 'wait_health x "$P" "$!" "/v1/health-check.json"; then\n', "/v1/health-check.json"),
    ("a path that holds a variable is read as written, so it disagrees in the open", 'wait_health x "$P" "$!" "/h/$ID" || warn\n', "/h/$ID"),
    ("a real wrong path", 'if wait_health x "$P" "$!" "/readyz"; then\n', "/readyz"),
]

#: (what it is, the text): nothing here is a call.
NOT_CALLS = [
    ("the function definition", 'wait_health() {\n  local name="$1"\n}\n'),
    ("a comment quoting the signature", "# wait_health <name> <port> <pid> [path] [timeout]\n"),
    ("an indented comment naming a call", '    # wait_health x "$P" "$!" "/never"\n'),
    ("a different function with the name as a prefix", 'wait_healthy x "$P" "$!"\n'),
    ("the word with too few arguments", "wait_health x 4300\n"),
]


def run() -> list[str]:
    problems: list[str] = []
    gate = _load_gate()
    rel, pattern, default = gate.PROBES["stack-up"]
    if default != "/healthz":
        problems.append(f"the default path for stack-up's wait_health is {default!r}, and the function itself says /healthz")

    got = gate.read_probes(STACK_UP_2026_10_28, pattern, default)
    if got != STACK_UP_READS:
        missing = {k: v for k, v in STACK_UP_READS.items() if got.get(k) != v}
        extra = {k: v for k, v in got.items() if k not in STACK_UP_READS}
        problems.append(
            f"stack-up's 12 wait_health calls are not all read as the path they poll: wrong or missing {missing}, extra {extra}"
        )
    for what, text, want in SHAPES:
        got = gate.read_probes(text, pattern, default)
        if got != {"x": want}:
            problems.append(f"{what}: read {got!r}, the path polled is {want!r}")
    for what, text in NOT_CALLS:
        got = gate.read_probes(text, pattern, default)
        if got:
            problems.append(f"{what} was read as a call: {got!r}")
    return problems


if __name__ == "__main__":
    import sys

    found = run()
    for p in found:
        print("FAIL:", p)
    print(f"{'FAIL' if found else 'OK'}: {len(found)} problem(s)")
    sys.exit(1 if found else 0)
