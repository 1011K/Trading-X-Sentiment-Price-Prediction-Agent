"""Capture and validate a dated USD equity price snapshot for offline replay."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .calendar import XNYSCalendar
from .exceptions import DataError

PROVIDER = "Yahoo Finance via yfinance"
FIELDS = ("open", "high", "low", "close", "adj_close", "volume", "dividends", "splits")
EXCHANGES = {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "BTS"}


def evaluation_bounds(end: date) -> tuple[date, date]:
    evaluation_start = end - timedelta(days=179)
    return evaluation_start - timedelta(days=100), evaluation_start


def capture_prices(path: Path, ticker: str, end: date) -> None:
    import yfinance as yf

    start, _ = evaluation_bounds(end)
    try:
        asset = yf.Ticker(ticker)
        bars = asset.history(
            start=str(start), end=str(end + timedelta(days=1)), interval="1d",
            auto_adjust=False, actions=True, raise_errors=True,
        )
        info = asset.get_history_metadata()
        columns = {
            "Open": "open", "High": "high", "Low": "low", "Close": "close",
            "Adj Close": "adj_close", "Volume": "volume", "Dividends": "dividends",
            "Stock Splits": "splits",
        }
        rows = bars[list(columns)].rename(columns=columns).copy()
        rows.insert(0, "date", rows.index.strftime("%Y-%m-%d"))
        snapshot = {
            "provider": PROVIDER, "ticker": info.get("symbol"),
            "currency": info.get("currency"), "exchange": info.get("exchangeName"),
            "instrument_type": info.get("instrumentType"),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "yfinance_version": yf.__version__, "rows": rows.to_dict(orient="records"),
        }
        payload = json.dumps(snapshot, allow_nan=False, indent=2)
        _validate_snapshot(snapshot, ticker, end)
    except (ImportError, DataError):
        raise
    except Exception as exc:
        raise DataError(f"Price capture failed for {ticker} ({type(exc).__name__})") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload + "\n")


def _validate_snapshot(snapshot: dict, ticker: str, end: date) -> pd.DataFrame:
    if (
        snapshot["provider"] != PROVIDER or snapshot["ticker"] != ticker
        or snapshot["currency"] != "USD" or snapshot["exchange"] not in EXCHANGES
        or snapshot["instrument_type"] not in {"EQUITY", "ETF"}
    ):
        raise DataError("Price snapshot must match the ticker and a supported USD exchange-listed equity or ETF")
    cal = XNYSCalendar()
    start, _ = evaluation_bounds(end)
    dates = cal.trading_days_between(start, end)
    retrieved = datetime.fromisoformat(snapshot["retrieved_at_utc"].replace("Z", "+00:00"))
    if (not dates or dates[-1] != end or retrieved.utcoffset() is None
            or not cal.session_close_dt(end) <= retrieved <= datetime.now(timezone.utc)):
        raise DataError("Evaluation end must be a completed session at snapshot retrieval")
    bars = pd.DataFrame(snapshot["rows"])
    if bars["date"].tolist() != [day.isoformat() for day in dates]:
        raise DataError("Price snapshot must contain every expected session once, in chronological order")
    data = bars[list(FIELDS)].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(data.to_numpy()).all():
        raise DataError("Price snapshot contains missing or nonfinite values")
    prices = data[["open", "high", "low", "close", "adj_close"]]
    if (
        (prices <= 0).any().any() or (data["volume"] < 0).any()
        or (data["volume"] % 1 != 0).any() or (data["dividends"] < 0).any()
        or (data["high"] < data[["open", "close", "low"]].max(axis=1)).any()
        or (data["low"] > data[["open", "close"]].min(axis=1)).any()
    ):
        raise DataError("Invalid OHLCV or corporate action values")
    if data["splits"].ne(0).any():
        raise DataError("Price policy withholds split-bearing windows pending corporate action review")
    data.index = cal.session_index(start, end)
    data["session_date"] = dates
    return data


def load_prices(path: Path, ticker: str, end: date) -> tuple[pd.DataFrame, dict]:
    try:
        data = path.read_bytes()
        snapshot = json.loads(data)
        bars = _validate_snapshot(snapshot, ticker, end)
    except (OSError, KeyError, ValueError, TypeError, AttributeError) as exc:
        raise DataError(f"Invalid price snapshot ({type(exc).__name__})") from exc
    digest = hashlib.sha256(data).hexdigest()
    policy = "Provider execution OHLC; raw close-to-close price targets, excluding dividend cash flows"
    bars.attrs.update(source_hash=digest, adjustment_policy=policy)
    source = {name: snapshot[name] for name in (
        "provider", "ticker", "currency", "exchange", "instrument_type", "retrieved_at_utc"
    )}
    source.update(sha256=digest, policy=policy, yfinance_version=snapshot.get("yfinance_version"))
    return bars, source
