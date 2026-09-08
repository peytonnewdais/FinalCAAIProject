"""SEC EDGAR client: ticker -> CIK, annual filings, AI-language scoring, R&D facts.

Every request carries the SEC-required User-Agent and is throttled well below the
10 requests/second fair-access limit. Parsed filings are cached on disk under
cache/edgar so a company is only downloaded once.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .config import CACHE_DIR, COMPANY_NAMES, SEC_USER_AGENT, TICKER_INDUSTRY

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

EDGAR_CACHE = CACHE_DIR / "edgar"
EDGAR_CACHE.mkdir(exist_ok=True)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"

HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
MIN_INTERVAL = 0.15          # seconds between requests (~6-7 req/s)
MAX_SNIPPETS = 12

# Per-term patterns for the breakdown; "AI" stays case-sensitive so "ai" prose never counts.
AI_TERMS = {
    "artificial intelligence": re.compile(r"\bartificial[\s-]intelligence\b", re.I),
    "AI": re.compile(r"\bAI\b"),
    "machine learning": re.compile(r"\bmachine[\s-]learning\b", re.I),
    "generative AI": re.compile(r"\bgenerative\s+AI\b|\bgen\s?AI\b", re.I),
    "large language model": re.compile(r"\blarge[\s-]language[\s-]models?\b|\bLLMs?\b"),
    "deep learning": re.compile(r"\bdeep[\s-]learning\b", re.I),
    "neural network": re.compile(r"\bneural[\s-]networks?\b", re.I),
}
# One union pattern so each occurrence is counted exactly once in the total.
AI_ANY = re.compile(
    r"(?i:\bartificial[\s-]intelligence\b|\bmachine[\s-]learning\b|\bgenerative\s+AI\b|\bgen\s?AI\b"
    r"|\blarge[\s-]language[\s-]models?\b|\bdeep[\s-]learning\b|\bneural[\s-]networks?\b)"
    r"|\bLLMs?\b|\bAI\b"
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")

RD_CONCEPTS = [
    ("us-gaap", "ResearchAndDevelopmentExpense"),
    ("us-gaap", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"),
    ("ifrs-full", "ResearchAndDevelopmentExpense"),
]
REVENUE_CONCEPTS = [
    ("us-gaap", "Revenues"),
    ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    ("us-gaap", "SalesRevenueNet"),
    ("ifrs-full", "Revenue"),
]


class EdgarError(RuntimeError):
    """Raised when EDGAR data cannot be fetched or a ticker is unknown."""


_lock = threading.Lock()
_last_request = 0.0


def _get(url: str, timeout: int = 120) -> requests.Response:
    """Throttled GET with the SEC User-Agent and a few retries on throttling."""
    global _last_request
    last_status = None
    for attempt in range(4):
        with _lock:
            wait = MIN_INTERVAL - (time.monotonic() - _last_request)
            if wait > 0:
                time.sleep(wait)
            _last_request = time.monotonic()
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        last_status = response.status_code
        if response.status_code == 200:
            return response
        if response.status_code in (403, 429, 503):
            time.sleep(2.0 * (attempt + 1))
            continue
        response.raise_for_status()
    raise EdgarError(f"EDGAR request failed with status {last_status}: {url}")


def _cached_json(path: Path, max_age_days: float, fetch) -> dict:
    if path.exists():
        age = (time.time() - path.stat().st_mtime) / 86400
        if age <= max_age_days:
            return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def ticker_map() -> dict:
    data = _cached_json(EDGAR_CACHE / "company_tickers.json", 7, lambda: _get(TICKERS_URL).json())
    return {row["ticker"].upper(): row for row in data.values()}


def cik_for(ticker: str) -> int:
    row = ticker_map().get(ticker.upper())
    if not row:
        raise EdgarError(f"{ticker} is not in SEC's ticker list.")
    return int(row["cik_str"])


def submissions(cik: int) -> dict:
    return _cached_json(EDGAR_CACHE / f"submissions_{cik}.json", 1,
                        lambda: _get(SUBMISSIONS_URL.format(cik=cik)).json())


def _filing_blocks(cik: int):
    """Yield the 'recent' filing block, then the older blocks EDGAR splits into extra files."""
    filings = submissions(cik)["filings"]
    yield filings["recent"]
    for extra in filings.get("files", []):
        name = extra["name"]
        yield _cached_json(EDGAR_CACHE / name, 30,
                           lambda n=name: _get(f"https://data.sec.gov/submissions/{n}").json())


def annual_filings(cik: int, count: int = 5) -> list[dict]:
    """Most recent annual reports (10-K / 20-F / 40-F), one per fiscal year, newest first."""
    filings, seen_years = [], set()
    for block in _filing_blocks(cik):
        for i, form in enumerate(block["form"]):
            if form not in ANNUAL_FORMS:
                continue
            report_date = block["reportDate"][i] or block["filingDate"][i]
            fiscal_year = int(report_date[:4])
            if fiscal_year in seen_years:
                continue
            seen_years.add(fiscal_year)
            accession = block["accessionNumber"][i]
            doc = block["primaryDocument"][i]
            filings.append({
                "form": form,
                "fiscal_year": fiscal_year,
                "filing_date": block["filingDate"][i],
                "report_date": report_date,
                "accession": accession,
                "url": ARCHIVE_URL.format(cik=cik, accession=accession.replace("-", ""), doc=doc),
            })
            if len(filings) >= count:
                return filings
    return filings


def _decode(content: bytes) -> str:
    """EDGAR documents are UTF-8 or Windows-1252; never let a wrong guess mangle quotes."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def _html_to_text(content: bytes) -> str:
    soup = BeautifulSoup(_decode(content), "lxml")
    for tag in soup(["script", "style", "ix:header"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


def _snippets(text: str, limit: int = MAX_SNIPPETS) -> list[str]:
    """Sentences that mention AI, ranked by how densely they discuss it."""
    candidates, seen = [], set()
    for sentence in SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not 60 <= len(sentence) <= 420:
            continue
        hits = len(AI_ANY.findall(sentence))
        if not hits:
            continue
        key = sentence[:80].lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append((hits, -len(sentence), sentence))
    candidates.sort(reverse=True)
    return [c[2] for c in candidates[:limit]]


def analyze_filing(filing: dict) -> dict:
    """Download one annual report and score its AI language. Cached by accession number."""
    path = EDGAR_CACHE / f"filing_{filing['accession']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    text = _html_to_text(_get(filing["url"]).content)
    words = max(len(text.split()), 1)
    total = len(AI_ANY.findall(text))
    result = {
        **filing,
        "word_count": words,
        "ai_mentions": total,
        "mentions_per_10k_words": round(total / words * 10_000, 2),
        "term_counts": {term: len(p.findall(text)) for term, p in AI_TERMS.items()},
        "snippets": _snippets(text),
    }
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def company_facts(cik: int) -> dict:
    try:
        return _cached_json(EDGAR_CACHE / f"facts_{cik}.json", 1,
                            lambda: _get(FACTS_URL.format(cik=cik)).json())
    except (EdgarError, requests.RequestException, ValueError):
        return {}


def _annual_values(facts: dict, concepts) -> tuple[dict, str | None]:
    """{fiscal_year_end_year: value} for the first concept that has full-year data."""
    for taxonomy, concept in concepts:
        units = facts.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {})
        if not units:
            continue
        unit = "USD" if "USD" in units else next(iter(units))
        by_year: dict[int, dict] = {}
        for entry in units[unit]:
            if entry.get("form") not in ANNUAL_FORMS or not entry.get("start"):
                continue
            start = dt.date.fromisoformat(entry["start"])
            end = dt.date.fromisoformat(entry["end"])
            if not 330 <= (end - start).days <= 400:
                continue
            year = end.year
            previous = by_year.get(year)
            if previous is None or entry.get("filed", "") > previous.get("filed", ""):
                by_year[year] = entry
        if by_year:
            return {year: float(e["val"]) for year, e in by_year.items()}, unit
    return {}, None


def financials(cik: int) -> tuple[dict, str | None]:
    """{year: {"rd": ..., "revenue": ..., "rd_pct_of_revenue": ...}} from XBRL company facts."""
    facts = company_facts(cik)
    rd, unit = _annual_values(facts, RD_CONCEPTS)
    revenue, rev_unit = _annual_values(facts, REVENUE_CONCEPTS)
    out = {}
    for year in sorted(set(rd) | set(revenue)):
        row = {"rd": rd.get(year), "revenue": revenue.get(year), "rd_pct_of_revenue": None}
        if row["rd"] is not None and row["revenue"]:
            row["rd_pct_of_revenue"] = round(row["rd"] / row["revenue"] * 100, 1)
        out[year] = row
    return out, unit or rev_unit


def company_ai_profile(ticker: str, years: int = 5) -> dict:
    """Everything the compare page needs for one company, filings oldest -> newest."""
    cik = cik_for(ticker)
    filings = annual_filings(cik, years)
    if not filings:
        raise EdgarError(f"No annual reports found on EDGAR for {ticker}.")
    with ThreadPoolExecutor(max_workers=3) as pool:
        analyzed = list(pool.map(analyze_filing, filings))
    analyzed.sort(key=lambda f: f["fiscal_year"])
    money, unit = financials(cik)
    for filing in analyzed:
        filing["financials"] = money.get(filing["fiscal_year"])
    return {
        "ticker": ticker,
        "name": COMPANY_NAMES.get(ticker, ticker),
        "industry": TICKER_INDUSTRY.get(ticker, ""),
        "cik": cik,
        "currency": unit,
        "filings": analyzed,
    }
