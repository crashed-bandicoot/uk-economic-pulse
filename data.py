from __future__ import annotations

import io
import time

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from fredapi import Fred


# ── Streamlit-facing API ──────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def load_csvs(abs_path: str, sig_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    abs_df = pd.read_csv(abs_path, index_col=0, parse_dates=True)
    sig_df = pd.read_csv(sig_path, index_col=0, parse_dates=True)
    abs_df.index = pd.to_datetime(abs_df.index)
    sig_df.index = pd.to_datetime(sig_df.index)
    return abs_df, sig_df


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_live(api_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    abs_df = _fetch_abs(api_key)
    return abs_df, _build_signals(abs_df)


# ── Core fetch (no Streamlit dependency — used by __main__ too) ───────────────

def _fetch_abs(api_key: str) -> pd.DataFrame:
    fred = Fred(api_key=api_key)

    def ffill_monthly(s): return s.resample("ME").ffill()
    def mean_monthly(s):  return s.resample("ME").mean()
    def last_monthly(s):  return s.resample("ME").last()

    # ── FRED ──────────────────────────────────────────────────────────────────
    gdp          = ffill_monthly(fred.get_series("NGDPRSAXDCGBQ"))  # UK GDP (quarterly)
    gdp_us       = ffill_monthly(fred.get_series("GDPC1"))           # US GDP (quarterly)
    house_prices = ffill_monthly(fred.get_series("QGBR628BIS"))      # UK house prices (quarterly)
    uk10y        = last_monthly(fred.get_series("IRLTLT01GBM156N"))  # UK 10Y gilt
    uk3m         = last_monthly(fred.get_series("IR3TIB01GBM156N"))  # UK 3M rate
    hy_spread    = mean_monthly(fred.get_series("BAMLH0A0HYM2"))     # US HY credit spread
    twusd        = mean_monthly(fred.get_series("DTWEXBGS"))         # Trade-weighted USD
    oil          = mean_monthly(fred.get_series("DCOILBRENTEU"))     # Brent crude

    # ── ONS ───────────────────────────────────────────────────────────────────
    retail     = _fetch_ons_retail()
    cpi_raw    = get_uk_cpi_index_ons()
    wages_raw  = get_uk_nominal_wages_ons()
    cpi        = last_monthly(cpi_raw)
    real_wages = last_monthly(get_uk_real_wages(cpi_raw, wages_raw))
    unemp      = last_monthly(get_uk_unemployment_rate_ons())
    particip   = last_monthly(get_uk_labour_participation_rate_ons())

    # ── BoE ───────────────────────────────────────────────────────────────────
    policy_rate = make_policy_rate_monthly(get_boe_policy_rate())

    # ── yfinance ──────────────────────────────────────────────────────────────
    def yf_monthly(ticker: str, start: str = "2000-01-01") -> pd.Series:
        try:
            raw = yf.download(ticker, start=start, progress=False)
            s = raw["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.squeeze()
            s.index = pd.to_datetime(s.index)
            return s.resample("ME").mean()
        except Exception:
            return pd.Series(dtype=float)

    gold    = yf_monthly("GC=F")
    copper  = yf_monthly("HG=F")
    nat_gas = yf_monthly("NG=F")
    sox     = yf_monthly("^SOX")
    dxy     = yf_monthly("DX-Y.NYB")
    uranium = yf_monthly("URA", start="2009-01-01")  # Global X Uranium ETF

    return pd.DataFrame({
        # Economic Activity
        "gdp":               gdp,
        "gdp_us":            gdp_us,
        "house_prices":      house_prices,
        "retail_sales":      retail,
        # Labour Market
        "unemployment_rate": unemp,
        "participation_rate":particip,
        # Inflation
        "cpi":               cpi,
        "real_wages":        real_wages,
        # Financial Conditions
        "policy_rate":       policy_rate,
        "yield_uk_10y":      uk10y,
        "yield_uk_3m":       uk3m,
        "spread_us_hy":      hy_spread,
        "twusd":             twusd,
        # Commodities
        "oil":               oil,
        "gold":              gold,
        "copper":            copper,
        "nat_gas":           nat_gas,
        "uranium":           uranium,
        # Markets
        "sox":               sox,
        "dxy":               dxy,
    }).sort_index()


def _build_signals(abs_df: pd.DataFrame) -> pd.DataFrame:
    sig_df = pd.DataFrame(index=abs_df.index)
    yoy = lambda col: abs_df[col].pct_change(12, fill_method=None) * 100

    # Economic Activity
    sig_df["gdp_growth_yoy"]   = yoy("gdp")
    sig_df["gdp_us_yoy"]       = yoy("gdp_us")
    sig_df["house_prices_yoy"] = yoy("house_prices")
    sig_df["retail_sales_yoy"] = yoy("retail_sales")
    # Labour Market
    sig_df["unemployment_rate"]  = abs_df["unemployment_rate"]
    sig_df["participation_rate"] = abs_df["participation_rate"]
    # Inflation
    sig_df["cpi_yoy"]          = yoy("cpi")
    sig_df["real_wages_yoy"]   = yoy("real_wages")
    # Financial Conditions
    sig_df["policy_rate"]      = abs_df["policy_rate"]
    sig_df["yield_uk_10y"]     = abs_df["yield_uk_10y"]
    sig_df["uk_yield_curve"]   = abs_df["yield_uk_10y"] - abs_df["yield_uk_3m"]
    sig_df["spread_us_hy"]     = abs_df["spread_us_hy"]
    sig_df["twusd_yoy"]        = yoy("twusd")
    # Commodities
    sig_df["oil_yoy"]          = yoy("oil")
    sig_df["gold_yoy"]         = yoy("gold")
    sig_df["copper_yoy"]       = yoy("copper")
    sig_df["nat_gas_yoy"]      = yoy("nat_gas")
    sig_df["uranium_yoy"]      = yoy("uranium")
    # Markets
    sig_df["sox_yoy"]          = yoy("sox")
    sig_df["dxy_yoy"]          = yoy("dxy")

    return sig_df


# ── ONS helpers ───────────────────────────────────────────────────────────────

def _parse_ons_monthly_series_from_csv(url: str, series_name: str) -> pd.Series:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["raw_date", "raw_value"]
    monthly_mask = df["raw_date"].astype(str).str.match(r"^\d{4}\s[A-Z]{3}$", na=False)
    df = df.loc[monthly_mask].copy()
    df["raw_value"] = pd.to_numeric(df["raw_value"], errors="coerce")
    df = df.dropna(subset=["raw_value"])
    df["date"] = pd.to_datetime(df["raw_date"], format="%Y %b")
    return df.set_index("date")["raw_value"].sort_index().rename(series_name)


def get_uk_cpi_index_ons() -> pd.Series:
    """CPI INDEX 00: ALL ITEMS 2015=100 — ONS series D7BT (MM23)."""
    url = (
        "https://www.ons.gov.uk/generator?format=csv&uri="
        "/economy/inflationandpriceindices/timeseries/d7bt/mm23"
    )
    return _parse_ons_monthly_series_from_csv(url, "cpi_index")


def get_uk_nominal_wages_ons() -> pd.Series:
    """AWE Total Pay — ONS series KAB9 (LMS)."""
    url = (
        "https://www.ons.gov.uk/generator?format=csv&uri="
        "/employmentandlabourmarket/peopleinwork/earningsandworkinghours"
        "/timeseries/kab9/lms"
    )
    return _parse_ons_monthly_series_from_csv(url, "nominal_wage")


def get_uk_real_wages(cpi_index: pd.Series, wages: pd.Series) -> pd.Series:
    """Real wage index: nominal wages deflated by CPI (base = CPI 100)."""
    df = pd.concat([cpi_index, wages], axis=1).dropna()
    return (df["nominal_wage"] / df["cpi_index"] * 100).rename("real_wage")


def _fetch_ons_retail() -> pd.Series:
    """ONS Retail Sales Index (KPSA sheet)."""
    try:
        url = (
            "https://www.ons.gov.uk/file?uri=/businessindustryandtrade/retailindustry"
            "/datasets/retailsalesindexreferencetables/current/mainreferencetables.xlsx"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df = pd.read_excel(io.BytesIO(r.content), sheet_name="KPSA", header=6)
        time_col  = "Time Period"
        value_col = "All retailing including automotive fuel [note1]"
        df = df[[time_col, value_col]].dropna(subset=[time_col])
        mask = df[time_col].astype(str).str.contains("Revision", case=False, na=False)
        if mask.any():
            df = df[: mask.idxmax()]
        df[time_col] = pd.to_datetime(df[time_col].astype(str), format="%Y %b", errors="coerce")
        return df.dropna(subset=[time_col]).set_index(time_col)[value_col].sort_index().resample("ME").last()
    except Exception:
        return pd.Series(dtype=float)


def get_uk_unemployment_rate_ons() -> pd.Series:
    """UK unemployment rate, 16+, seasonally adjusted — ONS series MGSX (LMS)."""
    url = (
        "https://www.ons.gov.uk/generator?format=csv&uri="
        "/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms"
    )
    return _parse_ons_monthly_series_from_csv(url, "unemployment_rate")


def get_uk_labour_participation_rate_ons() -> pd.Series:
    """Labour participation proxied as 100 − economic inactivity rate — ONS series LF2S (LMS)."""
    url = (
        "https://www.ons.gov.uk/generator?format=csv&uri="
        "/employmentandlabourmarket/peoplenotinwork/economicinactivity/timeseries/lf2s/lms"
    )
    inactivity = _parse_ons_monthly_series_from_csv(url, "uk_economic_inactivity_rate")
    return (100 - inactivity).rename("participation_rate")


# ── BoE helpers ───────────────────────────────────────────────────────────────

def get_boe_policy_rate(local_fallback_path=None) -> pd.Series:
    """Bank Rate history scraped from the BoE database page."""
    url = "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp"
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://www.bankofengland.co.uk/boeapps/database/",
    })
    try:
        session.get("https://www.bankofengland.co.uk/boeapps/database/", timeout=30)
        time.sleep(1.0)
    except Exception:
        pass

    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        if not tables:
            raise ValueError("No tables found on Bank Rate page.")
        df = tables[0].copy()
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if "date_changed" not in df.columns or "rate" not in df.columns:
            raise ValueError(f"Unexpected columns: {list(df.columns)}")
        df["date_changed"] = pd.to_datetime(df["date_changed"], format="%d %b %y", errors="coerce")
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        return df.dropna(subset=["date_changed", "rate"]).sort_values("date_changed").set_index("date_changed")["rate"].rename("policy_rate")

    except requests.HTTPError as e:
        if local_fallback_path is None:
            raise RuntimeError(
                f"BoE request blocked ({e.response.status_code}). "
                "Download Bank Rate CSV manually and pass as local_fallback_path."
            ) from e
        raw = pd.read_csv(local_fallback_path)
        raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
        date_col = next((c for c in raw.columns if c in ["date_changed", "date"]), None)
        rate_col = next((c for c in raw.columns if c in ["rate", "value"]), None)
        if not date_col or not rate_col:
            raise ValueError(f"Cannot identify columns in fallback CSV: {list(raw.columns)}")
        df = raw[[date_col, rate_col]].copy()
        df.columns = ["date_changed", "rate"]
        df["date_changed"] = pd.to_datetime(df["date_changed"], errors="coerce", dayfirst=True)
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        return df.dropna(subset=["date_changed", "rate"]).sort_values("date_changed").set_index("date_changed")["rate"].rename("policy_rate")


def make_policy_rate_monthly(policy_rate_changes: pd.Series, end_date=None) -> pd.Series:
    """Forward-fill rate-change events onto a full monthly index."""
    monthly = policy_rate_changes.resample("ME").last()
    if end_date is None:
        end_date = pd.Timestamp.today().to_period("M").to_timestamp("M")
    full_index = pd.date_range(start=monthly.index.min(), end=end_date, freq="ME")
    return monthly.reindex(full_index).ffill().rename("policy_rate")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    from pathlib import Path

    api_key = os.environ.get("FRED_API_KEY") or ""
    if not api_key:
        raise SystemExit("FRED_API_KEY environment variable not set")

    print("Fetching data…")
    abs_df = _fetch_abs(api_key)
    sig_df = _build_signals(abs_df)

    out = Path("data/raw")
    out.mkdir(parents=True, exist_ok=True)
    abs_df.to_csv(out / "absolute_values.csv")
    sig_df.to_csv(out / "signals.csv")
    print(f"Saved to {out.resolve()}")
