#!/usr/bin/env python3
"""C7: the agent_id rule, copied into code, still agrees with agent-passport.

WHY

C2 holds vendored schema FILES byte-identical. It cannot see a rule that was
read out of a schema once and retyped as a constant, and the estate has four of
those for one rule: SPEC.md 3.1's `agent://<trust-domain>/<name>` grammar and
the 255-byte cap the envelope puts on it.

A file copy and a constant copy fail differently, which is why this is a
separate check rather than a widening of C2. A drifted file is visible in a
diff; a drifted constant compiles, passes its own suite, and is only visible to
somebody holding both repositories open. The consequence is not cosmetic: the
copy is what decides whether an emitter warns about an id a consumer will
reject, so two copies that disagree mean two planes disagreeing about whether
the same event is well formed.

WHERE THE COPIES ARE

  agent-stack-go   passport/passport.go. The heaviest one: six repositories
                   import this module by tag, so its copy is the one a
                   disagreement propagates from.
  engram           engram/events.py
  verdryx          verdryx/events.py
  tokenfuse        crates/core/src/agent_event.rs, added when
                   TAIPANBOX/tokenfuse#190 merged 2026-08-09.

THE RUST COPY ANCHORS ON A FUNCTION, NOT A CONSTANT

The other three name their grammar: `AGENT_ID_PATTERN`, `agentURIPattern`.
tokenfuse compiles its regex inside `is_canonical_agent_id` behind a `OnceLock`,
so there is no constant to anchor on and the function name is the strongest
name available. The extractor runs from that name to the first `Regex::new` and
refuses to cross another `fn`, so a regex that moved OUT of the function breaks
the anchor loudly instead of silently comparing some other pattern in the file.

Anchoring on the bare `Regex::new` would have been shorter and wrong for the
reason below: it answers "is a pattern somewhere in this file", which reads as
agreement and is not.

ANCHORED ON NAMES, NOT ON THE LITERAL

Each extractor matches a named constant and captures whatever pattern is beside
it, rather than searching the file for the canonical literal. Searching for the
literal would answer "is the right string somewhere in this file", which reads
as agreement and is not: a file can carry the right pattern in a comment while
the code uses another. Anchoring on the name also means a rename breaks the
anchor loudly instead of quietly finding nothing.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

CANONICAL_REPO = "agent-passport"
CANONICAL = "schemas/agent-event.v0.2.schema.json"

#: repo -> (path, what the copy is for, pattern extractor, cap extractor)
COPIES: dict[str, tuple[str, str, re.Pattern[str], re.Pattern[str]]] = {
    "agent-stack-go": (
        "passport/passport.go",
        "what passport.Parse and ValidateAgentURI enforce, in the module six repos import by tag",
        re.compile(r"agentURIPattern\s*=\s*regexp\.MustCompile\(`([^`]*)`\)"),
        re.compile(r"maxURIBytes\s*=\s*(\d+)"),
    ),
    "engram": (
        "engram/events.py",
        "what is_canonical_agent_id checks before the memory plane emits",
        re.compile(r"AGENT_ID_PATTERN\s*=\s*re\.compile\(r\"([^\"]*)\"\)"),
        re.compile(r"AGENT_ID_MAX_LENGTH\s*=\s*(\d+)"),
    ),
    "tokenfuse": (
        "crates/core/src/agent_event.rs",
        "what is_canonical_agent_id checks before the spend plane emits",
        # From the function name to the first Regex::new, without crossing
        # another `fn`. See the docstring: this copy has no named constant for
        # its grammar, so the function it lives in is the anchor.
        re.compile(
            r'fn is_canonical_agent_id\b(?:(?!\bfn\b)[\s\S])*?'
            r'regex::Regex::new\(r"([^"]*)"\)'
        ),
        re.compile(r"AGENT_ID_MAX_LENGTH\s*:\s*usize\s*=\s*(\d+)"),
    ),
    "verdryx": (
        "verdryx/events.py",
        "what is_canonical_agent_id checks before the quality plane emits",
        re.compile(r"AGENT_ID_PATTERN\s*=\s*re\.compile\(r\"([^\"]*)\"\)"),
        re.compile(r"AGENT_ID_MAX_LENGTH\s*=\s*(\d+)"),
    ),
}


def canonical_rule(text: str) -> tuple[str, int]:
    """The pattern and cap the published schema states, or Missing."""
    doc = json.loads(text)
    field = (doc.get("properties") or {}).get("agent_id")
    if not isinstance(field, dict):
        raise E.Missing(
            f"{CANONICAL} declares no `agent_id` property, so the rule this "
            f"check compares against is not there to read"
        )
    pattern = field.get("pattern")
    cap = field.get("maxLength")
    if not isinstance(pattern, str) or not pattern:
        raise E.Missing(
            f"{CANONICAL}'s `agent_id` states no pattern. A copy cannot be "
            f"compared against a rule the canonical no longer makes."
        )
    if not isinstance(cap, int):
        raise E.Missing(
            f"{CANONICAL}'s `agent_id` states no maxLength. The cap is half "
            f"the rule and a check that compared only the grammar would pass "
            f"a copy that had lost it."
        )
    return pattern, cap


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C7", "the agent_id rule, copied into code", estate)

    try:
        raw = estate.read_text(CANONICAL_REPO, CANONICAL)
    except E.Unavailable as u:
        c.unavailable("c7.canonical-unread", str(u))
        return c
    except E.Missing as m:
        c.missing("c7.canonical-gone", str(m))
        return c

    try:
        pattern, cap = canonical_rule(raw)
    except E.Missing as m:
        c.missing("c7.canonical-unusable", str(m))
        return c

    c.note(f"the published rule is {pattern!r}, at most {cap} bytes.")

    for repo, (path, purpose, pattern_re, cap_re) in sorted(COPIES.items()):
        try:
            text = estate.read_text(repo, path)
        except E.Unavailable as u:
            c.unavailable(f"c7.unread:{repo}", str(u))
            continue
        except E.Missing as m:
            c.missing(f"c7.copy-gone:{repo}", str(m))
            continue

        pm = pattern_re.search(text)
        if pm is None:
            c.missing(
                "c7.anchor-gone",
                f"{estate.where(repo, path)} no longer carries a pattern this "
                f"check can find, so nothing here compared the grammar",
                [
                    f"looked for: {pattern_re.pattern}",
                    f"the copy is {purpose}",
                    "either it was renamed, in which case this check needs the "
                    "new name, or it was deleted, in which case the plane "
                    "stopped checking the rule at all",
                ],
            )
        elif pm.group(1) != pattern:
            c.drift(
                "c7.pattern-differs",
                f"{estate.where(repo, path)} enforces a different agent_id "
                f"grammar from the one agent-passport publishes",
                [
                    f"canonical: {CANONICAL_REPO}:{CANONICAL} says {pattern!r}",
                    f"copy:      {estate.where(repo, path)} says {pm.group(1)!r}",
                    f"the copy is {purpose}",
                ],
            )
        else:
            c.ok(f"c7.grammar-agrees:{repo}", f"{repo} enforces the published grammar.")

        cm = cap_re.search(text)
        if cm is None:
            c.missing(
                "c7.cap-anchor-gone",
                f"{estate.where(repo, path)} no longer carries a length cap this "
                f"check can find, so nothing here compared it",
                [
                    f"looked for: {cap_re.pattern}",
                    "the cap is half the rule: a copy enforcing only the "
                    "grammar accepts an id the envelope rejects on length",
                ],
            )
        elif int(cm.group(1)) != cap:
            c.drift(
                "c7.cap-differs",
                f"{estate.where(repo, path)} caps an agent_id at "
                f"{cm.group(1)} bytes where agent-passport says {cap}",
                [
                    f"canonical: {CANONICAL_REPO}:{CANONICAL} says {cap}",
                    f"copy:      {estate.where(repo, path)} says {cm.group(1)}",
                ],
            )
        else:
            c.ok(f"c7.cap-agrees:{repo}", f"{repo} caps an agent_id at {cap} bytes.")

    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
