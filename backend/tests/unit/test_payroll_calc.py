from datetime import date
from decimal import Decimal

import pytest
from app import payroll

D = Decimal


@pytest.mark.parametrize(
    ("period", "days"),
    [
        (date(2026, m, 1), d)
        for m, d in [
            (1, 31),
            (2, 28),
            (3, 31),
            (4, 30),
            (5, 31),
            (6, 30),
            (7, 31),
            (8, 31),
            (9, 30),
            (10, 31),
            (11, 30),
            (12, 31),
        ]
    ]
    + [(date(2024, 2, 1), 29), (date(2000, 2, 1), 29), (date(1900, 2, 1), 28)],
)
def test_days_in_month(period, days):
    assert payroll.days_in_month(period) == days


@pytest.mark.parametrize(
    ("hire", "end", "expected"),
    [
        (date(2020, 1, 1), None, 30),
        (date(2026, 4, 1), None, 30),
        (date(2026, 4, 2), None, 29),
        (date(2026, 4, 15), None, 16),
        (date(2026, 4, 30), None, 1),
        (date(2026, 5, 1), None, 0),
        (date(2020, 1, 1), date(2026, 4, 30), 30),
        (date(2020, 1, 1), date(2026, 4, 15), 15),
        (date(2020, 1, 1), date(2026, 4, 1), 1),
        (date(2020, 1, 1), date(2026, 3, 31), 0),
        (date(2026, 4, 10), date(2026, 4, 20), 11),
        (date(2026, 4, 10), date(2026, 4, 10), 1),
    ],
)
def test_worked_days_in_april(hire, end, expected):
    assert payroll.worked_days(date(2026, 4, 1), hire, end) == expected


@pytest.mark.parametrize("days", range(0, 31))
def test_prorate_is_linear_and_bounded(days):
    full = D("9300")
    value = payroll.prorate(full, days, date(2026, 1, 1))
    assert value == payroll.money(full * days / 31)
    assert D(0) <= value <= full


@pytest.mark.parametrize("days", [-1, 32, 100])
def test_prorate_rejects_impossible_days(days):
    with pytest.raises(ValueError):
        payroll.prorate(D("1000"), days, date(2026, 1, 1))


@pytest.mark.parametrize(
    ("taxable", "expected"),
    [
        (D("0"), D("0")),
        (D("4999.99"), D("0")),
        (D("5000"), D("0")),
        (D("5000.01"), D("0.00")),
        (D("6000"), D("50.00")),
        (D("15000"), D("500.00")),
        (D("16000"), D("600.00")),
        (D("40000"), D("3000.00")),
        (D("50000"), D("4500.00")),
        (D("100000"), D("12000.00")),
    ],
)
def test_progressive_tax_bands(taxable, expected):
    assert payroll.progressive_tax(taxable) == expected


@pytest.mark.parametrize("taxable", [D(x) for x in range(0, 120_000, 4_000)])
def test_progressive_tax_never_exceeds_top_rate(taxable):
    tax = payroll.progressive_tax(taxable)
    assert D(0) <= tax <= taxable * D("0.15")


@pytest.mark.parametrize(("low", "high"), [(D(a), D(a + 2500)) for a in range(0, 60_000, 5_000)])
def test_progressive_tax_is_monotonic(low, high):
    assert payroll.progressive_tax(low) <= payroll.progressive_tax(high)


def test_progressive_tax_rejects_negative_income():
    with pytest.raises(ValueError):
        payroll.progressive_tax(D("-1"))


def test_progressive_tax_with_custom_flat_bracket():
    assert payroll.progressive_tax(D("1000"), ((D(0), D("0.2")),)) == D("200.00")


@pytest.mark.parametrize(
    ("basic", "expected"),
    [(D("0"), D("0")), (D("10000"), D("900.00")), (D("45000"), D("4050.00")), (D("90000"), D("4050.00"))],
)
def test_social_insurance_is_capped(basic, expected):
    assert payroll.social_insurance(basic) == expected


@pytest.mark.parametrize(
    ("years", "expected"),
    [
        (D("0"), D("0")),
        (D("0.99"), D("0")),
        (D("1"), D("21000.00")),
        (D("3"), D("63000.00")),
        (D("5"), D("105000.00")),
        (D("6"), D("135000.00")),
        (D("10"), D("255000.00")),
    ],
)
def test_gratuity_rates_change_after_five_years(years, expected):
    assert payroll.gratuity(D("30000"), years) == expected


def test_gratuity_rejects_negative_service():
    with pytest.raises(ValueError):
        payroll.gratuity(D("30000"), D("-1"))


@pytest.mark.parametrize("unpaid", [0, 1, 5, 10, 29, 30, 45])
def test_payslip_net_identity_holds(unpaid):
    slip = payroll.compute_payslip(
        period=date(2026, 4, 1),
        basic=D("20000"),
        housing=D("5000"),
        transport=D("1500"),
        hire_date=date(2021, 6, 1),
        unpaid_days=unpaid,
    )
    assert slip.net == slip.gross - slip.social_ins - slip.tax
    assert slip.net >= 0


@pytest.mark.parametrize(
    ("hire", "end", "gross"),
    [
        (date(2021, 1, 1), None, D("16000.00")),
        (date(2026, 4, 16), None, D("8000.00")),
        (date(2021, 1, 1), date(2026, 4, 15), D("8000.00")),
        (date(2026, 5, 1), None, D("0.00")),
    ],
)
def test_payslip_gross_prorates_joiners_and_leavers(hire, end, gross):
    slip = payroll.compute_payslip(
        period=date(2026, 4, 1),
        basic=D("12000"),
        housing=D("3000"),
        transport=D("1000"),
        hire_date=hire,
        end_date=end,
    )
    assert slip.gross == gross


def test_unpaid_days_reduce_gross():
    full = payroll.compute_payslip(period=date(2026, 4, 1), basic=D("12000"), hire_date=date(2020, 1, 1))
    docked = payroll.compute_payslip(
        period=date(2026, 4, 1), basic=D("12000"), hire_date=date(2020, 1, 1), unpaid_days=3
    )
    assert docked.gross == full.gross - D("1200.00")


@pytest.mark.parametrize("value", ["1.005", "2.675", "0.125", "10", 3, 3.3])
def test_money_rounds_half_up_to_cents(value):
    result = payroll.money(value)
    assert result == result.quantize(D("0.01"))
