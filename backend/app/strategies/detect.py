"""Candidate-generation strategies (A-D). They flag price/valuation situations worth researching.
They are NOT buy signals: classification happens in scoring/classify.py after analysis."""
from dataclasses import dataclass, field

from app.core.config import ScanRules
from app.scanner.features import Features


@dataclass
class Hit:
    strategy: str
    reasons: list[str]
    needs_quality: bool = False  # must be confirmed by the quality screen in the research step
    details: dict = field(default_factory=dict)


def strong_company_pullback(f: Features, idx: Features | None, r: ScanRules) -> Hit | None:
    reasons = []
    if f.daily_change_pct <= -r.daily_drop_pct:
        reasons.append(f"daily {f.daily_change_pct:.1f}% <= -{r.daily_drop_pct}%")
    if f.five_day_change_pct is not None and f.five_day_change_pct <= -r.five_day_drop_pct:
        reasons.append(f"5-day {f.five_day_change_pct:.1f}% <= -{r.five_day_drop_pct}%")
    if not reasons:
        return None
    if f.volume_ratio and f.volume_ratio >= r.unusual_volume_ratio:
        reasons.append(f"volume {f.volume_ratio:.1f}x 20d average")
    return Hit("strong_company_pullback", reasons, needs_quality=True)


def market_overreaction(f: Features, idx: Features | None, r: ScanRules) -> Hit | None:
    if idx is None or idx.daily_change_pct > -r.market_selloff_pct:
        return None
    gap = f.daily_change_pct - idx.daily_change_pct
    if gap > -r.underperf_vs_index_pct:
        return None
    return Hit("market_overreaction",
               [f"index {idx.daily_change_pct:.1f}%, stock {f.daily_change_pct:.1f}% (gap {gap:.1f}pp)"],
               needs_quality=True, details={"relative_pp": gap})


def technical_pullback(f: Features, idx: Features | None, r: ScanRules) -> Hit | None:
    if f.sma50 is None or f.sma200 is None or f.drawdown_20d_pct is None:
        return None
    if not (f.sma50 > f.sma200 and f.price > f.sma200):
        return None  # not an established uptrend
    dist = (f.price / f.sma50 - 1) * 100
    if abs(dist) > r.pullback_sma_tol_pct or f.drawdown_20d_pct > -r.pullback_min_drawdown_pct:
        return None
    return Hit("technical_pullback", [f"uptrend (SMA50>SMA200); {dist:+.1f}% from SMA50, {f.drawdown_20d_pct:.1f}% off 20d high"],
               needs_quality=True)


STRATEGIES = [strong_company_pullback, market_overreaction, technical_pullback]
# Strategy C (valuation_opportunity) needs fundamentals; it is evaluated in the research pipeline.


def run_all(f: Features, idx: Features | None, r: ScanRules) -> list[Hit]:
    return [h for s in STRATEGIES if (h := s(f, idx, r))]
