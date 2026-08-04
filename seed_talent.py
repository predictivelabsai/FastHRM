"""Synthetic ATS data — requisitions, candidates and a live pipeline.

Separate from seed.py and safe to re-run: it clears only the ATS tables, so the
three-pillar baseline (employees, leave, attendance, payroll) is untouched.

    python seed_talent.py
"""
from __future__ import annotations

import json
import random
from datetime import timedelta

import db
import talent
from web import cv_extract

RNG = random.Random(20260611)
TODAY = db.TODAY

REQS = [
    ("Senior Backend Engineer", "Engineering", 2, 78000, 105000, "Berlin", "Hybrid", 41),
    ("Product Designer", "Product", 1, 62000, 82000, "London", "Hybrid", 26),
    ("Account Executive — DACH", "Sales", 3, 55000, 75000, "Berlin", "Remote", 68),
    ("People Ops Manager", "People & Culture", 1, 58000, 72000, "London", "Onsite", 12),
    ("Data Engineer", "Engineering", 1, 70000, 92000, "Remote", "Remote", 19),
    ("Customer Success Manager", "Customer Success", 2, 48000, 62000, "Stockholm", "Hybrid", 33),
]

FIRST = ["Aisha", "Mateo", "Freya", "Tomas", "Nadia", "Idris", "Lucia", "Bo", "Anouk", "Rafael",
         "Mina", "Otto", "Sanne", "Emeka", "Klara", "Dmitri", "Yara", "Pieter", "Rosa", "Kwame",
         "Solveig", "Amir", "Beatriz", "Jonas", "Ingrid", "Tariq", "Elif", "Viktor", "Noor", "Casper"]
LAST = ["Berglund", "Okonkwo", "Vasquez", "Halvorsen", "Bianchi", "Demir", "Kowalski", "Ferreira",
        "Nakamura", "Adeyemi", "Lindgren", "Moreau", "Castellanos", "Virtanen", "Haddad", "Novotny",
        "Espinoza", "Jankowski", "Olsen", "Bakker"]

TITLES = {
    "Senior Backend Engineer": ["Backend Engineer", "Senior Software Engineer", "Platform Engineer", "Staff Engineer"],
    "Product Designer": ["Product Designer", "UX Designer", "Senior Designer", "Design Lead"],
    "Account Executive — DACH": ["Account Executive", "Senior AE", "Sales Manager", "Business Development Manager"],
    "People Ops Manager": ["HR Manager", "People Partner", "HR Business Partner", "People Ops Lead"],
    "Data Engineer": ["Data Engineer", "Analytics Engineer", "Senior Data Engineer", "ETL Developer"],
    "Customer Success Manager": ["Customer Success Manager", "Account Manager", "Onboarding Lead", "CS Lead"],
}
EMPLOYERS = ["Zephyr Payments", "Northwind Analytics", "Casseline Retail", "Brightline Health",
             "Orbital Logistics", "Vantage Media", "Kestrel Bank", "Nimbus Cloud", "Larkspur Foods",
             "Meridian Legal", "Halcyon Energy", "Tessellate AI"]
LOCATIONS = ["Berlin, Germany", "London, UK", "Amsterdam, Netherlands", "Stockholm, Sweden",
             "Madrid, Spain", "Remote (EU)", "Lisbon, Portugal", "Dublin, Ireland"]
SKILLS = {
    "Senior Backend Engineer": ["Python", "Postgres", "Kafka", "Kubernetes", "Go", "Terraform", "REST API design"],
    "Product Designer": ["Figma", "Design systems", "User research", "Prototyping", "Accessibility", "Motion design"],
    "Account Executive — DACH": ["MEDDIC", "Salesforce", "German", "Pipeline management", "Negotiation", "SaaS sales"],
    "People Ops Manager": ["Employment law", "HRIS", "Onboarding design", "Comp benchmarking", "Employee relations"],
    "Data Engineer": ["dbt", "Airflow", "Snowflake", "Python", "SQL", "Spark", "Data modelling"],
    "Customer Success Manager": ["Churn analysis", "QBRs", "Zendesk", "Onboarding", "Upselling", "Swedish"],
}
LEVELS = ["Intermediate", "Advanced", "Expert"]
STAGE_WEIGHTS = [("Applied", 46), ("Screen", 20), ("Interview", 13), ("Offer", 4),
                 ("Hired", 3), ("Rejected", 14)]
REJECTIONS = ["Not enough depth in the core stack", "Comp expectations out of band",
              "Withdrew — accepted another offer", "Stronger candidates in pipeline",
              "No right to work in location"]


def _d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


def _years(title: str) -> float:
    return round(RNG.uniform(2, 14), 1) if "Senior" in title or "Lead" in title else round(RNG.uniform(1, 9), 1)


def build():
    db.migrate()
    cv_extract.ensure_default_prompt()

    with db.cursor() as conn:
        for t in ("extraction_runs", "candidate_documents", "candidate_skills",
                  "candidate_experience", "candidate_education", "applications",
                  "candidates", "job_openings"):
            conn.execute(f"DELETE FROM {t}")
        conn.execute("DELETE FROM lifecycle_events WHERE entity_type IN ('candidate','application')")
        depts = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM departments")}
        managers = {}
        for name, did in depts.items():
            row = conn.execute("""SELECT id FROM employees WHERE dept_id=? AND manager_id IS NULL
                                  LIMIT 1""", (did,)).fetchone()
            if row:
                managers[name] = row["id"]

    # --- requisitions --------------------------------------------------------
    job_ids = {}
    with db.cursor() as conn:
        for i, (title, dept, headcount, cmin, cmax, loc, remote, age) in enumerate(REQS):
            status = "Open" if i < 5 else "Draft"
            cur = conn.execute(
                """INSERT INTO job_openings(code,title,dept_id,hiring_manager_id,headcount,filled,
                       comp_min,comp_max,currency,location,remote_policy,employment_type,status,
                       description,requirements,stages_json,opened_on,target_date,created)
                   VALUES (?,?,?,?,?,0,?,?,'GBP',?,?,'Permanent',?,?,?,?,?,?,datetime('now'))""",
                (f"REQ-{2001 + i}", title, depts.get(dept), managers.get(dept), headcount,
                 cmin, cmax, loc, remote, status,
                 f"We're hiring a {title} to join {dept}. Fully synthetic demo requisition.",
                 ", ".join(SKILLS[title][:4]), json.dumps(talent.STAGES),
                 _d(age) if status == "Open" else None,
                 (TODAY + timedelta(days=RNG.randint(20, 75))).isoformat()))
            job_ids[title] = cur.execute("SELECT last_insert_rowid()").fetchone()[0]

    # --- candidates + applications ------------------------------------------
    n_cand = 0
    n_app = 0
    used_emails = set()
    open_titles = {r["title"] for r in talent.jobs("Open")}
    for title, job_id in job_ids.items():
        if title not in open_titles:
            continue  # a Draft req has not been published, so it has no applicants
        n = RNG.randint(9, 18) if title != "People Ops Manager" else 6
        for _ in range(n):
            fn, ln = RNG.choice(FIRST), RNG.choice(LAST)
            email = f"{fn.lower()}.{ln.lower()}@example.com"
            while email in used_emails:
                email = f"{fn.lower()}.{ln.lower()}{RNG.randint(2, 99)}@example.com"
            used_emails.add(email)
            cur_title = RNG.choice(TITLES[title])
            employer = RNG.choice(EMPLOYERS)
            years = _years(cur_title)
            source = RNG.choices(talent.SOURCES, weights=[30, 12, 40, 10, 8])[0]

            cid = talent.create_candidate(
                first_name=fn, last_name=ln, email=email,
                phone=f"+44 7{RNG.randint(100, 999)} {RNG.randint(100000, 999999)}",
                source=source, consent=True,
                location=RNG.choice(LOCATIONS),
                headline=f"{cur_title} with {years:.0f} years in {title.split()[0].lower()} roles",
                current_title=cur_title, current_employer=employer, years_experience=years,
                linkedin_url=f"linkedin.com/in/{fn.lower()}{ln.lower()}")
            n_cand += 1

            picked = RNG.sample(SKILLS[title], RNG.randint(3, min(6, len(SKILLS[title]))))
            with db.cursor() as conn:
                conn.executemany(
                    """INSERT INTO candidate_skills(candidate_id,skill,level,years,evidence,source)
                       VALUES (?,?,?,?,?,'seed')""",
                    [(cid, s, RNG.choice(LEVELS), round(RNG.uniform(1, years), 1),
                      f"Listed under skills; used at {employer}") for s in picked])
                for j in range(RNG.randint(1, 3)):
                    start = RNG.randint(400, 3600) + j * 900
                    conn.execute(
                        """INSERT INTO candidate_experience
                           (candidate_id,employer,title,start_date,end_date,location,summary,sort_order)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (cid, employer if j == 0 else RNG.choice(EMPLOYERS),
                         cur_title if j == 0 else RNG.choice(TITLES[title]),
                         _d(start)[:7], None if j == 0 else _d(start - 700)[:7],
                         RNG.choice(LOCATIONS), f"Owned delivery across {RNG.choice(picked).lower()}.", j))
                conn.execute(
                    """INSERT INTO candidate_education(candidate_id,institution,qualification,field,end_year)
                       VALUES (?,?,?,?,?)""",
                    (cid, RNG.choice(["Anna University", "TU Munich", "KTH Stockholm", "UCL",
                                      "Universidade de Lisboa", "Trinity College Dublin"]),
                     RNG.choice(["BSc", "BEng", "MSc", "MA"]),
                     RNG.choice(["Computer Science", "Design", "Business", "Economics", "Psychology"]),
                     str(RNG.randint(2008, 2022))))

            aid = talent.apply_to_job(cid, job_id, actor="seed")
            n_app += 1
            stage = RNG.choices([s for s, _ in STAGE_WEIGHTS], weights=[w for _, w in STAGE_WEIGHTS])[0]
            applied = RNG.randint(3, 55)
            with db.cursor() as conn:
                conn.execute(
                    """UPDATE applications SET stage=?, status=?, applied_on=?, stage_entered_on=?,
                           rating=?, rejection_reason=? WHERE id=?""",
                    (stage, {"Hired": "Hired", "Rejected": "Rejected"}.get(stage, "Active"),
                     _d(applied), _d(max(0, applied - RNG.randint(1, 12))),
                     round(RNG.uniform(2.0, 4.9), 1) if stage not in ("Applied",) else None,
                     RNG.choice(REJECTIONS) if stage == "Rejected" else None, aid))
                if stage == "Hired":
                    conn.execute("UPDATE job_openings SET filled=filled+1 WHERE id=?", (job_id,))
                    conn.execute("UPDATE candidates SET status='Hired' WHERE id=?", (cid,))

    print(f"FastHRM talent seeded → {db.DB_PATH}")
    print(f"  {len(job_ids)} requisitions · {n_cand} candidates · {n_app} applications")
    print("  CV extraction prompt: v%s active" % (talent.active_prompt(cv_extract.PROMPT_KEY) or {}).get("version"))


if __name__ == "__main__":
    build()
