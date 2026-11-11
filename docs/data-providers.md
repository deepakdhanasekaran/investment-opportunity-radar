# Data providers

| Need | Provider | Notes |
|---|---|---|
| Prices, 1m quotes, fundamentals, dividends/splits | Yahoo via `yfinance` | Unofficial, rate-limited, no SLA, schema can change without notice. Behind the `MarketDataProvider` interface so another source can replace it |
| News | Google News RSS | Headlines only; no full text; relevance is query-based and noisy |
| Calendars | `exchange_calendars` (XSTO, XNYS, XBOM) | Holidays, early closes, DST. India uses the BSE calendar (XBOM) because the library has no NSE calendar: same hours (09:15–15:30 IST), near-identical holidays |

## Verified vs unverified (2026-11-03)
* Verified live: US and Swedish 1-minute quotes, daily history, fundamentals (VOLV-B, SEB-A, AAPL), annual EPS, corporate actions all return data and the full US scan ran in Docker.
* **Not verified:** Swedish quote *latency during the session*. At test time Stockholm had closed (last 1-minute bar 17:29 CET = session close). The scanner therefore rejects any quote older than `max_quote_age_minutes` (20) rather than assuming freshness. **Action for you:** during a Stockholm session, check `Overview → last scan` for SE: if many symbols fail as stale, Yahoo is delayed for you; consider a paid feed behind the same interface. Delayed data is never relabelled as live; every quote stores `source_ts`, `retrieved_ts`, and source.
* Yahoo's price history is dividend/split adjusted (`auto_adjust`); the live quote is unadjusted. Rule `recent_split` flags names with a split in the last 7 days.
* Yahoo gives only ~4 annual statements: valuation "own history" uses ≤4 year-end P/Es and is marked unavailable below 3. Fundamentals are not point-in-time (affects backtests).
* Swedish fundamentals are sometimes sparse: this lowers confidence and prevents GREEN rather than defaulting to good scores.
* No official company-announcement feeds (e.g. Nasdaq Stockholm, SEC EDGAR) are integrated: "announcements" are headline-derived only.
* Failures: retry with backoff (3 tries), provider health table, consecutive failures ⇒ system alert, analysis marked incomplete (never silently filled).

## India (NSE) — added 2026-11-11
* Symbols are Yahoo `.NS` tickers; benchmark `^NSEI` (Nifty 50); currency INR; universe `nifty100` (`backend/app/universe/in_nifty100.csv`, 98 names, hand-compiled: re-check against NSE's published list occasionally).
* Verified: daily history for the universe and a price-only backtest ran. **Not verified:** live NSE quote latency during the session (same stale-quote gate of 20 min applies) and fundamentals coverage, which is likely sparser than US.
* News uses Google News `en-IN`; the English lexicon sentiment is used as is.
* Paper stake per GREEN: 10000 INR (`scan.paper_stake`).
