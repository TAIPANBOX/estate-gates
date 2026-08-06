#!/usr/bin/env python3
"""C3: verdryx's hand-copied mirrors of tokenfuse constants still agree with
tokenfuse.

WHY

verdryx held seven of the nine Breaker block-decision wire strings. The other
two, `unit_budget_exceeded` and `identity_mismatch`, had been in tokenfuse
since 2026-07-23. For eleven days verdryx counted the avoided estimate on
those two decisions as real money, because a blocked call's `cost_microusd`
carries what was NOT spent. Both repositories were internally consistent. Both
test suites were green. The copy was correct on the day it was written and
nothing was watching it afterwards.

TWO MODES, AND THE OUTPUT SAYS WHICH

tokenfuse is publishing `contracts/tokenfuse-constants.json`, generated from
the Rust and gated by its own `scripts/constants.sh`. When that artifact is
present this check reads it, because a generated projection cannot half-match
the way a regular expression over Rust can.

When it is absent, this check parses the Rust source instead. That is the
weaker mode and it says so in its output, every run. A comparison whose reader
does not know what was compared is one somebody will quote wrongly later.

THE THREE MIRRORS

  blocked decisions   BreakerReason::as_wire_str and the BLOCKED_DECISIONS
                      array, against verdryx's _BLOCKED_DECISIONS. Compared as
                      SETS: order is not a contract, membership is.
  price book          the gateway's default price book, against verdryx's
                      PriceBook.default(). Compared per model and on the
                      fallback, which is the entry a units error hides in.
  Parquet columns     the trace file's READ schema, against the five column
                      names verdryx names as constants. Verdryx reads five of
                      sixteen columns, so this is containment, not equality: a
                      column it names that tokenfuse does not write is a
                      column that silently reads as null.

WHAT IS NOT COVERED

The severity-per-type table (tokenfuse's EventType::severity against the
parenthesised severities in SPEC 6.2) is a fourth mirror and is not checked
here. See the README's uncovered list for why.
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

ARTIFACT = "contracts/tokenfuse-constants.json"
BREAKER_RS = "crates/core/src/breaker.rs"
OUTCOMES_RS = "crates/core/src/outcomes.rs"
PRICEBOOK_RS = "crates/gateway/src/pricebook.rs"
SINK_RS = "crates/gateway/src/sink.rs"

VERDRYX_COSTPER = "verdryx/costper.py"
VERDRYX_PRICING = "verdryx/pricing.py"


# ------------------------------------------------------- tokenfuse, artifact


def from_artifact(text: str) -> dict:
    data = json.loads(text)
    blocked = data.get("blocked_decisions")
    if not isinstance(blocked, list) or not blocked:
        raise E.Missing(
            f"{ARTIFACT} has no non-empty 'blocked_decisions' list, so the "
            f"artifact this check preferred does not carry the thing it was "
            f"preferred for"
        )
    book = data.get("price_book") or {}
    models = book.get("models")
    fallback = book.get("fallback")
    if not isinstance(models, list) or not models or not isinstance(fallback, dict):
        raise E.Missing(
            f"{ARTIFACT} has no usable 'price_book' with models and a fallback"
        )
    if book.get("units") != "microusd_per_mtok":
        raise E.Missing(
            f"{ARTIFACT} declares price units {book.get('units')!r}, and this "
            f"check only knows how to convert 'microusd_per_mtok'. Comparing "
            f"numbers whose unit is unknown is how a 1e6 error ships."
        )
    parquet = (data.get("trace_parquet") or {}).get("read_schema")
    if not isinstance(parquet, list) or not parquet:
        raise E.Missing(f"{ARTIFACT} has no 'trace_parquet.read_schema' list")

    prices = {}
    for m in models:
        prices[m["model"]] = (
            m["input_per_mtok_microusd"] / 1e6,
            m["output_per_mtok_microusd"] / 1e6,
            m["cache_read_per_mtok_microusd"] / 1e6,
            m["cache_write_per_mtok_microusd"] / 1e6,
        )
    return {
        "blocked": set(blocked),
        "prices": prices,
        "fallback": (
            fallback["input_per_mtok_microusd"] / 1e6,
            fallback["output_per_mtok_microusd"] / 1e6,
            fallback["cache_read_per_mtok_microusd"] / 1e6,
            fallback["cache_write_per_mtok_microusd"] / 1e6,
        ),
        "columns": [f["name"] for f in parquet],
    }


# ---------------------------------------------------------- tokenfuse, Rust

_WIRE_ARM = re.compile(r"BreakerReason::(\w+)\s*=>\s*\"([a-z_]+)\"")
_BLOCKED_ARRAY = re.compile(
    r"const\s+BLOCKED_DECISIONS\s*:\s*\[\s*BreakerReason\s*;\s*(\d+)\s*\]\s*=\s*\[(.*?)\]\s*;",
    re.DOTALL,
)
_WITH_PRICE = re.compile(
    r"\.with\(\s*\"([^\"]+)\"\s*,\s*ModelPrice::per_mtok_usd\(\s*"
    r"([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,?\s*\)",
    re.DOTALL,
)
_WITH_FALLBACK = re.compile(
    r"\.with_fallback\(\s*ModelPrice::per_mtok_usd\(\s*"
    r"([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,?\s*\)"
)
_READ_SCHEMA_FN = re.compile(r"pub fn read_schema\(\)(.*?)\n    \}", re.DOTALL)
_FIELD_NEW = re.compile(r"Field::new\(\s*\"([a-z_]+)\"")


def wire_strings(breaker_rs: str) -> dict[str, str]:
    """variant -> wire string, from BreakerReason::as_wire_str.

    Anchored on the function, not on the file: the same `=>` arms appear in
    http_status and in tests, and matching those would silently widen the set.
    """
    start = breaker_rs.find("fn as_wire_str")
    if start < 0:
        raise E.Missing(
            f"{BREAKER_RS} has no `fn as_wire_str`, which is where the Breaker "
            f"wire strings are defined. The anchor this check parses is gone, so "
            f"it knows nothing about the wire vocabulary"
        )
    end = breaker_rs.find("\n    }", start)
    body = breaker_rs[start : end if end > 0 else len(breaker_rs)]
    arms = dict(_WIRE_ARM.findall(body))
    if not arms:
        raise E.Missing(
            f"{BREAKER_RS}'s `fn as_wire_str` matched no "
            f"`BreakerReason::X => \"y\"` arms. The shape changed and this check "
            f"is reading nothing"
        )
    return arms


def from_rust(breaker_rs: str, outcomes_rs: str, pricebook_rs: str, sink_rs: str) -> dict:
    arms = wire_strings(breaker_rs)

    m = _BLOCKED_ARRAY.search(outcomes_rs)
    if not m:
        raise E.Missing(
            f"{OUTCOMES_RS} has no `const BLOCKED_DECISIONS: [BreakerReason; N]` "
            f"array. That array is the set this check compares, and its absence "
            f"is not an empty set"
        )
    declared_len = int(m.group(1))
    variants = re.findall(r"BreakerReason::(\w+)", m.group(2))
    if len(variants) != declared_len:
        raise E.Missing(
            f"{OUTCOMES_RS} declares BLOCKED_DECISIONS with length {declared_len} "
            f"and this check parsed {len(variants)} entries out of it. One of the "
            f"two readings is wrong and neither should be trusted"
        )
    unknown = [v for v in variants if v not in arms]
    if unknown:
        raise E.Missing(
            f"{OUTCOMES_RS} lists BreakerReason variants with no arm in "
            f"as_wire_str: {', '.join(unknown)}. The two files disagree inside "
            f"tokenfuse itself, so there is no wire set to compare against"
        )
    blocked = {arms[v] for v in variants}

    prices = {}
    for name, i, o, cr, cw in _WITH_PRICE.findall(pricebook_rs):
        prices[name] = (float(i), float(o), float(cr), float(cw))
    if not prices:
        raise E.Missing(
            f"{PRICEBOOK_RS} matched no `.with(\"model\", "
            f"ModelPrice::per_mtok_usd(...))` entries, so no price was read"
        )
    fb = _WITH_FALLBACK.search(pricebook_rs)
    if not fb:
        raise E.Missing(
            f"{PRICEBOOK_RS} has no `.with_fallback(ModelPrice::per_mtok_usd(...))`. "
            f"The fallback is the entry an unknown model resolves through, so an "
            f"unread fallback is the expensive half unmeasured"
        )
    fallback = tuple(float(x) for x in fb.groups())

    rs = _READ_SCHEMA_FN.search(sink_rs)
    if not rs:
        raise E.Missing(
            f"{SINK_RS} has no `pub fn read_schema()`, which is the schema "
            f"verdryx's Parquet reader is pointed at"
        )
    columns = _FIELD_NEW.findall(rs.group(1))
    if not columns:
        raise E.Missing(
            f"{SINK_RS}'s `read_schema` matched no `Field::new(\"...\")` columns"
        )
    return {
        "blocked": blocked,
        "prices": prices,
        "fallback": fallback,
        "columns": columns,
    }


# ------------------------------------------------------------------- verdryx


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def verdryx_blocked(costper_py: str) -> set[str]:
    tree = ast.parse(costper_py)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "_BLOCKED_DECISIONS" not in names:
            continue
        # frozenset({...}) or a bare set literal.
        value = node.value
        if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "frozenset":
            value = value.args[0] if value.args else None
        got = _literal(value) if value is not None else None
        if not got:
            raise E.Missing(
                f"{VERDRYX_COSTPER} assigns _BLOCKED_DECISIONS to something this "
                f"check cannot evaluate as a literal set of strings"
            )
        return set(got)
    raise E.Missing(
        f"{VERDRYX_COSTPER} has no module-level _BLOCKED_DECISIONS assignment. "
        f"That name is the mirror this check compares; its absence means the "
        f"mirror moved, not that it agrees"
    )


def verdryx_columns(costper_py: str) -> dict[str, str]:
    tree = ast.parse(costper_py)
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id.startswith("_PARQUET_") and t.id.endswith("_COLUMN"):
                v = _literal(node.value)
                if isinstance(v, str):
                    out[t.id] = v
    if not out:
        raise E.Missing(
            f"{VERDRYX_COSTPER} has no _PARQUET_*_COLUMN constants. Those names "
            f"are the column mirror; finding none is a parse that failed"
        )
    return out


def verdryx_prices(pricing_py: str) -> tuple[dict[str, tuple], tuple | None]:
    """Walk the chained .with_price(...)/.with_fallback(...) builder.

    Parsed from the AST rather than by regular expression: the arguments are
    numeric literals in a call chain, and ast gives them exactly.
    """
    tree = ast.parse(pricing_py)
    prices: dict[str, tuple] = {}
    fallback: tuple | None = None

    def price_args(call: ast.Call) -> tuple | None:
        if not isinstance(call, ast.Call):
            return None
        fn = call.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        if name != "ModelPrice":
            return None
        vals = []
        for a in call.args:
            v = _literal(a)
            if not isinstance(v, (int, float)):
                return None
            vals.append(float(v))
        while len(vals) < 4:
            vals.append(0.0)
        return tuple(vals[:4])

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attr = getattr(node.func, "attr", "")
        if attr == "with_price" and len(node.args) == 2:
            model = _literal(node.args[0])
            args = price_args(node.args[1])
            if isinstance(model, str) and args:
                prices[model] = args
        elif attr == "with_fallback" and len(node.args) == 1:
            args = price_args(node.args[0])
            if args:
                fallback = args
    if not prices:
        raise E.Missing(
            f"{VERDRYX_PRICING} matched no `.with_price(\"model\", ModelPrice(...))` "
            f"calls, so no price was read from the mirror"
        )
    return prices, fallback


# ---------------------------------------------------------------------- run


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C3", "mirrored constants: tokenfuse to verdryx", estate)

    try:
        estate.dir_of("tokenfuse")
        estate.dir_of("verdryx")
    except E.Unavailable as u:
        c.unavailable(
            "c3.repo-unavailable",
            f"{u.repo} could not be read in this run ({u.reason}), so no mirror "
            f"was compared.",
        )
        return c

    # -- source selection, stated out loud --------------------------------
    mode = None
    try:
        artifact_text = estate.read_text("tokenfuse", ARTIFACT)
        mode = "artifact"
    except E.Missing:
        artifact_text = None

    try:
        if mode == "artifact":
            tf = from_artifact(artifact_text)
            c.note(
                f"MODE: read tokenfuse's published artifact {ARTIFACT} "
                f"(schema-versioned, generated from the Rust by tokenfuse's own "
                f"scripts/constants.sh)."
            )
        else:
            tf = from_rust(
                estate.read_text("tokenfuse", BREAKER_RS),
                estate.read_text("tokenfuse", OUTCOMES_RS),
                estate.read_text("tokenfuse", PRICEBOOK_RS),
                estate.read_text("tokenfuse", SINK_RS),
            )
            mode = "rust"
            c.note(
                f"MODE: {ARTIFACT} is not present in this source, so the Rust was "
                f"parsed instead ({BREAKER_RS}, {OUTCOMES_RS}, {PRICEBOOK_RS}, "
                f"{SINK_RS})."
            )
            c.note(
                "      That is the weaker of the two modes: it reads Rust with "
                "regular expressions, which can stop matching. Every anchor that "
                "matches nothing is a FAIL below, never a silent pass."
            )
    except E.Missing as m:
        c.missing("c3.tokenfuse-unreadable", str(m))
        return c

    # -- mirror one: blocked decisions -------------------------------------
    try:
        vd_blocked = verdryx_blocked(estate.read_text("verdryx", VERDRYX_COSTPER))
    except E.Missing as m:
        c.missing("c3.verdryx-blocked-unreadable", str(m))
        vd_blocked = None

    if vd_blocked is not None:
        only_tf = sorted(tf["blocked"] - vd_blocked)
        only_vd = sorted(vd_blocked - tf["blocked"])
        if not only_tf and not only_vd:
            c.ok(
                "c3.blocked-agree",
                f"the {len(vd_blocked)} Breaker block-decision wire strings agree "
                f"as sets ({mode} mode).",
            )
        else:
            detail = [
                f"  tokenfuse: {estate.where('tokenfuse', ARTIFACT if mode == 'artifact' else OUTCOMES_RS)}"
                f" holds {len(tf['blocked'])}",
                f"  verdryx:   {estate.where('verdryx', VERDRYX_COSTPER)} "
                f"_BLOCKED_DECISIONS holds {len(vd_blocked)}",
            ]
            if only_tf:
                detail.append(
                    f"  in tokenfuse and NOT in verdryx: {', '.join(only_tf)}"
                )
                detail.append(
                    "  verdryx counts those rows' cost_microusd as real spend. It is"
                )
                detail.append("  the avoided estimate, so its cost totals are too high.")
            if only_vd:
                detail.append(
                    f"  in verdryx and NOT in tokenfuse: {', '.join(only_vd)}"
                )
                detail.append(
                    "  verdryx excludes rows tokenfuse no longer blocks, so its cost"
                )
                detail.append("  totals are too low.")
            c.drift(
                "c3.blocked-differ",
                "the Breaker block-decision wire strings do not agree as sets.",
                detail,
            )

    # -- mirror two: the price book ----------------------------------------
    try:
        vd_prices, vd_fallback = verdryx_prices(
            estate.read_text("verdryx", VERDRYX_PRICING)
        )
    except E.Missing as m:
        c.missing("c3.verdryx-prices-unreadable", str(m))
        vd_prices, vd_fallback = None, None

    if vd_prices is not None:
        tf_prices = tf["prices"]
        only_tf = sorted(set(tf_prices) - set(vd_prices))
        only_vd = sorted(set(vd_prices) - set(tf_prices))
        differing = sorted(
            m
            for m in set(tf_prices) & set(vd_prices)
            if [round(x, 9) for x in tf_prices[m]] != [round(x, 9) for x in vd_prices[m]]
        )
        if not only_tf and not only_vd and not differing:
            c.ok(
                "c3.prices-agree",
                f"the price book agrees on all {len(vd_prices)} models "
                f"({mode} mode).",
            )
        else:
            detail = [
                f"  tokenfuse: {estate.where('tokenfuse', ARTIFACT if mode == 'artifact' else PRICEBOOK_RS)}"
                f" holds {len(tf_prices)} models",
                f"  verdryx:   {estate.where('verdryx', VERDRYX_PRICING)} "
                f"PriceBook.default() holds {len(vd_prices)} models",
            ]
            for m in only_tf:
                detail.append(
                    f"  only tokenfuse prices {m}: verdryx charges it the fallback rate"
                )
            for m in only_vd:
                detail.append(
                    f"  only verdryx prices {m}: tokenfuse charges it the fallback rate"
                )
            for m in differing:
                detail.append(
                    f"  {m}: tokenfuse {tf_prices[m]} vs verdryx {vd_prices[m]} "
                    f"(usd per Mtok: input, output, cache read, cache write)"
                )
            c.drift(
                "c3.prices-differ",
                "the default price book and verdryx's mirror of it disagree.",
                detail,
            )

        if vd_fallback is None:
            c.missing(
                "c3.verdryx-fallback-missing",
                f"{estate.where('verdryx', VERDRYX_PRICING)} has no "
                f"`.with_fallback(ModelPrice(...))`, and the fallback is the rate "
                f"every unlisted model resolves through.",
            )
        elif [round(x, 9) for x in vd_fallback] != [round(x, 9) for x in tf["fallback"]]:
            c.drift(
                "c3.fallback-differs",
                "the conservative fallback price differs between tokenfuse and "
                "verdryx.",
                [
                    f"  tokenfuse: {tf['fallback']}",
                    f"  verdryx:   {vd_fallback}",
                    "  (usd per Mtok: input, output, cache read, cache write)",
                    "  The fallback prices every model neither side lists, so this is",
                    "  the entry a units error hides in.",
                ],
            )
        else:
            c.ok("c3.fallback-agrees", "the conservative fallback price agrees.")

    # -- mirror three: Parquet column names ---------------------------------
    try:
        vd_columns = verdryx_columns(estate.read_text("verdryx", VERDRYX_COSTPER))
    except E.Missing as m:
        c.missing("c3.verdryx-columns-unreadable", str(m))
        vd_columns = None

    if vd_columns is not None:
        tf_columns = set(tf["columns"])
        absent = sorted(
            (const, col) for const, col in vd_columns.items() if col not in tf_columns
        )
        if absent:
            c.drift(
                "c3.column-absent",
                f"{len(absent)} of the {len(vd_columns)} Parquet column names "
                f"verdryx reads are not in tokenfuse's read schema.",
                [
                    f"  tokenfuse: {estate.where('tokenfuse', ARTIFACT if mode == 'artifact' else SINK_RS)}"
                    f" read schema, {len(tf_columns)} columns",
                    f"  verdryx:   {estate.where('verdryx', VERDRYX_COSTPER)}",
                ]
                + [f"  {const} = \"{col}\" is not written by tokenfuse" for const, col in absent]
                + [
                    "  A column verdryx names and tokenfuse does not write reads as",
                    "  null for every row, which looks like an empty dataset rather",
                    "  than a mismatch.",
                ],
            )
        else:
            c.ok(
                "c3.columns-present",
                f"all {len(vd_columns)} Parquet column names verdryx reads exist "
                f"in tokenfuse's read schema ({mode} mode).",
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
