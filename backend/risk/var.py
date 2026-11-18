from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from backend.research.analytics import compute_portfolio_simple_returns


def compute_mc_var(
    terminal_losses: np.ndarray,
    initial_capital: float,
    confidence_level: float = 0.95,
) -> dict:
    """
    Monte Carlo Value at Risk under consistent positive-loss convention (L = V0 - VT).
    VaR_alpha is the alpha-quantile of the simulated loss distribution.
    """
    losses = np.asarray(terminal_losses, dtype=float)
    var_amount = float(np.percentile(losses, confidence_level * 100.0))
    var_pct = var_amount / float(initial_capital)
    return {
        "confidence_level": float(confidence_level),
        "var_amount": round(var_amount, 2),
        "var_pct": round(var_pct, 6),
    }


def compute_historical_var(
    simple_returns: pd.DataFrame,
    weights: np.ndarray,
    initial_capital: float,
    horizon_days: int = 1,
    confidence_level: float = 0.95,
) -> dict:
    """
    Empirical Historical VaR computed over rolling H-day compounded portfolio returns
    (avoids invalid sqrt(H) normality scaling on empirical historical returns).
    """
    port_r = compute_portfolio_simple_returns(simple_returns, weights)
    if len(port_r) <= horizon_days:
        # Fallback to 1-day empirical if history shorter than horizon
        horizon_returns = port_r.to_numpy(dtype=float)
    else:
        log_r = np.log1p(port_r.to_numpy(dtype=float))
        csum = np.concatenate([[0.0], np.cumsum(log_r)])
        h_log = csum[horizon_days:] - csum[:-horizon_days]
        horizon_returns = np.expm1(h_log)

    losses = float(initial_capital) * (-horizon_returns)
    var_amount = float(np.percentile(losses, confidence_level * 100.0))
    var_pct = var_amount / float(initial_capital)
    return {
        "confidence_level": float(confidence_level),
        "var_amount": round(var_amount, 2),
        "var_pct": round(var_pct, 6),
        "historical_windows": int(len(losses)),
    }


def compute_parametric_var(
    simple_returns: pd.DataFrame,
    weights: np.ndarray,
    initial_capital: float,
    horizon_days: int = 1,
    confidence_level: float = 0.95,
) -> dict:
    """
    Parametric Gaussian Variance-Covariance VaR:
        mu_p = w^T mu,  sigma_p = sqrt(w^T Sigma w)
        VaR_alpha = V0 * (-mu_p * H + z_alpha * sigma_p * sqrt(H))
    """
    mu_vec = simple_returns.mean(axis=0).to_numpy(dtype=float)
    cov_mat = simple_returns.cov().to_numpy(dtype=float)
    mu_p = float(weights @ mu_vec)
    sigma_p = float(np.sqrt(max(float(weights @ cov_mat @ weights), 0.0)))

    z = float(stats.norm.ppf(confidence_level))
    var_pct = -(mu_p * horizon_days) + z * sigma_p * np.sqrt(horizon_days)
    var_amount = float(initial_capital) * var_pct
    return {
        "confidence_level": float(confidence_level),
        "var_amount": round(var_amount, 2),
        "var_pct": round(float(var_pct), 6),
        "z_score": round(z, 4),
    }
