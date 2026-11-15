"""Calendar and session-mapping red-team cases."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from cwt_quant.calendar import XNYSCalendar, ET


@pytest.fixture
def cal():
    return XNYSCalendar()


def test_early_close_2026(cal):
    d = date(2026, 11, 27)  # Day after Thanksgiving
    assert cal.is_trading_day(d)
    assert cal.session_close_time(d) == time(13, 0)


def test_full_holiday(cal):
    d = date(2026, 11, 26)  # Thanksgiving
    assert not cal.is_trading_day(d)


def test_exact_close_maps_to_next(cal):
    # 16:00 on a regular day → next session
    d = date(2026, 11, 16)  # Monday
    close = cal.session_close_dt(d)
    mapped = cal.map_timestamp_to_session(close, assign_exact_close_to_next=True)
    assert mapped == cal.next_trading_day(d)


def test_pre_close_same_session(cal):
    d = date(2026, 11, 16)
    ts = datetime(2026, 11, 16, 15, 59, tzinfo=ET)
    mapped = cal.map_timestamp_to_session(ts, assign_exact_close_to_next=True)
    assert mapped == d


def test_after_early_close_next_session(cal):
    d = date(2026, 11, 27)
    # 13:30 after early close
    ts = datetime(2026, 11, 27, 13, 30, tzinfo=ET)
    mapped = cal.map_timestamp_to_session(ts, assign_exact_close_to_next=True)
    assert mapped == cal.next_trading_day(d)
