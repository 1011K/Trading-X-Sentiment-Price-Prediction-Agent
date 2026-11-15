"""
News headline connector (practical free/cheap path).

Options:
  1. NewsAPI.org free tier (100 req/day) — set NEWSAPI_KEY
  2. Finnhub free tier
  3. Fallback: empty (sentiment features zero)

This is intentionally simple and documented for CV honesty.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import List, Optional

import pandas as pd

from ..logging_utils import get_logger

log = get_logger(__name__)


def fetch_news_headlines(
    ticker: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    max_items: int = 200,
) -> pd.DataFrame:
    """
    Returns DataFrame with columns: published_at, title, source, url.
    Empty if no key or API fails (pipeline continues with zero news signal).
    """
    key = os.environ.get("NEWSAPI_KEY") or os.environ.get("NEWS_API_KEY")
    if not key:
        log.warning("NEWSAPI_KEY not set — news connector returns empty")
        return pd.DataFrame(columns=["published_at", "title", "source", "url", "ticker"])

    try:
        import requests
    except ImportError:
        log.warning("requests not installed — news connector disabled")
        return pd.DataFrame(columns=["published_at", "title", "source", "url", "ticker"])

    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=30)

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": ticker,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(max_items, 100),
        "apiKey": key,
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        articles = r.json().get("articles", [])
    except Exception as exc:
        log.warning("NewsAPI request failed: %s", exc)
        return pd.DataFrame(columns=["published_at", "title", "source", "url", "ticker"])

    rows = []
    for a in articles:
        pub = a.get("publishedAt")
        if not pub:
            continue
        rows.append(
            {
                "published_at": pd.to_datetime(pub, utc=True),
                "title": a.get("title") or "",
                "source": (a.get("source") or {}).get("name"),
                "url": a.get("url"),
                "ticker": ticker,
            }
        )
    df = pd.DataFrame(rows)
    log.info("Fetched %d news headlines for %s", len(df), ticker)
    return df
