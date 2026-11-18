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


def run_block_bootstrap(
    asset_log_returns: pd.DataFrame,
    config: SimulationConfig,
) -> SimulationOutput:
    """
    Circular multivariate block bootstrap:
    Resamples contiguous blocks of length `block_length` across all assets simultaneously,
    preserving both contemporaneous cross-asset dependence and local temporal volatility clustering.
    """
    hist_arr = asset_log_returns.to_numpy(dtype=float)
    n_obs, n_assets = hist_arr.shape
    block_len = max(2, min(int(config.block_length), n_obs))
    rng = build_rng(config.random_seed)

    n_blocks = int(np.ceil(config.horizon_days / block_len))
    starts = rng.integers(low=0, high=n_obs, size=(config.n_paths, n_blocks))
    offsets = np.arange(block_len)[None, None, :]
    # Circular wrap-around indices: shape (n_paths, n_blocks, block_len)
    indices = (starts[:, :, None] + offsets) % n_obs
    flat_indices = indices.reshape(config.n_paths, n_blocks * block_len)[:, : config.horizon_days]

    sim_log_rets = hist_arr[flat_indices]
    paths, port_rets = evolve_portfolio_from_log_returns(sim_log_rets, config)
    terminal_vals = paths[:, -1]
    terminal_losses = float(config.initial_capital) - terminal_vals

    return SimulationOutput(
        method=SimulationMethod.BLOCK_BOOTSTRAP,
        portfolio_paths=paths,
        portfolio_daily_returns=port_rets,
        terminal_values=terminal_vals,
        terminal_losses=terminal_losses,
        return_convention="Circular block-resampled historical log returns mapped via R = exp(r) - 1",
        assumptions=[
            f"Contiguous circular blocks of {block_len} trading days resampled with replacement.",
            "Preserves short-horizon volatility clustering, serial dependence, and fat tails.",
            "Cannot generate shocks larger than the worst historical block observed in the sample.",
        ],
        diagnostics={
            "historical_pool_observations": int(n_obs),
            "block_length_days": int(block_len),
        },
    )
