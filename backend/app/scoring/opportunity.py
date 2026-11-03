"""Opportunity Score (0-100). It ranks how interesting a price/valuation situation is for research.
It is NOT a probability of future returns."""
from dataclasses import dataclass, field

from app.fundamentals.quality import ramp
from app.scanner.features import Features
from app.valuation.valuation import ValuationResult


@dataclass
class OpportunityResult:
    score: float | None
    coverage: float
    components: dict[str, float | None] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


def score_opportunity(f: Features, idx: Features | None, val: ValuationResult | None, fwd_pe_ratio: float | None,
                      news_sentiment: float | None, negative_announcement: bool | None, weights: dict[str, float]) -> OpportunityResult:
    drops = [ramp(-f.daily_change_pct, 0, 8), ramp(-f.five_day_change_pct, 0, 15) if f.five_day_change_pct is not None else None,
             ramp(-f.drawdown_20d_pct, 0, 20) if f.drawdown_20d_pct is not None else None]
    drops = [d for d in drops if d is not None]
    trend = None
    if f.sma200:
        trend = 100.0 if f.price > f.sma200 else 50.0 if f.price > 0.9 * f.sma200 else 0.0
        if f.sma50 and f.sma50 < f.sma200:
            trend *= 0.5
    mkt = None
    if idx is not None:
        mkt = 100.0 if idx.daily_change_pct <= -1 else 30.0 if idx.daily_change_pct <= 0 else 0.0
    comp: dict[str, float | None] = {
        "price_decline": max(drops),
        "relative_perf": ramp(f.daily_change_pct - idx.daily_change_pct, 0, -5) if idx else None,
        "hist_valuation": val.hist_score if val else None,
        "cur_valuation": val.current_score if val else None,
        "earnings_outlook": ramp(fwd_pe_ratio, 1.3, 0.7) if fwd_pe_ratio else None,
        "volume": ramp(f.volume_ratio, 1, 3) if f.volume_ratio else None,
        "momentum": trend,
        "market_conditions": mkt,
        "announcements": None if negative_announcement is None else (0.0 if negative_announcement else 100.0),
        "news_sentiment": None if news_sentiment is None else (news_sentiment + 1) * 50,
    }
    have = {k: weights.get(k, 1.0) for k, v in comp.items() if v is not None}
    total = sum(weights.get(k, 1.0) for k in comp)
    if not have:
        return OpportunityResult(None, 0.0, comp, list(comp))
    s = sum(comp[k] * w for k, w in have.items()) / sum(have.values())
    return OpportunityResult(round(s, 1), round(sum(have.values()) / total, 3), comp, [k for k, v in comp.items() if v is None])
