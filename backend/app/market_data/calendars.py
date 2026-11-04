"""Trading calendars via exchange_calendars (handles holidays, early closes, DST)."""
from datetime import datetime, timezone
from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd

from .symbols import MARKETS


@lru_cache
def _cal(market: str):
    return xcals.get_calendar(MARKETS[market]["mic"])


def is_open(market: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return bool(_cal(market).is_open_on_minute(pd.Timestamp(now).tz_convert("UTC").floor("min"), ignore_breaks=True))


def session_fraction(market: str, ts: datetime) -> float | None:
    """Share of today's session elapsed at ts (1.0 after close); None if not a session day."""
    from zoneinfo import ZoneInfo
    cal = _cal(market)
    d = pd.Timestamp(ts.astimezone(ZoneInfo(MARKETS[market]["tz"])).date())
    if not cal.is_session(d):
        return None
    o, c = cal.session_open(d), cal.session_close(d)
    return min(1.0, max(0.0, (pd.Timestamp(ts).tz_convert("UTC") - o) / (c - o)))


def market_status(market: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {"market": market, "open": is_open(market, now), "checked_at": now.isoformat()}
