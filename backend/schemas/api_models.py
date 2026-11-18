from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.simulation.base import RebalanceMode, SimulationMethod
from backend.stress.hypothetical import HypotheticalScenarioType


class PortfolioAllocation(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=24)
    weight: float = Field(..., gt=0.0, le=1.0)


class PortfolioBaseRequest(BaseModel):
    allocations: list[PortfolioAllocation] = Field(..., min_length=1, max_length=15)
    start_date: date = Field(default=date(2016, 1, 1))
    end_date: Optional[date] = None
    initial_capital: float = Field(default=1_000_000.0, ge=10_000.0, le=1_000_000_000.0)
    risk_free_rate: float = Field(default=0.065, ge=0.0, le=0.25)

    @field_validator("allocations")
    @classmethod
    def check_unique_symbols(cls, v: list[PortfolioAllocation]) -> list[PortfolioAllocation]:
        seen: set[str] = set()
        for item in v:
            sym = item.symbol.upper()
            if sym in seen:
                raise ValueError(f"Duplicate portfolio symbol '{sym}'.")
            if sym == "INDIAVIX":
                raise ValueError("INDIAVIX is a volatility index indicator and cannot hold portfolio weight.")
            seen.add(sym)
        return v

    @model_validator(mode="after")
    def check_weights_and_dates(self) -> "PortfolioBaseRequest":
        total_w = sum(a.weight for a in self.allocations)
        if abs(total_w - 1.0) > 1e-3:
            raise ValueError(
                f"Portfolio weights must sum to 1.000 (100%); received {total_w:.6f}."
            )
        if self.end_date and self.end_date <= self.start_date:
            raise ValueError("end_date must be strictly after start_date.")
        return self


class SimulationRequest(PortfolioBaseRequest):
    name: str = Field(default="NSE Portfolio Risk Run", min_length=2, max_length=120)
    simulation_method: SimulationMethod = SimulationMethod.REGIME_SWITCHING_MC
    n_paths: int = Field(default=2000, ge=200, le=20000)
    horizon_days: int = Field(default=63, ge=5, le=252)
    confidence_level: float = Field(default=0.95)
    random_seed: int = Field(default=42, ge=0, le=2_147_483_647)
    rebalancing: RebalanceMode = RebalanceMode.DAILY
    transaction_cost_bps: float = Field(default=0.0, ge=0.0, le=100.0)
    block_length: int = Field(default=10, ge=2, le=63)
    crisis_correlation_stress: bool = False
    crisis_stress_blend: float = Field(default=0.55, ge=0.0, le=1.0)
    crisis_target_corr: float = Field(default=0.85, ge=0.1, le=0.99)
    loss_threshold_pct: float = Field(default=0.10, gt=0.0, lt=1.0)
    run_method_comparison: bool = True

    @field_validator("confidence_level")
    @classmethod
    def check_confidence_level(cls, v: float) -> float:
        if round(v, 4) not in (0.90, 0.95, 0.99):
            raise ValueError("confidence_level must be 0.90, 0.95, or 0.99.")
        return v


class HistoricalStressRequest(PortfolioBaseRequest):
    event_id: str = Field(..., min_length=2, max_length=64)
    random_seed: int = Field(default=42, ge=0, le=2_147_483_647)


class HypotheticalStressRequest(PortfolioBaseRequest):
    scenario_type: HypotheticalScenarioType
    shock_magnitude_pct: float = Field(default=-0.15, ge=-0.80, le=0.50)
    target_sector: str = Field(default="Financials")
    volatility_multiplier: float = Field(default=2.0, ge=0.5, le=6.0)
    target_crisis_corr: float = Field(default=0.88, ge=0.1, le=0.99)
    horizon_days: int = Field(default=21, ge=5, le=126)
    n_paths: int = Field(default=2000, ge=200, le=10000)
    random_seed: int = Field(default=42, ge=0, le=2_147_483_647)


class BacktestRequest(PortfolioBaseRequest):
    confidence_level: float = Field(default=0.95)
    window_size: int = Field(default=252, ge=126, le=756)
    oos_sessions: int = Field(default=250, ge=60, le=750)
    mc_draws_per_step: int = Field(default=800, ge=200, le=5000)
    random_seed: int = Field(default=42, ge=0, le=2_147_483_647)

    @field_validator("confidence_level")
    @classmethod
    def check_bt_confidence(cls, v: float) -> float:
        if round(v, 4) not in (0.95, 0.99):
            raise ValueError("Backtesting confidence_level must be 0.95 or 0.99.")
        return v
