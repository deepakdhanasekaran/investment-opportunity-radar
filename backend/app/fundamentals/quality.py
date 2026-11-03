"""Business Quality Score (0-100), sector-aware. Missing metrics are excluded from the score AND lower
`confidence`; the displayed score is additionally shrunk by confidence so gaps can never look favourable."""
from dataclasses import dataclass, field

from app.market_data.base import Fundamentals


def ramp(v: float | None, lo: float, hi: float) -> float | None:
    """Linear 0..100 between lo (->0) and hi (->100); works for inverted ranges (lo > hi)."""
    if v is None:
        return None
    return max(0.0, min(100.0, (v - lo) / (hi - lo) * 100))


def _mean(xs: list[float | None]) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def sector_class(sector: str | None, industry: str | None = None) -> str:
    s, i = (sector or "").lower(), (industry or "").lower()
    if "real estate" in s:
        return "real_estate"
    if "financial" in s or any(k in i for k in ("bank", "insurance", "asset management", "capital markets", "holding")):
        return "financial"
    return "industrial"


# Metrics that apply per sector class. Others are N/A and do not count against confidence.
APPLICABLE = {
    "industrial": ["revenue_growth", "earnings_growth", "profitability", "free_cash_flow", "debt", "roic", "earnings_stability", "resilience"],
    "real_estate": ["revenue_growth", "earnings_growth", "profitability", "debt", "earnings_stability", "resilience"],
    "financial": ["revenue_growth", "earnings_growth", "profitability", "earnings_stability"],
}


@dataclass
class QualityResult:
    score: float | None
    confidence: float
    sector_class: str
    components: dict[str, float | None] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


def score_quality(f: Fundamentals, weights: dict[str, float]) -> QualityResult:
    m = f.metrics
    sc = sector_class(f.sector, f.industry)
    fcf_margin = (m.get("free_cash_flow") / m["revenue"]) if m.get("free_cash_flow") is not None and m.get("revenue") else None
    cash_debt = (m.get("total_cash") / m["total_debt"]) if m.get("total_cash") is not None and m.get("total_debt") else None
    if sc == "financial":
        prof = _mean([ramp(m.get("roe"), 0.04, 0.15), ramp(m.get("profit_margin"), 0.05, 0.30)])
    else:
        prof = _mean([ramp(m.get("operating_margin"), 0.0, 0.20), ramp(m.get("profit_margin"), 0.0, 0.15)])
    debt_ramp = (4.0, 1.0) if sc == "real_estate" else (2.0, 0.3)
    comp: dict[str, float | None] = {
        "revenue_growth": ramp(m.get("revenue_growth"), -0.10, 0.15),
        "earnings_growth": ramp(m.get("earnings_growth"), -0.20, 0.20),
        "profitability": prof,
        "free_cash_flow": ramp(fcf_margin, -0.05, 0.10),
        "debt": ramp(m.get("debt_to_equity"), *debt_ramp),
        "roic": ramp(m.get("roic"), 0.0, 0.15),
        "earnings_stability": ramp(m.get("earnings_stability"), 0.5, 1.0),
        "resilience": _mean([ramp(m.get("current_ratio"), 0.8, 1.8), ramp(cash_debt, 0.0, 1.0)]),
    }
    applicable = {k: weights.get(k, 1.0) for k in APPLICABLE[sc]}
    total = sum(applicable.values())
    have = {k: w for k, w in applicable.items() if comp[k] is not None}
    conf = sum(have.values()) / total if total else 0.0
    if not have:
        return QualityResult(None, 0.0, sc, comp, list(applicable))
    raw = sum(comp[k] * w for k, w in have.items()) / sum(have.values())
    return QualityResult(round(raw * (0.5 + 0.5 * conf), 1), round(conf, 3), sc,
                         {k: comp[k] for k in applicable}, [k for k in applicable if k not in have])
