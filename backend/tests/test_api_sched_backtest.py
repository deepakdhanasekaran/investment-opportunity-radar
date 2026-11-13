from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backtesting.engine import generate_trades, report, summarize
from app.core.config import ScanRules
from app.database.models import Analysis, AuditLog, Base
from app.market_data.base import Bar
from tests.fakes import NOW, FakeProvider


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("RADAR_API_TOKEN", "secret")
    from app.core import config
    from app.database import session
    config.get_settings.cache_clear()
    session._factory.cache_clear()
    from sqlalchemy import create_engine
    Base.metadata.create_all(create_engine(f"sqlite:///{tmp_path}/t.db"))
    from app.api.main import app
    app.state.limiter.reset()
    yield TestClient(app)
    config.get_settings.cache_clear()
    session._factory.cache_clear()


H = {"Authorization": "Bearer secret"}


def test_health_open_everything_else_needs_token(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/overview").status_code == 401
    assert client.get("/api/overview", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/overview", headers=H).status_code == 200
    assert client.get("/openapi.json").status_code == 404


def test_api_refuses_when_token_unset(client, monkeypatch):
    from app.core import config
    monkeypatch.setenv("RADAR_API_TOKEN", "")
    config.get_settings.cache_clear()
    assert client.get("/api/overview", headers=H).status_code == 503


def test_watchlist_crud_validation_and_audit(client):
    assert client.post("/api/watchlist", json={"symbol": "volv b", "market": "SE"}, headers=H).json() == {"symbol": "VOLV-B.ST"}
    assert client.post("/api/watchlist", json={"symbol": "bad sym!", "market": "SE"}, headers=H).status_code == 422
    assert client.post("/api/watchlist", json={"symbol": "AAPL", "market": "XX"}, headers=H).status_code == 422
    assert [w["symbol"] for w in client.get("/api/watchlist", headers=H).json()] == ["VOLV-B.ST"]
    assert client.delete("/api/watchlist/VOLV-B.ST", headers=H).status_code == 204
    assert client.delete("/api/watchlist/VOLV-B.ST", headers=H).status_code == 404
    from app.database.session import session_scope
    with session_scope() as s:
        assert {a.action for a in s.scalars(select(AuditLog))} == {"watchlist.add", "watchlist.remove"}


def test_settings_validation_and_persistence(client):
    r = client.put("/api/settings/scan", json={"daily_drop_pct": 4.5}, headers=H)
    assert r.status_code == 200 and r.json()["daily_drop_pct"] == 4.5
    assert client.get("/api/settings", headers=H).json()["scan"]["daily_drop_pct"] == 4.5
    assert client.put("/api/settings/scan", json={"daily_drop_pct": "abc"}, headers=H).status_code == 422
    assert client.put("/api/settings/database_url", json={"x": 1}, headers=H).status_code == 404  # secrets not editable


def test_opportunities_and_company_detail(client, settings, db):
    # run a scan against the API's own DB
    from app.database.session import session_scope
    from app.database.models import Security, WatchlistItem
    from app.scanner.scan import run_scan
    import respx
    import httpx
    with session_scope() as s:
        sec = Security(symbol="VOLV-B.ST", name="Volvo", market="SE", exchange="Nasdaq Stockholm", currency="SEK")
        s.add(sec); s.flush(); s.add(WatchlistItem(security_id=sec.id))
        with respx.mock() as m:
            m.post(url__regex=r".*telegram.*").mock(return_value=httpx.Response(200))
            run_scan(s, settings, FakeProvider({"VOLV-B.ST": (100.0, 95.0), "^OMX": (1000.0, 985.0)}), "SE", NOW)
    # NOW in fakes is fixed; created_at uses 'now' param => fix up so the 7-day window includes it
    with session_scope() as s:
        for a in s.scalars(select(Analysis)):
            a.created_at = datetime.now(timezone.utc)
    rows = client.get("/api/opportunities", headers=H).json()
    assert rows and rows[0]["symbol"] == "VOLV-B.ST" and rows[0]["classification"] in ("GREEN", "YELLOW")
    assert client.get("/api/opportunities?classification=red", headers=H).json() == []
    d = client.get("/api/companies/VOLV-B.ST", headers=H).json()
    assert d["latest"]["factors"]["verdict"]["rules"] and d["signals"] and d["latest"]["report"]["facts"]["quote_source"] == "fake"
    assert client.get("/api/companies/NOPE", headers=H).status_code == 404
    assert client.get("/api/overview", headers=H).json()["markets"]["SE"]["last_run"] is not None


def test_scheduler_skips_closed_market_and_runs_open(monkeypatch):
    from app.scheduling import scheduler
    called = []
    monkeypatch.setattr(scheduler, "run_scan", lambda *a, **k: called.append(a[3]) or "run")
    monkeypatch.setattr(scheduler, "session_scope", lambda: __import__("contextlib").nullcontext(None))
    monkeypatch.setattr(scheduler, "effective_settings", lambda s: None)
    sat = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
    assert scheduler.scan_job("SE", object(), sat) is None and scheduler.scan_job("US", object(), sat) is None
    assert scheduler.scan_job("SE", object(), datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)) == "run"
    assert scheduler.scan_job("US", object(), datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)) is None  # 07:00 EST: closed
    assert called == ["SE"]


def test_scheduler_builds_one_job_per_market_no_overlap():
    from app.scheduling import scheduler
    sch = scheduler.build()
    ids = {j.id: j for j in sch.get_jobs()}
    assert {"scan-SE", "scan-US", "heartbeat"} <= set(ids)
    assert sch._job_defaults["max_instances"] == 1 and sch._job_defaults["coalesce"]


def _series(n=700, pattern=None):
    d0 = datetime(2022, 1, 3, tzinfo=timezone.utc)
    out, p = [], 100.0
    for i in range(n):
        p *= 1.0006 * (0.95 if i in (300, 450) else 1.0)  # two sharp drops in an uptrend
        out.append(Bar(d0 + timedelta(days=i), p, p, p, p, 1e6))
    return out


def test_backtest_no_lookahead_costs_and_splits():
    bars = _series()
    trades = generate_trades({"X": bars}, _series(), "Europe/Stockholm", ScanRules(), cost_bps=10)
    assert trades
    t = next(t for t in trades if t.holding == 5)
    ei = next(i for i, b in enumerate(bars) if b.ts == t.entry_date)
    # entry is strictly after the signal bar: signal date = entry date - 1 day; return uses entry OPEN, not signal close
    xi = next(i for i, b in enumerate(bars) if b.ts == t.exit_date)
    assert xi - ei == 5 and t.ret == pytest.approx(bars[xi].close / bars[ei].open - 1 - 0.002)
    rep = report(trades)
    assert rep["in_sample"] and rep["out_of_sample"] and any("Survivorship" in w for w in rep["warnings"])
    assert any("point-in-time" in w for w in rep["warnings"])
    s5 = summarize(trades, 5)
    assert s5["signals"] > 0 and 0 <= s5["win_rate"] <= 1 and s5["max_drawdown_sequenced"] <= 0


def test_portfolio_caps_positions_and_matches_hand_calc():
    from app.backtesting.engine import Trade, _curve_stats, portfolio
    d = [datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(4)]
    uni = {"A": [Bar(t, 100, 100, 100, c, 1) for t, c in zip(d, (100, 100, 110, 110))],
           "B": [Bar(t, 100, 100, 100, 100, 1) for t in d]}
    mk = lambda sym, ret, score: Trade(sym, "s", d[1], d[2], ret, None, 1, "hi20", "signal", 100.0, None, score)  # noqa: E731
    r = portfolio([mk("A", 0.10, -5), mk("B", 0.0, -1)], uni, [], "hi20", slots=1)
    # one slot: only the sharper drop (A) is taken with all capital; B is skipped
    assert r["trades"] == 1 and r["skipped_signals"] == 1 and r["strategy"]["total_return"] == pytest.approx(0.10)
    r2 = portfolio([mk("A", 0.10, -5), mk("B", 0.0, -1)], uni, [], "hi20", slots=2)
    assert r2["trades"] == 2 and r2["strategy"]["total_return"] == pytest.approx(0.05)  # half the capital in each
    assert r2["universe_equal_weight"]["total_return"] == pytest.approx(0.05)
    st = _curve_stats([(d[0], 1.0), (d[1], 1.2), (d[2], 0.9), (d[3], 1.0)])
    assert st["max_drawdown"] == pytest.approx(-0.25) and st["by_year"] == {"2024": pytest.approx(0.0)}
    rep = report(generate_trades({"X": _series()}, _series(), "Europe/Stockholm", ScanRules()), universe={"X": _series()}, index_bars=_series())
    assert rep["portfolio"]["hi20"]["all"]["trades"] > 0 and "mean_excess_vs_universe" in rep["exit_rules"]["hi20"]["all"]


def test_backtest_empty_is_labelled():
    assert report([])["signals"] == 0


def test_paper_evaluation_measures_outcomes_vs_benchmark(db):
    from app.backtesting.paper import evaluate, paper_report
    from app.database.models import Security
    sec = Security(symbol="VOLV-B.ST", name="V", market="SE", exchange="x", currency="SEK")
    db.add(sec); db.flush()
    t0 = NOW - timedelta(days=100)
    db.add(Analysis(security_id=sec.id, classification="GREEN", risk_level="LOW", created_at=t0, factors={},
                    report={"facts": {"price": 100.0, "strategies": [{"name": "strong_company_pullback"}]}}))
    db.add(Analysis(security_id=sec.id, classification="YELLOW", risk_level="LOW", created_at=t0, factors={}, report={"facts": {"price": 1, "strategies": []}}))
    db.flush()
    r = evaluate(db, FakeProvider({"VOLV-B.ST": (100.0, 100.0), "^OMX": (1000.0, 1000.0)}), NOW)
    assert r["tracked_green"] == 1  # YELLOW is not tracked
    assert {"5", "20", "60"} <= set(r["by_holding"]) and "120" not in r["by_holding"]  # not enough elapsed days for 120
    assert "false_positive_rate" in r["by_holding"]["20"] and paper_report(db)["tracked_green"] == 1


def test_exit_rules():
    from datetime import datetime, timedelta
    from app.backtesting.exits import simulate
    from app.market_data.base import Bar
    t0 = datetime(2024, 1, 1)
    def mk(cs):
        return [Bar(t0 + timedelta(days=i), c, c, c, c, 1) for i, c in enumerate(cs)]
    b = mk([100] * 30 + [90, 91, 95, 101])  # dip then recovery above prior 20d high
    assert simulate(b, 30, 90, "hi20") == (33, "signal")
    assert simulate(mk([100] * 30 + [90, 80]), 30, 90, "trail8") == (31, "signal")  # 80 <= 90*0.92
    assert simulate(mk([100] * 100), 30, 100, "trail8")[1] == "cap"
    assert simulate(mk([100] * 40), 30, 100, "trail8") == (None, "open")
