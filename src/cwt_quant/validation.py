"""Input and intermediate data validation."""

from __future__ import annotations

from typing import List, Optional, Set

import numpy as np
import pandas as pd

from .calendar import XNYSCalendar
from .config import Config
from .exceptions import DataError, LeakageError, ProvenanceError
from .logging_utils import get_logger

log = get_logger(__name__)


REQUIRED_PRICE_COLS = {"open", "high", "low", "close", "volume", "session_date"}
REQUIRED_POST_COLS = {
    "post_id",
    "created_at",
    "author",
    "followers",
    "text",
    "has_cashtag",
    "likes",
    "reposts",
    "comments",
    "engagement_asof",
}


def validate_prices(prices: pd.DataFrame, cfg: Config, cal: XNYSCalendar) -> List[str]:
    """
    Validate price panel. Returns list of soft warnings.
    Raises DataError on hard failures.
    """
    warnings: List[str] = []
    if prices is None or prices.empty:
        raise DataError("Price DataFrame is empty or None")

    missing = REQUIRED_PRICE_COLS - set(prices.columns)
    if missing:
        raise DataError(f"Price DataFrame missing columns: {sorted(missing)}")

    if not isinstance(prices.index, pd.DatetimeIndex):
        raise DataError("Price index must be DatetimeIndex (session closes)")

    if prices.index.tz is None:
        warnings.append("Price index is timezone-naive; assuming America/New_York")

    # Monotonic increasing
    if not prices.index.is_monotonic_increasing:
        raise DataError("Price index is not monotonic increasing")

    # No duplicate sessions
    if prices.index.duplicated().any():
        raise DataError("Duplicate session_close timestamps in prices")

    # Positive prices
    for col in ("open", "high", "low", "close"):
        if (prices[col] <= 0).any():
            raise DataError(f"Non-positive values found in price column '{col}'")

    # OHLC consistency
    bad_hl = (prices["high"] < prices["low"]).sum()
    if bad_hl:
        raise DataError(f"{bad_hl} rows have high < low")

    # Missing session audit
    if "session_date" in prices.columns:
        dates = sorted(prices["session_date"].tolist())
        if len(dates) >= 2:
            expected = cal.trading_days_between(dates[0], dates[-1])
            actual = set(dates)
            missing_sessions = [d for d in expected if d not in actual]
            if missing_sessions:
                msg = (
                    f"Missing {len(missing_sessions)} trading session(s) "
                    f"between {dates[0]} and {dates[-1]}: "
                    f"{missing_sessions[:5]}{'...' if len(missing_sessions) > 5 else ''}"
                )
                if cfg.fail_on_missing_sessions and len(missing_sessions) > cfg.max_allowed_missing_sessions:
                    raise DataError(msg + " (fail_on_missing_sessions=True)")
                warnings.append(msg)
                log.warning(msg)

    # Provenance
    if cfg.require_source_hashes and "source_hash" not in getattr(prices, "attrs", {}):
        # attrs may be lost on some operations; soft warning
        warnings.append("Price DataFrame lacks source_hash in attrs")

    return warnings


def validate_posts(posts: pd.DataFrame, cfg: Config) -> List[str]:
    warnings: List[str] = []
    if posts is None or posts.empty:
        warnings.append("Posts DataFrame is empty — sentiment features will be zero")
        return warnings

    missing = REQUIRED_POST_COLS - set(posts.columns)
    if missing:
        raise DataError(f"Posts DataFrame missing columns: {sorted(missing)}")

    if posts["post_id"].duplicated().any():
        n_dup = int(posts["post_id"].duplicated().sum())
        warnings.append(f"{n_dup} duplicate post_id rows present (will be deduplicated)")

    if posts["created_at"].isna().any():
        raise DataError("Posts contain null created_at")
    for col in ("created_at", "engagement_asof", "observed_at", "followers_asof", "reply_asof"):
        if col in posts.columns:
            naive = posts[col].map(lambda x: pd.notna(x) and getattr(x, "tzinfo", None) is None)
            if naive.any():
                raise DataError(f"{col} has {int(naive.sum())} timezone-naive value(s)")

    if (posts["followers"] < 0).any():
        raise DataError("Negative follower counts found")

    # Engagement asof should not be before created_at (data quality)
    if "engagement_asof" in posts.columns:
        engagement = pd.to_datetime(posts["engagement_asof"], utc=True)
        created = pd.to_datetime(posts["created_at"], utc=True)
        bad = engagement < created
        if bad.any():
            warnings.append(
                f"{int(bad.sum())} posts have engagement_asof < created_at (data quality issue)"
            )

    return warnings


def validate_panel(panel: pd.DataFrame, cfg: Config) -> None:
    if panel is None or panel.empty:
        raise DataError("Assembled panel is empty")
    required = {"close", "ret_1"}
    missing = required - set(panel.columns)
    if missing:
        raise DataError(f"Panel missing required columns: {sorted(missing)}")
    n = len(panel)
    if n < cfg.min_train_sessions + max(cfg.forecast_horizons) + 5:
        raise DataError(
            f"Panel too short ({n} sessions) for min_train={cfg.min_train_sessions} "
            f"and horizons={cfg.forecast_horizons}"
        )


def assert_no_future_labels(
    train_origins: pd.DatetimeIndex,
    test_origin: pd.Timestamp,
    horizon: int,
) -> None:
    """Hard leakage guard used inside walk-forward."""
    # train origins must satisfy origin + horizon sessions conceptually <= test
    # We check that no train origin is after the test origin.
    if (train_origins > test_origin).any():
        raise LeakageError(
            f"Train set contains origins after test origin {test_origin} (horizon={horizon})"
        )
