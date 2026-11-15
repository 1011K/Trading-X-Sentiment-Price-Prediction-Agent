"""Contract-based CSV parsing. Provider authentication belongs to a separate reviewed adapter."""
from __future__ import annotations
from pathlib import Path
import hashlib
import re
import numpy as np
import pandas as pd
import exchange_calendars as xc


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fd:
        for block in iter(lambda: fd.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def load_prices(path: str | Path, exchange: str = "XNYS") -> pd.DataFrame:
    d = pd.read_csv(path)
    if not {"date", "close"}.issubset(d.columns):
        raise ValueError("prices.csv must include date,close; optional open")
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"], errors="raise").dt.date
    for col in ("close", "open"):
        if col in d:
            d[col] = pd.to_numeric(d[col], errors="raise")
            if (d[col] <= 0).any() or not np.isfinite(d[col].to_numpy()).all():
                raise ValueError(f"Price column {col} must be finite and strictly positive")
    d = d.sort_values("date").reset_index(drop=True)
    if d.date.duplicated().any() or d.empty:
        raise ValueError("Price dates must be present and unique")
    cal = xc.get_calendar(exchange)
    dates = pd.to_datetime(d.date)
    start, end = dates.min().strftime("%Y-%m-%d"), dates.max().strftime("%Y-%m-%d")
    schedule = cal.schedule.loc[start:end]
    permitted = set(schedule.index.date)
    if not set(d.date).issubset(permitted):
        raise ValueError("Price file includes exchange non-session dates")
    # Reject missing exchange sessions rather than silently treating a gap as a daily observation.
    if set(d.date) != permitted:
        absent = sorted(permitted - set(d.date))
        raise ValueError(f"Missing exchange price sessions: {absent[:8]}")
    d["market_open_utc"] = pd.to_datetime(schedule.loc[dates.dt.strftime('%Y-%m-%d'), 'open'].to_numpy(), utc=True)
    d["market_close_utc"] = pd.to_datetime(schedule.loc[dates.dt.strftime('%Y-%m-%d'), 'close'].to_numpy(), utc=True)
    return d


def load_posts(path: str | Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    if not {"timestamp_utc", "text"}.issubset(d.columns):
        raise ValueError("posts.csv must include timestamp_utc,text")
    d = d.copy()
    d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], errors="raise", utc=True)
    if d.timestamp_utc.isna().any():
        raise ValueError("Post timestamps cannot be null")
    d["text"] = d.text.fillna("").astype(str)
    if "post_id" in d and (d["post_id"].isna().any() or d["post_id"].astype(str).str.strip().eq("").any()):
        raise ValueError("Missing explicit post_id; omit column for deterministic fixture fallback")
    if "post_id" not in d:
        # Fallback exists for fixture compatibility; its absence is disclosed.
        d["post_id"] = [hashlib.sha256(f"{t}:{s}".encode()).hexdigest() for t, s in zip(d.timestamp_utc, d.text)]
        d.attrs["generated_post_ids"] = True
    else:
        d["post_id"] = d.post_id.astype(str)
        d.attrs["generated_post_ids"] = False
    d = d.drop_duplicates(subset="post_id", keep="first").copy()
    if "author_id" not in d:
        d["author_id"] = ""
    else:
        d["author_id"] = d.author_id.fillna("").astype(str)
    if "is_repost" in d:
        flags = d.is_repost.fillna(False).astype(str).str.lower().str.strip()
        if not flags.isin({"true", "false", "1", "0"}).all():
            raise ValueError("is_repost must be a boolean-like field")
        d = d.loc[~flags.isin({"true", "1"})].copy()
    for c in ["likes", "reposts", "comments", "followers"]:
        if c not in d:
            d[c] = np.nan
        d[c] = pd.to_numeric(d[c], errors="coerce")
        if (d[c].dropna() < 0).any():
            raise ValueError(f"Negative engagement metric: {c}")
    for c in ["engagement_asof_utc", "reply_asof_utc"]:
        if c not in d: d[c] = pd.NaT
        d[c] = pd.to_datetime(d[c], errors="coerce", utc=True)
    for c in ["sentiment", "reply_sentiment"]:
        if c not in d: d[c] = np.nan
        d[c] = pd.to_numeric(d[c], errors="coerce")
        if (~d[c].dropna().between(-1, 1)).any():
            raise ValueError(f"{c} must be in [-1,+1]")
    return d.sort_values("timestamp_utc").reset_index(drop=True)


def is_relevant(text: str, ticker: str) -> bool:
    from .relevance import relevance_reason
    return relevance_reason(text, ticker) is not None


def assign_session(posts: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Posts strictly before actual exchange close belong to that session.
    Posted at close or later -> next trading session. All times are UTC.
    """
    if posts.empty: return posts.assign(session_date=pd.Series(dtype='object'), session_close_utc=pd.Series(dtype='datetime64[ns, UTC]'))
    utc_close = pd.to_datetime(prices.market_close_utc, utc=True)
    ts = pd.to_datetime(posts.timestamp_utc, utc=True)
    pos = np.searchsorted(utc_close.astype("int64").to_numpy(), ts.astype("int64").to_numpy(), side="right")
    begin = pd.Timestamp(prices.date.iloc[0], tz="UTC")
    valid = (pos < len(prices)) & (ts >= begin).to_numpy()
    out = posts.loc[valid].copy()
    positions = pos[valid]
    out["session_date"] = prices.date.iloc[positions].to_numpy()
    out["session_close_utc"] = utc_close.iloc[positions].to_numpy()
    return out
