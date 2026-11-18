from __future__ import annotations

import numpy as np
import pandas as pd
from arch import arch_model

from backend.app.core.exceptions import InsufficientDataError, ModelConvergenceError

TRADING_DAYS_PER_YEAR = 252


def fit_garch_1_1(
    returns: pd.Series,
    forecast_horizon: int = 21,
    min_observations: int = 120,
) -> dict:
    """
    Fit GARCH(1,1) conditional volatility model:
        sigma^2_t = omega + alpha * eps^2_{t-1} + beta * sigma^2_{t-1}
    Returns parameters in percentage-return space, stationarity checks,
    convergence diagnostics, conditional annualized volatility series,
    multi-step volatility forecast, and comparison with 21-day rolling vol.

    Note: GARCH models conditional variance clustering, NOT return direction.
    """
    clean = returns.astype(float).dropna()
    if len(clean) < min_observations:
        raise InsufficientDataError(
            f"GARCH(1,1) requires at least {min_observations} observations; received {len(clean)}."
        )

    # Scale to percentage returns (x100) for numerical optimizer stability in arch
    scaled = clean * 100.0
    if float(scaled.std(ddof=1)) < 1e-8:
        raise ModelConvergenceError("Return series has near-zero variance; cannot fit GARCH(1,1).")

    am = arch_model(scaled, vol="Garch", p=1, q=1, mean="Constant", dist="normal", rescale=False)
    res = am.fit(disp="off", show_warning=False)

    params = res.params.to_dict()
    omega = float(params.get("omega", 0.0))
    alpha = float(params.get("alpha[1]", 0.0))
    beta = float(params.get("beta[1]", 0.0))
    mu_pct = float(params.get("mu", 0.0))
    persistence = alpha + beta
    is_stationary = bool(omega > 0 and alpha >= 0 and beta >= 0 and persistence < 1.0)
    converged = bool(getattr(res, "convergence_flag", 0) == 0)

    if is_stationary:
        uncond_var_pct2 = omega / max(1.0 - persistence, 1e-12)
        uncond_vol_ann = float((np.sqrt(uncond_var_pct2) / 100.0) * np.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        uncond_vol_ann = None

    # Conditional volatility (daily decimal -> annualized)
    cond_vol_daily = res.conditional_volatility / 100.0
    cond_vol_ann = cond_vol_daily * np.sqrt(TRADING_DAYS_PER_YEAR)

    rolling_21_ann = clean.rolling(21).std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)

    # Multi-step analytic variance forecast
    fcast = res.forecast(horizon=forecast_horizon, reindex=False)
    fcast_var_pct2 = fcast.variance.iloc[-1].to_numpy(dtype=float)
    fcast_vol_ann = (np.sqrt(np.maximum(fcast_var_pct2, 0.0)) / 100.0) * np.sqrt(TRADING_DAYS_PER_YEAR)

    warnings: list[str] = []
    if not converged:
        warnings.append(
            f"MLE optimizer reported non-zero convergence flag ({getattr(res, 'convergence_flag', 'unknown')})."
        )
    if not is_stationary:
        warnings.append(
            f"Stationarity constraint violated (alpha + beta = {persistence:.4f} >= 1.0); "
            "unconditional variance is infinite (IGARCH behavior)."
        )

    aligned_comp = pd.DataFrame(
        {
            "garch_vol_ann": cond_vol_ann,
            "rolling_vol_21d_ann": rolling_21_ann,
        }
    ).dropna()

    series_records = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "garch_vol": round(float(row["garch_vol_ann"]), 6),
            "rolling_vol_21d": round(float(row["rolling_vol_21d_ann"]), 6),
        }
        for idx, row in aligned_comp.iterrows()
    ]

    return {
        "model": "GARCH(1,1)",
        "observations": int(len(clean)),
        "converged": converged,
        "convergence_flag": int(getattr(res, "convergence_flag", 0)),
        "log_likelihood": round(float(res.loglikelihood), 4),
        "aic": round(float(res.aic), 4),
        "bic": round(float(res.bic), 4),
        "parameters": {
            "mu_daily_pct": round(mu_pct, 6),
            "omega_pct2": round(omega, 6),
            "alpha": round(alpha, 6),
            "beta": round(beta, 6),
            "persistence": round(persistence, 6),
        },
        "is_stationary": is_stationary,
        "unconditional_vol_annualized": round(uncond_vol_ann, 6) if uncond_vol_ann is not None else None,
        "current_conditional_vol_annualized": round(float(cond_vol_ann.iloc[-1]), 6),
        "current_rolling_vol_21d_annualized": round(float(rolling_21_ann.dropna().iloc[-1]), 6)
        if not rolling_21_ann.dropna().empty
        else None,
        "forecast_horizon_days": int(forecast_horizon),
        "forecast_vol_annualized": [
            {"horizon_day": int(i + 1), "annualized_vol": round(float(v), 6)}
            for i, v in enumerate(fcast_vol_ann)
        ],
        "series": series_records,
        "warnings": warnings,
        "limitations": (
            "GARCH(1,1) captures conditional volatility clustering and mean reversion in variance; "
            "it does not predict directional asset returns and assumes symmetric response to positive/negative shocks."
        ),
    }
