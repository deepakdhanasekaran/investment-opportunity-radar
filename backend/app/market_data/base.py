"""Provider-neutral market data types and interface. Every quote carries source + timestamps."""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol


class ProviderError(Exception):
    pass


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    currency: str
    source_ts: datetime  # when the exchange/provider says the price is from (tz-aware UTC)
    retrieved_ts: datetime  # when we fetched it (tz-aware UTC)
    source: str
    volume: float | None = None

    def age_minutes(self, now: datetime | None = None) -> float:
        now = now or self.retrieved_ts
        return (now - self.source_ts).total_seconds() / 60


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float  # split/dividend-adjusted
    volume: float


@dataclass
class Fundamentals:
    symbol: str
    source: str
    retrieved_ts: datetime
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    metrics: dict[str, float | None] = field(default_factory=dict)
    raw_ts: datetime | None = None  # period end of the underlying statements, if known
    annual_eps: list[tuple[str, float]] = field(default_factory=list)  # (fiscal period end ISO date, diluted EPS)
    next_earnings: date | None = None  # next scheduled report per Yahoo calendar; None = unknown (not "none scheduled")


class MarketDataProvider(Protocol):
    name: str

    def history(self, symbol: str, days: int) -> list[Bar]: ...
    def quote(self, symbol: str) -> Quote: ...
    def fundamentals(self, symbol: str) -> Fundamentals: ...
    def corporate_actions(self, symbol: str) -> list[dict]: ...
