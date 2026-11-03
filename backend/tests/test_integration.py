from datetime import timedelta

import httpx
import pytest
import respx
from sqlalchemy import select

from app.database.models import Alert, Analysis, PriceObservation, ProviderHealth, Security, Signal
from app.notifications.alerts import decide, send_alert
from app.notifications.format import format_opportunity
from app.scanner.scan import run_scan
from tests.fakes import GOOD, NOW, FakeProvider

SE = {"VOLV-B.ST": (100.0, 95.0), "ERIC-B.ST": (100.0, 99.8), "^OMX": (1000.0, 985.0)}  # VOLV -5%, index -1.5%


@pytest.fixture
def tg():
    with respx.mock(assert_all_called=False) as m:
        yield m.post(url__regex=r"https://api\.telegram\.org/bot.*/sendMessage").mock(return_value=httpx.Response(200, json={"ok": True}))


def test_scan_detects_persists_classifies_and_alerts(db, settings, tg, watch):
    run = run_scan(db, settings, FakeProvider(SE), "SE", NOW)
    assert run.status in ("ok", "partial") and run.candidates == 1 and run.scanned >= 1
    sig = db.scalars(select(Signal)).all()
    assert {s.strategy for s in sig} >= {"strong_company_pullback", "market_overreaction"}
    a = db.scalars(select(Analysis)).one()
    assert a.classification == "GREEN" and a.risk_level == "LOW" and a.quality_confidence == 1.0
    assert a.report["facts"]["quote_source"] == "fake" and a.report["facts"]["quote_ts"]
    assert a.factors["verdict"]["rules"] and "risk_flags" in a.factors
    assert db.scalars(select(PriceObservation)).one().source == "fake"
    assert tg.call_count == 1
    al = db.scalars(select(Alert)).one()
    assert al.status == "sent" and al.kind == "new" and "INVESTMENT OPPORTUNITY" in al.message


def test_repeat_scan_is_idempotent_and_does_not_realert(db, settings, tg, watch):
    p = FakeProvider(SE)
    run_scan(db, settings, p, "SE", NOW)
    run_scan(db, settings, p, "SE", NOW + timedelta(minutes=15))
    assert len(db.scalars(select(Signal)).all()) == len(set((s.strategy) for s in db.scalars(select(Signal))))  # one per strategy/day
    assert len(db.scalars(select(Analysis)).all()) == 1  # research TTL
    assert tg.call_count == 1
    assert len(db.scalars(select(PriceObservation)).all()) == 2 or len(db.scalars(select(PriceObservation)).all()) == 1


def test_stale_quotes_never_used(db, settings, tg, watch):
    run = run_scan(db, settings, FakeProvider(SE, age_min=90), "SE", NOW)
    assert run.candidates == 0 and run.scanned == 0 and run.status == "failed"
    assert not db.scalars(select(Analysis)).all()
    assert any(a.kind == "system" for a in db.scalars(select(Alert)))  # operator is told


def test_missing_fundamentals_gives_incomplete_yellow_never_green(db, settings, tg, watch):
    p = FakeProvider(SE)
    p.metrics = None
    run_scan(db, settings, p, "SE", NOW)
    a = db.scalars(select(Analysis)).one()
    assert a.classification == "YELLOW" and a.incomplete and a.quality_score is None
    assert any("incomplete" in u.lower() or "unavailable" in u.lower() for u in a.report["uncertainties"])
    assert tg.call_count == 0  # YELLOW from nothing does not notify


def test_provider_outage_marks_run_failed_and_escalates(db, settings, tg, watch):
    p = FakeProvider(SE, fail=True)
    for i in range(3):
        r = run_scan(db, settings, p, "SE", NOW + timedelta(minutes=15 * i))
    assert r.status == "failed"
    h = db.scalars(select(ProviderHealth)).one()
    assert h.consecutive_failures == 3 and h.last_error
    assert not db.scalars(select(Analysis)).all()
    assert any(a.kind == "system" and a.status == "sent" for a in db.scalars(select(Alert)))


def test_bad_company_rejected_red(db, settings, tg, watch):
    p = FakeProvider(SE, metrics={**GOOD, "debt_to_equity": 6.0, "profit_margin": -0.1, "earnings_growth": -0.7})
    run_scan(db, settings, p, "SE", NOW)
    a = db.scalars(select(Analysis)).one()
    assert a.classification == "RED" and a.risk_level == "CRITICAL"
    assert tg.call_count == 0


def _analysis(cls, opp=70, risk="LOW"):
    return Analysis(classification=cls, opportunity_score=opp, risk_level=risk)


def test_decide_transitions():
    assert decide(None, _analysis("GREEN"), 10) == "new"
    assert decide(_analysis("GREEN"), _analysis("GREEN", 72), 10) is None
    assert decide(_analysis("GREEN"), _analysis("GREEN", 85), 10) == "change"
    assert decide(_analysis("GREEN"), _analysis("GREEN", 70, "HIGH"), 10) == "change"
    assert decide(_analysis("GREEN"), _analysis("RED"), 10) == "invalidated"
    assert decide(_analysis("YELLOW"), _analysis("YELLOW"), 10) is None


def test_cooldown_daily_cap_and_retry(db, settings, tg):
    s = settings
    a1 = send_alert(db, s, kind="new", severity="info", dedupe_key="k1", text="x", now=NOW)
    a2 = send_alert(db, s, kind="new", severity="info", dedupe_key="k1", text="x", now=NOW + timedelta(hours=1))
    a3 = send_alert(db, s, kind="new", severity="info", dedupe_key="k1", text="x", now=NOW + timedelta(hours=25))
    assert (a1.status, a2.status, a2.last_error, a3.status) == ("sent", "suppressed", "cooldown", "sent")
    s2 = s.model_copy(update={"alerts": s.alerts.model_copy(update={"max_per_day": 2})})
    for i in range(3):
        last = send_alert(db, s2, kind="new", severity="info", dedupe_key=f"d{i}", text="x", now=NOW + timedelta(hours=30))
    assert last.status == "suppressed" and last.last_error == "daily limit"
    crit = send_alert(db, s2, kind="system", severity="critical", dedupe_key="sys", text="x", now=NOW + timedelta(hours=30))
    assert crit.status == "sent"  # system alerts bypass the daily cap


def test_delivery_retries_then_logs_failure(db, settings):
    calls = []
    with respx.mock() as m:
        m.post(url__regex=r".*telegram.*").mock(side_effect=lambda r: (calls.append(1), httpx.Response(500))[1])
        a = send_alert(db, settings, kind="new", severity="info", dedupe_key="r", text="x", now=NOW, sleep=lambda _: None)
    assert a.status == "failed" and a.attempts == 3 and len(calls) == 3 and "HTTPStatusError" in a.last_error
    assert "t/sendMessage" not in (a.last_error or "")  # bot token never logged


def test_no_channel_configured_is_logged_not_silent(db, settings):
    s = settings.model_copy(update={"telegram_bot_token": ""})
    a = send_alert(db, s, kind="new", severity="info", dedupe_key="n", text="x", now=NOW)
    assert a.status == "failed" and "no notification channel" in a.last_error


def test_notification_content_and_banned_claims(db, settings, tg, watch):
    run_scan(db, settings, FakeProvider(SE), "SE", NOW)
    a = db.scalars(select(Analysis)).one()
    sec = db.get(Security, a.security_id)
    t = format_opportunity(a, sec, "https://dash")
    for must in ("Quality Score", "Opportunity Score", "GREEN - Worth Investigating", "source: fake", "https://dash/company/VOLV-B.ST", "not investment advice"):
        assert must in t
    assert not any(w in t.lower() for w in ("guaranteed", "safe investment", "risk-free", "sure thing"))
