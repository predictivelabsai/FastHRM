"""Learning and development administration."""
from __future__ import annotations

from datetime import date, timedelta

import db
from fasthtml.common import *

COURSE_CATEGORIES = ("onboarding", "compliance", "skills", "leadership", "other")
PLAN_STATUSES = ("Planned", "In progress", "Completed")


def courses(active_only: bool = False) -> list[dict]:
    where = "WHERE active=1" if active_only else ""
    return db.rows(f"SELECT * FROM courses {where} ORDER BY active DESC, name")


def list_courses(active_only: bool = False) -> list[dict]:
    """Compatibility-friendly name for the course catalogue read."""
    return courses(active_only)


def save_course(name: str, category: str = "skills", provider: str = "",
                course_id: int | None = None, active: int = 1) -> int:
    if not name.strip() or category not in COURSE_CATEGORIES:
        raise ValueError("Course name and a valid category are required")
    with db.cursor() as conn:
        if course_id:
            conn.execute("UPDATE courses SET name=?, category=?, provider=?, active=? WHERE id=?",
                         (name.strip(), category, provider.strip(), active, course_id))
            return course_id
        return conn.execute("INSERT INTO courses(name,category,provider,active) VALUES(?,?,?,?)",
                            (name.strip(), category, provider.strip(), active)).lastrowid


def deactivate_course(course_id: int) -> bool:
    with db.cursor() as conn:
        return bool(conn.execute("UPDATE courses SET active=0 WHERE id=?", (course_id,)).rowcount)


def plans_for(employee_id: int) -> list[dict]:
    return db.rows("""SELECT p.*, c.name course_name, c.category, c.provider,
                           e.first_name || ' ' || e.last_name employee_name
                    FROM learning_plans p JOIN courses c ON c.id=p.course_id
                    JOIN employees e ON e.id=p.employee_id
                    WHERE p.employee_id=? ORDER BY p.status, p.due_date, c.name""", (employee_id,))


def all_plans() -> list[dict]:
    return db.rows("""SELECT p.*, c.name course_name, c.category, c.provider,
                           e.first_name || ' ' || e.last_name employee_name
                    FROM learning_plans p JOIN courses c ON c.id=p.course_id
                    JOIN employees e ON e.id=p.employee_id
                    ORDER BY e.first_name, e.last_name, p.due_date, c.name""")


def assign(employee_id: int, course_id: int, assigned_by: str = "",
           due_date: str | None = None) -> int:
    with db.cursor() as conn:
        row = conn.execute("SELECT id FROM learning_plans WHERE employee_id=? AND course_id=?",
                           (employee_id, course_id)).fetchone()
        if row:
            conn.execute("UPDATE learning_plans SET assigned_by=?, due_date=? WHERE id=?",
                         (assigned_by.strip(), due_date or None, row[0]))
            return row[0]
        return conn.execute("""INSERT INTO learning_plans(employee_id,course_id,assigned_by,due_date)
                              VALUES(?,?,?,?)""",
                            (employee_id, course_id, assigned_by.strip(), due_date or None)).lastrowid


def set_progress(plan_id: int, progress: int) -> bool:
    progress = max(0, min(100, int(progress)))
    completed = db.TODAY.isoformat() if progress == 100 else None
    status = "Completed" if progress == 100 else ("In progress" if progress else "Planned")
    with db.cursor() as conn:
        return bool(conn.execute("""UPDATE learning_plans SET progress=?, status=?, completed_on=?
                                  WHERE id=?""", (progress, status, completed, plan_id)).rowcount)


def save_plan(plan_id: int, employee_id: int, course_id: int, assigned_by: str = "",
              due_date: str | None = None, status: str = "Planned",
              progress: int = 0) -> int:
    if status not in PLAN_STATUSES:
        raise ValueError("Unknown learning plan status")
    if plan_id:
        with db.cursor() as conn:
            conn.execute("""UPDATE learning_plans SET employee_id=?, course_id=?, assigned_by=?,
                           due_date=?, status=?, progress=? WHERE id=?""",
                         (employee_id, course_id, assigned_by.strip(), due_date or None,
                          status, max(0, min(100, int(progress))), plan_id))
        return plan_id
    return assign(employee_id, course_id, assigned_by, due_date)


def delete_plan(plan_id: int) -> bool:
    with db.cursor() as conn:
        return bool(conn.execute("DELETE FROM learning_plans WHERE id=?", (plan_id,)).rowcount)


def certifications_for(employee_id: int | None = None) -> list[dict]:
    query = """SELECT c.*, e.first_name || ' ' || e.last_name employee_name
               FROM certifications c JOIN employees e ON e.id=c.employee_id"""
    params: tuple = ()
    if employee_id is not None:
        query += " WHERE c.employee_id=?"
        params = (employee_id,)
    return db.rows(query + " ORDER BY c.expires_on IS NULL, c.expires_on, c.name", params)


def list_for(employee_id: int) -> list[dict]:
    return certifications_for(employee_id)


def add_certification(employee_id: int, name: str, issued_on: str | None = None,
                      expires_on: str | None = None, files_note: str = "") -> int:
    if not name.strip():
        raise ValueError("Certification name is required")
    with db.cursor() as conn:
        return conn.execute("""INSERT INTO certifications(employee_id,name,issued_on,expires_on,files_note)
                              VALUES(?,?,?,?,?)""",
                            (employee_id, name.strip(), issued_on or None, expires_on or None,
                             files_note.strip())).lastrowid


def add(employee_id: int, name: str, issued_on: str | None = None,
        expires_on: str | None = None, files_note: str = "") -> int:
    """Short CRUD alias for adding a certification."""
    return add_certification(employee_id, name, issued_on, expires_on, files_note)


def remove_certification(certification_id: int) -> bool:
    with db.cursor() as conn:
        return bool(conn.execute("DELETE FROM certifications WHERE id=?", (certification_id,)).rowcount)


def remove(certification_id: int) -> bool:
    """Short CRUD alias for removing a certification."""
    return remove_certification(certification_id)


def expiring_certifications(days: int = 60) -> list[dict]:
    end = (db.TODAY + timedelta(days=days)).isoformat()
    return db.rows("""SELECT c.*, e.first_name || ' ' || e.last_name employee_name
                    FROM certifications c JOIN employees e ON e.id=c.employee_id
                    WHERE c.expires_on IS NOT NULL AND c.expires_on BETWEEN ? AND ?
                    ORDER BY c.expires_on, c.name""", (db.TODAY.isoformat(), end))


def kpis() -> dict:
    year = db.TODAY.year
    return {"courses_active": db.scalar("SELECT COUNT(*) FROM courses WHERE active=1") or 0,
            "plans_in_progress": db.scalar("SELECT COUNT(*) FROM learning_plans WHERE status='In progress'") or 0,
            "completed_this_year": db.scalar("SELECT COUNT(*) FROM learning_plans WHERE status='Completed' AND completed_on LIKE ?", (f"{year}-%",)) or 0,
            "certifications_expiring": len(expiring_certifications())}


def staff_page(lang: str = "et"):
    et = lang != "en"
    employee_rows = db.employees_min()
    active_courses = courses(active_only=True)
    course_rows = courses()
    plan_rows = all_plans()
    cert_rows = certifications_for()
    expiring = {row["id"] for row in expiring_certifications()}
    labels = {"title": "Koolitus ja areng" if et else "Learning & development",
              "course": "Koolitus" if et else "Course", "plans": "Arengukavad" if et else "Learning plans",
              "certs": "Sertifikaadid" if et else "Certifications", "save": "Salvesta" if et else "Save",
              "assign": "Määra" if et else "Assign", "soon": "Tähtaeg läheneb" if et else "Expiring soon"}
    course_form = Form(Input(name="name", placeholder=labels["course"], required=True),
                       Select(*[Option(c.title(), value=c) for c in COURSE_CATEGORIES], name="category"),
                       Input(name="provider", placeholder="Pakkuja / Provider"), Button(labels["save"], type="submit", cls="btn primary"),
                       method="post", action="/learning/courses", cls="inline-form")
    course_table = Table(Thead(Tr(Th(labels["course"]), Th("Kategooria" if et else "Category"), Th("Pakkuja" if et else "Provider"), Th(""))), Tbody(*[
        Tr(Td(c["name"]), Td(c["category"]), Td(c["provider"]), Td(A("Deaktiveeri" if et else "Deactivate", href=f"/learning/courses/{c['id']}/deactivate", cls="btn sm") if c["active"] else ("Mitteaktiivne" if et else "Inactive"))) for c in course_rows] or [Tr(Td("Koolitusi pole." if et else "No courses yet.", colspan="4"))]), cls="tbl")
    assign_form = Form(Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in employee_rows], name="employee_id"), Select(*[Option(c["name"], value=str(c["id"])) for c in active_courses], name="course_id"), Input(type="date", name="due_date"), Button(labels["assign"], type="submit", cls="btn primary"), method="post", action="/learning/plans", cls="inline-form")
    progress_label = "Edenemine" if et else "Progress"
    due_label = "Tähtaeg" if et else "Due"
    plan_table = Table(Thead(Tr(Th("Töötaja" if et else "Employee"), Th(labels["course"]), Th("Staatus" if et else "Status"), Th(progress_label), Th(due_label))), Tbody(*[
        Tr(Td(p["employee_name"]), Td(p["course_name"]), Td(p["status"]),
           Td(Form(Input(type="number", name="progress", min="0", max="100", value=str(p["progress"])),
                    Button(labels["save"], type="submit", cls="btn sm"), method="post",
                    action=f"/learning/plans/{p['id']}/progress", cls="inline-form")),
           Td(p["due_date"] or "—")) for p in plan_rows] or [Tr(Td("Arengukavu pole." if et else "No learning plans yet.", colspan="5"))]), cls="tbl")
    cert_table = Table(Thead(Tr(Th("Töötaja" if et else "Employee"), Th(labels["certs"]), Th("Kehtiv kuni" if et else "Expires"), Th(""))), Tbody(*[
        Tr(Td(c["employee_name"]), Td(c["name"]), Td(Span(c["expires_on"] or "—", cls="pill pending" if c["id"] in expiring else "pill")), Td(A("Eemalda" if et else "Remove", href=f"/learning/certifications/{c['id']}/remove", cls="btn sm"))) for c in cert_rows] or [Tr(Td("Sertifikaate pole." if et else "No certifications yet.", colspan="4"))]), cls="tbl")
    cert_form = Form(Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in employee_rows], name="employee_id"), Input(name="name", placeholder="Sertifikaat / Certification", required=True), Input(type="date", name="issued_on"), Input(type="date", name="expires_on"), Button(labels["save"], type="submit", cls="btn primary"), method="post", action="/learning/certifications", cls="inline-form")
    k = kpis()
    subtitle = (f"{k['courses_active']} aktiivset koolitust · {k['plans_in_progress']} pooleli · "
                f"{k['certifications_expiring']} {labels['soon'].lower()}" if et else
                f"{k['courses_active']} active courses · {k['plans_in_progress']} in progress · "
                f"{k['certifications_expiring']} expiring soon")
    return Div(Div(H1(labels["title"]), P(subtitle, cls="sub"), cls="page-title"),
               Div(Div(H3(labels["course"]), course_form, course_table, cls="card"), Div(H3(labels["plans"]), assign_form, plan_table, cls="card"), Div(H3(labels["certs"]), cert_form, cert_table, cls="card")))
