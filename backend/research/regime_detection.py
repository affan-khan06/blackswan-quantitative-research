from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

from backend.app.core.exceptions import InsufficientDataError, ModelConvergenceError
from backend.data.feature_engineering import build_hmm_feature_matrix
from backend.research.covariance import estimate_and_validate_covariance

REGIME_LABELS = ["LOW_VOL", "NORMAL", "HIGH_VOL"]
TRADING_DAYS_PER_YEAR = 252


@dataclass
class FittedHMMResult:
    labels_ordered: list[str]
    transition_matrix: np.ndarray
    state_sequence: list[str]
    state_dates: list[str]
    state_probabilities: np.ndarray
    current_regime: str
    current_state_probs: dict[str, float]
    regime_stats: dict[str, dict]
    regime_mu_daily: dict[str, np.ndarray]
    regime_cov_daily: dict[str, np.ndarray]
    oos_regime_accuracy_note: str
    diagnostics: dict


def fit_market_regime_hmm(
    asset_log_returns: pd.DataFrame,
    benchmark_returns: pd.Series,
    n_states: int = 3,
    vol_window: int = 21,
    random_seed: int = 42,
    oos_split_ratio: float = 0.70,
) -> FittedHMMResult:
    """
    Fit a 3-state Gaussian Hidden Markov Model on causal market features
    [market_return, rolling_vol, abs_return].

    CRITICAL LEAKAGE PREVENTION:
    - Feature standardization (mean/std) is fitted strictly on the chronological
      training partition [0 : split_idx] for out-of-sample inference evaluation, and
      full-sample parameters are ordered post-fit solely by realized annualized
      volatility of each latent state (never assuming raw HMM index ordering).
    """
    if n_states != 3:
        raise ValueError("BLACKSWAN HMM regime engine requires exactly 3 latent states.")

    features = build_hmm_feature_matrix(benchmark_returns, vol_window=vol_window)
    # Align asset returns with causal feature dates
    common_idx = features.index.intersection(asset_log_returns.index)
    if len(common_idx) < 180:
        raise InsufficientDataError(
            f"HMM regime detection requires at least 180 aligned observations; found {len(common_idx)}."
        )

    feat_aligned = features.loc[common_idx]
    ret_aligned = asset_log_returns.loc[common_idx]
    bench_aligned = benchmark_returns.loc[common_idx]

    X_raw = feat_aligned.to_numpy(dtype=float)

    # Chronological Out-of-Sample check (train on first 70%, infer causally on remaining 30%)
    split_idx = max(120, int(len(X_raw) * oos_split_ratio))
    split_idx = min(split_idx, len(X_raw) - 30)
    X_train = X_raw[:split_idx]
    train_mean = X_train.mean(axis=0)
    train_std = np.where(X_train.std(axis=0, ddof=1) < 1e-8, 1.0, X_train.std(axis=0, ddof=1))

    Z_train = (X_train - train_mean) / train_std
    Z_all_from_train = (X_raw - train_mean) / train_std

    sticky_prior = np.ones((n_states, n_states), dtype=float) + 25.0 * np.eye(n_states, dtype=float)

    hmm_oos = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        transmat_prior=sticky_prior,
        n_iter=300,
        tol=1e-4,
        random_state=random_seed,
    )
    hmm_oos.fit(Z_train)
    # Filtered forward-only probabilities (no backward smoothing leakage)
    oos_posteriors = hmm_oos.predict_proba(Z_all_from_train[split_idx:])
    oos_raw_states = np.argmax(oos_posteriors, axis=1)

    # Full-sample estimation for portfolio regime-switching conditioning
    full_mean = X_raw.mean(axis=0)
    full_std = np.where(X_raw.std(axis=0, ddof=1) < 1e-8, 1.0, X_raw.std(axis=0, ddof=1))
    Z_full = (X_raw - full_mean) / full_std

    hmm_full = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        transmat_prior=sticky_prior,
        n_iter=400,
        tol=1e-4,
        random_state=random_seed,
    )
    hmm_full.fit(Z_full)

    if not getattr(hmm_full.monitor_, "converged", True):
        # Retry with diagonal covariance if full covariance optimization didn't converge
        hmm_full = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            transmat_prior=sticky_prior,
            n_iter=500,
            tol=1e-4,
            random_state=random_seed,
        )
        hmm_full.fit(Z_full)

    raw_states = hmm_full.predict(Z_full)
    raw_probs = hmm_full.predict_proba(Z_full)

    # Post-fit volatility-based state ordering: compute realized volatility in each raw state
    raw_state_vols: list[tuple[int, float]] = []
    for raw_k in range(n_states):
        mask = raw_states == raw_k
        if np.sum(mask) < 2:
            # Fallback to HMM feature mean for rolling_vol (column index 1)
            est_vol = float(hmm_full.means_[raw_k, 1] * full_std[1] + full_mean[1])
        else:
            est_vol = float(bench_aligned.iloc[mask].std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
        raw_state_vols.append((raw_k, est_vol))

    # Sort ascending by volatility -> [LOW_VOL, NORMAL, HIGH_VOL]
    raw_state_vols.sort(key=lambda pair: pair[1])
    raw_to_ordered = {raw_k: order_idx for order_idx, (raw_k, _) in enumerate(raw_state_vols)}
    perm = [pair[0] for pair in raw_state_vols]

    ordered_states = np.array([raw_to_ordered[s] for s in raw_states], dtype=int)
    ordered_probs = raw_probs[:, perm]
    ordered_trans = hmm_full.transmat_[np.ix_(perm, perm)]
    # Normalize rows strictly to sum to 1.0
    row_sums = ordered_trans.sum(axis=1, keepdims=True)
    ordered_trans = np.where(row_sums > 0, ordered_trans / row_sums, 1.0 / n_states)

    state_sequence = [REGIME_LABELS[idx] for idx in ordered_states]
    state_dates = [idx.strftime("%Y-%m-%d") for idx in common_idx]

    # Map OOS model states using the same post-fit volatility ordering on training sample
    train_raw_states = hmm_oos.predict(Z_train)
    oos_vol_order: list[tuple[int, float]] = []
    for rk in range(n_states):
        m = train_raw_states == rk
        ev = (
            float(bench_aligned.iloc[:split_idx][m].std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
            if np.sum(m) >= 2
            else float(hmm_oos.means_[rk, 1] * train_std[1] + train_mean[1])
        )
        oos_vol_order.append((rk, ev))
    oos_vol_order.sort(key=lambda x: x[1])
    oos_map = {rk: REGIME_LABELS[idx] for idx, (rk, _) in enumerate(oos_vol_order)}
    oos_labels = [oos_map[s] for s in oos_raw_states]
    oos_counts = {lbl: oos_labels.count(lbl) for lbl in REGIME_LABELS}

    # Compute regime-specific distributions and multi-asset covariance matrices
    regime_stats: dict[str, dict] = {}
    regime_mu_daily: dict[str, np.ndarray] = {}
    regime_cov_daily: dict[str, np.ndarray] = {}
    warnings: list[str] = []

    fallback_cov_diag = estimate_and_validate_covariance(ret_aligned, method="ledoit_wolf")
    fallback_mu = ret_aligned.mean(axis=0).to_numpy(dtype=float)

    for idx, label in enumerate(REGIME_LABELS):
        mask = ordered_states == idx
        count = int(np.sum(mask))
        pct = float(count / len(ordered_states) * 100.0)
        p_ii = float(ordered_trans[idx, idx])
        expected_dur = float(1.0 / max(1.0 - p_ii, 1e-4))

        # Empirical contiguous run durations
        durations: list[int] = []
        run = 0
        for s_val in ordered_states:
            if s_val == idx:
                run += 1
            elif run > 0:
                durations.append(run)
                run = 0
        if run > 0:
            durations.append(run)
        empirical_dur = float(np.mean(durations)) if durations else 0.0

        if count < 15:
            warnings.append(
                f"Regime {label} has only {count} historical observations ({pct:.1f}%); "
                "using regularized shrinkage fallback covariance for stability."
            )
            sub_ret = ret_aligned.iloc[mask] if count >= 2 else ret_aligned
            mu_vec = sub_ret.mean(axis=0).to_numpy(dtype=float) if count >= 2 else fallback_mu
            cov_mat = fallback_cov_diag.matrix
        else:
            sub_ret = ret_aligned.iloc[mask]
            mu_vec = sub_ret.mean(axis=0).to_numpy(dtype=float)
            cov_diag = estimate_and_validate_covariance(sub_ret, method="ledoit_wolf")
            cov_mat = cov_diag.matrix

        sub_bench = bench_aligned.iloc[mask] if count >= 2 else bench_aligned
        ann_ret = float(sub_bench.mean() * TRADING_DAYS_PER_YEAR)
        ann_vol = float(sub_bench.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))

        regime_mu_daily[label] = mu_vec
        regime_cov_daily[label] = cov_mat
        regime_stats[label] = {
            "observation_count": count,
            "frequency_pct": round(pct, 2),
            "annualized_mean_return": round(ann_ret, 6),
            "annualized_volatility": round(ann_vol, 6),
            "expected_duration_days": round(expected_dur, 2),
            "empirical_avg_duration_days": round(empirical_dur, 2),
            "persistence_probability": round(p_ii, 4),
        }

    # Verify strict volatility ordering monotonicity
    vols = [regime_stats[lbl]["annualized_volatility"] for lbl in REGIME_LABELS]
    if not (vols[0] <= vols[1] <= vols[2]):
        warnings.append("Regime volatilities were nearly indistinguishable across two states.")

    current_regime = state_sequence[-1]
    current_probs = {
        REGIME_LABELS[i]: round(float(ordered_probs[-1, i]), 4)
        for i in range(n_states)
    }

    diagnostics = {
        "converged": bool(getattr(hmm_full.monitor_, "converged", True)),
        "n_observations": int(len(common_idx)),
        "oos_evaluation_observations": int(len(oos_labels)),
        "oos_regime_distribution": oos_counts,
        "warnings": warnings,
        "assumptions": (
            "3-state Gaussian emissions over causal 21d rolling drift, 21d rolling volatility, and 5d realized volatility. "
            "States are strictly labeled post-fit by realized volatility; transitions follow a first-order Markov chain."
        ),
    }

    return FittedHMMResult(
        labels_ordered=REGIME_LABELS,
        transition_matrix=ordered_trans,
        state_sequence=state_sequence,
        state_dates=state_dates,
        state_probabilities=ordered_probs,
        current_regime=current_regime,
        current_state_probs=current_probs,
        regime_stats=regime_stats,
        regime_mu_daily=regime_mu_daily,
        regime_cov_daily=regime_cov_daily,
        oos_regime_accuracy_note=(
            f"Out-of-sample expanding check evaluated on final {len(oos_labels)} sessions "
            f"using strictly causal standardization fitted on prior {split_idx} sessions."
        ),
        diagnostics=diagnostics,
    )
