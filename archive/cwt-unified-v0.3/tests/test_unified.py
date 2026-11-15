from datetime import date
import numpy as np
import pandas as pd
import pytest
from cwt_unified.config import Config
from cwt_unified.data import load_prices, load_posts, is_relevant, assign_session
from cwt_unified.sentiment import influence_weight, lexical_sentiment, build_daily_sentiment
from cwt_unified.model import build_features, walkforward, training_indices, forecast_latest, research_pnl


def calendar_prices():
    import exchange_calendars as xc
    rows=xc.get_calendar("XNYS").schedule.loc["2026-04-01":"2026-10-01"]
    n=len(rows)
    p=pd.DataFrame({"date":rows.index.date,"open":100+np.arange(n)*.10,"close":100+np.arange(n)*.10+.06})
    p["market_close_utc"]=pd.to_datetime(rows['close'].to_numpy(),utc=True)
    p["market_open_utc"]=pd.to_datetime(rows['open'].to_numpy(),utc=True)
    return p


def row(ts,text="$AAPL bullish",author="X",**kw):
    return {"timestamp_utc":pd.Timestamp(ts),"text":text,"author_id":author,"post_id":kw.pop("post_id","p-"+str(ts)),
            "followers":kw.pop("followers",np.nan),"likes":kw.pop("likes",np.nan),
            "reposts":kw.pop("reposts",np.nan),"comments":kw.pop("comments",np.nan),
            "engagement_asof_utc":pd.Timestamp(kw.pop("engagement_asof_utc",pd.NaT)),
            "sentiment":kw.pop("sentiment",np.nan),"reply_sentiment":kw.pop("reply_sentiment",np.nan),
            "reply_asof_utc":pd.Timestamp(kw.pop("reply_asof_utc",pd.NaT))}


def test_sentiment_relevance_weights():
    assert lexical_sentiment("no bullish")<0
    assert lexical_sentiment("neutral market")==0
    assert is_relevant("$AAPL shares", "AAPL")
    assert not is_relevant("apple fruit shares", "AAPL")
    assert influence_weight(0,0,0,0)==1
    assert 1 <= influence_weight(20_000_000,50_000,50_000,10_000) <= 1.5


def test_early_close_nyse_timestamps():
    import exchange_calendars as xc
    sched=xc.get_calendar("XNYS").schedule.loc["2026-11-27":"2026-11-30"]
    assert pd.Timestamp(sched.loc['2026-11-27','close']).hour==18 # 13 ET (standard time)
    p=pd.DataFrame({"date":sched.index.date,"market_close_utc":pd.to_datetime(sched['close'].to_numpy(),utc=True)})
    posts=pd.DataFrame([row("2026-11-27T17:59:00Z",post_id="pre"),row("2026-11-27T18:01:00Z",post_id="post")])
    mapped=assign_session(posts,p)
    assert list(mapped.session_date)==[date(2026,11,27),date(2026,11,30)]


def test_price_calendar_rejects_missing_session(tmp_path):
    p=calendar_prices().iloc[:30][['date','close','open']].drop(index=4)
    path=tmp_path/'p.csv';p.to_csv(path,index=False)
    with pytest.raises(ValueError,match='Missing exchange price sessions'):
        load_prices(path)


def test_after_close_and_weekend():
    p=calendar_prices()
    sample=pd.DataFrame([row('2026-04-06T19:59:00Z',post_id='a'),row('2026-04-06T20:00:00Z',post_id='b'),row('2026-04-11T15:00:00Z',post_id='c')])
    m=assign_session(sample,p)
    assert list(m.session_date)==[date(2026,4,6),date(2026,4,7),date(2026,4,13)]


def test_future_engagement_snapshots_excluded():
    p=calendar_prices()
    d=p.loc[p.date==date(2026,4,6)].iloc[0]
    t=pd.Timestamp('2026-04-06T15:00:00Z')
    post=row(t,followers=50_000_000,likes=100000,reposts=30000,comments=1000,
             engagement_asof_utc='2026-04-07T09:00:00Z',sentiment=.8,post_id='future')
    daily,audit=build_daily_sentiment(p,pd.DataFrame([post]),Config(allow_influence=True))
    assert audit['influence_snapshot_coverage']==0
    assert not audit['influence_model_eligible']
    assert float(daily.loc[daily.date==d.date,'sentiment_influence'].iloc[0])==.8


def test_valid_replies_and_snapshots_and_neutrality():
    p=calendar_prices()
    t='2026-04-06T15:00:00Z'
    post=row(t,followers=100000,likes=300,reposts=20,comments=20,
             engagement_asof_utc='2026-04-06T15:20:00Z',sentiment=.6,
             reply_sentiment=-.5,reply_asof_utc='2026-04-06T16:00:00Z')
    daily,audit=build_daily_sentiment(p,pd.DataFrame([post]),Config(allow_influence=True))
    assert not audit['influence_model_eligible']  # one valid post cannot justify a separate predictor
    assert audit['reply_snapshots_valid']==1
    assert np.isclose(daily.loc[daily.date==date(2026,4,6),'sentiment_mean'].iloc[0],.6*.6+.4*(-.5))
    assert np.isclose(daily.loc[daily.date==date(2026,4,6),'sentiment_influence'].iloc[0],.6*.6+.4*(-.5))


def test_purge_and_future_close_invariant():
    p=calendar_prices();post=pd.DataFrame([row('2026-04-06T15:00:00Z')])
    daily,_=build_daily_sentiment(p,post,Config())
    before=build_features(p,daily)
    p2=p.copy();p2.loc[100:,'close']*=2
    after=build_features(p2,daily)
    for c in ['ret_1','ret_3','ret_5','vol_5','sentiment_mean']:
        pd.testing.assert_series_equal(before.loc[:99,c],after.loc[:99,c])
    for t in range(70,110):
        for h in range(1,6):
            tr=training_indices(t,h)
            assert all(tr+h<=t)


def test_real_walkforward_shapes_and_strategy():
    p=calendar_prices()
    post=pd.DataFrame([row('2026-04-06T15:00:00Z')])
    daily,audit=build_daily_sentiment(p,post,Config())
    df=build_features(p,daily)
    predictions=walkforward(df,Config(),audit['influence_model_eligible'])
    assert (predictions.loc[predictions.model!='naive_no_change','latest_train_label_index']<=predictions.loc[predictions.model!='naive_no_change','asof_index']).all()
    assert set(predictions.model)=={'naive_no_change','price_only','price_plus_sentiment'}
    forecast=forecast_latest(df,Config(),False)
    assert list(forecast.loc[forecast.horizon==0,'status'])==['OBSERVED_NOT_FORECAST']
    result=research_pnl(predictions,p,Config())
    assert result['status']=='EXPERIMENTAL_IDEALIZED_EXECUTION'
    assert result['entry']=='next session open'


def test_influence_variant_requires_sufficient_point_in_time_coverage():
    p=calendar_prices()
    rows=[]
    for d in p.date.iloc[:30]:
        for k in (0,1):
            t=pd.Timestamp(d,tz='UTC')+pd.Timedelta(hours=15,minutes=k)
            rows.append(row(t,post_id=f'{d}-{k}',author=f'{k}',followers=5000,likes=10,
                            reposts=2,comments=1,engagement_asof_utc=t+pd.Timedelta(minutes=2),sentiment=.5))
    _,audit=build_daily_sentiment(p,pd.DataFrame(rows),Config(allow_influence=True))
    assert audit['influence_model_eligible']
    assert audit['influence_snapshot_coverage']==1

def test_horizon_prediction_unchanged_by_future_price_mutation():
    from cwt_unified.model import _fit_predict,PRICE_FEATURES
    p=calendar_prices()
    d,_=build_daily_sentiment(p,pd.DataFrame([row('2026-04-06T15:00:00Z')]),Config())
    a=build_features(p,d)
    q=p.copy();q.loc[101:,'close']*=1.6
    b=build_features(q,d)
    f1=_fit_predict(a,90,5,PRICE_FEATURES,Config())
    f2=_fit_predict(b,90,5,PRICE_FEATURES,Config())
    assert np.isclose(f1[0],f2[0])
