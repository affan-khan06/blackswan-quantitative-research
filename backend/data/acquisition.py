from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
import yfinance as yf

from backend.app.core.config import get_settings
from backend.app.core.exceptions import DataAcquisitionError
from backend.app.core.logging import logger
from backend.data.schemas import AssetCategory, AssetMetadata

# Curated NSE Primary Universe
NSE_UNIVERSE: dict[str, AssetMetadata] = {
    "NIFTY50": AssetMetadata(
        symbol="NIFTY50",
        yahoo_ticker="^NSEI",
        name="NIFTY 50 Index",
        category=AssetCategory.INDEX,
        sector="Broad Market",
        description="Benchmark index of the 50 largest and most liquid Indian NSE equities.",
    ),
    "NIFTYBANK": AssetMetadata(
        symbol="NIFTYBANK",
        yahoo_ticker="^NSEBANK",
        name="NIFTY Bank Index",
        category=AssetCategory.SECTOR_INDEX,
        sector="Financials",
        description="Index tracking the most liquid and large-cap Indian banking stocks on NSE.",
    ),
    "NIFTYIT": AssetMetadata(
        symbol="NIFTYIT",
        yahoo_ticker="^CNXIT",
        name="NIFTY IT Index",
        category=AssetCategory.SECTOR_INDEX,
        sector="Information Technology",
        description="Index capturing the performance of major Indian IT services exporters.",
    ),
    "NIFTYAUTO": AssetMetadata(
        symbol="NIFTYAUTO",
        yahoo_ticker="^CNXAUTO",
        name="NIFTY Auto Index",
        category=AssetCategory.SECTOR_INDEX,
        sector="Automobiles",
        description="Index representing the Indian automotive and auto-ancillary sector.",
    ),
    "INDIAVIX": AssetMetadata(
        symbol="INDIAVIX",
        yahoo_ticker="^INDIAVIX",
        name="India VIX",
        category=AssetCategory.VOLATILITY_INDEX,
        sector="Volatility",
        description="Implied 30-day volatility index derived from NIFTY 50 option order books.",
    ),
    "RELIANCE": AssetMetadata(
        symbol="RELIANCE",
        yahoo_ticker="RELIANCE.NS",
        name="Reliance Industries Ltd",
        category=AssetCategory.EQUITY,
        sector="Energy & Telecom",
        description="Conglomerate spanning refining, petrochemicals, Jio telecom, and retail.",
    ),
    "HDFCBANK": AssetMetadata(
        symbol="HDFCBANK",
        yahoo_ticker="HDFCBANK.NS",
        name="HDFC Bank Ltd",
        category=AssetCategory.EQUITY,
        sector="Financials",
        description="India's largest private sector bank by assets and market capitalization.",
    ),
    "ICICIBANK": AssetMetadata(
        symbol="ICICIBANK",
        yahoo_ticker="ICICIBANK.NS",
        name="ICICI Bank Ltd",
        category=AssetCategory.EQUITY,
        sector="Financials",
        description="Major Indian private sector retail and corporate banking institution.",
    ),
    "INFY": AssetMetadata(
        symbol="INFY",
        yahoo_ticker="INFY.NS",
        name="Infosys Ltd",
        category=AssetCategory.EQUITY,
        sector="Information Technology",
        description="Global IT consulting and digital services leader listed on NSE.",
    ),
    "TCS": AssetMetadata(
        symbol="TCS",
        yahoo_ticker="TCS.NS",
        name="Tata Consultancy Services Ltd",
        category=AssetCategory.EQUITY,
        sector="Information Technology",
        description="India's largest IT services and enterprise technology consultancy.",
    ),
    "LT": AssetMetadata(
        symbol="LT",
        yahoo_ticker="LT.NS",
        name="Larsen & Toubro Ltd",
        category=AssetCategory.EQUITY,
        sector="Infrastructure & Industrials",
        description="Engineering, EPC construction, defense, and capital goods bellwether.",
    ),
    "ITC": AssetMetadata(
        symbol="ITC",
        yahoo_ticker="ITC.NS",
        name="ITC Ltd",
        category=AssetCategory.EQUITY,
        sector="Consumer Staples",
        description="Diversified FMCG, agribusiness, paperboards, and hospitality enterprise.",
    ),
    "SBIN": AssetMetadata(
        symbol="SBIN",
        yahoo_ticker="SBIN.NS",
        name="State Bank of India",
        category=AssetCategory.EQUITY,
        sector="Financials",
        description="India's largest public sector commercial bank.",
    ),
    "BHARTIARTL": AssetMetadata(
        symbol="BHARTIARTL",
        yahoo_ticker="BHARTIARTL.NS",
        name="Bharti Airtel Ltd",
        category=AssetCategory.EQUITY,
        sector="Telecom",
        description="Leading Indian and pan-African telecommunications operator.",
    ),
    "M&M": AssetMetadata(
        symbol="M&M",
        yahoo_ticker="M&M.NS",
        name="Mahindra & Mahindra Ltd",
        category=AssetCategory.EQUITY,
        sector="Automobiles",
        description="Leading Indian SUV, commercial vehicle, and farm equipment manufacturer.",
    ),
}

DEFAULT_PORTFOLIO_ASSETS = ["NIFTY50", "RELIANCE", "HDFCBANK", "INFY", "LT", "ITC"]


def get_universe_metadata() -> list[AssetMetadata]:
    return list(NSE_UNIVERSE.values())


def get_asset_metadata(symbol: str) -> AssetMetadata:
    key = symbol.upper()
    if key not in NSE_UNIVERSE:
        raise DataAcquisitionError(
            f"Unsupported asset symbol '{symbol}'. Choose from the verified NSE universe.",
            details={"supported_symbols": list(NSE_UNIVERSE.keys())},
        )
    return NSE_UNIVERSE[key]


def _raw_cache_path(symbol: str, data_dir: Optional[Path] = None) -> Path:
    settings = get_settings()
    base = data_dir / "raw" if data_dir else settings.raw_data_dir
    base.mkdir(parents=True, exist_ok=True)
    safe_sym = symbol.replace("&", "_AND_")
    return base / f"{safe_sym}_raw.csv"


def _raw_meta_path(symbol: str, data_dir: Optional[Path] = None) -> Path:
    settings = get_settings()
    base = data_dir / "raw" if data_dir else settings.raw_data_dir
    base.mkdir(parents=True, exist_ok=True)
    safe_sym = symbol.replace("&", "_AND_")
    return base / f"{safe_sym}_meta.json"


def _fetch_via_yahoo_chart_api(
    yahoo_ticker: str, start_date: date, end_date: date
) -> pd.DataFrame:
    """
    Direct Yahoo Finance v8 chart endpoint downloader preserving adjclose and OHLCV.
    """
    p1 = int(datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc).timestamp())
    encoded_ticker = httpx.URL(f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}")
    params = {
        "period1": str(p1),
        "period2": str(p2),
        "interval": "1d",
        "includeAdjustedClose": "true",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(str(encoded_ticker), params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise DataAcquisitionError(f"Yahoo chart API error for {yahoo_ticker}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise DataAcquisitionError(f"Empty Yahoo chart API result for {yahoo_ticker}")

    res = results[0]
    timestamps = res.get("timestamp") or []
    indicators = res.get("indicators", {})
    quote = (indicators.get("quote") or [{}])[0]
    adj_list = (indicators.get("adjclose") or [{}])[0].get("adjclose")

    if not timestamps:
        raise DataAcquisitionError(f"No timestamps returned for {yahoo_ticker}")

    dates = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("Asia/Kolkata").normalize().tz_localize(None)
    df = pd.DataFrame(
        {
            "date": dates,
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("close"),
            "adj_close": adj_list if adj_list is not None else quote.get("close"),
            "volume": quote.get("volume"),
        }
    )
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def _fetch_via_yfinance(yahoo_ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
    ticker = yf.Ticker(yahoo_ticker)
    hist = ticker.history(
        start=start_date.isoformat(),
        end=(pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
        actions=True,
    )
    if hist is None or hist.empty:
        raise DataAcquisitionError(f"yfinance returned empty history for {yahoo_ticker}")

    hist = hist.reset_index()
    date_col = "Date" if "Date" in hist.columns else hist.columns[0]
    dt_series = pd.to_datetime(hist[date_col])
    if dt_series.dt.tz is not None:
        dt_series = dt_series.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)

    df = pd.DataFrame(
        {
            "date": dt_series.dt.strftime("%Y-%m-%d"),
            "open": hist.get("Open"),
            "high": hist.get("High"),
            "low": hist.get("Low"),
            "close": hist.get("Close"),
            "adj_close": hist.get("Adj Close", hist.get("Close")),
            "volume": hist.get("Volume", 0),
        }
    )
    return df


def download_asset_history(
    symbol: str,
    start_date: date = date(2015, 1, 1),
    end_date: Optional[date] = None,
    force_refresh: bool = False,
    cache_ttl_hours: int = 12,
    data_dir: Optional[Path] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Acquire real historical OHLCV data for a supported NSE symbol.
    Caches raw data under data/raw/ with retrieval timestamp and provenance metadata.
    Never fabricates data if remote sources are unavailable.
    """
    meta = get_asset_metadata(symbol)
    effective_end = end_date or date.today()
    raw_path = _raw_cache_path(meta.symbol, data_dir=data_dir)
    meta_path = _raw_meta_path(meta.symbol, data_dir=data_dir)

    if not force_refresh and raw_path.exists() and meta_path.exists():
        try:
            cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            retrieved_at = datetime.fromisoformat(cached_meta["retrieved_at"])
            age_hours = (datetime.now(timezone.utc) - retrieved_at).total_seconds() / 3600.0
            cached_start = date.fromisoformat(cached_meta.get("requested_start", start_date.isoformat()))
            cached_end = date.fromisoformat(cached_meta.get("requested_end", effective_end.isoformat()))
            if age_hours <= cache_ttl_hours and cached_start <= start_date and cached_end >= effective_end - pd.Timedelta(days=3):
                df = pd.read_csv(raw_path)
                df = df[(df["date"] >= start_date.isoformat()) & (df["date"] <= effective_end.isoformat())].copy()
                if not df.empty:
                    return df, cached_meta
        except Exception as exc:
            logger.warning(f"Raw cache read fallback for {meta.symbol}: {exc}")

    last_error: Optional[Exception] = None
    df: Optional[pd.DataFrame] = None
    source_used = "Yahoo Finance v8 Chart API"

    # Try direct v8 chart API first (fast, reliable, preserves adjclose), then yfinance
    for attempt in range(2):
        try:
            df = _fetch_via_yahoo_chart_api(meta.yahoo_ticker, start_date, effective_end)
            source_used = "Yahoo Finance v8 Chart API"
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))

    if df is None or df.empty:
        try:
            df = _fetch_via_yfinance(meta.yahoo_ticker, start_date, effective_end)
            source_used = "yfinance Python Client"
        except Exception as exc:
            last_error = exc

    if df is None or df.empty:
        # If stale raw cache exists, use it ONLY if it exists on disk and disclose cache age honestly
        if raw_path.exists() and meta_path.exists():
            cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            cached_meta["stale_cache_fallback"] = True
            cached_meta["fallback_reason"] = str(last_error)
            df_cached = pd.read_csv(raw_path)
            logger.warning(
                f"Live acquisition failed for {meta.symbol}; serving verified local raw cache.",
                extra={"extra_data": {"symbol": meta.symbol, "error": str(last_error)}},
            )
            return df_cached, cached_meta
        raise DataAcquisitionError(
            f"Unable to download historical data for {meta.symbol} ({meta.yahoo_ticker}) "
            f"and no local cache exists. Upstream error: {last_error}",
            details={"symbol": meta.symbol, "yahoo_ticker": meta.yahoo_ticker},
        )

    # Persist raw untouched snapshot separately from cleaned data
    df.to_csv(raw_path, index=False)
    provenance = {
        "symbol": meta.symbol,
        "yahoo_ticker": meta.yahoo_ticker,
        "exchange": meta.exchange,
        "data_source": source_used,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "requested_start": start_date.isoformat(),
        "requested_end": effective_end.isoformat(),
        "raw_rows": int(len(df)),
        "stale_cache_fallback": False,
    }
    meta_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    logger.info(
        f"Acquired raw market history for {meta.symbol}",
        extra={"extra_data": {"symbol": meta.symbol, "rows": len(df), "source": source_used}},
    )
    return df, provenance


def download_universe(
    symbols: Optional[list[str]] = None,
    start_date: date = date(2015, 1, 1),
    end_date: Optional[date] = None,
    force_refresh: bool = False,
    data_dir: Optional[Path] = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    target_symbols = symbols or list(NSE_UNIVERSE.keys())
    frames: dict[str, pd.DataFrame] = {}
    provenances: dict[str, dict] = {}
    for sym in target_symbols:
        df, prov = download_asset_history(
            sym,
            start_date=start_date,
            end_date=end_date,
            force_refresh=force_refresh,
            data_dir=data_dir,
        )
        frames[sym.upper()] = df
        provenances[sym.upper()] = prov
    return frames, provenances
