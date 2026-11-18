from __future__ import annotations

from datetime import datetime, timezone
import numpy as np
import pandas as pd

from backend.app.core.exceptions import DataValidationError
from backend.data.acquisition import get_asset_metadata
from backend.data.market_calendar import build_nse_reference_calendar
from backend.data.schemas import AssetCategory, DatasetManifestEntry


def validate_raw_asset_frame(
    symbol: str,
    df: pd.DataFrame,
    provenance: dict,
    reference_calendar: pd.DatetimeIndex | None = None,
    raise_on_fatal: bool = False,
) -> tuple[pd.DataFrame, DatasetManifestEntry]:
    """
    Validate raw OHLCV data for integrity:
    - Duplicate timestamps
    - Non-positive prices (close / adj_close <= 0 or NaN)
    - Negative volumes
    - Extreme single-day jumps (> 40% abs log return) for corporate-action audit
    - Missing observations relative to NSE reference trading calendar
    Never fabricates or forward-fills returns.
    """
    meta = get_asset_metadata(symbol)
    notes: list[str] = []

    if df.empty:
        if raise_on_fatal:
            raise DataValidationError(f"Asset {symbol} has zero observations.")
        entry = DatasetManifestEntry(
            symbol=meta.symbol,
            yahoo_ticker=meta.yahoo_ticker,
            name=meta.name,
            exchange=meta.exchange,
            category=meta.category,
            sector=meta.sector,
            retrieved_at=datetime.fromisoformat(provenance["retrieved_at"]),
            data_source=provenance.get("data_source", "Yahoo Finance"),
            validation_status="FAILED_EMPTY",
            notes=["Zero observations returned by data provider."],
        )
        return df.copy(), entry

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    work = work.sort_values("date")

    duplicate_count = int(work["date"].duplicated().sum())
    if duplicate_count > 0:
        notes.append(f"Removed {duplicate_count} duplicate timestamp(s) keeping last valid quote.")
        work = work.drop_duplicates(subset=["date"], keep="last")

    # Identify price column (prefer adj_close for corporate action continuity)
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    price_series = work["adj_close"].where(work["adj_close"].notna(), work["close"])
    work["effective_price"] = price_series

    non_positive_mask = work["effective_price"].isna() | (work["effective_price"] <= 0)
    non_positive_count = int(non_positive_mask.sum())
    if non_positive_count > 0:
        notes.append(f"Excluded {non_positive_count} row(s) with missing or non-positive effective_price.")
        work = work[~non_positive_mask].copy()

    if "volume" in work.columns:
        neg_vol_mask = work["volume"].notna() & (work["volume"] < 0)
        negative_volumes = int(neg_vol_mask.sum())
        if negative_volumes > 0:
            notes.append(f"Detected {negative_volumes} negative volume row(s); coerced to NaN.")
            work.loc[neg_vol_mask, "volume"] = np.nan
    else:
        negative_volumes = 0

    if work.empty:
        if raise_on_fatal:
            raise DataValidationError(f"Asset {symbol} has no valid positive price rows after cleaning.")
        entry = DatasetManifestEntry(
            symbol=meta.symbol,
            yahoo_ticker=meta.yahoo_ticker,
            name=meta.name,
            exchange=meta.exchange,
            category=meta.category,
            sector=meta.sector,
            retrieved_at=datetime.fromisoformat(provenance["retrieved_at"]),
            data_source=provenance.get("data_source", "Yahoo Finance"),
            validation_status="FAILED_INVALID_PRICES",
            duplicate_timestamps=duplicate_count,
            non_positive_prices=non_positive_count,
            negative_volumes=negative_volumes,
            notes=notes,
        )
        return work, entry

    # Extreme jump audit (flag >40% single-day move for review; do not alter real crashes or splits silently)
    log_rets = np.log(work["effective_price"] / work["effective_price"].shift(1)).dropna()
    extreme_jump_flags = int((log_rets.abs() > 0.40).sum())
    if extreme_jump_flags > 0:
        notes.append(
            f"Flagged {extreme_jump_flags} session(s) with |log_return| > 40% (audit for unadjusted splits/outliers)."
        )

    start_dt = work["date"].min().date()
    end_dt = work["date"].max().date()
    cal = (
        reference_calendar[(reference_calendar >= work["date"].min()) & (reference_calendar <= work["date"].max())]
        if reference_calendar is not None and len(reference_calendar) > 0
        else build_nse_reference_calendar(start_dt, end_dt)
    )
    expected_days = max(int(len(cal)), int(len(work)))
    observed_set = set(work["date"].dt.normalize())
    missing_dates = [d for d in cal if d not in observed_set]
    missing_count = len(missing_dates)
    missing_pct = round((missing_count / expected_days) * 100.0, 3) if expected_days > 0 else 0.0

    if missing_count > 0:
        notes.append(
            f"{missing_count} missing session(s) ({missing_pct:.2f}%) vs NSE reference calendar; left uninterpolated."
        )
    if provenance.get("stale_cache_fallback"):
        notes.append(f"Served from cached raw snapshot due to upstream error: {provenance.get('fallback_reason')}")

    if meta.category == AssetCategory.VOLATILITY_INDEX:
        notes.append("Volatility index series (INDIA VIX); treated as state indicator, not investable asset.")

    status = "VALIDATED"
    if missing_pct > 5.0 or non_positive_count > 10:
        status = "VALIDATED_WITH_WARNINGS"

    entry = DatasetManifestEntry(
        symbol=meta.symbol,
        yahoo_ticker=meta.yahoo_ticker,
        name=meta.name,
        exchange=meta.exchange,
        category=meta.category,
        sector=meta.sector,
        start_date=start_dt,
        end_date=end_dt,
        observation_count=int(len(work)),
        expected_trading_days=expected_days,
        missing_observations=missing_count,
        missing_observation_pct=missing_pct,
        duplicate_timestamps=duplicate_count,
        non_positive_prices=non_positive_count,
        negative_volumes=negative_volumes,
        extreme_jump_flags=extreme_jump_flags,
        data_source=provenance.get("data_source", "Yahoo Finance"),
        retrieved_at=datetime.fromisoformat(provenance["retrieved_at"]),
        validation_status=status,
        notes=notes,
    )
    work = work.set_index("date").sort_index()
    return work, entry
