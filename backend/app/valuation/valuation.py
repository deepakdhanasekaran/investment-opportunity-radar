"""Current and historical valuation. Historical P/E = year-end price / that year's diluted EPS (annual statements,
typically 3-4 years from Yahoo): a coarse own-history reference, not a point-in-time dataset."""
import statistics
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.fundamentals.quality import ramp, sector_class
from app.market_data.base import Bar, Fundamentals


@dataclass
class ValuationResult:
    current_score: float | None
    hist_score: float | None
    pe: float | None
    hist_pe_median: float | None
    pe_vs_hist: float | None
    extreme: bool = False
    notes: list[str] = field(default_factory=list)


def hist_pe_median(eps: list[tuple[str, float]], bars: list[Bar]) -> float | None:
    if len(bars) < 2:
        return None
    ts = [b.ts for b in bars]
    pes = []
    for d, e in eps:
        if e <= 0:
            continue
        t = datetime.fromisoformat(d).replace(tzinfo=timezone.utc)
        i = bisect_right(ts, t) - 1
        if i >= 0 and (t - ts[i]).days < 10:
            pes.append(bars[i].close / e)
    return statistics.median(pes) if len(pes) >= 3 else None


def assess(f: Fundamentals, bars: list[Bar], price: float) -> ValuationResult:
    m, sc = f.metrics, sector_class(f.sector, f.industry)
    pe = m.get("pe")
    notes: list[str] = []
    if pe is not None and pe <= 0:
        notes.append("negative earnings: P/E not meaningful")
        pe = None
    if sc == "financial":
        cur = [ramp(m.get("pb"), 3.0, 0.8), ramp(pe, 25, 7)]
    else:
        cur = [ramp(pe, 35, 10), ramp(m.get("ev_ebitda"), 20, 6)]
    cur = [c for c in cur if c is not None]
    cur_score = sum(cur) / len(cur) if cur else None
    med = hist_pe_median(f.annual_eps, bars)
    ratio = pe / med if pe and med else None
    hist_score = ramp(ratio, 1.3, 0.7)
    if med is None:
        notes.append("own-history P/E unavailable (fewer than 3 positive-EPS years)")
    return ValuationResult(cur_score, hist_score, pe, med, ratio, extreme=bool(pe and pe > 60), notes=notes)
