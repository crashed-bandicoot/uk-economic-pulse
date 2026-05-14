"""
UK Economic Pulse — Streamlit Dashboard
========================================
Reads: data/raw/absolute_values.csv  +  data/raw/signals.csv
Run:   streamlit run app.py
"""

from __future__ import annotations

import os
import io
import requests
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from fredapi import Fred
import yfinance as yf

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="UK Economic Pulse",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# STYLING  — Bloomberg terminal meets broadsheet
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&family=Playfair+Display:wght@700;900&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0a0a0a;
    color: #e8e0d0;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem 4rem 2.5rem; max-width: 1400px; }

/* Masthead */
.masthead {
    border-bottom: 1px solid #2a2a2a;
    padding-bottom: 1.2rem;
    margin-bottom: 2rem;
}
.masthead-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.4rem;
    font-weight: 900;
    letter-spacing: -0.02em;
    color: #f5f0e8;
    line-height: 1;
    margin: 0;
}
.masthead-sub {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #d0ccc4;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 0.4rem;
}
.masthead-date {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #d0ccc4;
    text-align: right;
}

/* Section labels */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #d0ccc4;
    border-bottom: 1px solid #1e1e1e;
    padding-bottom: 0.4rem;
    margin-bottom: 1rem;
    margin-top: 1.8rem;
}

/* Metric cards */
.metric-card {
    background: #111111;
    border: 1px solid #1e1e1e;
    border-radius: 2px;
    padding: 1rem 1.1rem 0.9rem;
    min-height: 110px;
}
.metric-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #d0ccc4;
    margin-bottom: 0.5rem;
}
.metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.6rem;
    font-weight: 600;
    color: #f5f0e8;
    line-height: 1;
}
.metric-change-pos {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #4caf7d;
    margin-top: 0.3rem;
}
.metric-change-neg {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #e05a4e;
    margin-top: 0.3rem;
}
.metric-change-neu {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #d0ccc4;
    margin-top: 0.3rem;
}
.metric-date {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem;
    color: #5a5a5a;
    margin-top: 0.25rem;
}

/* Data freshness badge */
.badge-fresh {
    display: inline-block;
    background: #0d2b1a;
    color: #4caf7d;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.1em;
    padding: 0.15rem 0.5rem;
    border-radius: 2px;
    margin-left: 0.5rem;
    vertical-align: middle;
}
.badge-stale {
    display: inline-block;
    background: #2b1a0d;
    color: #e0904e;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.1em;
    padding: 0.15rem 0.5rem;
    border-radius: 2px;
    margin-left: 0.5rem;
    vertical-align: middle;
}

/* Divider */
.rule { border: none; border-top: 1px solid #1e1e1e; margin: 1.5rem 0; }

/* Stale data note */
.stale-note {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    color: #4a4a4a;
    font-style: italic;
    margin-top: 0.2rem;
}

/* API key input styling */
.api-banner {
    background: #111111;
    border: 1px solid #2a2a2a;
    border-left: 3px solid #e0904e;
    padding: 1rem 1.2rem;
    margin-bottom: 2rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    color: #d0ccc4;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SERIES CATALOGUE
# ─────────────────────────────────────────────
# Each entry: label, category, signal_col (in signals.csv), abs_col (in absolute_values.csv),
#             unit, decimals, higher_is_better, lag_note
CATALOGUE = [
    # Economic Activity
    dict(key="gdp",          label="UK GDP Growth",        category="Economic Activity",
         signal_col="gdp_growth_yoy",    abs_col="gdp",
         unit="% YoY",       decimals=1, higher_is_better=True,  lag="Quarterly · ~2m lag"),
    dict(key="retail",       label="Retail Sales",         category="Economic Activity",
         signal_col="retail_sales_yoy",  abs_col="retail_sales",
         unit="% YoY",       decimals=1, higher_is_better=True,  lag="Monthly · ~4w lag"),
    dict(key="house",        label="House Prices",         category="Economic Activity",
         signal_col="house_prices_yoy",  abs_col="house_prices",
         unit="% YoY",       decimals=1, higher_is_better=True,  lag="Quarterly · ~2m lag"),
    # Labour
    dict(key="unemp",        label="Unemployment Rate",    category="Labour Market",
         signal_col="unemployment_rate", abs_col="unemployment_rate",
         unit="%",           decimals=1, higher_is_better=False, lag="Monthly · ~6w lag"),
    dict(key="particip",     label="Labour Participation", category="Labour Market",
         signal_col="participation_rate",abs_col="participation_rate",
         unit="%",           decimals=1, higher_is_better=True,  lag="Monthly · ~6w lag"),
    # Inflation
    dict(key="cpi",          label="CPI Inflation",        category="Inflation Pressure",
         signal_col="cpi_yoy",           abs_col="cpi",
         unit="% YoY",       decimals=1, higher_is_better=False, lag="Monthly · ~3w lag"),
    dict(key="realwage",     label="Real Wage Growth",     category="Inflation Pressure",
         signal_col="real_wages_yoy",    abs_col="real_wages",
         unit="% YoY",       decimals=1, higher_is_better=True,  lag="Monthly · ~6w lag"),
    # Financial Conditions
    dict(key="polrate",      label="BoE Policy Rate",      category="Financial Conditions",
         signal_col="policy_rate",       abs_col="policy_rate",
         unit="%",           decimals=2, higher_is_better=False, lag="Real-time"),
    dict(key="uk10y",        label="UK 10Y Gilt Yield",    category="Financial Conditions",
         signal_col="yield_uk_10y",      abs_col="yield_uk_10y",
         unit="%",           decimals=2, higher_is_better=False, lag="Monthly mean"),
    dict(key="ukcrv",        label="UK Yield Curve",       category="Financial Conditions",
         signal_col="uk_yield_curve",    abs_col=None,
         unit="pp (10Y−3M)", decimals=2, higher_is_better=True,  lag="Monthly"),
    dict(key="hyspread",     label="US HY Credit Spread",  category="Financial Conditions",
         signal_col="spread_us_hy",      abs_col="spread_us_hy",
         unit="pp",          decimals=2, higher_is_better=False, lag="Daily · since 2023"),
    # Commodities
    dict(key="oil",          label="Brent Oil",            category="Commodities",
         signal_col="oil_yoy",           abs_col="oil",
         unit="% YoY",       decimals=1, higher_is_better=False, lag="Monthly mean"),
    dict(key="copper",       label="Copper",               category="Commodities",
         signal_col="copper_yoy",        abs_col="copper",
         unit="% YoY",       decimals=1, higher_is_better=True,  lag="Monthly mean"),
    dict(key="natgas",       label="Natural Gas",          category="Commodities",
         signal_col="nat_gas_yoy",       abs_col="nat_gas",
         unit="% YoY",       decimals=1, higher_is_better=False, lag="Monthly mean"),
    dict(key="gold",         label="Gold",                 category="Commodities",
         signal_col="gold_yoy",          abs_col="gold",
         unit="% YoY",       decimals=1, higher_is_better=False, lag="Monthly mean"),
    # FX / Market
    dict(key="dxy",          label="US Dollar (DXY)",      category="Markets",
         signal_col="dxy_yoy",           abs_col="dxy",
         unit="% YoY",       decimals=1, higher_is_better=False, lag="Monthly mean"),
    dict(key="sox",          label="Semiconductors (SOX)", category="Markets",
         signal_col="sox_yoy",           abs_col="sox",
         unit="% YoY",       decimals=1, higher_is_better=True,  lag="Monthly mean"),
]

CATEGORY_ORDER = [
    "Economic Activity",
    "Labour Market",
    "Inflation Pressure",
    "Financial Conditions",
    "Commodities",
    "Markets",
]


# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def load_csvs(abs_path: str, sig_path: str):
    abs_df  = pd.read_csv(abs_path,  index_col=0, parse_dates=True)
    sig_df  = pd.read_csv(sig_path,  index_col=0, parse_dates=True)
    abs_df.index  = pd.to_datetime(abs_df.index)
    sig_df.index  = pd.to_datetime(sig_df.index)
    return abs_df, sig_df


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_live_fred(api_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pull fresh data from FRED + ONS + yfinance."""
    from fredapi import Fred
    fred = Fred(api_key=api_key)

    def ffill_monthly(s):   return s.resample("ME").ffill()
    def mean_monthly(s):    return s.resample("ME").mean()
    def last_monthly(s):    return s.resample("ME").last()

    # ---- FRED series ----
    gdp            = ffill_monthly(fred.get_series("NGDPRSAXDCGBQ"))
    house_prices   = ffill_monthly(fred.get_series("QGBR628BIS"))
    cpi            = last_monthly(fred.get_series("GBRCPIALLMINMEI"))
    policy_rate    = last_monthly(fred.get_series("BOESRPPACBIS"))
    uk10y          = last_monthly(fred.get_series("IRLTLT01GBM156N"))
    uk3m           = last_monthly(fred.get_series("IR3TIB01GBM156N"))
    real_wages     = last_monthly(fred.get_series("LCEAMN01GBM661S"))
    unemp          = last_monthly(fred.get_series("LRUNTTTTGBM156S"))
    particip       = last_monthly(fred.get_series("LFAC64TTGBQ647S"))
    oil            = mean_monthly(fred.get_series("DCOILBRENTEU"))
    hy_spread      = mean_monthly(fred.get_series("BAMLH0A0HYM2"))
    twusd          = mean_monthly(fred.get_series("DTWEXBGS"))

    # ---- ONS Retail Sales ----
    try:
        url = "https://www.ons.gov.uk/file?uri=/businessindustryandtrade/retailindustry/datasets/retailsalesindexreferencetables/current/mainreferencetables.xlsx"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df_ons = pd.read_excel(io.BytesIO(r.content), sheet_name="KPSA", header=6)
        time_col  = "Time Period"
        value_col = "All retailing including automotive fuel [note1]"
        df_ons = df_ons[[time_col, value_col]].dropna(subset=[time_col])
        mask = df_ons[time_col].astype(str).str.contains("Revision", case=False, na=False)
        if mask.any():
            df_ons = df_ons[: mask.idxmax()]
        df_ons[time_col] = pd.to_datetime(df_ons[time_col].astype(str), format="%Y %b", errors="coerce")
        df_ons = df_ons.dropna(subset=[time_col])
        df_ons = df_ons.set_index(time_col)[value_col].sort_index()
        retail = df_ons.resample("ME").last()
    except Exception:
        retail = pd.Series(dtype=float)

    # ---- yfinance ----
    def yf_monthly(ticker, start="2000-01-01"):
        try:
            s = yf.download(ticker, start=start, progress=False)["Close"].squeeze()
            s.index = pd.to_datetime(s.index)
            return s.resample("ME").mean()
        except Exception:
            return pd.Series(dtype=float)

    gold    = yf_monthly("GC=F")
    copper  = yf_monthly("HG=F")
    nat_gas = yf_monthly("NG=F")
    sox     = yf_monthly("^SOX")
    dxy     = yf_monthly("DX-Y.NYB")

    # ---- Assemble ----
    abs_df = pd.DataFrame({
        "gdp":              gdp,
        "house_prices":     house_prices,
        "retail_sales":     retail,
        "cpi":              cpi,
        "real_wages":       real_wages,
        "policy_rate":      policy_rate,
        "yield_uk_10y":     uk10y,
        "yield_uk_3m":      uk3m,
        "spread_us_hy":     hy_spread,
        "oil":              oil,
        "gold":             gold,
        "copper":           copper,
        "nat_gas":          nat_gas,
        "sox":              sox,
        "dxy":              dxy,
        "unemployment_rate":unemp,
        "participation_rate":particip,
    }).sort_index()

    sig_df = pd.DataFrame(index=abs_df.index)
    yoy = lambda col: abs_df[col].pct_change(12, fill_method=None) * 100

    sig_df["gdp_growth_yoy"]     = yoy("gdp")
    sig_df["house_prices_yoy"]   = yoy("house_prices")
    sig_df["retail_sales_yoy"]   = yoy("retail_sales")
    sig_df["cpi_yoy"]            = yoy("cpi")
    sig_df["real_wages_yoy"]     = yoy("real_wages")
    sig_df["unemployment_rate"]  = abs_df["unemployment_rate"]
    sig_df["participation_rate"] = abs_df["participation_rate"]
    sig_df["policy_rate"]        = abs_df["policy_rate"]
    sig_df["yield_uk_10y"]       = abs_df["yield_uk_10y"]
    sig_df["uk_yield_curve"]     = abs_df["yield_uk_10y"] - abs_df["yield_uk_3m"]
    sig_df["spread_us_hy"]       = abs_df["spread_us_hy"]
    sig_df["oil_yoy"]            = yoy("oil")
    sig_df["copper_yoy"]         = yoy("copper")
    sig_df["nat_gas_yoy"]        = yoy("nat_gas")
    sig_df["gold_yoy"]           = yoy("gold")
    sig_df["dxy_yoy"]            = yoy("dxy")
    sig_df["sox_yoy"]            = yoy("sox")

    return abs_df, sig_df


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def latest_valid(series: pd.Series):
    s = series.dropna()
    if s.empty:
        return None, None
    return s.iloc[-1], s.index[-1]


def mom_change(series: pd.Series):
    s = series.dropna()
    if len(s) < 2:
        return None
    return s.iloc[-1] - s.iloc[-2]


def format_val(v, decimals=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v:+.{decimals}f}" if v != abs(v) else f"{v:.{decimals}f}"


def fmt(v, decimals=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{decimals}f}"


def arrow(chg, higher_is_better=True):
    if chg is None:
        return "→", "neu"
    favourable = (chg > 0) == higher_is_better
    if abs(chg) < 0.01:
        return "→", "neu"
    return ("↑", "pos") if chg > 0 else ("↓", "neg")


def staleness_badge(date):
    if date is None:
        return ""
    months_old = (pd.Timestamp.now() - date).days / 30
    if months_old <= 2:
        return '<span class="badge-fresh">CURRENT</span>'
    elif months_old <= 5:
        return '<span class="badge-stale">LAGGED</span>'
    else:
        return '<span class="badge-stale">STALE</span>'


def build_sparkline(series: pd.Series, months: int = 36, higher_is_better: bool = True):
    s = series.dropna().tail(months).reset_index()
    s.columns = ["date", "value"]
    if s.empty or len(s) < 3:
        return None

    latest = s["value"].iloc[-1]
    color  = "#4caf7d" if (
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

    chart = (zero + line).properties(
        width=180, height=55,
        background="#111111",
        padding={"left": 4, "right": 4, "top": 4, "bottom": 4},
    ).configure_view(stroke=None)

    return chart


# ─────────────────────────────────────────────
# MASTHEAD
# ─────────────────────────────────────────────
today_str = pd.Timestamp.now().strftime("%d %b %Y").upper()

col_l, col_r = st.columns([3, 1])
with col_l:
    st.markdown(f"""
    <div class="masthead">
        <div class="masthead-title">UK ECONOMIC PULSE</div>
        <div class="masthead-sub">Macro Intelligence Dashboard &nbsp;·&nbsp; Data: FRED / ONS / yfinance</div>
    </div>
    """, unsafe_allow_html=True)
with col_r:
    st.markdown(f"""
    <div style="text-align:right; padding-top:1.6rem;">
        <div class="masthead-date">{today_str}</div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DATA SOURCE SELECTION
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">Data Source</div>', unsafe_allow_html=True)

data_mode = st.radio(
    "Load data from",
    options=["Local CSV files", "Live FRED pull"],
    horizontal=True,
    label_visibility="collapsed",
)

abs_df = sig_df = None

if data_mode == "Local CSV files":
    abs_path = st.text_input(
        "Path to absolute_values.csv",
        value="data/raw/absolute_values.csv",
        label_visibility="visible",
    )
    sig_path = st.text_input(
        "Path to signals.csv",
        value="data/raw/signals.csv",
        label_visibility="visible",
    )
    if os.path.exists(abs_path) and os.path.exists(sig_path):
        abs_df, sig_df = load_csvs(abs_path, sig_path)
    else:
        st.markdown("""
        <div class="api-banner">
        ⚠ CSV files not found at the specified paths. Either update the paths above,
        or switch to Live FRED pull below.
        </div>
        """, unsafe_allow_html=True)

else:  # Live FRED pull
    api_key = st.text_input(
        "FRED API Key",
        type="password",
        placeholder="Enter your FRED API key…",
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
        st.markdown("""
        <div class="api-banner">
        Enter your FRED API key to pull live data. Free registration at
        <strong>fred.stlouisfed.org</strong>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN DASHBOARD  (only renders when data loaded)
# ─────────────────────────────────────────────
if abs_df is None or sig_df is None:
    st.stop()


# Derive yield curve if missing from signals
if "uk_yield_curve" not in sig_df.columns:
    if "yield_uk_10y" in abs_df.columns and "yield_uk_3m" in abs_df.columns:
        sig_df["uk_yield_curve"] = abs_df["yield_uk_10y"] - abs_df["yield_uk_3m"]


# ─── build a lookup: key → series
def get_series(spec: dict) -> pd.Series:
    col = spec["signal_col"]
    if col in sig_df.columns:
        return sig_df[col]
    return pd.Series(dtype=float)


# ─────────────────────────────────────────────
# METRICS TABLE
# ─────────────────────────────────────────────
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)

# Group by category
from itertools import groupby

for cat in CATEGORY_ORDER:
    items = [s for s in CATALOGUE if s["category"] == cat]
    if not items:
        continue

    st.markdown(f'<div class="section-label">{cat}</div>', unsafe_allow_html=True)

    # Economic Activity gets 3 columns (GDP, Retail Sales, House Prices); all others max 2
    max_cols = 4 if cat == "Economic Activity" else 2
    n_cols = min(max_cols, len(items))
    cols = st.columns(n_cols)

    for i, spec in enumerate(items):
        col_idx = i % n_cols
        series  = get_series(spec)
        val, vdate = latest_valid(series)
        chg     = mom_change(series)
        arr, sentiment = arrow(chg, spec["higher_is_better"])
        badge   = staleness_badge(vdate)

        date_str = vdate.strftime("%b %Y") if vdate is not None else "—"
        val_str  = fmt(val, spec["decimals"]) if val is not None else "—"

        if chg is None:
            chg_str   = "—"
            chg_class = "metric-change-neu"
        else:
            sign = "+" if chg >= 0 else ""
            chg_str   = f"{arr} {sign}{chg:.{spec['decimals']}f} MoM"
            chg_class = f"metric-change-{sentiment}"

        with cols[col_idx]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{spec['label']}{badge}</div>
                <div class="metric-value">{val_str}<span style="font-size:0.85rem;color:#d0ccc4;"> {spec['unit']}</span></div>
                <div class="{chg_class}">{chg_str}</div>
                <div class="metric-date">{date_str} &nbsp;·&nbsp; {spec['lag']}</div>
            </div>
            """, unsafe_allow_html=True)

            # Sparkline
            chart = build_sparkline(series, months=36, higher_is_better=spec["higher_is_better"])
            if chart is not None:
                st.altair_chart(chart, use_container_width=False)

        # Start new row
        if (i + 1) % n_cols == 0 and (i + 1) < len(items):
            cols = st.columns(n_cols)


# ─────────────────────────────────────────────
# CROSS-SERIES CONTEXT PANEL
# ─────────────────────────────────────────────
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">Contextual Relationships</div>', unsafe_allow_html=True)

# Copper vs DXY (global demand signal)
# Oil YoY vs CPI YoY (cost-push channel)
# Policy rate vs UK 10Y (monetary transmission)
# Real wages vs CPI (purchasing power)

# colors: (col_a color, col_b color)
context_pairs = [
    ("cpi_yoy",         "real_wages_yoy",   "CPI vs Real Wage Growth",      "Inflation Pressure",    ["#e05a4e", "#4caf7d"]),
    ("policy_rate",     "yield_uk_10y",     "Policy Rate vs 10Y Gilt",      "Financial Conditions",  ["#4caf7d", "#e05a4e"]),
    ("copper_yoy",      "dxy_yoy",          "Copper YoY vs DXY YoY",        "Global Demand Signal",  ["#4caf7d", "#e05a4e"]),
    ("oil_yoy",         "cpi_yoy",          "Oil YoY vs CPI YoY",           "Cost-Push Channel",     ["#4caf7d", "#e05a4e"]),
]

for row_start in range(0, len(context_pairs), 2):
    row_pairs = context_pairs[row_start:row_start + 2]
    ctx_cols = st.columns(2)

    for i, (col_a, col_b, title, subtitle, colors) in enumerate(row_pairs):
        sa = sig_df[col_a].dropna() if col_a in sig_df.columns else pd.Series(dtype=float)
        sb = sig_df[col_b].dropna() if col_b in sig_df.columns else pd.Series(dtype=float)

        if sa.empty or sb.empty:
            continue

        # Align and take last 36 months
        both = pd.DataFrame({"a": sa, "b": sb}).dropna().tail(36).reset_index()
        both.columns = ["date", col_a, col_b]

        try:
            melted = both.melt("date", var_name="series", value_name="value")

            name_a = col_a.replace("_yoy", "").replace("_", " ").title()
            name_b = col_b.replace("_yoy", "").replace("_", " ").title()
            name_map = {col_a: name_a, col_b: name_b}
            melted["series"] = melted["series"].map(name_map)

            chart = alt.Chart(melted).mark_line(strokeWidth=1.5).encode(
                x=alt.X("date:T", axis=alt.Axis(format="%y", labelColor="#5a5a5a", tickColor="#1e1e1e", domainColor="#1e1e1e")),
                y=alt.Y("value:Q", axis=alt.Axis(labelColor="#5a5a5a", tickColor="#1e1e1e", domainColor="#1e1e1e", gridColor="#1a1a1a")),
                color=alt.Color("series:N",
                                scale=alt.Scale(domain=[name_a, name_b], range=colors),
                                legend=alt.Legend(orient="bottom", labelColor="#d0ccc4", titleColor="#d0ccc4",
                                                  labelFontSize=9, titleFontSize=0)),
            ).properties(
                width=220, height=400,
                background="#111111",
                title=alt.TitleParams(text=title, subtitle=subtitle,
                                      color="#d0ccc4", subtitleColor="#4a4a4a",
                                      fontSize=10, subtitleFontSize=8,
                                      font="IBM Plex Mono"),
            ).configure_view(stroke=None).configure_axis(labelFont="IBM Plex Mono", labelFontSize=8)

            with ctx_cols[i]:
                st.altair_chart(chart, use_container_width=True)
        except Exception:
            pass


# ─────────────────────────────────────────────
# FULL HISTORY EXPLORER
# ─────────────────────────────────────────────
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">Series Explorer</div>', unsafe_allow_html=True)

all_keys    = [s["key"] for s in CATALOGUE]
all_labels  = {s["key"]: s["label"] for s in CATALOGUE}
all_specs   = {s["key"]: s for s in CATALOGUE}

selected_key = st.selectbox(
    "Select indicator",
    options=all_keys,
    format_func=lambda k: all_labels[k],
    label_visibility="collapsed",
)

spec   = all_specs[selected_key]
series = get_series(spec)
s      = series.dropna()

if not s.empty:
    df_plot = s.reset_index()
    df_plot.columns = ["date", "value"]

    val_now, vdate = latest_valid(series)
    chg = mom_change(series)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Current", f"{fmt(val_now, spec['decimals'])} {spec['unit']}")
    with c2:
        yoy_val = s.pct_change(12).iloc[-1] * 100 if len(s) >= 13 else None
        st.metric("12M change", f"{fmt(yoy_val, 1)} pp" if yoy_val is not None else "—")
    with c3:
        s_24 = s.tail(24)
        st.metric("24M high", fmt(s_24.max(), spec["decimals"]))
    with c4:
        st.metric("24M low", fmt(s_24.min(), spec["decimals"]))

    chart = alt.Chart(df_plot).mark_line(
        color="#c8b87a", strokeWidth=1.8
    ).encode(
        x=alt.X("date:T", axis=alt.Axis(format="%Y", labelColor="#d0ccc4",
                                         tickColor="#2a2a2a", domainColor="#2a2a2a")),
        y=alt.Y("value:Q", axis=alt.Axis(labelColor="#d0ccc4", tickColor="#2a2a2a",
                                          domainColor="#2a2a2a", gridColor="#1a1a1a")),
        tooltip=[
            alt.Tooltip("date:T", title="Date", format="%b %Y"),
            alt.Tooltip("value:Q", title=spec["unit"], format=".2f"),
        ],
    ).properties(
        width=900, height=600,
        background="#0f0f0f",
    ).configure_view(stroke=None).configure_axis(
        labelFont="IBM Plex Mono", labelFontSize=9
    )

    st.altair_chart(chart, use_container_width=True)


# ─────────────────────────────────────────────
# RAW DATA TABLE (collapsible)
# ─────────────────────────────────────────────
with st.expander("Raw signal data (last 24 months)"):
    display_cols = [s["signal_col"] for s in CATALOGUE if s["signal_col"] in sig_df.columns]
    display_labels = {s["signal_col"]: s["label"] for s in CATALOGUE}
    df_show = sig_df[display_cols].tail(24).rename(columns=display_labels)
    st.dataframe(df_show.style.format("{:.2f}", na_rep="—"), use_container_width=True)


# ─────────────────────────────────────────────
# METHODOLOGY (collapsible)
# ─────────────────────────────────────────────
with st.expander("Methodology"):
    st.markdown("""
    **What this dashboard does**
    - Ingests UK macro series from FRED, ONS, and yfinance
    - Aligns all series to a monthly backbone (ffill for quarterly, mean for daily, last for monthly point-in-time)
    - Applies YoY % change where appropriate; levels kept for rates and spreads
    - Presents raw signal values — no composite scoring in this version
    - MoM delta is the change in the signal value from the prior month's reading

    **Series lag guide**
    - GDP: quarterly, released ~2 months after quarter end
    - CPI / Retail Sales: monthly, released ~3–4 weeks after month end
    - Bond yields / spreads: daily/monthly, near real-time
    - US credit spreads: daily via FRED, data begins 2023

    **Interpretation notes**
    - A rising yield curve (10Y − 3M > 0) suggests the market expects growth/inflation ahead
    - An inverted curve has historically preceded recessions by 6–18 months
    - Copper YoY is a leading indicator of global industrial demand ("Dr. Copper")
    - Real wage growth above CPI = purchasing power gains = consumption support

    **What this is not**
    - Not a forecasting model
    - Not investment advice
    - A disciplined, transparent data layer for macro interpretation
    """)


# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("""
<div style="margin-top:3rem; border-top:1px solid #1e1e1e; padding-top:1rem;">
    <span style="font-family:'IBM Plex Mono',monospace; font-size:0.65rem; color:#5a5a5a; letter-spacing:0.1em;">
    UK ECONOMIC PULSE &nbsp;·&nbsp; DATA: FRED / ONS / YFINANCE &nbsp;·&nbsp; FOR INFORMATIONAL PURPOSES ONLY
    </span>
</div>
""", unsafe_allow_html=True)
