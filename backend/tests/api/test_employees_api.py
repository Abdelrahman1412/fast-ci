from datetime import date

import pytest
from tests import factories

pytestmark = pytest.mark.db


def body(dept_id, n=1, **overrides):
    return {
        "employee_no": f"E{n:05d}",
        "full_name": f"Person {n}",
        "email": f"person{n}@acme.example",
        "department_id": dept_id,
        "hire_date": "2025-03-01",
        "monthly_salary": "15000.00",
        **overrides,
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_fetch_employee(client, conn):
    dept = factories.department(conn)
    created = client.post("/employees", json=body(dept["id"]))
    assert created.status_code == 201, created.text
    fetched = client.get(f"/employees/{created.json()['id']}").json()
    assert fetched["employee_no"] == "E00001"
    assert fetched["status"] == "active"


def test_create_writes_an_audit_row(client, conn):
    dept = factories.department(conn)
    emp_id = client.post("/employees", json=body(dept["id"])).json()["id"]
    row = conn.execute("SELECT action FROM audit_log WHERE entity = 'employee' AND entity_id = %s", (emp_id,))
    assert row.fetchone()["action"] == "create"


@pytest.mark.parametrize("field", ["employee_no", "email"])
def test_duplicates_are_rejected(client, conn, field):
    dept = factories.department(conn)
    assert client.post("/employees", json=body(dept["id"], 1)).status_code == 201
    clash = body(dept["id"], 2, **{field: body(dept["id"], 1)[field]})
    assert client.post("/employees", json=clash).status_code == 409


def test_unknown_department_is_422(client):
    assert client.post("/employees", json=body(999_999)).status_code == 422


@pytest.mark.parametrize(
    "bad",
    [
        {"employee_no": "X1"},
        {"email": "nope"},
        {"monthly_salary": "-5"},
        {"hire_date": "2025-13-01"},
        {"full_name": ""},
        {"department_id": 0},
    ],
)
def test_validation_errors(client, conn, bad):
    dept = factories.department(conn)
    assert client.post("/employees", json=body(dept["id"], **bad)).status_code == 422


def test_missing_employee_is_404(client):
    assert client.get("/employees/987654").status_code == 404


@pytest.mark.parametrize("count", [0, 1, 7, 25])
def test_list_filters_by_department(client, conn, count):
    dept = factories.department(conn)
    other = factories.department(conn)
    for _ in range(count):
        factories.employee(conn, dept["id"])
    factories.employee(conn, other["id"])
    rows = client.get("/employees", params={"department_id": dept["id"]}).json()
    assert len(rows) == count
    assert {r["department_id"] for r in rows} <= {dept["id"]}


@pytest.mark.parametrize("status", ["active", "on_leave", "terminated"])
def test_list_filters_by_status(client, conn, status):
    dept = factories.department(conn)
    factories.employee(conn, dept["id"], status=status, end_date=date(2026, 1, 1) if status == "terminated" else None)
    rows = client.get("/employees", params={"department_id": dept["id"], "status": status}).json()
    assert [r["status"] for r in rows] == [status]


@pytest.mark.parametrize("limit", [0, 501])
def test_list_limit_is_bounded(client, limit):
    assert client.get("/employees", params={"limit": limit}).status_code == 422


def test_terminate(client, conn):
    emp = factories.employee(conn)
    res = client.post(f"/employees/{emp['id']}/terminate", json={"end_date": "2026-10-31"})
    assert res.status_code == 200
    assert res.json()["status"] == "terminated"
    assert client.post(f"/employees/{emp['id']}/terminate", json={"end_date": "2026-10-31"}).status_code == 409


def test_terminate_before_hire_is_rejected(client, conn):
    emp = factories.employee(conn, hire_date=date(2026, 5, 1))
    assert client.post(f"/employees/{emp['id']}/terminate", json={"end_date": "2026-04-30"}).status_code == 422


def test_departments_round_trip(client):
    assert client.post("/departments", json={"name": "Finance", "cost_center": "CC-100"}).status_code == 201
    assert client.post("/departments", json={"name": "Finance"}).status_code == 409
    assert "Finance" in [d["name"] for d in client.get("/departments").json()]


def test_department_name_required(client):
    assert client.post("/departments", json={"name": "  "}).status_code == 422


@pytest.mark.parametrize("n", range(10))
def test_rollback_isolates_tests(client, conn, n):
    """Each run sees an empty employees table for its own department, whatever ran before."""
    dept = factories.department(conn, name="Isolation")
    factories.employee(conn, dept["id"])
    assert len(client.get("/employees", params={"department_id": dept["id"]}).json()) == 1
