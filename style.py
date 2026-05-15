from __future__ import annotations

CSS = """
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
    color: #5a5a5a;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 0.4rem;
}
.masthead-date {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #5a5a5a;
    text-align: right;
}

/* Section labels */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #5a5a5a;
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

/* Data freshness badges */
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
"""

FOOTER_HTML = """
<div style="margin-top:3rem; border-top:1px solid #1e1e1e; padding-top:1rem;">
    <span style="font-family:'IBM Plex Mono',monospace; font-size:0.65rem; color:#5a5a5a; letter-spacing:0.1em;">
    UK ECONOMIC PULSE &nbsp;·&nbsp; DATA: FRED / ONS / YFINANCE &nbsp;·&nbsp; FOR INFORMATIONAL PURPOSES ONLY
    </span>
</div>
"""

METHODOLOGY_MD = """
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
"""


def masthead_html(today_str: str) -> tuple[str, str]:
    left = f"""
    <div class="masthead">
        <div class="masthead-title">UK ECONOMIC PULSE</div>
        <div class="masthead-sub">Macro Intelligence Dashboard &nbsp;·&nbsp; Data: FRED / ONS / yfinance</div>
    </div>
    """
    right = f"""
    <div style="text-align:right; padding-top:1.6rem;">
        <div class="masthead-date">{today_str}</div>
    </div>
    """
    return left, right
