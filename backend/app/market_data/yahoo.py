"""Yahoo Finance via yfinance. Unofficial; no SLA. Quote timestamps come from the data itself,
never fabricated: if Yahoo gives no timestamp we raise rather than stamping 'now'."""
import logging
import time
from datetime import datetime, timezone

import yfinance as yf

from .base import Bar, Fundamentals, ProviderError, Quote

log = logging.getLogger(__name__)

# yfinance info key -> our metric name
_INFO_MAP = {
    "revenueGrowth": "revenue_growth", "earningsGrowth": "earnings_growth", "profitMargins": "profit_margin",
    "operatingMargins": "operating_margin", "returnOnEquity": "roe", "returnOnAssets": "roa",
    "debtToEquity": "debt_to_equity", "freeCashflow": "free_cash_flow", "operatingCashflow": "operating_cash_flow",
    "totalRevenue": "revenue", "marketCap": "market_cap", "trailingPE": "pe", "forwardPE": "forward_pe",
    "priceToBook": "pb", "enterpriseToEbitda": "ev_ebitda", "currentRatio": "current_ratio",
    "totalDebt": "total_debt", "totalCash": "total_cash", "dividendYield": "dividend_yield",
    "averageVolume": "avg_volume", "beta": "beta",
}


def _retry(fn, tries: int = 3, base: float = 1.0):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # yfinance raises many types; wrap uniformly
            if i == tries - 1:
                raise ProviderError(f"yahoo: {e}") from e
            time.sleep(base * 2**i)


class YahooProvider:
    name = "yahoo"

    def history(self, symbol: str, days: int = 400) -> list[Bar]:
        df = _retry(lambda: yf.Ticker(symbol).history(period=f"{max(days, 5)}d", interval="1d", auto_adjust=True))
        if df is None or df.empty:
            raise ProviderError(f"yahoo: no history for {symbol}")
        df = df.dropna(subset=["Close"])
        return [Bar(ts=i.to_pydatetime().astimezone(timezone.utc), open=float(r.Open), high=float(r.High),
                    low=float(r.Low), close=float(r.Close), volume=float(r.Volume)) for i, r in df.iterrows()]

    def quote(self, symbol: str) -> Quote:
        t = yf.Ticker(symbol)
        df = _retry(lambda: t.history(period="1d", interval="1m", prepost=False))
        if df is None or df.empty:
            raise ProviderError(f"yahoo: no intraday data for {symbol}")
        last = df.iloc[-1]
        ts = df.index[-1].to_pydatetime().astimezone(timezone.utc)
        cur = (getattr(t, "fast_info", {}) or {}).get("currency") or ""
        return Quote(symbol=symbol, price=float(last.Close), currency=cur, source_ts=ts,
                     retrieved_ts=datetime.now(timezone.utc), source=self.name, volume=float(df.Volume.sum()))

    def quotes(self, symbols: list[str], currency: str) -> dict[str, Quote]:
        """Batch last-minute quotes. Symbols with no data are simply absent (caller treats as failed)."""
        out: dict[str, Quote] = {}
        if not symbols:
            return out
        df = _retry(lambda: yf.download(symbols, period="1d", interval="1m", group_by="ticker", progress=False,
                                        threads=True, auto_adjust=True, multi_level_index=True))
        now = datetime.now(timezone.utc)
        for sym in symbols:
            try:
                sub = df[sym].dropna(subset=["Close"])
            except KeyError:
                continue
            if sub.empty:
                continue
            out[sym] = Quote(sym, float(sub.Close.iloc[-1]), currency, sub.index[-1].to_pydatetime().astimezone(timezone.utc),
                             now, self.name, float(sub.Volume.sum()))
        return out

    def histories(self, symbols: list[str], days: int = 400) -> dict[str, list[Bar]]:
        out: dict[str, list[Bar]] = {}
        if not symbols:
            return out
        df = _retry(lambda: yf.download(symbols, period=f"{days}d", interval="1d", group_by="ticker", progress=False,
                                        threads=True, auto_adjust=True, multi_level_index=True))
        for sym in symbols:
            try:
                sub = df[sym].dropna(subset=["Close"])
            except KeyError:
                continue
            if not sub.empty:
                out[sym] = [Bar(i.to_pydatetime().astimezone(timezone.utc), float(r.Open), float(r.High), float(r.Low),
                                float(r.Close), float(r.Volume)) for i, r in sub.iterrows()]
        return out

    def fundamentals(self, symbol: str) -> Fundamentals:
        t = yf.Ticker(symbol)
        info = _retry(lambda: t.info) or {}
        m: dict[str, float | None] = {}
        for k, name in _INFO_MAP.items():
            v = info.get(k)
            m[name] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        # yfinance reports debtToEquity in percent; normalise to ratio
        if m.get("debt_to_equity") is not None:
            m["debt_to_equity"] = m["debt_to_equity"] / 100
        m.update(self._statement_metrics(t))
        return Fundamentals(annual_eps=self._annual_eps(t), symbol=symbol, source=self.name, retrieved_ts=datetime.now(timezone.utc),
                            sector=info.get("sector"), industry=info.get("industry"),
                            currency=info.get("financialCurrency") or info.get("currency"), metrics=m)

    @staticmethod
    def _annual_eps(t: yf.Ticker) -> list[tuple[str, float]]:
        try:
            inc = t.income_stmt
            if inc is None or inc.empty or "Diluted EPS" not in inc.index:
                return []
            return [(c.date().isoformat(), float(v)) for c, v in inc.loc["Diluted EPS"].dropna().items()]
        except Exception:
            return []

    @staticmethod
    def _statement_metrics(t: yf.Ticker) -> dict[str, float | None]:
        """Multi-year stability: earnings volatility + ROIC from annual statements; None if absent."""
        out: dict[str, float | None] = {"roic": None, "earnings_stability": None, "net_income_years": None}
        try:
            inc, bs = t.income_stmt, t.balance_sheet
            if inc is not None and not inc.empty and "Net Income" in inc.index:
                ni = inc.loc["Net Income"].dropna()
                out["net_income_years"] = float(len(ni))
                if len(ni) >= 3:
                    out["earnings_stability"] = float((ni > 0).mean())  # share of profitable years
            if inc is not None and bs is not None and not inc.empty and not bs.empty:
                ebit = inc.loc["EBIT"].dropna().iloc[0] if "EBIT" in inc.index else None
                ic = bs.loc["Invested Capital"].dropna().iloc[0] if "Invested Capital" in bs.index else None
                if ebit is not None and ic:
                    out["roic"] = float(ebit * 0.79 / ic)  # ponytail: flat ~21% tax assumption
        except Exception as e:
            log.debug("statement metrics failed for %s: %s", t.ticker, e)
        return out

    def corporate_actions(self, symbol: str) -> list[dict]:
        a = _retry(lambda: yf.Ticker(symbol).actions)
        if a is None or a.empty:
            return []
        a = a.tail(20)
        return [{"date": i.date().isoformat(), "dividend": float(r.get("Dividends", 0) or 0),
                 "split": float(r.get("Stock Splits", 0) or 0)} for i, r in a.iterrows()]
