from datetime import date, timedelta

import pytest
from app import leave

MON = date(2026, 11, 2)  # a Monday


@pytest.mark.parametrize(
    ("weekend", "length", "expected"),
    [
        ("sat-sun", 1, 1),
        ("sat-sun", 5, 5),
        ("sat-sun", 7, 5),
        ("sat-sun", 14, 10),
        ("sat-sun", 28, 20),
        ("fri-sat", 1, 1),
        ("fri-sat", 5, 4),
        ("fri-sat", 7, 5),
        ("fri-sat", 14, 10),
        ("fri", 7, 6),
        ("fri", 14, 12),
    ],
)
def test_working_days_by_weekend(weekend, length, expected):
    assert leave.working_days(MON, MON + timedelta(days=length - 1), weekend=weekend) == expected


@pytest.mark.parametrize("offset", range(7))
def test_single_day_is_one_or_zero(offset):
    day = MON + timedelta(days=offset)
    expected = 0 if day.weekday() in (5, 6) else 1
    assert leave.working_days(day, day) == expected


@pytest.mark.parametrize("weeks", range(1, 13))
def test_whole_weeks_are_five_days_each(weeks):
    assert leave.working_days(MON, MON + timedelta(weeks=weeks, days=-1)) == 5 * weeks


def test_holidays_are_not_counted():
    assert leave.working_days(MON, MON + timedelta(days=4), holidays=[MON + timedelta(days=2)]) == 4


def test_holiday_on_a_weekend_is_not_double_counted():
    saturday = MON + timedelta(days=5)
    assert leave.working_days(MON, MON + timedelta(days=6), holidays=[saturday]) == 5


def test_end_before_start_is_rejected():
    with pytest.raises(ValueError, match="before"):
        leave.working_days(MON, MON - timedelta(days=1))


def test_unknown_weekend_is_rejected():
    with pytest.raises(ValueError, match="unknown weekend"):
        leave.working_days(MON, MON, weekend="sun-mon")


@pytest.mark.parametrize(
    ("hire", "as_of", "expected"),
    [
        (date(2020, 1, 1), date(2026, 1, 1), 2),
        (date(2020, 1, 1), date(2026, 6, 30), 15),
        (date(2020, 1, 1), date(2026, 12, 31), 30),
        (date(2026, 7, 1), date(2026, 12, 31), 15),
        (date(2026, 7, 15), date(2026, 7, 14), 0),
        (date(2026, 7, 15), date(2026, 8, 14), 2),
        (date(2026, 7, 15), date(2026, 8, 15), 5),
        (date(2027, 1, 1), date(2026, 12, 31), 0),
    ],
)
def test_accrual_is_pro_rata_by_month(hire, as_of, expected):
    assert leave.accrued(30, hire, as_of) == expected


@pytest.mark.parametrize("month", range(1, 13))
def test_accrual_grows_each_month(month):
    hire = date(2019, 1, 1)
    assert leave.accrued(24, hire, date(2026, month, 28)) == 2 * month


@pytest.mark.parametrize("taken", [0, 5, 30, 31])
def test_balance_is_accrued_minus_taken(taken):
    assert leave.balance(30, date(2019, 1, 1), date(2026, 12, 31), taken) == 30 - taken
