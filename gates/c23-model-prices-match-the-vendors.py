#!/usr/bin/env python3
"""C23: every built-in model price table matches the vendors' current prices.

WHY

On 2026-10-13 a hand check found the gateway's built-in price book behind the
vendors. Claude Haiku 5.5, released about 2026-10-07 at 0.10 / 0.50 USD per
million tokens, had no row, so the gateway billed it at the 15 / 75 fallback,
about 150 times the price. claude-sonnet-5-5's cache read was 0.20 where the
page said 0.10. There were no GPT-6 rows at all. Gemini 3.8 Flash was priced at
its 2027 standard rate while the introductory rate was in force. costcrew's own
table carried Sonnet 5 at 3 / 15 and Opus 5 at 15 / 75 against 2 / 10 and 5 /
25. Every repository was internally consistent and every suite was green: a
price is a claim about somebody else's list, true on the day it was copied,
and nothing compared the copy with the list afterwards. This gate does, every
day, in the estate's existing scheduled run.

WHAT IS READ

Subjects come from estate.json, never from a list here: every repository whose
entry carries `price_table` (`path`, `format`, `every_current_model`, and a
`why` when that is false). The formats are `_prices.TABLE_READERS`; one the
gate cannot read is a finding, not a skip.

Sources, fetched live with no key (or read from ESTATE_GATES_PRICE_SOURCES, a
directory the self-test fills):

  Anthropic   platform.claude.com/docs/en/about-claude/pricing, the model
              pricing table (columns by their headers) and the sentence stating
              the regional premium
  OpenAI      developers.openai.com/api/docs/pricing, the TextTokenPricingTables
              island marked tier "standard", read in the column order its own
              headings state
  Google      cloud.google.com/vertex-ai/generative-ai/pricing, the Standard
              tabs under "Google models", Global and Non-global rows, dated rows
  OpenRouter  openrouter.ai/api/v1/models, PRIMARY only for a row billed through
              OpenRouter (costcrew's `openrouter/...` engine); otherwise a
              SECONDARY signal from /models/{id}/endpoints, the vendor's own
              endpoint row. Where it disagrees with a vendor page the vendor
              page wins and the disagreement is printed.

HOW A ROW IS MATCHED (`_prices.resolve`)

  global      the Claude API's own ids, a Bedrock `global.` profile, an
              OpenRouter-style `anthropic/...` id, OpenAI ids: the list price
  regional    a Bedrock `us.` / `eu.` / `jp.` / `apac.` profile: list plus the
              premium Anthropic's page states (10 percent on 2026-10-13); if
              that sentence is gone, these rows are not judged and that is red
  unnamed     an id that does not say which endpoint it reaches (a bare Bedrock
              `anthropic.` id, a Google `@`-dated id, a Vertex `google/` id):
              the row must equal ONE of the endpoint prices, every component
              from the same one

The same rule covers prompt-length tiers. A flat row cannot say how long a
prompt will be, so where a page prices a model in tiers (Haiku 5.5 up to and
over 100,000 tokens; Gemini up to and over 200K) the row must equal one tier,
every component from it. That accepts a book that chose the long-context rate
on purpose, which tokenfuse does for Gemini 2.5 Pro.

Only components BOTH sides state are compared. A vendor that states no cache
write price is not a disagreement with a table that wrote one.

DATED PRICES. The tokenfuse book has no effective date, so a row is compared
with the price in effect today (UTC; ESTATE_GATES_TODAY overrides it for the
self-test). A dated change within 30 days is printed as a WARN line on every
run; on the day it takes effect a row still at the old price is red.

WHAT COUNTS AS A FAILURE

  c23.price-differs            a row disagrees with the vendor beyond half a
                               percent (or a micro-dollar per million tokens);
                               names the repository, the row, ours, theirs,
                               the source URL, and the row as it should read
  c23.current-model-missing    a model the vendor's page marks current has no
                               row in a table declared to price every current
                               model, so the gateway prices it at the fallback;
                               prints the row to add
  c23.fallback-below-current   the fallback is cheaper than a current model, so
                               an unlisted call is billed below its price,
                               the direction that costs money
  c23.source-unparseable       a page was fetched and its shape no longer
                               parses: measured nothing for that vendor
  c23.table-unreadable         a declared table is absent, unreadable, in a
                               format this gate has no reader for, or declared
                               incompletely in estate.json
  c23.nothing-matched          not one row of a table maps to a vendor price:
                               measured nothing for that table
  c23.no-subjects              no repository declares a price table

A page nobody could FETCH is NOT MEASURED, never OK, and the runner exits 2 for
it (a repository estate.json excuses may end a run at 3; a vendor page never).

WHY A MISSING CURRENT MODEL IS RED AND NOT A WARNING

This suite has no warning level, by design: a finding nothing can fail on is
a label. And the cost is not cosmetic. A gateway with no row prices an
unknown model at its conservative fallback, so the 2026-10-13 Haiku 5.5 calls
were billed at about 150 times the price; a budget enforcer refusing calls on
money that was never spent is a wrong answer about money, the class this
estate gates hardest. "Current" is what the vendor's own page marks: the rows
above Anthropic's "Additional models" group, and the first
collapsedLatestRowCount rows of OpenAI's standard table. Vertex marks no set,
so a Gemini model no table prices is listed every run, not judged. Older
models a vendor still lists are printed, not red. Only tables declared
`every_current_model: true` are asked (the gateway's book); costcrew prices
its own engine catalogue and refuses anything else, and verdryx's mirror is
held to the gateway's book row for row by C3.

WHAT IT DOES NOT CATCH

Prices a vendor publishes somewhere this gate does not read (Bedrock's own
page, DeepSeek's, AWS's price list for Nova); rows for those are listed as not
judged. A model id the vendor renames without the page saying so. Data
residency multipliers on first-party APIs, which no table here prices. Whether
a vendor page is RIGHT: it is the source of truth by definition.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _estate as E  # noqa: E402
import _prices as P  # noqa: E402

WARN_DAYS = 30
USER_AGENT = "estate-gates/c23 (+https://github.com/TAIPANBOX/estate-gates)"
MAX_BYTES = 20 * 1024 * 1024
#: OpenRouter endpoint lookups per run, for the secondary signal only.
SECONDARY_LIMIT = 24

#: vendor key -> (name, URL, parser, fixture file name)
SOURCES = {
    "anthropic": ("Anthropic", P.ANTHROPIC_URL, P.parse_anthropic, "anthropic.html"),
    "openai": ("OpenAI", P.OPENAI_URL, P.parse_openai, "openai.html"),
    "google": ("Google Vertex AI", P.VERTEX_URL, P.parse_vertex, "vertex.html"),
    "openrouter": ("OpenRouter", P.OPENROUTER_MODELS_URL, P.parse_openrouter_models, "openrouter-models.json"),
}


class Unreachable(Exception):
    pass


class Fetcher:
    """Live pages, or the self-test's directory standing in for them."""

    def __init__(self) -> None:
        d = os.environ.get("ESTATE_GATES_PRICE_SOURCES")
        self.fixture = pathlib.Path(d) if d else None

    def label(self) -> str:
        if self.fixture:
            return f"saved pages under {self.fixture} (ESTATE_GATES_PRICE_SOURCES)"
        return "the vendors' live pages, fetched now with no key"

    def get(self, url: str, fixture_name: str) -> str:
        if self.fixture:
            path = self.fixture / fixture_name
            if not path.is_file():
                raise Unreachable(f"no saved page {path}")
            return path.read_bytes().decode("utf-8", "replace")
        last = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise Unreachable(f"{url} answered with more than {MAX_BYTES} bytes")
                return body.decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code} from {url}"
            except (urllib.error.URLError, OSError, ValueError) as e:
                last = f"{url}: {getattr(e, 'reason', e)}"
            if attempt == 0:
                time.sleep(3)
        raise Unreachable(last)


def today() -> datetime.date:
    forced = os.environ.get("ESTATE_GATES_TODAY")
    if forced:
        return datetime.date.fromisoformat(forced)
    return datetime.datetime.now(datetime.timezone.utc).date()


class Table:
    """One declared price table, read. A plain class rather than a dataclass:
    the runner loads gate files without registering them in sys.modules, and
    dataclasses looks its module up there."""

    def __init__(self, repo, path, fmt, where, rows, fallback, every_current, why):
        self.repo, self.path, self.fmt, self.where = repo, path, fmt, where
        self.rows, self.fallback, self.every_current, self.why = rows, fallback, every_current, why


# ----------------------------------------------------------- row printing


def suggested(fmt: str, key: str, prices: dict, url: str, day: datetime.date) -> str:
    """The row as it should read, in the table's own format."""
    if fmt == "tokenfuse-constants":
        row = {"model": key}
        for comp, field in P._TF_FIELDS.items():
            if comp in prices:
                row[field] = round(prices[comp] * 1e6)
        return json.dumps(row)
    if fmt == "verdryx-pricebook":
        args = ", ".join(P.fmt(prices.get(c, 0.0)) for c in P._VERDRYX_ORDER)
        return f'.with_price("{key}", ModelPrice({args}))'
    if fmt == "go-price-map":
        return (
            f'"{key}": {{InPerM: {P.fmt(prices.get("input", 0.0))}, OutPerM: {P.fmt(prices.get("output", 0.0))}, '
            f'Recorded: "{day.isoformat()}", Source: "{url}"}},'
        )
    return f"{key}: {prices}"


def fmt_prices(p: dict) -> str:
    return ", ".join(f"{c} {P.fmt(p[c])}" for c in P.COMPONENTS if c in p)


# ------------------------------------------------------------------- run


def _subjects(c: E.Check, estate: E.Estate) -> list[Table]:
    declared = [(r, e["price_table"]) for r, e in sorted(estate.repos.items()) if "price_table" in e]
    if not declared:
        c.missing(
            "c23.no-subjects",
            "no repository in estate.json declares a `price_table`, so this gate measured "
            "nothing. Three repositories carry one (the gateway's book, its mirror and "
            "costcrew's), so finding none means the registry lost them.",
        )
        return []
    tables = []
    for repo, decl in declared:
        reader = P.TABLE_READERS.get(decl.get("format")) if isinstance(decl, dict) else None
        problems = []
        if not isinstance(decl, dict):
            problems.append("is not an object")
        else:
            if not isinstance(decl.get("path"), str) or not decl.get("path"):
                problems.append("names no `path`")
            if reader is None:
                problems.append(
                    f"names format {decl.get('format')!r}, and this gate reads only "
                    f"{', '.join(sorted(P.TABLE_READERS))}"
                )
            if not isinstance(decl.get("every_current_model"), bool):
                problems.append("does not say `every_current_model` (true or false)")
            elif decl["every_current_model"] is False and not str(decl.get("why", "")).strip():
                problems.append("says `every_current_model: false` without a `why`")
        if problems:
            c.missing(
                "c23.table-unreadable",
                f"estate.json's `price_table` for {repo} {'; '.join(problems)}, so the table "
                f"could not be read.",
            )
            continue
        path = decl["path"]
        try:
            text = estate.read_text(repo, path)
        except E.Unavailable as u:
            c.unavailable(f"c23.table-unavailable:{repo}", f"{repo} could not be read in this run ({u.reason}).")
            continue
        except E.Missing as m:
            c.missing("c23.table-unreadable", f"{repo}'s declared price table is not there: {m}.")
            continue
        where = estate.where(repo, path)
        try:
            rows, fallback = reader(text, where)
        except E.Missing as m:
            c.missing("c23.table-unreadable", f"{repo}'s price table could not be read: {m}.")
            continue
        tables.append(Table(repo, path, decl["format"], where, rows, fallback,
                            decl["every_current_model"], str(decl.get("why", "")).strip()))
    return tables


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C23", "built-in model price tables match the vendors' current prices", estate)
    day = today()
    fetch = Fetcher()
    c.note(f"Vendor prices read from {fetch.label()}; today is {day.isoformat()} (UTC).")

    tables = _subjects(c, estate)
    if not tables:
        return c

    resolved = {t.repo: {k: P.resolve(k) for k in t.rows} for t in tables}
    needed = sorted({tg.vendor for rs in resolved.values() for tg in rs.values() if tg})
    vendors: dict[str, P.Vendor] = {}
    unmeasured: set[str] = set()
    for key in needed:
        name, url, parser, fixture_name = SOURCES[key]
        try:
            page = fetch.get(url, fixture_name)
        except Unreachable as u:
            unmeasured.add(key)
            estate.source_unreachable(name, str(u))
            c.unavailable(
                f"c23.source-unreachable:{key}",
                f"{name}'s prices could not be fetched ({u}), so this run measured nothing "
                f"for {name}. Every row priced from it went uncompared; that is not a pass.",
            )
            continue
        try:
            v = parser(page, url)
        except E.Missing as m:
            unmeasured.add(key)
            c.missing(
                "c23.source-unparseable",
                f"{name}'s price page was fetched and its shape no longer parses, so this "
                f"gate measured nothing for {name}: {m}.",
                [f"  source: {url}", "  The fix is in this gate's reader, after reading what the page says now."],
            )
            continue
        vendors[key] = v
        for problem in v.problems:
            c.missing(
                "c23.source-unparseable",
                f"{name}: {problem}.",
                [f"  source: {url}"],
            )
        for n in v.notes:
            c.note(f"{name}: {n}.")
        if v.current is not None:
            c.note(f"{name}: {len(v.models)} models on the page, current: {', '.join(v.current)}.")
        else:
            c.note(f"{name}: {len(v.models)} models {'listed' if key == 'openrouter' else 'on the page'}.")

    compared: dict[tuple[str, str], P.Vendor] = {}
    failed_models: set[tuple[str, str]] = set()

    # -- every row against the vendor's price in effect today -----------------
    for t in tables:
        matched, nosource, notlisted, unjudged = 0, [], [], []
        for key in sorted(t.rows):
            row, tg = t.rows[key], resolved[t.repo][key]
            if tg is None:
                nosource.append(key)
                continue
            v = vendors.get(tg.vendor)
            if v is None:
                unjudged.append(key)
                continue
            offers = v.models.get(tg.model)
            if not offers:
                notlisted.append(key)
                continue
            if tg.endpoint == "regional" and not any(o.endpoint in ("regional", "any") for o in offers):
                unjudged.append(key)
                continue
            cands = [o for o in P.candidates(offers, tg.endpoint, day) if P.shared(row, o)]
            if not cands:
                unjudged.append(key)
                continue
            matched += 1
            compared[(tg.vendor, tg.model)] = v
            good = [o for o in cands if not P.mismatches(row, o)]
            label = f"{v.name} {v.names.get(tg.model, tg.model)}"
            if good:
                c.ok(
                    f"c23.row:{t.repo}:{key}",
                    f"{t.repo}: {key} = {label}, {good[0].describe()} ({fmt_prices({k: row[k] for k in P.shared(row, good[0])})}).",
                )
                continue
            best = min(cands, key=lambda o: (len(P.mismatches(row, o)), P.distance(row, o), o.tier != cands[0].tier))
            failed_models.add((tg.vendor, tg.model))
            fixed = dict(row)
            fixed.update({k: best.prices[k] for k in P.shared(row, best)})
            detail = [
                f"  ours:     {t.where}, row {key!r}",
                f"  official: {v.url}, {label}, {best.describe()}",
            ]
            for comp in P.mismatches(row, best):
                detail.append(f"  {comp}: ours {P.fmt(row[comp])}, official {P.fmt(best.prices[comp])} (USD per 1M tokens)")
            if len(cands) > 1:
                detail.append(f"  ({len(cands)} official prices apply to this id; it matches none of them, the nearest is shown)")
            detail.append(f"  should read: {suggested(t.fmt, key, fixed, v.url, day)}")
            kept = [k for k in P.COMPONENTS if k in row and k not in best.prices]
            if kept:
                detail.append(f"  ({', '.join(kept)}: not stated by {v.name}, kept as the table has them; the table's own rule decides)")
            c.drift("c23.price-differs", f"{t.repo} prices {key} differently from {v.name}'s page.", detail)
        if nosource:
            c.note(f"{t.repo}: {len(nosource)} row(s) no source here prices, not judged: {', '.join(nosource)}.")
        if notlisted:
            c.note(f"{t.repo}: {len(notlisted)} row(s) whose vendor page lists no such model, not judged: {', '.join(notlisted)}.")
        if unjudged:
            c.note(f"{t.repo}: {len(unjudged)} row(s) NOT MEASURED because their source was not read or states no price for that endpoint today: {', '.join(unjudged)}.")
        if matched == 0 and not unjudged:
            c.missing(
                "c23.nothing-matched",
                f"not one row of {t.repo}'s price table maps to a price on a vendor page this "
                f"gate reads, so it measured nothing for that table ({len(t.rows)} row(s) read).",
                [f"  table: {t.where}"],
            )

    # -- current models a table declared complete does not price --------------
    for t in tables:
        if not t.every_current:
            c.note(f"{t.repo}: not asked to price every current model ({t.why}).")
            continue
        priced: dict[str, set] = {}
        for tg in resolved[t.repo].values():
            if tg:
                priced.setdefault(tg.vendor, set()).add(tg.model)
        for vk in sorted(priced):
            v = vendors.get(vk)
            if v is None or v.current is None:
                continue
            for mid in v.current:
                name = f"{v.name} {v.names.get(mid, mid)}"
                if mid in priced[vk]:
                    c.ok(f"c23.current:{t.repo}:{mid}", f"{t.repo} prices {name}, a current model.")
                    continue
                offers = [o for o in v.models.get(mid, []) if o.in_effect(day) and o.endpoint in ("global", "any")]
                if not offers:
                    continue
                base = offers[0]
                compared[(vk, mid)] = v
                detail = [
                    f"  table:    {t.where}",
                    f"  official: {v.url}, {name}, {base.describe()}: {fmt_prices(base.prices)}",
                    f"  add:      {suggested(t.fmt, mid, base.prices, v.url, day)}",
                ]
                unstated = [comp for comp in P.COMPONENTS if comp not in base.prices]
                if unstated and t.fmt == "tokenfuse-constants":
                    detail.append(f"  ({', '.join(unstated)}: not stated by {v.name}; the book's own rule decides)")
                for other in offers[1:]:
                    detail.append(f"  the page also prices it {other.describe()}: {fmt_prices(other.prices)}")
                if t.fallback:
                    detail.append(f"  until then it is billed at the fallback: {fmt_prices(t.fallback)}")
                c.drift(
                    "c23.current-model-missing",
                    f"{t.repo} has no row for {name}, which {v.name}'s page lists as a current model.",
                    detail,
                )

    # -- the fallback is never cheaper than a current model --------------------
    for t in tables:
        if not t.fallback:
            continue
        below = []
        for vk, v in sorted(vendors.items()):
            for mid in v.current or []:
                for o in v.models.get(mid, []):
                    if not o.in_effect(day):
                        continue
                    for comp in P.COMPONENTS:
                        if comp in t.fallback and comp in o.prices and t.fallback[comp] < o.prices[comp] and not P.close(t.fallback[comp], o.prices[comp]):
                            below.append(f"  {comp}: fallback {P.fmt(t.fallback[comp])} < {v.name} {v.names.get(mid, mid)} {P.fmt(o.prices[comp])} ({o.describe()})")
        if below:
            c.drift(
                "c23.fallback-below-current",
                f"{t.repo}'s fallback price is below a current model's, so a call the table "
                f"does not list is billed under its price, the direction that costs money.",
                [f"  table: {t.where}"] + below,
            )
        else:
            c.ok(f"c23.fallback:{t.repo}", f"{t.repo}'s fallback ({fmt_prices(t.fallback)}) is at or above every current model's price.")

    # -- dated changes ahead ----------------------------------------------------
    horizon = day + datetime.timedelta(days=WARN_DAYS)
    seen_changes = set()
    for (vk, mid), v in sorted(compared.items()):
        for o in v.models.get(mid, []):
            when = None
            if o.start and o.start > day:
                when = o.start
            elif o.end and o.end >= day:
                when = o.end + datetime.timedelta(days=1)
            if when is None or (vk, mid, when) in seen_changes:
                continue
            seen_changes.add((vk, mid, when))
            new = [x for x in v.models[mid] if x.in_effect(when) and x.endpoint in ("global", "any")]
            what = f"{v.name} {v.names.get(mid, mid)} changes price on {when.isoformat()}"
            if new:
                what += f" (global then: {fmt_prices(new[0].prices)})"
            if when <= horizon:
                c.note(f"WARN: {what}, within {WARN_DAYS} days. A row still at today's price goes red that day.")
            else:
                c.note(f"{what}, more than {WARN_DAYS} days away.")

    # -- secondary signal --------------------------------------------------------
    _secondary(c, fetch, vendors, sorted((k for k in compared if k[0] in P.FIRST_PARTY_TAG and (k in failed_models or k[1] in (vendors[k[0]].current or [])))), day)

    if vendors.get("google") and any(t.every_current for t in tables):
        priced_google = {tg.model for rs in resolved.values() for tg in rs.values() if tg and tg.vendor == "google"}
        unpriced = sorted(set(vendors["google"].models) - priced_google)
        if unpriced:
            c.note(f"Google Vertex AI: {len(unpriced)} model(s) no table prices, listed and not judged: {', '.join(unpriced)}.")
    return c


def _secondary(c: E.Check, fetch: Fetcher, vendors: dict, keys: list, day: datetime.date) -> None:
    agree, disagree, unread = 0, [], []
    for vk, mid in keys[:SECONDARY_LIMIT]:
        v = vendors[vk]
        oid = P.openrouter_id(vk, mid)
        try:
            text = fetch.get(P.OPENROUTER_ENDPOINTS_URL.format(id=oid), f"openrouter-endpoints/{oid}.json")
            eps = P.parse_openrouter_endpoints(text)
        except (Unreachable, E.Missing) as e:
            unread.append(f"{oid} ({str(e)[:200]})")
            continue
        theirs = eps.get(P.FIRST_PARTY_TAG[vk])
        ours = [o for o in v.models.get(mid, []) if o.in_effect(day) and o.endpoint in ("global", "any")]
        if not theirs or not ours:
            unread.append(f"{oid} (no {P.FIRST_PARTY_TAG[vk]} endpoint row)")
            continue
        diff = P.mismatches(theirs[0].prices, ours[0])
        if diff:
            disagree.append(
                f"{oid}: OpenRouter's {P.FIRST_PARTY_TAG[vk]} row says "
                + ", ".join(f"{k} {P.fmt(theirs[0].prices[k])}" for k in diff)
                + f"; {v.name}'s page says " + ", ".join(f"{k} {P.fmt(ours[0].prices[k])}" for k in diff)
            )
        else:
            agree += 1
    if not keys:
        return
    c.note(
        f"OpenRouter, secondary signal: {agree} agree with the vendor page, {len(disagree)} disagree, "
        f"{len(unread)} NOT MEASURED. The vendor page wins every disagreement."
    )
    for d in disagree:
        c.note(f"  disagrees: {d}.")
    for u in unread:
        c.note(f"  not measured: {u}.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    E.add_common_args(p)
    args = p.parse_args()
    estate = E.estate_from_args(args)
    return run(estate).render()


if __name__ == "__main__":
    sys.exit(main())
