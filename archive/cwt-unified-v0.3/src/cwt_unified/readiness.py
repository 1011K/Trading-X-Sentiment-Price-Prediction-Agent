"""Fail-closed preflight of actual dataset quality before reporting forecasts."""
from dataclasses import dataclass, asdict
from datetime import timedelta
import numpy as np
import pandas as pd
from .data import load_posts,load_prices,assign_session,is_relevant

@dataclass(frozen=True)
class Readiness:
    state: str
    post_rows: int
    mapped_posts: int
    unique_post_sessions: int
    calendar_span_days: int
    price_bars: int
    price_180d_covered: bool
    x_month_buckets_with_posts: int
    x_window_distribution_covered: bool
    page_complete_declared: bool
    historical_text_point_in_time_verified: bool
    known_limitations: list[str]
    def to_json(self): return asdict(self)

def check_dataset(posts_file,prices_file,ticker,source,min_posts=50,min_post_sessions=20):
    p=load_prices(prices_file)
    x=load_posts(posts_file)
    x=x.loc[x.text.map(lambda t:is_relevant(t,ticker))].copy()
    mapped=assign_session(x,p)
    n_dates=int(mapped.session_date.nunique()) if not mapped.empty else 0
    # First actual exchange session in the 180-calendar-day window must be present.
    import exchange_calendars as xc
    last=pd.Timestamp(p.date.iloc[-1]); start=last-pd.Timedelta(days=179)
    calendar=xc.get_calendar('XNYS')
    required=calendar.schedule.loc[str(start.date()):str(last.date())]
    covered=bool(len(required) and p.date.iloc[0] == required.index[0].date())
    # At least one relevant observed X post in each of six approximate monthly bins.
    # This is a distribution floor, NOT proof of exhaustive API search coverage.
    if mapped.empty:
        month_buckets=0
    else:
        origin=pd.Timestamp(p.date.iloc[0])
        bucket=((pd.to_datetime(mapped.session_date)-origin).dt.days//30).clip(0,5)
        month_buckets=int(bucket.nunique())
    x_spread_ok=month_buckets==6
    problems=[]
    if not x_spread_ok:problems.append(f'X dates span only {month_buckets} of 6 approximately monthly bins')
    if not covered:problems.append('Price data does not cover first scheduled trading session of the 180-day window')
    if len(mapped)<min_posts:problems.append(f'Only {len(mapped)} mapped posts; require {min_posts}')
    if n_dates<min_post_sessions:problems.append(f'Only {n_dates} sentiment sessions; require {min_post_sessions}')
    if not source['pagination_complete']:problems.append('Provider collection pagination not declared complete')
    if not source.get('coverage_independently_verified',False):
        problems.append('Collection coverage not independently verified beyond user declaration')
    pit=bool(source.get('historical_text_point_in_time_verified',False))
    if not pit:
        problems.append('Historical post content/edits not independently known as of each forecast date')
    if mapped.empty:problems.append('No mapped posts, refusing price-only masquerading as X model')
    if not covered or not x_spread_ok or len(mapped)<min_posts or n_dates<min_post_sessions:
        state='BLOCKED_INSUFFICIENT_DATA'
    elif not source['pagination_complete']:
        state='BLOCKED_INCOMPLETE_COLLECTION'
    else:
        state='RESEARCH_PROVISIONAL' if problems else 'RESEARCH_SOURCE_READY'
    return Readiness(state=state,post_rows=len(x),mapped_posts=len(mapped),
         unique_post_sessions=n_dates,calendar_span_days=(p.date.iloc[-1]-p.date.iloc[0]).days+1,
         price_bars=len(p),price_180d_covered=covered,
         x_month_buckets_with_posts=month_buckets,x_window_distribution_covered=x_spread_ok,
         page_complete_declared=source['pagination_complete'],
         historical_text_point_in_time_verified=pit,known_limitations=problems)
