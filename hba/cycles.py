import math

import pandas as pd

from hba.config import CYCLE_START_MONTHS


def cycle_start_for(date):
    # walk back month by month until we hit a cycle start month
    date = pd.Timestamp(date)
    year, month = date.year, date.month
    while month not in CYCLE_START_MONTHS:
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return pd.Timestamp(year, month, 1)


def cycle_end(start):
    # cycles are 2 calendar months, so the end is the day before the next start
    return pd.Timestamp(start) + pd.DateOffset(months=2) - pd.Timedelta(days=1)


def cycle_length(start):
    return (cycle_end(start) - pd.Timestamp(start)).days + 1


def halfway_day(start):
    return math.ceil(cycle_length(start) / 2)


def same_cycle_last_year(start):
    return pd.Timestamp(start) - pd.DateOffset(years=1)


def cycle_starts_between(first, last):
    # all cycle start dates from first to last, inclusive
    starts = []
    s = cycle_start_for(first)
    while s <= pd.Timestamp(last):
        starts.append(s)
        s = s + pd.DateOffset(months=2)
    return starts


def cycle_label(start):
    # "Aug-Sep 2026", or "Dec 2025-Jan 2026" when it crosses the new year
    start = pd.Timestamp(start)
    end = cycle_end(start)
    if start.year == end.year:
        return f"{start:%b}-{end:%b} {end.year}"
    return f"{start:%b %Y}-{end:%b %Y}"
