"""All tunable thresholds live here. Override via env: RADAR_SCAN__DAILY_DROP_PCT=4 etc."""
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScanRules(BaseModel):
    daily_drop_pct: float = 3.0
    five_day_drop_pct: float = 5.0
    unusual_volume_ratio: float = 2.0  # today's volume / 20d avg
    underperf_vs_index_pct: float = 2.0  # stock daily % minus index daily %
    max_quote_age_minutes: dict[str, int] = {"US": 20, "SE": 20, "IN": 20}
    interval_minutes: int = 15
    markets: list[str] = ["SE", "US", "IN"]
    paper_stake: dict[str, float] = {"SE": 1000, "US": 100, "IN": 10000}  # amount invested per GREEN, in the market currency
    us_universe: list[str] = ["sp500"]  # sp500 | nasdaq100 (needs manual CSV) | watchlist
    se_universe: list[str] = ["omxs30", "largecap"]
    in_universe: list[str] = ["nifty100"]
    max_candidates_per_scan: int = 25
    market_selloff_pct: float = 1.0  # index daily drop that counts as a broad selloff
    pullback_sma_tol_pct: float = 3.0  # strategy D: price within this % above/below SMA50
    pullback_min_drawdown_pct: float = 5.0  # strategy D: drop from 20d high
    valuation_discount: float = 0.85  # strategy C: current P/E <= this * own historical median


class ScoreWeights(BaseModel):
    """Weights are relative; each score is normalised by the weights of metrics that had data."""
    quality: dict[str, float] = {
        "revenue_growth": 1.0, "earnings_growth": 1.0, "profitability": 1.5, "free_cash_flow": 1.0,
        "debt": 1.5, "roic": 1.0, "earnings_stability": 1.0, "resilience": 1.0,
    }
    opportunity: dict[str, float] = {
        "price_decline": 2.0, "relative_perf": 1.0, "hist_valuation": 1.5, "cur_valuation": 1.5,
        "earnings_outlook": 1.0, "volume": 0.5, "momentum": 0.5, "market_conditions": 0.5,
        "announcements": 0.5, "news_sentiment": 1.0,
    }


class Classification(BaseModel):
    green_min_quality: float = 65.0
    green_min_opportunity: float = 60.0
    green_min_confidence: float = 0.7  # share of quality weight that had real data
    red_max_quality: float = 40.0


class Alerts(BaseModel):
    cooldown_hours: int = 24
    max_per_day: int = 10
    material_score_change: float = 10.0
    retries: int = 3


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RADAR_", env_nested_delimiter="__", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./radar.db"  # compose sets a postgres+psycopg URL
    log_level: str = "INFO"
    api_token: str = Field(default="", description="Bearer token for the API; empty => API refuses to start serving data")
    cors_origins: list[str] = []
    dashboard_url: str = "http://localhost:4000"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    ntfy_url: str = ""  # topic URL, e.g. https://ntfy.sh/my-private-topic or https://ntfy.example.com/radar
    ntfy_token: str = ""  # bearer token for access-controlled / self-hosted ntfy (optional)
    news_enabled: bool = True
    sentiment_backend: str = "lexicon"  # lexicon | finbert
    scan: ScanRules = ScanRules()
    weights: ScoreWeights = ScoreWeights()
    cls: Classification = Classification()
    alerts: Alerts = Alerts()


@lru_cache
def get_settings() -> Settings:
    return Settings()
