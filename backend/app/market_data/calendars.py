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


def market_status(market: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {"market": market, "open": is_open(market, now), "checked_at": now.isoformat()}
