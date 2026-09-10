-- Phase 2 shifts, roster, time clocks and location-aware capture.
CREATE TABLE IF NOT EXISTS shift_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    break_minutes INTEGER NOT NULL DEFAULT 0,
    hourly_rate_multiplier REAL NOT NULL DEFAULT 1.0,
    color TEXT
);

CREATE TABLE IF NOT EXISTS shift_locations (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    radius_m REAL NOT NULL DEFAULT 150
);

CREATE TABLE IF NOT EXISTS shift_assignments (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    shift_type_id INTEGER NOT NULL REFERENCES shift_types(id),
    shift_date TEXT NOT NULL,
    location_label TEXT,
    status TEXT NOT NULL DEFAULT 'Scheduled'
        CHECK (status IN ('Scheduled', 'Completed', 'Missed', 'Cancelled')),
    notes TEXT,
    UNIQUE(employee_id, shift_date, shift_type_id)
);

CREATE TABLE IF NOT EXISTS clock_punches (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    shift_assignment_id INTEGER REFERENCES shift_assignments(id),
    punch_type TEXT NOT NULL CHECK (punch_type IN ('In', 'Out', 'Break Start', 'Break End')),
    punched_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'Web' CHECK (source IN ('Web', 'Mobile', 'Kiosk', 'Terminal')),
    latitude REAL,
    longitude REAL,
    accuracy_m REAL,
    note TEXT,
    on_site INTEGER
);

CREATE INDEX IF NOT EXISTS idx_shift_assignments_date ON shift_assignments(shift_date);
CREATE INDEX IF NOT EXISTS idx_clock_punches_employee_date ON clock_punches(employee_id, punched_at);
CREATE INDEX IF NOT EXISTS idx_clock_punches_assignment ON clock_punches(shift_assignment_id);
