"""Authorized-source import / normalization / coverage audit.

This module DOES NOT scrape X. It reads a permitted Apify export or an
already authorized Apify dataset, plus an explicit daily price CSV. All
post engagement counts are retrospective unless separate time-stamped
point-in-time snapshots are supplied and verified: never fabricate them.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .data import load_posts, load_prices


REQUIRED_TEXT = ('fullText', 'text', 'full_text', 'content')
REQUIRED_TIME = ('createdAt', 'created_at', 'timestamp_utc', 'date', 'timestamp')
ID_KEYS = ('id', 'tweetId', 'tweet_id', 'post_id', 'id_str')


def field(obj: dict, *keys, default=None):
    """First present non-null value, with support for dotted nested paths."""
    for path in keys:
        if path in obj and obj[path] not in (None, ''):
            return obj[path]
        node = obj
        for key in path.split('.'):
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if node is not None and node != '':
            return node
    return default


def from_export(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    if p.suffix.lower() == '.csv':
        with p.open('r', encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))
    if p.suffix.lower() == '.jsonl':
        with p.open('r', encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    if p.suffix.lower() == '.json':
        data = json.loads(p.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('items'), list):
            data = data['items']
        if not isinstance(data, list):
            raise ValueError('Expected a JSON list of post objects')
        return data
    raise ValueError('Post export must be .json, .jsonl or .csv')


def apify_dataset_items(dataset_id: str, max_items: int = 10000) -> list[dict]:
    """Read only an existing, authorized Apify dataset. Does not start an Actor."""
    token = os.environ.get('APIFY_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Set APIFY_TOKEN in your local environment; do not paste it into chat or commit it')
    if not dataset_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in dataset_id):
        raise ValueError('Dataset ID must be an existing Apify dataset ID')
    rows = []
    offset = 0
    while offset < max_items:
        limit = min(500, max_items - offset)
        params = urlencode({'format': 'json', 'offset': offset, 'limit': limit})
        url = f'https://api.apify.com/v2/datasets/{dataset_id}/items?{params}'
        req = Request(url, headers={'Authorization': f'Bearer {token}', 'Accept':'application/json'})
        with urlopen(req, timeout=30) as res:
            batch = json.load(res)
            total = res.headers.get('X-Apify-Pagination-Total')
        if not isinstance(batch, list):
            raise ValueError('Unexpected Apify API response; expected list')
        rows.extend(batch)
        offset += len(batch)
        if not batch or len(batch) < limit:
            break
        if total is not None and offset >= int(total):
            break
    if offset >= max_items and (total is None or offset < int(total)):
        raise ValueError(f'Dataset may exceed max_items={max_items}; refusing to silently truncate coverage')
    return rows


def utc_timestamp(value) -> str:
    ts = pd.to_datetime(value, utc=True, errors='raise')
    if pd.isna(ts):
        raise ValueError('Null post timestamp')
    return ts.isoformat()


def _integer_or_none(value):
    if value in (None, '', 'None'):
        return None
    v = int(float(value))
    if v < 0:
        raise ValueError('Negative count')
    return v


def normalize_posts(items: list[dict], ticker: str, cutoff: str, days: int = 180) -> tuple[pd.DataFrame, dict]:
    """Reject mismatched schemas. Keep all relevant posts, excluding out-of-window and duplicates."""
    if not items:
        raise ValueError('Empty post dataset; no fabricated fallback')
    from .data import is_relevant
    cutoff_utc = pd.Timestamp(cutoff)
    if cutoff_utc.tz is None:
        raise ValueError('cutoff must be timezone-aware UTC')
    cutoff_utc = cutoff_utc.tz_convert('UTC')
    start_utc = cutoff_utc - pd.Timedelta(days=days)
    posts = []
    filtered = {'missing_text_or_time':0, 'not_relevant':0, 'outside_window':0, 'duplicate_id':0}
    seen = set()
    for obj in items:
        if not isinstance(obj, dict):
            raise ValueError('Malformed post item; expected object')
        text = field(obj, *REQUIRED_TEXT)
        timestamp = field(obj, *REQUIRED_TIME)
        if not isinstance(text, str) or not text.strip() or timestamp is None:
            filtered['missing_text_or_time'] += 1
            continue
        ts = pd.Timestamp(utc_timestamp(timestamp))
        if not start_utc <= ts <= cutoff_utc:
            filtered['outside_window'] += 1
            continue
        if not is_relevant(text, ticker):
            filtered['not_relevant'] += 1
            continue
        pid = field(obj, *ID_KEYS)
        if pid is None:
            # Retrospective fixture fallback; record that provenance is weaker.
            pid = hashlib.sha256((ts.isoformat() + ':' + text).encode()).hexdigest()
        pid = str(pid)
        if pid in seen:
            filtered['duplicate_id'] += 1
            continue
        seen.add(pid)
        author_id = field(obj, 'author.id', 'author.id_str', 'user.id', 'authorId', 'author_id', default='')
        follows = field(obj, 'author.followers', 'author.followersCount', 'user.followers_count', 'authorFollowers', 'followers')
        likes = field(obj, 'likeCount', 'favoriteCount', 'likes', 'favorite_count')
        reposts = field(obj, 'retweetCount', 'repostCount', 'reposts', 'retweet_count')
        views = field(obj, 'viewCount', 'views', 'view_count')
        comments = field(obj, 'replyCount', 'comments', 'reply_count')
        posts.append({
            'post_id': pid, 'author_id': str(author_id), 'timestamp_utc': ts.isoformat(),
            'text': text, 'likes': _integer_or_none(likes),
            'reposts': _integer_or_none(reposts), 'views': _integer_or_none(views),
            'comments': _integer_or_none(comments), 'followers': _integer_or_none(follows),
            # Do NOT claim retrieval-time counts were available at historical closes.
            'engagement_asof_utc': None, 'reply_asof_utc': None,
        })
    if not posts:
        raise ValueError(f'No {ticker} posts in requested window; rejects={filtered}')
    result = pd.DataFrame(posts).sort_values('timestamp_utc').reset_index(drop=True)
    days_seen = pd.to_datetime(result.timestamp_utc, utc=True).dt.date.nunique()
    audit = {'raw_rows':len(items),'relevant_window_rows':len(result),'unique_post_days':int(days_seen),
             'window_start_utc_exclusive':start_utc.isoformat(),'window_end_utc_inclusive':cutoff_utc.isoformat(),
             'rejections':filtered,'historical_engagement_snapshots_verified':False,
             'retrospective_engagement_counts_present':bool(result[['likes','reposts','views','followers']].notna().any().any()),
             'minimum_one_post_each_day':False,
             'dataset_completeness_status':'UNVERIFIED_QUERY_COVERAGE'}
    return result, audit


def normalize_prices(path: str | Path, cutoff: str, days: int = 180) -> pd.DataFrame:
    df = pd.read_csv(path)
    colmap = {c.strip().lower().replace(' ', '_'): c for c in df.columns}
    if 'date' not in colmap or 'close' not in colmap:
        raise ValueError('Price CSV needs Date,date and Close,close; optional Open,open')
    source_cols = [colmap['date'], colmap['close']]
    data = {'date':df[source_cols[0]], 'close':df[source_cols[1]]}
    if 'open' in colmap:
        data['open'] = df[colmap['open']]
    out = pd.DataFrame(data)
    parsed = pd.to_datetime(out.date, errors='raise').dt.date
    cut = pd.Timestamp(cutoff)
    if cut.tz is None:
        raise ValueError('cutoff must be timezone-aware')
    end = cut.date()
    start = end - timedelta(days=days-1)
    out['date'] = parsed
    out = out.loc[(out.date >= start) & (out.date <= end)].copy()
    if out.empty:
        raise ValueError('No price rows in 180-day window')
    out = out.sort_values('date').reset_index(drop=True)
    return out


def write_dataset(posts: pd.DataFrame, prices: pd.DataFrame, outdir: Path, ticker: str,
                  cutoff: str, source_name: str, audit: dict, actor_id: str | None = None,
                  dataset_id: str | None = None) -> dict:
    from .data import is_relevant, assign_session, sha256
    outdir.mkdir(parents=True, exist_ok=True)
    posts_file = outdir / 'posts.csv'
    prices_file = outdir / 'prices.csv'
    posts.to_csv(posts_file,index=False)
    prices.to_csv(prices_file,index=False)
    # Use original core validators and market calendar rather than changing behavior silently.
    p = load_prices(prices_file)
    x = load_posts(posts_file)
    x = x.loc[x.text.apply(lambda t:is_relevant(t,ticker))]
    mapped = assign_session(x,p)
    dbfile = outdir / 'research.sqlite'
    with sqlite3.connect(dbfile) as con:
        p_to_store=p[['date','open','close']].copy() if 'open' in p.columns else p[['date','close']].copy()
        p_to_store['date'] = p_to_store.date.astype(str)
        p_to_store.to_sql('prices',con,if_exists='replace',index=False)
        x_to_store=x.copy()
        x_to_store['timestamp_utc']=x_to_store.timestamp_utc.astype(str)
        for c in ('engagement_asof_utc','reply_asof_utc'):
            x_to_store[c]=x_to_store[c].astype(str).replace('NaT',None)
        x_to_store.to_sql('posts',con,if_exists='replace',index=False)
        mapped_to_store=mapped[['post_id','session_date']].copy()
        mapped_to_store['session_date']=mapped_to_store.session_date.astype(str)
        mapped_to_store.to_sql('post_session_map',con,if_exists='replace',index=False)
        con.execute('DROP VIEW IF EXISTS daily_post_counts')
        con.execute('''CREATE VIEW daily_post_counts AS
            SELECT p.date, p.close, COALESCE(s.post_count,0) AS post_count
            FROM prices p LEFT JOIN
            (SELECT session_date, COUNT(*) AS post_count FROM post_session_map GROUP BY session_date) s
            ON p.date = s.session_date''')
    # 180 calendar days: require the first expected exchange session in the window,
    # not merely a partial price file with contiguous sessions.
    import exchange_calendars as xc
    expected_start = pd.Timestamp(cutoff).date() - timedelta(days=179)
    expected_sched = xc.get_calendar('XNYS').schedule.loc[str(expected_start):str(pd.Timestamp(cutoff).date())]
    first_expected = expected_sched.index[0].date()
    start_covered = p.date.iloc[0] <= first_expected
    audit.update({'requested_180d_start_date':str(expected_start),
                  'first_expected_exchange_session':str(first_expected),
                  'price_180d_start_covered':bool(start_covered),
                  'price_window_status':'PASSES_START_GATE' if start_covered else 'PARTIAL_MISSING_EARLY_SESSIONS',
                  'ticker':ticker,'source':source_name,'actor_id':actor_id,'dataset_id':dataset_id,
                  'cutoff_utc':cutoff, 'price_bars':len(p),'first_price_session':str(p.date.iloc[0]),
                  'last_price_session':str(p.date.iloc[-1]),'mapped_posts':len(mapped),
                  'post_sha256':sha256(posts_file),'price_sha256':sha256(prices_file),
                  'sqlite_database':'research.sqlite',
                  'critical_limitations':['Apify export schema and source permissions must be independently checked',
                     'Historical likes/reposts/follower numbers may include future engagement: disabled',
                     'Search queries may miss relevant posts: 180-day date span is not completeness proof',
                     'No fabricated sentiment, no inferred as-of snapshot timestamps',
                     'Price corporate-action consistency and redistribution permission are user-reviewed']})
    (outdir/'data_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    return audit


def main(argv=None):
    parser=argparse.ArgumentParser(description='Import permitted historical X data into CWT research project')
    src=parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--posts-export',help='Local permitted Apify JSON, JSONL or CSV export')
    src.add_argument('--apify-dataset-id',help='Already authorized Apify dataset ID; APIFY_TOKEN must be in env')
    parser.add_argument('--prices-export',required=True,help='Daily price CSV with Date/Open/Close; no price scraping done')
    parser.add_argument('--ticker',default='AAPL')
    parser.add_argument('--cutoff-utc',required=True,help='Explicit UTC cutoff, e.g. 2026-11-13T21:00:00Z')
    parser.add_argument('--actor-id',help='Optional exact provenance ID; never invent')
    parser.add_argument('--out',default='input_real')
    parser.add_argument('--max-items',type=int,default=10000)
    args=parser.parse_args(argv)
    items=from_export(args.posts_export) if args.posts_export else apify_dataset_items(args.apify_dataset_id,args.max_items)
    posts,audit=normalize_posts(items,args.ticker.upper(),args.cutoff_utc)
    prices=normalize_prices(args.prices_export,args.cutoff_utc)
    audit=write_dataset(posts,prices,Path(args.out),args.ticker.upper(),args.cutoff_utc,
                         str(args.posts_export) if args.posts_export else 'authorized Apify dataset',audit,args.actor_id,args.apify_dataset_id)
    print(json.dumps({'status':'DATA_IMPORTED_COVERAGE_NOT_VERIFIED','post_count':audit['relevant_window_rows'],
                      'bars':audit['price_bars'],'mapped_posts':audit['mapped_posts'],
                      'files':str(args.out)},indent=2))

if __name__=='__main__':
    main()
