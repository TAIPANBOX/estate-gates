#!/usr/bin/env python3
"""C4: the SPEC 6.2 event-type registry against what the producers actually
emit, in both directions.

WHY

The registry in agent-passport/SPEC.md section 6.2 is the only statement of
which product writes which event types into the shared envelope. It said idryx
emits seven types. idryx has no event writer at all, in any file: its
detections leave by OTLP and by Slack. A consumer that built a handler for one
of those seven would have waited forever, and one downstream product had
already shipped the operator-facing description for two of them.

The reverse direction is the more valuable one and nothing anywhere checks it.
genaryx appends `console_command` lines with `source: "console"`, and
`console` is not a row in 6.2 at all. A source nobody registered is a producer
no consumer knows to expect.

HOW IT PARSES, AND WHAT THAT COSTS

Three languages, and no shortcut that works across them. This check does NOT
scan for strings that look like event names: `policy_deny` appears in prose,
in tests, in a comment and in a policy fixture, and a check anchored on the
shape of a word would report a producer for every one of them.

Instead each producer below declares the exact site its types come from: a
Rust match arm inside a named function, a Go composite-literal field resolved
through the file's own string constants, a Python literal passed to the
emitter. When one of those anchors matches nothing, that is a FAIL naming the
anchor, never a skip. The rule this repository is built on cuts both ways: a
producer this check could not read must be said out loud, because "no types
found" and "no types emitted" look identical in a summary.

WHAT IT DOES NOT CATCH

An emit site that builds its type string at runtime, from a variable or a
format. None exists in the estate today. If one arrives, this check will
report the producer's declared types and miss it, and the anchor will still
match, so nothing will complain. That is the honest limit and it is in the
README.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import posixpath
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

SPEC_REPO = "agent-passport"
SPEC_PATH = "SPEC.md"


# --------------------------------------------------------------- the registry


def parse_registry(spec: str) -> tuple[dict[str, set[str]], set[str]]:
    """Section 6.2's table. Lives in `_estate` since 2026-08-26, because C8
    reads the same table and a second parser would be a second reading of it."""
    return E.parse_registry(spec)


# ------------------------------------------------------------ small parsers

_GO_CONST = re.compile(
    r"^\s*(?:const\s+)?(\w+)\s*(?:string\s*)?=\s*\"([a-z0-9_]+)\"\s*$", re.MULTILINE
)
_GO_TYPE_FIELD = re.compile(r"\bType:\s*(\"[a-z0-9_]+\"|\w+)")
_RUST_ARM = re.compile(r"=>\s*\"([a-z0-9_]+)\"")


def go_consts(*texts: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in texts:
        for name, value in _GO_CONST.findall(t):
            out[name] = value
    return out


def _resolve(raw: str, consts: dict[str, str], unresolved: set[str]) -> str | None:
    """A literal, or a constant, or NOTHING RECORDED AS SUCH.

    The third case is why this function exists. Both parsers used to drop an
    identifier they could not resolve, which is the silent-zero failure this
    estate keeps finding, sitting inside the check written to catch it: a
    producer whose type is computed rather than written at the call site
    contributed nothing to the emitted set, the anchor still matched the file,
    and the run reported clean with the words "every subject was measured".

    scopyx is a real instance. It names its types as constants and passes the
    variable at the emit site, so `Type: kind` resolved to nothing and C4 had no
    opinion about two live event types the registry does not carry.
    """
    if raw.startswith('"'):
        return raw.strip('"')
    if raw in consts:
        return consts[raw]
    unresolved.add(raw)
    return None




def go_call_first_args(
    text: str, call: str, consts: dict[str, str]
) -> tuple[set[str], set[str]]:
    """First argument of every `call(` in the text. Returns (resolved, unresolved)."""
    found: set[str] = set()
    unresolved: set[str] = set()
    for m in re.finditer(re.escape(call) + r"\(\s*(\"[a-z0-9_]+\"|\w+)", text):
        v = _resolve(m.group(1), consts, unresolved)
        if v is not None:
            found.add(v)
    return found, unresolved


def rust_match_arms(text: str, fn: str, after: str | None = None) -> set[str]:
    """The `=> "literal"` arms of one named function.

    `after` narrows to the right impl block first: `as_wire_str` is the name of
    two different functions in tokenfuse, one on EventType and one on
    BreakerReason, and reading the wrong one would put the wrong vocabulary in
    front of the registry.
    """
    origin = 0
    if after is not None:
        origin = text.find(after)
        if origin < 0:
            raise E.Missing(f"the anchor `{after}` is not in the file")
    start = text.find(fn, origin)
    if start < 0:
        raise E.Missing(f"the anchor `{fn}` is not in the file")
    end = text.find("\n    }", start)
    return set(_RUST_ARM.findall(text[start : end if end > 0 else len(text)]))




# ----------------------------------------------------------- the producers
#
# One entry per repository that can write into the envelope. `writer` is the
# proof an event-writing code path exists at all: a file and the call that
# opens the writer. `extract` returns {source: {types}} and must raise
# E.Missing rather than return an empty set when its anchor stops matching.


# ------------------------------------------------- reading a producer's files
#
# Every producer reads the non-test source files of its own code directories,
# never only the file that once held its emits. A file this run cannot read,
# or a scan that finds no type at all, says "measured nothing" in its finding:
# the same red a missing subject gets, never a quiet zero.

#: The trees whose non-test Go files can open an event writer or emit one.
GO_TREES = ("internal/", "cmd/")

_EVENT_LITERAL = re.compile(r"\bevent\.Event\{")
_PY_TEST = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$)")
_RUST_TEST = re.compile(r"(^|/)(tests?/|it/)|_test\.rs$")
_RUST_TYPE_INSERT = re.compile(
    r'insert\(\s*"type"\.to_string\(\),\s*Value::String\(\s*"([a-z0-9_-]+)"'
)
_RUST_SOURCE_INSERT = re.compile(
    r'insert\(\s*"source"\.to_string\(\),\s*Value::String\(\s*"([a-z0-9_-]+)"'
)


def _measured_nothing(repo: str, what: str) -> E.Missing:
    """The one wording every reader uses when it could not read its emits."""
    return E.Missing(f"{repo}: {what}, so this run measured nothing about {repo}'s emits")


def go_package_files(
    estate: E.Estate, repo: str, trees: tuple[str, ...] = GO_TREES
) -> dict[str, list[tuple[str, str]]]:
    """Every non-test .go file under `trees`, read now and grouped by directory.

    Go scopes a constant to its package, so the directory is the unit in which a
    constant is resolved. A tracked file this run cannot read raises rather than
    being skipped: a skipped file is an emit nobody compared.
    """
    by_dir: dict[str, list[tuple[str, str]]] = {}
    for path in estate.list_files(repo, ".go"):
        if not path.startswith(trees) or path.endswith("_test.go"):
            continue
        try:
            text = estate.read_text(repo, path)
        except E.Missing as m:
            raise _measured_nothing(repo, f"{m}. That file's emits were not read") from None
        by_dir.setdefault(posixpath.dirname(path), []).append((path, text))
    return by_dir


def _braced_body(text: str, start: int) -> str:
    """The text between an opening brace consumed just before `start` and its match."""
    depth, i = 1, start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start : i - 1]


def _top_level(body: str) -> str:
    """`body` with everything nested inside a brace blanked: the literal's own fields."""
    out: list[str] = []
    depth = 0
    for c in body:
        if c == "{":
            depth += 1
            out.append(" ")
        elif c == "}":
            depth -= 1
            out.append(" ")
        else:
            out.append(c if depth == 0 else " ")
    return "".join(out)


def go_event_literal_types(text: str, consts: dict[str, str]) -> tuple[set[str], set[str]]:
    """The `Type:` field of every event.Event literal, its own fields only.

    A `Type:` inside a nested struct names something else (an identity, a
    finding's kind), and a `Type:` outside an event literal is not an event at
    all. So only the top-level fields of an event literal count. Returns
    (resolved, unresolved), the pair go_call_first_args returns.
    """
    found: set[str] = set()
    unresolved: set[str] = set()
    for m in _EVENT_LITERAL.finditer(text):
        for raw in _GO_TYPE_FIELD.findall(_top_level(_braced_body(text, m.end()))):
            v = _resolve(raw, consts, unresolved)
            if v is not None:
                found.add(v)
    return found, unresolved


def go_producer_types(
    estate: E.Estate,
    repo: str,
    *,
    calls: tuple[str, ...] = (),
    event_literals: bool = False,
    trees: tuple[str, ...] = GO_TREES,
) -> set[str]:
    """The types a Go producer writes, from every non-test file under `trees`.

    `calls` are emit helpers whose first argument is the type (`j.emit(`); with
    `event_literals` the `Type:` field of each event.Event literal counts. A
    type that is neither a literal nor a constant of its package is refused.
    """
    types: set[str] = set()
    for members in go_package_files(estate, repo, trees).values():
        consts = go_consts(*(text for _path, text in members))
        for path, text in members:
            for call in calls:
                found, unresolved = go_call_first_args(text, call, consts)
                _refuse_unresolved(repo, path, unresolved)
                types |= found
            if event_literals:
                found, unresolved = go_event_literal_types(text, consts)
                _refuse_unresolved(repo, path, unresolved)
                types |= found
    if not types:
        raise _measured_nothing(
            repo,
            f"no non-test Go file under {' or '.join(trees)} writes an event this "
            f"reader resolves",
        )
    return types


def python_emit_calls(text: str, funcs: set[str]) -> tuple[set[str], int]:
    """Literal first arguments to the emit helpers, and how many calls carry none.

    The second number counts calls whose type is computed at runtime, or passed
    by keyword, or absent. The caller refuses them: a type nobody can read is a
    hole, never an agreement.
    """
    tree = ast.parse(text)
    literal: set[str] = set()
    computed = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        if name not in funcs:
            continue
        if not node.args:
            computed += 1
            continue
        try:
            first = ast.literal_eval(node.args[0])
        except (ValueError, SyntaxError, TypeError):
            computed += 1
            continue
        if isinstance(first, str) and re.fullmatch(r"[a-z0-9_]+", first):
            literal.add(first)
        else:
            computed += 1
    return literal, computed


def python_package_types(
    estate: E.Estate, repo: str, package: str, funcs: set[str]
) -> set[str]:
    """The literal types emitted from every non-test .py file of one package."""
    types: set[str] = set()
    for path in estate.list_files(repo, ".py"):
        if not path.startswith(package + "/") or _PY_TEST.search(path):
            continue
        try:
            text = estate.read_text(repo, path)
        except E.Missing as m:
            raise _measured_nothing(repo, f"{m}. That file's emits were not read") from None
        literal, computed = python_emit_calls(text, funcs)
        if computed:
            raise E.Missing(
                f"{repo} {path}: {computed} emit call(s) take a type that is not a "
                f"literal string, which this check cannot read. Nothing here compared "
                f"those types against the registry, and reporting that as agreement "
                f"would be a clean run over a producer nobody read."
            )
        types |= literal
    if not types:
        raise _measured_nothing(repo, f"no non-test Python file under {package}/ emits a literal type")
    return types


def _tokenfuse(estate: E.Estate) -> dict[str, set[str]]:
    """tokenfuse's vocabulary is the `as_wire_str` mapping of its `EventType` enum.

    One enum in one file, and a `match` that names every variant. The compiler
    refuses a variant nobody mapped, and a wildcard arm would let one through with
    a wrong wire string, so a wildcard is refused here. Every emit names a variant,
    so the enum's file is the whole vocabulary rather than a sample of it.
    """
    text = estate.read_text("tokenfuse", "crates/core/src/agent_event.rs")
    types = rust_match_arms(text, "pub fn as_wire_str", after="impl EventType")
    if not types:
        raise _measured_nothing(
            "tokenfuse",
            "`impl EventType`'s `pub fn as_wire_str` matched no `EventType::X => \"y\"` arms",
        )
    origin = text.find("impl EventType")
    start = text.find("pub fn as_wire_str", origin)
    end = text.find("\n    }", start)
    body = text[start : end if end > 0 else len(text)]
    if re.search(r"^\s*_\s*=>", body, re.M):
        raise E.Missing(
            "tokenfuse crates/core/src/agent_event.rs: `as_wire_str` has a wildcard "
            "arm, so a variant nobody mapped would be written with a wrong wire "
            "string and this check would not see it"
        )
    return {"tokenfuse": types}




def _engram(estate: E.Estate) -> dict[str, set[str]]:
    """engram emits from its package: every non-test .py under engram/."""
    return {"engram": python_package_types(estate, "engram", "engram", {"emit", "_emit"})}




def _verdryx(estate: E.Estate) -> dict[str, set[str]]:
    """verdryx emits from its package, and names its taxonomy in EVENT_SEVERITY.

    The severity map is unioned in, so a type in it that no call site emits shows
    in either direction of the comparison below.
    """
    types = python_package_types(estate, "verdryx", "verdryx", {"emit"})
    ev = estate.read_text("verdryx", "verdryx/events.py")
    for node in ast.parse(ev).body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "EVENT_SEVERITY":
            got = ast.literal_eval(node.value) if node.value else {}
            types |= set(got)
    return {"verdryx": types}




def _refuse_unresolved(repo: str, path: str, unresolved: set[str]) -> None:
    """A type this parser could not read is a HOLE, never a silence.

    The alternative, which is what this check did until G4.4, is to drop the
    identifier and carry on. The anchor still matches, the file is still read,
    and the run says "every subject was measured" about a producer whose types
    it never saw. That sentence being false is worse than the missing coverage,
    because it is the sentence a reader trusts.
    """
    if unresolved:
        raise E.Missing(
            f"{repo} {path}: an event type is written as {sorted(unresolved)}, "
            f"which this check cannot resolve to a string. It is a variable or a "
            f"constant declared elsewhere. Nothing here compared those types "
            f"against the registry, and reporting that as agreement would be a "
            f"clean run over a producer nobody read."
        )


def _typryx(estate: E.Estate) -> dict[str, set[str]]:
    """The typed-answer service: its types are constants passed to `j.emit(`.

    Read from every non-test Go file, so a second file that emits is seen.
    """
    return {"typryx": go_producer_types(estate, "typryx", calls=("j.emit",))}




def _agent_conform(estate: E.Estate) -> dict[str, set[str]]:
    """The on-box chain verifier, `agent-conform watch-dir`, in agent-stack-go.

    It is the one producer here that lives inside the shared Go MODULE rather
    than in a repository of its own, which is why the PRODUCERS entry is keyed
    `agent-stack-go` and owns the source `agent-conform`.

    Its types are neither a `Type:` literal nor a first argument: the alert
    builder writes `Type: f.typ`, a variable. So this reads the names the command
    states in its `const (...)` blocks (`watchSource` and the `typeChain*`
    constants), from every non-test file of the command's package, and then
    requires the alert builder to still USE each of them: `Source: watchSource`
    and one `case <name>:` per type. A constant nobody switches on would be a type
    the verifier no longer writes, and the registry would go on claiming it.

    The `typeChain*` names are listed by hand, and that list is the kind that goes
    stale: a `typeChain*` constant the list does not name is a finding, not a
    silent omission. Comments are stripped first (invariant 14).
    """
    package = "cmd/agent-conform/"
    files: list[tuple[str, str]] = []
    for path in estate.list_files("agent-stack-go", ".go"):
        if not path.startswith(package) or path.endswith("_test.go"):
            continue
        try:
            text = estate.read_text("agent-stack-go", path)
        except E.Missing as m:
            raise _measured_nothing("agent-stack-go", f"{m}. That file's emits were not read") from None
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
        files.append((path, code))
    if not files:
        raise _measured_nothing("agent-stack-go", f"no non-test Go file under {package} can be read")
    consts: dict[str, str] = {}
    for _path, code in files:
        for block in re.finditer(r"^const \(\n(.*?)^\)", code, re.S | re.M):
            consts.update(re.findall(r"^\s*(\w+)\s*=\s*\"([a-z0-9_-]+)\"\s*$", block.group(1), re.M))
    if not consts:
        raise E.Missing(f"{package}: no `const (...)` block at the top level of any file")
    chain_types = ("typeChainBroken", "typeChainUnchained", "typeChainRestarted")
    unlisted = sorted(n for n in consts if n.startswith("typeChain") and n not in chain_types)
    if unlisted:
        raise E.Missing(
            f"{package}: the const blocks declare {', '.join('`' + n + '`' for n in unlisted)}, "
            f"which this extractor does not read, so their types are not compared with 6.2"
        )
    for name in ("watchSource",) + chain_types:
        if name not in consts:
            raise E.Missing(
                f"{package}: the const blocks have no string constant `{name}`, so this "
                f"producer's source and types could not be read"
            )
    code_all = "\n".join(code for _path, code in files)
    if not re.search(r"\bSource:\s*watchSource\b", code_all):
        raise E.Missing(f"{package}: no `Source: watchSource`, so the declared source is not the one written")
    for name in chain_types:
        if not re.search(rf"\bcase\s+{name}\s*:", code_all):
            raise E.Missing(
                f"{package}: no `case {name}:` in the alert builder, so the constant is "
                f"declared and nothing writes it"
            )
    return {consts["watchSource"]: {consts[name] for name in chain_types}}




def _scopyx(estate: E.Estate) -> dict[str, set[str]]:
    """The egress plane: constants passed to `j.emit(`, from every non-test Go file."""
    return {"scopyx": go_producer_types(estate, "scopyx", calls=("j.emit",))}




def _idryx(estate: E.Estate) -> dict[str, set[str]]:
    """idryx writes its findings as event.Event literals, from every non-test Go file."""
    return {"idryx": go_producer_types(estate, "idryx", event_literals=True)}




def _qryx(estate: E.Estate) -> dict[str, set[str]]:
    """qryx writes its findings as event.Event literals, from every non-test Go file."""
    return {"qryx": go_producer_types(estate, "qryx", event_literals=True)}






def _wardryx(estate: E.Estate) -> dict[str, set[str]]:
    """Every type the wardryx tree writes, through either of its two helpers.

    `s.emit(` writes an event that carries no decision. `s.recordDecision(` writes
    one that does, and W2a moved `policy_allow` and `approval_requested` onto it, so
    a search that read only `s.emit(` reported both as never emitted. Both helpers
    take the event type as their first argument.

    Every non-test `.go` file under `internal/` and `cmd/` is read, not
    `internal/api/api.go` alone. wardryx's identity-mismatch emit sits in
    `internal/api/agent_token.go`, with its constant declared beside it. Go scopes a
    constant to its package, so each directory is resolved on its own.
    """
    return {"wardryx": go_producer_types(estate, "wardryx", calls=("s.emit", "s.recordDecision"))}




def _keyryx(estate: E.Estate) -> dict[str, set[str]]:
    """The witness writes each finding through `t.find(`, from every non-test Go file.

    Only the witness is a producer at origin/main: the custody side writes no
    event, and 6.2 declares its `key_*` types ahead of it.
    """
    return {"keyryx": go_producer_types(estate, "keyryx", calls=("t.find",))}




def _mockryx(estate: E.Estate) -> dict[str, set[str]]:
    """mockryx writes its events as event.Event literals, from every non-test Go file."""
    return {"mockryx": go_producer_types(estate, "mockryx", event_literals=True)}




def _vouchryx(estate: E.Estate) -> dict[str, set[str]]:
    """vouchryx names its types at the CALL SITES, not in a `Type:` field.

    The types are the literals handed to its `s.emit(` helper, read from every
    non-test Go file under internal/ and cmd/: the delegation emits sit in
    agents.go and xaa.go as well as api.go. Its source is the constant in api.go.
    """
    text = estate.read_text("vouchryx", "internal/api/api.go")
    m = re.search(r"const\s+Source\s*=\s*\"([a-z0-9-]+)\"", text)
    if not m:
        raise E.Missing('vouchryx internal/api/api.go: no `const Source = "..."`')
    return {m.group(1): go_producer_types(estate, "vouchryx", calls=("s.emit",))}




def _costcrew(estate: E.Estate) -> dict[str, set[str]]:
    """costcrew DECLARES its wire types, and its own suite holds the declaration.

    Every other producer here names its types somewhere a reader can resolve: a
    composite literal, or one `emit` helper taking a string literal. costcrew
    has neither shape. Its kinds are literals at nine HTTP handlers and two
    background paths, ONE of them built as `"anomaly_" + string(to)` from a
    state value, and TWO of them renamed on the way out by `internal/stack/
    vocabulary.go` before they reach the envelope.

    A regular expression over that would be inference, and inference is the
    thing this gate's own history warns about: seven names were reserved for
    idryx that were wrong in both directions, in both directions, because
    somebody wrote down what a producer looked like it did.

    So this reads a list the producer states, `stack.WireTypes`, and the
    producer's own test (`TestWireTypesIsExactlyWhatTheCallSitesProduce`) is
    what holds that list equal to its call sites with the translation applied.
    The division is SPEC 6.2's own, which says of idryx's detector count that
    "what knows is idryx's own `scripts/detectors-complete.sh`".

    What this check still owns is the comparison against the registry. What it
    delegates is reading Go it cannot read without guessing.
    """
    text = estate.read_text("costcrew", "internal/stack/types.go")
    if "func WireTypes()" not in text:
        raise E.Missing(
            "costcrew internal/stack/types.go: no `func WireTypes()`, so the "
            "declaration this check reads is gone and nothing was compared"
        )
    block = re.search(r"var wireTypes = \[\]string\{(.*?)\n\}", text, re.S)
    if not block:
        raise E.Missing(
            "costcrew internal/stack/types.go: `var wireTypes = []string{...}` "
            "did not parse, so this producer's types could not be read"
        )
    types = set(re.findall(r'"([a-z][a-z0-9_]*)"', block.group(1)))
    if not types:
        raise E.Missing(
            "costcrew internal/stack/types.go: `wireTypes` holds no type, so "
            "the registry was compared against nothing"
        )

    # The list is a claim, and the producer's own test is what makes it one
    # worth reading. A gate that trusted the list without checking the test is
    # still there would keep passing after somebody deleted the test.
    held = estate.read_text("costcrew", "internal/stack/wiretypes_test.go")
    if "TestWireTypesIsExactlyWhatTheCallSitesProduce" not in held:
        raise E.Missing(
            "costcrew declares its wire types and the test that held that "
            "declaration to its call sites is gone, so the list is now "
            "somebody's memory rather than a reading of the code"
        )

    source = estate.read_text("costcrew", "internal/stack/stack.go")
    m = re.search(r'const\s+Source\s*=\s*"([a-z0-9-]+)"', source)
    if not m:
        raise E.Missing('costcrew internal/stack/stack.go: no `const Source = "..."`')
    return {m.group(1): types}


def _heraldyx(estate: E.Estate) -> dict[str, set[str]]:
    """heraldyx names its source in one constant and writes event literals."""
    text = estate.read_text("heraldyx", "internal/record/record.go")
    m = re.search(r"const\s+Source\s*=\s*\"([a-z0-9-]+)\"", text)
    if not m:
        raise E.Missing("heraldyx internal/record/record.go: no `const Source = \"...\"`")
    return {m.group(1): go_producer_types(estate, "heraldyx", event_literals=True)}




def _genaryx(estate: E.Estate) -> dict[str, set[str]]:
    """genaryx writes its console lines with literal `source` and `type` inserts.

    Every non-test .rs under crates/ is read. A file that inserts a literal type
    takes its source from the same file. A type inserted from a variable is not
    read here: those are the demo and mock generators, which replay other
    products' envelopes or build display rows rather than emit genaryx's own. They
    are named in the report, not counted as agreement.
    """
    out: dict[str, set[str]] = {}
    for path in estate.list_files("genaryx", ".rs"):
        if not path.startswith("crates/") or _RUST_TEST.search(path):
            continue
        try:
            text = estate.read_text("genaryx", path)
        except E.Missing as m:
            raise _measured_nothing("genaryx", f"{m}. That file's emits were not read") from None
        types = _RUST_TYPE_INSERT.findall(text)
        if not types:
            continue
        sources = set(_RUST_SOURCE_INSERT.findall(text))
        if len(sources) != 1:
            raise E.Missing(
                f"genaryx {path}: inserts a literal type but {len(sources)} literal "
                f"source(s) in the same file, so the source those types belong to "
                f"is not read"
            )
        out.setdefault(sources.pop(), set()).update(types)
    if not out:
        raise _measured_nothing("genaryx", "no non-test Rust file under crates/ inserts a literal type")
    return out




def _taipan(estate: E.Estate) -> dict[str, set[str]]:
    """`taipan demo` writes envelopes ATTRIBUTED TO OTHER PLANES.

    It is not a producer of its own source: every pair it writes claims another
    product wrote it. That makes it the one place in the estate where a wrong
    attribution is undetectable from inside the repo that owns the name.
    """
    text = estate.read_text("taipan", "src/commands/demo.rs")
    m = re.search(r"SAMPLE_EVENTS\s*:\s*&\[\([^)]*\)\]\s*=\s*&\[(.*?)\]\s*;", text, re.DOTALL)
    if not m:
        raise E.Missing("taipan src/commands/demo.rs: no SAMPLE_EVENTS array matched")
    pairs = re.findall(r"\(\s*\"([a-z0-9_-]+)\"\s*,\s*\"([a-z0-9_]+)\"", m.group(1))
    if not pairs:
        raise E.Missing("taipan src/commands/demo.rs: SAMPLE_EVENTS matched no (source, type) pairs")
    out: dict[str, set[str]] = {}
    for source, etype in pairs:
        out.setdefault(source, set()).add(etype)
    return out


# `owns` is the list of registry sources this repo is the producer OF. A repo
# that writes under a source it does not own is a REPLAYER: it can be wrong
# about somebody else's vocabulary, and it can never be the thing that makes a
# registry row true. taipan is the only one today, and the distinction matters:
# without it, `taipan demo` writing three of tokenfuse's fourteen types would
# read as tokenfuse failing to emit the other eleven.
PRODUCERS: dict[str, dict] = {
    "tokenfuse": {
        "writer": ("crates/core/src/agent_event.rs", "pub fn emit"),
        "extract": _tokenfuse,
        "owns": ["tokenfuse"],
    },
    "engram": {
        "writer": ("engram/events.py", "class EventLog"),
        "extract": _engram,
        "owns": ["engram"],
    },
    "verdryx": {
        "writer": ("verdryx/events.py", "class EventLog"),
        "extract": _verdryx,
        "owns": ["verdryx"],
    },
    "scopyx": {
        "writer": ("internal/record/record.go", "event.NewChainedWriter"),
        "extract": _scopyx,
        "owns": ["scopyx"],
    },
    "typryx": {
        "writer": ("internal/record/record.go", "event.NewChainedWriter"),
        "extract": _typryx,
        "owns": ["typryx"],
    },
    # Not a repository of its own: the verifier is a command inside the shared
    # module, so the entry is keyed by the module's repository.
    "agent-stack-go": {
        "writer": ("cmd/agent-conform/watchdir.go", "event.NewChainedWriter"),
        "extract": _agent_conform,
        "owns": ["agent-conform"],
    },
    "qryx": {
        "writer": ("internal/exporter/exporter.go", "event.NewChainedWriter"),
        "extract": _qryx,
        "owns": ["qryx"],
    },
    "vouchryx": {
        "writer": ("internal/api/api.go", "const Source"),
        "extract": _vouchryx,
        "owns": ["vouchryx"],
    },
    "wardryx": {
        "writer": ("cmd/wardryx/main.go", "event.NewChainedWriter"),
        "extract": _wardryx,
        "owns": ["wardryx"],
    },
    "mockryx": {
        "writer": ("internal/events/events.go", "event.NewChainedWriter"),
        "extract": _mockryx,
        "owns": ["mockryx"],
    },
    "heraldyx": {
        "writer": ("internal/record/record.go", "event.NewChainedWriter"),
        "extract": _heraldyx,
        "owns": ["heraldyx"],
    },
    "costcrew": {
        "writer": ("internal/stack/stack.go", "const Source"),
        "extract": _costcrew,
        "owns": ["costcrew"],
    },
    "genaryx": {
        "writer": ("crates/core/src/command.rs", "\"source\""),
        "extract": _genaryx,
        "owns": ["console"],
    },
    "taipan": {
        "writer": ("src/commands/demo.rs", "SAMPLE_EVENTS"),
        "extract": _taipan,
        "owns": [],
    },
    # idryx had no writer entry until 2026-08-10, on purpose: 6.2 recorded it as
    # RESERVED and the reserved branch looked for a writer precisely because one
    # appearing would make the registry wrong in the other direction. It
    # appeared, the registry was corrected in the same wave, and this is now an
    # ordinary producer row.
    #
    # The RESERVED machinery below stays. No row uses it today, and that is the
    # point: deleting it would mean the next reserved row ships with nothing
    # checking it, and the case it guards (a row that says "do not expect these"
    # while a writer quietly exists) is the one that cost the most to find.
    "idryx": {
        "writer": ("internal/events/events.go", "event.NewWriter"),
        "extract": _idryx,
        "owns": ["idryx"],
    },
    "keyryx": {
        "writer": ("internal/witness/witness.go", "event.NewChainedWriter"),
        "extract": _keyryx,
        "owns": ["keyryx"],
    },
}

# Which repo owns which registry `source`, derived from the table above so the
# two cannot disagree.
SOURCE_REPO = {
    source: repo for repo, spec in PRODUCERS.items() for source in spec["owns"]
}

# Every Go file in a repo that could open a writer. Used only for idryx, where
# the claim being checked is that NO event-writing path exists.
WRITER_CALLS = ("event.NewChainedWriter", "event.NewWriter")


# Markers a Go or Python producer cannot avoid: CALLING the writer.
#
# Package-qualified on purpose. A bare `NewChainedWriter(` also matches
# agent-stack-go, which DEFINES it, and a library that defines a writer emits
# nothing: the first version of this flagged agent-stack-go as an undeclared
# producer, which is the check confusing the tool for its user.
#
# Rust producers build their own writers and are declared rather than
# discovered, which is a real limit and is stated in `discover_producers`.
WRITER_MARKERS = ("event.NewChainedWriter(", "event.NewWriter(", "class EventLog")

_TEST_PATH = re.compile(
    r"(^|/)tests?/ | _test\.(go|py)$ | (^|/)test_[^/]+\.py$ | \.test\.(ts|tsx)$",
    re.X,
)


def discover_producers(estate: E.Estate, c: E.Check) -> None:
    """Find a repository that WRITES events and that PRODUCERS does not declare.

    The dict above is written by hand, and a hand-written list of subjects is
    itself a copy of the truth that nothing watches. That is not a hypothetical
    here: vouchryx wrote three types from the day it existed and was absent from
    PRODUCERS, so this check reported clean on eight producers while a ninth
    emitted types 6.2 did not register. C2 had the same defect on the same day,
    about vendored schema copies.

    It cannot be closed the way C2's was. Each producer needs a bespoke
    extractor because each names its types differently, so the DECLARATIONS
    stay. What is discovered is the QUESTION: is there a producer nobody
    declared. The answer then needs a person to write the extractor, which is
    the right amount of work to ask for.

    THE LIMIT, stated rather than left to be found: it looks for the writer
    constructors a Go or Python producer must call. tokenfuse and genaryx are
    Rust and build their own, so they are declared and not discovered, and a new
    RUST producer would be invisible to this. Go-first is the estate's rule for
    new services, which is why this covers the likely case rather than every
    case, and why saying so matters.
    """
    declared = set(PRODUCERS)
    searched = 0
    undeclared = 0
    for repo in sorted(estate.repos):
        hits: list[str] = []
        for marker in WRITER_MARKERS:
            try:
                hits += estate.grep_files(repo, marker)
            except E.Unavailable as u:
                c.unavailable(
                    f"c4.search-unavailable:{repo}",
                    f"{repo} could not be read in this run ({u.reason}), so it was "
                    f"not searched for an undeclared producer.",
                )
                hits = []
                break
            except E.Missing:
                hits = []
                break
        else:
            searched += 1
        real = [h for h in hits if h.endswith((".go", ".py")) and not _TEST_PATH.search(h)]
        if not real or repo in declared:
            continue
        undeclared += 1
        c.drift(
            "c4.producer-undeclared",
            f"{repo} constructs an agent-event writer and PRODUCERS does not "
            f"declare it, so nothing compares what it emits against 6.2.",
            [
                f"  writer: {estate.where(repo, real[0])}",
                "",
                "Every type this repository emits is currently unchecked against the",
                "registry, and this gate reports on the producers it knows while",
                "saying nothing about this one. That is not a smaller answer, it is",
                "a confident one about the wrong set.",
                "",
                "Add an entry to PRODUCERS with an extractor that reads how THIS",
                "producer names its types. They all differ, which is why the list",
                "cannot simply be replaced by this search.",
            ],
        )

    # Only when nothing drifted. Saying "every one found is declared" beside a
    # finding that one is not would be two answers to one question, and the
    # reassuring one is the one a reader remembers.
    if searched and undeclared == 0:
        c.ok(
            "c4.producers-all-declared",
            f"{searched} repositories searched for an agent-event writer; every one "
            f"found is declared above.",
        )


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C4", "the 6.2 event-type registry against the real producers", estate)

    try:
        registry, reserved = parse_registry(estate.read_text(SPEC_REPO, SPEC_PATH))
    except E.Unavailable as u:
        c.unavailable(
            "c4.spec-unavailable",
            f"{SPEC_REPO} could not be read in this run ({u.reason}), so nothing "
            f"was compared against the registry.",
        )
        return c
    except E.Missing as m:
        c.missing("c4.registry-unparsed", str(m))
        return c

    c.note(
        f"SPEC 6.2 registers {sum(len(v) for v in registry.values())} type strings "
        f"across {len(registry)} sources; {len(reserved)} row(s) marked RESERVED: "
        f"{', '.join(sorted(reserved)) or 'none'}."
    )

    # -- what each producer actually emits ---------------------------------
    # source -> {repo: types}, and separately the replayers, which can only
    # ever be wrong about attribution and never make a registry row true.
    emitted: dict[str, dict[str, set[str]]] = {}
    replayed: dict[str, dict[str, set[str]]] = {}
    for repo, spec in sorted(PRODUCERS.items()):
        if spec["extract"] is None:
            continue
        try:
            estate.dir_of(repo)
        except E.Unavailable as u:
            c.unavailable(
                f"c4.producer-unavailable:{repo}",
                f"{repo} could not be read in this run ({u.reason}). Whatever it "
                f"emits, and whether the registry knows about it, is unmeasured "
                f"here.",
            )
            continue
        wfile, wneedle = spec["writer"]
        try:
            wtext = estate.read_text(repo, wfile)
        except E.Missing:
            c.missing(
                "c4.writer-file-gone",
                f"{repo} is recorded here as writing events from {wfile}, and that "
                f"file is not there. Either the producer moved or it stopped "
                f"producing, and the two need different fixes.",
            )
            continue
        if wneedle not in wtext:
            c.missing(
                "c4.writer-anchor-gone",
                f"{estate.where(repo, wfile)} no longer contains `{wneedle}`, which "
                f"is how this check knows {repo} has an event-writing code path. "
                f"Its types below, if any, were read from a file that may no "
                f"longer emit.",
            )
        try:
            got = spec["extract"](estate)
        except E.Missing as m:
            c.missing(
                "c4.producer-unreadable",
                f"{repo}: {m}. This producer's types could not be read, so nothing "
                f"below says whether they match the registry. A producer this "
                f"check cannot parse is a hole, not a pass.",
            )
            continue
        for source, types in got.items():
            bucket = emitted if source in spec["owns"] else replayed
            bucket.setdefault(source, {})[repo] = types

    # -- direction one: the registry claims a producer ----------------------
    for source in sorted(registry):
        repo = SOURCE_REPO.get(source, source)
        if source in reserved:
            # The claim is the opposite one: nothing is emitted. Verify it.
            try:
                estate.dir_of(repo)
            except E.Unavailable as u:
                c.unavailable(
                    f"c4.reserved-unavailable:{repo}",
                    f"{repo} could not be read in this run ({u.reason}), so 6.2's "
                    f"RESERVED claim about it was not checked.",
                )
                continue
            except E.Missing as m:
                # A RESERVED claim about a repository estate.json does not
                # register cannot be checked at all. That is a finding, not an
                # uncaught exception: the runner would abort and report nothing.
                c.missing(
                    "c4.reserved-unregistered",
                    f"6.2 records `{source}` as RESERVED, but estate.json has no entry "
                    f"for `{repo}`, so nothing here knows where that claim is checked "
                    f"({m}). Register the repository, or the claim is unverifiable.",
                    [f"  registry: {E.REPO_ROOT / 'estate.json'}"],
                )
                continue
            try:
                writers = writer_sites(estate, repo)
            except E.Missing as m:
                c.missing(
                    "c4.reserved-unverifiable",
                    f"6.2 records `{source}` as RESERVED, not emitted today, and "
                    f"nothing here could check that claim: {m}.",
                )
                continue
            if writers:
                c.drift(
                    "c4.reserved-source-emits",
                    f"6.2 records `{source}` as RESERVED, not emitted today, and "
                    f"{repo} has an event-writing code path.",
                    [
                        f"  registry: {estate.where(SPEC_REPO, SPEC_PATH)} section 6.2",
                        f"  producer: {', '.join(writers)}",
                        "A reserved row tells consumers not to expect these events.",
                    ],
                )
            else:
                c.ok(
                    "c4.reserved-holds",
                    f"6.2 records `{source}` as RESERVED and {repo} opens no event "
                    f"writer anywhere, which is what the row says.",
                )
            continue

        if source not in emitted:
            c.drift(
                "c4.registered-source-silent",
                f"6.2 registers `{source}` with "
                f"{len(registry[source])} type(s) and no producer for it could be "
                f"read in this run.",
                [
                    f"  registry: {estate.where(SPEC_REPO, SPEC_PATH)} section 6.2",
                    f"  producer: expected in {repo}, nothing found",
                    "A row here is a claim that the source writes those types today.",
                ],
            )
            continue

        for repo_name, types in sorted(emitted[source].items()):
            unbacked = sorted(registry[source] - types)
            if unbacked:
                c.drift(
                    "c4.registered-type-not-emitted",
                    f"6.2 lists {len(unbacked)} type(s) under `{source}` that no "
                    f"emit site in {repo_name} produces: {', '.join(unbacked)}.",
                    [
                        f"  registry: {estate.where(SPEC_REPO, SPEC_PATH)} section 6.2, "
                        f"row `{source}`",
                        f"  producer: {repo_name}, "
                        f"{estate.where(repo_name, PRODUCERS[repo_name]['writer'][0])}",
                        "A consumer that built a handler for one of these waits forever.",
                    ],
                )
            else:
                c.ok(
                    "c4.row-backed",
                    f"every one of the {len(registry[source])} types 6.2 lists under "
                    f"`{source}` appears at an emit site in {repo_name}.",
                )

    # -- direction two: a producer emits what nobody registered -------------
    # The more valuable direction, and the one nothing else in the estate can
    # see. Both real producers and replayers are measured here: a replayer
    # writing a pair the registry does not carry is claiming another product
    # emits something it does not.
    both: dict[str, dict[str, set[str]]] = {}
    for bucket in (emitted, replayed):
        for source, per_repo in bucket.items():
            both.setdefault(source, {}).update(per_repo)

    for source in sorted(both):
        for repo_name, types in sorted(both[source].items()):
            owner = repo_name in PRODUCERS and source in PRODUCERS[repo_name]["owns"]
            role = "emits" if owner else "writes lines attributed to"
            site = estate.where(repo_name, PRODUCERS[repo_name]["writer"][0])
            if source not in registry:
                c.drift(
                    "c4.unregistered-source",
                    f"{repo_name} {role} `source: \"{source}\"`, and 6.2 has no row "
                    f"for that source at all.",
                    [
                        f"  producer: {site}",
                        f"  types:    {', '.join(sorted(types))}",
                        f"  registry: {estate.where(SPEC_REPO, SPEC_PATH)} section 6.2",
                        "Nothing tells a consumer these events exist. 6.2 is the only",
                        "statement of which product writes what, and it does not know.",
                    ],
                )
                continue
            extra = sorted(types - registry[source])
            if extra:
                c.drift(
                    "c4.unregistered-type",
                    f"{repo_name} {role} {len(extra)} type(s) under `{source}` that "
                    f"6.2 does not list: {', '.join(extra)}.",
                    [
                        f"  producer: {site}",
                        f"  registry: {estate.where(SPEC_REPO, SPEC_PATH)} section 6.2, "
                        f"row `{source}`",
                        "6.4 allows new types inside a source, and 6.2 is where a",
                        "reader finds out they exist.",
                    ],
                )
            elif not owner:
                c.ok(
                    "c4.attribution-clean",
                    f"{repo_name} writes {len(types)} type(s) under `{source}`, a "
                    f"source it does not own, and 6.2 registers every one of them.",
                )

    discover_producers(estate, c)
    return c


def writer_sites(estate: E.Estate, repo: str) -> list[str]:
    """Every file in the repo that opens an envelope writer.

    Go only, and it says so rather than returning an empty list: the calls it
    looks for are the ones agent-stack-go's `event` package exposes, so this
    can only ever answer the question for a Go repository. The one RESERVED
    row today (idryx) is Go. A reserved row for a Rust or Python producer
    would get "no writer found" from a scan that never knew how to look, which
    is the exact shape of silent success this repository exists to prevent.

    Tests are excluded: a test may write whatever it needs, and a producer is
    a production path.
    """
    files = [f for f in estate.list_files(repo) if f.endswith(".go")]
    if not files:
        raise E.Missing(
            f"{repo} has no Go files, and looking for an event writer is the "
            f"only thing this check knows how to do. Whether it emits is "
            f"unknown here, which is not the same as it emitting nothing"
        )
    found = []
    for f in files:
        if f.endswith("_test.go"):
            continue
        try:
            text = estate.read_text(repo, f)
        except E.Missing as m:
            # A file the repository lists and this run cannot read leaves the
            # scan incomplete, and an incomplete scan that reports "no writer
            # anywhere" is the loudest possible version of the mistake this
            # whole check is about. It used to `continue` here.
            raise E.Missing(
                f"{repo} lists {f} and it could not be read ({m}), so the scan "
                f"for an event writer did not cover the whole repository"
            ) from None
        if any(call in text for call in WRITER_CALLS):
            found.append(f)
    return found


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
