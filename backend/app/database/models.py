"""Schema. Source timestamps (`source_ts`) and retrieval timestamps (`retrieved_ts`) are kept separately.
Uniqueness constraints make repeated scans idempotent. Exchange data is denormalised onto Security
(two markets only; a separate table would be speculative)."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Security(Base):
    __tablename__ = "securities"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), unique=True, index=True)  # Yahoo-style
    name: Mapped[str] = mapped_column(String(200), default="")
    market: Mapped[str] = mapped_column(String(4))  # SE | US
    exchange: Mapped[str] = mapped_column(String(40), default="")
    currency: Mapped[str] = mapped_column(String(4), default="")
    sector: Mapped[str] = mapped_column(String(80), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (UniqueConstraint("security_id", "source", "source_ts"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(4), default="")
    source: Mapped[str] = mapped_column(String(20))
    source_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieved_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshots"
    __table_args__ = (UniqueConstraint("security_id", "source", "snapshot_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    snapshot_date: Mapped[date] = mapped_column(Date)
    retrieved_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sector: Mapped[str | None] = mapped_column(String(80))
    metrics: Mapped[dict] = mapped_column(JSON)


class NewsArticle(Base):
    __tablename__ = "news_articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)
    url_hash: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(120), default="")
    source_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sentiment: Mapped[float | None] = mapped_column(Float)  # -1..1
    sentiment_model: Mapped[str | None] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint("security_id", "url_hash"),)


class ScannerRun(Base):
    __tablename__ = "scanner_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    market: Mapped[str] = mapped_column(String(4))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="running")  # running|ok|partial|failed|skipped
    scanned: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    candidates: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Signal(Base):
    """Candidate detected by a strategy. One per (security, strategy, trading day)."""
    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("security_id", "strategy", "session_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("scanner_runs.id"))
    strategy: Mapped[str] = mapped_column(String(40))
    session_date: Mapped[date] = mapped_column(Date)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    price: Mapped[float] = mapped_column(Float)
    daily_change_pct: Mapped[float | None] = mapped_column(Float)
    five_day_change_pct: Mapped[float | None] = mapped_column(Float)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    security: Mapped[Security] = relationship()


class Analysis(Base):
    """Deterministic assessment. `factors` stores every input behind the classification (audit trail)."""
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    quality_score: Mapped[float | None] = mapped_column(Float)
    quality_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_score: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(12))  # LOW|MODERATE|HIGH|CRITICAL|UNKNOWN
    classification: Mapped[str] = mapped_column(String(8))  # GREEN|YELLOW|RED
    incomplete: Mapped[bool] = mapped_column(Boolean, default=False)
    factors: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict] = mapped_column(JSON)
    security: Mapped[Security] = relationship()


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int | None] = mapped_column(ForeignKey("securities.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # new|change|invalidated|system
    severity: Mapped[str] = mapped_column(String(10), default="info")
    dedupe_key: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|sent|failed|suppressed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(String(12))


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), unique=True)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    security: Mapped[Security] = relationship()


class ProviderHealth(Base):
    __tablename__ = "provider_health"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), unique=True)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)


class StrategyConfig(Base):
    """Runtime overrides of env defaults (edited from the dashboard). key e.g. 'scan', 'weights'."""
    __tablename__ = "strategy_configs"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(20))  # historical|paper
    params: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
