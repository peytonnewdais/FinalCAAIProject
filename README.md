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
| Accessibility | `/accessibility` | The accessibility statement: the two display modes, what has been done, and what is still imperfect |

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

### Deploy (Render)

The repo includes `render.yaml`, a [Render Blueprint](https://render.com/docs/blueprint-spec):

1. Push this repo to GitHub.
2. In the Render dashboard, **New +** → **Blueprint**, point it at the repo.
3. Render reads `render.yaml`, installs `requirements.txt`, and starts the app with
   `gunicorn app:server` - the same Dash `server` object `python app.py` runs locally, just
   served by gunicorn instead of Dash's dev server.
4. Set `ANTHROPIC_API_KEY` and `SEC_USER_AGENT` in the dashboard (left out of `render.yaml` on
   purpose so they're never committed).

Local development still uses `python app.py`; `gunicorn` is a Linux-only production server so it
runs on Render, not on a Windows dev machine.

### Tests

```bash
pytest
```

Covers the pure helper functions and data transforms - price/return math (`services/market_data.py`,
`services/forecast.py`), the SEC filing text-scoring regexes and XBRL year-picking logic
(`services/edgar.py`), and the display-formatting helpers (`services/ui.py`). It does not hit the
network: EDGAR- and price-dependent functions are exercised against small synthetic inputs via
`monkeypatch` rather than real API calls.

`tests/test_a11y.py` additionally re-derives every WCAG contrast ratio and colour-blindness
separation from the live palette values, so an inaccessible colour change fails the suite.

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

## Data dictionary

**Prices** (`services/market_data.load_prices()`, cached at `cache/prices_<date>.pkl`)

| Field | Type | Meaning |
|---|---|---|
| index (`Date`) | date | Trading day |
| one column per ticker | float | Adjusted daily close (splits/dividends applied), forward-filled |

**Industry index** (`services/market_data.industry_index()`, derived - not cached to disk)

| Field | Type | Meaning |
|---|---|---|
| index (`Date`) | date | Trading day, from `BASELINE_START` (Oct 1, 2022) onward |
| one column per industry | float | Equal-weight mean of that industry's 5 tickers, each rebased to 100 on `BASELINE_START` |
| `S&P 500 (SPY)` | float | SPY rebased to 100 the same way, for comparison |

**Price stats** (`services/market_data.price_stats(ticker, start)`, one ticker/period at a time)

| Field | Type | Meaning |
|---|---|---|
| `start_date`, `end_date` | ISO date string | First and last trading day in the window |
| `start_price`, `end_price` | float | Adjusted close on those days |
| `total_return_pct` | float | `end_price / start_price - 1`, as a percent |
| `cagr_pct` | float | Annualized total return |
| `ann_vol_pct` | float | Annualized standard deviation of daily log returns |
| `max_drawdown_pct` | float | Largest peak-to-trough decline in the window |

**Company AI profile** (`services/edgar.company_ai_profile(ticker)`, cached under `cache/edgar/`)

| Field | Type | Meaning |
|---|---|---|
| `ticker`, `name`, `industry`, `cik` | string / int | Identity fields |
| `currency` | string | Reporting currency for the financial figures (usually `USD`) |
| `filings` | list | One entry per annual report, oldest first (see below) |

Each entry in `filings`:

| Field | Type | Meaning |
|---|---|---|
| `form` | string | `10-K`, `20-F`, or `40-F` |
| `fiscal_year`, `filing_date`, `report_date` | int / ISO date | When the fiscal year ended and when it was filed |
| `url` | string | Link to the primary document on EDGAR |
| `word_count` | int | Words in the document after HTML is stripped |
| `ai_mentions` | int | Total AI-related term occurrences (see term list in "How the analysis works") |
| `mentions_per_10k_words` | float | `ai_mentions` normalized to a per-10,000-word rate |
| `term_counts` | dict | Occurrences broken down by individual term |
| `snippets` | list of strings | Up to 12 sentences that mention AI most densely |
| `financials` | dict or null | `{rd, revenue, rd_pct_of_revenue}` for that fiscal year from XBRL, when reported |

**Forecast stats** (`services/forecast.forecast_series()`, one industry/setting combination at a time)

| Field | Type | Meaning |
|---|---|---|
| `last_date`, `last_value` | ISO date / float | Where the projection starts |
| `lookback_start`, `observations` | ISO date / int | The return-estimation window actually used |
| `ann_drift_pct`, `ann_vol_pct` | float | Annualized drift and volatility fit to that window |
| `horizon_months` | int | How far forward the cone runs |
| `median_change_pct`, `p10_change_pct`, `p90_change_pct` | float | Projected change at the horizon, median and outer band |
| `prob_gain_pct` | float | Modeled probability the index is above today's level at the horizon |

## Design notes

- Light and dark themes are CSS variables on `<html data-theme>`; `assets/theme-init.js`
  stamps the saved (or OS-preferred) theme before Dash renders so there is no flash, and every
  Plotly figure re-paints from the same tokens when the toggle is pressed. Colorblind mode
  works the same way via `<html data-cvd>`.
- A colour always follows its industry, never its rank, so filtering never repaints the
  survivors.
- Every chart uses a single axis: series of different scale are indexed to a common base
  instead of sharing a dual axis.

## Accessibility

The app targets **WCAG 2.1 Level AA**, and the claim is enforced by tests rather than asserted
in a comment - `tests/test_a11y.py` recomputes every contrast ratio and colour-blindness
separation from the real palette values and fails if one drops below its threshold.

Two display modes sit in the header on every page and persist in `localStorage`:

- **Theme** - light or dark, defaulting to the operating system preference.
- **Colorblind** - swaps in a palette optimised for maximum separation under protanopia,
  deuteranopia and tritanopia, *and* gives every series its own dash pattern so hue stops
  mattering at all. That second half is the important one: eight categories cannot be told
  apart by colour alone under dichromacy - not even with the reference Okabe-Ito palette,
  which scores a worst-case CIEDE2000 gap of 1.1 under tritanopia.

Also: `<html lang>`, a skip link, visible focus rings, written text alternatives for every
Plotly figure, labelled control groups, live regions for errors and results, reduced-motion
support, Windows High Contrast support, and text that respects the browser's own font size.

Full detail, measurements, and known limitations: [`docs/ACCESSIBILITY.md`](docs/ACCESSIBILITY.md).

## Project structure

```
app.py                  Dash app shell: navbar, theme + colorblind stores, page container
pages/
  home.py               Landing page
  industries.py         Original rebased-index chart + scorecard
  compare.py            Two-company EDGAR comparison + Claude summary
  forecast.py           Industry forecast cones + Claude outlook
  accessibility.py      Accessibility statement
services/
  config.py             Industries, tickers, palette, events, .env settings
  market_data.py        yfinance download, daily cache, indices, return stats
  edgar.py              SEC EDGAR client: CIK lookup, filings, AI-term scoring, XBRL facts
  ai_summary.py         Claude API calls, prompts, on-disk response cache
  forecast.py           Lognormal drift/volatility cone
  a11y.py               Contrast + CVD maths, colorblind palette, dash/marker encodings
  theme.py              Theme tokens and Plotly figure styling
  ui.py                 Small layout helpers (tiles, tables, charts, notices)
assets/
  style.css             Light/dark tokens and component styling
  theme-init.js         Applies the saved display modes before first paint
tests/                  pytest coverage for pure helpers, data transforms, accessibility
docs/
  AI_USAGE.md           AI usage appendix
  ACCESSIBILITY.md      Accessibility audit, measurements, and known limitations
render.yaml             Render Blueprint (deploy config)
```

## Data sources

- Yahoo Finance (via the `yfinance` package) - adjusted closes
- SEC EDGAR - company tickers, submissions, annual report documents, XBRL company facts
- Anthropic Claude API - narrative summaries

This is a university project for educational purposes and is not investment advice.

## AI usage disclosure

AI assistance was used for: understanding the yfinance, SEC EDGAR, and Anthropic APIs;
building the Dash multi-page structure, callbacks, and theming; the forecast mathematics;
test coverage and the Render deploy config; and formatting and design of the site.

This project also uses AI as a **runtime feature**, not just a development aid: the Compare
and Forecast pages call the Claude API live to write the narrative summaries shown on those
pages (`services/ai_summary.py`), clearly labeled "Written by \<model\>" wherever they appear.

See [`docs/AI_USAGE.md`](docs/AI_USAGE.md) for the full appendix - tools used, what was asked
at a high level, and what the team verified or edited by hand. Individual `.py` files that AI
meaningfully touched carry a one-line `AI usage:` pointer back to that file.
