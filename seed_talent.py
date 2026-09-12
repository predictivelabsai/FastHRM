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
    ("Vanemarendaja (backend)", "Arendus", 2, 78000, 105000, "Tallinn", "Hübriid", 41),
    ("Tootedisainer", "Toode", 1, 62000, 82000, "Tallinn", "Hübriid", 26),
    ("Müügikonsultant", "Müük", 3, 55000, 75000, "Tartu", "Kaugtöö", 68),
    ("Personalijuht", "Personal", 1, 58000, 72000, "Tallinn", "Kontoris", 12),
    ("Andmeinsener", "Arendus", 1, 70000, 92000, "Kaugtöö", "Kaugtöö", 19),
    ("Klienditoe juht", "Klienditugi", 2, 48000, 62000, "Pärnu", "Hübriid", 33),
]

FIRST = ["Mari", "Jaan", "Kadri", "Peeter", "Liisa", "Mati", "Anna", "Kristjan",
         "Eva", "Tõnu", "Katrin", "Andres", "Piret", "Jüri", "Tiina", "Marko",
         "Sirje", "Urmas", "Kairi", "Rain", "Maarja", "Indrek", "Külli", "Toomas",
         "Anu", "Priit", "Heli", "Meelis", "Triin", "Siim"]
LAST = ["Tamm", "Saar", "Mägi", "Sepp", "Rebane", "Kask", "Kukk", "Pärn",
        "Ilves", "Karu", "Raud", "Õun", "Lepp", "Kuusk", "Vaher", "Nurk",
        "Puu", "Kivi", "Roos", "Hall"]

TITLES = {
    "Vanemarendaja (backend)": ["Tarkvaraarendaja", "Vanemarendaja", "Platvormiarendaja", "Juhtarendaja"],
    "Tootedisainer": ["Tootedisainer", "UX-disainer", "Vanemdisainer", "Disainijuht"],
    "Müügikonsultant": ["Müügikonsultant", "Vanem müügikonsultant", "Müügijuht", "Äriarendusjuht"],
    "Personalijuht": ["Personalijuht", "Personalipartner", "Värbaja", "Personalivaldkonna juht"],
    "Andmeinsener": ["Andmeinsener", "Analüütikainsener", "Vanemandmeinsener", "Andmetöötluse arendaja"],
    "Klienditoe juht": ["Klienditoe juht", "Võtmekliendihaldur", "Kasutuselevõtu spetsialist", "Klienditoe spetsialist"],
}
EMPLOYERS = ["Viru Tarkvara", "Emajõe Andmed", "Pärnu Jaekaubandus", "Pelgulinna Kliinik",
             "Muuga Logistika", "Telliskivi Meedia", "Lasnamäe Finants", "Ülemiste Pilv",
             "Kalamaja Toit", "Rotermanni Õigus", "Pirita Energia", "Kopli Tehisintellekt"]
LOCATIONS = ["Tallinn, Eesti", "Tartu, Eesti", "Pärnu, Eesti", "Narva, Eesti",
             "Kaugtöö (Eesti)", "Helsingi, Soome", "Riia, Läti", "Vilnius, Leedu"]
SKILLS = {
    "Vanemarendaja (backend)": ["Python", "Postgres", "Kafka", "Kubernetes", "Go", "Terraform", "REST API disain"],
    "Tootedisainer": ["Figma", "Disainisüsteemid", "Kasutajauuringud", "Prototüüpimine", "Ligipääsetavus", "Liikumisdisain"],
    "Müügikonsultant": ["MEDDIC", "Salesforce", "Saksa keel", "Müügitoru juhtimine", "Läbirääkimised", "SaaS-müük"],
    "Personalijuht": ["Tööõigus", "HRIS", "Sisseelamise disain", "Tasustuse võrdlus", "Töötajasuhted"],
    "Andmeinsener": ["dbt", "Airflow", "Snowflake", "Python", "SQL", "Spark", "Andmemodelleerimine"],
    "Klienditoe juht": ["Kliendikao analüüs", "QBR", "Zendesk", "Kasutuselevõtt", "Lisamüük", "Rootsi keel"],
}
LEVELS = ["Kesktase", "Edasijõudnud", "Ekspert"]
STAGE_WEIGHTS = [("Applied", 46), ("Screen", 20), ("Interview", 13), ("Offer", 4),
                 ("Hired", 3), ("Rejected", 14)]
REJECTIONS = ["Liiga vähe süvitsi kogemust põhitehnoloogiates", "Palgaootus väljaspool vahemikku",
              "Kandus ära, võttis vastu teise pakkumise", "Tugevamad kandidaadid protsessis",
              "Puudub õigus asukohas töötada"]


def _slug(name):
    """ASCII email local-part: strip Estonian diacritics (õäöüšž)."""
    return (name.lower().replace("õ", "o").replace("ä", "a").replace("ö", "o")
            .replace("ü", "u").replace("š", "s").replace("ž", "z"))


def _d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


def _years(title: str) -> float:
    return round(RNG.uniform(2, 14), 1) if "Vanem" in title or "Juht" in title else round(RNG.uniform(1, 9), 1)


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
                   VALUES (?,?,?,?,?,0,?,?,'EUR',?,?,'Tähtajatu',?,?,?,?,?,?,datetime('now'))""",
                (f"REQ-{2001 + i}", title, depts.get(dept), managers.get(dept), headcount,
                 cmin, cmax, loc, remote, status,
                 f"Otsime meeskonda {dept} töötajat ametikohale {title}. Sünteetiline näidiskuulutus.",
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
        n = RNG.randint(9, 18) if title != "Personalijuht" else 6
        for _ in range(n):
            fn, ln = RNG.choice(FIRST), RNG.choice(LAST)
            email = f"{_slug(fn)}.{_slug(ln)}@example.com"
            while email in used_emails:
                email = f"{_slug(fn)}.{_slug(ln)}{RNG.randint(2, 99)}@example.com"
            used_emails.add(email)
            cur_title = RNG.choice(TITLES[title])
            employer = RNG.choice(EMPLOYERS)
            years = _years(cur_title)
            source = RNG.choices(talent.SOURCES, weights=[30, 12, 40, 10, 8])[0]

            cid = talent.create_candidate(
                first_name=fn, last_name=ln, email=email,
                phone=f"+372 5{RNG.randint(100, 999)} {RNG.randint(100, 999)}",
                source=source, consent=True,
                location=RNG.choice(LOCATIONS),
                headline=f"{cur_title}, {years:.0f} aastat kogemust",
                current_title=cur_title, current_employer=employer, years_experience=years,
                linkedin_url=f"linkedin.com/in/{_slug(fn)}{_slug(ln)}")
            n_cand += 1

            picked = RNG.sample(SKILLS[title], RNG.randint(3, min(6, len(SKILLS[title]))))
            with db.cursor() as conn:
                conn.executemany(
                    """INSERT INTO candidate_skills(candidate_id,skill,level,years,evidence,source)
                       VALUES (?,?,?,?,?,'seed')""",
                    [(cid, s, RNG.choice(LEVELS), round(RNG.uniform(1, years), 1),
                      f"Oskuste loendis; kasutanud kohas {employer}") for s in picked])
                for j in range(RNG.randint(1, 3)):
                    start = RNG.randint(400, 3600) + j * 900
                    conn.execute(
                        """INSERT INTO candidate_experience
                           (candidate_id,employer,title,start_date,end_date,location,summary,sort_order)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (cid, employer if j == 0 else RNG.choice(EMPLOYERS),
                         cur_title if j == 0 else RNG.choice(TITLES[title]),
                         _d(start)[:7], None if j == 0 else _d(start - 700)[:7],
                         RNG.choice(LOCATIONS), f"Vastutas valdkonna {RNG.choice(picked).lower()} tarnete eest.", j))
                conn.execute(
                    """INSERT INTO candidate_education(candidate_id,institution,qualification,field,end_year)
                       VALUES (?,?,?,?,?)""",
                    (cid, RNG.choice(["Tartu Ülikool", "Tallinna Tehnikaülikool", "EKA",
                                      "Eesti Maaülikool", "Tallinna Ülikool", "Mainori Kõrgkool"]),
                     RNG.choice(["BSc", "BEng", "MSc", "MA"]),
                     RNG.choice(["Informaatika", "Disain", "Ärijuhtimine", "Majandus", "Psühholoogia"]),
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

    print(f"FastHR talent seeded → {db.DB_PATH}")
    print(f"  {len(job_ids)} requisitions · {n_cand} candidates · {n_app} applications")
    print("  CV extraction prompt: v%s active" % (talent.active_prompt(cv_extract.PROMPT_KEY) or {}).get("version"))


if __name__ == "__main__":
    build()
