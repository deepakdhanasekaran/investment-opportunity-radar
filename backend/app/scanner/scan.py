"""One scan pass for one market. Stage 1 is price-only and cheap (batched); stage 2 (research) runs only for candidates."""
import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database import health
from app.database.models import Analysis, PriceObservation, ScannerRun, Security, Signal, WatchlistItem
from app.market_data.base import MarketDataProvider
from app.market_data.calendars import session_fraction
from app.market_data.symbols import MARKETS
from app.notifications.alerts import alert_for_analysis, system_alert
from app.scanner.features import compute, session_date
from app.scanner.research import research
from app.strategies.detect import run_all
from app.universe.loader import universe

log = logging.getLogger(__name__)
RESEARCH_TTL = timedelta(minutes=60)


def _chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def _upsert_security(s: Session, m, mk: dict) -> Security:
    sec = s.scalar(select(Security).where(Security.symbol == m.symbol))
    if sec is None:
        sec = Security(symbol=m.symbol, name=m.name, market=m.market, exchange=mk["exchange"], currency=mk["currency"], sector=m.sector)
        s.add(sec)
        s.flush()
    return sec


def run_scan(s: Session, st: Settings, provider: MarketDataProvider, market: str, now: datetime | None = None) -> ScannerRun:
    now = now or datetime.now(timezone.utc)
    mk = MARKETS[market]
    run = ScannerRun(market=market, started_at=now)
    s.add(run)
    s.flush()
    wl = [(w.security.symbol, w.security.market) for w in s.scalars(select(WatchlistItem)).all()]
    names = getattr(st.scan, f"{market.lower()}_universe")
    members = universe(market, names, wl)
    by_sym = {m.symbol: m for m in members}
    syms = list(by_sym)
    try:
        index_sym = mk["index"]
        bars, quotes = {}, {}
        for ch in _chunks(syms + [index_sym], 100):
            bars.update(provider.histories(ch, 400))
            quotes.update(provider.quotes(ch, mk["currency"]))
        health.record(s, provider.name, True)
    except Exception as e:
        run.status, run.error, run.finished_at = "failed", f"provider error: {e}"[:500], datetime.now(timezone.utc)
        h = health.record(s, provider.name, False, str(e))
        if h.consecutive_failures >= 3:
            system_alert(s, st, f"provider:{provider.name}", f"Data provider '{provider.name}' failing repeatedly: {e}", now=now)
        return run

    max_age = st.scan.max_quote_age_minutes.get(market, 20)
    idx = None
    iq = quotes.get(index_sym)
    if iq and iq.age_minutes(now) <= max_age and index_sym in bars:
        idx = compute(bars[index_sym], iq, mk["tz"])

    found: list[tuple] = []
    failed = stale = 0
    for sym in syms:
        q, b = quotes.get(sym), bars.get(sym)
        if q is None or b is None:
            failed += 1
            continue
        if q.age_minutes(now) > max_age:
            stale += 1
            failed += 1
            continue
        f = compute(b, q, mk["tz"], session_fraction(market, q.source_ts))
        if f is None:
            failed += 1
            continue
        hits = run_all(f, idx, st.scan)
        if hits:
            found.append((sym, q, f, hits, b))
    run.scanned, run.failed = len(syms) - failed, failed
    # rank by the sharper of the daily move and half the 5-day move so slow bleeds are not buried by flat days
    found.sort(key=lambda t: min(t[2].daily_change_pct, (t[2].five_day_change_pct or 0) / 2))
    found = found[: st.scan.max_candidates_per_scan]
    run.candidates = len(found)

    for sym, q, f, hits, b in found:
        sec = _upsert_security(s, by_sym[sym], mk)
        q = replace(q, currency=q.currency or sec.currency)
        if not s.scalar(select(PriceObservation.id).where(PriceObservation.security_id == sec.id, PriceObservation.source == q.source,
                                                          PriceObservation.source_ts == q.source_ts)):
            s.add(PriceObservation(security_id=sec.id, price=q.price, volume=q.volume, currency=q.currency, source=q.source,
                                   source_ts=q.source_ts, retrieved_ts=q.retrieved_ts))
        sd = session_date(q.source_ts, mk["tz"])
        sig = None
        for h in hits:
            sig = s.scalar(select(Signal).where(Signal.security_id == sec.id, Signal.strategy == h.strategy, Signal.session_date == sd))
            if sig is None:
                sig = Signal(security_id=sec.id, run_id=run.id, strategy=h.strategy, session_date=sd, price=q.price)
                s.add(sig)
            sig.price, sig.daily_change_pct, sig.five_day_change_pct = q.price, f.daily_change_pct, f.five_day_change_pct
            sig.details = {"reasons": h.reasons, **h.details}
        s.flush()
        prev = s.scalar(select(Analysis).where(Analysis.security_id == sec.id).order_by(Analysis.created_at.desc()).limit(1))
        if prev is not None and (now - prev.created_at.replace(tzinfo=timezone.utc)) < RESEARCH_TTL:
            continue  # recently researched; avoid hammering providers every 15 minutes
        try:
            a = research(s, st, provider, sec, q, f, idx, hits, sig, now)
            alert_for_analysis(s, st, sec, prev, a, now=now)
        except Exception:
            log.exception("research failed", extra={"extra_fields": {"symbol": sym}})
            run.failed += 1

    run.status = "ok" if run.failed == 0 else "failed" if run.scanned == 0 else "partial"
    run.finished_at = datetime.now(timezone.utc)
    if run.scanned == 0 or (syms and run.failed / len(syms) > 0.5):
        system_alert(s, st, f"scan:{market}", f"{market} scan degraded: {run.failed}/{len(syms)} symbols failed ({stale} stale quotes). Results may be incomplete.", now=now)
    log.info("scan done", extra={"extra_fields": {"market": market, "scanned": run.scanned, "failed": run.failed, "candidates": run.candidates}})
    return run
