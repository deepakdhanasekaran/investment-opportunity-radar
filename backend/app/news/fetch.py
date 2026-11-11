"""Headline retrieval: Google News RSS (query = company name + ticker). Headlines are retrieval-only evidence;
publisher and link are kept so every claim can be traced. No official regulatory feeds (see docs/data-providers.md)."""
import hashlib
import logging
import time
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
    hl = {"SE": "sv&gl=SE&ceid=SE:sv", "IN": "en-IN&gl=IN&ceid=IN:en"}.get(market, "en-US&gl=US&ceid=US:en")
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}"
    err: Exception | None = None
    for attempt in range(3):  # retry transient network errors (e.g. TLS handshake timeouts)
        try:
            r = (client or httpx).get(url, timeout=httpx.Timeout(20, connect=10), follow_redirects=True, headers={"User-Agent": "opportunity-radar/0.1"})
            r.raise_for_status()
            break
        except httpx.HTTPError as e:
            err = e
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    else:
        raise RuntimeError(f"news fetch failed after 3 attempts: {err}") from err
    out = []
    for e in feedparser.parse(r.text).entries[:limit]:
        ts = datetime.fromtimestamp(mktime(e.published_parsed), timezone.utc) if getattr(e, "published_parsed", None) else None
        out.append(Article(e.title, e.link, (getattr(e, "source", None) or {}).get("title", ""), ts))
    return out
