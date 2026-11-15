from datetime import datetime
from pathlib import Path
import json
import sqlite3

import pandas as pd
import pytest
import exchange_calendars as xc

from cwt_unified.ingest import (field, from_export, normalize_posts, normalize_prices,
                                write_dataset)

CUTOFF = '2026-11-13T21:00:00Z'


def sample_rows():
    return [
        {'id':'1','createdAt':'2026-11-12T19:00:00Z','fullText':'$AAPL bullish market',
         'author':{'id':'u1','followersCount':100000},'likeCount':201,'viewCount':5000},
        {'id':'1','createdAt':'2026-11-12T19:00:00Z','fullText':'$AAPL bullish market'},
        {'id':'2','createdAt':'2026-11-12T20:00:00Z','fullText':'apple fruit is excellent'},
        {'id':'3','createdAt':'2025-11-12T19:00:00Z','fullText':'$AAPL old'},
        {'id':'4','createdAt':'2026-11-13T19:59:00Z','fullText':'$AAPL earnings risk',
         'retweetCount':4}
    ]


def test_nested_and_dedup_and_relevance():
    df,a = normalize_posts(sample_rows(),'AAPL',CUTOFF)
    assert len(df)==2 and a['rejections']['duplicate_id']==1
    assert a['rejections']['outside_window']==1
    assert a['rejections']['not_relevant']==1
    assert pd.isna(df.iloc[0]['engagement_asof_utc'])
    assert not a['historical_engagement_snapshots_verified']
    assert int(df.iloc[0].followers)==100000


def test_strict_cutoff_excludes_future():
    rows=[{'id':'future','createdAt':'2026-11-14T00:00:00Z','fullText':'$AAPL rally'}]
    with pytest.raises(ValueError,match='No AAPL posts'):
        normalize_posts(rows,'AAPL',CUTOFF)


def test_blank_timestamp_rejected():
    with pytest.raises(ValueError,match='No AAPL posts'):
        normalize_posts([{'text':'$AAPL','createdAt':None}], 'AAPL', CUTOFF)


def test_json_import(tmp_path):
    path=tmp_path/'p.json'
    path.write_text(json.dumps(sample_rows()))
    assert len(from_export(path))==5


def test_sqlite_join_and_model_input(tmp_path):
    sched=xc.get_calendar('XNYS').schedule.loc['2026-07-01':'2026-11-13']
    raw=tmp_path/'prices_source.csv'
    pd.DataFrame({'Date':sched.index.date,'Open':[100.0]*len(sched),
                  'Close':[101.0]*len(sched)}).to_csv(raw,index=False)
    prices=normalize_prices(raw,CUTOFF)
    posts,a=normalize_posts(sample_rows(),'AAPL',CUTOFF)
    result=write_dataset(posts,prices,tmp_path/'output','AAPL',CUTOFF,'fixture',a)
    assert result['mapped_posts']==2
    assert (tmp_path/'output'/'data_audit.json').exists()
    with sqlite3.connect(tmp_path/'output'/'research.sqlite') as con:
        assert con.execute('SELECT SUM(post_count) FROM daily_post_counts').fetchone()[0] == 2


def test_refuse_missing_sessions(tmp_path):
    sched=xc.get_calendar('XNYS').schedule.loc['2026-07-01':'2026-11-13']
    raw=tmp_path/'p.csv'
    pd.DataFrame({'Date':sched.index.date[1:],'Close':[101]* (len(sched)-1)}).drop(index=[10]).to_csv(raw,index=False)
    posts,a=normalize_posts(sample_rows(),'AAPL',CUTOFF)
    with pytest.raises(ValueError,match='Missing exchange price sessions'):
        write_dataset(posts,normalize_prices(raw,CUTOFF),tmp_path/'o','AAPL',CUTOFF,'fixture',a)


def test_flattened_actor_columns():
    assert field({'author.followersCount':900},'author.followersCount')==900


def test_price_window_flag_is_not_silent(tmp_path):
    sched=xc.get_calendar('XNYS').schedule.loc['2026-07-01':'2026-11-13']
    raw=tmp_path/'p.csv'
    pd.DataFrame({'Date':sched.index.date,'Open':[100]*len(sched),'Close':[101]*len(sched)}).to_csv(raw,index=False)
    posts,a=normalize_posts(sample_rows(),'AAPL',CUTOFF)
    result=write_dataset(posts,normalize_prices(raw,CUTOFF),tmp_path/'o','AAPL',CUTOFF,'fixture',a)
    assert result['price_window_status']=='PARTIAL_MISSING_EARLY_SESSIONS'


def test_lexical_scoring_cli_backend():
    from cwt_unified.score import score_texts
    vals=score_texts(['$AAPL bullish growth','$AAPL bearish risk'],'lexical')
    assert len(vals)==2 and vals[0]>vals[1]
