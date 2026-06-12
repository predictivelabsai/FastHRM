"""Demo seed — populates a small Nordic-shaped organisation so the UI isn't empty."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from . import repo
from .db import (
    Department, Employee, EmployeeStatus, ExpenseClaim, ExpenseStatus,
    LeaveKind, LeaveRequest, LeaveStatus, create_all, get_engine,
)


def seed_demo() -> None:
    create_all()
    with Session(get_engine()) as s:
        if s.query(Employee).count() > 0:
            print("DB already has employees; skipping seed.")
            return

        # Departments
        exec_dept = Department(name="Executive", code="EXEC")
        hr = Department(name="HR & People", code="HR")
        eng = Department(name="Engineering", code="ENG")
        finance = Department(name="Finance", code="FIN")
        ops = Department(name="Operations", code="OPS")
        s.add_all([exec_dept, hr, eng, finance, ops])
        s.flush()

        # Executive
        ceo = Employee(employee_number="E-0001", first_name="Anne", last_name="Kristoffersen",
                       email="anne.k@example.gov", job_title="CEO", department_id=exec_dept.id,
                       start_date=date(2022, 1, 10), base_salary_annual=Decimal("1200000"),
                       currency="NOK", annual_leave_entitlement_days=27)
        s.add(ceo)
        s.flush()

        # HR
        hr_lead = Employee(employee_number="E-0002", first_name="Maria", last_name="Olsen",
                           email="maria.o@example.gov", job_title="Head of HR",
                           department_id=hr.id, manager_id=ceo.id, start_date=date(2022, 3, 1),
                           base_salary_annual=Decimal("900000"), currency="NOK")
        s.add(hr_lead)
        s.flush()

        # Finance
        cfo = Employee(employee_number="E-0003", first_name="Lars", last_name="Berg",
                       email="lars.b@example.gov", job_title="CFO", department_id=finance.id,
                       manager_id=ceo.id, start_date=date(2022, 2, 14),
                       base_salary_annual=Decimal("1050000"), currency="NOK")
        s.add(cfo)
        s.flush()

        # Engineering leadership + team
        cto = Employee(employee_number="E-0004", first_name="Ingrid", last_name="Halvorsen",
                       email="ingrid.h@example.gov", job_title="CTO", department_id=eng.id,
                       manager_id=ceo.id, start_date=date(2022, 2, 1),
                       base_salary_annual=Decimal("1100000"), currency="NOK")
        s.add(cto)
        s.flush()

        eng_people = [
            ("E-0005", "Jakob", "Lie", "Staff Engineer", 950000),
            ("E-0006", "Sofie", "Andresen", "Senior Engineer", 820000),
            ("E-0007", "Mikkel", "Solberg", "Engineer", 720000),
            ("E-0008", "Linnea", "Johansen", "Engineer", 710000),
        ]
        for num, fn, ln, title, sal in eng_people:
            s.add(Employee(
                employee_number=num, first_name=fn, last_name=ln,
                email=f"{fn.lower()}.{ln.lower()[:1]}@example.gov",
                job_title=title, department_id=eng.id, manager_id=cto.id,
                start_date=date(2023, 4, 1), base_salary_annual=Decimal(str(sal)),
                currency="NOK",
            ))
        s.flush()

        # Ops
        ops_lead = Employee(employee_number="E-0009", first_name="Henrik", last_name="Dahl",
                            email="henrik.d@example.gov", job_title="Head of Operations",
                            department_id=ops.id, manager_id=ceo.id, start_date=date(2022, 5, 20),
                            base_salary_annual=Decimal("880000"), currency="NOK")
        s.add(ops_lead)
        s.flush()
        for num, fn, ln, title, sal in [
            ("E-0010", "Camilla", "Ruud", "Operations Analyst", 650000),
            ("E-0011", "Magnus", "Nilsen", "Operations Analyst", 640000),
        ]:
            s.add(Employee(
                employee_number=num, first_name=fn, last_name=ln,
                email=f"{fn.lower()}.{ln.lower()[:1]}@example.gov",
                job_title=title, department_id=ops.id, manager_id=ops_lead.id,
                start_date=date(2024, 1, 15), base_salary_annual=Decimal(str(sal)),
                currency="NOK",
            ))
        s.commit()

        # A few pending + approved leave requests
        emps = s.query(Employee).all()
        s.add_all([
            LeaveRequest(employee_id=emps[4].id, kind=LeaveKind.ANNUAL,
                         from_date=date.today() + timedelta(days=5),
                         to_date=date.today() + timedelta(days=9),
                         days=5, status=LeaveStatus.PENDING, reason="Family trip"),
            LeaveRequest(employee_id=emps[5].id, kind=LeaveKind.SICK,
                         from_date=date.today() - timedelta(days=3),
                         to_date=date.today() - timedelta(days=2),
                         days=2, status=LeaveStatus.APPROVED,
                         reason="Cold", approver_id=emps[3].id,
                         decided_at=datetime.utcnow()),
            LeaveRequest(employee_id=emps[6].id, kind=LeaveKind.PARENTAL,
                         from_date=date.today() + timedelta(days=14),
                         to_date=date.today() + timedelta(days=42),
                         days=21, status=LeaveStatus.PENDING, reason="Parental leave"),
        ])

        # A couple of expense claims
        s.add_all([
            ExpenseClaim(employee_id=emps[4].id, claim_date=date.today() - timedelta(days=6),
                         category="travel", amount=Decimal("420.50"), currency="EUR",
                         description="Train Oslo-Trondheim for onsite",
                         status=ExpenseStatus.SUBMITTED),
            ExpenseClaim(employee_id=emps[6].id, claim_date=date.today() - timedelta(days=10),
                         category="training", amount=Decimal("899.00"), currency="EUR",
                         description="NDC conference",
                         status=ExpenseStatus.SUBMITTED),
        ])
        s.commit()

        # Onboarding for the newest Ops hires
        for emp in emps[-2:]:
            repo.create_onboarding(s, emp)

        # Payslips for last month
        from datetime import date as _d
        y, m = _d.today().year, _d.today().month - 1 or 12
        for emp in emps:
            repo.create_payslip(s, emp, y, m)

        print(f"Seeded demo data: {len(emps)} employees, "
              f"{s.query(LeaveRequest).count()} leave requests, "
              f"{s.query(ExpenseClaim).count()} expenses.")
