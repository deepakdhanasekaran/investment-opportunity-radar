"""Ticker normalization to Yahoo symbols. Swedish tickers: share classes use '-' ('VOLV B' -> 'VOLV-B.ST')."""
import re


def to_yahoo(symbol: str, market: str) -> str:
    s = symbol.strip().upper()
    if not s:
        raise ValueError("empty symbol")
    if market == "SE":
        if s.endswith(".ST"):
            s = s[:-3]
        s = re.sub(r"[ _.]", "-", s)  # 'VOLV B', 'VOLV.B' -> 'VOLV-B'
        if not re.fullmatch(r"[A-Z0-9]+(-[A-Z]{1,2})?", s):
            raise ValueError(f"invalid Swedish ticker: {symbol!r}")
        return f"{s}.ST"
    if market == "US":
        s = s.replace(".", "-")  # BRK.B -> BRK-B
        if not re.fullmatch(r"[A-Z0-9]{1,6}(-[A-Z])?", s):
            raise ValueError(f"invalid US ticker: {symbol!r}")
        return s
    raise ValueError(f"unknown market {market!r}")


MARKETS = {
    "SE": {"exchange": "Nasdaq Stockholm", "mic": "XSTO", "currency": "SEK", "tz": "Europe/Stockholm", "index": "^OMX"},
    "US": {"exchange": "NYSE/Nasdaq", "mic": "XNYS", "currency": "USD", "tz": "America/New_York", "index": "^GSPC"},
}
