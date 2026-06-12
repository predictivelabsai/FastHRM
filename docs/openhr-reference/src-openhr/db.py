"""SQLAlchemy models for OpenHR.

Kept intentionally flat — one module, no repository/service/aggregate layers. The
data shapes a city / ministry / state enterprise needs: employees, departments,
leave, attendance, payslips, expense claims, onboarding checklists. Postgres and
SQLite both work (defaults to SQLite for easy single-binary deployments).
"""

from __future__ import annotations

import enum
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DEFAULT_DB_PATH = Path(os.environ.get("OPENHR_DB", "./openhr.db")).resolve()
DEFAULT_URL = os.environ.get("OPENHR_DATABASE_URL") or f"sqlite:///{DEFAULT_DB_PATH}"


class Base(DeclarativeBase):
    pass


class LeaveKind(str, enum.Enum):
    ANNUAL = "annual"
    SICK = "sick"
    PARENTAL = "parental"
    CARE = "care"              # omsorgspermisjon (NO) and equivalents
    STUDY = "study"
    UNPAID = "unpaid"
    OTHER = "other"


class LeaveStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class ExpenseStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REIMBURSED = "reimbursed"
    REJECTED = "rejected"


class OnboardingTaskState(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"
    BLOCKED = "blocked"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))

    parent: Mapped["Department | None"] = relationship(remote_side="Department.id", back_populates="children")
    children: Mapped[list["Department"]] = relationship(back_populates="parent")
    employees: Mapped[list["Employee"]] = relationship(back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_number: Mapped[str] = mapped_column(String(20), unique=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    national_id: Mapped[str | None] = mapped_column(String(40))
    job_title: Mapped[str] = mapped_column(String(120))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[EmployeeStatus] = mapped_column(Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE)
    annual_leave_entitlement_days: Mapped[int] = mapped_column(Integer, default=25)
    base_salary_annual: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department: Mapped[Department | None] = relationship(back_populates="employees")
    manager: Mapped["Employee | None"] = relationship(remote_side="Employee.id", back_populates="reports")
    reports: Mapped[list["Employee"]] = relationship(back_populates="manager")
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(back_populates="employee",
                                                                foreign_keys="LeaveRequest.employee_id")
    attendance: Mapped[list["AttendanceRecord"]] = relationship(back_populates="employee")
    payslips: Mapped[list["Payslip"]] = relationship(back_populates="employee")
    expense_claims: Mapped[list["ExpenseClaim"]] = relationship(back_populates="employee",
                                                                foreign_keys="ExpenseClaim.employee_id")
    onboarding: Mapped["OnboardingChecklist | None"] = relationship(back_populates="employee", uselist=False)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    kind: Mapped[LeaveKind] = mapped_column(Enum(LeaveKind))
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    days: Mapped[float] = mapped_column(Numeric(5, 2))
    status: Mapped[LeaveStatus] = mapped_column(Enum(LeaveStatus), default=LeaveStatus.DRAFT)
    reason: Mapped[str | None] = mapped_column(Text)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    employee: Mapped[Employee] = relationship(foreign_keys=[employee_id], back_populates="leave_requests")
    approver: Mapped[Employee | None] = relationship(foreign_keys=[approver_id])


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_attendance_one_per_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    work_date: Mapped[date] = mapped_column(Date)
    check_in: Mapped[datetime | None] = mapped_column(DateTime)
    check_out: Mapped[datetime | None] = mapped_column(DateTime)
    hours_worked: Mapped[float | None] = mapped_column(Numeric(4, 2))
    note: Mapped[str | None] = mapped_column(Text)

    employee: Mapped[Employee] = relationship(back_populates="attendance")


class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("employee_id", "period_year", "period_month", name="uq_one_payslip_per_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    period_year: Mapped[int] = mapped_column(Integer)
    period_month: Mapped[int] = mapped_column(Integer)
    gross: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    pension: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    net: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    paid_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    employee: Mapped[Employee] = relationship(back_populates="payslips")


class ExpenseClaim(Base):
    __tablename__ = "expense_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    claim_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    description: Mapped[str] = mapped_column(Text)
    receipt_url: Mapped[str | None] = mapped_column(String(400))
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus), default=ExpenseStatus.DRAFT)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    reimbursed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    employee: Mapped[Employee] = relationship(foreign_keys=[employee_id], back_populates="expense_claims")
    approver: Mapped[Employee | None] = relationship(foreign_keys=[approver_id])


class OnboardingChecklist(Base):
    __tablename__ = "onboarding_checklists"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    employee: Mapped[Employee] = relationship(back_populates="onboarding")
    tasks: Mapped[list["OnboardingTask"]] = relationship(back_populates="checklist", cascade="all,delete-orphan")


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("onboarding_checklists.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    state: Mapped[OnboardingTaskState] = mapped_column(Enum(OnboardingTaskState), default=OnboardingTaskState.PENDING)
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    owner: Mapped[str | None] = mapped_column(String(40))  # hr | manager | employee | it

    checklist: Mapped[OnboardingChecklist] = relationship(back_populates="tasks")


_engine = None


def get_engine(url: str | None = None) -> sa.Engine:
    global _engine
    if _engine is not None and url is None:
        return _engine
    _engine = sa.create_engine(url or DEFAULT_URL, future=True, pool_pre_ping=True)
    return _engine


def create_all(engine: sa.Engine | None = None) -> None:
    (engine or get_engine()).begin().__enter__()  # sanity: open a connection once
    Base.metadata.create_all(engine or get_engine())


def drop_all(engine: sa.Engine | None = None) -> None:
    Base.metadata.drop_all(engine or get_engine())
