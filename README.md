# AI Boom Scorecard
[Live On Render](https://aiboomscorecard.onrender.com/)
**Team 8 - Peyton, Asad, Maya**

> Over the past five years, which companies adapted around AI most successfully, and has the
> stock market rewarded that adoption?

A multi-page Dash dashboard. It tracks 40 large companies across eight industries from just
before ChatGPT's launch (Nov 30, 2022), reads what each company tells the SEC about artificial
intelligence, asks Claude to weigh that against the share price, and projects where each
industry index could go next.

## Pages

| Page | URL | What it shows |
|---|---|---|
| Home | `/` | The question, the headline numbers, and links to the other pages |
| Industries | `/industries` | Eight equal-weight industry indices rebased to 100 versus the S&P 500, with a year slider and event markers, plus the total-return bar chart |
| Compare Stocks | `/compare` | Pick two companies. Their last five annual reports (10-K / 20-F) come from SEC EDGAR and are scanned for AI language, and Claude writes the comparison |
| Forecast | `/forecast` | A trend-and-volatility cone for every industry index, with an adjustable horizon, lookback and trend assumption. Claude can write an outlook |

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # then put your Claude API key in .env
python app.py
```

Then open http://127.0.0.1:8050/.

Without an API key everything still works except the two Claude write-ups, which show a
message instead. Summaries that have already been generated are read from `cache/summaries`.

## Files

```
app.py                  the Dash app, the nav bar and the footer
pages/
  home.py               the question and headline numbers
  industries.py         industry index chart + scorecard bar chart
  compare.py            two-company comparison, EDGAR filings, Claude summary
  forecast.py           forecast cones, forecast table, Claude outlook
services/
  config.py             industries, tickers, colors, dates, settings
  market_data.py        yfinance prices, industry indices, return statistics
  edgar.py              SEC EDGAR filings and the AI word counting
  forecast.py           the drift and volatility forecast math
  ai_summary.py         the two Claude prompts, with answers cached on disk
assets/styles.css       the stylesheet
cache/                  downloaded prices, filings and Claude answers
```

## Where the data comes from

- **Prices**: Yahoo Finance through `yfinance`, adjusted daily closes, cached once a day.
- **Filings**: SEC EDGAR. Requests carry the User-Agent the SEC asks for (set `SEC_USER_AGENT`
  in `.env` with your own email) and are spaced out to stay under their rate limit.
- **AI mentions**: every occurrence of artificial intelligence, AI, machine learning,
  generative AI, large language model / LLM, deep learning and neural network, divided by the
  filing's word count and scaled to a rate per 10,000 words.
- **Claude**: `claude-haiku-4-5` through the `anthropic` package, writing the comparison on the
  compare page and the outlook on the forecast page.

Educational project, not investment advice. Many parts of this project and this README were AI generated
