from __future__ import annotations

from enum import Enum
import numpy as np
import pandas as pd

from backend.data.acquisition import NSE_UNIVERSE
from backend.research.covariance import apply_crisis_correlation_stress, estimate_and_validate_covariance, safe_cholesky
from backend.risk.cvar import compute_cvar_from_losses
from backend.risk.var import compute_mc_var
from backend.simulation.base import build_rng, evolve_portfolio_from_log_returns, SimulationConfig, RebalanceMode


class HypotheticalScenarioType(str, Enum):
    BROAD_MARKET_DECLINE = "broad_market_decline"
    SECTOR_DECLINE = "sector_decline"
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_SHOCK = "correlation_shock"
    COMBINED_CRISIS = "combined_crisis"


def run_hypothetical_stress_test(
    scenario_type: HypotheticalScenarioType,
    symbols: list[str],
    weights: np.ndarray,
    asset_log_returns: pd.DataFrame,
    initial_capital: float = 1_000_000.0,
    shock_magnitude_pct: float = -0.15,
    target_sector: str = "Financials",
    volatility_multiplier: float = 2.0,
    target_crisis_corr: float = 0.88,
    horizon_days: int = 21,
    n_paths: int = 2000,
    random_seed: int = 42,
) -> dict:
    """
    Execute a clearly labeled HYPOTHETICAL stress test against the baseline empirical covariance.
    Computes both instantaneous shock impact (where applicable) and stressed forward Monte Carlo
    loss distribution vs baseline un-stressed distribution.
    """
    cov_diag = estimate_and_validate_covariance(asset_log_returns, method="sample")
    base_mu = asset_log_returns.mean(axis=0).to_numpy(dtype=float)
    base_cov = cov_diag.matrix
    n_assets = len(symbols)

    cfg = SimulationConfig(
        symbols=symbols,
        weights=weights,
        initial_capital=initial_capital,
        horizon_days=horizon_days,
        n_paths=n_paths,
        random_seed=random_seed,
        rebalancing=RebalanceMode.DAILY,
    )

    # Baseline forward simulation
    L_base, _, _ = safe_cholesky(base_cov)
    rng_base = build_rng(random_seed)
    Z_base = rng_base.standard_normal(size=(n_paths, horizon_days, n_assets))
    sim_base_log = base_mu[None, None, :] + Z_base @ L_base.T
    base_paths, _ = evolve_portfolio_from_log_returns(sim_base_log, cfg)
    base_losses = initial_capital - base_paths[:, -1]
    base_var_95 = compute_mc_var(base_losses, initial_capital, 0.95)
    base_cvar_95 = compute_cvar_from_losses(base_losses, initial_capital, 0.95)
    base_var_99 = compute_mc_var(base_losses, initial_capital, 0.99)

    # Construct stressed parameters
    stressed_mu = base_mu.copy()
    stressed_cov = base_cov.copy()
    instant_asset_shocks = np.zeros(n_assets, dtype=float)

    if scenario_type == HypotheticalScenarioType.BROAD_MARKET_DECLINE:
        instant_asset_shocks[:] = shock_magnitude_pct
        # Also apply drift shock spread across horizon
        stressed_mu = base_mu + (np.log1p(max(shock_magnitude_pct, -0.80)) / horizon_days)
        desc = f"Hypothetical uniform {shock_magnitude_pct*100:.1f}% broad equity market drawdown."
    elif scenario_type == HypotheticalScenarioType.SECTOR_DECLINE:
        for i, sym in enumerate(symbols):
            meta = NSE_UNIVERSE.get(sym)
            if meta and meta.sector.lower() == target_sector.lower():
                instant_asset_shocks[i] = shock_magnitude_pct
            else:
                instant_asset_shocks[i] = shock_magnitude_pct * 0.25
        stressed_mu = base_mu + (np.log1p(np.maximum(instant_asset_shocks, -0.80)) / horizon_days)
        desc = (
            f"Hypothetical {target_sector} sector shock of {shock_magnitude_pct*100:.1f}% "
            f"(spillover {shock_magnitude_pct*25:.1f}% to other sectors)."
        )
    elif scenario_type == HypotheticalScenarioType.VOLATILITY_SPIKE:
        stressed_cov = base_cov * (volatility_multiplier ** 2)
        desc = f"Hypothetical {volatility_multiplier:.2f}x annualized volatility expansion across all assets."
    elif scenario_type == HypotheticalScenarioType.CORRELATION_SHOCK:
        stressed_cov, _, _ = apply_crisis_correlation_stress(
            base_cov, stress_blend=0.80, target_crisis_corr=target_crisis_corr
        )
        desc = f"Hypothetical diversification breakdown: off-diagonal correlations stressed toward {target_crisis_corr:.2f}."
    else:  # COMBINED_CRISIS
        instant_asset_shocks[:] = shock_magnitude_pct
        stressed_mu = base_mu + (np.log1p(max(shock_magnitude_pct, -0.80)) / horizon_days)
        vol_scaled_cov = base_cov * (volatility_multiplier ** 2)
        stressed_cov, _, _ = apply_crisis_correlation_stress(
            vol_scaled_cov, stress_blend=0.80, target_crisis_corr=target_crisis_corr
        )
        desc = (
            f"Hypothetical Combined Black Swan: {shock_magnitude_pct*100:.1f}% market shock + "
            f"{volatility_multiplier:.2f}x volatility spike + {target_crisis_corr:.2f} correlation convergence."
        )

    L_stress, _, _ = safe_cholesky(stressed_cov)
    rng_stress = build_rng(random_seed)
    Z_stress = rng_stress.standard_normal(size=(n_paths, horizon_days, n_assets))
    sim_stress_log = stressed_mu[None, None, :] + Z_stress @ L_stress.T
    stress_paths, _ = evolve_portfolio_from_log_returns(sim_stress_log, cfg)
    stress_losses = initial_capital - stress_paths[:, -1]
    stress_var_95 = compute_mc_var(stress_losses, initial_capital, 0.95)
    stress_cvar_95 = compute_cvar_from_losses(stress_losses, initial_capital, 0.95)
    stress_var_99 = compute_mc_var(stress_losses, initial_capital, 0.99)

    instant_port_shock_pct = float(weights @ instant_asset_shocks)
    instant_port_loss_inr = float(initial_capital * (-instant_port_shock_pct))

    asset_breakdown = [
        {
            "symbol": symbols[i],
            "sector": NSE_UNIVERSE[symbols[i]].sector if symbols[i] in NSE_UNIVERSE else "Unknown",
            "weight": round(float(weights[i]), 4),
            "hypothetical_shock_pct": round(float(instant_asset_shocks[i]), 4),
            "shock_pnl_inr": round(float(initial_capital * weights[i] * instant_asset_shocks[i]), 2),
        }
        for i in range(n_assets)
    ]

    return {
        "scenario_type": "HYPOTHETICAL",
        "scenario_name": scenario_type.value,
        "description": desc,
        "disclaimer": (
            "HYPOTHETICAL SCENARIO: Parameters are user-specified sensitivity shocks, "
            "not observed historical market episodes or predictive forecasts."
        ),
        "horizon_days": int(horizon_days),
        "instantaneous_shock": {
            "portfolio_return_pct": round(instant_port_shock_pct, 6),
            "portfolio_loss_inr": round(instant_port_loss_inr, 2),
            "post_shock_value_inr": round(float(initial_capital - instant_port_loss_inr), 2),
        },
        "baseline_distribution": {
            "expected_terminal_value": round(float(np.mean(base_paths[:, -1])), 2),
            "var_95_inr": base_var_95["var_amount"],
            "cvar_95_inr": base_cvar_95["cvar_amount"],
            "var_99_inr": base_var_99["var_amount"],
        },
        "stressed_distribution": {
            "expected_terminal_value": round(float(np.mean(stress_paths[:, -1])), 2),
            "var_95_inr": stress_var_95["var_amount"],
            "cvar_95_inr": stress_cvar_95["cvar_amount"],
            "var_99_inr": stress_var_99["var_amount"],
        },
        "var_95_amplification_ratio": round(
            float(stress_var_95["var_amount"] / max(base_var_95["var_amount"], 1.0)), 3
        ),
        "asset_breakdown": asset_breakdown,
    }
