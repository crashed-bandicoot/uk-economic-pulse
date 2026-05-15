from __future__ import annotations

import numpy as np
import pandas as pd
import altair as alt


def latest_valid(series: pd.Series) -> tuple:
    s = series.dropna()
    if s.empty:
        return None, None
    return s.iloc[-1], s.index[-1]


def mom_change(series: pd.Series) -> float | None:
    s = series.dropna()
    if len(s) < 2:
        return None
    return s.iloc[-1] - s.iloc[-2]


def fmt(v, decimals: int = 1) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{decimals}f}"


def arrow(chg, higher_is_better: bool = True) -> tuple[str, str]:
    if chg is None:
        return "→", "neu"
    if abs(chg) < 0.01:
        return "→", "neu"
    favourable = (chg > 0) == higher_is_better
    return ("↑", "pos") if chg > 0 else ("↓", "neg")


def staleness_badge(date) -> str:
    if date is None:
        return ""
    months_old = (pd.Timestamp.now() - date).days / 30
    if months_old <= 2:
        return '<span class="badge-fresh">CURRENT</span>'
    elif months_old <= 5:
        return '<span class="badge-stale">LAGGED</span>'
    return '<span class="badge-stale">STALE</span>'


def build_sparkline(
    series: pd.Series, months: int = 36, higher_is_better: bool = True
) -> alt.Chart | None:
    s = series.dropna().tail(months).reset_index()
    s.columns = ["date", "value"]
    if s.empty or len(s) < 3:
        return None

    latest = s["value"].iloc[-1]
    color = "#4caf7d" if (
        (higher_is_better and latest >= 0) or (not higher_is_better and latest <= 0)
    ) else "#e05a4e"

    base = alt.Chart(s).encode(
        x=alt.X("date:T", axis=None),
        y=alt.Y("value:Q", axis=None, scale=alt.Scale(zero=False)),
    )
    line = base.mark_line(color=color, strokeWidth=1.5)
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(
        color="#2a2a2a", strokeWidth=1, strokeDash=[2, 2]
    ).encode(y="y:Q")

    return (zero + line).properties(
        width=180, height=55,
        background="#111111",
        padding={"left": 4, "right": 4, "top": 4, "bottom": 4},
    ).configure_view(stroke=None)


def metric_card_html(
    label: str, badge: str, val_str: str, unit: str,
    chg_str: str, chg_class: str, date_str: str, lag: str,
) -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}{badge}</div>
        <div class="metric-value">{val_str}<span style="font-size:0.85rem;color:#5a5a5a;"> {unit}</span></div>
        <div class="{chg_class}">{chg_str}</div>
        <div class="metric-date">{date_str} &nbsp;·&nbsp; {lag}</div>
    </div>
    """


def build_context_chart(
    col_a: str, col_b: str,
    sa: pd.Series, sb: pd.Series,
    title: str, subtitle: str, colors: list[str],
) -> alt.Chart | None:
    both = pd.DataFrame({"a": sa, "b": sb}).dropna().tail(36).reset_index()
    if len(both) < 3:
        return None
    both.columns = ["date", col_a, col_b]
    melted = both.melt("date", var_name="series", value_name="value")
    name_a = col_a.replace("_yoy", "").replace("_", " ").title()
    name_b = col_b.replace("_yoy", "").replace("_", " ").title()
    melted["series"] = melted["series"].map({col_a: name_a, col_b: name_b})

    return alt.Chart(melted).mark_line(strokeWidth=1.5).encode(
        x=alt.X("date:T", axis=alt.Axis(
            format="%y", labelColor="#5a5a5a",
            tickColor="#1e1e1e", domainColor="#1e1e1e")),
        y=alt.Y("value:Q", axis=alt.Axis(
            labelColor="#5a5a5a", tickColor="#1e1e1e",
            domainColor="#1e1e1e", gridColor="#1a1a1a")),
        color=alt.Color("series:N",
            scale=alt.Scale(domain=[name_a, name_b], range=colors),
            legend=alt.Legend(
                orient="bottom", labelColor="#d0ccc4", titleColor="#d0ccc4",
                labelFontSize=9, titleFontSize=0)),
    ).properties(
        width=220, height=400,
        background="#111111",
        title=alt.TitleParams(
            text=title, subtitle=subtitle,
            color="#8a8a8a", subtitleColor="#4a4a4a",
            fontSize=10, subtitleFontSize=8, font="IBM Plex Mono"),
    ).configure_view(stroke=None).configure_axis(
        labelFont="IBM Plex Mono", labelFontSize=8)


def build_explorer_chart(df_plot: pd.DataFrame, unit: str) -> alt.Chart:
    return alt.Chart(df_plot).mark_line(
        color="#c8b87a", strokeWidth=1.8
    ).encode(
        x=alt.X("date:T", axis=alt.Axis(
            format="%Y", labelColor="#d0ccc4",
            tickColor="#2a2a2a", domainColor="#2a2a2a")),
        y=alt.Y("value:Q", axis=alt.Axis(
            labelColor="#d0ccc4", tickColor="#2a2a2a",
            domainColor="#2a2a2a", gridColor="#1a1a1a")),
        tooltip=[
            alt.Tooltip("date:T", title="Date", format="%b %Y"),
            alt.Tooltip("value:Q", title=unit, format=".2f"),
        ],
    ).properties(
        width=900, height=400,
        background="#0f0f0f",
    ).configure_view(stroke=None).configure_axis(
        labelFont="IBM Plex Mono", labelFontSize=9)
