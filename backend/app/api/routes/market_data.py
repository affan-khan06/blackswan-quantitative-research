from __future__ import annotations

from datetime import date
from typing import Optional
from fastapi import APIRouter, Query

from backend.data.acquisition import DEFAULT_PORTFOLIO_ASSETS, get_universe_metadata
from backend.data.preprocessing import align_and_clean_universe
from backend.research.analytics import compute_asset_summary_metrics

router = APIRouter(prefix="/market-data", tags=["Market Data"])


@router.get("/universe")
def list_universe() -> dict:
    assets = [m.model_dump(mode="json") for m in get_universe_metadata()]
    return {
        "assets": assets,
        "default_portfolio_symbols": DEFAULT_PORTFOLIO_ASSETS,
    }


@router.get("/overview")
def get_market_overview(
    symbols: Optional[str] = Query(default=None, description="Comma-separated NSE symbols"),
    start_date: date = Query(default=date(2016, 1, 1)),
    force_refresh: bool = Query(default=False),
) -> dict:
    req_syms = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else ["NIFTY50", "NIFTYBANK", "NIFTYIT", "NIFTYAUTO", "INDIAVIX", "RELIANCE", "HDFCBANK", "INFY", "LT", "ITC"]
    )
    aligned_prices, simple_rets, _, quality_report = align_and_clean_universe(
        symbols=req_syms,
        start_date=start_date,
        force_refresh=force_refresh,
    )

    # Latest prices and summary metrics
    latest_prices = {
        col: round(float(aligned_prices[col].iloc[-1]), 2)
        for col in aligned_prices.columns
    }
    latest_date = aligned_prices.index.max().strftime("%Y-%m-%d")

    investable_cols = [c for c in simple_rets.columns if c != "INDIAVIX"]
    asset_metrics = compute_asset_summary_metrics(simple_rets[investable_cols])

    # Benchmark NIFTY50 normalized equity curve (base 100) for initial market overview
    nifty_series = []
    if "NIFTY50" in aligned_prices.columns:
        base_val = float(aligned_prices["NIFTY50"].iloc[0])
        for idx, val in aligned_prices["NIFTY50"].items():
            nifty_series.append(
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "price": round(float(val), 2),
                    "normalized": round(float(val / base_val * 100.0), 2),
                }
            )

    return {
        "latest_trading_date": latest_date,
        "latest_prices": latest_prices,
        "asset_metrics": asset_metrics,
        "benchmark_series": nifty_series,
        "data_quality_report": quality_report.model_dump(mode="json"),
    }
