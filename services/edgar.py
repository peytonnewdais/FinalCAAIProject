"""Reads annual reports from SEC EDGAR and counts how much they talk about AI.

Steps: ticker -> CIK number -> list of 10-K / 20-F filings -> download the HTML
-> strip the tags -> count AI words. Everything downloaded is saved in
cache/edgar so a company is only fetched once.


We used AI to understand and use the edgar endpoitns. 
"""
import json
import re
import time
import warnings

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .config import CACHE_DIR, COMPANY_NAMES, SEC_USER_AGENT, TICKER_INDUSTRY

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

EDGAR_CACHE = CACHE_DIR / "edgar"
EDGAR_CACHE.mkdir(exist_ok=True)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"

HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
ANNUAL_FORMS = ["10-K", "20-F", "40-F"]

# One pattern per AI term, used for the breakdown by term. "AI" is case
# sensitive so ordinary words containing "ai" are not counted.
AI_TERMS = {
    "artificial intelligence": re.compile(r"\bartificial[\s-]intelligence\b", re.I),
    "AI": re.compile(r"\bAI\b"),
    "machine learning": re.compile(r"\bmachine[\s-]learning\b", re.I),
    "generative AI": re.compile(r"\bgenerative\s+AI\b|\bgen\s?AI\b", re.I),
    "large language model": re.compile(r"\blarge[\s-]language[\s-]models?\b|\bLLMs?\b"),
    "deep learning": re.compile(r"\bdeep[\s-]learning\b", re.I),
    "neural network": re.compile(r"\bneural[\s-]networks?\b", re.I),
}

# One combined pattern for the total, so overlapping terms are not double counted.
AI_ANY = re.compile(
    r"(?i:\bartificial[\s-]intelligence\b|\bmachine[\s-]learning\b|\bgenerative\s+AI\b"
    r"|\bgen\s?AI\b|\blarge[\s-]language[\s-]models?\b|\bdeep[\s-]learning\b"
    r"|\bneural[\s-]networks?\b)|\bLLMs?\b|\bAI\b"
)
SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")

class EdgarError(Exception):
    """Something went wrong talking to EDGAR."""


def get(url):
    """Download a URL from EDGAR, waiting and retrying if we are asked to slow down."""
    for attempt in range(4):
        time.sleep(0.15)                       # stay under SEC's 10 requests/second limit
        response = requests.get(url, headers=HEADERS, timeout=120)
        if response.status_code == 200:
            return response
        if response.status_code in (403, 429, 503):
            time.sleep(2 * (attempt + 1))      # busy: wait longer each try
            continue
        raise EdgarError(f"EDGAR returned status {response.status_code} for {url}")
    raise EdgarError(f"EDGAR kept refusing the request: {url}")


def cached_json(filename, max_age_days, download):
    """Return a saved JSON file, or download it again if it is missing or old."""
    path = EDGAR_CACHE / filename
    if path.exists():
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days <= max_age_days:
            return json.loads(path.read_text(encoding="utf-8"))

    data = download()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def cik_for(ticker):
    """Look up a company's CIK number, which is how EDGAR identifies companies."""
    data = cached_json("company_tickers.json", 7, lambda: get(TICKERS_URL).json())
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"])
    raise EdgarError(f"{ticker} is not in SEC's ticker list.")


def annual_filings(cik, count=5):
    """The most recent annual reports, one per fiscal year, newest first."""
    submissions = cached_json(f"submissions_{cik}.json", 1,
                              lambda: get(SUBMISSIONS_URL.format(cik=cik)).json())

    # EDGAR splits older filings into extra files, so collect those blocks too.
    blocks = [submissions["filings"]["recent"]]
    for extra in submissions["filings"].get("files", []):
        name = extra["name"]
        blocks.append(cached_json(name, 30,
                                  lambda n=name: get(f"https://data.sec.gov/submissions/{n}").json()))

    filings, seen_years = [], []
    for block in blocks:
        for i, form in enumerate(block["form"]):
            if form not in ANNUAL_FORMS:
                continue

            report_date = block["reportDate"][i] or block["filingDate"][i]
            year = int(report_date[:4])
            if year in seen_years:              # one report per fiscal year is enough
                continue
            seen_years.append(year)

            accession = block["accessionNumber"][i]
            filings.append({
                "form": form,
                "fiscal_year": year,
                "filing_date": block["filingDate"][i],
                "accession": accession,
                "url": ARCHIVE_URL.format(cik=cik, accession=accession.replace("-", ""),
                                          doc=block["primaryDocument"][i]),
            })
            if len(filings) >= count:
                return filings
    return filings


def html_to_text(content):
    """Turn the filing's HTML into plain text, one long string."""
    try:
        html = content.decode("utf-8")
    except UnicodeDecodeError:
        html = content.decode("cp1252", errors="replace")   # some older filings

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "ix:header"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


def ai_snippets(text, limit=12):
    """Sentences that mention AI, the densest ones first. Claude reads these."""
    found, seen_starts = [], []
    for sentence in SENTENCES.split(text):
        sentence = sentence.strip()
        if not 60 <= len(sentence) <= 420:      # skip fragments and giant blocks
            continue

        hits = len(AI_ANY.findall(sentence))
        start = sentence[:80].lower()
        if hits == 0 or start in seen_starts:   # skip repeated boilerplate
            continue

        seen_starts.append(start)
        found.append((hits, -len(sentence), sentence))

    found.sort(reverse=True)
    return [sentence for _, _, sentence in found[:limit]]


def analyze_filing(filing):
    """Download one annual report and count its AI words. Saved by accession number."""
    path = EDGAR_CACHE / f"filing_{filing['accession']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    text = html_to_text(get(filing["url"]).content)
    words = max(len(text.split()), 1)
    mentions = len(AI_ANY.findall(text))

    result = dict(filing)
    result.update({
        "word_count": words,
        "ai_mentions": mentions,
        # Longer reports naturally contain more of everything, so divide by length.
        "mentions_per_10k_words": round(mentions / words * 10000, 2),
        "term_counts": {term: len(pattern.findall(text)) for term, pattern in AI_TERMS.items()},
        "snippets": ai_snippets(text),
    })

    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def company_ai_profile(ticker, years=5):
    """Everything the compare page needs about one company, oldest year first."""
    cik = cik_for(ticker)
    filings = annual_filings(cik, years)
    if not filings:
        raise EdgarError(f"No annual reports found on EDGAR for {ticker}.")

    analyzed = [analyze_filing(f) for f in filings]
    analyzed.sort(key=lambda f: f["fiscal_year"])

    return {
        "ticker": ticker,
        "name": COMPANY_NAMES.get(ticker, ticker),
        "industry": TICKER_INDUSTRY.get(ticker, ""),
        "cik": cik,
        "filings": analyzed,
    }
