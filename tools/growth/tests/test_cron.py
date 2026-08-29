"""The minimal cron matcher the simulator expands cadences with."""

from datetime import datetime

import pytest

from growth.cron import Cron, CronError


def test_daily_firing_count_and_time():
    fires = Cron("19 7 * * *").firings(datetime(2026, 8, 29), 7)
    assert len(fires) == 7
    assert fires[0] == datetime(2026, 8, 29, 7, 19)
    assert fires[-1] == datetime(2026, 9, 4, 7, 19)


def test_hourly_step():
    fires = Cron("17 */6 * * *").firings(datetime(2026, 1, 1), 1)
    assert [f.hour for f in fires] == [0, 6, 12, 18]
    assert all(f.minute == 17 for f in fires)


def test_comma_list_hours():
    fires = Cron("0 6,18 * * *").firings(datetime(2026, 1, 1), 2)
    assert [f.hour for f in fires] == [6, 18, 6, 18]


def test_weekly_dow():
    # 2026-08-31 is a Monday.
    fires = Cron("47 5 * * 1").firings(datetime(2026, 8, 29), 7)
    assert fires == [datetime(2026, 8, 31, 5, 47)]


def test_dow_7_is_sunday():
    # 2026-08-30 is a Sunday.
    fires = Cron("0 12 * * 7").firings(datetime(2026, 8, 29), 3)
    assert fires == [datetime(2026, 8, 30, 12, 0)]


def test_window_start_is_inclusive_end_exclusive():
    fires = Cron("0 0 * * *").firings(datetime(2026, 1, 1), 1)
    assert fires == [datetime(2026, 1, 1, 0, 0)]


def test_bad_field_count_raises():
    with pytest.raises(CronError, match="5 fields"):
        Cron("0 0 * *")


def test_unsupported_token_raises():
    with pytest.raises(CronError):
        Cron("0 0 * * MON")


def test_out_of_range_raises():
    with pytest.raises(CronError, match="out of range"):
        Cron("61 0 * * *")
