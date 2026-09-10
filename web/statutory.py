"""Estonian TÖR and TSD CSV exports for payroll runs."""
from __future__ import annotations

import csv
import io
import re

import db


TOR_HEADERS = (
    "Ees- ja perekonnanimi", "Isikukood", "Töösuhte algus", "Lepingu liik",
    "Normtundide osakaal", "Põhitöötasu", "Viimase muudatuse kuupäev",
)
TSD_HEADERS = (
    "Ees- ja perekonnanimi", "Isikukood", "Brutopalk", "Palk maksustamise kuul",
    "Tulumaks", "Kogumispension II sammas", "Kohustusliku kogumispensioni maksed",
    "Töötaja töötuskindlustusmakse", "Tööandja töötuskindlustusmakse",
    "Sotsiaalmaks", "Krediidijääk",
)


def _csv(headers: tuple[str, ...], rows: list[dict]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(header, "") for header in headers])
    return "\ufeff" + output.getvalue()


def _amount(value) -> float:
    return round(float(value or 0), 2)


def _money(value) -> str:
    return f"{_amount(value):.2f}"


def build_tor(period: str) -> tuple[str, int]:
    """Build a TÖR-style employment snapshot for active employees.

    ``employees`` is the only employment source in the current product. The
    nullable statutory columns are intentionally blank until the employer
    supplies them, instead of fabricating personal IDs or amendments.
    """
    employees = db.rows("""SELECT first_name,last_name,personal_code,date_of_joining,
                                  employment_type,working_time_ratio,base_salary,
                                  latest_amendment_date
                           FROM employees WHERE status='Active'
                           ORDER BY first_name,last_name""")
    data = [{
        "Ees- ja perekonnanimi": f"{e['first_name'] or ''} {e['last_name'] or ''}".strip(),
        "Isikukood": e["personal_code"] or "",
        "Töösuhte algus": e["date_of_joining"] or "",
        "Lepingu liik": e["employment_type"] or "",
        "Normtundide osakaal": f"{_amount(e['working_time_ratio'] or 1):.2f}",
        "Põhitöötasu": _money(e["base_salary"]),
        "Viimase muudatuse kuupäev": e["latest_amendment_date"] or "",
    } for e in employees]
    return _csv(TOR_HEADERS, data), len(data)


def _line_amount(lines: list[dict], patterns: tuple[str, ...]) -> float | None:
    for line in lines:
        label = (line.get("label") or "").lower()
        if any(re.search(pattern, label) for pattern in patterns):
            return _amount(line["amount"])
    return None


def build_tsd(run_id: int) -> tuple[str, int, str]:
    run = db.one("SELECT period FROM pay_runs WHERE id=?", (run_id,))
    if not run:
        raise ValueError("Pay run not found")
    payslips = db.rows("""SELECT p.*,e.first_name,e.last_name,e.personal_code
                          FROM payslips p JOIN employees e ON e.id=p.employee_id
                          WHERE p.run_id=? ORDER BY e.first_name,e.last_name""", (run_id,))
    data = []
    for slip in payslips:
        lines = db.payslip_lines(slip["id"])
        gross = _amount(slip.get("gross_pay") or slip.get("gross"))
        tax = _line_amount(lines, (r"income tax", r"tulumaks"))
        pension = _line_amount(lines, (r"funded pension", r"ii pillar", r"kogumispension"))
        employee_unemployment = _line_amount(lines, (r"employee unemployment", r"töötaja.*töötuskindlust"))
        employer_unemployment = _line_amount(lines, (r"employer unemployment", r"tööandja.*töötuskindlust"))
        social_tax = _line_amount(lines, (r"social tax", r"sotsiaalmaks"))
        # Current payroll calculation has no employer-cost social-tax line.
        # Until such a line exists, Estonia's 33% rate is applied to gross.
        social_tax = _amount(gross * 0.33) if social_tax is None else social_tax
        credit = _line_amount(lines, (r"credit", r"krediid", r"jääd")) or 0
        name = f"{slip['first_name'] or ''} {slip['last_name'] or ''}".strip()
        data.append({
            "Ees- ja perekonnanimi": name, "Isikukood": slip["personal_code"] or "",
            "Brutopalk": _money(gross), "Palk maksustamise kuul": _money(gross),
            "Tulumaks": _money(tax), "Kogumispension II sammas": _money(pension),
            "Kohustusliku kogumispensioni maksed": _money(pension),
            "Töötaja töötuskindlustusmakse": _money(employee_unemployment),
            "Tööandja töötuskindlustusmakse": _money(employer_unemployment),
            "Sotsiaalmaks": _money(social_tax), "Krediidijääk": _money(credit),
        })
    return _csv(TSD_HEADERS, data), len(data), run["period"]


def record_export(kind: str, period: str, file_name: str, payload: str,
                  row_count: int, created_by: str | None = None) -> int:
    with db.cursor() as conn:
        return conn.execute("""INSERT INTO statutory_exports
            (kind,period,file_name,row_count,payload,created_by)
            VALUES (?,?,?,?,?,?)""", (kind, period, file_name, row_count, payload, created_by)).lastrowid


def export_history() -> list[dict]:
    return db.rows("SELECT * FROM statutory_exports ORDER BY created_at DESC,id DESC")
