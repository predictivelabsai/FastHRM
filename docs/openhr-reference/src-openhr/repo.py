"""Query helpers — thin wrappers around Session so views stay readable.

Convention: everything takes an explicit SA Session, returns dataclasses or ORM
objects. No globals. No implicit sessions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from .db import (
    AttendanceRecord, Department, Employee, EmployeeStatus, ExpenseClaim, ExpenseStatus,
    LeaveKind, LeaveRequest, LeaveStatus, OnboardingChecklist, OnboardingTask,
    OnboardingTaskState, Payslip,
)


# -------- Employees ---------------------------------------------------------

def list_employees(session: Session, *, status: EmployeeStatus | None = None,
                   department_id: int | None = None, search: str | None = None) -> list[Employee]:
    q = sa.select(Employee).options(joinedload(Employee.department), joinedload(Employee.manager))
    if status:
        q = q.where(Employee.status == status)
    if department_id:
        q = q.where(Employee.department_id == department_id)
    if search:
        like = f"%{search.lower()}%"
        q = q.where(sa.func.lower(Employee.first_name + " " + Employee.last_name).like(like))
    q = q.order_by(Employee.last_name, Employee.first_name)
    return list(session.scalars(q).all())


def get_employee(session: Session, employee_id: int) -> Employee | None:
    return session.get(
        Employee, employee_id,
        options=[joinedload(Employee.department), joinedload(Employee.manager),
                 joinedload(Employee.onboarding)],
    )


def org_tree(session: Session) -> list[tuple[Employee, list["OrgNode"]]]:
    """Return a list of (root_employee, subtree) pairs for the org chart view."""
    employees = list(session.scalars(sa.select(Employee)).unique().all())
    by_id = {e.id: e for e in employees}
    roots = [e for e in employees if e.manager_id is None]
    return [(root, _build_subtree(root, by_id)) for root in roots]


def _build_subtree(node: Employee, by_id: dict[int, Employee]) -> list:
    direct_reports = [e for e in by_id.values() if e.manager_id == node.id]
    return [(r, _build_subtree(r, by_id)) for r in direct_reports]


OrgNode = tuple[Employee, list["OrgNode"]]  # typing helper


# -------- Leave -------------------------------------------------------------

def list_leave_requests(session: Session, *, employee_id: int | None = None,
                        status: LeaveStatus | None = None) -> list[LeaveRequest]:
    q = sa.select(LeaveRequest).options(
        joinedload(LeaveRequest.employee), joinedload(LeaveRequest.approver)
    ).order_by(LeaveRequest.from_date.desc())
    if employee_id:
        q = q.where(LeaveRequest.employee_id == employee_id)
    if status:
        q = q.where(LeaveRequest.status == status)
    return list(session.scalars(q).all())


def leave_balance(session: Session, employee: Employee, year: int | None = None) -> dict[str, float]:
    year = year or date.today().year
    taken = session.scalars(sa.select(LeaveRequest).where(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        sa.extract("year", LeaveRequest.from_date) == year,
    )).all()
    by_kind: dict[str, float] = defaultdict(float)
    for lr in taken:
        by_kind[lr.kind.value] += float(lr.days)
    entitlement = employee.annual_leave_entitlement_days
    remaining_annual = max(0.0, entitlement - by_kind.get(LeaveKind.ANNUAL.value, 0.0))
    return {
        "entitlement": entitlement,
        "taken_annual": by_kind.get(LeaveKind.ANNUAL.value, 0.0),
        "remaining_annual": remaining_annual,
        "taken_sick": by_kind.get(LeaveKind.SICK.value, 0.0),
        "taken_parental": by_kind.get(LeaveKind.PARENTAL.value, 0.0),
        "taken_total": sum(by_kind.values()),
    }


def submit_leave(session: Session, employee_id: int, kind: LeaveKind, from_date: date,
                 to_date: date, reason: str = "") -> LeaveRequest:
    if to_date < from_date:
        raise ValueError("to_date must be >= from_date")
    days = _working_days(from_date, to_date)
    lr = LeaveRequest(employee_id=employee_id, kind=kind, from_date=from_date,
                      to_date=to_date, days=days, status=LeaveStatus.PENDING, reason=reason)
    session.add(lr)
    session.commit()
    session.refresh(lr)
    return lr


def decide_leave(session: Session, leave_id: int, approver_id: int, approve: bool) -> LeaveRequest:
    from datetime import datetime as _dt
    lr = session.get(LeaveRequest, leave_id)
    if not lr:
        raise ValueError(f"leave {leave_id} not found")
    lr.status = LeaveStatus.APPROVED if approve else LeaveStatus.REJECTED
    lr.approver_id = approver_id
    lr.decided_at = _dt.utcnow()
    session.commit()
    session.refresh(lr)
    return lr


def _working_days(from_date: date, to_date: date) -> float:
    """Count Mon-Fri days inclusive. Ignores public holidays — the regional module
    layers those in later."""
    total = 0
    d = from_date
    while d <= to_date:
        if d.weekday() < 5:
            total += 1
        d += timedelta(days=1)
    return float(total)


# -------- Attendance --------------------------------------------------------

def list_attendance(session: Session, employee_id: int, *, since: date | None = None) -> list[AttendanceRecord]:
    q = sa.select(AttendanceRecord).where(AttendanceRecord.employee_id == employee_id)
    if since:
        q = q.where(AttendanceRecord.work_date >= since)
    q = q.order_by(AttendanceRecord.work_date.desc())
    return list(session.scalars(q).all())


def check_in(session: Session, employee_id: int, *, at=None) -> AttendanceRecord:
    from datetime import datetime as _dt
    at = at or _dt.utcnow()
    today = at.date()
    existing = session.scalar(sa.select(AttendanceRecord).where(
        AttendanceRecord.employee_id == employee_id,
        AttendanceRecord.work_date == today,
    ))
    if existing:
        if not existing.check_in:
            existing.check_in = at
            session.commit()
        return existing
    rec = AttendanceRecord(employee_id=employee_id, work_date=today, check_in=at)
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return rec


def check_out(session: Session, employee_id: int, *, at=None) -> AttendanceRecord | None:
    from datetime import datetime as _dt
    at = at or _dt.utcnow()
    today = at.date()
    rec = session.scalar(sa.select(AttendanceRecord).where(
        AttendanceRecord.employee_id == employee_id,
        AttendanceRecord.work_date == today,
    ))
    if not rec:
        return None
    rec.check_out = at
    if rec.check_in:
        rec.hours_worked = round((rec.check_out - rec.check_in).total_seconds() / 3600.0, 2)
    session.commit()
    session.refresh(rec)
    return rec


# -------- Payroll -----------------------------------------------------------

def list_payslips(session: Session, *, employee_id: int | None = None, year: int | None = None
                  ) -> list[Payslip]:
    q = sa.select(Payslip).options(joinedload(Payslip.employee))
    if employee_id:
        q = q.where(Payslip.employee_id == employee_id)
    if year:
        q = q.where(Payslip.period_year == year)
    q = q.order_by(Payslip.period_year.desc(), Payslip.period_month.desc())
    return list(session.scalars(q).all())


def create_payslip(session: Session, employee: Employee, year: int, month: int,
                   gross: Decimal | None = None, tax_rate: float = 0.22,
                   pension_rate: float = 0.02) -> Payslip:
    gross = gross if gross is not None else (employee.base_salary_annual / Decimal("12"))
    tax = (gross * Decimal(str(tax_rate))).quantize(Decimal("0.01"))
    pension = (gross * Decimal(str(pension_rate))).quantize(Decimal("0.01"))
    net = (gross - tax - pension).quantize(Decimal("0.01"))
    slip = Payslip(employee_id=employee.id, period_year=year, period_month=month,
                   gross=gross.quantize(Decimal("0.01")), tax=tax, pension=pension,
                   net=net, currency=employee.currency)
    session.add(slip)
    session.commit()
    session.refresh(slip)
    return slip


# -------- Expenses ----------------------------------------------------------

def list_expenses(session: Session, *, employee_id: int | None = None,
                  status: ExpenseStatus | None = None) -> list[ExpenseClaim]:
    q = sa.select(ExpenseClaim).options(joinedload(ExpenseClaim.employee), joinedload(ExpenseClaim.approver))
    if employee_id:
        q = q.where(ExpenseClaim.employee_id == employee_id)
    if status:
        q = q.where(ExpenseClaim.status == status)
    q = q.order_by(ExpenseClaim.claim_date.desc())
    return list(session.scalars(q).all())


def submit_expense(session: Session, employee_id: int, *, claim_date: date, category: str,
                   amount: Decimal, currency: str, description: str,
                   receipt_url: str | None = None) -> ExpenseClaim:
    claim = ExpenseClaim(employee_id=employee_id, claim_date=claim_date, category=category,
                         amount=amount, currency=currency, description=description,
                         receipt_url=receipt_url, status=ExpenseStatus.SUBMITTED)
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return claim


def decide_expense(session: Session, claim_id: int, approver_id: int, approve: bool) -> ExpenseClaim:
    from datetime import datetime as _dt
    claim = session.get(ExpenseClaim, claim_id)
    if not claim:
        raise ValueError(f"expense {claim_id} not found")
    claim.status = ExpenseStatus.APPROVED if approve else ExpenseStatus.REJECTED
    claim.approver_id = approver_id
    claim.approved_at = _dt.utcnow()
    session.commit()
    session.refresh(claim)
    return claim


# -------- Onboarding --------------------------------------------------------

DEFAULT_ONBOARDING_TEMPLATE = [
    ("Signed contract returned to HR", "hr"),
    ("Politiattest / background check cleared", "hr"),
    ("IT: laptop + email + SSO", "it"),
    ("IT: MFA enrolment + password reset", "it"),
    ("Manager: team intro & first-week plan", "manager"),
    ("Manager: role-specific training plan", "manager"),
    ("Employee: probation goals agreed", "employee"),
    ("Employee: emergency contact + bank details submitted", "employee"),
]


def create_onboarding(session: Session, employee: Employee,
                      template: list[tuple[str, str]] | None = None) -> OnboardingChecklist:
    tmpl = template or DEFAULT_ONBOARDING_TEMPLATE
    checklist = OnboardingChecklist(employee_id=employee.id)
    session.add(checklist)
    session.flush()
    for title, owner in tmpl:
        session.add(OnboardingTask(checklist_id=checklist.id, title=title, owner=owner))
    session.commit()
    session.refresh(checklist)
    return checklist


def complete_task(session: Session, task_id: int) -> OnboardingTask:
    from datetime import datetime as _dt
    task = session.get(OnboardingTask, task_id)
    if not task:
        raise ValueError(f"task {task_id} not found")
    task.state = OnboardingTaskState.DONE
    task.completed_at = _dt.utcnow()
    session.commit()
    session.refresh(task)
    return task
