"""Home page: the question we asked, the headline numbers, and links to the other pages."""
import dash
from dash import dcc, html

from services import config
from services.market_data import last_updated, scorecard

dash.register_page(__name__, path="/", name="Home")

# The three pages the home page links to.
CARDS = [
    ("/industries", "Industries",
     "Eight industry baskets rebased to 100 and compared against the S&P 500, with the "
     "key AI moments marked on the chart."),
    ("/compare", "Compare Stocks",
     "Pick any two companies. We read their last five annual reports from SEC EDGAR, count "
     "how much they talk about AI, and ask Claude to weigh that against the share price."),
    ("/forecast", "Forecast",
     "A drift-and-volatility cone for every industry index, plus a Claude outlook on what "
     "the numbers do and do not say."),
]


def tile(label, value, sub, color=""):
    """One small box showing a single number."""
    return html.Div(className="tile", children=[
        html.Div(label, className="label"),
        html.Div(value, className=f"value {color}"),
        html.Div(sub, className="sub"),
    ])


def layout():
    scores = scorecard()
    industries = scores.drop(config.BENCHMARK)      # the S&P 500 is not an industry
    best = industries.idxmax()
    worst = industries.idxmin()
    benchmark = scores[config.BENCHMARK]

    return html.Div([
        html.H1("Did the AI boom reward the companies that embraced it?"),
        html.P("ChatGPT launched on November 30, 2022. Since then, forty large companies "
               "across eight industries have taken very different paths. This dashboard "
               "compares their stock performance, reads what they tell the SEC about "
               "artificial intelligence, and projects where each industry could go next."),

        html.Div(className="tiles", children=[
            tile("Biggest winner since the boom", f"{industries[best]:+,.0f}%", best, "up"),
            tile("Biggest loser since the boom", f"{industries[worst]:+,.0f}%", worst, "down"),
            tile("S&P 500 over the same stretch", f"{benchmark:+,.0f}%", "SPY",
                 "up" if benchmark > 0 else "down"),
            tile("Companies tracked", str(len(config.COMPANY_TICKERS)),
                 f"{len(config.INDUSTRIES)} industries, 5 each"),
            tile("Prices as of", last_updated(), "Yahoo Finance"),
        ]),

        html.H2("Where to go next"),
        html.Div([
            dcc.Link(className="link-card", href=path, children=[
                html.H3(title),
                html.P(text, className="muted"),
            ])
            for path, title, text in CARDS
        ]),

        html.Div(className="card", children=[
            html.H3("The story"),
            html.P("We took the five largest companies in each of eight industries the AI boom "
                   "touched, from chip makers to the outsourcing and content businesses that AI "
                   "threatens. Each industry becomes an equal-weight index starting at 100 in "
                   "October 2022, one month before ChatGPT, so every line shares the same "
                   "starting point."),
            html.P("This was not a rising tide that lifted every industry equally. Semiconductors "
                   "climbed to many times their starting value while IT services and content "
                   "businesses lost most of theirs."),
        ]),

        html.Div(className="card", children=[
            html.H3("How the analysis works"),
            html.Ol([
                html.Li("Daily prices come from Yahoo Finance and are cached once a day."),
                html.Li("Each industry index is the average of its five rebased stocks."),
                html.Li("For any two companies we pull their last five annual reports from SEC "
                        "EDGAR and count the AI words, and read R&D spending from XBRL."),
                html.Li("Claude reads those counts, the filing excerpts and the returns, and "
                        "writes the comparison."),
                html.Li("Forecasts measure a trend and a volatility, then project a cone forward."),
            ]),
        ]),
    ])
