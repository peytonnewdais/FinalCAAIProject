"""Stock prices from yfinance, plus the industry indices built from them.

The download takes a while, so the prices are saved to a pickle file in cache/
and re-downloaded only when the date changes.
"""
import datetime as dt

import numpy as np
import pandas as pd
import yfinance as yf

from .config import (BASELINE_START, BENCHMARK, BENCHMARK_TICKER, BOOM_START,
                     CACHE_DIR, HISTORY_START, INDUSTRIES, TICKERS)

TRADING_DAYS = 252

_prices = None               # the price table, once it has been loaded
_prices_date = None          # the day that table was downloaded


def load_prices():
    """Daily adjusted closing prices for every ticker. One column per ticker."""
    global _prices, _prices_date

    today = dt.date.today()
    if _prices is not None and _prices_date == today:
        return _prices

    path = CACHE_DIR / f"prices_{today}.pkl"
    if path.exists():
        close = pd.read_pickle(path)
    else:
        raw = yf.download(TICKERS, start=HISTORY_START, auto_adjust=True, progress=False)
        if raw is None or raw.empty:
            raise RuntimeError("yfinance returned no data. Check your internet connection.")

        # yfinance gives back columns like ("Close", "NVDA"), so keep the Close block.
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        close = close.sort_index().ffill().dropna(axis=1, how="all")
        close.index = pd.to_datetime(close.index)

        for old in CACHE_DIR.glob("prices_*.pkl"):   # only keep today's file
            old.unlink()
        close.to_pickle(path)

    _prices, _prices_date = close, today
    return close


def rebase(data):
    """Rescale prices so the first row equals 100. Works on a column or a table."""
    return data / data.iloc[0] * 100


def industry_index():
    """One index per industry: the average of its five rebased stocks, plus the S&P 500."""
    close = load_prices().loc[BASELINE_START:].dropna(how="any")
    norm = rebase(close)

    index = pd.DataFrame({
        industry: norm[[t for t in tickers if t in norm.columns]].mean(axis=1)
        for industry, tickers in INDUSTRIES.items()
    })
    index[BENCHMARK] = norm[BENCHMARK_TICKER]
    return index


def years():
    """Every year the index covers, for the slider marks."""
    return sorted(int(y) for y in industry_index().index.year.unique())


def scorecard(start=BOOM_START):
    """Total return (in %) of each industry index since the given date."""
    window = rebase(industry_index().loc[start:])
    return (window.iloc[-1] - 100).sort_values()


def last_updated():
    """The date of the most recent price, as text."""
    return str(load_prices().index[-1].date())


def period_start(period):
    """Turn a period name from config.PERIODS into a start date."""
    end = load_prices().index[-1]
    if period == "boom":
        return pd.Timestamp(BOOM_START)
    if period == "1y":
        return end - pd.DateOffset(years=1)
    if period == "3y":
        return end - pd.DateOffset(years=3)
    if period == "5y":
        return end - pd.DateOffset(years=5)
    return pd.Timestamp(HISTORY_START)


def ticker_series(ticker, start=None):
    """The price history of one ticker, optionally trimmed to start at a date."""
    series = load_prices()[ticker].dropna()
    if start is not None:
        series = series.loc[pd.Timestamp(start):]
    return series


def price_stats(ticker, start):
    """Return, growth rate, volatility and worst drop for one stock since 'start'."""
    s = ticker_series(ticker, start)
    if len(s) < 2:
        return {}

    daily = np.log(s).diff().dropna()          # daily log returns
    span_years = (s.index[-1] - s.index[0]).days / 365.25
    total = float(s.iloc[-1] / s.iloc[0] - 1)
    drawdown = float((s / s.cummax() - 1).min())

    return {
        "start_date": str(s.index[0].date()),
        "end_date": str(s.index[-1].date()),
        "start_price": round(float(s.iloc[0]), 2),
        "end_price": round(float(s.iloc[-1]), 2),
        "total_return_pct": round(total * 100, 1),
        "cagr_pct": round(((1 + total) ** (1 / span_years) - 1) * 100, 1),
        "ann_vol_pct": round(float(daily.std() * np.sqrt(TRADING_DAYS)) * 100, 1),
        "max_drawdown_pct": round(drawdown * 100, 1),
    }
