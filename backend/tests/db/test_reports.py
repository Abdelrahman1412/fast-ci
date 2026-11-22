from datetime import date

import pytest
from tests import factories

pytestmark = pytest.mark.db


@pytest.mark.parametrize("count", [0, 1, 3, 12])
def test_headcount_per_department(client, conn, count):
    dept = factories.department(conn, name=f"Report {count}")
    for _ in range(count):
        factories.employee(conn, dept["id"])
    rows = {r["department"]: r for r in client.get("/reports/headcount", params={"as_of": "2026-06-01"}).json()}
    assert rows[f"Report {count}"]["headcount"] == count


@pytest.mark.parametrize(
    ("hire", "end", "as_of", "counted"),
    [
        (date(2026, 1, 1), None, "2026-06-01", True),
        (date(2026, 7, 1), None, "2026-06-01", False),
        (date(2020, 1, 1), date(2026, 5, 31), "2026-06-01", False),
        (date(2020, 1, 1), date(2026, 6, 1), "2026-06-01", True),
    ],
)
def test_headcount_respects_dates(client, conn, hire, end, as_of, counted):
    dept = factories.department(conn, name="Dated")
    factories.employee(conn, dept["id"], hire_date=hire, end_date=end)
    rows = {r["department"]: r for r in client.get("/reports/headcount", params={"as_of": as_of}).json()}
    assert rows["Dated"]["headcount"] == (1 if counted else 0)


@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP", "INR", "EGP", "SAR", "AED", "QAR", "KWD", "OMR"])
def test_fx_average_over_a_year(client, currency):
    res = client.get("/reports/fx", params={"currency": currency.lower(), "start": "2025-01-01", "end": "2025-12-31"})
    assert res.status_code == 200
    assert res.json()["days"] == 365
    assert 1 <= float(res.json()["average"]) <= 2


def test_fx_unknown_currency_is_404(client):
    params = {"currency": "XYZ", "start": "2025-01-01", "end": "2025-01-31"}
    assert client.get("/reports/fx", params=params).status_code == 404
