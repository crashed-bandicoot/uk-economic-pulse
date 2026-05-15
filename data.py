from __future__ import annotations

import io

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from fredapi import Fred


@st.cache_data(show_spinner=False, ttl=3600)
def load_csvs(abs_path: str, sig_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    abs_df = pd.read_csv(abs_path, index_col=0, parse_dates=True)
    sig_df = pd.read_csv(sig_path, index_col=0, parse_dates=True)
    abs_df.index = pd.to_datetime(abs_df.index)
    sig_df.index = pd.to_datetime(sig_df.index)
    return abs_df, sig_df


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_live_fred(api_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    fred = Fred(api_key=api_key)

    def ffill_monthly(s): return s.resample("ME").ffill()
    def mean_monthly(s):  return s.resample("ME").mean()
    def last_monthly(s):  return s.resample("ME").last()

    gdp          = ffill_monthly(fred.get_series("NGDPRSAXDCGBQ"))
    house_prices = ffill_monthly(fred.get_series("QGBR628BIS"))
    cpi          = last_monthly(fred.get_series("GBRCPIALLMINMEI"))
    policy_rate  = last_monthly(fred.get_series("BOESRPPACBIS"))
    uk10y        = last_monthly(fred.get_series("IRLTLT01GBM156N"))
    uk3m         = last_monthly(fred.get_series("IR3TIB01GBM156N"))
    real_wages   = last_monthly(fred.get_series("LCEAMN01GBM661S"))
    unemp        = last_monthly(fred.get_series("LRUNTTTTGBM156S"))
    particip     = ffill_monthly(fred.get_series("LFAC64TTGBQ647S"))
    oil          = mean_monthly(fred.get_series("DCOILBRENTEU"))
    hy_spread    = mean_monthly(fred.get_series("BAMLH0A0HYM2"))
    twusd        = mean_monthly(fred.get_series("DTWEXBGS"))  # noqa: F841

    retail = _fetch_ons_retail()

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

    abs_df = pd.DataFrame({
        "gdp":               gdp,
        "house_prices":      house_prices,
        "retail_sales":      retail,
        "cpi":               cpi,
        "real_wages":        real_wages,
        "policy_rate":       policy_rate,
        "yield_uk_10y":      uk10y,
        "yield_uk_3m":       uk3m,
        "spread_us_hy":      hy_spread,
        "oil":               oil,
        "gold":              gold,
        "copper":            copper,
        "nat_gas":           nat_gas,
        "sox":               sox,
        "dxy":               dxy,
        "unemployment_rate": unemp,
        "participation_rate":particip,
    }).sort_index()

    sig_df = _build_signals(abs_df)
    return abs_df, sig_df


def _fetch_ons_retail() -> pd.Series:
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
        df = df.dropna(subset=[time_col]).set_index(time_col)[value_col].sort_index()
        return df.resample("ME").last()
    except Exception:
        return pd.Series(dtype=float)


def _build_signals(abs_df: pd.DataFrame) -> pd.DataFrame:
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
    return sig_df


if __name__ == "__main__":
    import os
    from pathlib import Path

    api_key = os.environ.get("FRED_API_KEY") or ""
    if not api_key:
        raise SystemExit("FRED_API_KEY environment variable not set")

    print("Fetching data...")
    fred = Fred(api_key=api_key)

    def ffill_monthly(s): return s.resample("ME").ffill()
    def mean_monthly(s):  return s.resample("ME").mean()
    def last_monthly(s):  return s.resample("ME").last()

    gdp          = ffill_monthly(fred.get_series("NGDPRSAXDCGBQ"))
    house_prices = ffill_monthly(fred.get_series("QGBR628BIS"))
    cpi          = last_monthly(fred.get_series("GBRCPIALLMINMEI"))
    policy_rate  = last_monthly(fred.get_series("BOESRPPACBIS"))
    uk10y        = last_monthly(fred.get_series("IRLTLT01GBM156N"))
    uk3m         = last_monthly(fred.get_series("IR3TIB01GBM156N"))
    real_wages   = last_monthly(fred.get_series("LCEAMN01GBM661S"))
    unemp        = last_monthly(fred.get_series("LRUNTTTTGBM156S"))
    particip     = ffill_monthly(fred.get_series("LFAC64TTGBQ647S"))
    oil          = mean_monthly(fred.get_series("DCOILBRENTEU"))
    hy_spread    = mean_monthly(fred.get_series("BAMLH0A0HYM2"))

    retail = _fetch_ons_retail()

    def yf_monthly(ticker, start="2000-01-01"):
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

    abs_df = pd.DataFrame({
        "gdp": gdp, "house_prices": house_prices, "retail_sales": retail,
        "cpi": cpi, "real_wages": real_wages, "policy_rate": policy_rate,
        "yield_uk_10y": uk10y, "yield_uk_3m": uk3m, "spread_us_hy": hy_spread,
        "oil": oil, "gold": gold, "copper": copper, "nat_gas": nat_gas,
        "sox": sox, "dxy": dxy, "unemployment_rate": unemp,
        "participation_rate": particip,
    }).sort_index()
    sig_df = _build_signals(abs_df)

    out = Path("data/raw")
    out.mkdir(parents=True, exist_ok=True)
    abs_df.to_csv(out / "absolute_values.csv")
    sig_df.to_csv(out / "signals.csv")
    print(f"Saved to {out.resolve()}")
