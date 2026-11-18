from __future__ import annotations

import numpy as np
import pandas as pd

from backend.simulation.base import (
    SimulationConfig,
    SimulationMethod,
    SimulationOutput,
    build_rng,
    evolve_portfolio_from_log_returns,
)


def run_historical_bootstrap(
    asset_log_returns: pd.DataFrame,
    config: SimulationConfig,
) -> SimulationOutput:
    """
    Multivariate IID historical bootstrap:
    Resamples complete cross-sectional historical trading day vectors with replacement,
    preserving empirical skewness, fat tails, and contemporaneous cross-asset dependence.
    """
    hist_arr = asset_log_returns.to_numpy(dtype=float)
    n_obs = hist_arr.shape[0]
    rng = build_rng(config.random_seed)

    idx = rng.integers(low=0, high=n_obs, size=(config.n_paths, config.horizon_days))
    sim_log_rets = hist_arr[idx]

    paths, port_rets = evolve_portfolio_from_log_returns(sim_log_rets, config)
    terminal_vals = paths[:, -1]
    terminal_losses = float(config.initial_capital) - terminal_vals

    return SimulationOutput(
        method=SimulationMethod.HISTORICAL_BOOTSTRAP,
        portfolio_paths=paths,
        portfolio_daily_returns=port_rets,
        terminal_values=terminal_vals,
        terminal_losses=terminal_losses,
        return_convention="Empirical daily log-return vectors resampled i.i.d. and mapped via R = exp(r) - 1",
        assumptions=[
            "Cross-sectional return vectors are resampled uniformly with replacement from historical sessions.",
            "Preserves empirical marginal fat tails and historical cross-asset co-movements.",
            "Destroys serial autocorrelation and multi-day volatility clustering due to IID day sampling.",
        ],
        diagnostics={"historical_pool_observations": int(n_obs)},
    )
