"""Alert decisions, dedupe, cooldown, daily cap, delivery logging."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import Alert, Analysis, Security
from app.notifications.channels import deliver
from app.notifications.format import format_invalidated, format_opportunity

log = logging.getLogger(__name__)
RISK_ORDER = {"LOW": 0, "MODERATE": 1, "UNKNOWN": 1, "HIGH": 2, "CRITICAL": 3}


def decide(prev: Analysis | None, new: Analysis, material_change: float) -> str | None:
    was_green = prev is not None and prev.classification == "GREEN"
    if new.classification == "GREEN" and not was_green:
        return "new"
    if was_green and new.classification != "GREEN":
        return "invalidated"
    if was_green and new.classification == "GREEN":
        d = abs((new.opportunity_score or 0) - (prev.opportunity_score or 0))
        if d >= material_change or RISK_ORDER[new.risk_level] > RISK_ORDER[prev.risk_level]:
            return "change"
    return None


def _recent_sent(s: Session, since: datetime, **filters):
    q = select(func.count()).select_from(Alert).where(Alert.created_at >= since, Alert.status.in_(("sent", "pending")))
    for k, v in filters.items():
        q = q.where(getattr(Alert, k) == v)
    return s.scalar(q) or 0


def send_alert(s: Session, st: Settings, *, kind: str, severity: str, dedupe_key: str, text: str,
               security_id: int | None = None, now: datetime | None = None, sleep=None, client=None) -> Alert:
    now = now or datetime.now(timezone.utc)
    # counts are taken before the new row exists, otherwise it would count itself
    in_cooldown = _recent_sent(s, now - timedelta(hours=st.alerts.cooldown_hours), dedupe_key=dedupe_key) > 0
    over_cap = kind != "system" and _recent_sent(s, now - timedelta(hours=24)) >= st.alerts.max_per_day
    a = Alert(security_id=security_id, kind=kind, severity=severity, dedupe_key=dedupe_key, message=text, created_at=now)
    s.add(a)
    if in_cooldown or over_cap:
        a.status, a.last_error = "suppressed", "cooldown" if in_cooldown else "daily limit"
        s.flush()
        return a
    kw = {"sleep": sleep} if sleep else {}
    ok, attempts, err = deliver(st, text, severity, st.alerts.retries, client=client, **kw)
    a.attempts, a.channel = attempts, ",".join(ok) or None
    a.status, a.last_error = ("sent", None) if ok else ("failed", err)
    s.flush()
    return a


def alert_for_analysis(s: Session, st: Settings, sec: Security, prev: Analysis | None, new: Analysis, **kw) -> Alert | None:
    kind = decide(prev, new, st.alerts.material_score_change)
    if kind is None:
        return None
    text = (format_invalidated(new, sec, st.dashboard_url) if kind == "invalidated"
            else format_opportunity(new, sec, st.dashboard_url, "INVESTMENT OPPORTUNITY" if kind == "new" else "OPPORTUNITY UPDATE"))
    return send_alert(s, st, kind=kind, severity="info", dedupe_key=f"{kind}:{sec.symbol}:{new.classification}", text=text,
                      security_id=sec.id, **kw)


def system_alert(s: Session, st: Settings, key: str, message: str, **kw) -> Alert:
    return send_alert(s, st, kind="system", severity="critical", dedupe_key=f"system:{key}", text=f"SYSTEM ALERT\n\n{message}", **kw)
