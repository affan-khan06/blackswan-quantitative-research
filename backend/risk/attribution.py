from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def compute_euler_risk_attribution(
    symbols: list[str],
    weights: np.ndarray,
    daily_cov_matrix: np.ndarray | pd.DataFrame,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> dict:
    """
    Euler Volatility Risk Attribution:
        sigma_p = sqrt(w^T Sigma w)
        MCR_i = (Sigma w)_i / sigma_p
        CCR_i = w_i * MCR_i
        sum_i CCR_i == sigma_p   (Euler's homogeneous function theorem)

    Explicitly measures contributions to portfolio return VOLATILITY,
    distinct from expected-loss or tail-CVaR attribution.
    """
    cov_daily = (
        daily_cov_matrix.to_numpy(dtype=float)
        if isinstance(daily_cov_matrix, pd.DataFrame)
        else np.asarray(daily_cov_matrix, dtype=float)
    )
    cov_ann = cov_daily * float(trading_days)
    w = np.asarray(weights, dtype=float)

    port_var = float(w @ cov_ann @ w)
    port_vol = float(np.sqrt(max(port_var, 1e-16)))

    sigma_w = cov_ann @ w
    mcr = sigma_w / port_vol
    ccr = w * mcr
    pct_contrib = ccr / port_vol

    standalone_vols = np.sqrt(np.maximum(np.diag(cov_ann), 0.0))
    weighted_standalone_sum = float(np.sum(np.abs(w) * standalone_vols))
    diversification_benefit = max(0.0, weighted_standalone_sum - port_vol)

    sum_ccr = float(np.sum(ccr))
    reconciliation_error = float(abs(sum_ccr - port_vol))

    assets_out = []
    for i, sym in enumerate(symbols):
        assets_out.append(
            {
                "symbol": sym,
                "weight": round(float(w[i]), 6),
                "standalone_annualized_vol": round(float(standalone_vols[i]), 6),
                "marginal_contribution_to_vol": round(float(mcr[i]), 6),
                "component_contribution_to_vol": round(float(ccr[i]), 6),
                "pct_risk_contribution": round(float(pct_contrib[i] * 100.0), 3),
            }
        )

    return {
        "methodology": "Euler Variance-Covariance Volatility Decomposition",
        "note": (
            "Component risk contributions measure each asset's share of total annualized portfolio "
            "volatility (sigma_p) and reconcile exactly by Euler's theorem; this is distinct from "
            "tail-loss (CVaR) attribution."
        ),
        "portfolio_annualized_volatility": round(port_vol, 6),
        "sum_component_contributions": round(sum_ccr, 6),
        "reconciliation_error": reconciliation_error,
        "reconciled": bool(reconciliation_error < 1e-7),
        "diversification_benefit_vol": round(float(diversification_benefit), 6),
        "assets": assets_out,
    }
