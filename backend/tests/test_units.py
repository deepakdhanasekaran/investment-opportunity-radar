import pytest

from app.core.config import Classification, ScanRules, ScoreWeights
from app.fundamentals.quality import score_quality
from app.market_data.base import Fundamentals
from app.market_data.calendars import is_open
from app.market_data.symbols import to_yahoo
from app.risk.rules import evaluate, risk_level
from app.scanner.features import compute
from app.scoring.classify import classify
from app.scoring.opportunity import OpportunityResult
from app.sentiment.analyzer import lexicon_score
from app.strategies.detect import run_all
from app.universe.loader import load
from datetime import datetime, timezone
from tests.fakes import GOOD, NOW, make_bars
from app.market_data.base import Quote

W = ScoreWeights()


@pytest.mark.parametrize("raw,exp", [("VOLV B", "VOLV-B.ST"), ("volv-b.st", "VOLV-B.ST"), ("HM.B", "HM-B.ST"), ("ERIC-B", "ERIC-B.ST"), ("EQT", "EQT.ST")])
def test_se_normalization(raw, exp):
    assert to_yahoo(raw, "SE") == exp


def test_us_and_invalid():
    assert to_yahoo("brk.b", "US") == "BRK-B"
    for bad in ("", "VOLV!", "A B C D"):
        with pytest.raises(ValueError):
            to_yahoo(bad, "SE")


def test_calendars_holidays_and_dst():
    # Stockholm opens 09:00 local: CET (UTC+1) in November, CEST (UTC+2) in July
    assert is_open("SE", datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc))
    assert not is_open("SE", datetime(2026, 11, 3, 7, 30, tzinfo=timezone.utc))
    assert is_open("SE", datetime(2026, 7, 7, 7, 0, tzinfo=timezone.utc))
    assert not is_open("SE", datetime(2026, 7, 7, 6, 30, tzinfo=timezone.utc))
    # US: 14:35 UTC open in Nov (EST, 09:35); in July (EDT) the same UTC time is 10:35 -> open; 13:00 UTC July = 09:00 EDT closed
    assert is_open("US", datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc))
    assert not is_open("US", datetime(2026, 7, 7, 13, 0, tzinfo=timezone.utc))
    assert is_open("US", datetime(2026, 7, 7, 14, 0, tzinfo=timezone.utc))
    # Christmas Eve: Stockholm closed, weekend closed
    assert not is_open("SE", datetime(2026, 12, 24, 11, 0, tzinfo=timezone.utc))
    assert not is_open("US", datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc))


def test_universes_load_and_normalize():
    se = load("omxs30")
    assert len(se) >= 25 and all(m.symbol.endswith(".ST") for m in se)
    assert len(load("sp500")) > 400


def _feat(prev, last):
    q = Quote("X", last, "SEK", NOW, NOW, "fake", 5_000_000)
    return compute(make_bars(prev), q, "Europe/Stockholm")


def test_strategies_trigger_on_drop_not_on_flat():
    f = _feat(100, 95.5)  # -4.5%
    assert round(f.daily_change_pct, 1) == -4.5
    names = {h.strategy for h in run_all(f, None, ScanRules())}
    assert "strong_company_pullback" in names
    assert run_all(_feat(100, 99.5), None, ScanRules()) == []


def test_market_overreaction_needs_index_selloff():
    f, idx = _feat(100, 95), _feat(1000, 985)  # stock -5, index -1.5
    assert "market_overreaction" in {h.strategy for h in run_all(f, idx, ScanRules())}
    calm = _feat(1000, 999)
    assert "market_overreaction" not in {h.strategy for h in run_all(f, calm, ScanRules())}


def test_today_bar_not_used_as_prev_close():
    bars = make_bars(100)
    from app.market_data.base import Bar
    bars.append(Bar(NOW.replace(hour=9), 90, 90, 90, 90, 1))  # partial bar for today
    q = Quote("X", 95, "SEK", NOW, NOW, "fake", 1)
    assert compute(bars, q, "Europe/Stockholm").prev_close == pytest.approx(100)


def test_quality_missing_data_lowers_confidence_not_inflates():
    full = score_quality(Fundamentals("X", "t", NOW, "Industrials", metrics=dict(GOOD)), W.quality)
    sparse = score_quality(Fundamentals("X", "t", NOW, "Industrials", metrics={"profit_margin": 0.14, "operating_margin": 0.18}), W.quality)
    empty = score_quality(Fundamentals("X", "t", NOW, "Industrials", metrics={}), W.quality)
    assert full.confidence == 1.0 and full.score > 75
    assert sparse.confidence < 0.4 and sparse.score < full.score
    assert empty.score is None and empty.confidence == 0 and len(empty.missing) == 8


def test_financials_not_judged_on_industrial_metrics():
    m = {"revenue_growth": 0.08, "earnings_growth": 0.1, "roe": 0.14, "profit_margin": 0.3, "earnings_stability": 1.0,
         "debt_to_equity": 9.0, "current_ratio": 0.2}  # absurd for industrials, normal for a bank
    q = score_quality(Fundamentals("SEB-A.ST", "t", NOW, "Financial Services", metrics=m), W.quality)
    assert q.sector_class == "financial" and q.confidence == 1.0 and q.score > 60
    assert "debt" not in q.components
    assert not [f for f in evaluate(Fundamentals("S", "t", NOW, "Financial Services", metrics=m), 100, [], 20, -4, False, False, 1.0)
                if f.code in ("excessive_leverage", "liquidity_stress")]


def test_risk_flags_and_levels():
    bad = Fundamentals("X", "t", NOW, "Industrials", metrics={**GOOD, "debt_to_equity": 5.0, "earnings_growth": -0.6})
    fl = evaluate(bad, 100, ["Company files for bankruptcy protection"], 20, -5, False, False, 1.0)
    codes = {f.code for f in fl}
    assert {"excessive_leverage", "earnings_deterioration", "negative_news_critical"} <= codes
    assert risk_level(fl, False) == "CRITICAL"
    assert risk_level([], True) == "UNKNOWN" and risk_level([], False) == "LOW"
    assert any(f.code == "implausible_move" for f in evaluate(None, 100, [], None, -55, False, False, 0))


def _q(score=80, conf=1.0):
    from app.fundamentals.quality import QualityResult
    return QualityResult(score, conf, "industrial")


def test_classification_rules():
    cfg, o = Classification(), OpportunityResult(75, 0.8)
    assert classify(_q(), o, [], cfg).classification == "GREEN"
    from app.risk.rules import Flag
    assert classify(_q(), o, [Flag("x", "CRITICAL", "t")], cfg).classification == "RED"
    assert classify(_q(), o, [Flag("x", "REVIEW", "t")], cfg).classification == "YELLOW"
    assert classify(_q(30), o, [], cfg).classification == "RED"
    assert classify(_q(80, 0.5), o, [], cfg).classification == "YELLOW"  # low confidence cannot be GREEN
    v = classify(None, o, [], cfg)  # missing fundamentals: never GREEN, never RED by itself
    assert v.classification == "YELLOW" and v.incomplete
    assert classify(_q(), o, [], cfg, quote_ok=False).classification == "YELLOW"
    assert classify(_q(), OpportunityResult(40, 0.8), [], cfg).classification == "YELLOW"


def test_lexicon_sentiment():
    assert lexicon_score("Company issues profit warning, shares plunge") < 0
    assert lexicon_score("Record profit, analysts upgrade") > 0
    assert lexicon_score("Annual meeting scheduled") == 0
