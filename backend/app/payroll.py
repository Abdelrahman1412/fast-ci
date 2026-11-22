"""Pure payroll arithmetic. No I/O, so it is cheap to test exhaustively."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
SOCIAL_INSURANCE_RATE = Decimal("0.09")
SOCIAL_INSURANCE_CAP = Decimal("45000")
DEFAULT_BRACKETS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("0"), Decimal("0")),
    (Decimal("5000"), Decimal("0.05")),
    (Decimal("15000"), Decimal("0.10")),
    (Decimal("40000"), Decimal("0.15")),
)


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def days_in_month(period: date) -> int:
    return calendar.monthrange(period.year, period.month)[1]


def worked_days(period: date, hire_date: date, end_date: date | None) -> int:
    """Calendar days in `period`'s month that the employee was employed."""
    first = period.replace(day=1)
    last = period.replace(day=days_in_month(period))
    start = max(first, hire_date)
    stop = min(last, end_date) if end_date else last
    if stop < start:
        return 0
    return (stop - start).days + 1


def prorate(amount: Decimal, days: int, period: date) -> Decimal:
    total = days_in_month(period)
    if days < 0 or days > total:
        raise ValueError(f"days must be between 0 and {total}, got {days}")
    return money(amount * days / total)


def progressive_tax(taxable: Decimal, brackets=DEFAULT_BRACKETS) -> Decimal:
    if taxable < 0:
        raise ValueError("taxable income cannot be negative")
    tax = Decimal("0")
    ordered = sorted(brackets)
    for i, (lower, rate) in enumerate(ordered):
        upper = ordered[i + 1][0] if i + 1 < len(ordered) else None
        if taxable <= lower:
            break
        band_top = taxable if upper is None else min(taxable, upper)
        tax += (band_top - lower) * rate
    return money(tax)


def social_insurance(basic: Decimal) -> Decimal:
    return money(min(basic, SOCIAL_INSURANCE_CAP) * SOCIAL_INSURANCE_RATE)


def gratuity(basic: Decimal, years: Decimal) -> Decimal:
    """End-of-service award: 21 days' basic per year for the first 5 years, 30 after."""
    if years < 0:
        raise ValueError("years cannot be negative")
    if years < 1:
        return money(0)
    daily = basic / 30
    first = min(years, Decimal(5)) * 21 * daily
    rest = max(years - 5, Decimal(0)) * 30 * daily
    return money(first + rest)


@dataclass(frozen=True)
class Payslip:
    gross: Decimal
    unpaid_days: int
    social_ins: Decimal
    tax: Decimal

    @property
    def net(self) -> Decimal:
        return money(self.gross - self.social_ins - self.tax)


def compute_payslip(
    *,
    period: date,
    basic: Decimal,
    housing: Decimal = Decimal(0),
    transport: Decimal = Decimal(0),
    hire_date: date,
    end_date: date | None = None,
    unpaid_days: int = 0,
    brackets=DEFAULT_BRACKETS,
) -> Payslip:
    days = worked_days(period, hire_date, end_date)
    days = max(days - unpaid_days, 0)
    monthly = basic + housing + transport
    gross = prorate(monthly, days, period)
    basic_paid = prorate(basic, days, period)
    si = social_insurance(basic_paid)
    tax = progressive_tax(max(gross - si, Decimal(0)), brackets)
    return Payslip(gross=gross, unpaid_days=unpaid_days, social_ins=si, tax=tax)
