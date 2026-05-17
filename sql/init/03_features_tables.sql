-- features.weekly_registrations
-- One row per ISO (year, week). Lag features and legalform shares are computed
-- at training time from this table, not stored here.
CREATE TABLE IF NOT EXISTS features.weekly_registrations (
    iso_year         INTEGER     NOT NULL,
    iso_week         INTEGER     NOT NULL,
    n_registrations  INTEGER     NOT NULL DEFAULT 0,
    coverage_ratio   NUMERIC(5, 4),          -- share of UIDs with scraping_status='success'
    month            INTEGER,
    quarter          INTEGER,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (iso_year, iso_week)
);
