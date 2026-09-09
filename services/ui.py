"""Small Dash layout helpers shared by the pages (tiles, controls, tables, notices).

AI usage: see docs/AI_USAGE.md.
"""
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
    """A labeled control group.

    Dash renders its own internal inputs, so a bare ``<label>`` sitting next to a dropdown
    or a radio group is not programmatically tied to it. Naming the wrapper instead means
    assistive tech announces the label when focus enters the control (WCAG 1.3.1, 4.1.2).
    """
    label_id = f"{getattr(component, 'id', 'control')}-label"
    return html.Div(
        className="control grow" if grow else "control",
        role="group",
        **{"aria-labelledby": label_id},
        children=[html.Label(label, id=label_id), component],
    )


def notice(text: str, kind: str = "info") -> html.Div:
    """A status or error panel.

    Errors are announced assertively because they interrupt what the user asked for;
    ordinary notices are polite so they wait for a pause (WCAG 4.1.3 Status Messages).
    """
    return html.Div(
        text,
        className=f"notice {kind}",
        role="alert" if kind == "error" else "status",
        **{"aria-live": "assertive" if kind == "error" else "polite"},
    )


def page_head(title: str, subtitle: str, eyebrow: str | None = None) -> html.Div:
    children = []
    if eyebrow:
        children.append(html.P(eyebrow, className="eyebrow"))
    children += [html.H1(title), html.P(subtitle, className="subtitle")]
    return html.Div(className="page-head", children=children)


def table(headers: list[str], rows: list[list], numeric_from: int = 1,
          caption: str | None = None) -> html.Table:
    """A plain themed table. Cells from ``numeric_from`` onward are right-aligned.

    ``scope="col"`` ties every data cell to its header for screen readers (WCAG 1.3.1), and
    ``caption`` adds a visually hidden name so the table is identifiable out of context.
    """
    def cell(value, i):
        cls = "num" if i >= numeric_from else ""
        return html.Td(value, className=cls)

    children = []
    if caption:
        children.append(html.Caption(caption, className="sr-only"))
    children += [
        html.Thead(html.Tr([html.Th(h, scope="col", className="num" if i >= numeric_from else "")
                            for i, h in enumerate(headers)])),
        html.Tbody([html.Tr([cell(v, i) for i, v in enumerate(row)]) for row in rows]),
    ]
    return html.Table(className="data", children=children)


def chart(graph, caption_id: str) -> html.Figure:
    """A chart paired with the text alternative WCAG 1.1.1 requires.

    Plotly draws to SVG with no accessible description, so each figure carries a caption
    that the callback fills with a written summary of what the chart currently shows. It is
    visually hidden - sighted users have the chart itself - but it is real page text, so it
    is reachable by screen readers and by find-in-page.
    """
    return html.Figure(className="chart", children=[
        graph,
        html.Figcaption(id=caption_id, className="sr-only"),
    ])


def describe_ranked(intro: str, pairs, unit: str = "", digits: int = 0) -> str:
    """'<intro> Name value, Name value.' - the spoken form of a ranked chart."""
    parts = ", ".join(f"{name} {value:,.{digits}f}{unit}" for name, value in pairs)
    return f"{intro} {parts}." if parts else f"{intro} no data available."


def summary_block(result: dict) -> html.Div:
    meta = f"Written by {result.get('model', 'Claude')}"
    if result.get("cached"):
        meta += " (cached)"
    return html.Div(className="summary", children=[
        dcc.Markdown(result["text"], link_target="_blank"),
        html.P(meta, className="muted small"),
    ])
