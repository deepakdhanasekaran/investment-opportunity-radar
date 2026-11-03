import csv
from dataclasses import dataclass
from importlib.resources import files

from app.market_data.symbols import to_yahoo


@dataclass(frozen=True)
class Member:
    symbol: str  # yahoo symbol
    name: str
    sector: str
    market: str


_FILES = {"sp500": ("US", "us_sp500.csv"), "nasdaq100": ("US", "us_nasdaq100.csv"),
          "omxs30": ("SE", "se_omxs30.csv"), "largecap": ("SE", "se_largecap.csv")}


def load(name: str) -> list[Member]:
    market, fn = _FILES[name]
    p = files("app.universe").joinpath(fn)
    if not p.is_file():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return [Member(to_yahoo(r["symbol"], market), r["name"], r["sector"], market) for r in csv.DictReader(f)]


def universe(market: str, names: list[str], watchlist: list[tuple[str, str]] = ()) -> list[Member]:
    """Members for a market, de-duplicated; watchlist = [(yahoo_symbol, market)] always included."""
    seen: dict[str, Member] = {}
    for n in names:
        if n in _FILES and _FILES[n][0] == market:
            for m in load(n):
                seen.setdefault(m.symbol, m)
    for sym, mk in watchlist:
        if mk == market:
            seen.setdefault(sym, Member(sym, sym, "", mk))
    return list(seen.values())
