import numpy as np
import pandas as pd
import pytest

from backend.app.core.exceptions import InsufficientDataError, NumericalStabilityError
from backend.data.preprocessing import compute_log_returns, compute_simple_returns
from backend.research.analytics import (
    compute_max_drawdown,
    compute_portfolio_simple_returns,
    compute_sharpe_ratio,
    compute_sortino_ratio,
)
from backend.research.covariance import estimate_and_validate_covariance, safe_cholesky
from backend.research.regime_detection import REGIME_LABELS, fit_market_regime_hmm
from backend.research.volatility import fit_garch_1_1


def test_simple_and_log_returns():
    dates = pd.date_range("2024-01-01", periods=4, freq="B")
    prices = pd.DataFrame({"A": [100.0, 110.0, 99.0, 108.9]}, index=dates)
    simp = compute_simple_returns(prices)
    log_r = compute_log_returns(prices)

    assert len(simp) == 3
    assert np.isclose(simp["A"].iloc[0], 0.10)
    assert np.isclose(simp["A"].iloc[1], -0.10)
    assert np.isclose(log_r["A"].iloc[0], np.log(1.10))
    assert np.allclose(np.expm1(log_r["A"].to_numpy()), simp["A"].to_numpy(), atol=1e-12)


def test_max_drawdown_exact():
    dates = pd.date_range("2024-01-01", periods=4, freq="B")
    # Wealth: 1.0 -> 1.2 -> 0.9 -> 1.08 => MDD = 0.9 / 1.2 - 1 = -0.25
    rets = pd.Series([0.20, -0.25, 0.20], index=dates[1:])
    mdd = compute_max_drawdown(rets)
    assert np.isclose(mdd, -0.25, atol=1e-12)


def test_sharpe_and_sortino_deterministic():
    rng = np.random.default_rng(123)
    dates = pd.date_range("2023-01-01", periods=300, freq="B")
    rets = pd.Series(rng.normal(0.0006, 0.01, size=300), index=dates)
    sr = compute_sharpe_ratio(rets, risk_free_rate=0.065)
    sor = compute_sortino_ratio(rets, risk_free_rate=0.065)
    assert np.isfinite(sr)
    assert np.isfinite(sor)
    # With normal-ish symmetric returns, Sortino > Sharpe is typical when mean > rf
    assert abs(sr) < 10.0


def test_covariance_psd_reporting_and_cholesky():
    # Construct a non-PSD matrix by design
    bad_cov = np.array([[1.0, 0.9, 0.9], [0.9, 1.0, -0.8], [0.9, -0.8, 1.0]])
    eigvals = np.linalg.eigvalsh(bad_cov)
    assert np.min(eigvals) < 0.0

    # Generate returns with rank deficiency (collinear columns)
    rng = np.random.default_rng(7)
    x = rng.normal(0, 0.01, size=(100, 2))
    rank_def = np.column_stack([x[:, 0], x[:, 1], x[:, 0] + x[:, 1]])
    diag = estimate_and_validate_covariance(rank_def, method="sample", min_eig_floor=1e-8)
    assert diag.psd_adjusted is True
    assert diag.adjustment_frobenius_norm > 0.0

    L, repaired, _ = safe_cholesky(diag.matrix)
    assert L.shape == (3, 3)
    assert np.allclose(L @ L.T, diag.matrix, atol=1e-10)
    assert repaired is False


def test_garch_convergence_and_insufficient_data():
    rng = np.random.default_rng(42)
    short_s = pd.Series(rng.normal(0, 0.01, size=50), index=pd.date_range("2024-01-01", periods=50, freq="B"))
    with pytest.raises(InsufficientDataError):
        fit_garch_1_1(short_s, min_observations=120)

    # Simulate GARCH-like volatility clustering series
    n = 600
    r = np.zeros(n)
    sig2 = np.zeros(n)
    sig2[0] = 0.0001
    for t in range(1, n):
        sig2[t] = 1e-6 + 0.08 * (r[t - 1] ** 2) + 0.88 * sig2[t - 1]
        r[t] = np.sqrt(sig2[t]) * rng.standard_normal()

    s = pd.Series(r, index=pd.date_range("2022-01-01", periods=n, freq="B"))
    res = fit_garch_1_1(s, forecast_horizon=10)
    assert res["model"] == "GARCH(1,1)"
    assert res["is_stationary"] is True
    assert len(res["forecast_vol_annualized"]) == 10
    assert res["current_conditional_vol_annualized"] > 0.0


def test_hmm_regime_post_fit_volatility_ordering():
    rng = np.random.default_rng(99)
    # Create 3 distinct volatility blocks
    seg1 = rng.normal(0.0005, 0.005, size=(150, 2))
    seg2 = rng.normal(0.0002, 0.012, size=(150, 2))
    seg3 = rng.normal(-0.001, 0.032, size=(150, 2))
    data = np.vstack([seg1, seg2, seg3])
    dates = pd.date_range("2022-01-01", periods=450, freq="B")
    df = pd.DataFrame(data, columns=["A", "B"], index=dates)
    bench = pd.Series(data[:, 0], index=dates)

    hmm_res = fit_market_regime_hmm(df, bench, random_seed=42)
    assert hmm_res.labels_ordered == REGIME_LABELS
    assert hmm_res.current_regime in REGIME_LABELS
    assert np.allclose(hmm_res.transition_matrix.sum(axis=1), 1.0, atol=1e-6)

    vols = [hmm_res.regime_stats[lbl]["annualized_volatility"] for lbl in REGIME_LABELS]
    assert vols[0] <= vols[1] <= vols[2]
