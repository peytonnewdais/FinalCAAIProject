"""Shared constants: industries, tickers, palette, events, and settings read from .env.

AI usage: see docs/AI_USAGE.md.

AI usage, we used AI to develop this function faster; however, AI's role was mainly to help us refactor the site as a whole which 
is why this function has its own file. 
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)

APP_TITLE = "AI Boom Scorecard"
TEAM = "Team 8 - Peyton, Asad, Maya"
SOURCE = "Source: Yahoo Finance (yfinance) adjusted closes; SEC EDGAR annual filings"

BENCHMARK = "S&P 500 (SPY)"
BENCHMARK_TICKER = "SPY"

BOOM_START = "2022-11-30"       # ChatGPT public launch
BASELINE_START = "2022-10-01"   # one month of shared pre-boom baseline for the industry index
HISTORY_START = "2020-01-01"    # deeper history for the compare page and forecast lookbacks

# Eight industry buckets, 5 tickers each. Insertion order is load-bearing: INDUSTRY_COLORS
# below zips this dict against COLORS to assign colors, and legend/stack order is
# list(INDUSTRIES), so reordering keys repaints every chart and a 9th industry needs a
# matching color. Each ticker belongs to exactly one bucket (TICKER_INDUSTRY assumes no
# overlap); keys are used raw as UI labels and dropdown values.
INDUSTRIES = {
    "Semiconductors & AI Hardware": ["NVDA", "AMD", "AVGO", "TSM", "MU"],
    "Big Tech & Cloud":             ["MSFT", "GOOGL", "AMZN", "META", "AAPL"],
    "Enterprise Software & Data":   ["CRM", "ORCL", "NOW", "PLTR", "SNOW"],
    "Energy & Utilities":           ["NEE", "CEG", "VST", "SO", "DUK"],
    "Financials":                   ["JPM", "BAC", "GS", "V", "MS"],
    "Industrials":                  ["CAT", "GE", "HON", "DE", "UNP"],
    "IT Services & Consulting":     ["ACN", "INFY", "CTSH", "EPAM", "GLOB"],
    "Content & Support Services":   ["CHGG", "TTEC", "SSTK", "GETY", "CNXC"],
}

# Ticker -> short display name, used in dropdown labels and chart legends. Must cover every
# ticker in INDUSTRIES: compare.py subscripts this directly, so a missing entry is a KeyError
# (edgar.py is the exception and falls back to the raw ticker). No entry for BENCHMARK_TICKER.
# Rows are grouped to mirror INDUSTRIES order for readability only; lookup ignores it.
COMPANY_NAMES = {
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC", "MU": "Micron",
    "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta", "AAPL": "Apple",
    "CRM": "Salesforce", "ORCL": "Oracle", "NOW": "ServiceNow", "PLTR": "Palantir", "SNOW": "Snowflake",
    "NEE": "NextEra Energy", "CEG": "Constellation Energy", "VST": "Vistra", "SO": "Southern Co",
    "DUK": "Duke Energy",
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs", "V": "Visa",
    "MS": "Morgan Stanley",
    "CAT": "Caterpillar", "GE": "GE Aerospace", "HON": "Honeywell", "DE": "Deere", "UNP": "Union Pacific",
    "ACN": "Accenture", "INFY": "Infosys", "CTSH": "Cognizant", "EPAM": "EPAM Systems", "GLOB": "Globant",
    "CHGG": "Chegg", "TTEC": "TTEC", "SSTK": "Shutterstock", "GETY": "Getty Images", "CNXC": "Concentrix",
}

TICKER_INDUSTRY = {t: ind for ind, tickers in INDUSTRIES.items() for t in tickers}
COMPANY_TICKERS = [t for tickers in INDUSTRIES.values() for t in tickers]
TICKERS = sorted(set(COMPANY_TICKERS) | {BENCHMARK_TICKER})

# One color per industry, in the same order as INDUSTRIES, so an industry keeps
# its color on every chart.
COLORS = ["#1f73d0", "#eb6834", "#00a571", "#c88200",
          "#d96e97", "#008300", "#4a3aa7", "#e34948"]
INDUSTRY_COLORS = dict(zip(INDUSTRIES, COLORS))
INDUSTRY_COLORS[BENCHMARK] = "#33322f"

EVENTS = [
    ("2022-11-30", "ChatGPT launches"),
    ("2023-05-24", "NVDA guides AI blowout"),
    ("2025-01-27", "DeepSeek selloff"),
]

# SEC asks for a descriptive User-Agent with contact details on every EDGAR request.
SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "AI-Boom-Scorecard/1.0 (university research project; research@example.com)",
)

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
# Named SUMMARY_EFFORT (not CLAUDE_EFFORT) because Claude Code exports CLAUDE_EFFORT
# into shells it launches, which would silently override the app's setting.
CLAUDE_EFFORT = os.getenv("SUMMARY_EFFORT", "medium")

PERIODS = {
    "boom": "Since ChatGPT launch (Nov 30, 2022)",
    "1y": "Last 1 year",
    "3y": "Last 3 years",
    "5y": "Last 5 years",
}
 