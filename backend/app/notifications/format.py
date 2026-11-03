from app.database.models import Analysis, Security

DISCLAIMER = "Screening aid only, not investment advice. Scores are not return forecasts. Verify the data before acting."


def format_opportunity(a: Analysis, sec: Security, dashboard_url: str, header: str = "INVESTMENT OPPORTUNITY") -> str:
    r, facts, interp = a.report, a.report["facts"], a.report["interpretation"]
    q = f"{a.quality_score:.0f}/100 (data coverage {a.quality_confidence:.0%})" if a.quality_score is not None else "n/a (insufficient data)"
    o = f"{a.opportunity_score:.0f}/100" if a.opportunity_score is not None else "n/a"
    label = {"GREEN": "GREEN - Worth Investigating", "YELLOW": "YELLOW - Watchlist", "RED": "RED - Reject"}[a.classification]
    lines = [header, "",
             f"Company: {sec.name or sec.symbol} ({sec.symbol})", f"Exchange: {sec.exchange}", f"Currency: {sec.currency}", "",
             f"Price: {facts['price']:.2f} at {facts['quote_ts']} (source: {facts['quote_source']})",
             f"Daily change: {facts['daily_change_pct']:+.1f}%" + (f" | 5-day: {facts['five_day_change_pct']:+.1f}%" if facts.get("five_day_change_pct") is not None else ""),
             f"Quality Score: {q}", f"Opportunity Score: {o}", f"Risk: {a.risk_level}", "",
             f"Potential explanation: {interp['decline_explanation']}", f"Financial assessment: {interp['financial_assessment']}",
             f"Valuation: {interp['valuation']}", "", f"Classification: {label}"]
    if r.get("uncertainties"):
        lines += ["", "Uncertainties:"] + [f"- {u}" for u in r["uncertainties"][:5]]
    if r.get("news"):
        lines += ["", "News:"] + [f"- {n['title'][:100]} {n['url']}" for n in r["news"][:3]]
    lines += ["", f"Data: {', '.join(facts['providers'])}", f"Dashboard: {dashboard_url}/company/{sec.symbol}", "", DISCLAIMER]
    return "\n".join(lines)


def format_invalidated(a: Analysis, sec: Security, dashboard_url: str) -> str:
    return (f"OPPORTUNITY NO LONGER VALID\n\n{sec.name or sec.symbol} ({sec.symbol}) is now {a.classification}.\n"
            f"Reasons: {'; '.join(a.factors['verdict']['rules'][:4])}\nDashboard: {dashboard_url}/company/{sec.symbol}\n\n{DISCLAIMER}")
