"""Headline retrieval: Google News RSS (query = company name + ticker). Headlines are retrieval-only evidence;
publisher and link are kept so every claim can be traced. No official regulatory feeds (see docs/data-providers.md)."""
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from time import mktime
from urllib.parse import quote_plus

import feedparser
import httpx

log = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    url: str
    publisher: str
    source_ts: datetime | None

    @property
    def url_hash(self) -> str:
        return hashlib.sha1(self.url.encode()).hexdigest()


def fetch_news(name: str, symbol: str, market: str, limit: int = 10, client: httpx.Client | None = None) -> list[Article]:
    q = quote_plus(f'"{name}" stock' if name else symbol)
    hl = "sv&gl=SE&ceid=SE:sv" if market == "SE" else "en-US&gl=US&ceid=US:en"
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}"
    try:
        r = (client or httpx).get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "opportunity-radar/0.1"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise RuntimeError(f"news fetch failed: {e}") from e
    out = []
    for e in feedparser.parse(r.text).entries[:limit]:
        ts = datetime.fromtimestamp(mktime(e.published_parsed), timezone.utc) if getattr(e, "published_parsed", None) else None
        out.append(Article(e.title, e.link, (getattr(e, "source", None) or {}).get("title", ""), ts))
    return out
