"""Weekly aggregation of raw company registration data."""

import pandas as pd


def aggregate_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw company records to ISO-week registration counts.

    Input columns: 'eintragsdatum' (date-like), 'legalform_short' (str | None)
    Output columns: iso_year, iso_week, n_registrations, ag_share, gmbh_share
    Sorted ascending by (iso_year, iso_week).
    """
    dates = pd.to_datetime(df["eintragsdatum"])
    iso = dates.dt.isocalendar()

    temp = pd.DataFrame({
        "iso_year": iso["year"].astype(int),
        "iso_week": iso["week"].astype(int),
        "lf": df["legalform_short"].str.upper().fillna(""),
    })
    temp["is_ag"] = (temp["lf"] == "AG").astype(int)
    temp["is_gmbh"] = (temp["lf"] == "GMBH").astype(int)

    agg = temp.groupby(["iso_year", "iso_week"], as_index=False).agg(
        n_registrations=("lf", "count"),
        ag_count=("is_ag", "sum"),
        gmbh_count=("is_gmbh", "sum"),
    )
    agg["ag_share"] = agg["ag_count"] / agg["n_registrations"]
    agg["gmbh_share"] = agg["gmbh_count"] / agg["n_registrations"]

    return (
        agg.drop(columns=["ag_count", "gmbh_count"])
        .sort_values(["iso_year", "iso_week"])
        .reset_index(drop=True)
    )
