"""Paper-trading evaluation: every GREEN analysis the live system produced is tracked as a hypothetical entry at the
alerted price; outcomes are measured at 5/20/60/120 trading days against the market benchmark. Nothing is traded."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

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
        rows.append({"symbol": sec.symbol, "at": d0.isoformat(), "strategies": [x["name"] for x in a.report["facts"]["strategies"]], "outcomes": out})
    summary = {}
    for h in HOLDS:
        xs = [r["outcomes"][str(h)] for r in rows if str(h) in r["outcomes"]]
        if xs:
            summary[str(h)] = {"n": len(xs), "win_rate": sum(x["ret"] > 0 for x in xs) / len(xs),
                               "mean_return": sum(x["ret"] for x in xs) / len(xs), "mean_excess": sum(x["excess"] for x in xs) / len(xs),
                               "false_positive_rate": sum(x["excess"] < 0 for x in xs) / len(xs)}
    strat = {}
    for r in rows:
        for st in set(r["strategies"]):
            if "20" in r["outcomes"]:
                strat.setdefault(st, []).append(r["outcomes"]["20"]["excess"])
    result = {"as_of": now.isoformat(), "tracked_green": len(rows), "by_holding": summary,
              "by_strategy_20d_mean_excess": {k: sum(v) / len(v) for k, v in strat.items()}, "rows": rows,
              "note": "Entry = analysed price (no costs/slippage). 'false positive' = underperformed the market index over the holding period. Small samples are not statistically meaningful."}
    s.add(BacktestResult(kind="paper", params={}, result=result))
    return result


def paper_report(s: Session) -> dict:
    r = s.scalar(select(BacktestResult).where(BacktestResult.kind == "paper").order_by(BacktestResult.created_at.desc()).limit(1))
    return r.result if r else {"tracked_green": 0, "by_holding": {}, "note": "No paper-trading evaluation has run yet."}
