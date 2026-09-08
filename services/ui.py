"""Small Dash layout helpers shared by the pages (tiles, controls, tables, notices)."""
from __future__ import annotations

from dash import dcc, html

GRAPH_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}


def pct(value, digits: int = 1, sign: bool = True) -> str:
    if value is None:
        return "n/a"
    text = f"{value:+,.{digits}f}%" if sign else f"{value:,.{digits}f}%"
    return text


def num(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def tone(value) -> str:
    if value is None:
        return ""
    return "up" if value > 0 else "down" if value < 0 else ""


def tile(label: str, value: str, sub: str | None = None, value_tone: str = "") -> html.Div:
    children = [html.Div(label, className="label"), html.Div(value, className=f"value {value_tone}".strip())]
    if sub:
        children.append(html.Div(sub, className="sub"))
    return html.Div(className="tile", children=children)


def control(label: str, component, grow: bool = False) -> html.Div:
    return html.Div(className="control grow" if grow else "control",
                    children=[html.Label(label), component])


def notice(text: str, kind: str = "info") -> html.Div:
    return html.Div(text, className=f"notice {kind}")


def page_head(title: str, subtitle: str, eyebrow: str | None = None) -> html.Div:
    children = []
    if eyebrow:
        children.append(html.P(eyebrow, className="eyebrow"))
    children += [html.H1(title), html.P(subtitle, className="subtitle")]
    return html.Div(className="page-head", children=children)


def table(headers: list[str], rows: list[list], numeric_from: int = 1) -> html.Table:
    """A plain themed table. Cells from ``numeric_from`` onward are right-aligned."""
    def cell(value, i):
        cls = "num" if i >= numeric_from else ""
        return html.Td(value, className=cls)

    return html.Table(className="data", children=[
        html.Thead(html.Tr([html.Th(h, className="num" if i >= numeric_from else "")
                            for i, h in enumerate(headers)])),
        html.Tbody([html.Tr([cell(v, i) for i, v in enumerate(row)]) for row in rows]),
    ])


def summary_block(result: dict) -> html.Div:
    meta = f"Written by {result.get('model', 'Claude')}"
    if result.get("cached"):
        meta += " (cached)"
    return html.Div(className="summary", children=[
        dcc.Markdown(result["text"], link_target="_blank"),
        html.P(meta, className="muted small"),
    ])
