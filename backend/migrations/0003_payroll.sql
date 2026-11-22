CREATE TABLE tax_brackets (
    lower_bound NUMERIC(12, 2) PRIMARY KEY,
    rate        NUMERIC(5, 4) NOT NULL CHECK (rate >= 0 AND rate < 1)
);

INSERT INTO tax_brackets (lower_bound, rate) VALUES
    (0, 0),
    (5000, 0.05),
    (15000, 0.10),
    (40000, 0.15);

CREATE TABLE payroll_runs (
    id         SERIAL PRIMARY KEY,
    period     DATE NOT NULL UNIQUE CHECK (EXTRACT(DAY FROM period) = 1),
    status     TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'paid')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payslips (
    id             SERIAL PRIMARY KEY,
    run_id         INTEGER NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id    INTEGER NOT NULL REFERENCES employees(id),
    gross          NUMERIC(12, 2) NOT NULL,
    unpaid_days    INTEGER NOT NULL DEFAULT 0,
    social_ins     NUMERIC(12, 2) NOT NULL,
    tax            NUMERIC(12, 2) NOT NULL,
    net            NUMERIC(12, 2) NOT NULL,
    UNIQUE (run_id, employee_id),
    CHECK (net = gross - social_ins - tax)
);
