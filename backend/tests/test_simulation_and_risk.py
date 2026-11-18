import numpy as np
import pandas as pd

from backend.research.regime_detection import fit_market_regime_hmm
from backend.risk.attribution import compute_euler_risk_attribution
from backend.risk.backtesting import christoffersen_cc_test, kupiec_pof_test
from backend.risk.cvar import compute_cvar_from_losses
from backend.risk.drawdown import compute_simulated_risk_summary
from backend.risk.var import compute_mc_var
from backend.simulation.base import RebalanceMode, SimulationConfig
from backend.simulation.block_bootstrap import run_block_bootstrap
from backend.simulation.gaussian import run_gaussian_monte_carlo
from backend.simulation.historical_bootstrap import run_historical_bootstrap
from backend.simulation.regime_switching import run_regime_switching_monte_carlo


def _synthetic_log_returns(n_days: int = 400, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cov = np.array(
        [
            [0.00018, 0.00010, 0.00006],
            [0.00010, 0.00025, 0.00008],
            [0.00006, 0.00008, 0.00014],
        ]
    )
    mu = np.array([0.0004, 0.0005, 0.0003])
    draws = rng.multivariate_normal(mu, cov, size=n_days)
    dates = pd.date_range("2023-01-02", periods=n_days, freq="B")
    return pd.DataFrame(draws, columns=["A", "B", "C"], index=dates)


def test_simulation_dimensions_and_reproducibility():
    df = _synthetic_log_returns()
    weights = np.array([0.5, 0.3, 0.2])
    cfg = SimulationConfig(
        symbols=["A", "B", "C"],
        weights=weights,
        initial_capital=1_000_000.0,
        horizon_days=30,
        n_paths=500,
        random_seed=777,
        rebalancing=RebalanceMode.DAILY,
    )

    g1 = run_gaussian_monte_carlo(df, cfg)
    g2 = run_gaussian_monte_carlo(df, cfg)
    assert g1.portfolio_paths.shape == (500, 31)
    assert g1.portfolio_daily_returns.shape == (500, 30)
    assert np.allclose(g1.portfolio_paths, g2.portfolio_paths, atol=1e-12)
    assert np.all(g1.portfolio_paths > 0.0)

    hb1 = run_historical_bootstrap(df, cfg)
    hb2 = run_historical_bootstrap(df, cfg)
    assert hb1.portfolio_paths.shape == (500, 31)
    assert np.allclose(hb1.terminal_values, hb2.terminal_values, atol=1e-12)

    bb = run_block_bootstrap(df, cfg)
    assert bb.portfolio_paths.shape == (500, 31)

    hmm = fit_market_regime_hmm(df, df["A"], random_seed=42)
    rs1 = run_regime_switching_monte_carlo(hmm, cfg)
    rs2 = run_regime_switching_monte_carlo(hmm, cfg)
    assert rs1.portfolio_paths.shape == (500, 31)
    assert np.allclose(rs1.terminal_values, rs2.terminal_values, atol=1e-12)


def test_var_cvar_invariant_and_drawdown_summary():
    df = _synthetic_log_returns()
    weights = np.array([0.4, 0.4, 0.2])
    cfg = SimulationConfig(
        symbols=["A", "B", "C"],
        weights=weights,
        initial_capital=1_000_000.0,
        horizon_days=21,
        n_paths=1000,
        random_seed=42,
    )
    out = run_gaussian_monte_carlo(df, cfg)

    var95 = compute_mc_var(out.terminal_losses, 1_000_000.0, 0.95)
    cvar95 = compute_cvar_from_losses(out.terminal_losses, 1_000_000.0, 0.95)
    var99 = compute_mc_var(out.terminal_losses, 1_000_000.0, 0.99)
    cvar99 = compute_cvar_from_losses(out.terminal_losses, 1_000_000.0, 0.99)

    assert cvar95["cvar_amount"] >= var95["var_amount"]
    assert cvar99["cvar_amount"] >= var99["var_amount"]
    assert var99["var_amount"] >= var95["var_amount"]

    summary = compute_simulated_risk_summary(out.portfolio_paths, out.portfolio_daily_returns, 1_000_000.0)
    assert summary["p95_worst_max_drawdown"] <= 0.0
    assert 0.0 <= summary["probability_negative_return"] <= 1.0


def test_euler_risk_attribution_reconciliation():
    df = _synthetic_log_returns()
    weights = np.array([0.45, 0.35, 0.20])
    cov = df.cov()
    attr = compute_euler_risk_attribution(["A", "B", "C"], weights, cov)

    assert attr["reconciled"] is True
    assert attr["reconciliation_error"] < 1e-8
    pct_sum = sum(a["pct_risk_contribution"] for a in attr["assets"])
    assert np.isclose(pct_sum, 100.0, atol=0.05)


def test_kupiec_and_christoffersen_backtest_math():
    # Exact 5% violations on 200 days => 10 violations -> should pass Kupiec
    pof_ok = kupiec_pof_test(violations=10, observations=200, alpha=0.95)
    assert pof_ok["rejected_at_5pct"] is False
    assert pof_ok["p_value"] > 0.90

    # Gross under-coverage: 35 violations on 200 days (17.5% vs 5%) -> should reject
    pof_bad = kupiec_pof_test(violations=35, observations=200, alpha=0.95)
    assert pof_bad["rejected_at_5pct"] is True
    assert pof_bad["p_value"] < 0.01

    # Clustered violations: 10 consecutive violations -> Christoffersen independence rejects
    seq = np.zeros(200, dtype=int)
    seq[50:60] = 1
    cc_clustered = christoffersen_cc_test(seq, alpha=0.95)
    assert cc_clustered["lr_ind"] > 10.0
    assert cc_clustered["cc_rejected_at_5pct"] is True
