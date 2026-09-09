"""Tests for the lognormal drift/volatility cone in services/forecast.py."""
import numpy as np
import pandas as pd

from services import forecast


def _synthetic_series(periods: int = 300, seed: int = 0) -> pd.Series:
    dates = pd.bdate_range("2024-01-01", periods=periods)
    rng = np.random.default_rng(seed)
    daily_returns = rng.normal(0.0005, 0.01, len(dates))
    prices = 100 * np.exp(np.cumsum(daily_returns))
    return pd.Series(prices, index=dates)


def test_forecast_series_quantiles_are_ordered():
    paths, _ = forecast.forecast_series(_synthetic_series(), horizon_months=6,
                                        lookback="1y", drift_mode="historical")
    last = paths.iloc[-1]
    assert last["p10"] < last["p25"] < last["p50"] < last["p75"] < last["p90"]


def test_zero_drift_mode_has_no_annualized_drift():
    _, stats = forecast.forecast_series(_synthetic_series(), horizon_months=6,
                                        lookback="1y", drift_mode="zero")
    assert stats["ann_drift_pct"] == 0.0
    # with mu = 0, the median path never moves
    assert stats["median_change_pct"] == 0.0


def test_horizon_controls_the_number_of_projected_business_days():
    paths, _ = forecast.forecast_series(_synthetic_series(), horizon_months=3,
                                        lookback="1y", drift_mode="half")
    assert len(paths) == 3 * forecast.DAYS_PER_MONTH


def test_prob_positive_is_a_probability():
    p = forecast._prob_positive(mu=0.0004, sigma=0.02, days=63)
    assert 0.0 <= p <= 1.0


def test_prob_positive_handles_zero_volatility():
    assert forecast._prob_positive(mu=0.01, sigma=0.0, days=10) == 1.0
    assert forecast._prob_positive(mu=-0.01, sigma=0.0, days=10) == 0.0
