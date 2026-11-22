from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EmployeeIn(BaseModel):
    employee_no: str = Field(pattern=r"^E\d{4,6}$")
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")
    department_id: int = Field(gt=0)
    hire_date: date
    monthly_salary: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    housing: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=2)
    transport: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=2)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("name is too short")
        return value


class EmployeeOut(EmployeeIn):
    id: int
    status: str
    end_date: date | None = None


class LeaveIn(BaseModel):
    employee_id: int = Field(gt=0)
    leave_type: Literal["annual", "sick", "unpaid"]
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=500)

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
    status: str


class PayrollRunIn(BaseModel):
    period: date

    @field_validator("period")
    @classmethod
    def first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("period must be the first day of a month")
        return value


__all__ = ["EmployeeIn", "EmployeeOut", "LeaveIn", "LeaveOut", "PayrollRunIn"]
