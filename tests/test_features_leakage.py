"""Feature-level leakage and red-team tests."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from cwt_quant.calendar import XNYSCalendar, ET
from cwt_quant.config import Config
from cwt_quant.features import build_post_features, lexical_sentiment


def test_lexical_neutral_celebrity():
    # Reach alone must not create positive score
    text = "Just commenting on $AAPL. Neutral."
    assert lexical_sentiment(text) == 0.0


def test_cashtag_gate():
    cfg = Config()
    cal = XNYSCalendar()
    posts = pd.DataFrame(
        [
            {
                "post_id": 1,
                "created_at": datetime(2026, 11, 16, 12, 0, tzinfo=ET),
                "author": "x",
                "followers": 100,
                "text": "I like apple fruit",
                "has_cashtag": False,
                "likes": 10,
                "reposts": 0,
                "comments": 0,
                "engagement_asof": datetime(2026, 11, 16, 12, 5, tzinfo=ET),
                "reply_sentiment": None,
                "reply_asof": None,
            },
            {
                "post_id": 2,
                "created_at": datetime(2026, 11, 16, 12, 0, tzinfo=ET),
                "author": "y",
                "followers": 100,
                "text": "$AAPL looks fine",
                "has_cashtag": True,
                "likes": 10,
                "reposts": 0,
                "comments": 0,
                "engagement_asof": datetime(2026, 11, 16, 12, 5, tzinfo=ET),
                "reply_sentiment": None,
                "reply_asof": None,
            },
        ]
    )
    prices = pd.DataFrame({"session_date": [date(2026, 11, 16)]})
    feat = build_post_features(posts, prices, cfg, cal)
    assert len(feat) == 1
    assert feat.iloc[0]["post_id"] == 2


def test_future_engagement_excluded():
    cfg = Config()
    cal = XNYSCalendar()
    sess = date(2026, 11, 16)
    close = cal.session_close_dt(sess)
    posts = pd.DataFrame(
        [
            {
                "post_id": 10,
                "created_at": datetime(2026, 11, 16, 10, 0, tzinfo=ET),
                "author": "z",
                "followers": 50000,
                "text": "$AAPL bullish",
                "has_cashtag": True,
                "likes": 1000,
                "reposts": 200,
                "comments": 50,
                "engagement_asof": close + timedelta(minutes=5),  # AFTER close
                "reply_sentiment": None,
                "reply_asof": None,
            }
        ]
    )
    prices = pd.DataFrame({"session_date": [sess]})
    feat = build_post_features(posts, prices, cfg, cal)
    assert len(feat) == 1
    assert bool(feat.iloc[0]["influence_valid"]) is False
    # weight should be neutral (1.0)
    assert float(feat.iloc[0]["weight"]) == 1.0
