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


def _tf_rates(entry: dict, label: str, where: str) -> dict:
    out = {}
    for comp, field in _TF_FIELDS.items():
        v = entry.get(field)
        if v is None and comp in _TF_OPTIONAL:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise E.Missing(f"{where}: {label} has no numeric {field}")
        out[comp] = v / 1e6
    return out


def tokenfuse_long(book, where: str) -> dict[str, list] | None:
    """`price_book.long_context`: model -> [(above_prompt_tokens, prices)].

    None when the artifact has no such block: a book that cannot express a
    prompt-length tier, whose flat rows are then free to carry either tier.
    """
    if not isinstance(book, dict) or "long_context" not in book:
        return None
    block = book["long_context"]
    if not isinstance(block, list):
        raise E.Missing(f"{where}: 'price_book.long_context' is not a list")
    out: dict[str, list] = {}
    for m in block:
        if not isinstance(m, dict) or not isinstance(m.get("model"), str):
            raise E.Missing(f"{where}: a long_context row has no 'model' string")
        above = m.get("above_prompt_tokens")
        if isinstance(above, bool) or not isinstance(above, int) or above <= 0:
            raise E.Missing(f"{where}: the long_context row for {m['model']} has no positive integer above_prompt_tokens")
        out.setdefault(m["model"], []).append((above, _tf_rates(m, f"the long_context row for {m['model']}", where)))
    return out


def tokenfuse_artifact(text: str, where: str) -> "TableData":
    try:
        data = json.loads(text)
    except ValueError as e:
        raise E.Missing(f"{where} is not JSON ({e})") from None
    if not isinstance(data, dict):
        raise E.Missing(f"{where} is not a JSON object")
    rows, fallback = tokenfuse_book(data.get("price_book"), where)
    return TableData(rows, fallback, tokenfuse_long(data.get("price_book"), where))


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


def _model_price(node) -> dict | None:
    if not isinstance(node, ast.Call):
        return None
    fn = node.func
    if (fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")) != "ModelPrice":
        return None
    vals = [_literal(a) for a in node.args]
    if not vals or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in vals):
        return None
    vals = [float(v) for v in vals] + [0.0] * 4
    return dict(zip(_VERDRYX_ORDER, vals[:4]))


def verdryx_long(pricing_py: str, where: str) -> dict[str, list] | None:
    """`.with_long_context(...)` calls: model -> [(above_prompt_tokens, prices)].

    Read in the shapes a builder call plausibly takes: (model, above, price),
    the same with keywords (`above_prompt_tokens=`, `price=`), or (model,
    LongContext(above, price)). A call in any other shape is refused rather
    than skipped, because a tier this reader cannot see would leave the long
    prompts of that model compared with nothing. None when the module neither
    defines nor calls `with_long_context`.
    """
    try:
        tree = ast.parse(pricing_py)
    except SyntaxError as e:
        raise E.Missing(f"{where} does not parse as Python ({e.msg}, line {e.lineno})") from None
    defined = any(isinstance(n, ast.FunctionDef) and n.name == "with_long_context" for n in ast.walk(tree))
    out: dict[str, list] = {}
    called = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or getattr(node.func, "attr", "") != "with_long_context":
            continue
        called = True
        args = list(node.args)
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        model = _literal(args[0]) if args else _literal(kw.get("model"))
        rest = args[1:]
        if len(rest) == 1 and isinstance(rest[0], ast.Call) and getattr(rest[0].func, "id", getattr(rest[0].func, "attr", "")) == "LongContext":
            inner = rest[0]
            rest = list(inner.args)
            kw = {**kw, **{k.arg: k.value for k in inner.keywords if k.arg}}
        above = _literal(rest[0]) if rest else _literal(kw.get("above_prompt_tokens", kw.get("above")))
        price = _model_price(rest[1]) if len(rest) > 1 else _model_price(kw.get("price"))
        if not isinstance(model, str) or isinstance(above, bool) or not isinstance(above, int) or above <= 0 or price is None:
            raise E.Missing(
                f"{where} line {node.lineno}: a `.with_long_context(...)` call this reader cannot read "
                f"as (model, above_prompt_tokens, ModelPrice(...))"
            )
        out.setdefault(model, []).append((above, price))
    return out if (called or defined) else None


def verdryx_rows(pricing_py: str, where: str) -> "TableData":
    prices, fallback = verdryx_book(pricing_py, where)
    as_dict = lambda t: dict(zip(_VERDRYX_ORDER, t))  # noqa: E731
    return TableData(
        {m: as_dict(t) for m, t in prices.items()},
        as_dict(fallback) if fallback else None,
        verdryx_long(pricing_py, where),
    )


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


def costcrew_rows(src: str, where: str) -> "TableData":
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
    return TableData(rows, None, None)


@dataclasses.dataclass
class TableData:
    """One price table as read: base rows, the fallback (None: the table has
    none), and the prompt-length tiers (None: the table cannot express one)."""

    rows: dict
    fallback: dict | None
    long: dict | None


#: format name (as estate.json declares it) -> reader(text, where) -> TableData
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
    #: a prompt-length tier: this price applies to prompts strictly above this
    #: many tokens. None is the base price.
    above: int | None = None

    def in_effect(self, day: datetime.date) -> bool:
        return (self.start is None or self.start <= day) and (self.end is None or day <= self.end)

    def describe(self) -> str:
        bits = [self.endpoint if self.endpoint != "any" else "every endpoint"]
        if self.above is not None:
            bits.append(f"prompts above {self.above:,} tokens")
        elif self.tier:
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
    #: whether the page shows every model's prompt-length tiers. OpenAI's shows
    #: them for its latest rows only, so a tier it does not show is unknown,
    #: not absent.
    tiers_complete: bool = True
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
#: The sentence stating the regional premium, in the two spellings the page has
#: used: "10% premium" (2026-10-13) and "10 percent premium" (2026-10-28). Those
#: two and nothing looser: a number in words, "per cent", "pct" or a sentence
#: about something else is a page whose shape changed, and a premium guessed
#: from it would be a price nobody stated.
_PREMIUM = re.compile(
    r"Regional and multi-region endpoints include an? (\d+(?:\.\d+)?)(?:\s*%|\s+percent\b) premium over global endpoints"
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
            above = None
            over = re.match(r"(?:over|above|more than)\s+([0-9][0-9,]*)\s+tokens", tier)
            if over:
                above = int(over.group(1).replace(",", ""))
            mid = anthropic_id(name)
            v.add(mid, name, Offer(prices, "global", tier, above=above))
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
                        "regional", o.tier, o.start, o.end, o.above,
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


#: What a rendered heading of OpenAI's text-token table calls each price. The
#: page renders the columns in the order its component chooses (Input, Cached
#: input, Cache writes, Output until 2026-10-13; Input, Output, Cached input,
#: 30m write, 12h write on 2026-10-28) and keeps the data rows behind them in one
#: fixed order, (input, cached input, cache write, output) for a row of four
#: prices and (input, cached input, output) for a row of three. The data rows
#: carry no headings of their own, so the headings alone cannot say what a data
#: row's third number is. The reader ties the two together by VALUE: every row
#: the table renders must show, under each heading, the number the data row
#: holds at the position this reader gives that heading. "12h write" is a price
#: the data rows do not carry and is not read.
_OPENAI_HEADING_COMPONENT = {
    "input": "input",
    "output": "output",
    "cached input": "cache_read",
    "cache writes": "cache_write",
    "30m write": "cache_write",
}
_OPENAI_LAYOUTS = {
    4: ("input", "cache_read", "cache_write", "output"),
    3: ("input", "cache_read", "output"),
}


class _OpenAIRow:
    __slots__ = ("raw", "name", "tier", "prices", "layout")

    def __init__(self, raw: str, name: str, tier: str, prices: dict, layout: tuple):
        self.raw, self.name, self.tier, self.prices, self.layout = raw, name, tier, prices, layout


class _OpenAITable:
    """One text-token price table marked tier `standard`, read on its own."""

    def __init__(self, idx: int, props: dict, doc: TableReader):
        self.idx, self.props = idx, props
        group = props.get("modelGroup")
        #: None for the flagship table; the group's name for a table of one
        #: group of models (the page's "Cyber models" is modelGroup "cyber").
        self.group = group if isinstance(group, str) and group else None
        self.heads: list = []
        self.ssr = None
        for t in doc.tables:
            if t.context.get("island") != idx:
                continue
            for row in t.rows():
                labels = [c.text.lower() for c in row]
                if labels and labels[0] == "model":
                    self.heads, self.ssr = labels, t
                    break
            if self.heads:
                break
        heading = self.ssr.context.get("h2") if self.ssr is not None else ""
        self.label = (
            f"{heading!r} table" if heading
            else (f"{self.group!r} group's table" if self.group else "table with no model group")
        )
        self.rows: list[_OpenAIRow] = []
        self.skipped: list[str] = []

    def columns(self) -> dict:
        """component -> rendered column, from the headings, or Missing."""
        cols: dict = {}
        for i, h in enumerate(self.heads):
            comp = _OPENAI_HEADING_COMPONENT.get(h)
            if comp and comp not in cols:
                cols[comp] = i
        if self.heads[:1] != ["model"] or any(c not in cols for c in ("input", "output", "cache_read", "cache_write")):
            raise E.Missing(
                f"OpenAI's {self.label} no longer heads its columns Input, Output, Cached input and "
                f"a cache-write price (it reads {' | '.join(self.heads) or 'nothing'}), and this check "
                f"takes each price from the column its heading names"
            )
        return cols

    def read_rows(self) -> None:
        rows = self.props.get("rows")
        if not isinstance(rows, list) or not rows:
            raise E.Missing(f"OpenAI's {self.label} carries no rows")
        for row in rows:
            if not isinstance(row, list) or not row or not isinstance(row[0], str):
                self.skipped.append(repr(row)[:60])
                continue
            raw = row[0]
            name = re.sub(r"\s*\(.*\)\s*$", "", raw).strip()
            tm = re.search(r"\((.*)\)", raw)
            tier = tm.group(1).strip() if tm else ""
            vals = row[1:]
            layout = _OPENAI_LAYOUTS.get(len(vals))
            if layout is None:
                self.skipped.append(raw)
                continue
            prices = {c: _number(x) for c, x in zip(layout, vals)}
            prices = {c: p for c, p in prices.items() if p is not None}
            if "input" not in prices or "output" not in prices:
                self.skipped.append(raw)
                continue
            self.rows.append(_OpenAIRow(raw, name, tier, prices, layout))

    def prove_columns(self, cols: dict) -> int:
        """Every rendered row against its data row, by value. Returns how many
        rows were tied; raises Missing on the first that disagrees."""
        tied = 0
        by_name = {r.name: r for r in self.rows}
        for cells in (r for r in self.ssr.rows()):
            texts = [c.text for c in cells]
            if not texts or texts[0].lower() == "model" or len(texts) <= max(cols.values()):
                continue
            data = by_name.get(re.sub(r"\s*\(.*\)\s*$", "", texts[0]).strip())
            if data is None:
                continue
            for comp, i in cols.items():
                shown = dollars(texts[i])
                stated = data.prices.get(comp) if comp in data.layout else None
                if (shown is None) != (stated is None) or (shown is not None and not close(shown, stated)):
                    raise E.Missing(
                        f"OpenAI's {self.label} renders {data.name}'s {comp.replace('_', ' ')} as "
                        f"{shown if shown is not None else 'no price'} under {self.heads[i]!r}, and the data "
                        f"behind the table holds {stated if stated is not None else 'no price'} at the position "
                        f"this check gives that column, so the columns are not in the order the check reads them"
                    )
            tied += 1
        return tied


def parse_openai(page: str, url: str = OPENAI_URL) -> Vendor:
    """Every text-token table the page marks tier `standard`, read together.

    On 2026-10-28 the page carried two: the flagship table and a group of
    models of its own ("Cyber models"), with gpt-5.6-sol in both. A reader that
    took one would have priced half the page, and one that took either by
    position would have been right by accident. So all are read, a model both
    price identically is one row, and a model they price differently is read
    from NEITHER and reported: a page that contradicts itself has no price.
    Which rows are the latest models is the flagship table's to say (the one
    with no model group); a group's own latest rows are not counted.
    """
    v = Vendor("openai", "OpenAI", url)
    doc = read_tables(page)
    tables: list[_OpenAITable] = []
    for idx, island in enumerate(doc.islands):
        if island.get("component-export") != "TextTokenPricingTables":
            continue
        try:
            props = _astro(json.loads(island.get("props", "")))
        except ValueError:
            continue
        if isinstance(props, dict) and props.get("tier") == "standard":
            tables.append(_OpenAITable(idx, props, doc))
    if not tables:
        raise E.Missing(
            "OpenAI's pricing page carries no text-token price table marked tier 'standard' "
            "(component TextTokenPricingTables), which is the table this check reads. The page changed shape"
        )
    for tb in tables:
        cols = tb.columns()
        tb.read_rows()
        if tb.ssr is None or tb.prove_columns(cols) == 0:
            raise E.Missing(
                f"OpenAI's {tb.label} renders no row that can be tied to its data, so the order of the "
                f"data columns is unproven and this check will not read prices by it"
            )

    merged: dict = {}  # name -> (label, [(tier, prices)])
    clashes: dict = {}  # name -> [(label, [(tier, prices)])]
    for tb in tables:
        per: dict = {}
        for r in tb.rows:
            per.setdefault(r.name, []).append((r.tier, r.prices))
        for name, offers in per.items():
            if name in clashes:
                clashes[name].append((tb.label, offers))
            elif name not in merged:
                merged[name] = (tb.label, offers)
            elif merged[name][1] != offers:
                clashes[name] = [merged.pop(name), (tb.label, offers)]
    for name, readings in sorted(clashes.items()):
        said = "; ".join(
            f"the {label} says " + " / ".join(
                (f"{tier}: " if tier else "") + ", ".join(f"{c} {fmt(p[c])}" for c in COMPONENTS if c in p)
                for tier, p in offers
            )
            for label, offers in readings
        )
        v.problems.append(
            f"OpenAI's standard text-token tables price {name} differently ({said}), so this check reads "
            f"it from neither and a row priced from it is not judged"
        )
    order: dict = {}
    for tb in tables:
        for r in tb.rows:
            if r.name in merged and merged[r.name][0] == tb.label and r.name not in order:
                order[r.name] = None
    for name in order:
        for tier, prices in merged[name][1]:
            v.add(name, name, Offer(prices, "global", tier))
    if not v.models and not clashes:
        raise E.Missing("no row of OpenAI's standard text-token tables parsed")
    skipped = [x for tb in tables for x in tb.skipped]
    if skipped:
        v.notes.append(f"{len(skipped)} OpenAI row(s) in a shape this check does not read: {', '.join(skipped[:6])}")
    if len(tables) > 1:
        v.notes.append(
            f"OpenAI carries {len(tables)} standard text-token tables ({', '.join(tb.label for tb in tables)}); "
            f"all are read, and a model in more than one at one price is one row"
        )

    flagship = [tb for tb in tables if tb.group is None]
    if len(flagship) == 1:
        n = flagship[0].props.get("collapsedLatestRowCount")
        names = [r.name for r in flagship[0].rows if r.name in merged]
        names = list(dict.fromkeys(names))
        if isinstance(n, int) and not isinstance(n, bool) and 0 < n <= len(names):
            v.current = names[:n]
        else:
            v.problems.append(
                "the standard text-token table no longer says how many of its rows are the "
                "latest models (collapsedLatestRowCount), so which models are current could not be read"
            )
    else:
        v.problems.append(
            f"the page carries {len(flagship)} standard text-token tables with no model group, so which "
            f"table's latest rows are the current models could not be read"
        )
    _openai_long(v, doc, tables)
    return v


def _walk(value):
    yield value
    if isinstance(value, dict):
        for x in value.values():
            yield from _walk(x)
    elif isinstance(value, list):
        for x in value:
            yield from _walk(x)


def _openai_long(v: Vendor, doc: TableReader, tables: list) -> None:
    """OpenAI's long-context prices, where the page states them.

    The page states a long price in three shapes, depending on the day. Until
    2026-10-13 a rendered "Long context" column group beside the short price for
    its latest rows, and a grouped short/long table. From 2026-10-28 a
    `longContextRows` prop on a table, one entry per model, "-" where the page
    states none. For the rest it computes the long price in script, which this
    reader does not run. So OpenAI's tiers are marked incomplete: a tier the
    page does not show is unknown, not absent. The threshold is the one the page
    states (">272K input tokens"), read from a tooltip or from a row name's
    "(<272K context length)", and there must be exactly one.
    """
    v.tiers_complete = False
    thresholds = set()
    props_all = []
    for island in doc.islands:
        try:
            props_all.append(_astro(json.loads(island.get("props", ""))))
        except ValueError:
            props_all.append(None)
    for props in props_all:
        for node in _walk(props):
            if isinstance(node, dict) and str(node.get("label", "")).strip().lower() == "long context":
                m = re.search(r">\s*([0-9]+)\s*K", str(node.get("tooltip", "")))
                if m:
                    thresholds.add(int(m.group(1)) * 1000)
    for offers in v.models.values():
        for o in offers:
            m = re.search(r"<\s*([0-9]+)\s*K", o.tier)
            if m:
                thresholds.add(int(m.group(1)) * 1000)
    if len(thresholds) != 1:
        v.notes.append(
            f"the page states {len(thresholds)} long-context thresholds ({sorted(thresholds)}), so no "
            f"OpenAI long-context price was read"
        )
        return
    above = thresholds.pop()
    found = 0
    clashed: set = set()

    def put_long(name: str, prices: dict) -> bool:
        """One long price for one model. The same price from two places is one
        price; two prices for one model are read as neither, and reported."""
        nonlocal found
        if name in clashed:
            return False
        have = [o for o in v.models.get(name, []) if o.above == above]
        if have and have[0].prices == prices:
            return True
        if have:
            clashed.add(name)
            v.models[name] = [o for o in v.models[name] if o.above != above]
            v.problems.append(
                f"OpenAI's page states two different long-context prices for {name} "
                f"({', '.join(f'{c} {fmt(have[0].prices[c])}' for c in COMPONENTS if c in have[0].prices)} and "
                f"{', '.join(f'{c} {fmt(prices[c])}' for c in COMPONENTS if c in prices)}), so this check reads "
                f"neither"
            )
            found -= 1
            return False
        v.models.setdefault(name, []).append(Offer(prices, "global", f"over {above // 1000}K context", above=above))
        v.names.setdefault(name, name)
        found += 1
        return True

    long_heads = ["input", "cached input", "cache writes", "output"]
    for tb in tables:
        heads, ssr = tb.heads, tb.ssr
        if ssr is not None and heads[5:9] == long_heads and len(heads) == 9:
            for row in ssr.rows():
                texts = [c.text for c in row]
                if len(texts) != 9 or texts[0].lower() == "model":
                    continue
                name = re.sub(r"\s*\(.*\)\s*$", "", texts[0]).strip()
                prices = {c: dollars(x) for c, x in zip(("input", "cache_read", "cache_write", "output"), texts[5:9])}
                prices = {c: x for c, x in prices.items() if x is not None}
                if name in v.models and "input" in prices and "output" in prices:
                    put_long(name, prices)
        rows = tb.props.get("longContextRows")
        if isinstance(rows, dict):
            fields = {"input": "input", "cachedInput": "cache_read", "cacheWrite": "cache_write", "output": "output"}
            for name, entry in rows.items():
                if not isinstance(name, str) or not isinstance(entry, dict) or name not in v.models:
                    continue
                prices = {c: _number(entry.get(f)) for f, c in fields.items()}
                prices = {c: x for c, x in prices.items() if x is not None}
                if "input" in prices and "output" in prices:
                    put_long(name, prices)
    for idx, island in enumerate(doc.islands):
        props = props_all[idx]
        if island.get("component-export") != "GroupedPricingTable" or not isinstance(props, dict):
            continue
        headings = [str(h).strip().lower() for h in props.get("headings") or [] if isinstance(h, str)]
        want = [f"{s} context {c}" for s in ("short", "long") for c in long_heads]
        if headings[1:9] != want:
            continue
        for group in props.get("groups") or []:
            if not isinstance(group, dict) or not isinstance(group.get("model"), str):
                continue
            for row in group.get("rows") or []:
                if not isinstance(row, list) or len(row) != 8:
                    continue
                comps = ("input", "cache_read", "cache_write", "output")
                short = {c: _number(x) for c, x in zip(comps, row[:4])}
                long = {c: _number(x) for c, x in zip(comps, row[4:])}
                short = {c: x for c, x in short.items() if x is not None}
                long = {c: x for c, x in long.items() if x is not None}
                name = group["model"]
                if name not in v.models and name not in clashed and "input" in short and "output" in short:
                    v.add(name, name, Offer(short, "global"))
                if "input" in long and "output" in long:
                    put_long(name, long)
    v.notes.append(f"long-context prices (prompts above {above:,} tokens) stated for {found} model(s); for the rest the page computes them in script and they are not judged")


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
            over = re.search(r">\s*([0-9]+)\s*k\b", h)
            upto = re.search(r"<=\s*([0-9]+)\s*k\b", h)
            if over:
                tier = (f"over {over.group(1)}K input tokens", int(over.group(1)) * 1000)
            elif upto:
                tier = (f"up to {upto.group(1)}K input tokens", None)
            else:
                tier = ("", None)
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
        for (name, start, end, endpoint, (tier, above)), prices in rows_by.items():
            if "input" not in prices or "output" not in prices:
                continue
            if above is not None:
                # A "> 200K" column that repeats the base price is not a tier.
                base = [p for (n2, s2, e2, ep2, (_, a2)), p in rows_by.items()
                        if (n2, s2, e2, ep2) == (name, start, end, endpoint) and a2 is None]
                if base and base[0] == prices:
                    continue
            v.add(gemini_id(name), name, Offer(prices, endpoint, tier, start, end, above))
    if not v.models:
        raise E.Missing(
            f"no Standard token price table under Vertex AI's 'Google models' heading parsed "
            f"into a Gemini model with an input and an output price ({used} candidate table(s) read)"
        )
    v.notes.append("the page marks no set of current models, so a Gemini model no table prices is listed, not judged")
    return v


# ------------------------------------------------------------- OpenRouter

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
        above = n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else None
        offers.append(Offer(p, "global", f"prompts of {n} tokens and more" if n else "override", above=above))
    return offers


def parse_openrouter_providers(text: str) -> list[dict] | None:
    """Every provider OpenRouter routes one model to, with its base price.

    The price of a call billed through OpenRouter is the price of the provider
    that served it, and OpenRouter's model list shows one provider's price as
    "the" price and switches which one as providers come and go: on 2026-10-13
    its list said 0.32 / 0.89 for deepseek/deepseek-chat (DeepInfra's) while
    StreamLake served the same model at 0.2574 / 1.0287. So a row is read
    against every provider this answer lists, never against the aggregate.

    Returns [{name, tag, status, prices}] (prices: the base rate, no prompt-
    length override), [] when the model has no priced endpoint, and None when
    OpenRouter answers that it does not know the model (its 404 body).
    """
    try:
        data = json.loads(text)
    except ValueError as e:
        raise E.Missing(f"OpenRouter's endpoint list is not JSON ({e})") from None
    if isinstance(data, dict) and isinstance(data.get("error"), dict) and data["error"].get("code") == 404:
        return None
    inner = data.get("data") if isinstance(data, dict) else None
    eps = inner.get("endpoints") if isinstance(inner, dict) else None
    if not isinstance(eps, list):
        raise E.Missing("OpenRouter's endpoint list has no 'data.endpoints' array")
    out = []
    for ep in eps:
        if not isinstance(ep, dict):
            continue
        base = [o for o in _openrouter_offers(ep.get("pricing") or {}) if o.above is None]
        if not base:
            continue
        name = ep.get("provider_name") if isinstance(ep.get("provider_name"), str) else "?"
        tag = ep.get("tag") if isinstance(ep.get("tag"), str) else "?"
        out.append({"name": name, "tag": tag, "status": ep.get("status"), "prices": base[0].prices})
    return out


def exact(ours: float, theirs: float) -> bool:
    """Equal to the nanodollar per million tokens: no tolerance, only float noise."""
    return abs(ours - theirs) <= 1e-9


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


def candidates(offers: list[Offer], endpoint: str, day: datetime.date, tiers: str = "all") -> list[Offer]:
    """The offers a row on `endpoint` may equal on `day`. `tiers` is "all" (a
    flat row in a table that cannot express a tier may carry either), "base"
    or "long"."""
    allowed = {"global": ("global", "any"), "regional": ("regional", "any")}.get(endpoint, ("global", "regional", "any"))
    keep = {"all": lambda o: True, "base": lambda o: o.above is None, "long": lambda o: o.above is not None}[tiers]
    return [o for o in offers if o.in_effect(day) and o.endpoint in allowed and keep(o)]


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
