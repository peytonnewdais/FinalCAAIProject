"""A simple statistical forecast for each industry index.

Idea: take the daily log returns over a recent window, get their average (the
drift) and their standard deviation (the volatility), then assume the future
price keeps drifting at that rate with that much random noise. That gives a
"cone" of possible paths, which we describe with five percentiles.
"""
from statistics import NormalDist

import numpy as np
import pandas as pd

from .config import BOOM_START

TRADING_DAYS = 252
DAYS_PER_MONTH = 21

# The three drift assumptions offered on the page, and how much of the
# historical trend each one keeps.
DRIFT_MODES = {
    "historical": "Historical trend",
    "half": "Half of historical trend",
    "zero": "No trend (random walk)",
}
DRIFT_SCALE = {"historical": 1.0, "half": 0.5, "zero": 0.0}

# How far back to look when measuring drift and volatility.
LOOKBACKS = {"1y": "Last 1 year", "2y": "Last 2 years", "boom": "Since ChatGPT launch"}
LOOKBACK_DAYS = {"1y": TRADING_DAYS, "2y": 2 * TRADING_DAYS, "boom": None}

# The percentiles we draw, and the number of standard deviations each one sits at.
QUANTILES = {"p10": 0.10, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90}
Z_SCORES = {name: NormalDist().inv_cdf(q) for name, q in QUANTILES.items()}


def forecast_series(series, horizon_months, lookback, drift_mode):
    """Forecast one index. Returns (percentile paths, summary numbers)."""
    s = series.dropna()

    days = LOOKBACK_DAYS[lookback]
    window = s.iloc[-days:] if days else s.loc[BOOM_START:]
    log_returns = np.log(window).diff().dropna()

    mu = float(log_returns.mean()) * DRIFT_SCALE[drift_mode]     # drift per day
    sigma = float(log_returns.std())                             # volatility per day
    today_value = float(s.iloc[-1])
    horizon_days = horizon_months * DAYS_PER_MONTH

    # Uncertainty grows with the square root of time, which is what spreads the cone.
    t = np.arange(1, horizon_days + 1)
    dates = pd.bdate_range(s.index[-1], periods=horizon_days + 1)[1:]
    paths = pd.DataFrame(
        {name: today_value * np.exp(mu * t + z * sigma * np.sqrt(t))
         for name, z in Z_SCORES.items()},
        index=dates,
    )

    stats = {
        "last_date": str(s.index[-1].date()),
        "last_value": round(today_value, 1),
        "lookback_start": str(window.index[0].date()),
        "observations": len(log_returns),
        "ann_drift_pct": round((np.exp(mu * TRADING_DAYS) - 1) * 100, 1),
        "ann_vol_pct": round(sigma * np.sqrt(TRADING_DAYS) * 100, 1),
        "horizon_months": horizon_months,
        "median_change_pct": round(float(paths["p50"].iloc[-1] / today_value - 1) * 100, 1),
        "p10_change_pct": round(float(paths["p10"].iloc[-1] / today_value - 1) * 100, 1),
        "p90_change_pct": round(float(paths["p90"].iloc[-1] / today_value - 1) * 100, 1),
        "prob_gain_pct": round(prob_higher(mu, sigma, horizon_days) * 100),
    }
    return paths, stats


def prob_higher(mu, sigma, days):
    """Chance the index ends above today's level, under the same model."""
    if sigma <= 0:
        return 1.0 if mu > 0 else 0.0
    return 1 - NormalDist().cdf(-mu * days / (sigma * np.sqrt(days)))


def forecast_all(index, horizon_months, lookback, drift_mode):
    """Run forecast_series on every column of the industry index table."""
    return {name: forecast_series(index[name], horizon_months, lookback, drift_mode)
            for name in index.columns}
