from datetime import date

import pytest
from app.schemas import EmployeeIn, LeaveIn, PayrollRunIn
from pydantic import ValidationError

VALID = {
    "employee_no": "E00001",
    "full_name": "Sara Example",
    "email": "sara@acme.example",
    "department_id": 1,
    "hire_date": "2024-01-15",
    "monthly_salary": "12000.00",
}


def test_valid_employee_parses():
    emp = EmployeeIn(**VALID)
    assert emp.hire_date == date(2024, 1, 15)


@pytest.mark.parametrize("employee_no", ["E1234", "E123456", "E0000"])
def test_employee_number_accepts_known_shapes(employee_no):
    assert EmployeeIn(**{**VALID, "employee_no": employee_no}).employee_no == employee_no


@pytest.mark.parametrize("employee_no", ["", "1234", "E123", "E1234567", "e12345", "EMP123", "E12 34"])
def test_employee_number_rejects_other_shapes(employee_no):
    with pytest.raises(ValidationError):
        EmployeeIn(**{**VALID, "employee_no": employee_no})


@pytest.mark.parametrize("email", ["no-at-sign", "a@b", "a b@c.com", "@acme.example", "x@acme.c"])
def test_email_rejects_malformed(email):
    with pytest.raises(ValidationError):
        EmployeeIn(**{**VALID, "email": email})


@pytest.mark.parametrize(("raw", "clean"), [("  Sara   Example ", "Sara Example"), ("Li\tWei", "Li Wei")])
def test_names_are_normalised(raw, clean):
    assert EmployeeIn(**{**VALID, "full_name": raw}).full_name == clean


@pytest.mark.parametrize("name", ["", "A", "  A  ", "x" * 121])
def test_names_reject_bad_lengths(name):
    with pytest.raises(ValidationError):
        EmployeeIn(**{**VALID, "full_name": name})


@pytest.mark.parametrize("field", ["monthly_salary", "housing", "transport"])
@pytest.mark.parametrize("value", ["-1", "-0.01", "1.001", "12345678901.00"])
def test_money_fields_reject_bad_values(field, value):
    with pytest.raises(ValidationError):
        EmployeeIn(**{**VALID, field: value})


@pytest.mark.parametrize("department_id", [0, -1])
def test_department_must_be_positive(department_id):
    with pytest.raises(ValidationError):
        EmployeeIn(**{**VALID, "department_id": department_id})


def leave_body(**overrides):
    return {"employee_id": 1, "leave_type": "annual", "start_date": "2026-11-02", "end_date": "2026-11-06", **overrides}


@pytest.mark.parametrize("leave_type", ["annual", "sick", "unpaid"])
def test_leave_types_accepted(leave_type):
    assert LeaveIn(**leave_body(leave_type=leave_type)).leave_type == leave_type


@pytest.mark.parametrize("leave_type", ["", "Annual", "maternity", "holiday"])
def test_unknown_leave_types_rejected(leave_type):
    with pytest.raises(ValidationError):
        LeaveIn(**leave_body(leave_type=leave_type))


def test_leave_range_must_be_ordered():
    with pytest.raises(ValidationError, match="before"):
        LeaveIn(**leave_body(start_date="2026-11-06", end_date="2026-11-02"))


@pytest.mark.parametrize(("end", "ok"), [("2027-01-31", True), ("2027-02-01", False)])
def test_leave_range_limited_to_90_days(end, ok):
    body = leave_body(start_date="2026-11-02", end_date=end)
    if ok:
        LeaveIn(**body)
    else:
        with pytest.raises(ValidationError):
            LeaveIn(**body)


@pytest.mark.parametrize(("period", "ok"), [("2026-11-01", True), ("2026-11-02", False), ("2026-02-28", False)])
def test_payroll_period_is_first_of_month(period, ok):
    if ok:
        assert PayrollRunIn(period=period).period.day == 1
    else:
        with pytest.raises(ValidationError):
            PayrollRunIn(period=period)
