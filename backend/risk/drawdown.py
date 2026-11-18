from __future__ import annotations

import numpy as np


def compute_simulated_risk_summary(
    portfolio_paths: np.ndarray,
    portfolio_daily_returns: np.ndarray,
    initial_capital: float,
    loss_threshold_pct: float = 0.10,
) -> dict:
    """
    Compute pathwise drawdown statistics, terminal wealth distribution summaries,
    tail probabilities, and downside deviation from simulated trajectories.
    """
    paths = np.asarray(portfolio_paths, dtype=float)
    daily_rets = np.asarray(portfolio_daily_returns, dtype=float)
    v0 = float(initial_capital)

    terminal_values = paths[:, -1]
    terminal_losses = v0 - terminal_values
    terminal_returns = (terminal_values / v0) - 1.0

    # Pathwise maximum drawdown: min_t (V_t / max_{s <= t} V_s - 1)
    running_peaks = np.maximum.accumulate(paths, axis=1)
    drawdowns = (paths / np.maximum(running_peaks, 1e-12)) - 1.0
    path_max_dd = np.min(drawdowns, axis=1)  # negative values <= 0

    # Downside deviation across simulated daily returns (MAR = 0)
    neg_rets = np.minimum(0.0, daily_rets)
    downside_dev_daily = float(np.sqrt(np.mean(neg_rets ** 2)))
    downside_dev_ann = downside_dev_daily * np.sqrt(252.0)

    # Portfolio annualized volatility across simulated paths
    sim_vol_ann = float(np.std(daily_rets, ddof=1) * np.sqrt(252.0))

    prob_negative = float(np.mean(terminal_values < v0))
    prob_exceed_loss = float(np.mean(terminal_losses > (v0 * loss_threshold_pct)))

    return {
        "initial_capital": round(v0, 2),
        "expected_terminal_value": round(float(np.mean(terminal_values)), 2),
        "median_terminal_value": round(float(np.median(terminal_values)), 2),
        "std_terminal_value": round(float(np.std(terminal_values, ddof=1)), 2),
        "min_terminal_value": round(float(np.min(terminal_values)), 2),
        "max_terminal_value": round(float(np.max(terminal_values)), 2),
        "expected_terminal_return_pct": round(float(np.mean(terminal_returns)), 6),
        "median_terminal_return_pct": round(float(np.median(terminal_returns)), 6),
        "probability_negative_return": round(prob_negative, 4),
        "loss_threshold_pct": float(loss_threshold_pct),
        "probability_exceeding_loss_threshold": round(prob_exceed_loss, 4),
        "mean_max_drawdown": round(float(np.mean(path_max_dd)), 6),
        "median_max_drawdown": round(float(np.median(path_max_dd)), 6),
        "p95_worst_max_drawdown": round(float(np.percentile(path_max_dd, 5)), 6),
        "simulated_annualized_volatility": round(sim_vol_ann, 6),
        "downside_deviation_annualized": round(float(downside_dev_ann), 6),
    }
