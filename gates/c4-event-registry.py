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
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

SPEC_REPO = "agent-passport"
SPEC_PATH = "SPEC.md"


# --------------------------------------------------------------- the registry


def parse_registry(spec: str) -> tuple[dict[str, set[str]], set[str]]:
    """Section 6.2's table: source -> set of type strings, plus reserved rows.

    The table is markdown, `| `source` | `a` . `b` . `c` |`. A row whose type
    cell begins with RESERVED is a promise about names, not a claim about a
    producer, and 6.2 says so on the row.
    """
    start = spec.find("### 6.2")
    if start < 0:
        raise E.Missing(
            f"{SPEC_PATH} has no `### 6.2` heading, which is where the event-type "
            f"registry lives. Without it this check has no statement to measure "
            f"anything against"
        )
    end = spec.find("### 6.3", start)
    section = spec[start : end if end > 0 else len(spec)]

    registry: dict[str, set[str]] = {}
    reserved: set[str] = set()
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or "`source`" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        m = re.fullmatch(r"`([a-z0-9-]+)`", cells[0])
        if not m:
            continue
        source = m.group(1)
        cell = cells[1]
        if cell.upper().startswith("RESERVED"):
            reserved.add(source)
        types = set(re.findall(r"`([a-z0-9_]+)`", cell))
        registry.setdefault(source, set()).update(types)
    if not registry:
        raise E.Missing(
            f"{SPEC_PATH} section 6.2 was found but no `source` rows could be "
            f"parsed out of it. The table's shape changed and this check is "
            f"comparing against an empty registry"
        )
    return registry, reserved


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


def go_types(text: str, consts: dict[str, str]) -> set[str]:
    """Every `Type:` field value in a composite literal, idents resolved."""
    found: set[str] = set()
    for raw in _GO_TYPE_FIELD.findall(text):
        if raw.startswith('"'):
            found.add(raw.strip('"'))
        elif raw in consts:
            found.add(consts[raw])
    return found


def go_call_first_args(text: str, call: str, consts: dict[str, str]) -> set[str]:
    """First argument of every `call(` in the text, idents resolved."""
    found: set[str] = set()
    for m in re.finditer(re.escape(call) + r"\(\s*(\"[a-z0-9_]+\"|\w+)", text):
        raw = m.group(1)
        if raw.startswith('"'):
            found.add(raw.strip('"'))
        elif raw in consts:
            found.add(consts[raw])
    return found


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


def python_emit_types(text: str, funcs: set[str]) -> set[str]:
    """Literal first arguments to the emit helpers, from the AST."""
    tree = ast.parse(text)
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        if name not in funcs:
            continue
        try:
            first = ast.literal_eval(node.args[0])
        except (ValueError, SyntaxError, TypeError):
            continue
        if isinstance(first, str) and re.fullmatch(r"[a-z0-9_]+", first):
            found.add(first)
    return found


# ----------------------------------------------------------- the producers
#
# One entry per repository that can write into the envelope. `writer` is the
# proof an event-writing code path exists at all: a file and the call that
# opens the writer. `extract` returns {source: {types}} and must raise
# E.Missing rather than return an empty set when its anchor stops matching.


def _tokenfuse(estate: E.Estate) -> dict[str, set[str]]:
    text = estate.read_text("tokenfuse", "crates/core/src/agent_event.rs")
    types = rust_match_arms(text, "pub fn as_wire_str", after="impl EventType")
    if not types:
        raise E.Missing(
            "crates/core/src/agent_event.rs: `impl EventType`'s `pub fn "
            "as_wire_str` matched no `EventType::X => \"y\"` arms"
        )
    return {"tokenfuse": types}


def _engram(estate: E.Estate) -> dict[str, set[str]]:
    types: set[str] = set()
    for f in ("engram/core.py", "engram/reflection.py"):
        types |= python_emit_types(estate.read_text("engram", f), {"emit", "_emit"})
    if not types:
        raise E.Missing(
            "engram/core.py and engram/reflection.py: no literal event type "
            "reached an emit call"
        )
    return {"engram": types}


def _verdryx(estate: E.Estate) -> dict[str, set[str]]:
    types: set[str] = set()
    for f in ("verdryx/cli.py", "verdryx/store.py", "verdryx/drift.py", "verdryx/events.py"):
        try:
            types |= python_emit_types(estate.read_text("verdryx", f), {"emit"})
        except E.Missing:
            continue
    # verdryx names its taxonomy in one place as well; a type in the severity
    # map that no call site emits is worth seeing, so both are unioned and the
    # registry comparison below reports either direction.
    ev = estate.read_text("verdryx", "verdryx/events.py")
    tree = ast.parse(ev)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "EVENT_SEVERITY":
            got = ast.literal_eval(node.value) if node.value else {}
            types |= set(got)
    if not types:
        raise E.Missing("verdryx: no event types found at any emit site or in EVENT_SEVERITY")
    return {"verdryx": types}


def _qryx(estate: E.Estate) -> dict[str, set[str]]:
    text = estate.read_text("qryx", "internal/exporter/exporter.go")
    types = go_types(text, go_consts(text))
    if not types:
        raise E.Missing("qryx internal/exporter/exporter.go: no `Type:` field resolved")
    return {"qryx": types}


def _wardryx(estate: E.Estate) -> dict[str, set[str]]:
    text = estate.read_text("wardryx", "internal/api/api.go")
    consts = go_consts(text)
    types = go_call_first_args(text, "s.emit", consts)
    if not types:
        raise E.Missing("wardryx internal/api/api.go: no `s.emit(` call resolved to a type")
    return {"wardryx": types}


def _mockryx(estate: E.Estate) -> dict[str, set[str]]:
    text = estate.read_text("mockryx", "internal/events/events.go")
    types = go_types(text, go_consts(text))
    if not types:
        raise E.Missing("mockryx internal/events/events.go: no `Type:` field resolved")
    return {"mockryx": types}


def _heraldyx(estate: E.Estate) -> dict[str, set[str]]:
    text = estate.read_text("heraldyx", "internal/record/record.go")
    m = re.search(r"const\s+Source\s*=\s*\"([a-z0-9-]+)\"", text)
    if not m:
        raise E.Missing("heraldyx internal/record/record.go: no `const Source = \"...\"`")
    types = go_types(text, go_consts(text))
    if not types:
        raise E.Missing("heraldyx internal/record/record.go: no `Type:` field resolved")
    return {m.group(1): types}


def _genaryx(estate: E.Estate) -> dict[str, set[str]]:
    text = estate.read_text("genaryx", "crates/core/src/command.rs")
    src = re.search(
        r"insert\(\s*\"source\"\.to_string\(\),\s*Value::String\(\s*\"([a-z0-9_-]+)\"", text
    )
    typ = re.search(
        r"insert\(\s*\"type\"\.to_string\(\),\s*Value::String\(\s*\"([a-z0-9_-]+)\"", text
    )
    if not src or not typ:
        raise E.Missing(
            "genaryx crates/core/src/command.rs: the source and type inserts that "
            "build the console_command line did not match"
        )
    return {src.group(1): {typ.group(1)}}


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
    "qryx": {
        "writer": ("internal/exporter/exporter.go", "event.NewChainedWriter"),
        "extract": _qryx,
        "owns": ["qryx"],
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
    # idryx has no writer entry on purpose: 6.2 records it as RESERVED, and the
    # check below looks for a writer in it precisely because a writer appearing
    # would make the registry wrong in the other direction.
    "idryx": {"writer": None, "extract": None, "owns": ["idryx"]},
}

# Which repo owns which registry `source`, derived from the table above so the
# two cannot disagree.
SOURCE_REPO = {
    source: repo for repo, spec in PRODUCERS.items() for source in spec["owns"]
}

# Every Go file in a repo that could open a writer. Used only for idryx, where
# the claim being checked is that NO event-writing path exists.
WRITER_CALLS = ("event.NewChainedWriter", "event.NewWriter")


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
