"""Acme HR demo API: employees, leave and payroll runs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

from app import leave, payroll
from app.db import get_conn
from app.schemas import (
    INT4_MAX,
    DepartmentIn,
    DepartmentOut,
    EmployeeIn,
    EmployeeOut,
    EmployeeStatus,
    ErrorOut,
    IsoDate,
    LeaveIn,
    LeaveOut,
    LeaveStatus,
    PayrollRunIn,
    TerminateIn,
)

app = FastAPI(title="Acme HR demo API")
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
PathId = Annotated[int, Path(ge=1, le=INT4_MAX)]
QueryId = Annotated[int | None, Query(ge=1, le=INT4_MAX)]

# Status codes: 422 means the request breaks the published schema (FastAPI's
# validation shape). A request that fits the schema but breaks a business rule
# gets 409; a referenced record that does not exist gets 404.
NOT_FOUND = {404: {"model": ErrorOut, "description": "Not found"}}
BAD_BODY = {400: {"model": ErrorOut, "description": "Body is not valid JSON"}}
CONFLICT = {409: {"model": ErrorOut, "description": "Breaks a business rule"}}


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    headers = dict(exc.headers or {})
    if exc.status_code == 405:
        # Starlette lists only the first matching route's methods; list every route on the path.
        allowed = {
            method
            for route in request.app.router.routes
            if isinstance(route, APIRoute) and route.matches(request.scope)[0] != Match.NONE
            for method in route.methods
        }
        headers["Allow"] = ", ".join(sorted(allowed))
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=headers)


def audit(conn: psycopg.Connection, entity: str, entity_id: int, action: str) -> None:
    conn.execute("INSERT INTO audit_log (entity, entity_id, action) VALUES (%s, %s, %s)", (entity, entity_id, action))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/departments", response_model=list[DepartmentOut])
def list_departments(conn: Conn) -> list[dict]:
    return conn.execute("SELECT id, name, cost_center FROM departments ORDER BY name").fetchall()


@app.post("/departments", response_model=DepartmentOut, status_code=201, responses={**BAD_BODY, **CONFLICT})
def create_department(body: DepartmentIn, conn: Conn) -> dict:
    name = body.name.strip()
    with conn.transaction():
        try:
            row = conn.execute(
                "INSERT INTO departments (name, cost_center) VALUES (%s, %s) RETURNING id, name, cost_center",
                (name, body.cost_center),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "department exists") from None
    return row


@app.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    conn: Conn,
    department_id: QueryId = None,
    status: EmployeeStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    sql = "SELECT * FROM employees WHERE TRUE"
    args: list = []
    if department_id is not None:
        sql += " AND department_id = %s"
        args.append(department_id)
    if status is not None:
        sql += " AND status = %s"
        args.append(status)
    sql += " ORDER BY employee_no LIMIT %s"
    args.append(limit)
    return conn.execute(sql, args).fetchall()


@app.get("/employees/{employee_id}", response_model=EmployeeOut, responses=NOT_FOUND)
def get_employee(employee_id: PathId, conn: Conn) -> dict:
    row = conn.execute("SELECT * FROM employees WHERE id = %s", (employee_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "employee not found")
    return row


@app.post("/employees", response_model=EmployeeOut, status_code=201, responses={**BAD_BODY, **NOT_FOUND, **CONFLICT})
def create_employee(body: EmployeeIn, conn: Conn) -> dict:
    with conn.transaction():
        try:
            row = conn.execute(
                """
                INSERT INTO employees (employee_no, full_name, email, department_id, hire_date,
                                       monthly_salary, housing, transport)
                VALUES (%(employee_no)s, %(full_name)s, %(email)s, %(department_id)s, %(hire_date)s,
                        %(monthly_salary)s, %(housing)s, %(transport)s)
                RETURNING *
                """,
                body.model_dump(),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "employee number or email already used") from None
        except psycopg.errors.ForeignKeyViolation:
            raise HTTPException(404, "department not found") from None
        audit(conn, "employee", row["id"], "create")
    return row


@app.post(
    "/employees/{employee_id}/terminate", response_model=EmployeeOut, responses={**BAD_BODY, **NOT_FOUND, **CONFLICT}
)
def terminate_employee(employee_id: PathId, body: TerminateIn, conn: Conn) -> dict:
    end = body.end_date
    with conn.transaction():
        emp = get_employee(employee_id, conn)
        if emp["status"] == "terminated":
            raise HTTPException(409, "already terminated")
        if end < emp["hire_date"]:
            raise HTTPException(409, "end_date is before hire_date")
        row = conn.execute(
            "UPDATE employees SET status = 'terminated', end_date = %s WHERE id = %s RETURNING *",
            (end, employee_id),
        ).fetchone()
        audit(conn, "employee", employee_id, "terminate")
    return row


def _holidays(conn: psycopg.Connection, start: date, end: date) -> list[date]:
    rows = conn.execute("SELECT day FROM holidays WHERE day BETWEEN %s AND %s", (start, end)).fetchall()
    return [r["day"] for r in rows]


@app.post("/leave-requests", response_model=LeaveOut, status_code=201, responses={**BAD_BODY, **NOT_FOUND, **CONFLICT})
def create_leave(body: LeaveIn, conn: Conn, weekend: Literal["sat-sun", "fri-sat", "fri"] = "sat-sun") -> dict:
    with conn.transaction():
        emp = get_employee(body.employee_id, conn)
        if emp["status"] == "terminated":
            raise HTTPException(409, "employee is terminated")
        days = leave.working_days(
            body.start_date, body.end_date, weekend=weekend, holidays=_holidays(conn, body.start_date, body.end_date)
        )
        if days == 0:
            raise HTTPException(409, "request covers no working days")
        overlap = conn.execute(
            """SELECT 1 FROM leave_requests WHERE employee_id = %s AND status IN ('pending', 'approved')
               AND start_date <= %s AND end_date >= %s""",
            (body.employee_id, body.end_date, body.start_date),
        ).fetchone()
        if overlap:
            raise HTTPException(409, "overlaps an existing request")
        if body.leave_type != "unpaid":
            annual = conn.execute("SELECT annual_days FROM leave_types WHERE code = %s", (body.leave_type,)).fetchone()[
                "annual_days"
            ]
            taken = conn.execute(
                """SELECT COALESCE(SUM(days), 0) AS taken FROM leave_requests
                   WHERE employee_id = %s AND leave_type = %s AND status = 'approved'
                   AND EXTRACT(YEAR FROM start_date) = %s""",
                (body.employee_id, body.leave_type, body.start_date.year),
            ).fetchone()["taken"]
            year_end = date(body.start_date.year, 12, 31)
            if days > leave.balance(annual, emp["hire_date"], year_end, int(taken)):
                raise HTTPException(409, "insufficient balance")
        row = conn.execute(
            """INSERT INTO leave_requests (employee_id, leave_type, start_date, end_date, days, reason)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
            (body.employee_id, body.leave_type, body.start_date, body.end_date, days, body.reason),
        ).fetchone()
        audit(conn, "leave", row["id"], "create")
    return row


def _transition(conn: psycopg.Connection, leave_id: int, target: str, allowed: set[str]) -> dict:
    with conn.transaction():
        row = conn.execute("SELECT * FROM leave_requests WHERE id = %s FOR UPDATE", (leave_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "leave request not found")
        if row["status"] not in allowed:
            raise HTTPException(409, f"cannot move from {row['status']} to {target}")
        row = conn.execute(
            "UPDATE leave_requests SET status = %s WHERE id = %s RETURNING *", (target, leave_id)
        ).fetchone()
        audit(conn, "leave", leave_id, target)
    return row


@app.post("/leave-requests/{leave_id}/approve", response_model=LeaveOut, responses={**NOT_FOUND, **CONFLICT})
def approve_leave(leave_id: PathId, conn: Conn) -> dict:
    return _transition(conn, leave_id, "approved", {"pending"})


@app.post("/leave-requests/{leave_id}/reject", response_model=LeaveOut, responses={**NOT_FOUND, **CONFLICT})
def reject_leave(leave_id: PathId, conn: Conn) -> dict:
    return _transition(conn, leave_id, "rejected", {"pending"})


@app.post("/leave-requests/{leave_id}/cancel", response_model=LeaveOut, responses={**NOT_FOUND, **CONFLICT})
def cancel_leave(leave_id: PathId, conn: Conn) -> dict:
    return _transition(conn, leave_id, "cancelled", {"pending", "approved"})


@app.get("/leave-requests", response_model=list[LeaveOut])
def list_leave(conn: Conn, employee_id: QueryId = None, status: LeaveStatus | None = None) -> list[dict]:
    sql = "SELECT * FROM leave_requests WHERE TRUE"
    args: list = []
    if employee_id is not None:
        sql += " AND employee_id = %s"
        args.append(employee_id)
    if status is not None:
        sql += " AND status = %s"
        args.append(status)
    return conn.execute(sql + " ORDER BY start_date, id", args).fetchall()


def _unpaid_days(conn: psycopg.Connection, period: date) -> dict[int, int]:
    last = period.replace(day=payroll.days_in_month(period))
    rows = conn.execute(
        """SELECT employee_id,
                  SUM((LEAST(end_date, %(last)s) - GREATEST(start_date, %(first)s)) + 1) AS days
           FROM leave_requests
           WHERE leave_type = 'unpaid' AND status = 'approved'
             AND start_date <= %(last)s AND end_date >= %(first)s
           GROUP BY employee_id""",
        {"first": period, "last": last},
    ).fetchall()
    return {r["employee_id"]: int(r["days"]) for r in rows}


@app.post("/payroll-runs", status_code=201, responses={**BAD_BODY, **CONFLICT})
def create_payroll_run(body: PayrollRunIn, conn: Conn) -> dict:
    period = body.period
    last = period.replace(day=payroll.days_in_month(period))
    with conn.transaction():
        try:
            run = conn.execute(
                "INSERT INTO payroll_runs (period) VALUES (%s) RETURNING id, period, status", (period,)
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "a run already exists for this period") from None
        brackets = tuple(
            (r["lower_bound"], r["rate"]) for r in conn.execute("SELECT lower_bound, rate FROM tax_brackets")
        )
        unpaid = _unpaid_days(conn, period)
        employees = conn.execute(
            """SELECT id, hire_date, end_date, monthly_salary, housing, transport FROM employees
               WHERE hire_date <= %s AND (end_date IS NULL OR end_date >= %s)""",
            (last, period),
        ).fetchall()
        rows = []
        for emp in employees:
            slip = payroll.compute_payslip(
                period=period,
                basic=emp["monthly_salary"],
                housing=emp["housing"],
                transport=emp["transport"],
                hire_date=emp["hire_date"],
                end_date=emp["end_date"],
                unpaid_days=unpaid.get(emp["id"], 0),
                brackets=brackets,
            )
            rows.append((run["id"], emp["id"], slip.gross, slip.unpaid_days, slip.social_ins, slip.tax, slip.net))
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO payslips (run_id, employee_id, gross, unpaid_days, social_ins, tax, net)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                rows,
            )
        totals = conn.execute(
            "SELECT COUNT(*) AS payslips, COALESCE(SUM(gross), 0) AS gross, COALESCE(SUM(net), 0) AS net "
            "FROM payslips WHERE run_id = %s",
            (run["id"],),
        ).fetchone()
        audit(conn, "payroll_run", run["id"], "create")
    return {**run, **totals}


@app.post("/payroll-runs/{run_id}/approve", responses=CONFLICT)
def approve_run(run_id: PathId, conn: Conn) -> dict:
    with conn.transaction():
        row = conn.execute(
            "UPDATE payroll_runs SET status = 'approved' WHERE id = %s AND status = 'draft' RETURNING id, status",
            (run_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(409, "run not found or not in draft")
    return row


@app.get("/payroll-runs/{run_id}/payslips")
def list_payslips(run_id: PathId, conn: Conn) -> list[dict]:
    return conn.execute(
        "SELECT employee_id, gross, unpaid_days, social_ins, tax, net FROM payslips "
        "WHERE run_id = %s ORDER BY employee_id",
        (run_id,),
    ).fetchall()


@app.get("/reports/headcount")
def headcount(conn: Conn, as_of: IsoDate | None = None) -> list[dict]:
    day = as_of or date.today()
    return conn.execute(
        """SELECT d.name AS department, COUNT(e.id) AS headcount,
                  COALESCE(SUM(e.monthly_salary + e.housing + e.transport), 0) AS monthly_cost
           FROM departments d
           LEFT JOIN employees e ON e.department_id = d.id
                AND e.hire_date <= %s AND (e.end_date IS NULL OR e.end_date >= %s)
           GROUP BY d.name ORDER BY d.name""",
        (day, day),
    ).fetchall()


@app.get("/reports/fx", responses=NOT_FOUND)
def fx(conn: Conn, currency: Annotated[str, Query(pattern=r"^[A-Za-z]{3}$")], start: IsoDate, end: IsoDate) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS days, AVG(rate) AS average FROM exchange_rates "
        "WHERE currency = %s AND day BETWEEN %s AND %s",
        (currency.upper(), start, end),
    ).fetchone()
    if row["days"] == 0:
        raise HTTPException(404, "no rates for that range")
    return {"currency": currency.upper(), "days": row["days"], "average": round(Decimal(row["average"]), 6)}
