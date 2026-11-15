"""Error-path and validation tests."""

import pytest
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from cwt_quant.config import Config
from cwt_quant.exceptions import ConfigError, DataError
from cwt_quant.validation import validate_prices, validate_posts
from cwt_quant.calendar import XNYSCalendar, ET


def test_config_rejects_bad_weights():
    with pytest.raises(ConfigError):
        Config(post_weight=0.7, reply_weight=0.4).validate()


def test_config_rejects_skill_claim_without_real_data():
    with pytest.raises(ConfigError):
        Config(claim_predictive_skill=True, real_data_present=False).validate()


def test_empty_prices_raises():
    cfg = Config(fail_on_missing_sessions=False)
    cal = XNYSCalendar()
    with pytest.raises(DataError):
        validate_prices(pd.DataFrame(), cfg, cal)


def test_missing_price_columns_raises():
    cfg = Config()
    cal = XNYSCalendar()
    df = pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex([datetime(2026, 11, 16, 16, 0, tzinfo=ET)]))
    with pytest.raises(DataError):
        validate_prices(df, cfg, cal)


def test_negative_followers_raises():
    cfg = Config()
    posts = pd.DataFrame(
        {
            "post_id": [1],
            "created_at": [datetime(2026, 11, 16, 12, 0, tzinfo=ET)],
            "author": ["x"],
            "followers": [-5],
            "text": ["$AAPL"],
            "has_cashtag": [True],
            "likes": [0],
            "reposts": [0],
            "comments": [0],
            "engagement_asof": [datetime(2026, 11, 16, 12, 5, tzinfo=ET)],
        }
    )
    with pytest.raises(DataError):
        validate_posts(posts, cfg)
