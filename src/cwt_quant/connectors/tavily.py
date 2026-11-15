"""Optional current news context. Never imported by historical feature construction."""

from __future__ import annotations

import http.client
import json
import os
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from ..exceptions import DataError


def fetch_news_context(ticker: str) -> dict:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise DataError("TAVILY_API_KEY is required for optional current news")
    request = {
        "query": f"{ticker} stock company earnings and market news",
        "topic": "news", "time_range": "week", "search_depth": "basic",
        "max_results": 3, "include_published_date": True,
        "filter_by_published_date": True,
    }
    try:
        with closing(http.client.HTTPSConnection("api.tavily.com", timeout=20)) as client:
            client.request("POST", "/search", json.dumps(request), {
                "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            })
            response = client.getresponse()
            if response.status != 200:
                raise DataError(f"Tavily returned HTTP {response.status}")
            result = json.loads(response.read())["results"]
    except (OSError, http.client.HTTPException, KeyError, ValueError, TypeError):
        raise DataError("Tavily request failed") from None

    if not isinstance(result, list):
        raise DataError("Tavily returned malformed news results")
    headlines = []
    for item in result[:3]:
        if not isinstance(item, dict):
            continue
        title, url = item.get("title"), item.get("url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or any(char in url for char in "<>\r\n") or key in title or key in url):
            continue
        headlines.append({
            "title": " ".join(title.split())[:180],
            "url": urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")),
        })
    return {
        "source": "Tavily", "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "historical_features_eligible": False, "headlines": headlines,
    }
