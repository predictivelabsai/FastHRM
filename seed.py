"""Generate a synthetic FastHR database (deterministic, no PII)."""
from __future__ import annotations

import random
from datetime import date, timedelta

import db

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
        for t in ("chat_messages", "payslips", "attendance", "leave_requests", "leave_balances", "employees", "departments"):
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

    # payslips — last 4 months
    pays = []
    periods = []
    y, m = 2026, 6
    for _ in range(4):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        periods.append(f"{y:04d}-{m:02d}")
    for eid in emp_ids:
        monthly_gross = salary_by[eid] / 12
        for per in periods:
            gross = round(monthly_gross * RNG.uniform(0.98, 1.05), 2)
            tax = round(gross * RNG.uniform(0.18, 0.32), 2)
            pension = round(gross * 0.05, 2)
            other = round(gross * RNG.uniform(0, 0.03), 2)
            net = round(gross - tax - pension - other, 2)
            pays.append((eid, per, gross, tax, pension, other, net, "Paid"))
    with db.cursor() as conn:
        conn.executemany(
            """INSERT INTO payslips(employee_id,period,gross,tax,pension,other_ded,net,status)
               VALUES (?,?,?,?,?,?,?,?)""", pays)

    print(f"FastHR seeded → {db.DB_PATH}")
    print(f"  {n} employees · {len(DEPTS)} depts · {len(reqs)} leave requests · {len(att)} attendance · {len(pays)} payslips")


if __name__ == "__main__":
    build()
