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
  OpenRouter  openrouter.ai/api/v1/models/{id}/endpoints, every provider
              OpenRouter routes a model to. PRIMARY for a row billed through
              OpenRouter (costcrew's `openrouter/...` engine): the row must
              equal one provider's price exactly, every component from that
              provider, because the call is billed at the price of whichever
              provider served it. Never OpenRouter's model list, whose single
              price switches provider as they come and go (on 2026-10-13 it
              showed DeepInfra's 0.32 / 0.89 for deepseek-chat while StreamLake
              served it at 0.2574 / 1.0287). Otherwise a SECONDARY signal: the
              vendor's own endpoint row, where the vendor page wins every
              disagreement and the disagreement is printed.

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

PROMPT-LENGTH TIERS. Haiku 5.5 is priced up to and over 100,000 prompt
tokens, Gemini 2.5 and 3.1 Pro up to and over 200K, OpenAI's long-context
models up to and over 272K. A table that cannot express a tier (no
`long_context` block, no `.with_long_context`) is flat, and a flat row may
equal either tier, every component from the same one. A table that CAN
express one is held to more: its base row must be the base price, each tier
it carries must start at the vendor's threshold at the vendor's long price,
a tier for a model the vendor prices at one rate is red, and a model the
vendor prices by prompt length with no tier in such a table is red, because
every long prompt is then billed at the base rate. OpenAI's page shows its
long prices only for its latest rows and its grouped short/long table, and
computes the rest in script, so an OpenAI tier the page does not show is
listed as not judged rather than called absent.

Only components BOTH sides state are compared. A vendor that states no cache
write price is not a disagreement with a table that wrote one.

DATED PRICES. The tokenfuse book has no effective date, so a row is compared
with the price in effect today (UTC; ESTATE_GATES_TODAY overrides it for the
self-test). A dated change within 30 days is printed as a WARN line on every
run; on the day it takes effect a row still at the old price is red.

RECORDED CHOICES. A repository may choose a disagreement on purpose: tokenfuse
carries Gemini 3.6 to 3.8 Flash at the standard rate that takes effect on
2027-01-01 (the dearer of two dated rates), and keeps its fallback below
gpt-6-astra's long-prompt price (its invariant 99, decisions 2 and 6).
`expectations/model-prices.json` records each such choice with its reason
and provenance (`Exceptions` below). An applied one is printed as an
EXCEPTION on every run, never a silent pass; one that excuses nothing in a
run where its subject was measured is red, so the dated one goes red the day
its price takes effect and has to be removed, and none can outlive its reason.

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
  c23.no-endpoints             a row is billed through OpenRouter and OpenRouter
                               lists no provider for the model (or does not
                               know it)
  c23.nothing-matched          not one row of a table maps to a vendor price:
                               measured nothing for that table
  c23.stale-exception          a recorded exception excused nothing (its row
                               agrees, matches neither price, or is gone; its
                               date has passed), or it cannot be read
  c23.no-subjects              no repository declares a price table

A page nobody could FETCH is NOT MEASURED, never OK, and the runner exits 2 for
it (a repository estate.json excuses may end a run at 3; a vendor page never).
A row that no source here can judge, and that no recorded exception declares,
is NOT MEASURED too, counted against its repository: exit 2 where that
repository has a public remote, exit 3 where it has none. A row whose source
states no price for it, or whose vendor lists no such model, is "not judged":
listed by name, never counted, and the run does not say every subject was
measured while one is listed.

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
import re
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

    def get(self, url: str, fixture_name: str, accept_404: bool = False) -> str:
        """The page's text. With `accept_404`, a 404 is an answer (OpenRouter
        says so for a model it does not know) and its body is returned."""
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
                if accept_404 and e.code == 404:
                    return e.read(MAX_BYTES).decode("utf-8", "replace")
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

    def __init__(self, repo, path, fmt, where, data, every_current, why):
        self.repo, self.path, self.fmt, self.where = repo, path, fmt, where
        self.rows, self.fallback, self.long = data.rows, data.fallback, data.long
        self.every_current, self.why = every_current, why


# ------------------------------------------------------------- exceptions

EXCEPTIONS_DEFAULT = E.REPO_ROOT / "expectations" / "model-prices.json"
_EXCEPTION_KEY = re.compile(r"^(price-differs|fallback-below-current|tier-not-on-page):([^:\s]+):(\S+)$")


class Exceptions:
    """Disagreements a repository chose on purpose, recorded with a reason.

    `expectations/model-prices.json`, the same bargain C5's expectations file
    makes: a recorded choice is printed as an EXCEPTION on every run, never a
    silent pass, and one that no longer describes anything is red, so the file
    cannot become a graveyard. Two kinds, keyed exactly as the gate prints them:

      price-differs:<repo>:<row>[:above-<N>]   the row may carry the vendor's
          DATED price from `price_from` ahead of that date (the dearer of two
          dated rates, chosen so passing the date never leaves the row under-
          charging). Red as stale once `price_from` has passed, because the
          row then needs no exception.
      fallback-below-current:<repo>:<model>   the fallback may stay below that
          current model's price. Red as stale once it no longer is.
      tier-not-on-page:<repo>:<row>:above-<N>   the vendor's page states no
          prompt-length price for this model, so the table's long-prompt tier
          cannot be judged; the row is the book's own. Red as stale once the page
          does state that tier, or the row is gone.

    ESTATE_GATES_PRICE_EXCEPTIONS points the gate at another file, so the
    self-test can plant a stale one.
    """

    def __init__(self, c: E.Check, day: datetime.date):
        path = os.environ.get("ESTATE_GATES_PRICE_EXCEPTIONS")
        self.path = pathlib.Path(path) if path else EXCEPTIONS_DEFAULT
        self.entries: dict[str, dict] = {}
        self.seen: set[str] = set()
        self.used: set[str] = set()
        if not self.path.is_file():
            c.note(f"No exceptions file at {self.path}: no disagreement below is excused.")
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            entries = data["exceptions"]
            if not isinstance(entries, dict):
                raise ValueError("'exceptions' is not an object")
        except (ValueError, KeyError, TypeError) as e:
            c.missing(
                "c23.stale-exception",
                f"{self.path} cannot be read as an exceptions file ({e}), so every decision "
                f"recorded in it is unaccounted for.",
            )
            return
        for key, entry in sorted(entries.items()):
            problem = self._problem(key, entry, day)
            if problem:
                c.missing("c23.stale-exception", f"the exception {key!r} {problem}.", [f"  file: {self.path}"])
                continue
            self.entries[key] = entry

    @staticmethod
    def _problem(key: str, entry, day: datetime.date) -> str | None:
        m = _EXCEPTION_KEY.match(key)
        if not m:
            return "is not keyed `price-differs:<repo>:<row>` or `fallback-below-current:<repo>:<model>`"
        if not isinstance(entry, dict):
            return "is not an object"
        for field in ("why", "recorded", "provenance"):
            if not str(entry.get(field, "")).strip():
                return f"has no `{field}`"
        if m.group(1) == "price-differs":
            try:
                start = datetime.date.fromisoformat(str(entry.get("price_from")))
            except ValueError:
                return "has no `price_from` date, the dated price the row may carry early"
            if start <= day:
                return (f"accepts the price from {start.isoformat()}, which is in effect now, so the row "
                        f"needs no exception (or no longer matches it). Remove the entry")
        return None

    def ask(self, key: str) -> dict | None:
        self.seen.add(key)
        return self.entries.get(key)

    def apply(self, c: E.Check, key: str, what: str) -> None:
        e = self.entries[key]
        self.used.add(key)
        c.ok(f"c23.excepted:{key}", f"EXCEPTION {key}: {what}")
        c.note(f"EXCEPTION {key}: {e['why']} (recorded {e['recorded']}; {e['provenance']}).")

    def finish(self, c: E.Check, evaluable) -> None:
        for key in sorted(self.entries):
            if key in self.used:
                continue
            if key in self.seen or evaluable(key):
                c.missing(
                    "c23.stale-exception",
                    f"the exception {key!r} excused nothing this run: the subject agrees without it, "
                    f"matches neither price, or is gone. Remove it or correct it.",
                    [f"  file: {self.path}", f"  why it was recorded: {self.entries[key]['why']}"],
                )
            else:
                c.note(f"exception {key}: its subject was not measured this run, so it was not evaluated.")


# ----------------------------------------------------------- row printing


def suggested(fmt: str, key: str, prices: dict, url: str, day: datetime.date, above: int | None = None) -> str:
    """The row as it should read, in the table's own format."""
    if fmt == "tokenfuse-constants":
        row = {"model": key}
        if above is not None:
            row["above_prompt_tokens"] = above
        for comp, field in P._TF_FIELDS.items():
            if comp in prices:
                row[field] = round(prices[comp] * 1e6)
        where = "price_book.long_context" if above is not None else "price_book.models"
        return f"{json.dumps(row)}  (in {where})"
    if fmt == "verdryx-pricebook":
        args = ", ".join(P.fmt(prices.get(c, 0.0)) for c in P._VERDRYX_ORDER)
        if above is not None:
            return f'.with_long_context("{key}", {above}, ModelPrice({args}))'
        return f'.with_price("{key}", ModelPrice({args}))'
    if fmt == "go-price-map":
        if above is not None:
            return "(this table has no prompt-length tier)"
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
            data = reader(text, where)
        except E.Missing as m:
            c.missing("c23.table-unreadable", f"{repo}'s price table could not be read: {m}.")
            continue
        tables.append(Table(repo, path, decl["format"], where, data,
                            decl["every_current_model"], str(decl.get("why", "")).strip()))
    return tables


def _fetch_vendors(c: E.Check, estate: E.Estate, fetch: Fetcher, needed: list) -> tuple[dict, set]:
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
            c.missing("c23.source-unparseable", f"{name}: {problem}.", [f"  source: {url}"])
        for n in v.notes:
            c.note(f"{name}: {n}.")
        listed = "listed" if key == "openrouter" else "on the page"
        current = f", current: {', '.join(v.current)}" if v.current is not None else ""
        c.note(f"{name}: {len(v.models)} models {listed}{current}.")
    return vendors, unmeasured


def _differs(c, t, key, row, v, label, cands, exc, ekey, tiers, day, above=None) -> bool:
    """Report a row that equals none of `cands`, unless a recorded exception
    accepts the vendor's dated price. Returns True when it was excused."""
    entry = exc.ask(ekey)
    if entry:
        start = datetime.date.fromisoformat(str(entry["price_from"]))
        later = [o for o in P.candidates(v.models.get(label[1], []), label[2], start, tiers)
                 if P.shared(row, o) and (above is None or o.above == above)]
        ok = [o for o in later if not P.mismatches(row, o)]
        if ok:
            exc.apply(c, ekey, f"{t.repo}: {key} carries {label[0]}'s price {ok[0].describe()} ahead of its date "
                               f"({fmt_prices({k: row[k] for k in P.shared(row, ok[0])})}).")
            return True
    best = min(cands, key=lambda o: (len(P.mismatches(row, o)), P.distance(row, o), o.tier != cands[0].tier))
    fixed = dict(row)
    fixed.update({k: best.prices[k] for k in P.shared(row, best)})
    detail = [
        f"  ours:     {t.where}, row {key!r}" + (f", tier above {above:,} prompt tokens" if above else ""),
        f"  official: {v.url}, {label[0]}, {best.describe()}",
    ]
    for comp in P.mismatches(row, best):
        detail.append(f"  {comp}: ours {P.fmt(row[comp])}, official {P.fmt(best.prices[comp])} (USD per 1M tokens)")
    if len(cands) > 1:
        detail.append(f"  ({len(cands)} official prices apply to this id; it matches none of them, the nearest is shown)")
    detail.append(f"  should read: {suggested(t.fmt, key, fixed, v.url, day, above)}")
    kept = [k for k in P.COMPONENTS if k in row and k not in best.prices]
    if kept:
        detail.append(f"  ({', '.join(kept)}: not stated by {v.name}, kept as the table has them; the table's own rule decides)")
    if entry:
        detail.append(f"  the exception {ekey} accepts the price from {entry['price_from']}, and the row matches that neither")
    else:
        detail.append(f"  exception key, if this is a recorded choice: {ekey}")
    c.drift("c23.price-differs", f"{t.repo} prices {key}{' above ' + format(above, ',') + ' prompt tokens' if above else ''} differently from {v.name}'s page.", detail)
    return False


def run(estate: E.Estate) -> E.Check:
    c = E.Check("C23", "built-in model price tables match the vendors' current prices", estate)
    day = today()
    fetch = Fetcher()
    c.note(f"Vendor prices read from {fetch.label()}; today is {day.isoformat()} (UTC).")

    tables = _subjects(c, estate)
    exc = Exceptions(c, day)
    if not tables:
        return c

    resolved = {t.repo: {k: P.resolve(k) for k in set(t.rows) | set(t.long or {})} for t in tables}
    needed = sorted({tg.vendor for rs in resolved.values() for tg in rs.values() if tg and tg.vendor != "openrouter"})
    vendors, unmeasured = _fetch_vendors(c, estate, fetch, needed)

    compared: dict[tuple[str, str], P.Vendor] = {}
    failed_models: set[tuple[str, str]] = set()

    # -- every row against the vendor's price in effect today -----------------
    for t in tables:
        matched, nosource, notlisted, unjudged = 0, [], [], []
        tiers = "base" if t.long is not None else "all"
        for key in sorted(t.rows):
            row, tg = t.rows[key], resolved[t.repo][key]
            if tg is None:
                nosource.append(key)
                continue
            if tg.vendor == "openrouter":
                got = _openrouter_row(c, estate, fetch, t, key, row, tg.model, exc, day)
                if got is None:
                    unjudged.append(key)
                    unmeasured.add("openrouter")
                else:
                    matched += 1
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
            cands = [o for o in P.candidates(offers, tg.endpoint, day, tiers) if P.shared(row, o)]
            if not cands:
                unjudged.append(key)
                continue
            matched += 1
            compared[(tg.vendor, tg.model)] = v
            label = (f"{v.name} {v.names.get(tg.model, tg.model)}", tg.model, tg.endpoint)
            good = [o for o in cands if not P.mismatches(row, o)]
            ekey = f"price-differs:{t.repo}:{key}"
            if good:
                exc.ask(ekey)
                c.ok(
                    f"c23.row:{t.repo}:{key}",
                    f"{t.repo}: {key} = {label[0]}, {good[0].describe()} ({fmt_prices({k: row[k] for k in P.shared(row, good[0])})}).",
                )
            elif not _differs(c, t, key, row, v, label, cands, exc, ekey, tiers, day):
                failed_models.add((tg.vendor, tg.model))
            # A table that CAN carry a tier and carries none for a model the
            # vendor prices by prompt length bills every long prompt at the base.
            if t.long is not None and key not in t.long:
                vlong = P.candidates(offers, tg.endpoint, day, "long")
                if vlong:
                    endpoint = good[0].endpoint if good else vlong[0].endpoint
                    pick = next((o for o in vlong if o.endpoint == endpoint), vlong[0])
                    failed_models.add((tg.vendor, tg.model))
                    c.drift(
                        "c23.price-differs",
                        f"{t.repo} has no prompt-length tier for {key}, and {v.name} prices "
                        f"{v.names.get(tg.model, tg.model)} prompts above {pick.above:,} tokens higher, so every "
                        f"long prompt is billed at the base rate.",
                        [
                            f"  ours:     {t.where}, row {key!r}, no tier",
                            f"  official: {v.url}, {pick.describe()}: {fmt_prices(pick.prices)}",
                            f"  add:      {suggested(t.fmt, key, pick.prices, v.url, day, pick.above)}",
                        ],
                    )
        # -- the tiers the table carries ----------------------------------------
        for key in sorted(t.long or {}):
            tg = resolved[t.repo][key]
            if tg is None:
                nosource.append(f"{key} (tier)")
                continue
            v = vendors.get(tg.vendor)
            if v is None:
                unjudged.append(f"{key} (tier)")
                continue
            if key not in t.rows:
                c.note(f"{t.repo}: {key} has a prompt-length tier and no base row.")
            offers = v.models.get(tg.model)
            if not offers:
                notlisted.append(f"{key} (tier)")
                continue
            label = (f"{v.name} {v.names.get(tg.model, tg.model)}", tg.model, tg.endpoint)
            for above, row in t.long[key]:
                ekey = f"price-differs:{t.repo}:{key}:above-{above}"
                longs = [o for o in P.candidates(offers, tg.endpoint, day, "long") if P.shared(row, o)]
                if not longs:
                    if v.tiers_complete:
                        failed_models.add((tg.vendor, tg.model))
                        base = P.candidates(offers, tg.endpoint, day, "base")
                        c.drift(
                            "c23.price-differs",
                            f"{t.repo} prices {key} higher above {above:,} prompt tokens, and {v.name}'s page "
                            f"prices {v.names.get(tg.model, tg.model)} at one rate for every prompt length.",
                            [
                                f"  ours:     {t.where}, row {key!r}, tier above {above:,}: {fmt_prices(row)}",
                                f"  official: {v.url}, {base[0].describe() if base else 'one rate'}: {fmt_prices(base[0].prices) if base else ''}",
                                "  should read: no tier for this model",
                            ],
                        )
                    else:
                        tkey = f"tier-not-on-page:{t.repo}:{key}:above-{above}"
                        if exc.ask(tkey):
                            exc.apply(c, tkey, f"{t.repo}: {key} above {above:,} prompt tokens is not judged, "
                                               f"because {v.name}'s page states no long-prompt price for it.")
                        else:
                            unjudged.append(f"{key} (tier above {above:,}, which {v.name}'s page does not show)")
                    continue
                matched += 1
                compared[(tg.vendor, tg.model)] = v
                same = [o for o in longs if o.above == above]
                good = [o for o in same if not P.mismatches(row, o)]
                if good:
                    exc.ask(ekey)
                    c.ok(f"c23.tier:{t.repo}:{key}:{above}",
                         f"{t.repo}: {key} above {above:,} tokens = {label[0]}, {good[0].describe()} ({fmt_prices({k: row[k] for k in P.shared(row, good[0])})}).")
                    continue
                if not same:
                    failed_models.add((tg.vendor, tg.model))
                    c.drift(
                        "c23.price-differs",
                        f"{t.repo} starts {key}'s long-prompt price above {above:,} tokens, and {v.name}'s page "
                        f"starts it above {longs[0].above:,}.",
                        [
                            f"  ours:     {t.where}, row {key!r}, tier above {above:,}",
                            f"  official: {v.url}, {longs[0].describe()}",
                            f"  should read: {suggested(t.fmt, key, {**row, **longs[0].prices}, v.url, day, longs[0].above)}",
                        ],
                    )
                    continue
                if not _differs(c, t, key, row, v, label, same, exc, ekey, "long", day, above):
                    failed_models.add((tg.vendor, tg.model))
        if nosource:
            c.not_judged(len(nosource), f"{t.repo}: {len(nosource)} row(s) no source here prices, not judged: {', '.join(nosource)}.")
        if notlisted:
            c.not_judged(len(notlisted), f"{t.repo}: {len(notlisted)} row(s) whose vendor page lists no such model, not judged: {', '.join(notlisted)}.")
        if unjudged:
            c.unmeasured(
                t.repo,
                len(unjudged),
                f"c23.unmeasured:{t.repo}",
                f"{t.repo}: {len(unjudged)} row(s) NOT MEASURED, and no recorded exception declares them: "
                f"{', '.join(unjudged)}. Their source was not read, or states no price for them today.",
            )
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
        for k in t.rows:
            tg = resolved[t.repo][k]
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
                base = [o for o in offers if o.above is None]
                if not base:
                    continue
                compared[(vk, mid)] = v
                detail = [
                    f"  table:    {t.where}",
                    f"  official: {v.url}, {name}, {base[0].describe()}: {fmt_prices(base[0].prices)}",
                    f"  add:      {suggested(t.fmt, mid, base[0].prices, v.url, day)}",
                ]
                for o in offers:
                    if o.above is not None and t.long is not None:
                        detail.append(f"  add:      {suggested(t.fmt, mid, o.prices, v.url, day, o.above)}")
                    elif o is not base[0]:
                        detail.append(f"  the page also prices it {o.describe()}: {fmt_prices(o.prices)}")
                unstated = [comp for comp in P.COMPONENTS if comp not in base[0].prices]
                if unstated and t.fmt == "tokenfuse-constants":
                    detail.append(f"  ({', '.join(unstated)}: not stated by {v.name}; the book's own rule decides)")
                if t.fallback:
                    detail.append(f"  until then it is billed at the fallback: {fmt_prices(t.fallback)}")
                c.drift(
                    "c23.current-model-missing",
                    f"{t.repo} has no row for {name}, which {v.name}'s page lists as a current model.",
                    detail,
                )

    # -- the gateway's fallback is never cheaper than a current model ---------
    for t in tables:
        if not t.fallback or not t.every_current:
            continue
        below = []
        for vk, v in sorted(vendors.items()):
            for mid in v.current or []:
                ekey = f"fallback-below-current:{t.repo}:{mid}"
                lines = []
                for o in v.models.get(mid, []):
                    if not o.in_effect(day):
                        continue
                    for comp in P.COMPONENTS:
                        if comp in t.fallback and comp in o.prices and t.fallback[comp] < o.prices[comp] and not P.close(t.fallback[comp], o.prices[comp]):
                            lines.append(f"  {comp}: fallback {P.fmt(t.fallback[comp])} < {v.name} {v.names.get(mid, mid)} {P.fmt(o.prices[comp])} ({o.describe()})")
                if not lines:
                    exc.ask(ekey)
                    continue
                if exc.ask(ekey):
                    exc.apply(c, ekey, f"{t.repo}'s fallback stays below {v.name} {v.names.get(mid, mid)}: " + "; ".join(x.strip() for x in lines))
                    continue
                below += lines + [f"  exception key, if this is a recorded choice: {ekey}"]
        if below:
            c.drift(
                "c23.fallback-below-current",
                f"{t.repo}'s fallback price is below a current model's, so a call the table "
                f"does not list is billed under its price, the direction that costs money.",
                [f"  table: {t.where}"] + below,
            )
        else:
            c.ok(f"c23.fallback:{t.repo}", f"{t.repo}'s fallback ({fmt_prices(t.fallback)}) is at or above every current model's price, or the exception says why not.")

    read_repos = {t.repo for t in tables}

    def evaluable(key: str) -> bool:
        # Its table was read and every page was measured: an exception that
        # excused nothing in such a run describes nothing, whatever the reason.
        return _EXCEPTION_KEY.match(key).group(2) in read_repos and not unmeasured

    exc.finish(c, evaluable)

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
            new = [x for x in v.models[mid] if x.in_effect(when) and x.endpoint in ("global", "any") and x.above is None]
            what = f"{v.name} {v.names.get(mid, mid)} changes price on {when.isoformat()}"
            if new:
                what += f" (global then: {fmt_prices(new[0].prices)})"
            if when <= horizon:
                c.note(f"WARN: {what}, within {WARN_DAYS} days. A row still at today's price goes red that day.")
            else:
                c.note(f"{what}, more than {WARN_DAYS} days away.")

    # -- secondary signal --------------------------------------------------------
    _secondary(c, estate, fetch, vendors, sorted((k for k in compared if k[0] in P.FIRST_PARTY_TAG and (k in failed_models or k[1] in (vendors[k[0]].current or [])))), day)

    if vendors.get("google") and any(t.every_current for t in tables):
        priced_google = {tg.model for rs in resolved.values() for tg in rs.values() if tg and tg.vendor == "google"}
        unpriced = sorted(set(vendors["google"].models) - priced_google)
        if unpriced:
            c.not_judged(len(unpriced), f"Google Vertex AI: {len(unpriced)} model(s) no table prices, listed and not judged: {', '.join(unpriced)}.")
    return c


def _openrouter_row(c, estate, fetch, t, key, row, oid, exc, day) -> bool | None:
    """A row billed through OpenRouter, against every provider it routes to.

    PASS when the row equals one provider's price exactly, every component
    compared from that one provider; red listing every provider when it equals
    none; red when OpenRouter lists no provider for the model. Never against
    OpenRouter's model list, whose single price switches provider as they come
    and go. Returns None when the answer could not be read (not measured).
    """
    url = P.OPENROUTER_ENDPOINTS_URL.format(id=oid)
    ekey = f"price-differs:{t.repo}:{key}"
    exc.ask(ekey)
    try:
        text = fetch.get(url, f"openrouter-endpoints/{oid}.json", accept_404=True)
    except Unreachable as u:
        estate.source_unreachable(f"OpenRouter endpoints of {oid}", str(u))
        c.unavailable(
            f"c23.source-unreachable:openrouter:{oid}",
            f"OpenRouter's providers for {oid} could not be fetched ({u}), so {t.repo}'s row {key} "
            f"was measured against nothing; that is not a pass.",
        )
        return None
    try:
        providers = P.parse_openrouter_providers(text)
    except E.Missing as m:
        c.missing(
            "c23.source-unparseable",
            f"OpenRouter's provider list for {oid} was fetched and no longer parses, so this gate "
            f"measured nothing for {t.repo}'s row {key}: {m}.",
            [f"  source: {url}"],
        )
        return False
    if not providers:
        c.missing(
            "c23.no-endpoints",
            f"{t.repo} prices {key}, and OpenRouter "
            + ("does not know the model" if providers is None else "lists no provider with a price for it")
            + ", so a call billed through it has no price to be checked against.",
            [f"  ours:     {t.where}, row {key!r}: {fmt_prices(row)}", f"  official: {url}"],
        )
        return False
    listing = [
        f"  {p['name']} ({p['tag']}{'' if p['status'] in (0, None) else ', status ' + str(p['status'])}): {fmt_prices(p['prices'])}"
        for p in providers
    ]
    matches = []
    for p in providers:
        comps = [k for k in P.COMPONENTS if k in row and k in p["prices"]]
        if comps and all(P.exact(row[k], p["prices"][k]) for k in comps):
            matches.append(p)
    if matches:
        names = ", ".join(f"{p['name']} ({p['tag']})" for p in matches)
        c.ok(
            f"c23.row:{t.repo}:{key}",
            f"{t.repo}: {key} = OpenRouter provider {names}, exactly ({fmt_prices(row)}); "
            f"{len(providers)} provider(s) listed.",
        )
        return True
    c.drift(
        "c23.price-differs",
        f"{t.repo} prices {key} at a price none of OpenRouter's {len(providers)} provider(s) for {oid} charges.",
        [f"  ours:     {t.where}, row {key!r}: {fmt_prices(row)}", f"  official: {url}, every provider listed today:"]
        + listing
        + [f"  should read one of: {suggested(t.fmt, key, p['prices'], url, day)}" for p in providers]
        + [f"  exception key, if this is a recorded choice: {ekey}"],
    )
    return True


def _secondary(c: E.Check, estate: E.Estate, fetch: Fetcher, vendors: dict, keys: list, day: datetime.date) -> None:
    agree, disagree, unread = 0, [], []
    for vk, mid in keys[:SECONDARY_LIMIT]:
        v = vendors[vk]
        oid = P.openrouter_id(vk, mid)
        try:
            text = fetch.get(P.OPENROUTER_ENDPOINTS_URL.format(id=oid), f"openrouter-endpoints/{oid}.json")
            eps = P.parse_openrouter_endpoints(text)
        except (Unreachable, E.Missing) as e:
            why = str(e)[:200]
            unread.append(f"{oid} ({why})")
            # OpenRouter is a source outside the estate: a secondary answer it
            # never gave is incomplete (exit 2), never a partial a repository excuses.
            estate.source_unreachable(f"OpenRouter endpoints of {oid}", why)
            c.unavailable(f"c23.secondary-unmeasured:{oid}",
                          f"OpenRouter's secondary signal for {oid} is NOT MEASURED ({why}). "
                          f"The vendor page was not checked against it; that is not a pass.")
            continue
        theirs = [o for o in eps.get(P.FIRST_PARTY_TAG[vk], []) if o.above is None]
        ours = [o for o in v.models.get(mid, []) if o.in_effect(day) and o.endpoint in ("global", "any") and o.above is None]
        if not theirs or not ours:
            why = f"no {P.FIRST_PARTY_TAG[vk]} endpoint row"
            unread.append(f"{oid} ({why})")
            estate.source_unreachable(f"OpenRouter endpoints of {oid}", why)
            c.unavailable(f"c23.secondary-unmeasured:{oid}",
                          f"OpenRouter's secondary signal for {oid} is NOT MEASURED ({why}). "
                          f"The vendor page was not checked against it; that is not a pass.")
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
