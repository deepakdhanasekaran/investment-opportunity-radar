"""Effective settings = env defaults overlaid with dashboard-edited overrides stored in strategy_configs."""
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.models import StrategyConfig

EDITABLE = ("scan", "weights", "cls", "alerts")


def effective_settings(s: Session) -> Settings:
    base = get_settings()
    upd = {}
    for row in s.scalars(select(StrategyConfig)):
        if row.key in EDITABLE:
            cur = getattr(base, row.key)
            try:
                upd[row.key] = type(cur).model_validate({**cur.model_dump(), **row.value})
            except ValidationError:
                continue  # ignore a corrupt override rather than stop scanning
    return base.model_copy(update=upd)
