"""AI Boom Scorecard - a multi-page Dash app.

Pages are in the pages/ folder, data and API code is in the services/ folder.
Run it with:  python app.py
"""
from dash import Dash, dcc, html, page_container

from services import config
from services.market_data import load_prices

app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True)
app.title = config.APP_TITLE
server = app.server          # used when the app is deployed

# The nav bar is the same on every page, so it lives here instead of in each page.
NAV = [("/", "Home"), ("/industries", "Industries"),
       ("/compare", "Compare Stocks"), ("/forecast", "Forecast")]

app.layout = html.Div([
    html.Div(className="navbar", children=[
        dcc.Link("AI Boom Scorecard", href="/", className="brand"),
        html.Span("   "),
        *[dcc.Link(label, href=path) for path, label in NAV],
    ]),

    # page_container is where Dash draws whichever page is selected
    html.Div(page_container, className="page"),

    html.Div(className="footer", children=[
        html.Div(config.TEAM),
        html.Div(config.SOURCE),
        html.Div("Educational project, not investment advice."),
    ]),
])

if __name__ == "__main__":
    load_prices()            # download prices once before the first page loads
    app.run(debug=True)
