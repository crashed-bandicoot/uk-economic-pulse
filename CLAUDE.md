# CLAUDE.md — UK Economic Pulse

## What this project is

A macro-economic monitoring system that answers: *what is going on with the UK economy?*

It pulls raw data from public APIs, transforms it into standardised signals across four pillars, combines them into a composite index (the Economic Pulse Index), and surfaces the result as a Streamlit dashboard.

---

## Contents

- Tech stack 
- Development commands
- Project structure
- Data sources
- Key data conventions
- The four pillars
- Notebook editing
- Git
- Code conventions
- What to avoid

## Project structure

```
notebooks/
  freeform/
    UK Economic Pulse.ipynb   ← main working notebook (active development)
    UK Economics App.ipynb    ← Streamlit dashboard prototype
  defined/
    01-data-pull.ipynb        ← scaffold: formalised data fetch
    02-cleaning.ipynb         ← scaffold: cleaning & resampling
    03-features.ipynb         ← scaffold: signal engineering
    04-composite-index.ipynb  ← scaffold: EPI construction

src/uk-economic-pulse/
  fetch.py                    ← data fetch functions (graduate from notebook)
  transform.py                ← resampling, cleaning
  features.py                 ← signal/z-score logic
  plots.py                    ← chart helpers
  config.py                   ← series config, weights
```

The `src/` files and `defined/` notebooks are currently empty scaffolds. The intended workflow (from the README) is:

> Discover in notebook → formalise in Python file → import back into notebook.

When a function in the freeform notebook is stable, move it into the appropriate `src/` module and import it back.

---

## Data sources

| Series | Source | Function |
|---|---|---|
| UK GDP (quarterly) | FRED (`NGDPRSAXDCGBQ`) | `fred.get_series()` |
| US GDP (quarterly) | FRED (`GDPC1`) | `fred.get_series()` |
| UK House Prices | FRED | `fred.get_series()` |
| Brent Crude Oil | FRED (`DCOILBRENTEU`) | `fred.get_series()` |
| UK CPI Index | ONS (MM23, series D7BT) | `get_uk_cpi_index_ons()` |
| UK Nominal Wages (AWE) | ONS (LMS, series KAB9) | `get_uk_nominal_wages_ons()` |
| Consumer Confidence | OECD MEI_CLI (CCI) | `get_uk_consumer_confidence_oecd()` |
| BoE Policy Rate | Bank of England website | `get_boe_policy_rate()` |
| UK Retail Sales | ONS Retail Sales Index | `get_uk_retail_sales_ons()` |

**FRED** requires an API key — set as `FRED_API_KEY` environment variable.

---

## Key data conventions

- All series are resampled to **month-end** before joining:
  - GDP: `resample("ME").ffill()` (quarterly → monthly, forward-filled)
  - Oil: `resample("ME").mean()` (daily → monthly average)
  - CPI, wages: `resample("ME").last()`
  - Policy rate, retail sales: already monthly, `.copy()`

- **Retail sales date format**: the index is a string in `dd-mm-yyyy` format (e.g. `'01-03-2024'`). Monthly data starts from January 1996. Source sheet is `KPSA` in the ONS reference tables xlsx, headers at row 7 (`header=6` in pandas).

- **Consumer confidence** returns a `pd.DataFrame` with one column per area: `GBR`, `G7`, `CHN`, `USA`.

- **Signals** are year-on-year percentage changes (or levels for policy rate/oil), then z-scored over a 36-month rolling window. Higher z-score = better for growth signals; CPI and policy rate signs are flipped so that *higher always means better for the economy*.

---

## The four pillars

| Pillar | Series |
|---|---|
| Economic Activity | GDP (UK), GDP (US), House Prices, Retail Sales |
| Inflation Pressure | CPI, Real Wages |
| Financial Conditions | Policy Rate |
| Commodity Prices | Oil |

Plots are produced as **four separate figures**, one per pillar.

---

## Notebook editing

The freeform notebook is edited directly as JSON via Python scripts (not the `NotebookEdit` tool), because the file exceeds the Read tool's token limit. The standard pattern:

```python
import json
path = 'notebooks/freeform/UK Economic Pulse.ipynb'
with open(path) as f:
    nb = json.load(f)
# find cell by id, modify cell['source'], clear cell['outputs']
with open(path, 'w') as f:
    json.dump(nb, f, indent=1)
```

Use `/Users/ornettematthews/anaconda3/bin/python3` — the system `python3` does not have `requests`, `pandas`, or `openpyxl`.

---

## Git

- Single branch: `main`
- Remote: `https://github.com/crashed-bandicoot/uk-economic-pulse.git`
- During a rebase conflict: `--theirs` = your local changes, `--ours` = upstream. This is the opposite of a merge.
