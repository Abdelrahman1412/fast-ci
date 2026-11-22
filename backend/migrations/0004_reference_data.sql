-- Reference data that every environment needs. Building it is what makes a
-- from-scratch test database slow, and what the cached dump skips.
CREATE TABLE exchange_rates (
    day      DATE NOT NULL,
    currency TEXT NOT NULL,
    rate     NUMERIC(14, 6) NOT NULL,
    PRIMARY KEY (day, currency)
);

INSERT INTO exchange_rates (day, currency, rate)
SELECT d::date, c, round((1 + random())::numeric, 6)
FROM generate_series('2015-01-01'::date, '2026-12-31'::date, interval '1 day') AS d,
     unnest(ARRAY['USD', 'EUR', 'GBP', 'INR', 'EGP', 'SAR', 'AED', 'QAR', 'KWD', 'OMR', 'BHD', 'JOD']) AS c;

INSERT INTO holidays (day, name)
SELECT make_date(y, 1, 1), 'New Year' FROM generate_series(2015, 2030) AS y
UNION ALL
SELECT make_date(y, 12, 2), 'National Day' FROM generate_series(2015, 2030) AS y;

CREATE TABLE audit_log (
    id         BIGSERIAL PRIMARY KEY,
    entity     TEXT NOT NULL,
    entity_id  INTEGER NOT NULL,
    action     TEXT NOT NULL,
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_entity_idx ON audit_log (entity, entity_id);
