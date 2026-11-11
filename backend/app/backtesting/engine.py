"""Price-only historical backtest of candidate strategies (A, B, D).

Methodology (also returned in every result as `warnings`):
* Signal uses only data up to the close of day t; entry is the OPEN of day t+1 (no look-ahead).
* Exit is the close h trading days after entry. Transaction cost is charged per side (default 10 bps).
* Quality/valuation gates are NOT applied: Yahoo has no point-in-time fundamentals, so using them would leak the future.
* The universe is today's constituents: survivorship bias inflates results. Delisted names are absent.
* Thresholds are the unmodified defaults (nothing was fitted); results are split chronologically into in-sample and
  out-of-sample (last 40%) so a degradation is visible. An in-sample number is not evidence of profitability.
"""
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from app.backtesting.exits import RULES, simulate
from app.core.config import ScanRules
from app.market_data.base import Bar, Quote
from app.scanner.features import compute
from app.strategies.detect import run_all

HOLDINGS = (5, 20, 60, 120)
BASE_WARNINGS = [
    "Survivorship bias: universe is current index members; delisted companies are not included.",
    "No point-in-time fundamentals: quality, valuation and news gates are not applied; only price-based strategies A, B, D are tested.",
    "Daily bars: intraday triggers are approximated by the daily close. Slippage beyond the flat cost is not modelled.",
    "Past performance of a rule set does not predict future returns; do not treat in-sample results as evidence of profitability.",
]


@dataclass
class Trade:
    symbol: str
    strategy: str
    entry_date: datetime
    exit_date: datetime
    ret: float  # net of costs, local currency unless fx supplied
    bench: float | None
    holding: int
    rule: str = "fixed"  # 'fixed' = hold N days; else an exit rule from exits.RULES (holding = days actually held)
    reason: str = ""  # signal | cap (exit rules only)


def _index_at(bars: list[Bar], ts: datetime) -> int | None:
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].ts < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(bars) and bars[lo].ts == ts else None


def generate_trades(universe: dict[str, list[Bar]], index_bars: list[Bar], tz: str, rules: ScanRules, holdings=HOLDINGS,
                    cost_bps: float = 10.0, cooldown_days: int = 20, fx: list[Bar] | None = None) -> list[Trade]:
    trades: list[Trade] = []
    for sym, bars in universe.items():
        last_sig: dict[str, int] = {}
        for i in range(210, len(bars) - 1):
            window = bars[max(0, i - 260): i + 1]
            q = Quote(sym, bars[i].close, "", bars[i].ts, bars[i].ts, "backtest", bars[i].volume)
            f = compute(window, q, tz)
            if f is None:
                continue
            ii = _index_at(index_bars, bars[i].ts)
            idx = None
            if ii is not None and ii >= 210:
                iw = index_bars[max(0, ii - 260): ii + 1]
                idx = compute(iw, Quote("idx", iw[-1].close, "", iw[-1].ts, iw[-1].ts, "backtest", iw[-1].volume), tz)
            for h in run_all(f, idx, rules):
                if i - last_sig.get(h.strategy, -10**9) < cooldown_days:
                    continue
                last_sig[h.strategy] = i
                e = i + 1
                entry = bars[e].open
                for hold in holdings:
                    x = e + hold
                    if x >= len(bars):
                        continue
                    r = bars[x].close / entry - 1
                    if fx:
                        a, b = _index_at(fx, bars[e].ts), _index_at(fx, bars[x].ts)
                        if a is not None and b is not None:
                            r = (1 + r) * (fx[b].close / fx[a].open if fx[a].open else 1) - 1
                    net = r - 2 * cost_bps / 1e4
                    bench = None
                    ie, ix = _index_at(index_bars, bars[e].ts), _index_at(index_bars, bars[x].ts)
                    if ie is not None and ix is not None:
                        bench = index_bars[ix].close / index_bars[ie].open - 1
                    trades.append(Trade(sym, h.strategy, bars[e].ts, bars[x].ts, net, bench, hold))
                for rule in RULES:
                    x, why = simulate(bars, e + 1, entry, rule)
                    if x is None:
                        continue
                    r = bars[x].close / entry - 1
                    if fx:
                        a, b = _index_at(fx, bars[e].ts), _index_at(fx, bars[x].ts)
                        if a is not None and b is not None:
                            r = (1 + r) * (fx[b].close / fx[a].open if fx[a].open else 1) - 1
                    ie, ix = _index_at(index_bars, bars[e].ts), _index_at(index_bars, bars[x].ts)
                    bench = index_bars[ix].close / index_bars[ie].open - 1 if ie is not None and ix is not None else None
                    trades.append(Trade(sym, h.strategy, bars[e].ts, bars[x].ts, r - 2 * cost_bps / 1e4, bench, x - e, rule, why))
    return trades


def _max_drawdown(trades: list[Trade], slots: int = 10) -> float:
    eq, peak, dd = 1.0, 1.0, 0.0
    for t in sorted(trades, key=lambda t: t.exit_date):
        eq *= 1 + t.ret / slots  # each trade sized at 1/slots of equity
        peak = max(peak, eq)
        dd = min(dd, eq / peak - 1)
    return dd


def summarize(trades: list[Trade], holding: int | None, slots: int = 10, rule: str = "fixed") -> dict:
    ts = [t for t in trades if t.rule == rule and (holding is None or t.holding == holding)]
    if holding is None and ts:
        holding = round(statistics.fmean(t.holding for t in ts))  # exit rules: average days held
    if not ts:
        return {"holding_days": holding, "signals": 0}
    rets = [t.ret for t in ts]
    ex = [t.ret - t.bench for t in ts if t.bench is not None]
    sd = statistics.stdev(rets) if len(rets) > 1 else None
    top = Counter(t.symbol for t in ts).most_common(1)[0]
    return {"holding_days": holding, "signals": len(ts), "cap_exit_share": sum(t.reason == "cap" for t in ts) / len(ts) if rule != "fixed" else None, "win_rate": sum(r > 0 for r in rets) / len(rets),
            "mean_return": statistics.fmean(rets), "median_return": statistics.median(rets), "volatility": sd,
            "sharpe_per_trade_annualised": (statistics.fmean(rets) / sd * (252 / holding) ** 0.5) if sd else None,
            "mean_excess_vs_benchmark": statistics.fmean(ex) if ex else None,
            "beat_benchmark_rate": sum(e > 0 for e in ex) / len(ex) if ex else None,
            "max_drawdown_sequenced": _max_drawdown(ts, slots),
            "concentration": {"top_symbol": top[0], "top_symbol_share": top[1] / len(ts), "distinct_symbols": len({t.symbol for t in ts})}}


def report(trades: list[Trade], oos_fraction: float = 0.4, holdings=HOLDINGS) -> dict:
    if not trades:
        return {"signals": 0, "warnings": BASE_WARNINGS + ["No signals generated."]}
    dates = sorted({t.entry_date for t in trades})
    cut = dates[int(len(dates) * (1 - oos_fraction))]
    ins, oos = [t for t in trades if t.entry_date < cut], [t for t in trades if t.entry_date >= cut]
    by_strat = {s: [summarize([t for t in trades if t.strategy == s], h) for h in holdings] for s in {t.strategy for t in trades}}
    return {"split_date": cut.isoformat(), "in_sample": [summarize(ins, h) for h in holdings],
            "out_of_sample": [summarize(oos, h) for h in holdings], "by_strategy": by_strat,
            "exit_rules": {r: {"label": RULES[r], "all": summarize(trades, None, rule=r), "out_of_sample": summarize(oos, None, rule=r)} for r in RULES},
            "warnings": BASE_WARNINGS + ["Exit rules are checked on daily closes with a 60-day cap; entries whose data ends before an exit are dropped. Overlapping holding periods are counted as separate trades; trades are not independent."]}
