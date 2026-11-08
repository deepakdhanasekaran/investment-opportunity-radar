# Investment Opportunity Radar

Self-hosted **decision-support** tool. It watches Swedish (OMXS30 + selected Large Cap) and US (S&P 500 + watchlist) stocks,
flags price declines in companies that pass quality screens, explains *why* with evidence, and sends an ntfy push notification for the few that matter.
**It never trades and holds no brokerage credentials.** Scores rank research candidates; they are not return forecasts.

```
Yahoo (yfinance) ─► scheduler (every 15 min, only while exchange open) ─► candidates (strategies A–D)
                                       └► research: fundamentals, valuation, news+sentiment, risk rules
                                           └► deterministic GREEN / YELLOW / RED  ─► Postgres ─► Telegram / ntfy
                                                                                          └► FastAPI ─► Next.js dashboard
```

## Quick start (Ubuntu or any Docker host)
```bash
cp .env.example .env      # set POSTGRES_PASSWORD, RADAR_API_TOKEN (openssl rand -hex 32), RADAR_NTFY_URL
docker compose up -d --build            # db + api (runs migrations) + scheduler
curl localhost:8000/health
docker compose --profile dashboard up -d --build   # optional dashboard on 127.0.0.1:4000 (remote access via Tailscale: docs/deployment.md)
```
Details: [docs/deployment.md](docs/deployment.md). Tests: `cd backend && pip install -e '.[dev]' && pytest`.

## Docs
[architecture-assessment](docs/architecture-assessment.md) · [architecture](docs/architecture.md) · [strategy](docs/strategy.md) ·
[data-providers](docs/data-providers.md) · [security](docs/security.md) · [deployment](docs/deployment.md)

## Status — what is and is not done
| Area | State |
|---|---|
| Scanner, calendars, universes, persistence, dedupe, ntfy (Telegram optional), Docker | **Working**; verified live against Yahoo (US scan of 502 symbols ran end-to-end in Docker + Postgres) |
| Quality / valuation / risk / classification / reports | **Working**, rule-based, unit-tested; sector-aware (financials, real estate, industrials) |
| FinBERT | Optional (`INSTALL_SENTIMENT=1` build arg). **Default is a keyword lexicon**, labelled as such in reports. FinBERT path is coded but **not exercised in tests/CI** |
| LLM research summaries | **Not implemented** (optional in spec). Reports are template-generated from verified numbers |
| Dashboard | Overview, opportunities, company detail, watchlist, settings, performance. Builds and type-checks; **not visually/browser-tested**. Charts are a plain SVG line, not TradingView. OpenStock was deliberately not reused (see assessment) |
| Backtesting | Price-only strategies, next-open entry, costs, in/out-of-sample, benchmark. **No point-in-time fundamentals, survivorship bias, no FX conversion by default** — see warnings in every result. Not run on a real multi-year sample yet |
| Swedish intraday freshness | **Unverified during a live Stockholm session** (tests were run after the close). Stale quotes are rejected by age rather than trusted. See data-providers.md |
| Monitoring | Healthchecks + Telegram system alerts + provider-health table. No Prometheus/Grafana |
| Index lists | Static CSVs; S&P 500 refreshed from Wikipedia by `scripts/refresh_universe.py`; Swedish lists hand-maintained and should be verified; Nasdaq-100 not seeded |
