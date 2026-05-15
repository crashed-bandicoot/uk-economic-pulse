"""
UK Economic Pulse — Streamlit Dashboard
========================================
Run: streamlit run app.py
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from catalogue import CATALOGUE, CATEGORY_ORDER, CONTEXT_PAIRS
from data import fetch_live_fred, load_csvs
from style import CSS, FOOTER_HTML, METHODOLOGY_MD, masthead_html
from utils import (
    arrow, build_context_chart, build_explorer_chart,
    build_sparkline, fmt, latest_valid, metric_card_html,
    mom_change, staleness_badge,
)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="UK Economic Pulse",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MASTHEAD
# ─────────────────────────────────────────────
today_str = pd.Timestamp.now().strftime("%d %b %Y").upper()
left_html, right_html = masthead_html(today_str)

col_l, col_r = st.columns([3, 1])
with col_l:
    st.markdown(left_html, unsafe_allow_html=True)
with col_r:
    st.markdown(right_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DATA SOURCE SELECTION
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">Data Source</div>', unsafe_allow_html=True)

data_mode = st.radio(
    "Load data from",
    options=["Local CSV files"
             #, "Live FRED pull"
             ],
    horizontal=True,
    label_visibility="collapsed",
)

abs_df = sig_df = None

if data_mode == "Local CSV files":
    abs_path = st.text_input("Path to absolute_values.csv", value="data/raw/absolute_values.csv")
    sig_path = st.text_input("Path to signals.csv", value="data/raw/signals.csv")
    if os.path.exists(abs_path) and os.path.exists(sig_path):
        abs_df, sig_df = load_csvs(abs_path, sig_path)
    else:
        st.markdown(
            '<div class="api-banner">⚠ CSV files not found. Update the paths above or switch to Live FRED pull.</div>',
            unsafe_allow_html=True,
        )

else:
    api_key = st.text_input(
        "FRED API Key", type="password", placeholder="Enter your FRED API key…",
        help="Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html",
    )
    if not api_key:
        api_key = st.secrets.get("FRED_API_KEY", os.getenv("FRED_API_KEY", ""))
    if api_key:
        with st.spinner("Pulling live macro data from FRED / ONS / yfinance…"):
            try:
                abs_df, sig_df = fetch_live_fred(api_key)
            except Exception as e:
                st.error(f"Data pull failed: {e}")
    else:
        st.markdown(
            '<div class="api-banner">Enter your FRED API key to pull live data. Free registration at <strong>fred.stlouisfed.org</strong></div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────
# GATE — nothing below renders without data
# ─────────────────────────────────────────────
if abs_df is None or sig_df is None:
    st.stop()

if "uk_yield_curve" not in sig_df.columns:
    if "yield_uk_10y" in abs_df.columns and "yield_uk_3m" in abs_df.columns:
        sig_df["uk_yield_curve"] = abs_df["yield_uk_10y"] - abs_df["yield_uk_3m"]


def get_series(spec: dict) -> pd.Series:
    col = spec["signal_col"]
    return sig_df[col] if col in sig_df.columns else pd.Series(dtype=float)


# ─────────────────────────────────────────────
# METRICS TABLE
# ─────────────────────────────────────────────
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)

for cat in CATEGORY_ORDER:
    items = [s for s in CATALOGUE if s["category"] == cat]
    if not items:
        continue

    st.markdown(f'<div class="section-label">{cat}</div>', unsafe_allow_html=True)
    n_cols = min(4, len(items))
    cols = st.columns(n_cols)

    for i, spec in enumerate(items):
        series = get_series(spec)
        val, vdate = latest_valid(series)
        chg = mom_change(series)
        arr, sentiment = arrow(chg, spec["higher_is_better"])

        val_str  = fmt(val, spec["decimals"]) if val is not None else "—"
        date_str = vdate.strftime("%b %Y") if vdate is not None else "—"
        badge    = staleness_badge(vdate)

        if chg is None:
            chg_str, chg_class = "—", "metric-change-neu"
        else:
            sign = "+" if chg >= 0 else ""
            chg_str   = f"{arr} {sign}{chg:.{spec['decimals']}f} MoM"
            chg_class = f"metric-change-{sentiment}"

        with cols[i % n_cols]:
            st.markdown(
                metric_card_html(spec["label"], badge, val_str, spec["unit"], chg_str, chg_class, date_str, spec["lag"]),
                unsafe_allow_html=True,
            )
            chart = build_sparkline(series, months=36, higher_is_better=spec["higher_is_better"])
            if chart is not None:
                st.altair_chart(chart, use_container_width=False)

        if (i + 1) % n_cols == 0 and (i + 1) < len(items):
            cols = st.columns(n_cols)


# ─────────────────────────────────────────────
# CONTEXTUAL RELATIONSHIPS
# ─────────────────────────────────────────────
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">Contextual Relationships</div>', unsafe_allow_html=True)

for row_start in range(0, len(CONTEXT_PAIRS), 2):
    ctx_cols = st.columns(2)
    for i, (col_a, col_b, title, subtitle, colors) in enumerate(CONTEXT_PAIRS[row_start:row_start + 2]):
        sa = sig_df[col_a].dropna() if col_a in sig_df.columns else pd.Series(dtype=float)
        sb = sig_df[col_b].dropna() if col_b in sig_df.columns else pd.Series(dtype=float)
        if sa.empty or sb.empty:
            continue
        try:
            chart = build_context_chart(col_a, col_b, sa, sb, title, subtitle, colors)
            if chart is not None:
                with ctx_cols[i]:
                    st.altair_chart(chart, use_container_width=True)
        except Exception:
            pass


# ─────────────────────────────────────────────
# SERIES EXPLORER
# ─────────────────────────────────────────────
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">Series Explorer</div>', unsafe_allow_html=True)

all_keys  = [s["key"] for s in CATALOGUE]
all_specs = {s["key"]: s for s in CATALOGUE}

selected_key = st.selectbox(
    "Select indicator",
    options=all_keys,
    format_func=lambda k: all_specs[k]["label"],
    label_visibility="collapsed",
)

spec   = all_specs[selected_key]
series = get_series(spec)
s      = series.dropna()

if not s.empty:
    df_plot = s.reset_index()
    df_plot.columns = ["date", "value"]
    val_now, _ = latest_valid(series)
    s_24 = s.tail(24)
    yoy_val = s.pct_change(12).iloc[-1] * 100 if len(s) >= 13 else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Current", f"{fmt(val_now, spec['decimals'])} {spec['unit']}")
    with c2:
        st.metric("12M change", f"{fmt(yoy_val, 1)} pp" if yoy_val is not None else "—")
    with c3:
        st.metric("24M high", fmt(s_24.max(), spec["decimals"]))
    with c4:
        st.metric("24M low", fmt(s_24.min(), spec["decimals"]))

    st.altair_chart(build_explorer_chart(df_plot, spec["unit"]), use_container_width=True)


# ─────────────────────────────────────────────
# RAW DATA TABLE
# ─────────────────────────────────────────────
with st.expander("Raw signal data (last 24 months)"):
    display_cols   = [s["signal_col"] for s in CATALOGUE if s["signal_col"] in sig_df.columns]
    display_labels = {s["signal_col"]: s["label"] for s in CATALOGUE}
    df_show = sig_df[display_cols].tail(24).rename(columns=display_labels)
    st.dataframe(df_show.style.format("{:.2f}", na_rep="—"), use_container_width=True)


# ─────────────────────────────────────────────
# METHODOLOGY + FOOTER
# ─────────────────────────────────────────────
with st.expander("Methodology"):
    st.markdown(METHODOLOGY_MD)

st.markdown(FOOTER_HTML, unsafe_allow_html=True)
