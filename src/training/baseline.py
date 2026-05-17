"""Simple lag baselines for benchmarking trained models."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Metrics:
    mae: float
    rmse: float


def _compute(y_true: np.ndarray, y_pred: np.ndarray) -> Metrics:
    errors = y_true.astype(float) - y_pred.astype(float)
    return Metrics(
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(errors**2))),
    )


def lag1_baseline(df: pd.DataFrame) -> Metrics:
    """Predict y[t] = lag_1[t]  (previous week's count)."""
    return _compute(df["n_registrations"].to_numpy(), df["lag_1"].to_numpy())


def lag52_baseline(df: pd.DataFrame) -> Metrics:
    """Predict y[t] = lag_52[t]  (same week last year)."""
    return _compute(df["n_registrations"].to_numpy(), df["lag_52"].to_numpy())
