CREATE TABLE departments (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    cost_center TEXT NOT NULL
);

CREATE TABLE employees (
    id             SERIAL PRIMARY KEY,
    employee_no    TEXT NOT NULL UNIQUE,
    full_name      TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE,
    department_id  INTEGER NOT NULL REFERENCES departments(id),
    hire_date      DATE NOT NULL,
    end_date       DATE,
    monthly_salary NUMERIC(12, 2) NOT NULL CHECK (monthly_salary >= 0),
    housing        NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (housing >= 0),
    transport      NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (transport >= 0),
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'on_leave', 'terminated')),
    CHECK (end_date IS NULL OR end_date >= hire_date)
);

CREATE INDEX employees_department_idx ON employees (department_id);
