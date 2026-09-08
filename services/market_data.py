"""Price data: yfinance download with a once-a-day disk cache, industry indices, stats."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import numpy as np
import pandas as pd
import yfinance as yf

from .config import (BASELINE_START, BENCHMARK, BENCHMARK_TICKER, BOOM_START, CACHE_DIR,
                     HISTORY_START, INDUSTRIES, TICKERS)

TRADING_DAYS = 252


def _cache_path() -> "Path":
    return CACHE_DIR / f"prices_{dt.date.today():%Y-%m-%d}.pkl"


@lru_cache(maxsize=1)
def load_prices() -> pd.DataFrame:
    """Adjusted daily closes for every ticker since HISTORY_START (columns = tickers)."""
    path = _cache_path()
    if path.exists():
        return pd.read_pickle(path)

    raw = yf.download(TICKERS, start=HISTORY_START, auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        raise RuntimeError("yfinance returned no data. Check your internet connection and retry.")
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    close = close.sort_index().ffill()
    close = close.dropna(axis=1, how="all")
    close.index = pd.to_datetime(close.index)
    close.index.name = "Date"
    close.columns.name = None

    for old in CACHE_DIR.glob("prices_*.pkl"):
        old.unlink(missing_ok=True)
    close.to_pickle(path)
    return close


def rebase(frame):
    """Index a frame or series to 100 at its first row."""
    return frame / frame.iloc[0] * 100


@lru_cache(maxsize=1)
def industry_index() -> pd.DataFrame:
    """Equal-weight rebased index per industry (=100 on BASELINE_START) plus the benchmark."""
    close = load_prices().loc[BASELINE_START:].dropna(how="any")
    norm = rebase(close)
    index = pd.DataFrame({
        industry: norm[[t for t in tickers if t in norm.columns]].mean(axis=1)
        for industry, tickers in INDUSTRIES.items()
    })
    index[BENCHMARK] = norm[BENCHMARK_TICKER]
    index.index.name = "Date"
    return index


def years() -> list[int]:
    return sorted(int(y) for y in industry_index().index.year.unique())


def scorecard(start: str = BOOM_START) -> pd.Series:
    """Total return (%) of each industry index and the benchmark since ``start``."""
    window = rebase(industry_index().loc[start:])
    return (window.iloc[-1] - 100).sort_values()


def last_updated() -> str:
    return load_prices().index[-1].date().isoformat()


def period_start(period: str) -> pd.Timestamp:
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


def ticker_series(ticker: str, start=None) -> pd.Series:
    series = load_prices()[ticker].dropna()
    if start is not None:
        series = series.loc[pd.Timestamp(start):]
    return series


def price_stats(ticker: str, start) -> dict:
    """Total return, CAGR, volatility and drawdown for one ticker from ``start``."""
    s = ticker_series(ticker, start)
    if len(s) < 2:
        return {}
    daily = np.log(s).diff().dropna()
    years_span = max((s.index[-1] - s.index[0]).days / 365.25, 1 / 365.25)
    total = float(s.iloc[-1] / s.iloc[0] - 1)
    running_max = s.cummax()
    drawdown = float((s / running_max - 1).min())
    return {
        "start_date": s.index[0].date().isoformat(),
        "end_date": s.index[-1].date().isoformat(),
        "start_price": round(float(s.iloc[0]), 2),
        "end_price": round(float(s.iloc[-1]), 2),
        "total_return_pct": round(total * 100, 1),
        "cagr_pct": round(((1 + total) ** (1 / years_span) - 1) * 100, 1),
        "ann_vol_pct": round(float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS)) * 100, 1),
        "max_drawdown_pct": round(drawdown * 100, 1),
    }
