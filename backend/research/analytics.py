from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS_PER_YEAR = 252


def compute_portfolio_simple_returns(
    simple_returns: pd.DataFrame,
    weights: np.ndarray,
) -> pd.Series:
    """
    Compute daily rebalanced simple portfolio returns: R_{p,t} = sum_i w_i * R_{i,t}.
    """
    arr = simple_returns.to_numpy(dtype=float) @ weights
    return pd.Series(arr, index=simple_returns.index, name="portfolio_simple_return")


def compute_portfolio_log_returns(
    simple_returns: pd.DataFrame,
    weights: np.ndarray,
) -> pd.Series:
    """
    Exact daily rebalanced portfolio log return: r_{p,t} = ln(1 + sum_i w_i * R_{i,t}).
    """
    port_simple = compute_portfolio_simple_returns(simple_returns, weights)
    if (port_simple <= -1.0).any():
        raise ValueError("Portfolio experienced <= -100% single-day return; log return undefined.")
    return np.log1p(port_simple).rename("portfolio_log_return")


def compute_drawdown_series(returns: pd.Series) -> pd.Series:
    """
    Compute cumulative wealth drawdown series DD_t = W_t / max_{s <= t} W_s - 1 <= 0.
    """
    wealth = (1.0 + returns).cumprod()
    running_peak = wealth.cummax()
    return (wealth / running_peak) - 1.0


def compute_max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float(compute_drawdown_series(returns).min())


def compute_sortino_ratio(
    simple_returns: pd.Series,
    risk_free_rate: float = 0.065,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> float:
    if simple_returns.empty:
        return 0.0
    rf_daily = (1.0 + risk_free_rate) ** (1.0 / trading_days) - 1.0
    excess = simple_returns - rf_daily
    downside = np.minimum(0.0, excess.to_numpy(dtype=float))
    downside_dev_daily = float(np.sqrt(np.mean(downside ** 2)))
    downside_dev_ann = downside_dev_daily * np.sqrt(trading_days)
    if downside_dev_ann <= 1e-12:
        return 0.0
    ann_return = float(simple_returns.mean() * trading_days)
    return float((ann_return - risk_free_rate) / downside_dev_ann)


def compute_sharpe_ratio(
    simple_returns: pd.Series,
    risk_free_rate: float = 0.065,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> float:
    if len(simple_returns) < 2:
        return 0.0
    ann_vol = float(simple_returns.std(ddof=1) * np.sqrt(trading_days))
    if ann_vol <= 1e-12:
        return 0.0
    ann_return = float(simple_returns.mean() * trading_days)
    return float((ann_return - risk_free_rate) / ann_vol)


def compute_asset_summary_metrics(
    simple_returns: pd.DataFrame,
    risk_free_rate: float = 0.065,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> list[dict]:
    summaries: list[dict] = []
    for col in simple_returns.columns:
        s = simple_returns[col].dropna()
        if len(s) < 2:
            continue
        ann_ret_arith = float(s.mean() * trading_days)
        total_growth = float((1.0 + s).prod())
        years = max(len(s) / trading_days, 1e-6)
        ann_ret_cagr = float(total_growth ** (1.0 / years) - 1.0) if total_growth > 0 else -1.0
        ann_vol = float(s.std(ddof=1) * np.sqrt(trading_days))
        mdd = compute_max_drawdown(s)
        sharpe = compute_sharpe_ratio(s, risk_free_rate, trading_days)
        sortino = compute_sortino_ratio(s, risk_free_rate, trading_days)
        skew = float(stats.skew(s, bias=False)) if len(s) > 3 else 0.0
        kurt = float(stats.kurtosis(s, fisher=True, bias=False)) if len(s) > 4 else 0.0
        summaries.append(
            {
                "symbol": str(col),
                "observations": int(len(s)),
                "annualized_return_arithmetic": round(ann_ret_arith, 6),
                "annualized_return_cagr": round(ann_ret_cagr, 6),
                "annualized_volatility": round(ann_vol, 6),
                "sharpe_ratio": round(sharpe, 4),
                "sortino_ratio": round(sortino, 4),
                "max_drawdown": round(mdd, 6),
                "skewness": round(skew, 4),
                "excess_kurtosis": round(kurt, 4),
            }
        )
    return summaries


def compute_portfolio_historical_analytics(
    simple_returns: pd.DataFrame,
    weights: np.ndarray,
    risk_free_rate: float = 0.065,
    trading_days: int = TRADING_DAYS_PER_YEAR,
    initial_capital: float = 1_000_000.0,
) -> dict:
    port_r = compute_portfolio_simple_returns(simple_returns, weights)
    wealth = initial_capital * (1.0 + port_r).cumprod()
    dd = compute_drawdown_series(port_r)

    ann_ret_arith = float(port_r.mean() * trading_days)
    total_growth = float((1.0 + port_r).prod())
    years = max(len(port_r) / trading_days, 1e-6)
    ann_ret_cagr = float(total_growth ** (1.0 / years) - 1.0) if total_growth > 0 else -1.0
    ann_vol = float(port_r.std(ddof=1) * np.sqrt(trading_days))
    rolling_21 = (port_r.rolling(21).std(ddof=1) * np.sqrt(trading_days)).dropna()
    rolling_63 = (port_r.rolling(63).std(ddof=1) * np.sqrt(trading_days)).dropna()

    # Rolling pairwise correlation against first asset / equal benchmark
    corr_matrix = simple_returns.corr().round(6)
    cov_matrix = (simple_returns.cov() * trading_days).round(8)

    # Sample rolling correlation between first two assets if >= 2 assets
    rolling_corr_series: list[dict] = []
    if simple_returns.shape[1] >= 2:
        c0, c1 = simple_returns.columns[0], simple_returns.columns[1]
        rc = simple_returns[c0].rolling(63).corr(simple_returns[c1]).dropna()
        rolling_corr_series = [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(val), 4)}
            for idx, val in rc.items()
        ]

    return {
        "observations": int(len(port_r)),
        "start_date": port_r.index.min().strftime("%Y-%m-%d"),
        "end_date": port_r.index.max().strftime("%Y-%m-%d"),
        "annualized_return_arithmetic": round(ann_ret_arith, 6),
        "annualized_return_cagr": round(ann_ret_cagr, 6),
        "annualized_volatility": round(ann_vol, 6),
        "sharpe_ratio": round(compute_sharpe_ratio(port_r, risk_free_rate, trading_days), 4),
        "sortino_ratio": round(compute_sortino_ratio(port_r, risk_free_rate, trading_days), 4),
        "max_drawdown": round(float(dd.min()), 6),
        "skewness": round(float(stats.skew(port_r, bias=False)), 4),
        "excess_kurtosis": round(float(stats.kurtosis(port_r, fisher=True, bias=False)), 4),
        "current_rolling_vol_21d": round(float(rolling_21.iloc[-1]), 6) if not rolling_21.empty else None,
        "current_rolling_vol_63d": round(float(rolling_63.iloc[-1]), 6) if not rolling_63.empty else None,
        "equity_curve": [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(val), 2)}
            for idx, val in wealth.items()
        ],
        "drawdown_curve": [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(val), 6)}
            for idx, val in dd.items()
        ],
        "rolling_vol_21d": [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(val), 6)}
            for idx, val in rolling_21.items()
        ],
        "rolling_vol_63d": [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(val), 6)}
            for idx, val in rolling_63.items()
        ],
        "rolling_correlation_pair": {
            "pair": f"{simple_returns.columns[0]} vs {simple_returns.columns[1]}"
            if simple_returns.shape[1] >= 2
            else None,
            "series": rolling_corr_series,
        },
        "correlation_matrix": {
            "symbols": list(corr_matrix.columns),
            "values": corr_matrix.to_numpy().tolist(),
        },
        "annualized_covariance_matrix": {
            "symbols": list(cov_matrix.columns),
            "values": cov_matrix.to_numpy().tolist(),
        },
        "asset_metrics": compute_asset_summary_metrics(simple_returns, risk_free_rate, trading_days),
    }
