"""REST API consumed by the dashboard. Every route except /health requires the bearer token."""
import hmac
import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.runtime import EDITABLE, effective_settings
from app.database.models import Alert, Analysis, AuditLog, BacktestResult, NewsArticle, ProviderHealth, ScannerRun, Security, Signal, StrategyConfig, WatchlistItem
from app.database.session import session_scope
from app.market_data.calendars import market_status
from app.market_data.symbols import MARKETS, to_yahoo

log = logging.getLogger("api")
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app = FastAPI(title="Opportunity Radar", docs_url=None, redoc_url=None, openapi_url=None)  # no public schema
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_st = get_settings()
setup_logging(_st.log_level)
if _st.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=_st.cors_origins, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])


def auth(authorization: str = Header(default="")) -> str:
    token = get_settings().api_token
    if not token:
        raise HTTPException(503, "API token not configured")
    given = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given.encode(), token.encode()):
        raise HTTPException(401, "invalid token")
    return "dashboard"


def db():
    with session_scope() as s:
        yield s


def _audit(s, actor: str, action: str, detail: dict) -> None:
    s.add(AuditLog(actor=actor, action=action, detail=detail))


def _latest_analyses(s, since: timedelta = timedelta(days=7)):
    sub = select(Analysis.security_id, func.max(Analysis.created_at).label("m")).where(
        Analysis.created_at >= datetime.now(timezone.utc) - since).group_by(Analysis.security_id).subquery()
    return s.scalars(select(Analysis).join(sub, (Analysis.security_id == sub.c.security_id) & (Analysis.created_at == sub.c.m))).all()


def _row(a: Analysis) -> dict:
    f, sec = a.report["facts"], a.security
    return {"symbol": sec.symbol, "name": sec.name, "exchange": sec.exchange, "currency": sec.currency, "price": f["price"],
            "daily_change_pct": f["daily_change_pct"], "five_day_change_pct": f.get("five_day_change_pct"),
            "quality_score": a.quality_score, "quality_confidence": a.quality_confidence, "opportunity_score": a.opportunity_score,
            "risk_level": a.risk_level, "classification": a.classification, "incomplete": a.incomplete,
            "analyzed_at": a.created_at.isoformat(), "quote_ts": f["quote_ts"], "strategies": [x["name"] for x in f["strategies"]]}


@app.get("/health")
def health():
    try:
        with session_scope() as s:
            s.execute(text("select 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(503, "database unavailable")


@app.get("/api/overview")
def overview(s=Depends(db), _=Depends(auth)):
    rows = _latest_analyses(s, timedelta(days=1))
    runs = {}
    for mk in MARKETS:
        r = s.scalar(select(ScannerRun).where(ScannerRun.market == mk).order_by(ScannerRun.started_at.desc()).limit(1))
        runs[mk] = {**market_status(mk), "last_run": None if r is None else {"at": r.started_at.isoformat(), "status": r.status, "scanned": r.scanned, "failed": r.failed, "candidates": r.candidates}}
    top = sorted((a for a in rows if a.classification == "GREEN"), key=lambda a: -(a.opportunity_score or 0))[:10]
    alerts = s.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(10)).all()
    prov = s.scalars(select(ProviderHealth)).all()
    return {"markets": runs, "active_opportunities": sum(a.classification == "GREEN" for a in rows), "top": [_row(a) for a in top],
            "alerts": [{"at": a.created_at.isoformat(), "kind": a.kind, "status": a.status, "severity": a.severity, "message": a.message[:200]} for a in alerts],
            "providers": [{"provider": p.provider, "last_success": p.last_success and p.last_success.isoformat(), "last_error": p.last_error,
                           "consecutive_failures": p.consecutive_failures} for p in prov]}


@app.get("/api/opportunities")
def opportunities(classification: str | None = None, days: int = 7, s=Depends(db), _=Depends(auth)):
    rows = _latest_analyses(s, timedelta(days=min(max(days, 1), 90)))
    if classification:
        rows = [a for a in rows if a.classification == classification.upper()]
    return sorted((_row(a) for a in rows), key=lambda r: -(r["opportunity_score"] or -1))


@app.get("/api/companies/{symbol}")
def company(symbol: str, s=Depends(db), _=Depends(auth)):
    sec = s.scalar(select(Security).where(Security.symbol == symbol.upper()))
    if not sec:
        raise HTTPException(404, "unknown symbol")
    hist = s.scalars(select(Analysis).where(Analysis.security_id == sec.id).order_by(Analysis.created_at.desc()).limit(30)).all()
    sigs = s.scalars(select(Signal).where(Signal.security_id == sec.id).order_by(Signal.detected_at.desc()).limit(50)).all()
    news = s.scalars(select(NewsArticle).where(NewsArticle.security_id == sec.id).order_by(NewsArticle.retrieved_ts.desc()).limit(15)).all()
    return {"security": {"symbol": sec.symbol, "name": sec.name, "exchange": sec.exchange, "currency": sec.currency, "sector": sec.sector},
            "latest": None if not hist else {"id": hist[0].id, "created_at": hist[0].created_at.isoformat(), **_row(hist[0]), "factors": hist[0].factors, "report": hist[0].report},
            "history": [{"at": a.created_at.isoformat(), "classification": a.classification, "quality": a.quality_score, "opportunity": a.opportunity_score} for a in hist],
            "signals": [{"at": g.detected_at.isoformat(), "strategy": g.strategy, "price": g.price, "daily_change_pct": g.daily_change_pct, "details": g.details} for g in sigs],
            "news": [{"title": n.title, "url": n.url, "publisher": n.publisher, "ts": n.source_ts and n.source_ts.isoformat(), "sentiment": n.sentiment, "model": n.sentiment_model} for n in news]}


@app.get("/api/companies/{symbol}/prices")
def prices(symbol: str, days: int = 365, _=Depends(auth)):
    from app.market_data.yahoo import YahooProvider
    try:
        bars = YahooProvider().history(symbol.upper(), min(max(days, 5), 2000))
    except Exception:
        raise HTTPException(502, "price provider unavailable")
    return {"source": "yahoo", "adjusted": True, "bars": [{"t": b.ts.date().isoformat(), "c": round(b.close, 4), "v": b.volume} for b in bars]}


class WatchIn(BaseModel):
    symbol: str
    market: str
    alerts_enabled: bool = True


@app.get("/api/watchlist")
def watchlist(s=Depends(db), _=Depends(auth)):
    return [{"symbol": w.security.symbol, "name": w.security.name, "market": w.security.market, "alerts_enabled": w.alerts_enabled} for w in s.scalars(select(WatchlistItem))]


@app.post("/api/watchlist", status_code=201)
def watch_add(body: WatchIn, s=Depends(db), actor=Depends(auth)):
    if body.market not in MARKETS:
        raise HTTPException(422, "market must be SE or US")
    try:
        sym = to_yahoo(body.symbol, body.market)
    except ValueError as e:
        raise HTTPException(422, str(e))
    sec = s.scalar(select(Security).where(Security.symbol == sym))
    if not sec:
        mk = MARKETS[body.market]
        sec = Security(symbol=sym, name=sym, market=body.market, exchange=mk["exchange"], currency=mk["currency"])
        s.add(sec)
        s.flush()
    w = s.scalar(select(WatchlistItem).where(WatchlistItem.security_id == sec.id))
    if w:
        w.alerts_enabled = body.alerts_enabled
    else:
        s.add(WatchlistItem(security_id=sec.id, alerts_enabled=body.alerts_enabled))
    _audit(s, actor, "watchlist.add", {"symbol": sym})
    return {"symbol": sym}


@app.delete("/api/watchlist/{symbol}", status_code=204)
def watch_del(symbol: str, s=Depends(db), actor=Depends(auth)):
    sec = s.scalar(select(Security).where(Security.symbol == symbol.upper()))
    w = sec and s.scalar(select(WatchlistItem).where(WatchlistItem.security_id == sec.id))
    if not w:
        raise HTTPException(404, "not on watchlist")
    s.delete(w)
    _audit(s, actor, "watchlist.remove", {"symbol": symbol})


@app.get("/api/settings")
def get_settings_api(s=Depends(db), _=Depends(auth)):
    eff = effective_settings(s)
    return {k: getattr(eff, k).model_dump() for k in EDITABLE}


@app.put("/api/settings/{key}")
def put_settings(key: str, body: dict, s=Depends(db), actor=Depends(auth)):
    if key not in EDITABLE:
        raise HTTPException(404, "unknown settings group")
    cur = getattr(get_settings(), key)
    try:
        merged = type(cur).model_validate({**effective_settings(s).__getattribute__(key).model_dump(), **body})
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))
    row = s.get(StrategyConfig, key)
    if row:
        row.value = merged.model_dump()
    else:
        s.add(StrategyConfig(key=key, value=merged.model_dump()))
    _audit(s, actor, "settings.update", {"key": key, "changes": body})
    return merged.model_dump()


@app.get("/api/runs")
def runs(s=Depends(db), _=Depends(auth)):
    return [{"market": r.market, "at": r.started_at.isoformat(), "status": r.status, "scanned": r.scanned, "failed": r.failed, "candidates": r.candidates, "error": r.error}
            for r in s.scalars(select(ScannerRun).order_by(ScannerRun.started_at.desc()).limit(50))]


@app.get("/api/alerts")
def alerts(s=Depends(db), _=Depends(auth)):
    return [{"at": a.created_at.isoformat(), "kind": a.kind, "severity": a.severity, "status": a.status, "attempts": a.attempts, "error": a.last_error, "message": a.message}
            for a in s.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(100))]


@app.get("/api/performance")
def performance(s=Depends(db), _=Depends(auth)):
    from app.backtesting.paper import paper_report
    return paper_report(s)


@app.get("/api/backtests")
def backtests(s=Depends(db), _=Depends(auth)):
    return [{"id": b.id, "at": b.created_at.isoformat(), "kind": b.kind, "params": b.params, "result": b.result}
            for b in s.scalars(select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(20))]
