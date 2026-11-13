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
from collections import Counter, defaultdict
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
    "'vs index' compares dividend-adjusted stock returns with a price-only index, overstating the excess by roughly the dividend yield. 'vs universe' (equal-weight of the same stocks, same data) is the fair comparison: it shows whether the signal timing adds anything over simply holding these stocks.",
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
    entry: float = 0.0  # entry price (next-day open)
    bench_ew: float | None = None  # equal-weight universe return over the same span
    score: float = 0.0  # live-scan ranking key (lower = sharper drop); orders same-day signals in portfolio()


def _ew_index(universe: dict[str, list[Bar]]) -> dict[datetime, tuple[float, float]]:
    """Equal-weight index of the universe itself: {ts: (level_at_open, level_at_close)}. Built from the same adjusted bars
    and the same surviving names as the trades, so excess vs it is not flattered by dividends or survivorship."""
    co, cc = defaultdict(list), defaultdict(list)
    for bars in universe.values():
        for prev, b in zip(bars, bars[1:]):
            if prev.close and b.open:
                co[b.ts].append(b.open / prev.close)
                cc[b.ts].append(b.close / prev.close)
    out, lvl = {}, 1.0
    for ts in sorted(cc):
        out[ts] = (lvl * statistics.fmean(co[ts]), lvl * statistics.fmean(cc[ts]))
        lvl = out[ts][1]
    return out


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
    ew = _ew_index(universe)
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
            score = min(f.daily_change_pct, (f.five_day_change_pct or 0) / 2)  # same ranking as scanner/scan.py
            for h in run_all(f, idx, rules):
                if i - last_sig.get(h.strategy, -10**9) < cooldown_days:
                    continue
                last_sig[h.strategy] = i
                e = i + 1
                entry = bars[e].open

                def mk(x: int, hold: int, rule: str = "fixed", why: str = "", sym=sym, bars=bars, h=h, e=e, entry=entry, score=score) -> Trade:
                    r = bars[x].close / entry - 1
                    if fx:
                        a, b = _index_at(fx, bars[e].ts), _index_at(fx, bars[x].ts)
                        if a is not None and b is not None:
                            r = (1 + r) * (fx[b].close / fx[a].open if fx[a].open else 1) - 1
                    ie, ix = _index_at(index_bars, bars[e].ts), _index_at(index_bars, bars[x].ts)
                    bench = index_bars[ix].close / index_bars[ie].open - 1 if ie is not None and ix is not None else None
                    we, wx = ew.get(bars[e].ts), ew.get(bars[x].ts)
                    return Trade(sym, h.strategy, bars[e].ts, bars[x].ts, r - 2 * cost_bps / 1e4, bench, hold, rule, why,
                                 entry, wx[1] / we[0] - 1 if we and wx else None, score)

                for hold in holdings:
                    if e + hold < len(bars):
                        trades.append(mk(e + hold, hold))
                for rule in RULES:
                    x, why = simulate(bars, e + 1, entry, rule)
                    if x is not None:
                        trades.append(mk(x, x - e, rule, why))
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
    exu = [t.ret - t.bench_ew for t in ts if t.bench_ew is not None]
    sd = statistics.stdev(rets) if len(rets) > 1 else None
    top = Counter(t.symbol for t in ts).most_common(1)[0]
    return {"holding_days": holding, "signals": len(ts), "cap_exit_share": sum(t.reason == "cap" for t in ts) / len(ts) if rule != "fixed" else None, "win_rate": sum(r > 0 for r in rets) / len(rets),
            "mean_return": statistics.fmean(rets), "median_return": statistics.median(rets), "volatility": sd,
            "sharpe_per_trade_annualised": (statistics.fmean(rets) / sd * (252 / holding) ** 0.5) if sd else None,
            "mean_excess_vs_benchmark": statistics.fmean(ex) if ex else None,
            "beat_benchmark_rate": sum(e > 0 for e in ex) / len(ex) if ex else None,
            "mean_excess_vs_universe": statistics.fmean(exu) if exu else None,
            "beat_universe_rate": sum(e > 0 for e in exu) / len(exu) if exu else None,
            "max_drawdown_sequenced": _max_drawdown(ts, slots),
            "concentration": {"top_symbol": top[0], "top_symbol_share": top[1] / len(ts), "distinct_symbols": len({t.symbol for t in ts})}}


def _curve_stats(curve: list[tuple[datetime, float]]) -> dict:
    """CAGR, worst peak-to-trough drop and calendar-year returns of a dated equity curve."""
    (d0, v0), (d1, v1) = curve[0], curve[-1]
    peak, dd, years, prev = v0, 0.0, {}, v0
    for (d, v), nxt in zip(curve, curve[1:] + [None]):
        peak = max(peak, v)
        dd = min(dd, v / peak - 1)
        if nxt is None or nxt[0].year != d.year:
            years[str(d.year)] = v / prev - 1
            prev = v
    yrs = max((d1 - d0).days / 365.25, 1e-9)
    return {"total_return": v1 / v0 - 1, "cagr": (v1 / v0) ** (1 / yrs) - 1, "max_drawdown": dd, "by_year": years}


def portfolio(trades: list[Trade], universe: dict[str, list[Bar]], index_bars: list[Bar], rule: str = "hi20", slots: int = 10,
              start: datetime | None = None) -> dict:
    """What one account would actually have done: fixed starting capital, at most `slots` positions, one per symbol,
    each sized equity/slots at entry. Same-day signals compete for free slots in live-scan order (sharpest drop first);
    the rest are skipped. Entries at the open, exits at the close, equity marked on daily closes. Idle cash earns nothing.
    Compared with buying and holding (a) the same universe equal-weight and (b) the price-only index over the same days."""
    ts = sorted((t for t in trades if t.rule == rule and (start is None or t.entry_date >= start)), key=lambda t: (t.entry_date, t.score))
    if not ts:
        return {"trades": 0}
    px = {s: {b.ts: b.close for b in bars} for s, bars in universe.items()}
    days = sorted({d for m in px.values() for d in m if d >= ts[0].entry_date})
    by_day = defaultdict(list)
    for t in ts:
        by_day[t.entry_date].append(t)
    cash, equity, pos, curve, done, skipped, exposure = 1.0, 1.0, {}, [], [], 0, []
    for d in days:
        for t in by_day.get(d, ()):
            stake = min(equity / slots, cash)
            if t.symbol in pos or len(pos) >= slots or stake <= 0:
                skipped += 1
                continue
            cash -= stake
            pos[t.symbol] = [t, stake, t.entry]
        for sym in [s for s, (t, _, _) in pos.items() if t.exit_date <= d]:
            t, stake, _ = pos.pop(sym)
            cash += stake * (1 + t.ret)  # t.ret is net of both sides' costs
            done.append(t)
        for sym, p in pos.items():
            p[2] = px[sym].get(d, p[2])
        held = sum(stake * last / t.entry for t, stake, last in pos.values())
        equity = cash + held
        exposure.append(held / equity if equity else 0.0)
        curve.append((d, equity))
    ew = _ew_index(universe)
    idx = {b.ts: b.close for b in index_bars}
    return {"slots": slots, "from": days[0].isoformat(), "to": days[-1].isoformat(), "trades": len(done), "skipped_signals": skipped,
            "open_at_end": len(pos), "win_rate": sum(t.ret > 0 for t in done) / len(done) if done else None,
            "avg_exposure": statistics.fmean(exposure), "strategy": _curve_stats(curve),
            "universe_equal_weight": _curve_stats([(d, ew[d][1]) for d in days if d in ew]),
            "index_price_only": _curve_stats([(d, idx[d]) for d in days if d in idx]) if any(d in idx for d in days) else None}


def report(trades: list[Trade], oos_fraction: float = 0.4, holdings=HOLDINGS, universe: dict[str, list[Bar]] | None = None,
           index_bars: list[Bar] | None = None, slots: int = 10) -> dict:
    if not trades:
        return {"signals": 0, "warnings": BASE_WARNINGS + ["No signals generated."]}
    dates = sorted({t.entry_date for t in trades})
    cut = dates[int(len(dates) * (1 - oos_fraction))]
    ins, oos = [t for t in trades if t.entry_date < cut], [t for t in trades if t.entry_date >= cut]
    by_strat = {s: [summarize([t for t in trades if t.strategy == s], h) for h in holdings] for s in {t.strategy for t in trades}}
    port = {r: {"label": RULES[r], "all": portfolio(trades, universe, index_bars or [], r, slots),
                "out_of_sample": portfolio(trades, universe, index_bars or [], r, slots, start=cut)} for r in RULES} if universe else None
    return {"split_date": cut.isoformat(), "portfolio": port, "in_sample": [summarize(ins, h) for h in holdings],
            "out_of_sample": [summarize(oos, h) for h in holdings], "by_strategy": by_strat,
            "exit_rules": {r: {"label": RULES[r], "all": summarize(trades, None, rule=r), "out_of_sample": summarize(oos, None, rule=r)} for r in RULES},
            "warnings": BASE_WARNINGS + ["Exit rules are checked on daily closes with a 60-day cap; entries whose data ends before an exit are dropped. Overlapping holding periods are counted as separate trades; trades are not independent."]}
