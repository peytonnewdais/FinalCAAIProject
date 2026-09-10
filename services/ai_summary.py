"""Asks Claude to write the two narratives in the app: the stock comparison and
the industry outlook.

Answers are saved in cache/summaries and keyed by the prompt, so asking the same
question twice never costs a second API call.
"""
import hashlib
import json
import os

from .config import CACHE_DIR, CLAUDE_EFFORT, CLAUDE_MODEL

SUMMARY_CACHE = CACHE_DIR / "summaries"
SUMMARY_CACHE.mkdir(exist_ok=True)


class SummaryUnavailable(Exception):
    """No summary could be written. The message is shown to the user."""


COMPARE_SYSTEM = """You are an equity research analyst writing for a university data-visualization \
dashboard called "AI Boom Scorecard". You receive structured data about two public companies: how \
often each company's annual SEC report (10-K or 20-F) discusses artificial intelligence across \
several fiscal years, excerpts from those filings, and how each stock performed against the \
S&P 500 over a chosen period.

Write a comparison in Markdown using exactly these section headings, in this order:
## Verdict
## {a_name} ({a_ticker})
## {b_name} ({b_ticker})
## Did the market reward AI adoption?
## Caveats

Rules:
- Ground every claim in the numbers and excerpts provided and cite figures inline \
(for example "AI mentions rose from 1.2 to 9.8 per 10k words").
- Distinguish talking about AI from evidence of deploying it (products, capital spending, revenue).
- Say plainly when a stock's move is better explained by something other than AI.
- Mentions of AI in a filing can also be risk-factor boilerplate; treat that as weak evidence.
- This is educational analysis, not investment advice. Keep the whole response under 450 words. \
No preamble before the first heading."""

FORECAST_SYSTEM = """You are a markets analyst writing for a university data-visualization dashboard \
called "AI Boom Scorecard". You receive the output of a simple statistical forecast for eight \
industry indices (each an equal-weight basket of five large companies, indexed to 100 in October \
2022) plus the S&P 500. The model takes daily log returns over a lookback window, estimates a \
drift and a volatility, and projects a lognormal cone forward. The drift is always damped to \
half of its historical value - a fixed choice, not something the viewer selects - since a trend \
estimated from a few years of daily returns is too weak a signal to extrapolate at full strength. \
You also receive each industry's total return since ChatGPT launched.

Write an outlook in Markdown with exactly these section headings, in this order:
## Big picture
## Industry by industry
## How much to trust this

Rules:
- In "Industry by industry" use one bullet per industry, in the order given, each citing the \
median projected change and the 10th-90th percentile range from the data.
- Explain in plain language what drives the numbers: the damped drift and the volatility.
- Name where the projection is most likely to mislead (for example a trend that has already \
reversed since the lookback window, or a range so wide the median is not informative).
- This is educational analysis, not investment advice. Keep the response under 500 words. \
No preamble before the first heading."""


def ask_claude(tag, system, user, max_tokens=6000):
    """Send one request to Claude. Returns {"text", "model", "cached"}."""
    # The file name is a hash of the prompt, so a changed prompt gets a new answer.
    key = hashlib.sha256(
        json.dumps([CLAUDE_MODEL, CLAUDE_EFFORT, system, user]).encode()).hexdigest()
    path = SUMMARY_CACHE / f"{tag}_{key[:20]}.json"

    if path.exists():
        answer = json.loads(path.read_text(encoding="utf-8"))
        answer["cached"] = True
        return answer

    try:
        import anthropic
    except ImportError:
        raise SummaryUnavailable("The anthropic package is not installed. "
                                 "Run: pip install anthropic")

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SummaryUnavailable("No Claude API key found. Copy .env.example to .env, "
                                 "set ANTHROPIC_API_KEY, then restart the app.")

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        raise SummaryUnavailable("Claude rejected the API key. Check ANTHROPIC_API_KEY in .env.")
    except anthropic.RateLimitError:
        raise SummaryUnavailable("Claude is rate-limited right now. Try again in a minute.")
    except anthropic.APIError as error:
        raise SummaryUnavailable(f"Claude API error: {error}")

    text = "".join(block.text for block in message.content if block.type == "text").strip()
    if not text:
        raise SummaryUnavailable("Claude returned an empty response.")

    answer = {"text": text, "model": message.model, "cached": False}
    path.write_text(json.dumps(answer), encoding="utf-8")
    return answer


def filing_rows(profile):
    """The filing numbers for one company, trimmed down to what Claude needs."""
    rows = []
    for f in profile["filings"]:
        rows.append({
            "fiscal_year": f["fiscal_year"],
            "form": f["form"],
            "filed": f["filing_date"],
            "word_count": f["word_count"],
            "ai_mentions": f["ai_mentions"],
            "mentions_per_10k_words": f["mentions_per_10k_words"],
            "term_counts": f["term_counts"],
        })
    return rows


def excerpts(profile, per_filing=8):
    """The AI sentences from each filing, as text for the prompt."""
    lines = [f"### {profile['name']} ({profile['ticker']}) filing excerpts"]
    for f in profile["filings"]:
        snippets = f.get("snippets", [])[:per_filing]
        if snippets:
            lines.append(f"FY{f['fiscal_year']} {f['form']} (filed {f['filing_date']}):")
            lines += [f"- {s}" for s in snippets]
    return "\n".join(lines)


def compare_companies(profile_a, profile_b, stats_a, stats_b, benchmark, period_label):
    """Ask Claude to compare two companies' AI language against their share price."""
    system = COMPARE_SYSTEM.format(a_name=profile_a["name"], a_ticker=profile_a["ticker"],
                                   b_name=profile_b["name"], b_ticker=profile_b["ticker"])
    data = {
        "period": {"label": period_label, "start": benchmark.get("start_date"),
                   "end": benchmark.get("end_date")},
        "benchmark": {"ticker": "SPY", **benchmark},
        "companies": [
            {"ticker": p["ticker"], "name": p["name"], "industry": p["industry"],
             "stock": s, "annual_filings": filing_rows(p)}
            for p, s in [(profile_a, stats_a), (profile_b, stats_b)]
        ],
        # Explaining the columns keeps Claude from guessing what they mean.
        "notes": [
            "ai_mentions counts every occurrence of: artificial intelligence, AI, machine learning, "
            "generative AI, large language model / LLM, deep learning, neural network.",
            "mentions_per_10k_words normalises for filing length.",
            "Stock figures are total returns on adjusted closes over the period.",
        ],
    }
    user = ("DATA (JSON):\n" + json.dumps(data, indent=1, default=str) + "\n\n"
            + excerpts(profile_a) + "\n\n" + excerpts(profile_b))
    return ask_claude("compare", system, user)


def industry_outlook(rows, settings):
    """Ask Claude to explain the forecast numbers for all the industries."""
    user = "FORECAST OUTPUT (JSON):\n" + json.dumps(
        {"model_settings": settings, "industries": rows}, indent=1, default=str)
    return ask_claude("forecast", FORECAST_SYSTEM, user)
