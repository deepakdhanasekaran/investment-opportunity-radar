import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import ScanRules, Settings
from app.database.models import Base


@pytest.fixture
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    s = sessionmaker(eng, expire_on_commit=False)()
    yield s
    s.close()


@pytest.fixture
def settings():
    return Settings(news_enabled=False, telegram_bot_token="t", telegram_chat_id="c", api_token="secret", database_url="sqlite://",
                    scan=ScanRules(se_universe=[], us_universe=[]))


@pytest.fixture
def watch(db):
    """Put the fake symbols on the watchlist: they form the whole universe in integration tests."""
    from app.database.models import Security, WatchlistItem
    for sym in ("VOLV-B.ST", "ERIC-B.ST"):
        sec = Security(symbol=sym, name=sym.split(".")[0], market="SE", exchange="Nasdaq Stockholm", currency="SEK")
        db.add(sec)
        db.flush()
        db.add(WatchlistItem(security_id=sec.id))
    db.flush()
