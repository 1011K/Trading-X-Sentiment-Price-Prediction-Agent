"""Free daily crowd sentiment from CrowdWisdom Trading (same org as the assignment).

Uses the free PyPI package `crowdwisdomtrading`.
Daily call returns ProCrowdSentimentScore in roughly [-100, +100] and ProTraders count.
Free limit: 50 calls/day per IP. No key required.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd

from ..exceptions import DataError
from ..logging_utils import get_logger

log = get_logger(__name__)


def fetch_daily_crowd_score(ticker: str) -> dict:
    """
    Fetch today's free daily ProCrowdSentimentScore for ticker.
    Returns a dict with score, traders, as_of date, and raw payload.
    """
    ticker = ticker.upper().strip()
    try:
        from crowdwisdomtrading import Client
    except ImportError as exc:
        raise DataError(
            "crowdwisdomtrading package required. Install: pip install crowdwisdomtrading"
        ) from exc

    try:
        c = Client()
        payload = c.daily_sentiment(ticker)
    except Exception as exc:
        raise DataError(f"CrowdWisdomTrading daily_sentiment failed for {ticker}: {exc}") from exc

    data = payload.get("data") or {}
    score = data.get("ProCrowdSentimentScore")
    traders = data.get("ProTraders")
    as_of = data.get("date") or payload.get("as_of")

    log.info(
        "CWT free daily: %s score=%.1f traders=%s as_of=%s",
        ticker,
        float(score) if score is not None else float("nan"),
        traders,
        as_of,
    )
    return {
        "ticker": ticker,
        "score": float(score) if score is not None else None,
        "traders": int(traders) if traders is not None else None,
        "as_of": as_of,
        "raw": payload,
    }


def score_to_daily_feature(ticker: str, session_date: Optional[date] = None) -> pd.DataFrame:
    """Unavailable by design: a current aggregate must not be backdated.

    Use fetch_daily_crowd_score for observational, context-only reporting.
    To use this as a predictive feature, archive timestamped snapshots and
    validate availability against the actual market decision cutoff.
    """
    raise DataError("CWT score cannot be backfilled as a point-in-time historical feature")
