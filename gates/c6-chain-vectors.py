#!/usr/bin/env python3
"""C6: the pinned RFC 8785 canonicalization and chain-hash vectors, in every
language that copies them.

WHY

agent-stack-go/event/testdata/chain-vectors.json holds three events, each with
its JCS canonical serialization and its SPEC 6.5 chain hash. Four
implementations are supposed to reproduce those bytes: Go, Rust in tokenfuse,
and Python in engram and in verdryx. Three of the four hold the numbers as
LITERALS in their own test suites, retyped by hand.

That makes it a real drift surface, not a theoretical one. Change the Go
canonicalization, or the vector file, and the Rust and Python suites go on
passing against the old numbers. Every one of them would report green while
the four implementations produced three different chains. The event log's
tamper evidence is exactly the guarantee that would quietly stop being true.

WHAT IS COMPARED

Per vector, the canonical string and the hash. The event object itself is not
compared: each copy expresses it in its own language's literal syntax, and
canonicalization is what turns them into the same bytes. The canonical string
IS the comparison, and it is compared exactly, including the non-ASCII data
value the second vector carries specifically to catch an encoding difference.

The Go constants are compared too, although agent-stack-go's own
TestVectorFileMatchesPinnedConstants already keeps them and the file together.
Duplicating one in-repo test costs nothing and means this check does not
depend on a test in another repository still existing.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402

CANON_REPO = "agent-stack-go"
CANON_PATH = "event/testdata/chain-vectors.json"


def canonical_vectors(text: str) -> list[tuple[str, str]]:
    data = json.loads(text)
    vectors = data.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        raise E.Missing(
            f"{CANON_PATH} has no non-empty 'vectors' list, so there is nothing "
            f"for the four implementations to be compared against"
        )
    out = []
    for i, v in enumerate(vectors, 1):
        if "canonical" not in v or "hash" not in v:
            raise E.Missing(
                f"{CANON_PATH} vector {i} has no 'canonical' or no 'hash' field"
            )
        out.append((v["canonical"], v["hash"]))
    return out


# ------------------------------------------------------------ the copies


def python_copy(text: str, path: str) -> list[tuple[str, str]]:
    """_VEC_CANONICAL_N and _VEC_HASH_N, read with ast.

    The canonicals are written as implicitly concatenated string literals over
    several lines, which `ast.literal_eval` joins exactly and a regular
    expression would not.
    """
    tree = ast.parse(text)
    canon: dict[int, str] = {}
    hashes: dict[int, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if not isinstance(t, ast.Name):
                continue
            m = re.fullmatch(r"_VEC_(CANONICAL|HASH)_(\d+)", t.id)
            if not m:
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                raise E.Missing(
                    f"{path}: {t.id} is not a literal this check can evaluate"
                ) from None
            (canon if m.group(1) == "CANONICAL" else hashes)[int(m.group(2))] = value
    if not canon or not hashes:
        raise E.Missing(
            f"{path} has no _VEC_CANONICAL_n / _VEC_HASH_n assignments. Those "
            f"names are the pinned copy; finding none is a parse that failed, "
            f"not a copy that agrees"
        )
    n = max(max(canon), max(hashes))
    return [(canon.get(i, ""), hashes.get(i, "")) for i in range(1, n + 1)]


def go_copy(text: str, path: str) -> list[tuple[str, str]]:
    """vecCn (raw backtick string) and vecHn (quoted) in the const block."""
    canon = {
        int(n): v for n, v in re.findall(r"vecC(\d+)\s*=\s*`([^`]*)`", text)
    }
    hashes = {
        int(n): v for n, v in re.findall(r"vecH(\d+)\s*=\s*\"([^\"]*)\"", text)
    }
    if not canon or not hashes:
        raise E.Missing(
            f"{path} has no vecCn / vecHn constants. That const block is the Go "
            f"copy of the vectors"
        )
    n = max(max(canon), max(hashes))
    return [(canon.get(i, ""), hashes.get(i, "")) for i in range(1, n + 1)]


def rust_copy(text: str, path: str, fn: str) -> list[tuple[str, str]]:
    """The r#"..."# canonicals and "sha256:..." hashes inside one test fn.

    Anchored on the function so the many other raw strings in the file cannot
    join the list.
    """
    start = text.find(fn)
    if start < 0:
        raise E.Missing(
            f"{path} has no `{fn}`, which is where the pinned vectors are "
            f"asserted. The anchor is gone, so nothing was compared"
        )
    end = text.find("\n    }", start)
    body = text[start : end if end > 0 else len(text)]
    canon = re.findall(r'r#"(\{.*?\})"#', body, re.DOTALL)
    hashes = re.findall(r'"(sha256:[0-9a-f]{64})"', body)
    if not canon or not hashes:
        raise E.Missing(
            f"{path}: `{fn}` matched no r#\"...\"# canonical strings or no "
            f"sha256: hashes"
        )
    n = max(len(canon), len(hashes))
    return [
        (canon[i] if i < len(canon) else "", hashes[i] if i < len(hashes) else "")
        for i in range(n)
    ]


# The extractor for each language a copy can be written in, chosen by suffix.
#
# The LIST of copies used to live here: four (repo, path, purpose, extractor)
# tuples, hand-written. That is the defect shape this suite found nine times in
# two days, and it goes stale in the one direction that matters: a fifth
# language pins the vectors, nobody adds a row, and this gate reports agreement
# among the four it knew about.
#
# Copies are now FOUND, by the thing that makes a copy a copy: it quotes one of
# the canonical hashes. A 64-hex digest appears nowhere by accident, so any file
# carrying one is either the canonical or something pinning it.
#: How many copies of the vectors the estate is supposed to hold. Stated, and
#: compared against what is FOUND, for the reason at the check itself: discovery
#: cannot notice a copy that went away.
EXPECTED_COPIES = 4

EXTRACTORS: dict[str, callable] = {
    ".go": lambda text, path: go_copy(text, path),
    ".rs": lambda text, path: rust_copy(text, path, "fn cross_language_chain_vectors_pin"),
    ".py": lambda text, path: python_copy(text, path),
}


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C6", "cross-language chain vectors, every copy against the file", estate)

    try:
        canon = canonical_vectors(estate.read_text(CANON_REPO, CANON_PATH))
    except E.Unavailable as u:
        c.unavailable(
            "c6.canonical-unavailable",
            f"{CANON_REPO} could not be read in this run ({u.reason}), so no "
            f"copy of the vectors was compared against anything.",
        )
        return c
    except E.Missing as m:
        c.missing(
            "c6.canonical-gone",
            f"the pinned vector file is unusable: {m}. Four implementations claim "
            f"to reproduce it and none of them can be checked while it is gone.",
        )
        return c

    c.note(f"{CANON_PATH} pins {len(canon)} vectors.")

    # Every file in the estate quoting ANY canonical hash, which is what makes
    # a file a copy. The canonical itself is excluded by path.
    #
    # Every hash and not the first one, because the first draft probed with one
    # and the harness caught it: a mutation that changed THAT hash in a copy
    # made the copy vanish from the search instead of disagreeing, so the check
    # written to catch a drifting hash was blind to a drift in the hash it
    # searched by.
    probes = [h for _, h in canon]
    copies: list[tuple[str, str]] = []
    for repo in estate.repos:
        try:
            hits: list[str] = []
            for probe in probes:
                for hit in estate.grep_files(repo, probe):
                    if hit not in hits:
                        hits.append(hit)
        except E.Unavailable as u:
            c.unavailable(
                f"c6.copy-unavailable:{repo}",
                f"{repo} could not be read in this run ({u}), so any copy it "
                "holds was not compared.",
            )
            continue
        except E.Missing:
            continue
        for relpath in hits:
            if repo == CANON_REPO and relpath == CANON_PATH:
                continue
            copies.append((repo, relpath))

    # How many copies there are supposed to be.
    #
    # Discovery cannot miss a NEW copy and cannot notice a REMOVED one: a
    # language that stops pinning the vectors simply is not found, and its
    # implementation goes unchecked in silence. The harness caught exactly that
    # when the hand-written list came out.
    #
    # So the COUNT is stated and the discovered number must equal it. It is a
    # number somebody has to edit deliberately, which is the same bargain
    # `readme-numbers.sh` makes and the reason it works: removing a copy is
    # allowed, doing it silently is not.
    if copies and len(copies) != EXPECTED_COPIES:
        c.drift(
            "c6.copy-count-differs",
            f"{len(copies)} copy/copies of the chain vectors were found and "
            f"this gate expects {EXPECTED_COPIES}",
            [f"{r}/{p}" for r, p in copies]
            + [
                "A copy that went away is an implementation nobody is "
                "comparing any more. If that is intended, change "
                "EXPECTED_COPIES in the same commit, which is the point.",
            ],
        )

    if not copies:
        c.missing(
            "c6.no-copies",
            f"nothing in the estate quotes `{probe[:24]}...`, so this gate "
            "measured nothing. Four implementations are supposed to pin these "
            "vectors; finding none means the discovery broke or they all went "
            "away, and both need a person.",
        )
        return c

    for repo, relpath in copies:
        purpose = f"the {pathlib.PurePath(relpath).suffix or '?'} copy in {relpath}"
        extract = EXTRACTORS.get(pathlib.PurePath(relpath).suffix)
        if extract is None:
            c.drift(
                f"c6.copy-unreadable:{repo}",
                f"{repo}/{relpath} pins the chain vectors and this gate has no "
                f"extractor for `{pathlib.PurePath(relpath).suffix}`",
                [
                    "A copy it cannot read is a copy it cannot compare, and "
                    "reporting agreement about the ones it can read would be "
                    "the silence this check exists to end.",
                ],
            )
            continue
        try:
            text = estate.read_text(repo, relpath)
        except E.Unavailable as u:
            c.unavailable(f"c6.copy-unavailable:{repo}", str(u))
            continue
        except E.Missing:
            # Unreachable by construction: `relpath` came out of a grep over
            # this same tree, so the file is there. It had its own finding while
            # the copies were a hand-written list, because then a listed path
            # could simply not exist. Discovery removed the case, and a FAIL
            # path nothing can produce is a label rather than a check, so it is
            # gone rather than kept as decoration.
            continue

        try:
            copy = extract(text, f"{repo}/{relpath}")
        except E.Missing as m:
            c.missing("c6.copy-unparsed", str(m))
            continue

        if len(copy) != len(canon):
            c.drift(
                "c6.vector-count-differs",
                f"{repo} pins {len(copy)} vectors and {CANON_PATH} has {len(canon)}.",
                [
                    f"  canonical: {estate.where(CANON_REPO, CANON_PATH)}",
                    f"  copy:      {estate.where(repo, relpath)} ({purpose})",
                    "A vector added to the file and not to a copy is a case that",
                    "language is not pinned on, which is the whole point of the file.",
                ],
            )

        for i, (want_c, want_h) in enumerate(canon, 1):
            if i > len(copy):
                break
            got_c, got_h = copy[i - 1]
            if got_c != want_c:
                c.drift(
                    "c6.canonical-differs",
                    f"{repo} vector {i}: the pinned RFC 8785 canonical string does "
                    f"not match {CANON_PATH}.",
                    [
                        f"  canonical: {estate.where(CANON_REPO, CANON_PATH)}",
                        f"  copy:      {estate.where(repo, relpath)} ({purpose})",
                        f"  file says: {want_c}",
                        f"  copy says: {got_c}",
                        "The canonical bytes are the hash input. Two implementations",
                        "that canonicalize differently produce two different chains",
                        "from the same events, and each verifies its own.",
                    ],
                )
            else:
                c.ok(
                    "c6.canonical-matches",
                    f"{repo} vector {i} canonical string matches the file.",
                )
            if got_h != want_h:
                c.drift(
                    "c6.hash-differs",
                    f"{repo} vector {i}: the pinned chain hash does not match "
                    f"{CANON_PATH}.",
                    [
                        f"  canonical: {estate.where(CANON_REPO, CANON_PATH)}",
                        f"  copy:      {estate.where(repo, relpath)} ({purpose})",
                        f"  file says: {want_h}",
                        f"  copy says: {got_h}",
                        "This is the value the NEXT event carries as prev_hash, so a",
                        "difference here breaks the chain across a language boundary.",
                    ],
                )
            else:
                c.ok(
                    "c6.hash-matches",
                    f"{repo} vector {i} chain hash matches the file.",
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
