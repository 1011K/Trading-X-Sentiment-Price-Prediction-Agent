"""
XNYS session calendar with early closes and DST awareness.

Lightweight pure-Python implementation sufficient for 180-day synthetic
and real daily research. For production multi-year work prefer
exchange_calendars or pandas_market_calendars.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")


# Hard-coded early closes and full holidays for recent years (extend as needed).
# Source: NYSE published calendar + exchange_calendars cross-check.
FULL_HOLIDAYS: Dict[int, Set[date]] = {
    2024: {
        date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19),
        date(2024, 3, 29), date(2024, 5, 27), date(2024, 6, 19),
        date(2024, 7, 4), date(2024, 9, 2), date(2024, 11, 28),
        date(2024, 12, 25),
    },
    2025: {
        date(2025, 1, 1), date(2025, 1, 9),  # Carter day of mourning
        date(2025, 1, 20), date(2025, 2, 17),
        date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19),
        date(2025, 7, 4), date(2025, 9, 1), date(2025, 11, 27),
        date(2025, 12, 25),
    },
    2026: {
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
        date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
        date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26),
        date(2026, 12, 25),
    },
}

# Early closes: date -> close time (local ET)
EARLY_CLOSES: Dict[date, time] = {
    # 2024
    date(2024, 7, 3): time(13, 0),
    date(2024, 11, 29): time(13, 0),
    date(2024, 12, 24): time(13, 0),
    # 2025
    date(2025, 7, 3): time(13, 0),
    date(2025, 11, 28): time(13, 0),
    date(2025, 12, 24): time(13, 0),
    # 2026
    date(2026, 11, 27): time(13, 0),  # Day after Thanksgiving
    date(2026, 12, 24): time(13, 0),
}


class XNYSCalendar:
    """Point-in-time aware session calendar for XNYS."""

    def __init__(self) -> None:
        self.tz = ET
        self.regular_open = time(9, 30)
        self.regular_close = time(16, 0)

    def is_trading_day(self, d: date) -> bool:
        year = d.year
        if year not in FULL_HOLIDAYS:
            raise ValueError(f"XNYS calendar for {year} is not verified; use an official exchange calendar")
        if d.weekday() >= 5:
            return False
        holidays = FULL_HOLIDAYS[year]
        return d not in holidays

    def session_close_time(self, d: date) -> time:
        if not self.is_trading_day(d):
            raise ValueError(f"{d} is not a trading day")
        return EARLY_CLOSES.get(d, self.regular_close)

    def session_close_dt(self, d: date) -> datetime:
        """Timezone-aware close datetime in America/New_York."""
        t = self.session_close_time(d)
        return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=self.tz)

    def session_open_dt(self, d: date) -> datetime:
        if not self.is_trading_day(d):
            raise ValueError(f"{d} is not a trading day")
        return datetime(d.year, d.month, d.day, 9, 30, tzinfo=self.tz)

    def trading_days_between(self, start: date, end: date) -> List[date]:
        """Inclusive list of trading days."""
        out: List[date] = []
        cur = start
        while cur <= end:
            if self.is_trading_day(cur):
                out.append(cur)
            cur += timedelta(days=1)
        return out

    def next_trading_day(self, d: date) -> date:
        cur = d + timedelta(days=1)
        while not self.is_trading_day(cur):
            cur += timedelta(days=1)
        return cur

    def previous_trading_day(self, d: date) -> date:
        cur = d - timedelta(days=1)
        while not self.is_trading_day(cur):
            cur -= timedelta(days=1)
        return cur

    def map_timestamp_to_session(
        self,
        ts: datetime,
        assign_exact_close_to_next: bool = True,
    ) -> date:
        """
        Map a post/event timestamp to the first *strictly later* session close date.

        - If ts is exactly on a session close and assign_exact_close_to_next=True,
          it belongs to the *next* session.
        - Early-close days use the early close time.
        - Pre-open timestamps map to that day's close (if trading day).
        """
        if ts.tzinfo is None:
            raise ValueError("Timestamp must contain an explicit timezone; refusing ambiguous as-of mapping")
        else:
            ts = ts.astimezone(self.tz)

        d = ts.date()

        # Walk forward until we find a session whose close is strictly after ts
        # (or after if exact and policy says next).
        candidate = d
        for _ in range(14):  # safety
            if self.is_trading_day(candidate):
                close_dt = self.session_close_dt(candidate)
                if assign_exact_close_to_next:
                    if ts < close_dt:
                        return candidate
                else:
                    if ts <= close_dt:
                        return candidate
            candidate = self.next_trading_day(candidate)
        raise RuntimeError(f"Could not map timestamp {ts} to a session")

    def session_index(self, start: date, end: date) -> pd.DatetimeIndex:
        days = self.trading_days_between(start, end)
        # Use close timestamps as the index labels (common quant convention)
        closes = [self.session_close_dt(d) for d in days]
        return pd.DatetimeIndex(closes, name="session_close")
