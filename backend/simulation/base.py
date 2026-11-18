from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class SimulationMethod(str, Enum):
    GAUSSIAN_MC = "gaussian_mc"
    HISTORICAL_BOOTSTRAP = "historical_bootstrap"
    BLOCK_BOOTSTRAP = "block_bootstrap"
    REGIME_SWITCHING_MC = "regime_switching_mc"


class RebalanceMode(str, Enum):
    DAILY = "daily"
    BUY_AND_HOLD = "buy_and_hold"


@dataclass
class SimulationConfig:
    symbols: list[str]
    weights: np.ndarray
    initial_capital: float = 1_000_000.0
    horizon_days: int = 63
    n_paths: int = 2000
    random_seed: int = 42
    rebalancing: RebalanceMode = RebalanceMode.DAILY
    transaction_cost_bps: float = 0.0
    block_length: int = 10
    crisis_correlation_stress: bool = False
    crisis_stress_blend: float = 0.55
    crisis_target_corr: float = 0.85


@dataclass
class SimulationOutput:
    method: SimulationMethod
    portfolio_paths: np.ndarray        # shape (n_paths, horizon_days + 1)
    portfolio_daily_returns: np.ndarray  # shape (n_paths, horizon_days)
    terminal_values: np.ndarray        # shape (n_paths,)
    terminal_losses: np.ndarray        # shape (n_paths,), positive = loss (V0 - VT)
    return_convention: str
    assumptions: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)


def build_rng(seed: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(int(seed)))


def evolve_portfolio_from_log_returns(
    simulated_log_returns: np.ndarray,
    config: SimulationConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert simulated asset log-return tensor of shape (n_paths, horizon_days, n_assets)
    into portfolio value paths (n_paths, horizon_days + 1) and daily simple returns
    (n_paths, horizon_days).

    Convention:
    - Individual asset log returns r_{i,t} map exactly to simple returns R_{i,t} = exp(r_{i,t}) - 1,
      guaranteeing asset prices remain strictly positive.
    - Under RebalanceMode.DAILY, weights reset to target `w` each session; transaction cost
      (bps) is deducted proportional to one-way portfolio turnover from drifted weights.
    - Under RebalanceMode.BUY_AND_HOLD, initial capital is allocated at t=0 and each asset leg
      compounds independently without rebalancing turnover.
    """
    n_paths, horizon, n_assets = simulated_log_returns.shape
    w = np.asarray(config.weights, dtype=float)
    simple_asset_rets = np.expm1(simulated_log_returns)
    tc_rate = float(config.transaction_cost_bps) / 10_000.0

    paths = np.empty((n_paths, horizon + 1), dtype=float)
    paths[:, 0] = float(config.initial_capital)
    port_daily_rets = np.empty((n_paths, horizon), dtype=float)

    if config.rebalancing == RebalanceMode.BUY_AND_HOLD:
        # Track asset sleeve values: shape (n_paths, n_assets)
        sleeves = np.outer(np.full(n_paths, config.initial_capital), w)
        if tc_rate > 0:
            sleeves *= (1.0 - tc_rate)
        for t in range(horizon):
            sleeves = sleeves * (1.0 + simple_asset_rets[:, t, :])
            total_v = np.sum(sleeves, axis=1)
            prev_v = paths[:, t]
            port_daily_rets[:, t] = (total_v / np.maximum(prev_v, 1e-12)) - 1.0
            paths[:, t + 1] = total_v
    else:
        for t in range(horizon):
            step_r = simple_asset_rets[:, t, :]
            gross_port_r = step_r @ w
            if tc_rate > 0:
                # Drifted weights before rebalance: w_drift = w * (1 + r_i) / (1 + R_p)
                denom = np.maximum(1.0 + gross_port_r[:, None], 1e-12)
                drifted_w = (w[None, :] * (1.0 + step_r)) / denom
                turnover = 0.5 * np.sum(np.abs(drifted_w - w[None, :]), axis=1)
                net_r = gross_port_r - turnover * tc_rate
            else:
                net_r = gross_port_r
            port_daily_rets[:, t] = net_r
            paths[:, t + 1] = paths[:, t] * (1.0 + net_r)

    return paths, port_daily_rets
