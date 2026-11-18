from __future__ import annotations

import numpy as np
import pandas as pd

from backend.research.covariance import estimate_and_validate_covariance, safe_cholesky
from backend.simulation.base import (
    SimulationConfig,
    SimulationMethod,
    SimulationOutput,
    build_rng,
    evolve_portfolio_from_log_returns,
)


def run_gaussian_monte_carlo(
    asset_log_returns: pd.DataFrame,
    config: SimulationConfig,
    cov_method: str = "sample",
) -> SimulationOutput:
    """
    Correlated Gaussian Monte Carlo simulation:
        Sigma = L @ L^T
        Z ~ N(0, I)
        r_t = mu + L @ Z_t
    """
    mu = asset_log_returns.mean(axis=0).to_numpy(dtype=float)
    cov_diag = estimate_and_validate_covariance(asset_log_returns, method=cov_method)
    L, chol_repaired, chol_frob = safe_cholesky(cov_diag.matrix)

    rng = build_rng(config.random_seed)
    n_assets = len(config.symbols)
    Z = rng.standard_normal(size=(config.n_paths, config.horizon_days, n_assets))
    # r = mu + Z @ L.T
    sim_log_rets = mu[None, None, :] + Z @ L.T

    paths, port_rets = evolve_portfolio_from_log_returns(sim_log_rets, config)
    terminal_vals = paths[:, -1]
    terminal_losses = float(config.initial_capital) - terminal_vals

    assumptions = [
        "Multivariate Gaussian i.i.d. daily log returns r_t ~ N(mu, Sigma).",
        "Constant mean vector and constant covariance matrix across the entire simulation horizon.",
        "Assumes zero tail-kurtosis excess beyond multivariate normal and no volatility clustering.",
        f"Exact exponential return mapping R_i,t = exp(r_i,t) - 1 with {config.rebalancing.value} rebalancing.",
    ]

    diag = cov_diag.to_dict()
    diag["cholesky_repaired"] = bool(chol_repaired)
    diag["cholesky_repair_norm"] = float(chol_frob)

    return SimulationOutput(
        method=SimulationMethod.GAUSSIAN_MC,
        portfolio_paths=paths,
        portfolio_daily_returns=port_rets,
        terminal_values=terminal_vals,
        terminal_losses=terminal_losses,
        return_convention="Simulated multivariate log returns mapped via R = exp(r) - 1",
        assumptions=assumptions,
        diagnostics=diag,
    )
