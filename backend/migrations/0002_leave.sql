CREATE TABLE holidays (
    day  DATE PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE leave_types (
    code          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    annual_days   INTEGER NOT NULL CHECK (annual_days >= 0),
    paid          BOOLEAN NOT NULL
);

INSERT INTO leave_types (code, name, annual_days, paid) VALUES
    ('annual', 'Annual leave', 30, TRUE),
    ('sick', 'Sick leave', 15, TRUE),
    ('unpaid', 'Unpaid leave', 0, FALSE);

CREATE TABLE leave_requests (
    id          SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    leave_type  TEXT NOT NULL REFERENCES leave_types(code),
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    days        INTEGER NOT NULL CHECK (days > 0),
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    reason      TEXT NOT NULL DEFAULT '',
    CHECK (end_date >= start_date)
);

CREATE INDEX leave_requests_employee_idx ON leave_requests (employee_id, status);
