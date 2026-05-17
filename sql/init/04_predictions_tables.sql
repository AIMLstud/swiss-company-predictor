-- predictions.weekly
-- On-demand inference results written by the Streamlit app.
CREATE TABLE IF NOT EXISTS predictions.weekly (
    prediction_id    BIGSERIAL   PRIMARY KEY,
    target_iso_year  INTEGER     NOT NULL,
    target_iso_week  INTEGER     NOT NULL,
    predicted_count  NUMERIC(10, 2) NOT NULL,
    predicted_q05    NUMERIC(10, 2),
    predicted_q95    NUMERIC(10, 2),
    model_version    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (target_iso_year, target_iso_week, model_version)
);
