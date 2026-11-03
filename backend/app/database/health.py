from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ProviderHealth


def record(s: Session, provider: str, ok: bool, error: str | None = None) -> ProviderHealth:
    h = s.scalar(select(ProviderHealth).where(ProviderHealth.provider == provider))
    if h is None:
        h = ProviderHealth(provider=provider, consecutive_failures=0, successes=0, failures=0)
        s.add(h)
    now = datetime.now(timezone.utc)
    if ok:
        h.last_success, h.consecutive_failures, h.successes = now, 0, (h.successes or 0) + 1
    else:
        h.last_failure, h.last_error = now, (error or "")[:500]
        h.consecutive_failures, h.failures = (h.consecutive_failures or 0) + 1, (h.failures or 0) + 1
    s.flush()
    return h
