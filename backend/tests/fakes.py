from datetime import datetime, timedelta, timezone

from app.market_data.base import Bar, Fundamentals, ProviderError, Quote

NOW = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)  # Tuesday, both... US open, SE open


def make_bars(end_close: float, n: int = 260, drift: float = 0.0005, last_day=NOW) -> list[Bar]:
    """n daily bars ending the day BEFORE last_day, rising with `drift`, last close == end_close."""
    closes = [end_close / (1 + drift) ** (n - 1 - i) for i in range(n)]
    d0 = last_day.replace(hour=0, minute=0) - timedelta(days=n)
    return [Bar(d0 + timedelta(days=i), c, c, c, c, 1_000_000) for i, c in enumerate(closes)]


GOOD = {"revenue_growth": 0.12, "earnings_growth": 0.15, "profit_margin": 0.14, "operating_margin": 0.18, "debt_to_equity": 0.4,
        "free_cash_flow": 1e8, "revenue": 1e9, "roic": 0.14, "earnings_stability": 1.0, "current_ratio": 1.7, "total_cash": 5e8,
        "total_debt": 4e8, "pe": 14.0, "forward_pe": 12.0, "avg_volume": 5e6, "roe": 0.2, "pb": 2.0, "ev_ebitda": 9.0}


class FakeProvider:
    name = "fake"

    def __init__(self, prices: dict[str, tuple[float, float]], metrics: dict | None = None, fail: bool = False, age_min: float = 1):
        self.prices, self.fail, self.age = prices, fail, age_min  # symbol -> (prev_close, last_price)
        self.metrics = metrics if metrics is not None else GOOD

    def histories(self, symbols, days=400):
        if self.fail:
            raise ProviderError("boom")
        return {s: make_bars(self.prices[s][0]) for s in symbols if s in self.prices}

    def quotes(self, symbols, currency):
        if self.fail:
            raise ProviderError("boom")
        ts = NOW - timedelta(minutes=self.age)
        return {s: Quote(s, self.prices[s][1], currency, ts, NOW, "fake", 3_000_000) for s in symbols if s in self.prices}

    def history(self, symbol, days=400):
        return make_bars(self.prices[symbol][0])

    def quote(self, symbol):
        return self.quotes([symbol], "SEK")[symbol]

    def fundamentals(self, symbol):
        if self.metrics is None:
            raise ProviderError("no fundamentals")
        return Fundamentals(symbol, "fake", NOW, sector="Industrials", currency="SEK", metrics=dict(self.metrics))

    def corporate_actions(self, symbol):
        return []
