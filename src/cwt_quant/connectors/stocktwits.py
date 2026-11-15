"""Free public StockTwits symbol stream (no API key required).

Endpoint: https://api.stocktwits.com/api/2/streams/symbol/{TICKER}.json
Returns recent messages (typically ~30) with optional user Bullish/Bearish tags.
Historical depth is limited; use for live / recent sentiment only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
import requests

from ..exceptions import DataError
from ..logging_utils import get_logger

log = get_logger(__name__)

_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_UA = "cwt-quant/0.2 (+research; leakage-safe daily pipeline)"


def fetch_stocktwits_messages(
    ticker: str,
    max_pages: int = 3,
    timeout: float = 12.0,
) -> pd.DataFrame:
    """
    Pull recent StockTwits messages for a ticker via the public stream.

    Returns a DataFrame compatible with the internal post schema:
        post_id, created_at, author, body, is_reply, likes, replies,
        sentiment_label, source
    """
    ticker = ticker.upper().strip()
    all_msgs: List[dict] = []
    cursor_max: Optional[int] = None

    for page in range(max_pages):
        params = {}
        if cursor_max is not None:
            params["max"] = cursor_max
        url = _API.format(ticker=ticker)
        try:
            r = requests.get(
                url,
                params=params,
                headers={"User-Agent": _UA, "Accept": "application/json"},
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            if page == 0:
                raise DataError(f"StockTwits public stream failed for {ticker}: {exc}") from exc
            log.warning("StockTwits page %d failed for %s: %s", page, ticker, exc)
            break

        messages = data.get("messages") or []
        if not messages:
            break
        all_msgs.extend(messages)

        # cursor for next older page
        cursor = data.get("cursor") or {}
        next_max = cursor.get("max")
        if next_max is None or next_max == cursor_max:
            break
        cursor_max = next_max

    if not all_msgs:
        log.warning("No StockTwits messages returned for %s", ticker)
        return _empty_posts_df()

    rows = []
    for m in all_msgs:
        created = m.get("created_at")
        try:
            # ISO with Z
            ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except Exception:
            continue

        entities = m.get("entities")
        if not isinstance(entities, dict):
            entities = {}
        sent = entities.get("sentiment")
        if not isinstance(sent, dict):
            sent = {}
        label = sent.get("basic")  # "Bullish" / "Bearish" / None

        user = m.get("user")
        if not isinstance(user, dict):
            user = {}
        likes_obj = m.get("likes")
        likes = (likes_obj.get("total", 0) if isinstance(likes_obj, dict) else 0) or 0
        disc = m.get("discussion")
        replies = (disc.get("replies", 0) if isinstance(disc, dict) else 0) or 0

        rows.append(
            {
                "post_id": str(m.get("id")),
                "created_at": ts,
                "author": str(user.get("username") or user.get("id") or "unknown"),
                "body": str(m.get("body") or "")[:2000],
                "is_reply": False,  # top-level stream items
                "likes": int(likes),
                "replies": int(replies),
                "sentiment_label": label,
                "source": "stocktwits_public",
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return _empty_posts_df()

    # Deduplicate by post_id
    df = df.drop_duplicates(subset=["post_id"], keep="first")
    df = df.sort_values("created_at").reset_index(drop=True)
    log.info(
        "StockTwits: %d unique messages for %s (latest %s)",
        len(df),
        ticker,
        df["created_at"].iloc[-1] if len(df) else "n/a",
    )
    return df


def _empty_posts_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "post_id",
            "created_at",
            "author",
            "body",
            "is_reply",
            "likes",
            "replies",
            "sentiment_label",
            "source",
        ]
    )


def label_to_score(label: Optional[str]) -> float:
    """Map StockTwits basic label to continuous score in [-1, 1]."""
    if not label:
        return 0.0
    l = str(label).lower()
    if l == "bullish":
        return 1.0
    if l == "bearish":
        return -1.0
    return 0.0
