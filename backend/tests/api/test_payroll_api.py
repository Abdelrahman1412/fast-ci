from datetime import date
from decimal import Decimal

import pytest
from tests import factories

pytestmark = pytest.mark.db


def run(client, period="2026-04-01"):
    return client.post("/payroll-runs", json={"period": period})


def test_run_covers_active_employees(client, conn):
    dept = factories.department(conn)
    for _ in range(5):
        factories.employee(conn, dept["id"])
    res = run(client)
    assert res.status_code == 201, res.text
    slips = client.get(f"/payroll-runs/{res.json()['id']}/payslips").json()
    assert len(slips) >= 5


def test_one_run_per_period(client):
    assert run(client).status_code == 201
    assert run(client).status_code == 409


def test_period_must_be_first_of_month(client):
    assert run(client, "2026-04-02").status_code == 422


@pytest.mark.parametrize(
    ("hire", "end", "included"),
    [
        (date(2020, 1, 1), None, True),
        (date(2026, 4, 30), None, True),
        (date(2026, 5, 1), None, False),
        (date(2020, 1, 1), date(2026, 4, 1), True),
        (date(2020, 1, 1), date(2026, 3, 31), False),
    ],
)
def test_joiners_and_leavers(client, conn, hire, end, included):
    emp = factories.employee(conn, hire_date=hire, end_date=end, status="terminated" if end else "active")
    slips = client.get(f"/payroll-runs/{run(client).json()['id']}/payslips").json()
    assert (emp["id"] in {s["employee_id"] for s in slips}) is included


def test_net_equals_gross_minus_deductions(client, conn):
    factories.employee(conn, monthly_salary=Decimal("30000"), housing=Decimal("7500"))
    slips = client.get(f"/payroll-runs/{run(client).json()['id']}/payslips").json()
    for s in slips:
        assert Decimal(s["net"]) == Decimal(s["gross"]) - Decimal(s["social_ins"]) - Decimal(s["tax"])


def test_unpaid_leave_is_docked(client, conn):
    emp = factories.employee(conn, monthly_salary=Decimal("12000"), housing=Decimal("0"), transport=Decimal("0"))
    conn.execute(
        """INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, days, status)
           VALUES (%s, 'unpaid', '2026-03-28', '2026-04-03', 5, 'approved')""",
        (emp["id"],),
    )
    slips = client.get(f"/payroll-runs/{run(client).json()['id']}/payslips").json()
    mine = next(s for s in slips if s["employee_id"] == emp["id"])
    assert mine["unpaid_days"] == 3
    assert Decimal(mine["gross"]) == Decimal("10800.00")


@pytest.mark.parametrize("status", ["draft"])
def test_approve_once(client, status):
    run_id = run(client).json()["id"]
    assert client.post(f"/payroll-runs/{run_id}/approve").json()["status"] == "approved"
    assert client.post(f"/payroll-runs/{run_id}/approve").status_code == 409


@pytest.mark.parametrize("month", range(1, 13))
def test_a_run_for_every_month(client, conn, month):
    factories.employee(conn, hire_date=date(2019, 1, 1))
    res = run(client, f"2025-{month:02d}-01")
    assert res.status_code == 201
    assert res.json()["payslips"] >= 1
