"""Independent red-team tests from 15 Nov 2026 CWT audit."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from cwt_quant.config import Config
from cwt_quant.calendar import XNYSCalendar, ET
from cwt_quant.features import build_post_features
from cwt_quant.data import _map_stocktwits_to_posts, _map_news_to_posts


def post(created, observed_at=None):
    p={"post_id": "test", "created_at": created, "author":"tester",
       "followers":1000, "text":"$TSLA bullish", "has_cashtag":True,
       "likes":100, "reposts":0, "comments":0,
       "engagement_asof":pd.NaT, "reply_sentiment":None, "reply_asof":None}
    if observed_at is not None:
        p["observed_at"] = observed_at
    return pd.DataFrame([p])


def test_weekend_post_not_clipped_back_into_friday():
    cfg=Config(ticker="TSLA"); cal=XNYSCalendar()
    prices=pd.DataFrame({"session_date":[date(2026,11,13)]})
    saturday=datetime(2026,11,14,12,0,tzinfo=ET)
    feat=build_post_features(post(saturday),prices,cfg,cal)
    assert feat.empty, "Saturday's post must not change Friday's closed sentiment"


def test_late_collected_post_not_backfilled_as_historical():
    cfg=Config(ticker="TSLA"); cal=XNYSCalendar()
    prices=pd.DataFrame({"session_date":[date(2026,11,13)]})
    early_friday=datetime(2026,11,13,12,0,tzinfo=ET)
    sunday=datetime(2026,11,15,12,0,tzinfo=ET)
    feat=build_post_features(post(early_friday,sunday),prices,cfg,cal)
    assert feat.empty, "Today's retrieval cannot establish yesterday's availability"


def test_stocktwits_unknown_follower_count_not_manufactured():
    data=pd.DataFrame([{"post_id":"42", "created_at":pd.Timestamp('2026-11-13T12:00:00Z'),
                      "author":"someone", "body":"$TSLA bullish", "likes":22,
                      "replies":3, "sentiment_label":"Bullish"}])
    mapped=_map_stocktwits_to_posts(data,'TSLA')
    assert pd.isna(mapped['followers'].iloc[0])
    assert pd.isna(mapped['engagement_asof'].iloc[0])
    assert mapped['observed_at'].iloc[0] > mapped['created_at'].iloc[0]


def test_news_not_fabricated_as_social_media_reach():
    news=pd.DataFrame([{"published_at":pd.Timestamp('2026-11-13T12:00:00Z'),
                       "title":"Tesla bulletin","source":"Publisher"}])
    mapped=_map_news_to_posts(news, 'TSLA')
    assert pd.isna(mapped['followers'].iloc[0])
    assert pd.isna(mapped['engagement_asof'].iloc[0])


def test_price_history_window_is_exact_calendar_days(monkeypatch):
    import sys
    from types import SimpleNamespace
    from datetime import timedelta
    from cwt_quant.connectors.prices import fetch_daily_ohlc
    captured = {}
    def fake_download(ticker, **kwargs):
        captured.update(kwargs)
        dates=pd.DatetimeIndex(['2026-11-12','2026-11-13'],name='Date')
        return pd.DataFrame({"Open":[100.,101.], "High":[102.,103.],
                             "Low":[99.,100.], "Close":[101.,102.],
                             "Volume":[1000,2000]}, index=dates)
    monkeypatch.setitem(sys.modules,"yfinance",SimpleNamespace(download=fake_download))
    end=date(2026,11,15)
    bars=fetch_daily_ohlc('TSLA',end=end,history_calendar_days=180)
    assert captured['start'] == (end - timedelta(days=179)).isoformat()
    assert captured['end'] == (end + timedelta(days=1)).isoformat()
    assert len(bars) == 2
