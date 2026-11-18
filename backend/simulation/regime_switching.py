from __future__ import annotations

import numpy as np
import pandas as pd

from backend.research.covariance import apply_crisis_correlation_stress, safe_cholesky
from backend.research.regime_detection import FittedHMMResult, REGIME_LABELS
from backend.simulation.base import (
    SimulationConfig,
    SimulationMethod,
    SimulationOutput,
    build_rng,
    evolve_portfolio_from_log_returns,
)


def run_regime_switching_monte_carlo(
    hmm_result: FittedHMMResult,
    config: SimulationConfig,
) -> SimulationOutput:
    """
    Regime-aware Markov-switching Monte Carlo:
    At each step t = 1..H:
      1. Sample next latent regime s_t ~ P(s_{t-1}, .) using fitted HMM transition matrix.
      2. Draw correlated asset log returns r_t ~ N(mu_{s_t}, Sigma_{s_t}).
      3. When `crisis_correlation_stress` is enabled, the HIGH_VOL regime covariance
         applies upward correlation stress to model crisis correlation breakdown.
    """
    rng = build_rng(config.random_seed)
    n_assets = len(config.symbols)
    n_states = len(REGIME_LABELS)
    trans = hmm_result.transition_matrix

    # Pre-compute Cholesky factors per regime
    chol_by_state: list[np.ndarray] = []
    mu_by_state: list[np.ndarray] = []
    stress_details: dict = {"crisis_correlation_stress_enabled": bool(config.crisis_correlation_stress)}

    for label in REGIME_LABELS:
        mu_vec = hmm_result.regime_mu_daily[label]
        cov_mat = hmm_result.regime_cov_daily[label]
        if config.crisis_correlation_stress and label == "HIGH_VOL":
            stressed_cov, base_corr, stressed_corr = apply_crisis_correlation_stress(
                cov_mat,
                stress_blend=config.crisis_stress_blend,
                target_crisis_corr=config.crisis_target_corr,
            )
            L, _, _ = safe_cholesky(stressed_cov)
            off_diag_mask = ~np.eye(n_assets, dtype=bool)
            avg_base_corr = float(np.mean(base_corr[off_diag_mask])) if n_assets > 1 else 1.0
            avg_stress_corr = float(np.mean(stressed_corr[off_diag_mask])) if n_assets > 1 else 1.0
            stress_details["high_vol_avg_corr_baseline"] = round(avg_base_corr, 4)
            stress_details["high_vol_avg_corr_stressed"] = round(avg_stress_corr, 4)
        else:
            L, _, _ = safe_cholesky(cov_mat)
        chol_by_state.append(L)
        mu_by_state.append(mu_vec)

    # Initial regime distribution: use current filtered posterior probabilities from HMM
    init_probs = np.array(
        [hmm_result.current_state_probs[lbl] for lbl in REGIME_LABELS],
        dtype=float,
    )
    init_probs = init_probs / np.sum(init_probs)
    current_states = rng.choice(n_states, size=config.n_paths, p=init_probs)

    # Pre-generate all standard normal shocks for vectorised speed
    Z = rng.standard_normal(size=(config.n_paths, config.horizon_days, n_assets))
    sim_log_rets = np.empty((config.n_paths, config.horizon_days, n_assets), dtype=float)
    regime_path_counts = np.zeros(n_states, dtype=int)

    # Pre-compute cumulative transition probabilities for fast vectorised Markov sampling
    cum_trans = np.cumsum(trans, axis=1)
    cum_trans[:, -1] = 1.0
    uniforms = rng.random(size=(config.n_paths, config.horizon_days))

    for t in range(config.horizon_days):
        # Transition s_{t-1} -> s_t
        u_t = uniforms[:, t][:, None]
        thresholds = cum_trans[current_states]
        current_states = np.argmax(u_t <= thresholds, axis=1)

        for k in range(n_states):
            mask = current_states == k
            cnt = int(np.sum(mask))
            if cnt > 0:
                regime_path_counts[k] += cnt
                sim_log_rets[mask, t, :] = mu_by_state[k][None, :] + Z[mask, t, :] @ chol_by_state[k].T

    paths, port_rets = evolve_portfolio_from_log_returns(sim_log_rets, config)
    terminal_vals = paths[:, -1]
    terminal_losses = float(config.initial_capital) - terminal_vals

    total_steps = max(int(np.sum(regime_path_counts)), 1)
    simulated_occupancy = {
        REGIME_LABELS[k]: round(float(regime_path_counts[k] / total_steps * 100.0), 2)
        for k in range(n_states)
    }

    assumptions = [
        "First-order discrete Markov chain governs transitions between LOW_VOL, NORMAL, and HIGH_VOL regimes.",
        "Within each regime, daily log returns follow regime-conditioned multivariate Gaussian distributions.",
        f"Initial state sampled from latest HMM filtered posterior: {hmm_result.current_state_probs}.",
    ]
    if config.crisis_correlation_stress:
        assumptions.append(
            f"Crisis correlation sensitivity active: HIGH_VOL off-diagonal correlations stressed toward "
            f"{config.crisis_target_corr:.2f} (blend={config.crisis_stress_blend:.2f})."
        )

    return SimulationOutput(
        method=SimulationMethod.REGIME_SWITCHING_MC,
        portfolio_paths=paths,
        portfolio_daily_returns=port_rets,
        terminal_values=terminal_vals,
        terminal_losses=terminal_losses,
        return_convention="Regime-conditioned log returns mapped via R = exp(r) - 1",
        assumptions=assumptions,
        diagnostics={
            "simulated_regime_occupancy_pct": simulated_occupancy,
            **stress_details,
        },
    )
