"""C23's readers, against real pages and against hostile bytes.

THE SAVED PAGES

`selftest/pages/2026-10-13/` holds the vendor sources as they were fetched on
2026-10-13, trimmed to the parts the readers read (the model pricing table and
the premium paragraph of Anthropic's page; the standard and batch text-token
islands and the grouped short/long table of OpenAI's; the "Google models"
section of Vertex AI's from its h1 to the Gemini 2.0 heading; three of
OpenRouter's per-model provider lists and its 404 body), with class and style
attributes removed and nothing else changed. Each HTML file says so in its first line. They are evidence of what
the pages looked like, not a stand-in for them: the nightly run reads the live
pages, and an anchor that stops matching there is red by construction.

WHAT IS PROVED HERE

  1. The readers read those pages to the numbers a person reads off them that
     day (the values below were read by eye from the live pages, and the
     2026-10-13 hand check that started C23 agrees with them).
  2. The readers survive hostile input: empty, truncated at a sweep of points,
     spliced with random bytes, deeply nested, unclosed. Each call either
     answers or raises `_estate.Missing`, which the gate turns into "measured
     nothing". Any other exception is a crash the nightly run would print as a
     traceback instead of a finding, and a hang is a run that never reports.
     The sweep is seeded, so a failure names the seed that reproduces it.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "gates"))

import _estate as E  # noqa: E402
import _prices as P  # noqa: E402

PAGES = HERE / "pages" / "2026-10-13"
SEEDS = 60
#: one parse of a trimmed page takes milliseconds; a hostile one taking this
#: long is a reader that has stopped being linear.
SLOW = 5.0


def _read(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


def _offer(v: P.Vendor, model: str, endpoint: str = "global", tier: str | None = None, day=None, above="base"):
    for o in v.models.get(model, []):
        if o.endpoint != endpoint or (tier is not None and o.tier != tier):
            continue
        if above != "any" and o.above != (None if above == "base" else above):
            continue
        if day is not None and not o.in_effect(day):
            continue
        return o.prices
    return None


def golden() -> list[str]:
    problems: list[str] = []

    def expect(what, got, want):
        if got != want:
            problems.append(f"{what}: read {got!r}, the page said {want!r}")

    a = P.parse_anthropic(_read("anthropic.html"))
    expect("Anthropic current models", a.current,
           ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])
    expect("Anthropic Sonnet 5.5", _offer(a, "claude-sonnet-5-5"),
           {"input": 2.0, "output": 10.0, "cache_write": 2.5, "cache_write_1h": 4.0, "cache_read": 0.1})
    expect("Anthropic Haiku 5.5, up to 100,000 tokens", _offer(a, "claude-haiku-5-5", tier="up to 100,000 tokens"),
           {"input": 0.1, "output": 0.5, "cache_write": 0.125, "cache_write_1h": 0.2, "cache_read": 0.01})
    expect("Anthropic Haiku 5.5, over 100,000 tokens", _offer(a, "claude-haiku-5-5", tier="over 100,000 tokens", above=100000),
           {"input": 0.5, "output": 2.5, "cache_write": 0.625, "cache_write_1h": 1.0, "cache_read": 0.05})
    expect("Anthropic Opus 5 (the 2026-10-13 costcrew finding)", _offer(a, "claude-opus-5"),
           {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_write_1h": 10.0, "cache_read": 0.5})
    expect("Anthropic Sonnet 5.5 on a regional endpoint", _offer(a, "claude-sonnet-5-5", "regional"),
           {"input": 2.2, "output": 11.0, "cache_write": 2.75, "cache_write_1h": 4.4, "cache_read": 0.11})
    expect("Anthropic problems", a.problems, [])
    expect("Anthropic model count", len(a.models), 20)

    o = P.parse_openai(_read("openai.html"))
    expect("OpenAI current models", o.current, ["gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna"])
    expect("OpenAI gpt-6-sol (four columns)", _offer(o, "gpt-6-sol"),
           {"input": 2.0, "cache_read": 0.2, "cache_write": 2.5, "output": 10.0})
    expect("OpenAI gpt-5.6-sol, standard tier, not batch", _offer(o, "gpt-5.6-sol"),
           {"input": 4.0, "cache_read": 0.4, "cache_write": 5.0, "output": 20.0})
    expect("OpenAI gpt-4o (three columns)", _offer(o, "gpt-4o"), {"input": 2.5, "cache_read": 1.25, "output": 10.0})
    expect("OpenAI gpt-5.5, its name's context suffix taken off", _offer(o, "gpt-5.5"),
           {"input": 5.0, "cache_read": 0.5, "output": 30.0})
    expect("OpenAI gpt-5-pro, no cached price", _offer(o, "gpt-5-pro"), {"input": 15.0, "output": 120.0})
    # 40 rows in the standard table, plus gpt-5.6-cyber and gpt-5.5-cyber from
    # the grouped short/long table (gpt-5.6-sol is in both).
    expect("OpenAI model count, the standard table and the grouped short/long one", len(o.models), 42)
    expect("OpenAI gpt-6-astra above 272K, from the rendered Long context columns", _offer(o, "gpt-6-astra", above=272000),
           {"input": 20.0, "cache_read": 2.0, "cache_write": 25.0, "output": 75.0})
    expect("OpenAI gpt-5.6-sol above 272K, from the grouped table", _offer(o, "gpt-5.6-sol", above=272000),
           {"input": 8.0, "cache_read": 0.8, "cache_write": 10.0, "output": 30.0})
    expect("OpenAI gpt-6-sol's long price, which the page computes in script", _offer(o, "gpt-6-sol", above=272000), None)
    expect("OpenAI tiers marked incomplete", o.tiers_complete, False)

    g = P.parse_vertex(_read("vertex.html"))
    autumn, winter = datetime.date(2026, 10, 13), datetime.date(2027, 1, 1)
    expect("Vertex Gemini 3.8 Flash, global, introductory", _offer(g, "gemini-3.8-flash", "global", "up to 200K input tokens", autumn),
           {"input": 0.75, "cache_read": 0.075, "output": 3.75})
    expect("Vertex Gemini 3.8 Flash, non-global, introductory", _offer(g, "gemini-3.8-flash", "regional", "up to 200K input tokens", autumn),
           {"input": 0.825, "cache_read": 0.0825, "output": 4.125})
    expect("Vertex Gemini 3.8 Flash, global, from 2027", _offer(g, "gemini-3.8-flash", "global", "up to 200K input tokens", winter),
           {"input": 1.5, "cache_read": 0.15, "output": 7.5})
    expect("Vertex Gemini 3.5 Flash, non-global (a Region cell carrying an asterisk)",
           _offer(g, "gemini-3.5-flash", "regional", "up to 200K input tokens", autumn),
           {"input": 1.65, "cache_read": 0.165, "output": 9.9})
    expect("Vertex Gemini 2.5 Pro over 200K, no Region column", _offer(g, "gemini-2.5-pro", "any", "over 200K input tokens", autumn, 200000),
           {"input": 2.5, "cache_read": 0.25, "output": 15.0})
    expect("Vertex Gemini 4 Argon, standard tab, not priority", _offer(g, "gemini-4-argon", "global", "", autumn),
           {"input": 2.0, "cache_read": 0.1, "output": 10.0})
    expect("Vertex Gemini 4 Argon from 2026-12-01 (a date in parentheses, two models in one cell)",
           _offer(g, "gemini-4-argon", "global", "", datetime.date(2026, 12, 1)),
           {"input": 4.0, "cache_read": 0.2, "output": 20.0})
    expect("Vertex Gemini 3.8 Flash has no tier: its > 200K column repeats the base price",
           [x.above for x in g.models["gemini-3.8-flash"] if x.above is not None], [])
    priority = [m for m, offers in g.models.items() for x in offers if x.prices.get("input") in (3.6, 2.7, 2.25)]
    expect("Vertex prices read off a Priority tab", priority, [])
    expect("Vertex marks current models", g.current, None)

    providers = P.parse_openrouter_providers(_read("openrouter-endpoints-deepseek_deepseek-chat.json"))
    expect("OpenRouter's providers for deepseek/deepseek-chat (its model list showed only DeepInfra's)",
           [(x["name"], x["prices"]) for x in providers],
           [("StreamLake", {"input": 0.2574, "output": 1.0287}), ("DeepInfra", {"input": 0.32, "output": 0.89})])
    expect("OpenRouter's 404 for a model it does not know", P.parse_openrouter_providers(_read("openrouter-404.json")), None)
    eps = P.parse_openrouter_endpoints(_read("openrouter-endpoints-openai_gpt-5.6-sol.json"))
    expect("OpenRouter's own OpenAI row for gpt-5.6-sol (it disagrees with OpenAI's page)",
           {k: eps["openai"][0].prices[k] for k in ("input", "output")}, {"input": 2.0, "output": 10.0})
    shapes = (
        'B().with_price("m", ModelPrice(1, 2)).with_long_context("m", 100000, ModelPrice(5, 10, 0.5, 6))',
        'B().with_price("m", ModelPrice(1, 2)).with_long_context("m", above_prompt_tokens=100000, price=ModelPrice(5, 10, 0.5, 6))',
        'B().with_price("m", ModelPrice(1, 2)).with_long_context("m", LongContext(100000, ModelPrice(5, 10, 0.5, 6)))',
    )
    for src in shapes:
        expect(f"verdryx long tier read from {src.split('with_long_context', 1)[1]}",
               P.verdryx_rows(src, "shape").long, {"m": [(100000, {"input": 5.0, "output": 10.0, "cache_read": 0.5, "cache_write": 6.0})]})
    return problems


def _hostile_variants(text: str, rng: random.Random) -> list[str]:
    n = len(text)
    out = []
    for _ in range(4):
        cut = rng.randrange(n + 1)
        out.append(text[:cut])
        out.append(text[cut:])
    for _ in range(4):
        i = rng.randrange(n + 1)
        j = min(n, i + rng.randrange(1, 400))
        junk = "".join(chr(rng.choice([rng.randrange(32, 127), rng.randrange(0x80, 0x3000), 0])) for _ in range(rng.randrange(1, 60)))
        out.append(text[:i] + junk + text[j:])
        out.append(text[:i] + text[j:])
        out.append(text[:i] + text[i:j] * rng.randrange(2, 6) + text[j:])
    return out


FIXED_HOSTILE = [
    "",
    "\x00" * 64,
    "<" * 5000,
    "<div>" * 5000 + "</div>" * 10,
    "<table>" + "<tr><td>$1 / MTok" * 3000,
    "<table><tr><th>Name</th><th>Input</th><th>Output</th><th>5m writes</th><th>1h writes</th><th>Hits and refreshes</th></tr>"
    "<tr><td>Claude Opus 9</td><td>$1e400 / MTok</td><td>$NaN</td><td>$</td><td>$9" + "9" * 400 + "</td><td>x</td></tr></table>",
    '<astro-island component-export="TextTokenPricingTables" props="{&quot;tier&quot;:[0,&quot;standard&quot;],&quot;rows&quot;:[1,[[1,[[0,null]]],[0,5],[1,[[1,[]]]]]]}"></astro-island>',
    '<astro-island component-export="TextTokenPricingTables" props="[[0,1],{]"></astro-island>',
    "null", "[]", "{}", '{"data": null}', '{"data": [null, 1, "x", {"id": 5}, {"id": "a", "pricing": "free"}]}',
    '{"data": {"endpoints": [null, {"tag": 1}, {"tag": "openai", "pricing": {"prompt": "-1", "completion": "inf"}}]}}',
    '{"data": [{"id": "x/y", "pricing": {"prompt": "1e-6", "completion": "2e-6", "overrides": [null, 3, {"min_prompt_tokens": "lots"}]}}]}',
    "﻿" + "<html>" + "\ud800" + "</html>",
]

READERS = [
    ("parse_anthropic", P.parse_anthropic, "anthropic.html"),
    ("parse_openai", P.parse_openai, "openai.html"),
    ("parse_vertex", P.parse_vertex, "vertex.html"),
    ("parse_openrouter_providers", P.parse_openrouter_providers, "openrouter-endpoints-deepseek_deepseek-chat.json"),
    ("parse_openrouter_endpoints", P.parse_openrouter_endpoints, "openrouter-endpoints-openai_gpt-5.6-sol.json"),
]

TABLE_HOSTILE = {
    "tokenfuse-constants": [
        '{"price_book": {"units": "microusd_per_mtok", "models": [{"model": "m", "input_per_mtok_microusd": 1, "output_per_mtok_microusd": 1, "cache_read_per_mtok_microusd": 1, "cache_write_per_mtok_microusd": 1}], "fallback": {"input_per_mtok_microusd": 1, "output_per_mtok_microusd": 1, "cache_read_per_mtok_microusd": 1, "cache_write_per_mtok_microusd": 1}, "long_context": [null, {"model": "m", "above_prompt_tokens": true}]}}',
        '{"price_book": {"units": "microusd_per_mtok", "models": [{"model": "m", "input_per_mtok_microusd": 1, "output_per_mtok_microusd": 1, "cache_read_per_mtok_microusd": 1, "cache_write_per_mtok_microusd": 1}], "fallback": {"input_per_mtok_microusd": 1, "output_per_mtok_microusd": 1, "cache_read_per_mtok_microusd": 1, "cache_write_per_mtok_microusd": 1}, "long_context": {"m": 1}}}',
        "", "{", "[]", '{"price_book": null}', '{"price_book": {"units": "microusd_per_mtok", "models": [1], "fallback": {}}}',
        '{"price_book": {"units": "microusd_per_mtok", "models": [{"model": "m", "input_per_mtok_microusd": true}], "fallback": {}}}',
        '{"price_book": {"units": "usd", "models": [{"model": "m"}], "fallback": {}}}',
        '{"price_book": {"units": "microusd_per_mtok", "models": [{"model": "m", "input_per_mtok_microusd": "1"}], "fallback": {}}}',
    ],
    "verdryx-pricebook": [
        "", "def (", "x = PriceBook().with_price(1, 2)", 'PriceBook().with_price("m", ModelPrice("a", None))',
        'PriceBook().with_price("m", ModelPrice(*args))', "(" * 200 + ")" * 200,
        'PriceBook().with_price("m", ModelPrice(1, 2)).with_long_context()',
        'PriceBook().with_price("m", ModelPrice(1, 2)).with_long_context("m", -5, ModelPrice(1, 2))',
        'PriceBook().with_price("m", ModelPrice(1, 2)).with_long_context("m", LongContext(price=ModelPrice(1, 2)))',
        'PriceBook().with_price("m", ModelPrice(1, 2)).with_long_context("m", True, ModelPrice(1, 2))',
    ],
    "go-price-map": [
        "", "var prices = map[string]Price{", '// var prices = map[string]Price{"a": {InPerM: 1, OutPerM: 2}}',
        'var prices = map[string]Price{"a": {InPerM: x * 2, OutPerM: 1}}', 'var prices = map[string]Price{"a": {OutPerM: 1}}',
        'var prices = map[string]Price{"a": {InPerM: 1, OutPerM: 2, Source: "https://x.example/a//b", Note: `raw "{" text`}}',
        'var s = "/* not a comment"; var prices = map[string]Price{}',
        'var prices = map[string]Price{' + '{' * 3000,
    ],
}


def hostile() -> list[str]:
    problems: list[str] = []

    def call(label, fn, text):
        t0 = time.monotonic()
        try:
            fn(text)
        except E.Missing:
            pass
        except Exception as e:  # noqa: BLE001, the point is to catch anything
            problems.append(f"{label}: raised {type(e).__name__}: {str(e)[:120]}")
            return
        if time.monotonic() - t0 > SLOW:
            problems.append(f"{label}: took {time.monotonic() - t0:.1f}s")

    for name, fn, page in READERS:
        text = _read(page)
        for k, bad in enumerate(FIXED_HOSTILE):
            call(f"{name} on fixed hostile input #{k}", fn, bad)
        for seed in range(SEEDS):
            rng = random.Random(seed)
            for k, bad in enumerate(_hostile_variants(text, rng)):
                before = len(problems)
                call(f"{name} on {page}, seed {seed}, variant {k}", fn, bad)
                if len(problems) > before:
                    break
    for fmt, cases in TABLE_HOSTILE.items():
        reader = P.TABLE_READERS[fmt]
        for k, bad in enumerate(cases):
            call(f"{fmt} reader on hostile input #{k}", lambda t: reader(t, "hostile"), bad)
    # Every finding here must name its seed, and one crash class must not drown
    # the rest: keep the first few of each reader.
    seen: dict[str, int] = {}
    kept = []
    for p in problems:
        key = p.split(" on ", 1)[0]
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= 3:
            kept.append(p)
    return kept


def run() -> list[str]:
    try:
        problems = [f"golden: {p}" for p in golden()]
    except E.Missing as m:
        problems = [f"golden: a saved page did not parse at all: {m}"]
    problems += [f"hostile: {p}" for p in hostile()]
    return problems


if __name__ == "__main__":
    t0 = time.monotonic()
    found = run()
    for p in found:
        print("FAIL:", p)
    print(f"{'FAIL' if found else 'OK'}: {len(found)} problem(s), {time.monotonic() - t0:.1f}s")
    sys.exit(1 if found else 0)
