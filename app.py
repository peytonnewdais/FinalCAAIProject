"""AI Boom Scorecard - a multi-page Dash app.

Pages are in the pages/ folder, data and API code is in the services/ folder.
Run it with:  python app.py
"""
from dash import Dash, Input, Output, State, dcc, html, page_container

from services import config
from services.market_data import load_prices

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    # Font Awesome supplies the glyphs on the home page cards.
    external_stylesheets=[
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css",
    ],
)
app.title = config.APP_TITLE
server = app.server          # used when the app is deployed

# The nav bar is the same on every page, so it lives here instead of in each page.
NAV = [("/", "Home"), ("/industries", "Industries"),
       ("/compare", "Compare Stocks"), ("/forecast", "Forecast")]

app.layout = html.Div([
    # Remembers the colorblind-mode toggle in the browser (localStorage) so it
    # survives page navigation and repeat visits. Every page's charts take it
    # as a callback Input and pick a colorblind-safe palette (see
    # services/config.py); the CSS under "body.colorblind" recolors the
    # plain up/down text.
    dcc.Store(id="colorblind-mode", storage_type="local", data=False),

    html.Div(className="navbar", children=[
        dcc.Link("AI Boom Scorecard", href="/", className="brand"),
        html.Span("   "),
        *[dcc.Link(label, href=path) for path, label in NAV],
        html.Button(
            [html.I(className="fa-solid fa-eye-low-vision", **{"aria-hidden": "true"}),
             " Colorblind mode"],
            id="colorblind-toggle", n_clicks=0, className="colorblind-toggle",
            **{"aria-pressed": "false"},
        ),
    ]),

    # page_container is where Dash draws whichever page is selected
    html.Div(page_container, className="page"),

    html.Div(className="footer", children=[
        html.Div(config.TEAM),
        html.Div(config.SOURCE),
        html.Div("Educational project, not investment advice."),
    ]),
])

# Clicking the button flips the stored preference...
app.clientside_callback(
    """
    function(nClicks, isOn) {
        if (!nClicks) { return window.dash_clientside.no_update; }
        return !isOn;
    }
    """,
    Output("colorblind-mode", "data"),
    Input("colorblind-toggle", "n_clicks"),
    State("colorblind-mode", "data"),
)

# ...and this applies it to the button itself (its pressed state, which the CSS
# uses to highlight it) and to <body>, so the CSS-only elements (the up/down
# tile text, the error notices) recolor instantly. It also runs once on
# startup, so a preference saved from a previous visit takes effect right away.
app.clientside_callback(
    """
    function(isOn) {
        document.body.classList.toggle('colorblind', !!isOn);
        return isOn ? 'true' : 'false';
    }
    """,
    Output("colorblind-toggle", "aria-pressed"),
    Input("colorblind-mode", "data"),
)

if __name__ == "__main__":
    load_prices()            # download prices once before the first page loads
    app.run(debug=True)
