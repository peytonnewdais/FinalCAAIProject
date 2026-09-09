# AI usage appendix

This project uses AI in two different ways, and they should not be confused:

1. **Development tooling** - Claude Code (Anthropic's CLI coding agent) helped write and
   refactor this repository. That's the "did AI write your code" question.
2. **A runtime feature** - `services/ai_summary.py` calls the Claude API live, every time a
   user runs a comparison or asks for a forecast outlook, and its output is displayed in the
   app. That's a product decision, not a shortcut - it's disclosed to users directly in the UI
   ("Written by \<model\>") and in the README's "How the analysis works" section.

This appendix covers both. Every `.py` file that AI meaningfully touched also carries a short
`AI usage:` note pointing back here.

## 1. Development tooling

| Area | Tool | High-level ask (paraphrased) | What we verified / edited |
|---|---|---|---|
| Dash app shell (`app.py`), multi-page routing, light/dark theme store | Claude Code | "Set up a Dash `use_pages` app with a nav bar and a theme toggle stored in `dcc.Store`, no flash of the wrong theme on load." | Clicked the toggle in both light and dark, confirmed `assets/theme-init.js` runs before first paint, checked the CSS variables in devtools. |
| SEC EDGAR client (`services/edgar.py`) | Claude Code | "Write a client that finds a company's CIK, pulls its last 5 annual reports, downloads the primary document, and counts AI-related terms, respecting SEC's rate limit and User-Agent rules." | Opened several of the returned `url` values in a browser to confirm they resolve to the real filing; hand-checked the AI-term regex against filings that mention "AI" as a false positive risk (e.g. "maintain", "certain") - see `tests/test_edgar.py`; confirmed the 403-without-a-User-Agent behavior against the live API. |
| Forecast math (`services/forecast.py`) | Claude Code | "Given daily log returns, fit a drift and volatility and produce a closed-form lognormal quantile cone (p10-p90) for N months out." | Cross-checked the formulas (`mean = mu*t`, `variance = sigma^2*t`) against the standard geometric Brownian motion derivation by hand; added `tests/test_forecast.py` to assert the quantiles stay ordered and that the "no trend" mode truly zeroes the drift. |
| Categorical color palette (`services/config.py`, `services/theme.py`) | Claude Code | "Pick 8 colors that stay distinguishable for the common forms of color-vision deficiency and meet contrast on both a light and a dark chart surface." | Ran the palette through a CVD simulator and a contrast checker before accepting it; confirmed in the app that a color always follows its industry (not its rank), so filtering never repaints the survivors. |
| Once-a-day price cache and its cross-midnight bug (`services/market_data.py`) | Claude Code | Diagnosed why a long-running server kept showing a stale "prices as of" date after midnight even though the on-disk cache had rotated - traced it to a parameterless `@lru_cache` never re-checking the date. | Reproduced the bug against the real cache file, then re-ran `load_prices()` in a fresh process to confirm the fix (cache keyed to today's file path) actually re-fetches after rollover, before trusting the diagnosis. |
| Tests (`tests/`), Render deploy config (`render.yaml`), this appendix | Claude Code | "Add pytest coverage for the pure helper functions and data transforms, and a Render blueprint for deployment." | Ran `pytest` locally (22 tests, all passing) rather than trusting generated code unread; the deploy config's `startCommand` was checked against Render's documented gunicorn pattern before being committed. |
| Accessibility audit and colourblind mode (`services/a11y.py`, `pages/accessibility.py`, CSS) | Claude Code | "Make the site accessible and compliant, and add a colourblind mode." | This one was measured, not accepted: the contrast and CVD maths were implemented from the published WCAG / CIEDE2000 / Viénot formulae and then used to *audit* the existing palette, which turned out to fail in ways the old code comment denied (three light-mode chart colours below 3:1, muted text at 3.41:1). The candidate colourblind palettes were scored against the Okabe-Ito reference before being accepted, and a first attempt at a stricter 4:1 contrast floor was **rejected** because measurement showed it cost more discriminability than it gained. Final contrast figures were re-read off the live DOM in Chrome, and keyboard focus, the skip link and both toggles were exercised in the browser. |

**What we did not do:** accept AI output for anything touching money-shaped numbers (returns,
drawdowns, R&D percentages) without re-deriving the formula by hand at least once, or accept a
filing URL / AI-mention count without spot-checking it against the actual SEC document.

## 2. Runtime feature: Claude-written summaries

`services/ai_summary.py` sends Claude a **fixed, structured payload** - filing AI-mention
counts, R&D-to-revenue ratios, filing excerpts, and price statistics computed entirely in
Python - never raw model speculation standing in for data. The system prompt (visible in that
file) requires every claim to be grounded in the supplied numbers, to distinguish talking about
AI from deploying it, and to flag when a price move likely has a non-AI explanation. Responses
are cached on disk by prompt hash so the same inputs never re-bill.

This is the one place in the app where a user sees freshly generated AI text, and it is labeled
as such in the UI ("Written by \<model\>") every time it appears - never presented as if a human
analyst wrote it.

## Model and tool versions

- Development tooling: Claude Code, Claude Sonnet 5 (`claude-sonnet-5`).
- Runtime feature: Anthropic Python SDK (`anthropic` package), model configurable via
  `CLAUDE_MODEL` in `.env` (defaults to `claude-opus-5`).
