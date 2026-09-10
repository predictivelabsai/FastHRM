-- Estonian holiday and incapacity pay calculations use the existing approved
-- leave requests as their source of dates. The index keeps preparation fast.
CREATE INDEX IF NOT EXISTS idx_leave_requests_pay_type_status
    ON leave_requests(employee_id, leave_type, status, from_date, to_date);
