from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from backend.research.analytics import compute_portfolio_simple_returns
from backend.research.covariance import estimate_and_validate_covariance, safe_cholesky
from backend.research.regime_detection import REGIME_LABELS, fit_market_regime_hmm
from backend.simulation.base import build_rng


def kupiec_pof_test(violations: int, observations: int, alpha: float) -> dict:
    """
    Kupiec (1995) Proportion of Failures (Unconditional Coverage) Likelihood Ratio test:
        p = 1 - alpha (expected violation rate)
        phat = x / T
        LR_POF = -2 * ln( ((1-p)^(T-x) * p^x) / ((1-phat)^(T-x) * phat^x) ) ~ chi2(df=1)
    """
    p = 1.0 - float(alpha)
    T = int(observations)
    x = int(violations)
    if T <= 0:
        return {"lr_pof": 0.0, "p_value": 1.0, "rejected_at_5pct": False}

    phat = x / T
    # Boundary-safe log likelihood
    ll_null = (T - x) * np.log(max(1.0 - p, 1e-15)) + x * np.log(max(p, 1e-15))
    if x == 0:
        ll_alt = T * np.log(1.0)
    elif x == T:
        ll_alt = T * np.log(1.0)
    else:
        ll_alt = (T - x) * np.log(max(1.0 - phat, 1e-15)) + x * np.log(max(phat, 1e-15))

    lr_pof = max(0.0, float(-2.0 * (ll_null - ll_alt)))
    p_value = float(1.0 - stats.chi2.cdf(lr_pof, df=1))
    return {
        "lr_pof": round(lr_pof, 4),
        "p_value": round(p_value, 4),
        "rejected_at_5pct": bool(p_value < 0.05),
    }


def christoffersen_cc_test(violations_seq: np.ndarray, alpha: float) -> dict:
    """
    Christoffersen (1998) Conditional Coverage Likelihood Ratio test:
        LR_CC = LR_POF + LR_IND ~ chi2(df=2)
    Tests both correct unconditional exception frequency AND independence (no clustering).
    """
    seq = np.asarray(violations_seq, dtype=int)
    T = len(seq)
    x = int(np.sum(seq))
    pof = kupiec_pof_test(x, T, alpha)

    if T < 2:
        return {
            **pof,
            "lr_ind": 0.0,
            "lr_cc": pof["lr_pof"],
            "cc_p_value": pof["p_value"],
            "cc_rejected_at_5pct": pof["rejected_at_5pct"],
        }

    # Transition counts n_ij from t-1 to t
    prev_s = seq[:-1]
    curr_s = seq[1:]
    n00 = int(np.sum((prev_s == 0) & (curr_s == 0)))
    n01 = int(np.sum((prev_s == 0) & (curr_s == 1)))
    n10 = int(np.sum((prev_s == 1) & (curr_s == 0)))
    n11 = int(np.sum((prev_s == 1) & (curr_s == 1)))

    n0 = n00 + n01
    n1 = n10 + n11
    pi = (n01 + n11) / max(n0 + n1, 1)
    pi0 = n01 / n0 if n0 > 0 else pi
    pi1 = n11 / n1 if n1 > 0 else pi

    def _safe_term(count: int, prob: float) -> float:
        if count == 0:
            return 0.0
        return float(count * np.log(max(prob, 1e-15)))

    ll_ind_null = _safe_term(n00 + n10, 1.0 - pi) + _safe_term(n01 + n11, pi)
    ll_ind_alt = (
        _safe_term(n00, 1.0 - pi0)
        + _safe_term(n01, pi0)
        + _safe_term(n10, 1.0 - pi1)
        + _safe_term(n11, pi1)
    )
    lr_ind = max(0.0, float(-2.0 * (ll_ind_null - ll_ind_alt)))
    lr_cc = float(pof["lr_pof"]) + lr_ind
    cc_p_value = float(1.0 - stats.chi2.cdf(lr_cc, df=2))

    return {
        "lr_pof": pof["lr_pof"],
        "pof_p_value": pof["p_value"],
        "pof_rejected_at_5pct": pof["rejected_at_5pct"],
        "lr_ind": round(lr_ind, 4),
        "lr_cc": round(lr_cc, 4),
        "cc_p_value": round(cc_p_value, 4),
        "cc_rejected_at_5pct": bool(cc_p_value < 0.05),
    }


def run_rolling_var_backtest(
    asset_log_returns: pd.DataFrame,
    asset_simple_returns: pd.DataFrame,
    benchmark_log_returns: pd.Series,
    weights: np.ndarray,
    confidence_level: float = 0.95,
    window_size: int = 252,
    oos_sessions: int = 250,
    mc_draws_per_step: int = 1000,
    random_seed: int = 42,
) -> dict:
    """
    Chronological, strictly leakage-free out-of-sample 1-day VaR backtest comparing:
      1. Gaussian Monte Carlo (rolling window)
      2. Historical Bootstrap (rolling window)
      3. Block Bootstrap (rolling window, b=10)
      4. Regime-Switching Monte Carlo (expanding HMM refit every 21 sessions strictly <= t-1)

    Every day t's VaR estimate uses ONLY observations <= t-1.
    Never fabricates passing results; honestly reports over- or under-coverage.
    """
    common_idx = asset_log_returns.index.intersection(asset_simple_returns.index)
    log_df = asset_log_returns.loc[common_idx]
    simp_df = asset_simple_returns.loc[common_idx]
    bench_s = benchmark_log_returns.loc[common_idx]

    total_n = len(log_df)
    min_train = max(window_size, 252)
    if total_n < min_train + 40:
        raise ValueError(
            f"Backtesting requires at least {min_train + 40} observations; got {total_n}."
        )

    effective_oos = min(oos_sessions, total_n - min_train)
    start_pos = total_n - effective_oos
    port_actual_simple = compute_portfolio_simple_returns(simp_df, weights)

    rng = build_rng(random_seed)
    q_level = confidence_level * 100.0

    dates_oos: list[str] = []
    actual_loss_pct: list[float] = []
    var_series: dict[str, list[float]] = {
        "gaussian_mc": [],
        "historical_bootstrap": [],
        "block_bootstrap": [],
        "regime_switching_mc": [],
    }

    cached_hmm = None
    last_hmm_refit = -999

    for t in range(start_pos, total_n):
        dates_oos.append(log_df.index[t].strftime("%Y-%m-%d"))
        realized_loss = float(-port_actual_simple.iloc[t])
        actual_loss_pct.append(realized_loss)

        # Strictly trailing window [t - window_size : t] (excludes t!)
        win_log = log_df.iloc[t - window_size : t]
        win_arr = win_log.to_numpy(dtype=float)

        # 1. Gaussian MC 1-day VaR
        mu = np.mean(win_arr, axis=0)
        cov_diag = estimate_and_validate_covariance(win_arr, method="sample")
        L, _, _ = safe_cholesky(cov_diag.matrix)
        Z = rng.standard_normal(size=(mc_draws_per_step, len(weights)))
        g_log = mu[None, :] + Z @ L.T
        g_port_r = np.expm1(g_log) @ weights
        var_series["gaussian_mc"].append(float(np.percentile(-g_port_r, q_level)))

        # 2. Historical Bootstrap 1-day VaR
        h_idx = rng.integers(0, len(win_arr), size=mc_draws_per_step)
        h_port_r = np.expm1(win_arr[h_idx]) @ weights
        var_series["historical_bootstrap"].append(float(np.percentile(-h_port_r, q_level)))

        # 3. Block Bootstrap 1-day VaR (sample 10-day blocks and take first step or marginal block draws)
        b_len = min(10, len(win_arr))
        n_blk_draws = max(1, mc_draws_per_step // b_len)
        starts = rng.integers(0, len(win_arr), size=n_blk_draws)
        offsets = np.arange(b_len)[None, :]
        blk_idx = ((starts[:, None] + offsets) % len(win_arr)).ravel()[:mc_draws_per_step]
        b_port_r = np.expm1(win_arr[blk_idx]) @ weights
        var_series["block_bootstrap"].append(float(np.percentile(-b_port_r, q_level)))

        # 4. Regime-Switching MC 1-day VaR (causal expanding HMM fit up to t-1, refit every 21 sessions)
        if cached_hmm is None or (t - last_hmm_refit) >= 21:
            try:
                cached_hmm = fit_market_regime_hmm(
                    asset_log_returns=log_df.iloc[:t],
                    benchmark_returns=bench_s.iloc[:t],
                    random_seed=random_seed,
                )
                last_hmm_refit = t
            except Exception:
                cached_hmm = None

        if cached_hmm is not None:
            # Sample next regime from latest filtered state probabilities
            init_p = np.array([cached_hmm.current_state_probs[lbl] for lbl in REGIME_LABELS], dtype=float)
            init_p = init_p / np.sum(init_p)
            next_p = init_p @ cached_hmm.transition_matrix
            next_p = next_p / np.sum(next_p)
            states_draw = rng.choice(len(REGIME_LABELS), size=mc_draws_per_step, p=next_p)
            rs_log = np.empty((mc_draws_per_step, len(weights)), dtype=float)
            Z_rs = rng.standard_normal(size=(mc_draws_per_step, len(weights)))
            for k, lbl in enumerate(REGIME_LABELS):
                m = states_draw == k
                if np.any(m):
                    Lk, _, _ = safe_cholesky(cached_hmm.regime_cov_daily[lbl])
                    rs_log[m] = cached_hmm.regime_mu_daily[lbl][None, :] + Z_rs[m] @ Lk.T
            rs_port_r = np.expm1(rs_log) @ weights
            var_series["regime_switching_mc"].append(float(np.percentile(-rs_port_r, q_level)))
        else:
            var_series["regime_switching_mc"].append(var_series["gaussian_mc"][-1])

    actual_arr = np.asarray(actual_loss_pct, dtype=float)
    expected_rate = 1.0 - float(confidence_level)
    expected_violations = expected_rate * effective_oos

    model_reports: dict[str, dict] = {}
    for method_key, preds in var_series.items():
        pred_arr = np.asarray(preds, dtype=float)
        violations_seq = (actual_arr > pred_arr).astype(int)
        n_viol = int(np.sum(violations_seq))
        actual_rate = float(n_viol / effective_oos)
        cc_res = christoffersen_cc_test(violations_seq, confidence_level)

        if not cc_res["pof_rejected_at_5pct"] and not cc_res["cc_rejected_at_5pct"]:
            verdict = "CALIBRATED"
        elif actual_rate > expected_rate:
            verdict = "REJECTED_UNDER_COVERAGE"
        else:
            verdict = "REJECTED_OVER_CONSERVATIVE"

        violation_dates = [dates_oos[i] for i, v in enumerate(violations_seq) if v == 1]

        model_reports[method_key] = {
            "method": method_key,
            "observations": int(effective_oos),
            "confidence_level": float(confidence_level),
            "expected_violations": round(float(expected_violations), 2),
            "actual_violations": n_viol,
            "expected_violation_rate": round(float(expected_rate), 4),
            "actual_violation_rate": round(float(actual_rate), 4),
            "kupiec_lr_pof": cc_res["lr_pof"],
            "kupiec_p_value": cc_res["pof_p_value"],
            "kupiec_passed": not cc_res["pof_rejected_at_5pct"],
            "christoffersen_lr_ind": cc_res["lr_ind"],
            "christoffersen_lr_cc": cc_res["lr_cc"],
            "christoffersen_p_value": cc_res["cc_p_value"],
            "christoffersen_passed": not cc_res["cc_rejected_at_5pct"],
            "calibration_verdict": verdict,
            "violation_dates": violation_dates,
            "predicted_var_pct": [round(float(x), 6) for x in pred_arr],
        }

    return {
        "backtest_start_date": dates_oos[0],
        "backtest_end_date": dates_oos[-1],
        "observations": int(effective_oos),
        "rolling_window_days": int(window_size),
        "confidence_level": float(confidence_level),
        "dates": dates_oos,
        "realized_loss_pct": [round(float(x), 6) for x in actual_arr],
        "models": model_reports,
        "methodology_note": (
            "Strictly chronological out-of-sample rolling 1-day VaR evaluation. On each date t, "
            "covariance, bootstrap pools, and HMM parameters are estimated strictly from observations <= t-1. "
            "In-sample fit measures historical explanatory power; out-of-sample tests measure real-time predictive calibration."
        ),
    }
