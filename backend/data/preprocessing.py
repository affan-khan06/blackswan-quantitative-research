from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.app.core.config import get_settings
from backend.app.core.exceptions import DataValidationError
from backend.data.acquisition import NSE_UNIVERSE, download_universe
from backend.data.market_calendar import build_nse_reference_calendar
from backend.data.schemas import AssetCategory, DataQualityReport, DatasetManifestEntry
from backend.data.validation import validate_raw_asset_frame


def compute_simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple arithmetic returns: R_t = P_t / P_{t-1} - 1."""
    return prices.pct_change().dropna(how="any")


def compute_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Logarithmic returns: r_t = ln(P_t / P_{t-1})."""
    return np.log(prices / prices.shift(1)).dropna(how="any")


def align_and_clean_universe(
    symbols: list[str],
    start_date: date = date(2015, 1, 1),
    end_date: Optional[date] = None,
    force_refresh: bool = False,
    data_dir: Optional[Path] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, DataQualityReport]:
    """
    Download, validate, and strictly align selected symbols on common NSE trading dates.
    Returns:
      - aligned_prices: DataFrame indexed by date with effective adjusted prices
      - simple_returns: DataFrame of simple returns (no forward filling)
      - log_returns: DataFrame of log returns (no forward filling)
      - quality_report: DataQualityReport with provenance and per-asset manifest entries
    """
    settings = get_settings()
    processed_dir = (data_dir / "processed") if data_dir else settings.processed_data_dir
    processed_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = (data_dir / "manifest.json") if data_dir else (settings.data_dir / "manifest.json")

    req_symbols = [s.upper() for s in symbols]
    # Always include NIFTY50 as reference calendar anchor if available
    fetch_symbols = list(dict.fromkeys(["NIFTY50", *req_symbols]))
    raw_frames, provenances = download_universe(
        symbols=fetch_symbols,
        start_date=start_date,
        end_date=end_date,
        force_refresh=force_refresh,
        data_dir=data_dir,
    )

    # Establish empirical NSE trading calendar from NIFTY50 sessions
    nifty_raw = raw_frames.get("NIFTY50")
    benchmark_dates = None
    if nifty_raw is not None and not nifty_raw.empty:
        benchmark_dates = pd.DatetimeIndex(
            pd.to_datetime(nifty_raw["date"]).dt.normalize().dropna().unique()
        ).sort_values()
    ref_cal = build_nse_reference_calendar(
        start_date=start_date,
        end_date=end_date or date.today(),
        benchmark_dates=benchmark_dates,
    )

    cleaned_series: dict[str, pd.Series] = {}
    manifest_entries: list[DatasetManifestEntry] = []
    warnings: list[str] = []

    for sym in req_symbols:
        cleaned_df, entry = validate_raw_asset_frame(
            sym,
            raw_frames[sym],
            provenances[sym],
            reference_calendar=ref_cal,
        )
        manifest_entries.append(entry)
        if cleaned_df.empty:
            raise DataValidationError(f"Asset {sym} produced no valid observations after validation.")
        cleaned_series[sym] = cleaned_df["effective_price"].rename(sym)
        if entry.validation_status != "VALIDATED":
            warnings.append(f"{sym}: {entry.validation_status} ({'; '.join(entry.notes)})")

    # Strict inner join on common trading dates (no forward filling!)
    aligned_prices = pd.concat(cleaned_series.values(), axis=1, join="inner").sort_index()
    if aligned_prices.empty or len(aligned_prices) < 30:
        raise DataValidationError(
            "Insufficient overlapping trading dates across selected assets after strict alignment.",
            details={"aligned_rows": int(len(aligned_prices)), "symbols": req_symbols},
        )

    simple_returns = compute_simple_returns(aligned_prices)
    log_returns = compute_log_returns(aligned_prices)

    # Persist cleaned processed artifacts separately from raw cache
    aligned_prices.to_csv(processed_dir / "aligned_prices.csv")
    simple_returns.to_csv(processed_dir / "simple_returns.csv")
    log_returns.to_csv(processed_dir / "log_returns.csv")

    report = DataQualityReport(
        generated_at=datetime.now(timezone.utc),
        common_start_date=aligned_prices.index.min().date(),
        common_end_date=aligned_prices.index.max().date(),
        aligned_trading_days=int(len(aligned_prices)),
        assets=manifest_entries,
        warnings=warnings,
    )
    manifest_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return aligned_prices, simple_returns, log_returns, report


def get_investable_symbols() -> list[str]:
    return [
        sym
        for sym, meta in NSE_UNIVERSE.items()
        if meta.category != AssetCategory.VOLATILITY_INDEX
    ]
