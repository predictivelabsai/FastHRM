# FastHR Roadmap — Frappe HR (HRMS) feature comparison

`frappe/hrms` is the largest non-ERP Frappe app (~160 doctypes). FastHR ports the
**three pillars an HR team touches daily**; the long tail is deferred.

## Implemented ✅

| Capability | Upstream doctype(s) | FastHR |
|---|---|---|
| Employees | `Employee` | `employees` (dept, designation, manager, branch, status) |
| Departments | `Department` | `departments` + headcount/payroll |
| Org reporting line | `Employee.reports_to` | `manager_id` |
| Leave balances | `Leave Allocation`, `Leave Type` | `leave_balances` |
| Leave requests | `Leave Application` | `leave_requests` (Pending/Approved/Rejected) |
| Attendance | `Attendance` | `attendance` (Present/WFH/Leave/Half/Absent) + strip |
| Payslips | `Salary Slip` | `payslips` with gross/tax/pension/net breakdown |
| **AI assistant** | *(not upstream)* | grounded HR Q&A |

## Near-term roadmap 🔜

1. ✅ **Approve/reject + apply leave** (done) — HTMX approve/reject on
   pending requests with balance recompute (`Leave Application` workflow).
2. **Apply for leave** — a self-service request form (employee-side).
3. **Clock in/out** — `Employee Checkin` (today's check-ins → attendance).
4. **Org chart** — render the `reports_to` tree visually.
5. **Salary structure** — `Salary Structure`/`Salary Component` (formula-based
   components rather than fixed gross/tax).
6. **Holidays & shifts** — `Holiday List`, `Shift Type` (attendance respects
   working days/shifts).

## Later / out-of-scope 🗓️

The bulk of HRMS, deferred for a 3-pillar demonstrator:

- **Full payroll engine** — `Payroll Entry`, `Salary Structure Assignment`,
  tax slabs, benefits, flexible-benefit claims, loan/advance ledgers.
- **Recruitment** — `Job Opening`, `Job Applicant`, `Job Offer`, interviews.
- **Performance** — `Appraisal`, `Appraisal Cycle`, goals/KRAs.
- **Lifecycle** — `Employee Onboarding`/`Separation`/`Promotion`/`Transfer`,
  `Employee Grievance`.
- **Expenses & travel** — `Expense Claim`, `Employee Advance`, travel requests.
- **Shifts & attendance automation** — shift assignment, auto-attendance from
  check-ins, geolocation.

## Design notes

FastHR collapses Frappe's normalised leave/attendance/payroll doctypes into five
compact tables and computes the headline metrics in `db.kpis()`. The highest-value
next step is making leave **transactional** (apply → approve → balance updates) —
the demonstrator currently shows the data read-only.
