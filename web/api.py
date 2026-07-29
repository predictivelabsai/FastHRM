"""FastHRM public reads and token-gated integration writes."""

import db

from .api_core import Resource, SQLiteBackend, create_sqlite_api

RESOURCES = (
    Resource("employees", "employees", "Employees", "Employee master records and employment state.", search_fields=("code", "first_name", "last_name", "email", "designation")),
    Resource("departments", "departments", "Departments", "Organisation departments.", search_fields=("name",)),
    Resource("leave", "leave_requests", "Leave requests", "Employee leave requests and approval status.", write_fields=("employee_id", "leave_type", "from_date", "to_date", "days", "status", "reason", "applied_on"), search_fields=("leave_type", "status", "reason")),
    Resource("attendance", "attendance", "Attendance", "Daily attendance and recorded hours.", search_fields=("att_date", "status")),
)

backend = SQLiteBackend(db.DB_PATH, RESOURCES, initialize=db.init_schema)
api = create_sqlite_api(
    product="FastHRM", version="1.0.0",
    description="Open integration access to FastHRM people, leave, and attendance data.",
    base_url="https://hrm.fastsme.com", backend=backend, resources=RESOURCES,
)
