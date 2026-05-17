-- ── raw.companies ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.companies (
    uid                  TEXT        PRIMARY KEY,
    name                 TEXT        NOT NULL,
    legalform_id         INTEGER,
    legalform_short      TEXT,
    status               TEXT,
    canton               TEXT,
    cantonal_excerpt_web TEXT,
    sogc_date            DATE,
    deletion_date        DATE,
    raw_search           JSONB,
    raw_detail           JSONB,
    first_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── raw.company_eintragsdatum ─────────────────────────────────────────────────
-- Populated by HR-Auszug scraping (or CSV seed). Separate table because the
-- data source differs from Zefix and each row carries a scraping_status.
CREATE TABLE IF NOT EXISTS raw.company_eintragsdatum (
    uid             TEXT        PRIMARY KEY REFERENCES raw.companies (uid),
    eintragsdatum   DATE,
    scraping_status TEXT        NOT NULL,   -- success | viewstate_missing | regex_no_match | http_error | timeout | csv_import
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── raw.sogc_publications ─────────────────────────────────────────────────────
-- One row per SOGC publication entry. Used only to identify new LU registrations;
-- the uid column is the key used downstream.
CREATE TABLE IF NOT EXISTS raw.sogc_publications (
    publication_id  BIGINT      PRIMARY KEY,   -- sogcPublication.sogcId
    sogc_date       DATE        NOT NULL,
    canton          TEXT        NOT NULL,
    uid             TEXT,
    mutation_types  JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sogc_publications_sogc_date
    ON raw.sogc_publications (sogc_date);
