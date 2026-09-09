"""Tests for the pure data transforms in services/market_data.py.

`load_prices` / `ticker_series` hit the network or a disk cache, so these tests
monkeypatch `ticker_series` rather than touching yfinance.
"""
import pandas as pd

from services import market_data


def test_rebase_indexes_a_series_to_100_at_the_first_row():
    s = pd.Series([50.0, 100.0, 150.0])
    rebased = market_data.rebase(s)
    assert rebased.iloc[0] == 100.0
    assert rebased.iloc[-1] == 300.0


def test_rebase_indexes_each_dataframe_column_independently():
    df = pd.DataFrame({"A": [10.0, 20.0], "B": [5.0, 5.0]})
    rebased = market_data.rebase(df)
    assert rebased["A"].iloc[0] == 100.0
    assert rebased["A"].iloc[-1] == 200.0
    assert rebased["B"].iloc[-1] == 100.0  # a flat series stays at its rebased start


def test_price_stats_computes_return_and_drawdown(monkeypatch):
    dates = pd.date_range("2023-01-01", periods=5, freq="D")
    series = pd.Series([100.0, 120.0, 90.0, 110.0, 130.0], index=dates)
    monkeypatch.setattr(market_data, "ticker_series", lambda ticker, start=None: series)

    stats = market_data.price_stats("TEST", dates[0])

    assert stats["start_date"] == "2023-01-01"
    assert stats["end_date"] == "2023-01-05"
    assert stats["start_price"] == 100.0
    assert stats["end_price"] == 130.0
    assert stats["total_return_pct"] == 30.0
    # peak 120 -> trough 90 is a 25% drawdown
    assert stats["max_drawdown_pct"] == -25.0


def test_price_stats_is_empty_with_fewer_than_two_points(monkeypatch):
    monkeypatch.setattr(market_data, "ticker_series", lambda ticker, start=None: pd.Series([100.0]))
    assert market_data.price_stats("TEST", None) == {}
