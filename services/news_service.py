from __future__ import annotations

from dataclasses import dataclass
from typing import List
import urllib.parse

import feedparser
import requests

from services.cache import cache


@dataclass
class NewsItem:
    title: str
    link: str
    published: str | None = None
    source: str | None = None


class RSSNewsService:
    """
    Uses Google News RSS.
    No API key. Generally reliable structure.

    Free-plan optimization:
    - Cache results briefly to reduce repeated network calls.
    """

    def __init__(self, timeout_s: int = 10):
        self.timeout_s = timeout_s

    def fetch(self, query: str, limit: int = 5) -> List[NewsItem]:
        query = query.strip()
        cache_key = f"news:{query}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        q = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-GB&gl=GB&ceid=GB:en"

        resp = requests.get(
            url,
            timeout=self.timeout_s,
            headers={"User-Agent": "StockPilot/1.0"},
        )
        resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        items: List[NewsItem] = []

        for e in feed.entries[:limit]:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            published = getattr(e, "published", None)

            source = None
            if hasattr(e, "source") and e.source:
                source = getattr(e.source, "title", None)

            if title and link:
                items.append(
                    NewsItem(title=title, link=link, published=published, source=source)
                )

        # Cache news for 15 minutes
        cache.set(cache_key, items, expire=60 * 15)
        return items


# PHASE 3 PLUG-IN POINT:
# - Add alternative feeds / providers (NewsAPI, GDELT, etc.)
# - Add caching + deduplication (store links seen per ticker)
# - Add company-name expansion (ticker -> company name) for better search quality