# BLACKSWAN — Dataset Provenance, Licensing & Acquisition Guide

## 1. Primary Market Universe (Indian NSE)
BLACKSWAN sources historical daily OHLCV and split/dividend-adjusted closing prices (`adj_close`) for Indian indices and liquid NSE equities:

| Symbol | Yahoo Finance Ticker | Category | Notes |
| :--- | :--- | :--- | :--- |
| `NIFTY50` | `^NSEI` | Index | Reference NSE trading calendar & HMM market benchmark |
| `NIFTYBANK` | `^NSEBANK` | Sector Index | Banking & financials benchmark |
| `NIFTYIT` | `^CNXIT` | Sector Index | Indian IT services index |
| `NIFTYAUTO` | `^CNXAUTO` | Sector Index | Indian automotive sector index |
| `INDIAVIX` | `^INDIAVIX` | Volatility Index | Implied volatility indicator (excluded from portfolio weights) |
| `RELIANCE`, `HDFCBANK`, `ICICIBANK`, `INFY`, `TCS`, `LT`, `ITC`, `SBIN`, `BHARTIARTL`, `M&M` | `*.NS` | Liquid NSE Equities | Major Nifty 50 constituents |

## 2. Licensing & Redistribution Policy
- Yahoo Finance (`yfinance` / v8 chart API) data is retrieved at runtime for personal quantitative research and educational/internal risk analysis. Raw and processed CSV caches are stored under `data/raw/` and `data/processed/` (gitignored) and are **never committed** to the repository.
- If Yahoo Finance endpoints are temporarily rate-limited or unreachable, BLACKSWAN serves a previously validated raw cache only if present on disk and flags `stale_cache_fallback: true` in the manifest. It never fabricates observations.
- Alternative institutional ingestion: Drop clean NSE bhavcopy-derived CSV files with columns `date,open,high,low,close,adj_close,volume` into `data/raw/{SYMBOL}_raw.csv` alongside `{SYMBOL}_meta.json`.

## 3. Data Quality & Calendar Rules
- `backend/data/market_calendar.py` distinguishes Indian national and NSE exchange holidays from genuine missing observations.
- Missing asset returns are **never forward-filled**; multi-asset matrices use strict inner-join alignment across verified common trading sessions.
- Duplicate timestamps, non-positive effective prices, negative volumes, and >40% single-day log-return jumps are audited and logged in `data/manifest.json`.
