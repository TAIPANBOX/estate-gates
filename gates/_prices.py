"""Price tables and the vendor pages they claim to copy: one reader per shape.

This module holds READERS and nothing that decides. C3 compares verdryx's
mirror with tokenfuse's book and C23 compares both books, and costcrew's, with
the vendors' own pages. Both need the same two table readers, and a second
reader of a file whose shape is load-bearing for two checks is the copy hazard
this repository exists to find elsewhere (the precedent is `parse_registry`,
which moved into `_estate.py` the day C8 needed C4's table).

Every reader returns data or raises `_estate.Missing` with a sentence naming
what stopped matching. No reader returns an empty answer for an input it could
not read: an empty price list reads as "nothing to compare", which is a pass
nobody earned.

UNITS. Everything a reader returns is US dollars per million tokens, as a float.
The tokenfuse artifact stores micro-dollars per million tokens and states its
unit; a reader that does not recognise the unit refuses rather than guesses,
because a 1e6 error is the mistake a price table makes.

COMPONENTS. A price is a dict over these names, holding only the components the
source actually states. A component a vendor does not state is ABSENT, never
zero: OpenAI states no cache-write price for most models, and a zero there
would compare as a disagreement with every table that wrote the input price.
"""

from __future__ import annotations

import ast
import dataclasses
import datetime
import html
import json
import math
import re
from html.parser import HTMLParser

import _estate as E

COMPONENTS = ("input", "output", "cache_read", "cache_write", "cache_write_1h")

# ------------------------------------------------------------- the tables


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


_TF_FIELDS = {
    "input": "input_per_mtok_microusd",
    "output": "output_per_mtok_microusd",
    "cache_read": "cache_read_per_mtok_microusd",
    "cache_write": "cache_write_per_mtok_microusd",
    "cache_write_1h": "cache_write_1h_per_mtok_microusd",
}
#: The one component the artifact may omit: books generated before the 1-hour
#: cache write existed carry four rates, not five.
_TF_OPTIONAL = {"cache_write_1h"}


def tokenfuse_book(book, where: str) -> tuple[dict[str, dict], dict]:
    """`price_book` of tokenfuse's constants artifact: model -> prices, fallback."""
    if not isinstance(book, dict):
        raise E.Missing(f"{where} has no 'price_book' object")
    models = book.get("models")
    fallback = book.get("fallback")
    if not isinstance(models, list) or not models or not isinstance(fallback, dict):
        raise E.Missing(f"{where} has no usable 'price_book' with models and a fallback")
    if book.get("units") != "microusd_per_mtok":
        raise E.Missing(
            f"{where} declares price units {book.get('units')!r}, and this check only "
            f"knows how to convert 'microusd_per_mtok'. Comparing numbers whose unit is "
            f"unknown is how a 1e6 error ships."
        )

    def rates(entry, label: str) -> dict:
        out = {}
        for comp, field in _TF_FIELDS.items():
            v = entry.get(field)
            if v is None and comp in _TF_OPTIONAL:
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise E.Missing(f"{where}: {label} has no numeric {field}")
            out[comp] = v / 1e6
        return out

    prices: dict[str, dict] = {}
    for m in models:
        if not isinstance(m, dict) or not isinstance(m.get("model"), str):
            raise E.Missing(f"{where}: a price_book row has no 'model' string")
        prices[m["model"]] = rates(m, f"the row for {m['model']}")
    return prices, rates(fallback, "the fallback")


def tokenfuse_artifact(text: str, where: str) -> tuple[dict[str, dict], dict]:
    try:
        data = json.loads(text)
    except ValueError as e:
        raise E.Missing(f"{where} is not JSON ({e})") from None
    if not isinstance(data, dict):
        raise E.Missing(f"{where} is not a JSON object")
    return tokenfuse_book(data.get("price_book"), where)


#: verdryx's ModelPrice takes (input, output, cache_read, cache_write).
_VERDRYX_ORDER = ("input", "output", "cache_read", "cache_write")


def verdryx_book(pricing_py: str, where: str) -> tuple[dict[str, tuple], tuple | None]:
    """Walk verdryx's chained .with_price(...)/.with_fallback(...) builder.

    Parsed from the AST rather than by regular expression: the arguments are
    numeric literals in a call chain, and ast gives them exactly. Returns
    4-tuples in ModelPrice's own argument order, missing trailing arguments as
    0.0 the way the dataclass defaults them.
    """
    try:
        tree = ast.parse(pricing_py)
    except SyntaxError as e:
        raise E.Missing(f"{where} does not parse as Python ({e.msg}, line {e.lineno})") from None
    prices: dict[str, tuple] = {}
    fallback: tuple | None = None

    def price_args(call) -> tuple | None:
        if not isinstance(call, ast.Call):
            return None
        fn = call.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        if name != "ModelPrice":
            return None
        vals = []
        for a in call.args:
            v = _literal(a)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
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
            f"{where} matched no `.with_price(\"model\", ModelPrice(...))` "
            f"calls, so no price was read from the mirror"
        )
    return prices, fallback


def verdryx_rows(pricing_py: str, where: str) -> tuple[dict[str, dict], dict | None]:
    prices, fallback = verdryx_book(pricing_py, where)
    as_dict = lambda t: dict(zip(_VERDRYX_ORDER, t))  # noqa: E731
    return {m: as_dict(t) for m, t in prices.items()}, (as_dict(fallback) if fallback else None)


def go_code_only(src: str) -> str:
    """Go source with comments blanked, string and rune literals kept intact.

    A naive `//` strip cuts a Source string holding a URL in half; this walks
    the literals. Blanked rather than deleted so offsets still mean something.
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", src[i:j]))
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append(src[i : j + 1])
            i = j + 1
        elif c == "`":
            j = src.find("`", i + 1)
            j = n - 1 if j < 0 else j
            out.append(src[i : j + 1])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


_GO_MAP = re.compile(r"\bvar\s+prices\s*=\s*map\[string\]Price\s*\{")
_GO_ENTRY = re.compile(r'"((?:[^"\\\n]|\\.)*)"\s*:\s*\{([^{}]*)\}')
_GO_FIELD = {"input": "InPerM", "output": "OutPerM"}
_GO_NUMBER = re.compile(r"^[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")


def costcrew_rows(src: str, where: str) -> tuple[dict[str, dict], None]:
    """costcrew's `var prices = map[string]Price{...}`: key -> input, output.

    costcrew has no fallback, on purpose: an unknown model is refused rather
    than priced.
    """
    code = go_code_only(src)
    m = _GO_MAP.search(code)
    if not m:
        raise E.Missing(
            f"{where} has no `var prices = map[string]Price{{...}}`, which is the table "
            f"this check reads. Its absence means the table moved, not that it agrees"
        )
    depth, i = 1, m.end()
    while i < len(code) and depth:
        depth += {"{": 1, "}": -1}.get(code[i], 0)
        i += 1
    if depth:
        raise E.Missing(f"{where}: the prices map never closes")
    body = code[m.end() : i - 1]
    rows: dict[str, dict] = {}
    for key, fields in _GO_ENTRY.findall(body):
        row = {}
        for comp, name in _GO_FIELD.items():
            f = re.search(rf"\b{name}\s*:\s*([^,\n}}]+)", fields)
            if not f:
                raise E.Missing(f"{where}: the entry {key!r} has no {name}")
            text = f.group(1).strip()
            if not _GO_NUMBER.match(text):
                raise E.Missing(
                    f"{where}: the entry {key!r} sets {name} to `{text}`, which this check "
                    f"cannot evaluate as a number"
                )
            row[comp] = float(text)
        rows[key] = row
    if not rows:
        raise E.Missing(f"{where}: the prices map holds no entry this check can read")
    return rows, None


#: format name (as estate.json declares it) -> reader(text, where) -> (rows, fallback)
TABLE_READERS = {
    "tokenfuse-constants": tokenfuse_artifact,
    "verdryx-pricebook": verdryx_rows,
    "go-price-map": costcrew_rows,
}

# --------------------------------------------------------------- offers


@dataclasses.dataclass
class Offer:
    """One way a vendor sells one model: a set of rates, on an endpoint, for a
    prompt-length tier, during a window of days (both ends inclusive)."""

    prices: dict
    endpoint: str = "global"  # global | regional | any
    tier: str = ""
    start: datetime.date | None = None
    end: datetime.date | None = None

    def in_effect(self, day: datetime.date) -> bool:
        return (self.start is None or self.start <= day) and (self.end is None or day <= self.end)

    def describe(self) -> str:
        bits = [self.endpoint if self.endpoint != "any" else "every endpoint"]
        if self.tier:
            bits.append(self.tier)
        if self.start:
            bits.append(f"from {self.start.isoformat()}")
        if self.end:
            bits.append(f"through {self.end.isoformat()}")
        return ", ".join(bits)


@dataclasses.dataclass
class Vendor:
    key: str
    name: str
    url: str
    models: dict = dataclasses.field(default_factory=dict)  # id -> [Offer]
    names: dict = dataclasses.field(default_factory=dict)  # id -> name as printed
    current: list | None = None  # ids the page itself marks current; None: unmarked
    problems: list = dataclasses.field(default_factory=list)  # anchors that matched nothing
    notes: list = dataclasses.field(default_factory=list)

    def add(self, model: str, name: str, offer: Offer) -> None:
        self.models.setdefault(model, []).append(offer)
        self.names.setdefault(model, name)


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


def parse_date(text: str) -> datetime.date | None:
    m = re.fullmatch(r"\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s*", text)
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    try:
        return datetime.date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    except ValueError:
        return None


def dollars(text) -> float | None:
    """`$2.50 / MTok` -> 2.5; anything without a dollar amount -> None."""
    if text is None:
        return None
    m = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", str(text))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


# ------------------------------------------------------------ HTML tables


class _Cell:
    __slots__ = ("tag", "attrs", "parts")

    def __init__(self, tag: str, attrs: dict):
        self.tag, self.attrs, self.parts = tag, attrs, []

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


class _Table:
    def __init__(self, context: dict):
        self.context = context
        self.groups: list[list[list[_Cell]]] = []  # thead and each tbody, in order
        self.group_kinds: list[str] = []

    def rows(self, kind: str | None = None):
        for k, g in zip(self.group_kinds, self.groups):
            if kind is None or k == kind:
                yield from g


class TableReader(HTMLParser):
    """Every <table> on a page, with what surrounds it.

    Each table records the h1/h2/h3 above it, the label of the tab panel it
    sits in, and the astro island it sits in. That context is what tells a
    Standard price from a Priority one on pages whose headers are identical
    across tabs.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self.tabs: dict[str, str] = {}
        self.islands: list[dict] = []
        self.text_parts: list[str] = []
        self._headings = {"h1": "", "h2": "", "h3": ""}
        self._heading: tuple[str, list] | None = None
        self._tab: tuple[str, dict, list] | None = None
        self._divs = 0
        self._panels: list[tuple[int, str]] = []
        self._island_stack: list[int] = []
        self._skip = 0
        self._table: _Table | None = None
        self._nested = 0
        self._row: list[_Cell] | None = None
        self._cell: _Cell | None = None

    # -- structure ---------------------------------------------------------

    def _close_cell(self):
        if self._cell is not None and self._row is not None:
            self._row.append(self._cell)
        self._cell = None

    def _close_row(self):
        self._close_cell()
        if self._row is not None and self._table is not None:
            if not self._table.groups:
                self._table.groups.append([])
                self._table.group_kinds.append("body")
            self._table.groups[-1].append(self._row)
        self._row = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3"):
            self._heading = (tag, [])
        if a.get("role") == "tab" and a.get("id"):
            self._tab = (a["id"], a, [])
        if tag == "div":
            self._divs += 1
            if a.get("role") == "tabpanel":
                self._panels.append((self._divs, a.get("aria-labelledby", "")))
        if tag == "astro-island":
            self.islands.append(a)
            self._island_stack.append(len(self.islands) - 1)
        if tag == "table":
            if self._table is not None:
                self._nested += 1
                return
            self._table = _Table(
                {
                    **self._headings,
                    "panel": self._panels[-1][1] if self._panels else None,
                    "island": self._island_stack[-1] if self._island_stack else None,
                }
            )
            return
        if self._table is None or self._nested:
            if tag == "br" and self._cell is not None:
                self._cell.parts.append(" ")
            return
        if tag in ("thead", "tbody", "tfoot"):
            self._close_row()
            self._table.groups.append([])
            self._table.group_kinds.append("head" if tag == "thead" else "body")
        elif tag == "tr":
            self._close_row()
            self._row = []
        elif tag in ("td", "th"):
            self._close_cell()
            if self._row is None:
                self._row = []
            self._cell = _Cell(tag, a)
        elif tag == "br" and self._cell is not None:
            self._cell.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if self._heading and tag == self._heading[0]:
            h, parts = self._heading
            self._headings[h] = re.sub(r"\s+", " ", " ".join(parts)).strip()
            if h == "h1":
                self._headings["h2"] = self._headings["h3"] = ""
            elif h == "h2":
                self._headings["h3"] = ""
            self._heading = None
        if self._tab and tag == "button":
            tid, attrs, parts = self._tab
            label = attrs.get("track-metadata-eventdetail") or " ".join(parts)
            self.tabs[tid] = re.sub(r"\s+", " ", label).strip()
            self._tab = None
        if tag == "div":
            if self._panels and self._panels[-1][0] == self._divs:
                self._panels.pop()
            self._divs = max(0, self._divs - 1)
        if tag == "astro-island" and self._island_stack:
            self._island_stack.pop()
        if self._table is None:
            return
        if tag == "table":
            if self._nested:
                self._nested -= 1
                return
            self._close_row()
            self.tables.append(self._table)
            self._table = None
            return
        if self._nested:
            return
        if tag in ("td", "th"):
            self._close_cell()
        elif tag == "tr":
            self._close_row()

    def handle_data(self, data):
        if self._skip:
            return
        self.text_parts.append(data)
        if self._heading:
            self._heading[1].append(data)
        if self._tab:
            self._tab[2].append(data)
        if self._cell is not None and not self._nested:
            self._cell.parts.append(data)

    def close(self):
        super().close()
        if self._table is not None:
            self._close_row()
            self.tables.append(self._table)
            self._table = None

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_parts))


def read_tables(page: str) -> TableReader:
    r = TableReader()
    r.feed(page)
    r.close()
    return r


# -------------------------------------------------------------- Anthropic

ANTHROPIC_URL = "https://platform.claude.com/docs/en/about-claude/pricing"
_ANTHROPIC_COLUMNS = {
    "input": "input",
    "output": "output",
    "5m writes": "cache_write",
    "1h writes": "cache_write_1h",
    "hits and refreshes": "cache_read",
}
_CLAUDE_NAME = re.compile(r"^(Claude(?: [A-Z][A-Za-z]*)+ \d+(?:\.\d+)?)\b")
_PREMIUM = re.compile(
    r"Regional and multi-region endpoints include an? (\d+(?:\.\d+)?)\s*% premium over global endpoints"
)


def anthropic_id(name: str) -> str:
    """`Claude Sonnet 5.5` -> `claude-sonnet-5-5`, the Claude API's spelling."""
    return "-".join(name.lower().replace(".", " ").split())


def parse_anthropic(page: str, url: str = ANTHROPIC_URL) -> Vendor:
    v = Vendor("anthropic", "Anthropic", url)
    doc = read_tables(page)
    table = header = None
    for t in doc.tables:
        for row in t.rows():
            labels = [c.text.lower() for c in row]
            if all(k in labels for k in _ANTHROPIC_COLUMNS):
                table, header = t, labels
                break
        if table:
            break
    if table is None:
        raise E.Missing(
            "no table on Anthropic's pricing page has the columns "
            + ", ".join(repr(k) for k in _ANTHROPIC_COLUMNS)
            + ", which is the model pricing table this check reads"
        )
    cols = {comp: header.index(label) for label, comp in _ANTHROPIC_COLUMNS.items()}
    # The page's header row starts with a Name column the body rows share, so
    # a body row is header-wide and a second tier of the same model is one
    # cell narrower (the name cell spans both).
    width = len(header)

    bodies = [g for k, g in zip(table.group_kinds, table.groups) if k == "body"]
    current: list[str] = []
    divider_seen = False
    last: tuple[str, str] | None = None
    for gi, rows in enumerate(bodies):
        for row in rows:
            if len(row) == 1 and row[0].tag == "th":
                label = (row[0].attrs.get("aria-label") or row[0].text).strip().lower()
                if label.startswith("additional models"):
                    divider_seen = True
                continue
            if len(row) == width:
                m = _CLAUDE_NAME.match(row[0].text)
                if not m:
                    continue
                name = m.group(1)
                cells = row
                offset = 0
            elif len(row) == width - 1 and last is not None:
                name = last[1]
                cells = row
                offset = -1
            else:
                continue
            prices = {}
            for comp, idx in cols.items():
                val = dollars(cells[idx + offset].text) if 0 <= idx + offset < len(cells) else None
                if val is not None:
                    prices[comp] = val
            if "input" not in prices or "output" not in prices:
                continue
            tier_m = re.search(r"for prompts ([^$]*?tokens)", cells[cols["input"] + offset].text)
            tier = tier_m.group(1).strip() if tier_m else ""
            mid = anthropic_id(name)
            v.add(mid, name, Offer(prices, "global", tier))
            last = (mid, name)
            if gi == 0 and not divider_seen and mid not in current:
                current.append(mid)
    if not v.models:
        raise E.Missing(
            "Anthropic's model pricing table was found and no row in it parsed as a "
            "Claude model with an input and an output price"
        )
    if divider_seen and current:
        v.current = current
    else:
        v.problems.append(
            "the model pricing table no longer separates the current models from an "
            "'Additional models' group, so which models are current could not be read"
        )
    pm = _PREMIUM.search(doc.text)
    if pm:
        factor = 1 + float(pm.group(1)) / 100
        for mid, offers in list(v.models.items()):
            for o in list(offers):
                if o.endpoint == "global":
                    v.models[mid].append(Offer(
                        {c: round(p * factor, 9) for c, p in o.prices.items()},
                        "regional", o.tier, o.start, o.end,
                    ))
        v.notes.append(f"regional and multi-region endpoints: list plus {pm.group(1)} percent, as the page states")
    else:
        v.problems.append(
            "the sentence stating the regional and multi-region endpoint premium is gone, "
            "so no row naming a regional endpoint could be judged"
        )
    return v


# ----------------------------------------------------------------- OpenAI

OPENAI_URL = "https://developers.openai.com/api/docs/pricing"
_OPENAI_HEADINGS = ["model", "input", "cached input", "cache writes", "output"]


def _astro(value):
    """Undo Astro's prop serialisation: [0, x] is a value, [1, [...]] an array."""
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int) and not isinstance(value[0], bool):
        kind, inner = value
        if kind == 0:
            return {k: _astro(v) for k, v in inner.items()} if isinstance(inner, dict) else inner
        if kind == 1 and isinstance(inner, list):
            return [_astro(x) for x in inner]
        return None
    if isinstance(value, dict):
        return {k: _astro(v) for k, v in value.items()}
    return value


def _number(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    return float(x)


def parse_openai(page: str, url: str = OPENAI_URL) -> Vendor:
    v = Vendor("openai", "OpenAI", url)
    doc = read_tables(page)
    standard = []
    for idx, island in enumerate(doc.islands):
        if island.get("component-export") != "TextTokenPricingTables":
            continue
        try:
            props = _astro(json.loads(island.get("props", "")))
        except ValueError:
            continue
        if isinstance(props, dict) and props.get("tier") == "standard":
            standard.append((idx, props))
    if len(standard) != 1:
        raise E.Missing(
            f"OpenAI's pricing page carries {len(standard)} text-token price tables marked "
            f"tier 'standard' (component TextTokenPricingTables), and this check reads "
            f"exactly one. The page changed shape"
        )
    idx, props = standard[0]
    heads = []
    for t in doc.tables:
        if t.context.get("island") != idx:
            continue
        for row in t.rows():
            labels = [c.text.lower() for c in row]
            if labels and labels[0] == "model":
                heads = labels
                break
        if heads:
            break
    if heads[: len(_OPENAI_HEADINGS)] != _OPENAI_HEADINGS:
        raise E.Missing(
            "OpenAI's standard text-token table no longer heads its columns "
            + " | ".join(_OPENAI_HEADINGS)
            + f" (it reads {' | '.join(heads) or 'nothing'}), and this check reads the rows by that order"
        )
    rows = props.get("rows")
    if not isinstance(rows, list) or not rows:
        raise E.Missing("OpenAI's standard text-token table carries no rows")
    skipped = []
    order = []
    for row in rows:
        if not isinstance(row, list) or not row or not isinstance(row[0], str):
            skipped.append(repr(row)[:60])
            continue
        raw = row[0]
        name = re.sub(r"\s*\(.*\)\s*$", "", raw).strip()
        tm = re.search(r"\((.*)\)", raw)
        tier = tm.group(1).strip() if tm else ""
        vals = row[1:]
        if len(vals) == 4:
            comps = ("input", "cache_read", "cache_write", "output")
        elif len(vals) == 3:
            comps = ("input", "cache_read", "output")
        else:
            skipped.append(raw)
            continue
        prices = {c: _number(x) for c, x in zip(comps, vals)}
        prices = {c: p for c, p in prices.items() if p is not None}
        if "input" not in prices or "output" not in prices:
            skipped.append(raw)
            continue
        v.add(name, name, Offer(prices, "global", tier))
        order.append(name)
    if not v.models:
        raise E.Missing("no row of OpenAI's standard text-token table parsed")
    if skipped:
        v.notes.append(f"{len(skipped)} OpenAI row(s) in a shape this check does not read: {', '.join(skipped[:6])}")
    n = props.get("collapsedLatestRowCount")
    if isinstance(n, int) and not isinstance(n, bool) and 0 < n <= len(order):
        v.current = order[:n]
    else:
        v.problems.append(
            "the standard text-token table no longer says how many of its rows are the "
            "latest models (collapsedLatestRowCount), so which models are current could not be read"
        )
    return v


# ----------------------------------------------------------------- Vertex

VERTEX_URL = "https://cloud.google.com/vertex-ai/generative-ai/pricing"
_DATE_CLAUSE = re.compile(
    r"\(?\s*\b(through|until|starting|from)\s+([A-Z][a-z]+\s+\d{1,2},\s*\d{4})\s*\)?", re.I
)


def gemini_id(name: str) -> str:
    """`Gemini 3.5 Flash-Lite` -> `gemini-3.5-flash-lite`."""
    return "-".join(name.lower().replace("-", " ").split())


def _gemini_names(cell: str) -> list[tuple[str, datetime.date | None, datetime.date | None]]:
    out = []
    for part in re.split(r",\s*(?=Gemini\b)", cell):
        start = end = None
        for m in _DATE_CLAUSE.finditer(part):
            day = parse_date(m.group(2))
            if day is None:
                continue
            if m.group(1).lower() in ("through", "until"):
                end = day
            else:
                start = day
        name = _DATE_CLAUSE.sub(" ", part).replace("*", " ")
        name = re.sub(r"\s+", " ", name).strip(" ,")
        if re.match(r"^Gemini \d", name):
            out.append((name, start, end))
    return out


def parse_vertex(page: str, url: str = VERTEX_URL) -> Vendor:
    v = Vendor("google", "Google Vertex AI", url)
    doc = read_tables(page)
    used = 0
    for t in doc.tables:
        if t.context.get("h1", "").strip().lower() != "google models":
            continue
        panel = t.context.get("panel")
        if panel is not None:
            label = doc.tabs.get(panel, "")
            if not label.lower().startswith("standard"):
                continue
        header = None
        for row in t.rows():
            labels = [c.text.lower() for c in row]
            if labels and labels[0] == "model" and "type" in labels:
                header = labels
                break
        if not header:
            continue
        if any(re.search(r"priority|flex|batch", h) for h in header):
            continue
        cols = {"model": 0, "type": header.index("type")}
        if "region" in header:
            cols["region"] = header.index("region")
        price_cols = []  # (index, component, tier)
        for i, h in enumerate(header):
            if i in cols.values() or "price" not in h:
                continue
            tier = "over 200K input tokens" if "> 200k" in h else ("up to 200K input tokens" if "<= 200k" in h else "")
            price_cols.append((i, "cached" if "cached" in h else "price", tier))
        if not any(kind == "price" for _, kind, _ in price_cols):
            continue
        used += 1
        names: list = []
        kind = ""
        rows_by: dict = {}
        for row in t.rows():
            if row and row[0].tag == "th":
                continue
            texts = [c.text for c in row]
            if len(texts) < len(header):
                continue
            if texts[0]:
                names = _gemini_names(texts[0])
            if texts[cols["type"]]:
                kind = texts[cols["type"]]
            region = re.sub(r"[^a-z-]", "", texts[cols["region"]].lower()) if "region" in cols else "any"
            endpoint = {"global": "global", "non-global": "regional"}.get(region, "any" if region == "any" else None)
            if not names or endpoint is None:
                continue
            k = kind.lower()
            comp = "input" if re.match(r"^input \(text", k) else ("output" if k.startswith("text output") else None)
            if comp is None:
                continue
            for i, what, tier in price_cols:
                val = dollars(texts[i])
                if val is None:
                    continue
                c = comp if what == "price" else ("cache_read" if comp == "input" else None)
                if c is None:
                    continue
                for name, start, end in names:
                    rows_by.setdefault((name, start, end, endpoint, tier), {})[c] = val
        for (name, start, end, endpoint, tier), prices in rows_by.items():
            if "input" in prices and "output" in prices:
                v.add(gemini_id(name), name, Offer(prices, endpoint, tier, start, end))
    if not v.models:
        raise E.Missing(
            f"no Standard token price table under Vertex AI's 'Google models' heading parsed "
            f"into a Gemini model with an input and an output price ({used} candidate table(s) read)"
        )
    v.notes.append("the page marks no set of current models, so a Gemini model no table prices is listed, not judged")
    return v


# ------------------------------------------------------------- OpenRouter

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{id}/endpoints"
_OPENROUTER_FIELDS = {
    "prompt": "input",
    "completion": "output",
    "input_cache_read": "cache_read",
    "input_cache_write": "cache_write",
    "input_cache_write_1h": "cache_write_1h",
}


def _per_token(pricing: dict) -> dict:
    out = {}
    for field, comp in _OPENROUTER_FIELDS.items():
        raw = pricing.get(field) if isinstance(pricing, dict) else None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(val) or val < 0:
            continue
        out[comp] = round(val * 1e6, 9)
    return out


def _openrouter_offers(pricing: dict) -> list[Offer]:
    base = _per_token(pricing)
    offers = [Offer(base, "global")] if "input" in base and "output" in base else []
    overrides = pricing.get("overrides") if isinstance(pricing, dict) else None
    for ov in overrides if isinstance(overrides, list) else []:
        if not isinstance(ov, dict):
            continue
        p = dict(base)
        p.update(_per_token(ov))
        n = ov.get("min_prompt_tokens")
        offers.append(Offer(p, "global", f"prompts of {n} tokens and more" if n else "override"))
    return offers


def parse_openrouter_models(text: str, url: str = OPENROUTER_MODELS_URL) -> Vendor:
    v = Vendor("openrouter", "OpenRouter", url)
    try:
        data = json.loads(text)
    except ValueError as e:
        raise E.Missing(f"OpenRouter's model list is not JSON ({e})") from None
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise E.Missing("OpenRouter's model list has no 'data' array")
    for m in items:
        if not isinstance(m, dict) or not isinstance(m.get("id"), str):
            continue
        for o in _openrouter_offers(m.get("pricing") or {}):
            v.add(m["id"], m["id"], o)
    if not v.models:
        raise E.Missing("no model in OpenRouter's model list carries a prompt and a completion price")
    return v


def parse_openrouter_endpoints(text: str) -> dict[str, list[Offer]]:
    """tag -> offers, for one model's /endpoints answer."""
    try:
        data = json.loads(text)
    except ValueError as e:
        raise E.Missing(f"OpenRouter's endpoint list is not JSON ({e})") from None
    inner = data.get("data") if isinstance(data, dict) else None
    eps = inner.get("endpoints") if isinstance(inner, dict) else None
    if not isinstance(eps, list):
        raise E.Missing("OpenRouter's endpoint list has no 'data.endpoints' array")
    out = {}
    for ep in eps:
        if isinstance(ep, dict) and isinstance(ep.get("tag"), str):
            offers = _openrouter_offers(ep.get("pricing") or {})
            if offers:
                out[ep["tag"]] = offers
    return out


#: the OpenRouter endpoint tag that is the vendor itself, per vendor key
FIRST_PARTY_TAG = {"anthropic": "anthropic", "openai": "openai", "google": "google-vertex/global"}


def openrouter_id(vendor: str, model: str) -> str:
    """The id OpenRouter lists a vendor model under: Claude versions take a dot."""
    if vendor == "anthropic":
        model = re.sub(r"-(\d+)-(\d+)$", r"-\1.\2", model)
    return f"{vendor}/{model}"


# -------------------------------------------------------------- resolving


@dataclasses.dataclass(frozen=True)
class Target:
    vendor: str  # anthropic | openai | google | openrouter
    model: str
    endpoint: str  # global | regional | unnamed


_BEDROCK = re.compile(r"^(?:([a-z]{2,6})\.)?anthropic\.(claude-.+)$")
_OPENAI_BARE = re.compile(r"^(?:gpt-[0-9][0-9a-z.\-]*|o[1-9](?:-[a-z]+)?|chatgpt-[0-9a-z.\-]+)$")


def claude_model(raw: str) -> str:
    m = re.sub(r"-v\d+(?::\d+)?$", "", raw)
    m = re.sub(r"[-@]\d{8}$", "", m)
    return m.replace(".", "-")


def resolve(key: str) -> Target | None:
    """Which vendor price a table row is a copy of, and on which endpoint.

    `global` is the vendor's list price. `regional` is an endpoint the id names
    as regional. `unnamed` is an id that does not say which endpoint it reaches
    (a bare Bedrock `anthropic.` id, whose endpoint is the URL's; a Google
    `@`-dated id; a Vertex `google/` id): such a row must equal one of the
    endpoint prices, every component from the same one.
    """
    if key.startswith("openrouter/"):
        return Target("openrouter", key[len("openrouter/"):], "global")
    m = _BEDROCK.match(key)
    if m:
        prefix = m.group(1)
        endpoint = "unnamed" if prefix is None else ("global" if prefix == "global" else "regional")
        return Target("anthropic", claude_model(m.group(2)), endpoint)
    if key.startswith("anthropic/"):
        return Target("anthropic", claude_model(key[len("anthropic/"):]), "global")
    if key.startswith("claude-"):
        return Target("anthropic", claude_model(key), "unnamed" if "@" in key else "global")
    if key.startswith("google/gemini-") or key.startswith("gemini-"):
        return Target("google", key.split("/", 1)[-1], "unnamed")
    if key.startswith("openai/"):
        return Target("openai", key[len("openai/"):], "global")
    if _OPENAI_BARE.match(key):
        return Target("openai", key, "global")
    return None


# ----------------------------------------------------------------- compare


def close(ours: float, theirs: float) -> bool:
    """Within half a percent, or a micro-dollar per million tokens."""
    return abs(ours - theirs) <= max(1e-6, 0.005 * max(abs(ours), abs(theirs)))


def candidates(offers: list[Offer], endpoint: str, day: datetime.date) -> list[Offer]:
    allowed = {"global": ("global", "any"), "regional": ("regional", "any")}.get(endpoint, ("global", "regional", "any"))
    return [o for o in offers if o.in_effect(day) and o.endpoint in allowed]


def mismatches(row: dict, offer: Offer) -> list[str]:
    return [c for c in COMPONENTS if c in row and c in offer.prices and not close(row[c], offer.prices[c])]


def shared(row: dict, offer: Offer) -> list[str]:
    return [c for c in COMPONENTS if c in row and c in offer.prices]


def distance(row: dict, offer: Offer) -> float:
    """How far a row is from an offer, in summed log ratios: picks the price a
    wrong row was most plausibly copied from, for the message, never the verdict."""
    total = 0.0
    for c in shared(row, offer):
        a, b = row[c], offer.prices[c]
        total += abs(math.log(a / b)) if a > 0 and b > 0 else (0.0 if a == b else 50.0)
    return total


def fmt(x: float) -> str:
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s or "0"
