import pytest
from psycopg import errors
from tests import factories

pytestmark = pytest.mark.db


@pytest.mark.parametrize(
    "table",
    [
        "departments",
        "employees",
        "holidays",
        "leave_types",
        "leave_requests",
        "tax_brackets",
        "payroll_runs",
        "payslips",
        "exchange_rates",
        "audit_log",
        "schema_migrations",
    ],
)
def test_table_exists(conn, table):
    assert conn.execute("SELECT to_regclass(%s) AS t", (table,)).fetchone()["t"] is not None


def test_every_migration_is_recorded(conn):
    from app.migrate import migration_files

    applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    assert applied == {p.stem for p in migration_files()}


def test_reference_data_is_present(conn):
    assert conn.execute("SELECT COUNT(*) AS n FROM exchange_rates").fetchone()["n"] > 50_000
    assert conn.execute("SELECT COUNT(*) AS n FROM leave_types").fetchone()["n"] == 3


@pytest.mark.parametrize(
    ("column", "value"),
    [("monthly_salary", -1), ("housing", -1), ("transport", -1), ("status", "retired")],
)
def test_employee_constraints(conn, column, value):
    emp = factories.employee(conn)
    with pytest.raises((errors.CheckViolation,)), conn.transaction():
        conn.execute(f"UPDATE employees SET {column} = %s WHERE id = %s", (value, emp["id"]))


def test_payslip_net_constraint(conn):
    emp = factories.employee(conn)
    run = conn.execute("INSERT INTO payroll_runs (period) VALUES ('2026-01-01') RETURNING id").fetchone()
    with pytest.raises(errors.CheckViolation), conn.transaction():
        conn.execute(
            "INSERT INTO payslips (run_id, employee_id, gross, social_ins, tax, net) VALUES (%s, %s, 100, 10, 10, 90)",
            (run["id"], emp["id"]),
        )


def test_payroll_period_must_be_first_of_month(conn):
    with pytest.raises(errors.CheckViolation), conn.transaction():
        conn.execute("INSERT INTO payroll_runs (period) VALUES ('2026-01-02')")
