"""Statistical forecasts for each industry index.

Model: daily log returns over a lookback window give a drift (mu) and volatility
(sigma). Future log-price is normal with mean mu*t and variance sigma^2*t, which
yields closed-form quantile paths (a lognormal "volatility cone"). The drift is
the fragile input, so the page exposes three drift assumptions side by side.
"""
from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd

from .config import BOOM_START

TRADING_DAYS = 252
DAYS_PER_MONTH = 21

DRIFT_MODES = {
    "historical": "Historical trend",
    "half": "Half of historical trend",
    "zero": "No trend (random walk)",
}
DRIFT_SCALE = {"historical": 1.0, "half": 0.5, "zero": 0.0}

LOOKBACKS = {
    "1y": "Last 1 year",
    "2y": "Last 2 years",
    "boom": "Since ChatGPT launch",
}
LOOKBACK_DAYS = {"1y": TRADING_DAYS, "2y": 2 * TRADING_DAYS, "boom": None}

QUANTILES = {"p10": 0.10, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90}
_Z = {name: NormalDist().inv_cdf(q) for name, q in QUANTILES.items()}


def forecast_series(series: pd.Series, horizon_months: int, lookback: str,
                    drift_mode: str) -> tuple[pd.DataFrame, dict]:
    """Return (quantile paths indexed by future business days, summary stats)."""
    s = series.dropna()
    days = LOOKBACK_DAYS[lookback]
    window = s.iloc[-days:] if days else s.loc[BOOM_START:]
    log_returns = np.log(window).diff().dropna()

    mu = float(log_returns.mean()) * DRIFT_SCALE[drift_mode]
    sigma = float(log_returns.std(ddof=1))
    s0 = float(s.iloc[-1])
    horizon_days = horizon_months * DAYS_PER_MONTH

    t = np.arange(1, horizon_days + 1)
    dates = pd.bdate_range(s.index[-1], periods=horizon_days + 1)[1:]
    paths = pd.DataFrame(
        {name: s0 * np.exp(mu * t + z * sigma * np.sqrt(t)) for name, z in _Z.items()},
        index=dates,
    )

    stats = {
        "last_date": s.index[-1].date().isoformat(),
        "last_value": round(s0, 1),
        "lookback_start": window.index[0].date().isoformat(),
        "observations": int(len(log_returns)),
        "ann_drift_pct": round(float(np.exp(mu * TRADING_DAYS) - 1) * 100, 1),
        "ann_vol_pct": round(float(sigma * np.sqrt(TRADING_DAYS)) * 100, 1),
        "horizon_months": horizon_months,
        "median_change_pct": round(float(paths["p50"].iloc[-1] / s0 - 1) * 100, 1),
        "p10_change_pct": round(float(paths["p10"].iloc[-1] / s0 - 1) * 100, 1),
        "p90_change_pct": round(float(paths["p90"].iloc[-1] / s0 - 1) * 100, 1),
        "prob_gain_pct": round(float(_prob_positive(mu, sigma, horizon_days)) * 100),
    }
    return paths, stats


def _prob_positive(mu: float, sigma: float, days: int) -> float:
    """P(index above today's level at the horizon) under the lognormal model."""
    if sigma <= 0:
        return 1.0 if mu > 0 else 0.0
    return 1 - NormalDist().cdf(-mu * days / (sigma * np.sqrt(days)))


def forecast_all(index: pd.DataFrame, horizon_months: int, lookback: str, drift_mode: str) -> dict:
    """Forecast every column of the industry index frame."""
    return {
        name: forecast_series(index[name], horizon_months, lookback, drift_mode)
        for name in index.columns
    }
