"""Scheduler process: one interval job per market. Jobs are no-ops while the exchange is closed."""
import logging
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.runtime import effective_settings
from app.database.session import session_scope
from app.market_data.calendars import is_open
from app.market_data.yahoo import YahooProvider
from app.notifications.alerts import system_alert
from app.scanner.scan import run_scan

log = logging.getLogger("scheduler")
HEARTBEAT = Path("/tmp/scheduler.heartbeat")


def scan_job(market: str, provider=None, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    if not is_open(market, now):
        log.debug("market closed, skipping", extra={"extra_fields": {"market": market}})
        return None
    try:
        with session_scope() as s:
            return run_scan(s, effective_settings(s), provider or YahooProvider(), market, now)
    except Exception as e:
        log.exception("scan job crashed")
        try:
            with session_scope() as s:
                system_alert(s, effective_settings(s), f"job:{market}", f"{market} scan job crashed: {type(e).__name__}: {e}")
        except Exception:
            log.exception("could not send crash alert")
        return None


def paper_job(provider=None):
    from app.backtesting.paper import evaluate
    try:
        with session_scope() as s:
            evaluate(s, provider or YahooProvider())
    except Exception:
        log.exception("paper evaluation failed")


def heartbeat() -> None:
    HEARTBEAT.write_text(datetime.now(timezone.utc).isoformat())


def build() -> BlockingScheduler:
    st = get_settings()
    sch = BlockingScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300})
    for mk in st.scan.markets:
        # offset SE/US a little so the two never start in the same second
        sch.add_job(scan_job, "interval", minutes=st.scan.interval_minutes, args=[mk], id=f"scan-{mk}", next_run_time=datetime.now(timezone.utc))
    sch.add_job(paper_job, "cron", hour=22, minute=30, id="paper-eval")  # after both markets have closed
    sch.add_job(heartbeat, "interval", seconds=30, id="heartbeat", next_run_time=datetime.now(timezone.utc))
    return sch


def main() -> None:
    st = get_settings()
    setup_logging(st.log_level)
    sch = build()
    stop = threading.Event()

    def _term(*_):  # graceful: let the running scan finish, then exit
        log.info("shutdown requested")
        threading.Thread(target=lambda: sch.shutdown(wait=True), daemon=True).start()
        stop.set()

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    log.info("scheduler starting", extra={"extra_fields": {"markets": st.scan.markets, "interval": st.scan.interval_minutes}})
    sch.start()


if __name__ == "__main__":
    main()
