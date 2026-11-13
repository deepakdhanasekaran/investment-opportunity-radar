"""Paper-trading evaluation: every GREEN analysis the live system produced is tracked as a hypothetical entry at the
alerted price; outcomes are measured at 5/20/60/120 trading days against the market benchmark. Nothing is traded."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.exits import RULES, simulate
from app.core.config import get_settings
from app.database.models import Analysis, BacktestResult
from app.market_data.symbols import MARKETS

HOLDS = (5, 20, 60, 120)


def evaluate(s: Session, provider, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    greens = s.scalars(select(Analysis).where(Analysis.classification == "GREEN").order_by(Analysis.created_at)).all()
    first: dict[int, Analysis] = {}
    for a in greens:
        first.setdefault(a.security_id, a)  # first GREEN per security
    cache: dict[str, list] = {}
    stakes = get_settings().scan.paper_stake

    def bars(sym):
        if sym not in cache:
            cache[sym] = provider.history(sym, 600)
        return cache[sym]

    rows = []
    for a in first.values():
        sec = a.security
        try:
            b, ib = bars(sec.symbol), bars(MARKETS[sec.market]["index"])
        except Exception:
            continue
        entry_px = a.report["facts"]["price"]
        d0 = a.created_at.replace(tzinfo=timezone.utc)
        after = [x for x in b if x.ts > d0]
        ia = [x for x in ib if x.ts > d0]
        out = {}
        for h in HOLDS:
            if len(after) >= h and len(ia) >= h and ia[0].open:
                r, br = after[h - 1].close / entry_px - 1, ia[h - 1].close / ia[0].open - 1
                out[str(h)] = {"ret": r, "bench": br, "excess": r - br}
        stake = stakes.get(sec.market, 0.0)
        s0 = next((i for i, x in enumerate(b) if x.ts > d0), None)
        ex = {}
        for rule in RULES:
            if s0 is None or not ia:
                break
            xi, why = simulate(b, s0, entry_px, rule)
            d = None if xi is None else xi - s0 + 1
            if d and len(ia) >= d and ia[0].open:
                r, br = b[xi].close / entry_px - 1, ia[d - 1].close / ia[0].open - 1
                ex[rule] = {"ret": r, "bench": br, "excess": r - br, "days": d, "reason": why, "pnl": stake * r}
        pos = None
        if s0 is not None and s0 < len(b):  # position still running under at least one rule: show live value and the levels we're waiting for
            held, last = len(b) - s0, b[-1].close
            pos = {"stake": stake, "currency": sec.currency, "entry": entry_px, "last": last, "days_held": held, "days_left": max(0, 60 - held),
                   "unrealized_pct": last / entry_px - 1, "unrealized": stake * (last / entry_px - 1),
                   "targets": {"hi20": max(x.close for x in b[-20:]), "ma50": sum(x.close for x in b[-50:]) / len(b[-50:]),
                               "trail8": max(entry_px, *(x.close for x in b[s0:])) * 0.92}}
        rows.append({"position": pos, "currency": sec.currency, "stake": stake, "symbol": sec.symbol, "name": sec.name, "at": d0.isoformat(), "strategies": [x["name"] for x in a.report["facts"]["strategies"]], "outcomes": out, "exits": ex})
    summary = {}
    for h in HOLDS:
        xs = [r["outcomes"][str(h)] for r in rows if str(h) in r["outcomes"]]
        if xs:
            summary[str(h)] = {"n": len(xs), "win_rate": sum(x["ret"] > 0 for x in xs) / len(xs),
                               "mean_return": sum(x["ret"] for x in xs) / len(xs), "mean_excess": sum(x["excess"] for x in xs) / len(xs),
                               "false_positive_rate": sum(x["excess"] < 0 for x in xs) / len(xs)}
    by_exit = {}
    for rule in RULES:
        xs = [r["exits"][rule] for r in rows if rule in r["exits"]]
        by_exit[rule] = {"label": RULES[rule], "n": len(xs), "still_open": len(rows) - len(xs)}
        if xs:
            by_exit[rule].update(win_rate=sum(x["ret"] > 0 for x in xs) / len(xs), mean_return=sum(x["ret"] for x in xs) / len(xs),
                                 mean_excess=sum(x["excess"] for x in xs) / len(xs), mean_days=sum(x["days"] for x in xs) / len(xs), total_pnl=sum(x["pnl"] for x in xs),
                                 cap_exit_share=sum(x["reason"] == "cap" for x in xs) / len(xs))
    strat = {}
    for r in rows:
        for st in set(r["strategies"]):
            if "20" in r["outcomes"]:
                strat.setdefault(st, []).append(r["outcomes"]["20"]["excess"])
    result = {"as_of": now.isoformat(), "tracked_green": len(rows), "by_holding": summary, "by_exit_rule": by_exit, "open_positions": [r for r in rows if r["position"] and any(k not in r["exits"] for k in RULES)],
              "by_strategy_20d_mean_excess": {k: sum(v) / len(v) for k, v in strat.items()}, "rows": rows,
              "note": "Entry = analysed price (no costs/slippage). 'false positive' = underperformed the market index over the holding period. Small samples are not statistically meaningful."}
    s.add(BacktestResult(kind="paper", params={}, result=result))
    return result


def paper_report(s: Session) -> dict:
    r = s.scalar(select(BacktestResult).where(BacktestResult.kind == "paper").order_by(BacktestResult.created_at.desc()).limit(1))
    return r.result if r else {"tracked_green": 0, "by_holding": {}, "note": "No paper-trading evaluation has run yet."}
