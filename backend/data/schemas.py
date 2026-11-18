from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AssetCategory(str, Enum):
    INDEX = "INDEX"
    SECTOR_INDEX = "SECTOR_INDEX"
    VOLATILITY_INDEX = "VOLATILITY_INDEX"
    EQUITY = "EQUITY"


class AssetMetadata(BaseModel):
    symbol: str
    yahoo_ticker: str
    name: str
    exchange: str = "NSE"
    currency: str = "INR"
    category: AssetCategory
    sector: str
    description: str


class DatasetManifestEntry(BaseModel):
    symbol: str
    yahoo_ticker: str
    name: str
    exchange: str
    category: AssetCategory
    sector: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    observation_count: int = 0
    expected_trading_days: int = 0
    missing_observations: int = 0
    missing_observation_pct: float = 0.0
    duplicate_timestamps: int = 0
    non_positive_prices: int = 0
    negative_volumes: int = 0
    extreme_jump_flags: int = 0
    data_source: str = "Yahoo Finance (yfinance v8 / chart)"
    retrieved_at: datetime
    validation_status: str
    notes: list[str] = Field(default_factory=list)


class DataQualityReport(BaseModel):
    generated_at: datetime
    common_start_date: Optional[date] = None
    common_end_date: Optional[date] = None
    aligned_trading_days: int = 0
    assets: list[DatasetManifestEntry]
    alignment_policy: str = (
        "Strict inner-join alignment on verified NSE trading sessions where all selected "
        "return-series assets have valid observations; missing returns are never forward-filled."
    )
    warnings: list[str] = Field(default_factory=list)
