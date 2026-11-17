"""Optional current news context. Never imported by historical feature construction."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
from contextlib import closing
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import unquote, urlsplit, urlunsplit
from uuid import UUID

from ..exceptions import DataError


def _publication(value: object, collected: datetime) -> dict:
    fields = {"published_at_utc": None, "published_date": None, "publication_status": "missing"}
    if value is None or value == "":
        return fields
    fields["publication_status"] = "invalid"
    if not isinstance(value, str) or len(value) > 64:
        return fields
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            day = date.fromisoformat(value)
            if day > collected.date():
                return {**fields, "publication_status": "future"}
            return {**fields, "published_date": day.isoformat(), "publication_status": "provider_date"}
        if re.match(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ]", value):
            if not re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}"
                r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
                value,
            ):
                return fields
            stamp = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        else:
            if not re.search(r" (?:GMT|UTC|[+-](?:[01][0-9]|2[0-3])[0-5][0-9])$", value):
                return fields
            stamp = parsedate_to_datetime(value)
        if stamp.utcoffset() is None:
            return fields
        utc_stamp = stamp.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return fields
    if utc_stamp > collected:
        return {**fields, "publication_status": "future"}
    return {
        "published_at_utc": utc_stamp.isoformat(), "published_date": utc_stamp.date().isoformat(),
        "publication_status": "provider_timestamp",
    }


def _headline(item: dict, key: str) -> dict | None:
    title, url = item.get("title"), item.get("url")
    if not isinstance(title, str) or not isinstance(url, str):
        return None
    title = " ".join("".join(char for char in title if char.isprintable() or char.isspace()).split())
    if not title or any(char in url for char in "<>\\") or any(
        char.isspace() or not char.isprintable() for char in url
    ):
        return None
    decoded = [unescape(unquote(value)) for value in (title, url)]
    if any(
        (key and key in value) or re.search(r"\btvly-[A-Za-z0-9_-]{12,}", value) for value in decoded
    ):
        return None
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        if (
            parsed.scheme != "https" or not re.fullmatch(r"[a-z0-9.-]+", hostname)
            or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443)
        ):
            return None
    except ValueError:
        return None
    return {"title": title[:180], "url": urlunsplit(("https", hostname, parsed.path or "/", "", ""))}


def _search_request(ticker: str) -> dict:
    return {
        "query": f"{ticker} stock company earnings and market news",
        "topic": "news", "time_range": "week", "search_depth": "basic",
        "max_results": 3, "include_published_date": True,
        "filter_by_published_date": True,
    }


def _request_id(value: object, key: str) -> str | None:
    try:
        return str(UUID(value)) if isinstance(value, str) and (not key or key not in value) else None
    except ValueError:
        return None


def validate_news_context(context: dict, ticker: str) -> dict:
    """Normalize a local capture without promoting provider estimates into feature evidence."""
    error = DataError("Invalid Tavily context for this ticker")
    if (
        not isinstance(context, dict) or context.get("source") != "Tavily"
        or context.get("ticker") != ticker or context.get("historical_features_eligible") is not False
        or context.get("request") != _search_request(ticker)
    ):
        raise error
    digest, count, articles = (
        context.get("response_sha256"), context.get("response_result_count"), context.get("articles"),
    )
    if (
        not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
        or type(count) is not int or not isinstance(articles, list) or not 0 <= len(articles) <= min(count, 3)
    ):
        raise error
    value = context.get("collected_at_utc")
    try:
        if not isinstance(value, str):
            raise ValueError
        collected = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if collected.utcoffset() is None or collected > datetime.now(timezone.utc):
            raise ValueError
        collected = collected.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise error from None

    key = os.environ.get("TAVILY_API_KEY", "").strip()
    headlines, normalized, seen = [], [], set()
    for article in articles:
        headline = _headline(article, key) if isinstance(article, dict) else None
        if headline is None or headline["url"] in seen:
            raise error
        seen.add(headline["url"])
        stamp, day, status = (
            article.get("published_at_utc"), article.get("published_date"), article.get("publication_status"),
        )
        publication = {"published_at_utc": stamp, "published_date": day, "publication_status": status}
        if status in ("provider_date", "provider_timestamp"):
            if _publication(stamp or day, collected) != publication:
                raise error
        elif status not in ("missing", "invalid", "future") or stamp is not None or day is not None:
            raise error
        headlines.append(headline)
        normalized.append({**headline, **publication})
    return {
        "source": "Tavily", "ticker": ticker, "collected_at_utc": collected.isoformat(),
        "historical_features_eligible": False, "request": _search_request(ticker),
        "request_id": _request_id(context.get("request_id"), key),
        "response_sha256": digest, "response_result_count": count, "headlines": headlines,
        "articles": normalized,
    }


def fetch_news_context(ticker: str, *, receipt: dict | None = None) -> dict:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise DataError("TAVILY_API_KEY is required for optional current news")
    request = _search_request(ticker)
    try:
        with closing(http.client.HTTPSConnection("api.tavily.com", timeout=20)) as client:
            if receipt is not None:
                receipt["executed_at_utc"] = datetime.now(timezone.utc).isoformat()
            client.request("POST", "/search", json.dumps(request), {
                "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            })
            response = client.getresponse()
            if receipt is not None:
                receipt["http_status"] = response.status
            if response.status != 200:
                raise DataError(f"Tavily returned HTTP {response.status}")
            raw = response.read()
            collected = datetime.now(timezone.utc)
            if receipt is not None:
                receipt["response_sha256"] = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw)
            result = payload["results"]
    except (OSError, http.client.HTTPException, KeyError, ValueError, TypeError, RecursionError):
        raise DataError("Tavily request failed") from None

    if not isinstance(result, list):
        raise DataError("Tavily returned malformed news results")
    headlines, articles, seen = [], [], set()
    for item in result:
        if not isinstance(item, dict):
            continue
        headline = _headline(item, key)
        if headline is None or headline["url"] in seen:
            continue
        seen.add(headline["url"])
        headlines.append(headline)
        articles.append({**headline, **_publication(item.get("published_date"), collected)})
        if len(headlines) == request["max_results"]:
            break
    return {
        "source": "Tavily", "ticker": ticker, "collected_at_utc": collected.isoformat(),
        "historical_features_eligible": False, "request": request, "request_id": _request_id(payload.get("request_id"), key),
        "response_sha256": hashlib.sha256(raw).hexdigest(), "response_result_count": len(result),
        "headlines": headlines, "articles": articles,
    }
