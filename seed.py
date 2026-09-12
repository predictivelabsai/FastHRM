"""Generate a synthetic FastHR database (deterministic, no PII)."""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import db
import people

RNG = random.Random(20260611)
TODAY = db.TODAY

FIRST = ["Aisha", "Liam", "Sofia", "Noah", "Mia", "Ethan", "Priya", "Lucas", "Chloe", "Mateo",
         "Hana", "Omar", "Isla", "Diego", "Yuki", "Nora", "Kai", "Zara", "Leo", "Amara",
         "Felix", "Ravi", "Elena", "Tariq", "Maya", "Sven", "Ingrid", "Marco", "Lena", "Pablo",
         "Nina", "Theo", "Sara", "Hugo", "Ada", "Cyrus", "Maja", "Bo", "Rhea", "Jonas"]
LAST = ["Okafor", "Nguyen", "Rossi", "Andersen", "Kim", "Haddad", "Silva", "Müller", "Costa",
        "Tanaka", "Khan", "Lindqvist", "Moreau", "Ito", "Petrov", "Schmidt", "Dubois", "Reyes",
        "Novak", "Bauer", "Mensah", "Sato", "Larsen", "Romano", "Singh", "Fischer", "Mwangi", "Park"]
DEPTS = ["Engineering", "Sales", "Marketing", "Customer Success", "Finance", "People & Culture", "Operations", "Product"]
DESIG = {
    "Engineering": ["Software Engineer", "Senior Engineer", "Engineering Manager", "QA Engineer", "DevOps Engineer"],
    "Sales": ["Account Executive", "Sales Manager", "SDR", "Sales Director"],
    "Marketing": ["Marketing Manager", "Content Lead", "Growth Marketer", "Designer"],
    "Customer Success": ["CS Manager", "Onboarding Specialist", "Support Lead"],
    "Finance": ["Accountant", "Financial Analyst", "Finance Manager"],
    "People & Culture": ["HR Business Partner", "Recruiter", "People Ops Manager"],
    "Operations": ["Operations Manager", "Office Manager", "Ops Analyst"],
    "Product": ["Product Manager", "Product Designer", "Head of Product"],
}
BRANCHES = ["London", "Berlin", "Remote", "Stockholm", "Madrid"]
LEAVE_ALLOC = {"Annual Leave": 25, "Sick Leave": 10, "Casual Leave": 6, "Parental Leave": 0, "Unpaid Leave": 0}
LEAVE_REASONS = ["Family holiday", "Medical appointment", "Personal day", "Wedding", "Moving house",
                 "Childcare", "Feeling unwell", "Conference", "Bereavement", "Mental health day"]


def _d(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def build():
    db.init_schema()
    with db.cursor() as conn:
        for t in ("goal_checkins", "goals", "onboarding_tasks", "expense_claims", "employee_advances", "travel_requests", "expense_categories", "clock_punches", "shift_assignments", "shift_locations", "shift_types", "chat_messages", "payslip_lines", "payslips", "pay_runs", "attendance", "leave_requests", "leave_balances", "employees", "departments"):
            conn.execute(f"DELETE FROM {t}")
        conn.executemany("INSERT INTO departments(name) VALUES (?)", [(d,) for d in DEPTS])
        dept_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM departments").fetchall()}

    # employees — managers first per dept
    emps = []
    used = set()
    n = 64
    for i in range(n):
        fn, ln = RNG.choice(FIRST), RNG.choice(LAST)
        email = f"{fn.lower()}.{ln.lower()}@fasthr.example"
        if email in used:
            email = f"{fn.lower()}.{ln.lower()}{i}@fasthr.example"
        used.add(email)
        dept = RNG.choice(DEPTS)
        desig = RNG.choice(DESIG[dept])
        base = RNG.randint(38, 130) * 1000
        doj = _d(RNG.randint(60, 2200))
        status = RNG.choices(db.EMP_STATUSES, weights=[80, 6, 14])[0]
        emps.append((f"EMP-{1001+i}", fn, ln, email, dept_ids[dept], desig, None,
                     RNG.choice(BRANCHES), status, doj, RNG.choice(["Female", "Male", "Other"]), base))
    with db.cursor() as conn:
        conn.executemany(
            """INSERT INTO employees(code,first_name,last_name,email,dept_id,designation,manager_id,branch,status,date_of_joining,gender,base_salary)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", emps)
        emp_rows = conn.execute("SELECT id,dept_id,designation,base_salary FROM employees").fetchall()
        # assign managers: pick a 'Manager'/'Director'/'Head' per dept
        by_dept = {}
        for e in emp_rows:
            by_dept.setdefault(e["dept_id"], []).append(e)
        for dept_id, members in by_dept.items():
            mgrs = [m for m in members if any(w in m["designation"] for w in ("Manager", "Director", "Head", "Lead"))]
            mgr = (mgrs or members)[0]
            for m in members:
                if m["id"] != mgr["id"]:
                    conn.execute("UPDATE employees SET manager_id=? WHERE id=?", (mgr["id"], m["id"]))
        emp_ids = [e["id"] for e in emp_rows]
        salary_by = {e["id"]: e["base_salary"] for e in emp_rows}
        for eid in emp_ids[:4]:
            conn.execute("UPDATE employees SET status='Active' WHERE id=?", (eid,))

    # Demo portal credentials (synthetic only):
    # Aisha Okafor, Liam Nguyen, Sofia Rossi and Noah Andersen use
    # portal.demo@fasthr.example-style addresses and password PortalDemo2026!
    for eid in emp_ids[:4]:
        db.set_employee_password(eid, "PortalDemo2026!")

    for eid in emp_ids[:4]:
        people.start_onboarding(eid)
        people.create_goal(title="Make a strong start", owner_id=eid, metric="Progress",
                           target=100, current=35, unit="%", period="2026 H1",
                           due_date="2026-06-30")

    # leave balances
    balances = []
    for eid in emp_ids:
        for lt, alloc in LEAVE_ALLOC.items():
            a = alloc if alloc else (RNG.choice([0, 0, 0, 90]) if lt == "Parental Leave" else 0)
            used = round(RNG.uniform(0, a * 0.7), 1) if a else 0
            balances.append((eid, lt, a, used))
    with db.cursor() as conn:
        conn.executemany("INSERT INTO leave_balances(employee_id,leave_type,allocated,used) VALUES (?,?,?,?)", balances)

    # leave requests
    reqs = []
    for _ in range(46):
        eid = RNG.choice(emp_ids)
        lt = RNG.choice(["Annual Leave", "Sick Leave", "Casual Leave"])
        start = RNG.randint(-20, 30)  # negative = past
        days = RNG.choice([1, 1, 2, 3, 5])
        frm = TODAY + timedelta(days=start)
        to = frm + timedelta(days=days - 1)
        status = RNG.choices(db.LEAVE_STATUSES, weights=[28, 55, 12, 5])[0]
        reqs.append((eid, lt, frm.isoformat(), to.isoformat(), days, status,
                     RNG.choice(LEAVE_REASONS), _d(RNG.randint(0, 25))))
    with db.cursor() as conn:
        conn.executemany(
            """INSERT INTO leave_requests(employee_id,leave_type,from_date,to_date,days,status,reason,applied_on)
               VALUES (?,?,?,?,?,?,?,?)""", reqs)
        approved = conn.execute("SELECT employee_id,from_date,to_date FROM leave_requests WHERE status='Approved'").fetchall()
    leave_days = set()
    for a in approved:
        d0 = date.fromisoformat(a["from_date"])
        d1 = date.fromisoformat(a["to_date"])
        d = d0
        while d <= d1:
            leave_days.add((a["employee_id"], d.isoformat()))
            d += timedelta(days=1)

    # attendance — last 30 weekdays
    att = []
    for eid in emp_ids:
        for back in range(0, 30):
            d = TODAY - timedelta(days=back)
            if d.weekday() >= 5:
                continue
            if (eid, d.isoformat()) in leave_days:
                att.append((eid, d.isoformat(), "On Leave", 0))
                continue
            status = RNG.choices(db.ATTEND_STATUSES, weights=[62, 24, 3, 5, 6])[0]
            hours = 0 if status in ("On Leave", "Absent") else (4 if status == "Half Day" else round(RNG.uniform(7.2, 9.0), 1))
            att.append((eid, d.isoformat(), status, hours))
    with db.cursor() as conn:
        conn.executemany("INSERT INTO attendance(employee_id,att_date,status,hours) VALUES (?,?,?,?)", att)

    # Shifts and time clocks — deterministic demo data, rebuilt with the rest
    # of the synthetic database so repeated seed runs are idempotent.
    with db.cursor() as conn:
        conn.executemany("""INSERT INTO shift_types(name,start_time,end_time,break_minutes,hourly_rate_multiplier,color)
                           VALUES (?,?,?,?,?,?)""", [
            ("Day", "09:00", "17:00", 30, 1.0, "#4f7cff"),
            ("Evening", "14:00", "22:00", 30, 1.1, "#a855f7"),
            ("Night", "22:00", "06:00", 45, 1.25, "#334155"),
            ("Split", "09:00", "17:00", 60, 1.0, "#f59e0b"),
        ])
        conn.executemany("INSERT INTO shift_locations(label,latitude,longitude,radius_m) VALUES (?,?,?,?)", [
            ("Tallinn HQ", 59.4370, 24.7536, 180),
            ("Warehouse B", 59.4230, 24.7920, 250),
        ])
        type_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM shift_types")}
        shift_ids = [e["id"] for e in emp_rows if e["id"] in emp_ids[:12]]

    assignments = []
    for index, eid in enumerate(shift_ids):
        for offset in range(-10, 11):
            d = TODAY + timedelta(days=offset)
            if d.weekday() >= 5:
                continue
            kind = ["Day", "Evening", "Night", "Split"][(index + offset) % 4]
            status = "Scheduled" if d > TODAY else "Completed"
            if index == 0 and offset == -8:
                status = "Missed"
            aid = db.create_shift_assignment(eid, type_ids[kind], d.isoformat(),
                                              "Tallinn HQ" if index % 3 else "Warehouse B")
            assignments.append((aid, eid, d, kind, status))
    for aid, eid, d, kind, status in assignments:
        with db.cursor() as conn:
            conn.execute("UPDATE shift_assignments SET status=? WHERE id=?", (status, aid))
        if status != "Completed":
            continue
        start_hour = {"Day": 9, "Evening": 14, "Night": 22, "Split": 9}[kind]
        start = datetime(d.year, d.month, d.day, start_hour, 0)
        end = start + timedelta(hours=7, minutes=30 if kind != "Night" else 15)
        db.clock_in(eid, aid, "Web", 59.4370, 24.7536, 12, punched_at=start.isoformat(sep=" "))
        db.clock_out(eid, aid, "Web", 59.4370, 24.7536, 12, punched_at=end.isoformat(sep=" "))

    # Pay runs — the three most recent completed periods before TODAY.
    periods = []
    y, m = 2026, 6
    for _ in range(3):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        periods.append(f"{y:04d}-{m:02d}")
    statuses = ["Paid", "Approved", "In Review"]
    active_ids = [e for e in emp_ids if db.scalar("SELECT status FROM employees WHERE id=?", (e,)) == "Active"]
    for per, status in zip(periods, ["In Review", "Approved", "Paid"]):
        run_id = db.create_pay_run(per, active_ids)
        for next_status in db.PAY_RUN_STATUSES[1:]:
            if db.PAY_RUN_STATUSES.index(next_status) <= db.PAY_RUN_STATUSES.index(status):
                db.advance_pay_run(run_id, next_status)

    # Expenses, advances and travel — deterministic synthetic Phase 3 data.
    categories = [
        ("Travel & accommodation", 1, 250.0, 1800.0), ("Mileage", 1, None, 600.0),
        ("Meals", 1, 35.0, 450.0), ("Office supplies", 1, None, 500.0),
        ("Software", 0, None, 1000.0), ("Training", 1, None, 1500.0),
        ("Client entertainment", 1, 150.0, 800.0), ("Other", 1, None, None),
    ]
    with db.cursor() as conn:
        conn.executemany("INSERT INTO expense_categories(name,requires_receipt,daily_limit,monthly_limit) VALUES (?,?,?,?)", categories)
        cat_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM expense_categories")}
        descriptions = ["Hotel in Tallinn", "Client visit mileage", "Lunch during workshop", "Printer paper",
                        "Figma team subscription", "First aid training", "Customer dinner", "Taxi to station"]
        cat_names = ["Travel & accommodation", "Mileage", "Meals", "Office supplies", "Software", "Training", "Client entertainment", "Other"]
        claim_rows = []
        claim_statuses = ["Submitted", "Approved", "Reimbursed", "Rejected", "Draft"]
        for i in range(20):
            cat_name = cat_names[i % len(cat_names)]
            amount = round((420 if cat_name == "Travel & accommodation" else 0) +
                           (0.35 * (35 + i * 7) if cat_name == "Mileage" else RNG.uniform(12, 95)), 2)
            claim_rows.append((emp_ids[i % 16], cat_ids[cat_name], _d((i * 5) % 88), descriptions[i % len(descriptions)],
                               amount, "EUR", 0.22 if cat_name not in ("Mileage", "Other") else 0,
                               claim_statuses[i % len(claim_statuses)], emp_ids[(i + 20) % len(emp_ids)] if i % 5 in (0, 1, 2) else None,
                               _d((i * 5 + 2) % 88) if i % 5 in (0, 1, 2) else None,
                               _d((i * 5 + 4) % 88) if i % 5 == 2 else None, "Synthetic seed claim"))
        conn.executemany("""INSERT INTO expense_claims(employee_id,category_id,claim_date,description,amount,currency,tax_rate,status,approver_id,decided_at,reimbursed_at,notes)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", claim_rows)
        conn.executemany("""INSERT INTO employee_advances(employee_id,requested_amount,approved_amount,currency,reason,status,requested_at,decided_at,notes)
                           VALUES (?,?,?,?,?,?,datetime('now'),?,?)""", [
            (emp_ids[2], 800, None, "EUR", "Conference travel", "Requested", None, "Awaiting approval"),
            (emp_ids[0], 1200, 1200, "EUR", "Relocation support", "Approved", _d(18), "Approved seed advance"),
            (emp_ids[11], 450, None, "EUR", "Equipment purchase", "Repaid", _d(70), "Repaid seed advance"),
        ])
        conn.executemany("""INSERT INTO travel_requests(employee_id,destination,purpose,from_date,to_date,estimated_cost,advance_requested,status,approver_id,decided_at,notes)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""", [
            (emp_ids[1], "Tartu", "Customer workshop", _d(4), _d(2), 260, 100, "Submitted", None, None, "Synthetic seed request"),
            (emp_ids[4], "Helsinki", "Partner planning", _d(15), _d(13), 720, 300, "Approved", emp_ids[30], _d(20), "Synthetic seed request"),
            (emp_ids[8], "Riga", "Sales conference", _d(28), _d(25), 980, 400, "Returned", emp_ids[31], _d(30), "Add agenda"),
            (emp_ids[12], "Vilnius", "Team offsite", _d(42), _d(39), 650, 0, "Rejected", emp_ids[32], _d(45), "Synthetic seed request"),
            (emp_ids[15], "Pärnu", "Planning day", _d(60), _d(59), 180, 0, "Approved", emp_ids[33], _d(63), "Synthetic seed request"),
        ])

    pays = db.scalar("SELECT COUNT(*) FROM payslips") or 0

    print(f"FastHR seeded -> {db.DB_PATH}")
    print(f"  {n} employees · {len(DEPTS)} depts · {len(reqs)} leave requests · {len(att)} attendance · "
          f"{len(assignments)} shifts · {pays} payslips · 3 pay runs · 20 expense claims · 5 travel requests")


if __name__ == "__main__":
    build()
