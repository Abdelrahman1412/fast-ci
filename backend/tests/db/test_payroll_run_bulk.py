"""Large payroll runs. These are the slowest tests in the suite on purpose:
one file like this decides the length of whichever shard it lands on."""

from datetime import date
from decimal import Decimal

import pytest
from tests import factories

pytestmark = [pytest.mark.db, pytest.mark.slow]


@pytest.mark.parametrize("headcount", [2000, 5000, 10000, 15000, 20000, 30000])
def test_bulk_run_produces_one_payslip_each(client, conn, headcount):
    dept = factories.employees_bulk(conn, headcount)
    res = client.post("/payroll-runs", json={"period": "2026-04-01"})
    assert res.status_code == 201
    count = conn.execute(
        """SELECT COUNT(*) AS n FROM payslips p JOIN employees e ON e.id = p.employee_id
           WHERE p.run_id = %s AND e.department_id = %s""",
        (res.json()["id"], dept),
    ).fetchone()["n"]
    assert count == headcount


@pytest.mark.parametrize("headcount", [10000, 20000])
def test_bulk_run_totals_reconcile(client, conn, headcount):
    factories.employees_bulk(conn, headcount)
    run = client.post("/payroll-runs", json={"period": "2026-05-01"}).json()
    sums = conn.execute(
        "SELECT SUM(gross) AS gross, SUM(net) AS net, SUM(social_ins + tax) AS deductions "
        "FROM payslips WHERE run_id = %s",
        (run["id"],),
    ).fetchone()
    assert sums["gross"] - sums["deductions"] == sums["net"]
    assert Decimal(str(run["gross"])) == sums["gross"]


@pytest.mark.parametrize("months", [3, 6, 12])
def test_consecutive_runs(client, conn, months):
    factories.employees_bulk(conn, 4000, hire_date=date(2020, 1, 1))
    for m in range(1, months + 1):
        assert client.post("/payroll-runs", json={"period": f"2026-{m:02d}-01"}).status_code == 201
    runs = conn.execute("SELECT COUNT(*) AS n FROM payroll_runs").fetchone()["n"]
    assert runs == months
