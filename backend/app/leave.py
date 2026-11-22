"""Leave-day arithmetic: working days between two dates, and balances."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

# Python weekday numbers: Monday=0 ... Sunday=6.
WEEKENDS = {
    "sat-sun": frozenset({5, 6}),
    "fri-sat": frozenset({4, 5}),
    "fri": frozenset({4}),
}


def working_days(start: date, end: date, *, weekend: str = "sat-sun", holidays: Iterable[date] = ()) -> int:
    if end < start:
        raise ValueError("end date is before start date")
    try:
        off = WEEKENDS[weekend]
    except KeyError:
        raise ValueError(f"unknown weekend {weekend!r}") from None
    skip = set(holidays)
    count = 0
    day = start
    while day <= end:
        if day.weekday() not in off and day not in skip:
            count += 1
        day += timedelta(days=1)
    return count


def accrued(annual_days: int, hire_date: date, as_of: date) -> int:
    """Whole days accrued this calendar year, pro rata by completed months."""
    if as_of < hire_date:
        return 0
    start = max(hire_date, date(as_of.year, 1, 1))
    months = (as_of.year - start.year) * 12 + (as_of.month - start.month)
    if as_of.day >= start.day:
        months += 1
    months = min(months, 12)
    return annual_days * months // 12


def balance(annual_days: int, hire_date: date, as_of: date, taken: int) -> int:
    return accrued(annual_days, hire_date, as_of) - taken
