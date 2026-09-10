"""A simple statistical forecast for each industry index.

Idea: take the daily log returns over a recent window, get their average (the
trend) and their standard deviation (the volatility), then project the future
as that trend plus that much random noise. That gives a "cone" of possible
paths, which we describe with five percentiles.



Used AI to help us with the equation and creation of the forecasting function and reviewed over it. We dug into other methods it used initially and decided that Brownian motion was the best decision for the project.
While it does look complicated, the forecasting is simply using existing equations and capturing that data to show the trend line and confidence intervals
"""
from statistics import NormalDist

import numpy as np
import pandas as pd

from .config import BOOM_START

TRADING_DAYS = 252
DAYS_PER_MONTH = 21

# The trend is the shakiest input - a few years of daily returns is a weak bet on the
# future - so rather than extrapolate it at full strength (or drop it to zero), the model
# always damps it to half. This is fixed, not a user choice: the page used to offer
# "historical / half / no trend" as a control, but that just moved the guesswork onto
# whoever was clicking the button. Half is the one defensible middle ground.
DRIFT_SCALE = 0.5

# How far back to look when measuring trend and volatility.
LOOKBACKS = {"1y": "Last 1 year", "2y": "Last 2 years", "boom": "Since ChatGPT launch"}
LOOKBACK_DAYS = {"1y": TRADING_DAYS, "2y": 2 * TRADING_DAYS, "boom": None}

# The percentiles we draw, and the number of standard deviations each one sits at.
QUANTILES = {"p10": 0.10, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90}
Z_SCORES = {name: NormalDist().inv_cdf(q) for name, q in QUANTILES.items()}


def forecast_series(series, horizon_months, lookback):
    """Forecast one index. Returns (percentile paths, summary numbers)."""
    s = series.dropna()

    days = LOOKBACK_DAYS[lookback]
    window = s.iloc[-days:] if days else s.loc[BOOM_START:]
    log_returns = np.log(window).diff().dropna()

    mu = float(log_returns.mean()) * DRIFT_SCALE     # trend per day, damped to half
    sigma = float(log_returns.std())                 # volatility per day
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


def forecast_all(index, horizon_months, lookback):
    """Run forecast_series on every column of the industry index table."""
    return {name: forecast_series(index[name], horizon_months, lookback)
            for name in index.columns}
