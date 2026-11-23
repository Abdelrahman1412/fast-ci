from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, WithJsonSchema, field_validator, model_validator

_ISO_DATE = re.compile(r"^[1-9]\d{3}-\d{2}-\d{2}$")
# Published patterns avoid \s: regex engines disagree on which Unicode characters it
# matches, so a client validating against the schema would disagree with the server.
# Postgres text cannot hold a NUL byte; letting one through turns a bad request into a 500.
NO_NUL = r"^[^\x00]*$"
_MONEY = r"^\d{1,10}(\.\d{1,2})?$"


def _iso_date_only(value: Any) -> Any:
    # Lax parsing reads 0 as 1970-01-01 (a Unix timestamp). Dates must be ISO strings.
    if isinstance(value, date) or (isinstance(value, str) and _ISO_DATE.match(value)):
        return value
    raise ValueError("expected an ISO date, YYYY-MM-DD, year 1000 or later")


IsoDate = Annotated[
    date,
    BeforeValidator(_iso_date_only),
    WithJsonSchema({"type": "string", "format": "date", "pattern": _ISO_DATE.pattern}),
]


def _exact_money(value: Any) -> Any:
    # A float such as 0.1 is not exact. Money comes as a whole number or a decimal string.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float):
        raise ValueError('send money as an integer or a decimal string such as "1500.50"')
    if isinstance(value, str) and not re.match(_MONEY, value):
        raise ValueError("expected a decimal string with at most 2 decimal places")
    return value


# The default schema for Decimal says "any string". Publish what is actually accepted.
Money = Annotated[
    Decimal,
    BeforeValidator(_exact_money),
    Field(ge=0, max_digits=12, decimal_places=2),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "integer", "minimum": 0, "maximum": 9_999_999_999},
                {"type": "string", "pattern": _MONEY},
            ]
        }
    ),
]


# Ids are Postgres integers. A larger number fails in the database as a 500, so refuse it here.
INT4_MAX = 2_147_483_647
RowId = Annotated[int, Field(ge=1, le=INT4_MAX)]


class ErrorOut(BaseModel):
    detail: str


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[^\x00]*[^\x00-\x20][^\x00]*$")
    cost_center: str = Field(default="CC-000", max_length=20, pattern=NO_NUL)


class DepartmentOut(BaseModel):
    id: int
    name: str
    cost_center: str


class TerminateIn(BaseModel):
    end_date: IsoDate


class EmployeeIn(BaseModel):
    employee_no: str = Field(pattern=r"^E\d{4,6}$")
    full_name: str = Field(min_length=2, max_length=120, pattern=r"^[^\x00]*[^\x00-\x20][^\x00]*[^\x00-\x20][^\x00]*$")
    email: str = Field(pattern=r"^[^@\x00-\x20]+@[^@\x00-\x20]+\.[a-z]{2,}$")
    department_id: RowId
    hire_date: IsoDate
    monthly_salary: Money
    housing: Money = Decimal(0)
    transport: Money = Decimal(0)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = " ".join(re.findall(r"[^\x00-\x20]+", value))
        if len(value) < 2:
            raise ValueError("name is too short")
        return value


EmployeeStatus = Literal["active", "on_leave", "terminated"]
LeaveStatus = Literal["pending", "approved", "rejected", "cancelled"]


class EmployeeOut(EmployeeIn):
    id: int
    status: EmployeeStatus
    end_date: IsoDate | None = None


class LeaveIn(BaseModel):
    employee_id: RowId
    leave_type: Literal["annual", "sick", "unpaid"]
    start_date: IsoDate
    end_date: IsoDate
    reason: str = Field(default="", max_length=500, pattern=NO_NUL)

    @model_validator(mode="after")
    def check_range(self) -> LeaveIn:
        if self.end_date < self.start_date:
            raise ValueError("end_date is before start_date")
        if (self.end_date - self.start_date).days > 90:
            raise ValueError("a single request cannot exceed 90 days")
        return self


class LeaveOut(LeaveIn):
    id: int
    days: int
    status: LeaveStatus


class PayrollRunIn(BaseModel):
    period: Annotated[
        IsoDate, WithJsonSchema({"type": "string", "format": "date", "pattern": r"^[1-9]\d{3}-\d{2}-01$"})
    ]

    @field_validator("period")
    @classmethod
    def first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("period must be the first day of a month")
        return value


__all__ = [
    "EmployeeStatus",
    "LeaveStatus",
    "INT4_MAX",
    "RowId",
    "DepartmentIn",
    "DepartmentOut",
    "EmployeeIn",
    "EmployeeOut",
    "ErrorOut",
    "IsoDate",
    "LeaveIn",
    "LeaveOut",
    "Money",
    "PayrollRunIn",
    "TerminateIn",
]
