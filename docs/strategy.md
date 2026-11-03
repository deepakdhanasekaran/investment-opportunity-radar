# Strategy and scoring

## Candidate generation (configurable in Settings → scan)
| Strategy | Triggers when |
|---|---|
| A `strong_company_pullback` | daily ≤ −3% **or** 5-day ≤ −5% (volume ≥ 2× 20-day average is noted as support). Quality is confirmed in research |
| B `market_overreaction` | index ≤ −1% **and** stock at least 2 pp worse than the index |
| C `valuation_opportunity` | (research step) P/E ≤ 85% of the company's own median over available annual EPS (≥3 positive years) |
| D `technical_pullback` | SMA50 > SMA200 and price > SMA200, price within ±3% of SMA50, ≥5% below 20-day high |
Candidates are not buy signals. Every candidate goes through the same research and classification.

## Quality score (0–100, sector-aware)
Metrics: revenue growth, earnings growth, profitability, FCF margin, debt/equity, ROIC, earnings stability (share of profitable years), resilience (current ratio, cash/debt). Each maps linearly to 0–100 between fixed anchors; weights are in config (`weights.quality`).
* **Financials** (banks, insurers, asset managers, holding companies) use only growth, ROE/margin and stability. Leverage, FCF, ROIC and current ratio are *not applicable* and do not count against them. **Real estate** keeps debt but with looser anchors and no FCF.
* **Missing data**: metrics without data are excluded **and** reduce `confidence`; the displayed score is multiplied by `0.5 + 0.5·confidence`, so gaps never help.

## Opportunity score (0–100)
Weighted mean of: price decline depth, relative performance vs index, historical valuation, current valuation, earnings outlook (forward vs trailing P/E), volume, long-term trend health, market conditions, announcements, news sentiment. Components with no data are excluded and reported as missing (`coverage`). It ranks research interest; it is **not** a probability of gains.

## Risk rules (`risk/rules.py`)
`CRITICAL` forces RED: earnings growth ≤ −50%, debt/equity > 4 (industrials), loss-making + negative FCF + current ratio < 1, critical headline keywords (bankruptcy, going concern, fraud, restatement, delisting…).
`REVIEW` blocks GREEN: net loss, earnings −25%…−50%, D/E 2–4, current ratio < 0.8, thin liquidity, P/E > 60, volatility > 60%, recent split, >40% one-day move (possible data error), low data coverage, missing fundamentals, negative-news keywords (profit warning, guidance cut, investigation…).
Keyword rules are heuristics on headlines; they raise flags for review and prove nothing.

## Classification (`scoring/classify.py`, no AI input)
1. any CRITICAL → **RED**; 2. quality < 40 with ≥50% coverage → **RED**; 3. incomplete data (no quote/fundamentals/scores) → **YELLOW** at most; 4. **GREEN** only if quality ≥ 65, coverage ≥ 0.7, opportunity ≥ 60 and no REVIEW flags; else **YELLOW**.
All thresholds are configurable; the rule ids that fired and all component scores are stored in `analyses.factors`.

## Reports
`facts` (numbers with source/timestamps) are separate from `interpretation` (template text). The decline explanation is "unknown" unless a market-wide move or a flagged headline supports something, and says it is unverified.
