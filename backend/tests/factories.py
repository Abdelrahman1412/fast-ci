"""Row builders for tests. Every value has a sensible default."""

from __future__ import annotations

import itertools
from datetime import date
from decimal import Decimal

import psycopg

_seq = itertools.count(1)


def department(conn: psycopg.Connection, name: str | None = None) -> dict:
    n = next(_seq)
    return conn.execute(
        "INSERT INTO departments (name, cost_center) VALUES (%s, %s) RETURNING *",
        (name or f"Department {n}", f"CC-{n:03d}"),
    ).fetchone()


def employee(conn: psycopg.Connection, department_id: int | None = None, **overrides) -> dict:
    n = next(_seq)
    if department_id is None:
        department_id = department(conn)["id"]
    row = {
        "employee_no": f"E{n:05d}",
        "full_name": f"Employee {n}",
        "email": f"employee{n}@acme.example",
        "department_id": department_id,
        "hire_date": date(2022, 1, 1),
        "end_date": None,
        "monthly_salary": Decimal("12000"),
        "housing": Decimal("3000"),
        "transport": Decimal("1000"),
        "status": "active",
    }
    row.update(overrides)
    return conn.execute(
        """INSERT INTO employees (employee_no, full_name, email, department_id, hire_date, end_date,
                                  monthly_salary, housing, transport, status)
           VALUES (%(employee_no)s, %(full_name)s, %(email)s, %(department_id)s, %(hire_date)s, %(end_date)s,
                   %(monthly_salary)s, %(housing)s, %(transport)s, %(status)s)
           RETURNING *""",
        row,
    ).fetchone()


def employees_bulk(conn: psycopg.Connection, count: int, department_id: int | None = None, **overrides) -> int:
    """Insert `count` employees in one statement. Returns the department id."""
    if department_id is None:
        department_id = department(conn)["id"]
    start = next(_seq) * 10_000
    conn.execute(
        """INSERT INTO employees (employee_no, full_name, email, department_id, hire_date, monthly_salary,
                                  housing, transport)
           SELECT 'E' || (%(start)s + g), 'Bulk ' || g, 'bulk' || (%(start)s + g) || '@acme.example',
                  %(dept)s, %(hire)s, 5000 + (g %% 40) * 1000, 1500, 500
           FROM generate_series(1, %(count)s) AS g""",
        {"start": start, "dept": department_id, "count": count, "hire": overrides.get("hire_date", date(2020, 3, 1))},
    )
    return department_id
