from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from backend.research.analytics import compute_portfolio_simple_returns


def compute_cvar_from_losses(
    losses: np.ndarray,
    initial_capital: float,
    confidence_level: float = 0.95,
) -> dict:
    """
    Conditional Value at Risk (Expected Shortfall):
        CVaR_alpha = E[L | L >= VaR_alpha]
    Under continuous/finite sample loss convention (positive = loss).
    Guarantees CVaR >= VaR.
    """
    arr = np.asarray(losses, dtype=float)
    var_threshold = float(np.percentile(arr, confidence_level * 100.0))
    tail = arr[arr >= var_threshold]
    cvar_amount = float(np.mean(tail)) if len(tail) > 0 else var_threshold
    cvar_pct = cvar_amount / float(initial_capital)
    return {
        "confidence_level": float(confidence_level),
        "var_threshold": round(var_threshold, 2),
        "cvar_amount": round(cvar_amount, 2),
        "cvar_pct": round(cvar_pct, 6),
        "tail_observations": int(len(tail)),
    }


def compute_parametric_cvar(
    simple_returns: pd.DataFrame,
    weights: np.ndarray,
    initial_capital: float,
    horizon_days: int = 1,
    confidence_level: float = 0.95,
) -> dict:
    """
    Closed-form Gaussian Expected Shortfall:
        CVaR_alpha = V0 * (-mu_p * H + sigma_p * sqrt(H) * phi(z_alpha) / (1 - alpha))
    """
    mu_vec = simple_returns.mean(axis=0).to_numpy(dtype=float)
    cov_mat = simple_returns.cov().to_numpy(dtype=float)
    mu_p = float(weights @ mu_vec)
    sigma_p = float(np.sqrt(max(float(weights @ cov_mat @ weights), 0.0)))

    z = float(stats.norm.ppf(confidence_level))
    pdf_z = float(stats.norm.pdf(z))
    cvar_pct = -(mu_p * horizon_days) + sigma_p * np.sqrt(horizon_days) * (pdf_z / (1.0 - confidence_level))
    cvar_amount = float(initial_capital) * cvar_pct
    return {
        "confidence_level": float(confidence_level),
        "cvar_amount": round(cvar_amount, 2),
        "cvar_pct": round(float(cvar_pct), 6),
    }


def compute_historical_cvar(
    simple_returns: pd.DataFrame,
    weights: np.ndarray,
    initial_capital: float,
    horizon_days: int = 1,
    confidence_level: float = 0.95,
) -> dict:
    port_r = compute_portfolio_simple_returns(simple_returns, weights)
    if len(port_r) <= horizon_days:
        horizon_returns = port_r.to_numpy(dtype=float)
    else:
        log_r = np.log1p(port_r.to_numpy(dtype=float))
        csum = np.concatenate([[0.0], np.cumsum(log_r)])
        horizon_returns = np.expm1(csum[horizon_days:] - csum[:-horizon_days])

    losses = float(initial_capital) * (-horizon_returns)
    return compute_cvar_from_losses(losses, initial_capital, confidence_level)
