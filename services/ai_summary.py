"""Claude-generated narratives: the two-company comparison and the industry outlook.

Calls go through the official Anthropic SDK. Responses are cached on disk keyed by
the exact prompt, so re-rendering a page (or toggling the theme) never re-bills.

This module is the app's one runtime (user-facing) use of AI, distinct from AI used as a
development tool elsewhere in this repo. AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import hashlib
import json
import os

from .config import CACHE_DIR, CLAUDE_EFFORT, CLAUDE_MODEL

SUMMARY_CACHE = CACHE_DIR / "summaries"
SUMMARY_CACHE.mkdir(exist_ok=True)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class SummaryUnavailable(Exception):
    """A user-facing reason why no Claude summary could be produced."""


COMPARE_SYSTEM = """You are an equity research analyst writing for a university data-visualization \
dashboard called "AI Boom Scorecard". You receive structured data about two public companies: how \
often each company's annual SEC report (10-K or 20-F) discusses artificial intelligence across \
several fiscal years, R&D spending where reported, excerpts from those filings, and how each stock \
performed against the S&P 500 over a chosen period.

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
2022) plus the S&P 500. The model takes daily log returns over a lookback window, estimates a drift \
and a volatility, and projects a lognormal cone forward. You also receive each industry's total \
return since ChatGPT launched.

Write an outlook in Markdown with exactly these section headings, in this order:
## Big picture
## Industry by industry
## How much to trust this

Rules:
- In "Industry by industry" use one bullet per industry, in the order given, each citing the \
median projected change and the 10th-90th percentile range from the data.
- Explain in plain language what drives the numbers: the drift assumption and the volatility.
- Name where the extrapolation is most likely to break (for example a trend that already \
reversed, or a range so wide the median is not informative).
- This is educational analysis, not investment advice. Keep the response under 500 words. \
No preamble before the first heading."""


def _cache_path(tag: str, system: str, user: str) -> "os.PathLike[str]":
    key = hashlib.sha256(json.dumps([CLAUDE_MODEL, CLAUDE_EFFORT, system, user]).encode()).hexdigest()
    return SUMMARY_CACHE / f"{tag}_{key[:20]}.json"


def _extract_text(message) -> str:
    return "".join(block.text for block in message.content if block.type == "text").strip()


def _stream(messages_api, request: dict, **extra):
    with messages_api.stream(**request, **extra) as stream:
        return stream.get_final_message()


def _run(client, request: dict):
    """Stream the response, adapting the request to what the chosen model accepts.

    Server-side refusal fallbacks and the ``effort`` parameter only exist on some
    models (Haiku 4.5, for example, rejects effort). When the API turns one of them
    down, retry without it instead of failing the page.
    """
    import anthropic

    request = dict(request)
    use_fallbacks = True
    for _ in range(4):
        try:
            if use_fallbacks:
                return _stream(client.beta.messages, request,
                               betas=[FALLBACK_BETA], fallbacks="default")
            return _stream(client.messages, request)
        except anthropic.BadRequestError as exc:
            text = str(exc).lower()
            if "effort" in text and "output_config" in request:
                request.pop("output_config")
            elif use_fallbacks and ("fallback" in text or "beta" in text):
                use_fallbacks = False
            else:
                raise
    raise SummaryUnavailable("Claude rejected the request even without optional parameters.")


def generate(tag: str, system: str, user: str, max_tokens: int = 6000) -> dict:
    """Return {"text", "model", "cached"} or raise SummaryUnavailable with a friendly reason."""
    path = _cache_path(tag, system, user)
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        cached["cached"] = True
        return cached

    try:
        import anthropic
    except ImportError as exc:
        raise SummaryUnavailable("The anthropic package is not installed. Run: pip install anthropic") from exc

    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
        raise SummaryUnavailable(
            "No Claude credentials found. Copy .env.example to .env and set ANTHROPIC_API_KEY, "
            "then restart the app."
        )

    request = dict(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": CLAUDE_EFFORT},
    )
    try:
        client = anthropic.Anthropic()
        message = _run(client, request)
    except anthropic.AuthenticationError as exc:
        raise SummaryUnavailable("Claude rejected the API key. Check ANTHROPIC_API_KEY in .env.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise SummaryUnavailable("This API key is not allowed to use the configured model.") from exc
    except anthropic.NotFoundError as exc:
        raise SummaryUnavailable(f"Model '{CLAUDE_MODEL}' was not found. Check CLAUDE_MODEL in .env.") from exc
    except anthropic.RateLimitError as exc:
        raise SummaryUnavailable("Claude is rate-limited right now. Try again in a minute.") from exc
    except anthropic.APIStatusError as exc:
        raise SummaryUnavailable(f"Claude API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise SummaryUnavailable("Could not reach the Claude API. Check your connection.") from exc

    if message.stop_reason == "refusal":
        raise SummaryUnavailable("Claude declined to write this summary.")

    text = _extract_text(message)
    if not text:
        raise SummaryUnavailable("Claude returned an empty response.")

    result = {
        "text": text,
        "model": message.model,
        "cached": False,
        "usage": {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        },
    }
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


# --------------------------------------------------------------------------- prompts

def _filing_rows(profile: dict) -> list[dict]:
    rows = []
    for f in profile["filings"]:
        money = f.get("financials") or {}
        rows.append({
            "fiscal_year": f["fiscal_year"],
            "form": f["form"],
            "filed": f["filing_date"],
            "word_count": f["word_count"],
            "ai_mentions": f["ai_mentions"],
            "mentions_per_10k_words": f["mentions_per_10k_words"],
            "term_counts": f["term_counts"],
            "rd_expense": money.get("rd"),
            "revenue": money.get("revenue"),
            "rd_pct_of_revenue": money.get("rd_pct_of_revenue"),
        })
    return rows


def _excerpts(profile: dict, per_filing: int = 8) -> str:
    lines = [f"### {profile['name']} ({profile['ticker']}) filing excerpts"]
    for f in profile["filings"]:
        snippets = f.get("snippets", [])[:per_filing]
        if not snippets:
            continue
        lines.append(f"FY{f['fiscal_year']} {f['form']} (filed {f['filing_date']}):")
        lines.extend(f"- {s}" for s in snippets)
    return "\n".join(lines)


def compare_companies(profile_a: dict, profile_b: dict, stats_a: dict, stats_b: dict,
                      benchmark: dict, period_label: str) -> dict:
    system = COMPARE_SYSTEM.format(a_name=profile_a["name"], a_ticker=profile_a["ticker"],
                                   b_name=profile_b["name"], b_ticker=profile_b["ticker"])
    payload = {
        "period": {"label": period_label, "start": benchmark.get("start_date"),
                   "end": benchmark.get("end_date")},
        "benchmark": {"ticker": "SPY", **benchmark},
        "companies": [
            {"ticker": p["ticker"], "name": p["name"], "industry": p["industry"],
             "financial_currency": p.get("currency"), "stock": s, "annual_filings": _filing_rows(p)}
            for p, s in ((profile_a, stats_a), (profile_b, stats_b))
        ],
        "notes": [
            "ai_mentions counts every occurrence of: artificial intelligence, AI, machine learning, "
            "generative AI, large language model / LLM, deep learning, neural network.",
            "mentions_per_10k_words normalises for filing length.",
            "Stock figures are total returns on adjusted closes over the period.",
        ],
    }
    user = (
        "DATA (JSON):\n" + json.dumps(payload, indent=1, default=str) + "\n\n"
        + _excerpts(profile_a) + "\n\n" + _excerpts(profile_b)
    )
    return generate("compare", system, user)


def industry_outlook(rows: list[dict], settings: dict) -> dict:
    payload = {"model_settings": settings, "industries": rows}
    user = "FORECAST OUTPUT (JSON):\n" + json.dumps(payload, indent=1, default=str)
    return generate("forecast", FORECAST_SYSTEM, user)
