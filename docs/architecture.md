# Architecture
One Python package (`backend/app`), one image, two long-running processes (`api`, `scheduler`) plus Postgres. The scanner never imports the dashboard; the dashboard only reads the API.

| Module | Role |
|---|---|
| `market_data` | `Quote`/`Bar`/`Fundamentals` types, Yahoo provider (retry, batch), symbol normalisation (`VOLV B`→`VOLV-B.ST`), `exchange_calendars` (holidays, DST, early closes) |
| `universe` | CSV universes + watchlist, de-duplicated |
| `scanner` | `features` (pure price maths), `scan` (stage 1, batched, price-only), `research` (stage 2, per candidate) |
| `strategies` | A pullback in quality company, B market overreaction, D technical pullback; C valuation opportunity is evaluated in `research` (needs fundamentals) |
| `fundamentals`, `valuation`, `risk`, `scoring` | Quality score, valuation vs own history, risk flags, opportunity score, deterministic classification |
| `news`, `sentiment` | Google News RSS headlines; lexicon or FinBERT |
| `notifications` | Decision (new/change/invalidated), cooldown, daily cap, retries, delivery log, Telegram/ntfy |
| `backtesting` | Historical engine + paper-trading evaluation |
| `scheduling` | APScheduler (`max_instances=1`, `coalesce`), market-open gate, heartbeat, SIGTERM drain |
| `api` | FastAPI, bearer auth, rate limit, audit log |

## Flow of one scan
1. Gate: market open per calendar (else no-op, nothing recorded).
2. Batch-fetch daily history and last 1-minute quotes for the universe + index. Provider failure ⇒ run `failed`, health recorded, system alert after 3 consecutive failures.
3. Reject quotes older than `max_quote_age_minutes`; compute features (today's partial daily bar is excluded from "previous close").
4. Strategies produce hits → candidates (capped, ranked by sharper of daily / half 5-day move).
5. Per candidate: upsert `Signal` (unique per security/strategy/day), store the quote as a `PriceObservation` (source_ts and retrieved_ts separate), run research unless analysed in the last 60 min.
6. Alert decision vs previous analysis; dedupe key + cooldown + daily cap; delivery attempts logged.

## Data model
`securities, price_observations, fundamental_snapshots, news_articles, scanner_runs, signals, analyses (factors+report JSON = audit trail), alerts, watchlist, provider_health, strategy_configs (dashboard overrides), backtest_results, audit_log`. Exchange info is denormalised on `securities` (two markets; a table would be speculative). Only candidates' quotes are persisted (all 500 every 15 min would be ~5M rows/year of little value). Migrations: Alembic (`0001`), verified on Postgres.

## Config
Defaults + env (`RADAR_*`, nested `__`) are overlaid at each job start with dashboard edits from `strategy_configs` (scan, weights, cls, alerts only; secrets are never editable).
