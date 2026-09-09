"""Settings used by the whole app: industries, tickers, colors, dates."""
import os

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()                # reads the .env file so the Claude key is available

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)

APP_TITLE = "AI Boom Scorecard"
TEAM = "Team 8 - Peyton, Asad, Maya"
SOURCE = "Source: Yahoo Finance (yfinance) and SEC EDGAR annual filings"

BENCHMARK = "S&P 500 (SPY)"
BENCHMARK_TICKER = "SPY"

BOOM_START = "2022-11-30"        # the day ChatGPT launched
BASELINE_START = "2022-10-01"    # one month before, so every index starts level
HISTORY_START = "2020-01-01"     # how far back we download prices

# Five big companies in each of eight industries the AI boom touched.
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

COMPANY_NAMES = {
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC", "MU": "Micron",
    "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "META": "Meta", "AAPL": "Apple",
    "CRM": "Salesforce", "ORCL": "Oracle", "NOW": "ServiceNow", "PLTR": "Palantir",
    "SNOW": "Snowflake",
    "NEE": "NextEra Energy", "CEG": "Constellation Energy", "VST": "Vistra",
    "SO": "Southern Co", "DUK": "Duke Energy",
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs", "V": "Visa",
    "MS": "Morgan Stanley",
    "CAT": "Caterpillar", "GE": "GE Aerospace", "HON": "Honeywell", "DE": "Deere",
    "UNP": "Union Pacific",
    "ACN": "Accenture", "INFY": "Infosys", "CTSH": "Cognizant", "EPAM": "EPAM Systems",
    "GLOB": "Globant",
    "CHGG": "Chegg", "TTEC": "TTEC", "SSTK": "Shutterstock", "GETY": "Getty Images",
    "CNXC": "Concentrix",
}

# Flat lists built from the dictionary above, so the tickers are only typed once.
TICKER_INDUSTRY = {t: ind for ind, tickers in INDUSTRIES.items() for t in tickers}
COMPANY_TICKERS = [t for tickers in INDUSTRIES.values() for t in tickers]
TICKERS = sorted(set(COMPANY_TICKERS) | {BENCHMARK_TICKER})

# One color per industry, in the same order as INDUSTRIES, so an industry keeps
# its color on every chart.
COLORS = ["#1f73d0", "#eb6834", "#00a571", "#c88200",
          "#d96e97", "#008300", "#4a3aa7", "#e34948"]
INDUSTRY_COLORS = dict(zip(INDUSTRIES, COLORS))
INDUSTRY_COLORS[BENCHMARK] = "#33322f"

# Dates marked with a dotted line on the industry chart.
EVENTS = [
    ("2022-11-30", "ChatGPT launches"),
    ("2023-05-24", "NVDA guides AI blowout"),
    ("2025-01-27", "DeepSeek selloff"),
]

# The SEC asks every program to send a User-Agent with contact details.
SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "AI-Boom-Scorecard/1.0 (university research project; research@example.com)",
)

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
CLAUDE_EFFORT = os.getenv("SUMMARY_EFFORT", "medium")

# Periods offered on the compare page.
PERIODS = {
    "boom": "Since ChatGPT launch (Nov 30, 2022)",
    "1y": "Last 1 year",
    "3y": "Last 3 years",
    "5y": "Last 5 years",
}
