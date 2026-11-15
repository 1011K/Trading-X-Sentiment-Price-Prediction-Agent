"""Additional regression tests: data integrity > convincing-looking metrics."""
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo
import ast
from pathlib import Path

import pandas as pd
import pytest

from cwt_quant.calendar import ET, XNYSCalendar
from cwt_quant.config import Config
from cwt_quant.features import build_post_features
from cwt_quant.models import get_feature_sets
from cwt_quant.data import generate_synthetic_prices, _empty_posts_schema
from cwt_quant.pipeline import run_pipeline


def _test_post(**kwargs):
    created = datetime(2026, 11, 13, 11, tzinfo=ET)
    defaults = dict(post_id='a', created_at=created, observed_at=created + timedelta(minutes=10),
                    author='test', followers=99999, followers_asof=created,
                    text='$TSLA bullish', has_cashtag=True, likes=400, reposts=40,
                    comments=10, engagement_asof=created+timedelta(minutes=12),
                    reply_sentiment=None, reply_asof=None, source='verified_x_archive')
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


def _feat(df):
    return build_post_features(df, pd.DataFrame({'session_date':[date(2026,11,13)]}),
                               Config(ticker='TSLA'), XNYSCalendar())


def test_external_missing_observed_at_is_withheld():
    assert _feat(_test_post(observed_at=pd.NaT)).empty


def test_external_record_observed_before_cutoff_allowed():
    f = _feat(_test_post())
    assert len(f)==1
    assert f['influence_valid'].iloc[0]
    assert f['weight'].iloc[0]>1


def test_unverified_follower_snapshot_cannot_get_influence_weight():
    f = _feat(_test_post(followers_asof=pd.NaT))
    assert not f['influence_valid'].iloc[0]
    assert f['weight'].iloc[0]==1


def test_post_close_follower_snapshot_cannot_get_influence_weight():
    f=_feat(_test_post(followers_asof=datetime(2026,11,13,16,2,tzinfo=ET)))
    assert not f['influence_valid'].iloc[0]
    assert f['weight'].iloc[0]==1


def test_naive_post_timestamp_rejected():
    assert _feat(_test_post(created_at=datetime(2026,11,13,11))).empty


def test_calendar_outside_verified_year_fails_closed():
    with pytest.raises(ValueError,match='not verified'):
        XNYSCalendar().is_trading_day(date(2027,1,4))


def test_nyse_july_2_2026_regular_close_not_bond_schedule():
    assert XNYSCalendar().session_close_time(date(2026,7,2)) == time(16,0)


def test_unavailable_sentiment_model_absent_from_realistic_pipeline(tmp_path, monkeypatch):
    import cwt_quant.pipeline as pipe
    cal = XNYSCalendar()
    prices=generate_synthetic_prices(Config(ticker='TSLA'),cal,n_sessions=130)
    def fake_load(cfg,force_synthetic):
        return prices,_empty_posts_schema(),{'mode':'real','real_data_present':True,
            'price_hash':'synthetic_price_fixture','posts_hash':'empty',
            'adjustment_policy':'test only','n_sessions':len(prices),'n_posts':0,'warnings':[]}
    monkeypatch.setattr(pipe,'load_or_generate',fake_load)
    res=run_pipeline(Config(ticker='TSLA',real_data_present=True,outputs_dir=tmp_path),
                     force_synthetic=False,out_dir=tmp_path)
    assert not res['sentiment_enabled']
    assert not res['influence_enabled']
    assert 'price_sentiment' not in res['predictions']
    assert set(res['predictions'])=={'no_change','price_only'}
    assert set(res['forward']['model'])=={'no_change','price_only'}


def test_python310_grammar_compatibility():
    root=Path(__file__).resolve().parents[1]
    for path in (root/'src').rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path),feature_version=(3,10))


def test_stocktwits_does_not_inject_fake_cashtag():
    from cwt_quant.data import _map_stocktwits_to_posts
    df=pd.DataFrame([{'post_id':'1','created_at':pd.Timestamp('2026-11-13T12:00:00Z'),
        'author':'test','body':'I love apples', 'likes':0,'replies':0,'sentiment_label':None}])
    mapped=_map_stocktwits_to_posts(df,'AAPL')
    assert mapped['text'].iloc[0] == 'I love apples'
    assert not bool(mapped['has_cashtag'].iloc[0])


def test_no_retroactive_conversion_of_cwt_daily_score():
    from cwt_quant.connectors.cwt_sentiment import score_to_daily_feature
    from cwt_quant.exceptions import DataError
    with pytest.raises(DataError, match='cannot be backfilled'):
        score_to_daily_feature('AAPL', date(2026,11,13))

def test_news_does_not_inject_fake_cashtag():
    from cwt_quant.data import _map_news_to_posts
    news = pd.DataFrame([{'published_at': pd.Timestamp('2026-11-13T12:00:00Z'),
                          'source': 'Example News', 'title': 'Fresh apple harvest reported'}])
    mapped = _map_news_to_posts(news, 'AAPL')
    assert mapped['text'].iloc[0] == 'Fresh apple harvest reported'
    assert not bool(mapped['has_cashtag'].iloc[0])


def test_optional_stocktwits_dependency_is_lazy_import(monkeypatch):
    import importlib
    import sys
    monkeypatch.setitem(sys.modules, 'requests', None)
    import cwt_quant.connectors.stocktwits as module
    importlib.reload(module)
    assert module.label_to_score('Bullish') == 1.0
    assert module.label_to_score('Bearish') == -1.0
