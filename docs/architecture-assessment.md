# Architecture assessment (Phase 1)

Both repos were cloned (depth 50) and inspected on 2026-11-03. Claims below come from the code, not READMEs.

## balogun14/radar — MIT

| Item | Finding |
|---|---|
| Size | ~1,350 lines Python, 11 flat modules, 12 commits, single author, alpha (v0.5.0) |
| Stack | yfinance, feedparser, requests, Streamlit, torch+transformers (FinBERT) |
| Persistence | JSON state file + YAML config. No DB, no schema |
| Tests | **None** |
| Notifications | ntfy only (no Telegram) |
| Markets | US only (NASDAQ snapshot, Yahoo symbols). **No Swedish support**, no exchange calendars, no currency/time-zone handling |
| Quality / risk | None. "Discovery" is price/volume ranking; no fundamentals, scoring or classification |
| News | Google News RSS + CryptoPanic; FinBERT loaded lazily. Ticker-keyed, title-only |
| Security | Plain requests, no auth surface. `torch` makes images ~2 GB+ |

**Reusable:** the *idea* of Google-News-RSS + FinBERT title scoring (~60 lines), ntfy POST (~15 lines). Everything else is either US-only, single-process script glue or UI (Streamlit) that conflicts with the Next.js requirement.
**Decision:** do not vendor the code. Re-implement the two small pieces cleanly, with typing and tests, behind our own interfaces. MIT permits reuse; we keep attribution in `NOTICE` for the ideas used (`THIRD_PARTY.md`).

## Open-Dev-Society/OpenStock — AGPL-3.0

| Item | Finding |
|---|---|
| Stack | Next.js 15 / React 19, Tailwind 4, better-auth, Mongoose/MongoDB, Inngest, nodemailer |
| Data | **Finnhub** (free tier, US + crypto only) for quotes/alerts; **TradingView embeds** for charts; Yahoo only for Saudi. Its own `MARKET_SUPPORT.md` states non-US exchanges get no quotes/alerts |
| Sweden | **Not supported.** Nasdaq Stockholm is not in `lib/markets.ts`; TradingView embeds can't be fed our scoring data |
| DB | MongoDB (users, watchlist, alerts models only — 2 models). Our system of record is PostgreSQL |
| Tests | 8 vitest files (utils, yahoo, market clock, AI provider, alerts) — none cover anything we need |
| Auth | better-auth + cookie-presence middleware (the middleware only checks cookie *existence*; real validation is per-route) |
| Fit | A consumer-style stock app (marketing pages, SEO, sponsors, email onboarding, Inngest cloud jobs). Its domain model (watchlist/alert) doesn't contain scores, classifications, evidence or backtests |

**AGPL-3.0 implication:** copying/modifying OpenStock code and offering it over a network (even on a personal server, if others use it) requires publishing the combined source under AGPL. Mixing it with our code would force the whole dashboard under AGPL.
**Decision:** do **not** fork or copy OpenStock. Integration via adapter would mean running Mongo + Inngest + Finnhub keys purely to host two unrelated models, and still require writing every screen we need (opportunities, detail, scores, backtests) from scratch. Building a small Next.js dashboard (~6 pages) over our own FastAPI is simpler, license-clean, and keeps the scanner independent. We may borrow *ideas* (layout patterns) only.

## Architecture decision

* One Python 3.12 package (FastAPI API + APScheduler scheduler in the same codebase, run as separate Compose services from one image), PostgreSQL via SQLAlchemy + Alembic.
* Pluggable market-data provider interface; yfinance first. **Swedish intraday via Yahoo is delayed/unverified** → every quote carries timestamp + source + age, stale quotes are flagged and never used silently (see `docs/data-providers.md`).
* Small own Next.js + Tailwind dashboard in `frontend/dashboard` consuming the API with token auth.
* FinBERT is an optional extra (`pip install .[sentiment]`); a lexicon fallback keeps the system running without torch. Rule-based scoring is the sole decider of classification.

## Custom work required (everything material)

Universes, exchange calendars, Swedish ticker normalization, sector-aware scoring, strategies, risk rules, classification, alert dedupe/cooldown, Telegram, persistence, backtesting, dashboard, ops.

## Known risks

* yfinance is an unofficial scraper: rate limits, schema drift, no SLA, no point-in-time fundamentals (affects backtests; documented).
* Swedish fundamentals via Yahoo are patchy → confidence reduction rather than favourable defaults.
* Index membership lists are static seed files and must be refreshed manually.
