from datetime import date

import pytest
from tests import factories

pytestmark = pytest.mark.db


def request(client, emp_id, start, end, leave_type="annual", **params):
    return client.post(
        "/leave-requests",
        json={"employee_id": emp_id, "leave_type": leave_type, "start_date": start, "end_date": end},
        params=params,
    )


@pytest.fixture
def emp(conn):
    return factories.employee(conn, hire_date=date(2020, 1, 1))


@pytest.mark.parametrize(
    ("start", "end", "weekend", "days"),
    [
        ("2026-11-02", "2026-11-06", "sat-sun", 5),
        ("2026-11-02", "2026-11-08", "sat-sun", 5),
        ("2026-11-02", "2026-11-08", "fri-sat", 5),
        ("2026-11-05", "2026-11-05", "sat-sun", 1),
        ("2026-11-30", "2026-12-04", "sat-sun", 4),  # 2 December is a holiday
        ("2026-12-28", "2027-01-01", "sat-sun", 4),  # 1 January is a holiday
    ],
)
def test_days_are_counted_server_side(client, emp, start, end, weekend, days):
    res = request(client, emp["id"], start, end, weekend=weekend)
    assert res.status_code == 201, res.text
    assert res.json()["days"] == days
    assert res.json()["status"] == "pending"


def test_weekend_only_request_is_rejected(client, emp):
    assert request(client, emp["id"], "2026-11-07", "2026-11-08").status_code == 422


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-11-04", "2026-11-04"),
        ("2026-11-01", "2026-11-03"),
        ("2026-11-06", "2026-11-12"),
        ("2026-10-26", "2026-11-20"),
    ],
)
def test_overlaps_are_rejected(client, emp, start, end):
    assert request(client, emp["id"], "2026-11-03", "2026-11-06").status_code == 201
    assert request(client, emp["id"], start, end).status_code == 409


def test_rejected_requests_do_not_block(client, emp):
    first = request(client, emp["id"], "2026-11-03", "2026-11-06").json()
    assert client.post(f"/leave-requests/{first['id']}/reject").status_code == 200
    assert request(client, emp["id"], "2026-11-03", "2026-11-06").status_code == 201


@pytest.mark.parametrize(
    ("action", "from_status", "code"),
    [
        ("approve", "pending", 200),
        ("reject", "pending", 200),
        ("cancel", "pending", 200),
        ("approve", "approved", 409),
        ("reject", "approved", 409),
        ("cancel", "approved", 200),
        ("approve", "rejected", 409),
        ("cancel", "rejected", 409),
        ("approve", "cancelled", 409),
        ("cancel", "cancelled", 409),
    ],
)
def test_status_transitions(client, conn, emp, action, from_status, code):
    leave = request(client, emp["id"], "2026-11-02", "2026-11-03").json()
    conn.execute("UPDATE leave_requests SET status = %s WHERE id = %s", (from_status, leave["id"]))
    assert client.post(f"/leave-requests/{leave['id']}/{action}").status_code == code


def test_transition_on_missing_request_is_404(client):
    assert client.post("/leave-requests/424242/approve").status_code == 404


def test_balance_is_enforced(client, conn):
    new_joiner = factories.employee(conn, hire_date=date(2026, 10, 1))
    # Hired in October: 3 months accrued by year end = 7 days of annual leave.
    assert request(client, new_joiner["id"], "2026-11-02", "2026-11-10").status_code == 201
    ok = request(client, new_joiner["id"], "2026-11-02", "2026-11-06").json()  # overlapping, rejected below
    assert ok.get("detail") == "overlaps an existing request"


def test_insufficient_balance(client, conn):
    new_joiner = factories.employee(conn, hire_date=date(2026, 10, 1))
    first = request(client, new_joiner["id"], "2026-11-02", "2026-11-06").json()
    client.post(f"/leave-requests/{first['id']}/approve")
    res = request(client, new_joiner["id"], "2026-11-16", "2026-11-20")
    assert res.status_code == 422
    assert res.json()["detail"] == "insufficient balance"


def test_unpaid_leave_ignores_balance(client, conn):
    new_joiner = factories.employee(conn, hire_date=date(2026, 10, 1))
    assert request(client, new_joiner["id"], "2026-11-02", "2026-11-27", leave_type="unpaid").status_code == 201


def test_terminated_employee_cannot_request(client, conn):
    gone = factories.employee(conn, status="terminated", end_date=date(2026, 6, 30))
    assert request(client, gone["id"], "2026-11-02", "2026-11-03").status_code == 409


@pytest.mark.parametrize("status", ["pending", "approved", "rejected"])
def test_list_by_status(client, conn, emp, status):
    leave = request(client, emp["id"], "2026-11-02", "2026-11-03").json()
    conn.execute("UPDATE leave_requests SET status = %s WHERE id = %s", (status, leave["id"]))
    rows = client.get("/leave-requests", params={"employee_id": emp["id"], "status": status}).json()
    assert [r["id"] for r in rows] == [leave["id"]]
