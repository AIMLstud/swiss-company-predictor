"""Streamlit dashboard: weekly company registration predictions for Canton Lucerne."""

from __future__ import annotations

from datetime import date

import streamlit as st

st.set_page_config(
    page_title="Swiss Company Predictor – Kanton Luzern",
    page_icon="🏢",
    layout="wide",
)


# ── Cached data helpers ───────────────────────────────────────────────────────


@st.cache_data(ttl=3600)
def load_raw() -> object:
    from training.train import load_data

    return load_data()


@st.cache_data(ttl=3600)
def load_weekly(_raw_df) -> object:
    from features.aggregation import aggregate_weekly

    return aggregate_weekly(_raw_df)


@st.cache_data(ttl=3600)
def get_prediction(year: int, week: int, _weekly_df) -> dict:
    """Run prediction using pre-loaded weekly aggregate to avoid double DB hit."""
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost

    from common.config import get_settings
    from inference.predict import _build_feature_row, _get_latest_run_id
    from training.train import FEATURE_COLS

    cfg = get_settings()
    uri = cfg.mlflow_tracking_uri
    mlflow.set_tracking_uri(uri)

    run_id = _get_latest_run_id("swiss_company_predictor", uri)
    X = _build_feature_row(_weekly_df, year, week)[FEATURE_COLS].to_numpy()

    client = mlflow.MlflowClient()
    tags = client.get_run(run_id).data.tags

    p10 = mlflow.sklearn.load_model(tags["model_uri_p10"])
    p50 = mlflow.xgboost.load_model(tags["model_uri_p50"])
    p90 = mlflow.sklearn.load_model(tags["model_uri_p90"])

    return {
        "p10": max(0.0, float(p10.predict(X)[0])),
        "p50": max(0.0, float(p50.predict(X)[0])),
        "p90": max(0.0, float(p90.predict(X)[0])),
        "run_id": run_id,
    }


def _current_iso_week() -> tuple[int, int]:
    iso = date.today().isocalendar()
    return int(iso.year), int(iso.week)


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("Konfiguration")
default_year, default_week = _current_iso_week()
target_year = int(
    st.sidebar.number_input("Jahr", min_value=2020, max_value=2030, value=default_year)
)
target_week = int(st.sidebar.number_input("KW", min_value=1, max_value=53, value=default_week))
n_history = st.sidebar.slider("Historische Wochen (Grafik)", 26, 156, 52)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("Firmengründungen – Kanton Luzern")
st.caption(f"Prognose für KW {target_week:02d} / {target_year}")

# ── Load raw + weekly data ────────────────────────────────────────────────────

weekly = None
with st.spinner("Lade historische Daten…"):
    try:
        raw_df = load_raw()
        weekly = load_weekly(raw_df)
    except Exception as exc:
        st.error(f"Datenbankfehler – historische Daten nicht verfügbar: {exc}")

# ── Prediction panel ──────────────────────────────────────────────────────────

st.subheader(f"Prognose KW {target_week:02d} / {target_year}")

if weekly is not None:
    with st.spinner("Berechne Prognose…"):
        try:
            result = get_prediction(target_year, target_week, weekly)
            col1, col2, col3 = st.columns(3)
            col1.metric("P10 – untere Grenze", f"{result['p10']:.1f}")
            col2.metric("P50 – Median", f"{result['p50']:.1f}")
            col3.metric("P90 – obere Grenze", f"{result['p90']:.1f}")
            st.caption(f"MLflow Run-ID: `{result['run_id']}`")
        except ValueError as exc:
            st.warning(f"Nicht genug History für diese Woche: {exc}")
        except Exception as exc:
            st.error(f"Prognose fehlgeschlagen (kein trainiertes Modell?): {exc}")
else:
    st.info("Prognose nicht verfügbar – keine Datenbankverbindung.")

# ── Historical chart ──────────────────────────────────────────────────────────

st.subheader("Historische Registrierungen")

if weekly is not None and not weekly.empty:
    import plotly.graph_objects as go

    tail = weekly.sort_values(["iso_year", "iso_week"]).tail(n_history).copy()
    tail["label"] = tail.apply(lambda r: f"{int(r.iso_year)}-W{int(r.iso_week):02d}", axis=1)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tail["label"],
            y=tail["n_registrations"],
            mode="lines+markers",
            name="Registrierungen",
            line={"color": "#1f77b4"},
            marker={"size": 4},
        )
    )
    fig.update_layout(
        xaxis_title="ISO-Woche",
        yaxis_title="Anzahl Registrierungen",
        xaxis={"tickangle": -45, "nticks": 20},
        height=400,
        margin={"t": 20, "b": 60},
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    last = weekly.sort_values(["iso_year", "iso_week"]).iloc[-1]
    col_ag, col_gmbh = st.columns(2)
    col_ag.metric("AG-Anteil (letzte Woche)", f"{last['ag_share']:.1%}")
    col_gmbh.metric("GmbH-Anteil (letzte Woche)", f"{last['gmbh_share']:.1%}")
else:
    st.info("Keine historischen Daten verfügbar.")
