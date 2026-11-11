"""CLI: python -m app.backtesting.run [SE|US] [--limit N]. Downloads ~5y of daily bars via Yahoo and stores the result."""
import argparse
import json

from app.core.config import get_settings
from app.backtesting.engine import generate_trades, report
from app.database.models import BacktestResult
from app.database.session import session_scope
from app.market_data.symbols import MARKETS
from app.market_data.yahoo import YahooProvider
from app.universe.loader import universe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("market", choices=list(MARKETS))
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    a = ap.parse_args()
    st, mk, p = get_settings(), MARKETS[a.market], YahooProvider()
    names = getattr(st.scan, f"{a.market.lower()}_universe")
    syms = [m.symbol for m in universe(a.market, names)][: a.limit]
    bars = p.histories(syms + [mk["index"]], 1900)
    idx = bars.pop(mk["index"])
    res = report(generate_trades(bars, idx, mk["tz"], st.scan, cost_bps=a.cost_bps))
    res["universe"] = {"market": a.market, "symbols": len(bars), "cost_bps_per_side": a.cost_bps, "benchmark": mk["index"], "currency": "local (FX not applied)"}
    with session_scope() as s:
        s.add(BacktestResult(kind="historical", params=res["universe"], result=res))
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
