"""Daily OHLC via yfinance. Free, reliable for research."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from ..calendar import XNYSCalendar, ET
from ..exceptions import DataError
from ..logging_utils import get_logger

log = get_logger(__name__)


def fetch_daily_ohlc(
    ticker: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    history_calendar_days: int = 180,
) -> pd.DataFrame:
    """
    Pull adjusted daily bars. Returns DataFrame indexed by session_close (tz-aware ET).
    Requires: pip install yfinance
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise DataError(
            "yfinance is required for real prices. Install with: pip install yfinance"
        ) from exc

    cal = XNYSCalendar()
    if end is None:
        end = date.today()
    if start is None:
        # Exact inclusive calendar-day range. If a separate indicator warm-up
        # is needed, download it independently and exclude it from evaluation.
        start = end - timedelta(days=history_calendar_days - 1)

    log.info("Fetching yfinance daily OHLC for %s [%s → %s]", ticker, start, end)
    raw = yf.download(
        ticker,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise DataError(f"No price data returned for {ticker}")

    # Flatten MultiIndex columns if present
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in raw.columns]
    else:
        raw.columns = [str(c).lower() for c in raw.columns]

    needed = {"open", "high", "low", "close", "volume"}
    if not needed.issubset(set(raw.columns)):
        raise DataError(f"Unexpected yfinance columns: {list(raw.columns)}")

    raw = raw.reset_index()
    date_col = "Date" if "Date" in raw.columns else "date"
    raw["session_date"] = pd.to_datetime(raw[date_col]).dt.date

    # Keep only actual XNYS trading days
    trading = set(cal.trading_days_between(start, end))
    raw = raw[raw["session_date"].isin(trading)].copy()
    if raw.empty:
        raise DataError("No overlapping trading days after calendar filter")

    closes = [cal.session_close_dt(d) for d in raw["session_date"]]
    idx = pd.DatetimeIndex(closes, name="session_close")
    df = pd.DataFrame(
        {
            "open": raw["open"].values,
            "high": raw["high"].values,
            "low": raw["low"].values,
            "close": raw["close"].values,
            "volume": raw["volume"].values.astype(int),
            "session_date": raw["session_date"].values,
        },
        index=idx,
    )
    df["adj_close"] = df["close"]  # auto_adjust=True already
    df.attrs["source"] = "yfinance"
    df.attrs["ticker"] = ticker
    df.attrs["adjustment_policy"] = "yfinance auto_adjust=True"
    try:
        import hashlib
        raw_hash = pd.util.hash_pandas_object(df, index=True).values.tobytes()
        df.attrs["source_hash"] = hashlib.sha256(raw_hash).hexdigest()[:16]
    except Exception:
        df.attrs["source_hash"] = "yfinance_unhashed"
    log.info("Loaded %d daily bars for %s", len(df), ticker)
    return df
