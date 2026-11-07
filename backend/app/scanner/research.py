"""Research pipeline for one candidate -> Analysis row. All judgments are rule-based; text in the report is
generated from the verified numbers, never free-form. Facts and interpretation are kept in separate sections."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database import health
from app.database.models import Analysis, FundamentalSnapshot, NewsArticle, Security, Signal
from app.fundamentals.quality import QualityResult, score_quality
from app.market_data.base import Fundamentals, MarketDataProvider, Quote
from app.news.fetch import fetch_news
from app.risk.rules import evaluate, risk_level
from app.scanner.features import Features, reference_levels
from app.scoring.classify import classify
from app.scoring.opportunity import score_opportunity
from app.sentiment.analyzer import score_titles
from app.strategies.detect import Hit
from app.valuation.valuation import assess

log = logging.getLogger(__name__)


def _explain_decline(f: Features, idx: Features | None, neg_headlines: list[str]) -> str:
    if neg_headlines:
        return f"Possible company-specific cause (unverified, from headline): {neg_headlines[0][:120]}"
    if idx is not None and idx.daily_change_pct <= -1.0 and f.daily_change_pct - idx.daily_change_pct > -1.5:
        return "Broad market decline; no company-specific negative headline found in retrieved news (not proof of cause)."
    return "Cause unknown: no company-specific explanation established."


def _fin_text(q: QualityResult | None, m: dict) -> str:
    if q is None or q.score is None:
        return "Insufficient fundamentals to assess."
    bits = []
    if m.get("revenue_growth") is not None:
        bits.append(f"revenue growth {m['revenue_growth']:+.1%}")
    if m.get("profit_margin") is not None:
        bits.append(f"net margin {m['profit_margin']:.1%}")
    if m.get("debt_to_equity") is not None and q.sector_class != "financial":
        bits.append(f"debt/equity {m['debt_to_equity']:.2f}")
    return (", ".join(bits) or "limited metrics") + f" (sector class: {q.sector_class}; {q.confidence:.0%} of applicable metrics available)."


def research(s: Session, st: Settings, provider: MarketDataProvider, sec: Security, quote: Quote, feats: Features,
             idx: Features | None, hits: list[Hit], signal: Signal | None = None, now: datetime | None = None,
             long_bars=None) -> Analysis:
    now = now or datetime.now(timezone.utc)
    uncertainties: list[str] = []
    providers = {quote.source}

    fund: Fundamentals | None = None
    try:
        fund = provider.fundamentals(sec.symbol)
        health.record(s, provider.name, True)
        providers.add(fund.source)
        sec.sector = sec.sector or fund.sector or ""
        snap_date = fund.retrieved_ts.date()
        if not s.query(FundamentalSnapshot).filter_by(security_id=sec.id, source=fund.source, snapshot_date=snap_date).first():
            s.add(FundamentalSnapshot(security_id=sec.id, source=fund.source, snapshot_date=snap_date,
                                      retrieved_ts=fund.retrieved_ts, sector=fund.sector, metrics=fund.metrics))
    except Exception as e:
        health.record(s, provider.name, False, str(e))
        uncertainties.append(f"Fundamentals unavailable ({type(e).__name__}): analysis incomplete.")

    q = score_quality(fund, st.weights.quality) if fund else None
    bars = long_bars
    if bars is None and fund:
        try:
            bars = provider.history(sec.symbol, 1900)
        except Exception:
            bars = []
    val = assess(fund, bars or [], quote.price) if fund else None
    if val:
        uncertainties += val.notes
        if val.pe_vs_hist is not None and val.pe_vs_hist <= st.scan.valuation_discount and hits:
            hits = hits + [Hit("valuation_opportunity", [f"P/E {val.pe:.1f} vs own median {val.hist_pe_median:.1f}"], needs_quality=True)]

    arts = []
    if st.news_enabled:
        try:
            arts = fetch_news(sec.name, sec.symbol, sec.market)
            providers.add("google-news-rss")
            health.record(s, "google-news-rss", True)
        except Exception as e:
            health.record(s, "google-news-rss", False, str(e))
            uncertainties.append("News retrieval failed: news and announcement risk not assessed.")
    sents, model = score_titles([a.title for a in arts], st.sentiment_backend) if arts else ([], "none")
    for a, sc in zip(arts, sents):
        if not s.query(NewsArticle).filter_by(security_id=sec.id, url_hash=a.url_hash).first():
            s.add(NewsArticle(security_id=sec.id, url_hash=a.url_hash, title=a.title, url=a.url, publisher=a.publisher,
                              source_ts=a.source_ts, sentiment=sc, sentiment_model=model))
    avg_sent = sum(sents) / len(sents) if sents else None
    headlines = [a.title for a in arts]

    actions = []
    try:
        actions = provider.corporate_actions(sec.symbol)
    except Exception:
        uncertainties.append("Corporate actions unavailable.")
    cutoff = (now - timedelta(days=7)).date().isoformat()
    recent_split = any(a["split"] and a["date"] >= cutoff for a in actions)
    ex_div = any(a["dividend"] and a["date"] >= (now - timedelta(days=2)).date().isoformat() for a in actions)

    flags = evaluate(fund, quote.price, headlines, feats.volatility_ann_pct, feats.daily_change_pct, recent_split, ex_div,
                     q.confidence if q else 0.0,
                     days_to_earnings=(fund.next_earnings - now.date()).days if fund and fund.next_earnings else None,
                     pe_vs_hist=val.pe_vs_hist if val else None)
    neg = [x.text.split(": ", 1)[-1] for x in flags if x.code.startswith("negative_news")]
    fwd = fund.metrics.get("forward_pe") if fund else None
    fwd_ratio = fwd / val.pe if (fwd and val and val.pe) else None
    opp = score_opportunity(feats, idx, val, fwd_ratio, avg_sent, bool(neg) if arts else None, st.weights.opportunity)
    verdict = classify(q, opp, flags, st.cls)
    if not arts and st.news_enabled:
        uncertainties.append("No news retrieved: cause of decline cannot be verified.")
    if fund and fund.next_earnings is None:
        uncertainties.append("Next earnings date unavailable: an imminent report cannot be ruled out.")
    if q and q.missing:
        uncertainties.append("Missing quality metrics: " + ", ".join(q.missing))
    if len(headlines) > 0 and model == "lexicon":
        uncertainties.append("News sentiment uses a simple lexicon (English + a few Swedish terms), not FinBERT; headlines it does not recognise score 0.0, i.e. no signal.")

    m = fund.metrics if fund else {}
    facts = {
        "price": quote.price, "currency": sec.currency, "quote_ts": quote.source_ts.isoformat(),
        "quote_retrieved_ts": quote.retrieved_ts.isoformat(), "quote_source": quote.source,
        "daily_change_pct": feats.daily_change_pct, "five_day_change_pct": feats.five_day_change_pct,
        "index_daily_change_pct": idx.daily_change_pct if idx else None, "volume_ratio": feats.volume_ratio,
        "sma50": feats.sma50, "sma200": feats.sma200, "drawdown_20d_pct": feats.drawdown_20d_pct,
        "volatility_ann_pct": feats.volatility_ann_pct,
        "fundamentals": {k: m.get(k) for k in ("revenue_growth", "earnings_growth", "profit_margin", "operating_margin", "debt_to_equity",
                                               "roe", "roic", "pe", "forward_pe", "pb", "ev_ebitda", "current_ratio", "free_cash_flow")},
        "valuation": {"pe": val.pe, "hist_pe_median": val.hist_pe_median, "pe_vs_hist": val.pe_vs_hist} if val else None,
        "levels": reference_levels(feats), "next_earnings": fund.next_earnings.isoformat() if fund and fund.next_earnings else None,
        "providers": sorted(providers), "strategies": [{"name": h.strategy, "reasons": h.reasons} for h in hits],
    }
    val_text = "Valuation data unavailable."
    if val and val.pe_vs_hist is not None:
        val_text = f"P/E {val.pe:.1f} is {val.pe_vs_hist:.0%} of its own multi-year median ({val.hist_pe_median:.1f})."
    elif val and val.pe is not None:
        val_text = f"P/E {val.pe:.1f}; own-history comparison unavailable."
    interp = {"decline_explanation": _explain_decline(feats, idx, neg), "financial_assessment": _fin_text(q, m), "valuation": val_text}
    factors = {
        "quality": {"components": q.components, "missing": q.missing, "confidence": q.confidence, "sector_class": q.sector_class} if q else None,
        "opportunity": {"components": opp.components, "coverage": opp.coverage},
        "risk_flags": [vars(x) for x in flags],
        "verdict": {"classification": verdict.classification, "rules": verdict.rules},
        "weights": {"quality": st.weights.quality, "opportunity": st.weights.opportunity}, "thresholds": st.cls.model_dump(),
    }
    news_out = [{"title": a.title, "url": a.url, "publisher": a.publisher, "ts": a.source_ts.isoformat() if a.source_ts else None,
                 "sentiment": sc} for a, sc in zip(arts[:8], sents)]
    row = Analysis(security_id=sec.id, signal_id=signal.id if signal else None, created_at=now,
                   quality_score=q.score if q else None, quality_confidence=q.confidence if q else 0.0,
                   opportunity_score=opp.score, risk_level=risk_level(flags, verdict.incomplete),
                   classification=verdict.classification, incomplete=verdict.incomplete, factors=factors,
                   report={"facts": facts, "interpretation": interp, "news": news_out, "uncertainties": uncertainties})
    s.add(row)
    s.flush()
    return row
