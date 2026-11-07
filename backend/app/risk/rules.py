"""Deterministic risk rules. Severity: INFO (shown), REVIEW (blocks GREEN), CRITICAL (forces RED).
Keyword rules are headline-based and therefore heuristics: they raise flags for human review, nothing more."""
import re
from dataclasses import dataclass

from app.fundamentals.quality import sector_class
from app.market_data.base import Fundamentals

CRITICAL_KW = r"going concern|bankruptcy|insolven|delist|default(?:s|ed)? on|fraud|accounting irregularit|restate(?:s|d|ment)|auditor resign|sec investigation|criminal"
REVIEW_KW = r"profit warning|cuts? (?:its )?(?:guidance|outlook|forecast)|lowers? (?:guidance|outlook)|dividend cut|suspends? dividend|investigation|probe|lawsuit|antitrust|recall|fined|regulator|downgrade|short seller"


@dataclass
class Flag:
    code: str
    severity: str  # INFO | REVIEW | CRITICAL
    text: str


def evaluate(f: Fundamentals | None, price: float, headlines: list[str], vol_ann_pct: float | None,
             daily_change_pct: float, recent_splits: bool, ex_div_recent: bool, quality_conf: float, min_daily_value: float = 5e6,
             days_to_earnings: int | None = None, pe_vs_hist: float | None = None) -> list[Flag]:
    out: list[Flag] = []
    if f is None:
        out.append(Flag("fundamentals_missing", "REVIEW", "Fundamentals unavailable: analysis incomplete"))
    else:
        m, sc = f.metrics, sector_class(f.sector, f.industry)
        if quality_conf < 0.5:
            out.append(Flag("low_data_coverage", "REVIEW", f"Only {quality_conf:.0%} of applicable quality metrics available"))
        pm, eg, fcf, de, cr = m.get("profit_margin"), m.get("earnings_growth"), m.get("free_cash_flow"), m.get("debt_to_equity"), m.get("current_ratio")
        if pm is not None and pm < 0:
            out.append(Flag("net_loss", "REVIEW", f"Net profit margin {pm:.1%}"))
        if eg is not None and eg <= -0.5:
            out.append(Flag("earnings_deterioration", "CRITICAL", f"Earnings growth {eg:.0%}"))
        elif eg is not None and eg <= -0.25:
            out.append(Flag("earnings_deterioration", "REVIEW", f"Earnings growth {eg:.0%}"))
        if sc == "industrial":
            if de is not None and de > 4:
                out.append(Flag("excessive_leverage", "CRITICAL", f"Debt/equity {de:.1f}"))
            elif de is not None and de > 2:
                out.append(Flag("excessive_leverage", "REVIEW", f"Debt/equity {de:.1f}"))
            if cr is not None and cr < 0.8:
                out.append(Flag("liquidity_stress", "REVIEW", f"Current ratio {cr:.2f}"))
            if pm is not None and pm < 0 and fcf is not None and fcf < 0:
                out.append(Flag("financial_distress", "CRITICAL" if (cr is not None and cr < 1) else "REVIEW",
                                "Loss-making with negative free cash flow"))
        avg_vol = m.get("avg_volume")
        if avg_vol is not None and avg_vol * price < min_daily_value:
            out.append(Flag("liquidity_risk", "REVIEW", f"Average daily traded value ~{avg_vol * price:,.0f} below {min_daily_value:,.0f}"))
        pe = m.get("pe")
        if pe is not None and pe > 60:
            out.append(Flag("extreme_valuation", "REVIEW", f"P/E {pe:.0f}"))
        if f.sector in ("Energy", "Basic Materials"):
            out.append(Flag("cyclical_sector", "INFO", f"{f.sector}: earnings follow commodity prices, so P/E and own-history comparisons are unreliable"))
        if pe_vs_hist is not None and pe_vs_hist >= 1.5:
            out.append(Flag("expensive_vs_own_history", "REVIEW", f"P/E is {pe_vs_hist:.0%} of its own median: cheap only on absolute multiples"))
    if days_to_earnings is not None and 0 <= days_to_earnings <= 3:
        out.append(Flag("earnings_imminent", "REVIEW", "Earnings report today" if days_to_earnings == 0 else f"Earnings report in {days_to_earnings} day(s): event risk"))
    if vol_ann_pct is not None and vol_ann_pct > 60:
        out.append(Flag("unusual_volatility", "REVIEW", f"20-day annualised volatility {vol_ann_pct:.0f}%"))
    if daily_change_pct <= -40:
        out.append(Flag("implausible_move", "REVIEW", f"{daily_change_pct:.0f}% move: verify for data error or unadjusted split"))
    if recent_splits:
        out.append(Flag("recent_split", "REVIEW", "Stock split in recent sessions: verify price adjustment"))
    if ex_div_recent:
        out.append(Flag("ex_dividend", "INFO", "Recent dividend: part of the decline may be the dividend itself"))
    seen = set()
    for h in headlines:
        for pat, sev, code in ((CRITICAL_KW, "CRITICAL", "negative_news_critical"), (REVIEW_KW, "REVIEW", "negative_news")):
            mt = re.search(pat, h, re.I)
            if mt and (code, h) not in seen:
                seen.add((code, h))
                out.append(Flag(code, sev, f"Headline matched '{mt.group(0)}': {h[:140]}"))
                break
    return out


def risk_level(flags: list[Flag], incomplete: bool) -> str:
    if any(x.severity == "CRITICAL" for x in flags):
        return "CRITICAL"
    n = sum(x.severity == "REVIEW" for x in flags)
    if incomplete and n == 0:
        return "UNKNOWN"
    return "HIGH" if n >= 2 else "MODERATE" if n == 1 else "LOW"
