"""Price features from daily bars + a live quote. Pure functions: no I/O."""
import statistics
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.market_data.base import Bar, Quote


@dataclass
class Features:
    price: float
    prev_close: float
    daily_change_pct: float
    five_day_change_pct: float | None
    volume_ratio: float | None
    sma50: float | None
    sma200: float | None
    high_20d: float | None
    drawdown_20d_pct: float | None
    volatility_ann_pct: float | None
    n_bars: int


def session_date(ts: datetime, tz: str) -> date:
    return ts.astimezone(ZoneInfo(tz)).date()


def _sma(xs: list[float], n: int) -> float | None:
    return sum(xs[-n:]) / n if len(xs) >= n else None


MIN_SESSION_FRACTION = 0.15  # before this, partial-day volume is too noisy to compare with a full-day average


def compute(bars: list[Bar], quote: Quote, tz: str, session_frac: float | None = None) -> Features | None:
    """Bars may include today's partial bar; it is dropped so prev_close is truly the previous session.
    session_frac: share of the session elapsed; volume is pro-rated by it (None = full-day volume, e.g. backtests)."""
    today = session_date(quote.source_ts, tz)
    prior = [b for b in bars if session_date(b.ts, tz) < today]
    if len(prior) < 6:
        return None
    closes = [b.close for b in prior]
    prev = closes[-1]
    price = quote.price
    vols = [b.volume for b in prior[-20:] if b.volume]
    vol_ratio = (quote.volume / (sum(vols) / len(vols))) if quote.volume and vols else None
    if vol_ratio is not None and session_frac is not None:
        # ponytail: linear pro-rating ignores the intraday U-shape of volume; fine for a coarse screen
        vol_ratio = vol_ratio / session_frac if session_frac >= MIN_SESSION_FRACTION else None
    rets = [closes[i] / closes[i - 1] - 1 for i in range(max(1, len(closes) - 20), len(closes))]
    vol = statistics.stdev(rets) * (252**0.5) * 100 if len(rets) >= 10 else None
    h20 = max(max(closes[-20:]), price)
    return Features(
        price=price, prev_close=prev, daily_change_pct=(price / prev - 1) * 100,
        five_day_change_pct=(price / closes[-5] - 1) * 100 if len(closes) >= 5 else None,
        volume_ratio=vol_ratio, sma50=_sma(closes, 50), sma200=_sma(closes, 200),
        high_20d=h20, drawdown_20d_pct=(price / h20 - 1) * 100, volatility_ann_pct=vol, n_bars=len(closes),
    )
