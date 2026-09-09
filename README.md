# AI Boom Scorecard

**Team 8 - Peyton, Asad, Maya**

> Over the past five years, which companies adapted around AI most successfully, and has the
> stock market rewarded that adoption?

A multi-page Dash app that grows the original single-chart project into a small research
dashboard. This app is for investor or analyst trying to tell whether a a company's AI messaging is backed by financial reality.
It tracks 40 large companies across eight industries from just before ChatGPT's
launch (Nov 30, 2022), reads what each company tells the SEC about artificial intelligence,
asks Claude to weigh that against share prices, and projects where each industry index could
go next. Light and dark mode are built in.

## Pages

| Page | URL | What it shows |
|---|---|---|
| Home | `/` | The question, headline numbers (biggest winner and loser, S&P 500), and links to each page |
| Industries | `/industries` | The original chart: eight equal-weight industry indices rebased to 100 versus the S&P 500, with a year-range slider and event markers, plus the total-return scorecard |
| Compare stocks | `/compare` | Pick any two companies. Their last five annual reports (10-K / 20-F) are pulled from SEC EDGAR and scanned for AI language, R&D spend comes from XBRL company facts, and both are set against total return. Claude writes the comparison |
| Forecast | `/forecast` | A drift-and-volatility (lognormal cone) forecast for every industry index with adjustable horizon, lookback, and drift assumption. Claude can write an outlook on demand |

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # then edit .env
python app.py
```

Open http://127.0.0.1:8050/.

### Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | For Claude summaries | Without it the app still runs; the summary panels show a notice instead |
| `SEC_USER_AGENT` | Recommended | SEC EDGAR requires a descriptive User-Agent with a contact email and returns 403 without one. A placeholder is used if unset; put your own name and email here |
| `CLAUDE_MODEL` | No | Defaults to `claude-opus-5`; `claude-sonnet-5` and `claude-haiku-4-5` are cheaper |
| `SUMMARY_EFFORT` | No | `low`, `medium` (default), `high`, `xhigh`, or `max`. Dropped automatically on models that reject it, such as Haiku 4.5 |

The first start downloads about six years of daily prices for 41 tickers (a few seconds).
The first comparison of a company downloads its filings from EDGAR (10-20 seconds per
company). Everything is cached under `cache/`, which is git-ignored; delete it to refresh.

## How the analysis works

**Prices.** Adjusted daily closes from Yahoo Finance via `yfinance`, cached once per day.
Each industry index is the equal-weight mean of its five tickers, each rebased to 100 on
October 3, 2022, one month before ChatGPT launched, so every line shares a pre-boom baseline.

**AI adoption signal.** For each company the app finds the last five annual reports on EDGAR
(`10-K`, or `20-F` for foreign filers such as TSMC and Infosys), converts the primary document
to text, and counts every occurrence of: *artificial intelligence, AI, machine learning,
generative AI, large language model / LLM, deep learning, neural network*. Counts are
normalised to mentions per 10,000 words so document length does not matter. The sentences
that discuss AI most densely are kept as excerpts. R&D expense and revenue come from the XBRL
company-facts API, giving R&D as a share of revenue where a company reports it.

**Claude summaries.** The counts, excerpts, financials, and price statistics are sent to Claude
through the official Anthropic SDK with a system prompt that requires every claim to be
grounded in the supplied numbers, to distinguish talking about AI from deploying it, and to
flag when a stock move has a non-AI explanation. Responses are cached by prompt hash, so
re-rendering a page never re-bills.

**Forecast.** Daily log returns over the chosen lookback give a drift (mean) and a volatility
(standard deviation). Future log-price is modelled as normal with mean `drift x days` and
variance `volatility^2 x days`, which yields closed-form 10th/25th/50th/75th/90th percentile
paths. Because the drift is the fragile input, three assumptions are offered: the full
historical trend, half of it (shrunk toward zero), and no trend at all.

## Design notes

- Light and dark themes are CSS variables on `<html data-theme>`; `assets/theme-init.js`
  stamps the saved (or OS-preferred) theme before Dash renders so there is no flash, and every
  Plotly figure re-paints from the same tokens when the toggle is pressed.
- The eight industry colors are a fixed, validated categorical palette (checked for
  colour-vision-deficiency separation and contrast on both surfaces). A colour always follows
  its industry, never its rank, so filtering never repaints the survivors.
- Every chart uses a single axis: series of different scale are indexed to a common base
  instead of sharing a dual axis.

## Project structure

```
app.py                  Dash app shell: navbar, theme store and toggle, page container
pages/
  home.py               Landing page
  industries.py         Original rebased-index chart + scorecard
  compare.py            Two-company EDGAR comparison + Claude summary
  forecast.py           Industry forecast cones + Claude outlook
services/
  config.py             Industries, tickers, palette, events, .env settings
  market_data.py        yfinance download, daily cache, indices, return stats
  edgar.py              SEC EDGAR client: CIK lookup, filings, AI-term scoring, XBRL facts
  ai_summary.py         Claude API calls, prompts, on-disk response cache
  forecast.py           Lognormal drift/volatility cone
  theme.py              Theme tokens and Plotly figure styling
  ui.py                 Small layout helpers (tiles, tables, notices)
assets/
  style.css             Light/dark tokens and component styling
  theme-init.js         Applies the saved theme before first paint
```

## Data sources

- Yahoo Finance (via the `yfinance` package) - adjusted closes
- SEC EDGAR - company tickers, submissions, annual report documents, XBRL company facts
- Anthropic Claude API - narrative summaries

This is a university project for educational purposes and is not investment advice.

## AI usage disclosure

AI assistance was used for: understanding the yfinance, SEC EDGAR, and Anthropic APIs;
building the Dash multi-page structure, callbacks, and theming; the forecast mathematics;
and formatting and design of the site.
