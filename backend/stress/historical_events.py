from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import numpy as np
import pandas as pd

from backend.data.preprocessing import align_and_clean_universe
from backend.research.analytics import compute_drawdown_series, compute_portfolio_simple_returns
from backend.risk.cvar import compute_cvar_from_losses
from backend.risk.var import compute_mc_var
from backend.simulation.base import RebalanceMode, SimulationConfig
from backend.simulation.gaussian import run_gaussian_monte_carlo

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class HistoricalCrisisWindow:
    event_id: str
    title: str
    start_date: date
    end_date: date
    pre_start_date: date
    pre_end_date: date
    description: str


HISTORICAL_CRISIS_CATALOG: dict[str, HistoricalCrisisWindow] = {
    "GFC_2008": HistoricalCrisisWindow(
        event_id="GFC_2008",
        title="2008 Global Financial Crisis (Lehman & Liquidity Freeze)",
        start_date=date(2008, 9, 1),
        end_date=date(2009, 3, 31),
        pre_start_date=date(2007, 9, 1),
        pre_end_date=date(2008, 8, 31),
        description=(
            "Severe global credit contraction and FII capital outflows following the Lehman Brothers "
            "collapse; NIFTY 50 experienced >50% peak-to-trough drawdown across 2008-2009."
        ),
    ),
    "COVID_2020": HistoricalCrisisWindow(
        event_id="COVID_2020",
        title="2020 COVID-19 Pandemic Market Crash",
        start_date=date(2020, 2, 19),
        end_date=date(2020, 4, 30),
        pre_start_date=date(2019, 2, 19),
        pre_end_date=date(2020, 2, 18),
        description=(
            "Rapid global liquidity shock and nationwide lockdown uncertainty in India; "
            "INDIA VIX surged above 80 and correlations spiked sharply toward 1."
        ),
    ),
    "TIGHTENING_2022": HistoricalCrisisWindow(
        event_id="TIGHTENING_2022",
        title="2022 Global Inflation & Rate Tightening Cycle",
        start_date=date(2022, 1, 17),
        end_date=date(2022, 6, 30),
        pre_start_date=date(2021, 1, 17),
        pre_end_date=date(2022, 1, 16),
        description=(
            "Aggressive Fed/RBI monetary tightening, Russia-Ukraine commodity spike, and sustained "
            "FII outflows weighing heavily on Indian IT and rate-sensitive equities."
        ),
    ),
    "ELECTION_2024": HistoricalCrisisWindow(
        event_id="ELECTION_2024",
        title="2024 Indian General Election Result Volatility",
        start_date=date(2024, 5, 15),
        end_date=date(2024, 6, 15),
        pre_start_date=date(2023, 5, 15),
        pre_end_date=date(2024, 5, 14),
        description=(
            "Event-driven implied volatility surge and June 4, 2024 single-day Indian equity "
            "shock (>5.9% NIFTY 50 drop) around Lok Sabha election counting."
        ),
    ),
}


def run_historical_crisis_replay(
    event_id: str,
    symbols: list[str],
    weights: np.ndarray,
    initial_capital: float = 1_000_000.0,
    random_seed: int = 42,
) -> dict:
    """
    Replay an observed historical NSE market crisis using actual historical observations.
    Explicitly reports insufficient coverage if any selected symbol lacks history for the window.
    """
    if event_id not in HISTORICAL_CRISIS_CATALOG:
        raise ValueError(f"Unknown historical crisis event '{event_id}'.")

    event = HISTORICAL_CRISIS_CATALOG[event_id]

    # Acquire aligned series extending back before pre_start_date
    _, simple_rets, log_rets, _ = align_and_clean_universe(
        symbols=symbols,
        start_date=event.pre_start_date,
        end_date=event.end_date,
    )

    event_mask = (simple_rets.index >= pd.Timestamp(event.start_date)) & (
        simple_rets.index <= pd.Timestamp(event.end_date)
    )
    pre_mask = (simple_rets.index >= pd.Timestamp(event.pre_start_date)) & (
        simple_rets.index <= pd.Timestamp(event.pre_end_date)
    )

    event_simple = simple_rets.loc[event_mask]
    event_log = log_rets.loc[event_mask]
    pre_simple = simple_rets.loc[pre_mask]
    pre_log = log_rets.loc[pre_mask]

    if len(event_simple) < 10 or len(pre_simple) < 30:
        return {
            "scenario_type": "HISTORICAL_OBSERVED",
            "event_id": event.event_id,
            "title": event.title,
            "coverage_status": "INSUFFICIENT_COVERAGE",
            "message": (
                f"Selected asset combination has only {len(event_simple)} aligned sessions in "
                f"[{event.start_date}, {event.end_date}] and {len(pre_simple)} pre-event sessions. "
                "Cannot perform valid historical replay without fabricating observations."
            ),
        }

    port_event = compute_portfolio_simple_returns(event_simple, weights)
    port_pre = compute_portfolio_simple_returns(pre_simple, weights)

    dd_event = compute_drawdown_series(port_event)
    observed_mdd = float(dd_event.min())
    worst_day_ret = float(port_event.min())
    worst_day_date = port_event.idxmin().strftime("%Y-%m-%d")
    cum_ret = float((1.0 + port_event).prod() - 1.0)
    crisis_value_end = float(initial_capital * (1.0 + cum_ret))
    crisis_max_loss_amt = float(initial_capital * (-observed_mdd))

    realized_vol_event = float(port_event.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    realized_vol_pre = float(port_pre.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))

    # Correlation comparison
    pre_corr = pre_simple.corr().fillna(0.0)
    event_corr = event_simple.corr().fillna(0.0)
    n_assets = len(symbols)
    if n_assets > 1:
        off_mask = ~np.eye(n_assets, dtype=bool)
        avg_corr_pre = float(np.mean(pre_corr.to_numpy()[off_mask]))
        avg_corr_event = float(np.mean(event_corr.to_numpy()[off_mask]))
    else:
        avg_corr_pre = 1.0
        avg_corr_event = 1.0

    # Compare 21-day simulated 95% VaR & CVaR parameterized before vs during crisis
    horizon = min(21, max(10, len(event_log)))
    cfg = SimulationConfig(
        symbols=symbols,
        weights=weights,
        initial_capital=initial_capital,
        horizon_days=horizon,
        n_paths=1500,
        random_seed=random_seed,
        rebalancing=RebalanceMode.DAILY,
    )
    sim_pre = run_gaussian_monte_carlo(pre_log, cfg)
    sim_during = run_gaussian_monte_carlo(event_log, cfg)
    var_pre = compute_mc_var(sim_pre.terminal_losses, initial_capital, 0.95)
    cvar_pre = compute_cvar_from_losses(sim_pre.terminal_losses, initial_capital, 0.95)
    var_during = compute_mc_var(sim_during.terminal_losses, initial_capital, 0.95)
    cvar_during = compute_cvar_from_losses(sim_during.terminal_losses, initial_capital, 0.95)

    # Asset-level impact during event
    asset_impacts: list[dict] = []
    for i, sym in enumerate(symbols):
        s_ret = event_simple[sym]
        a_cum = float((1.0 + s_ret).prod() - 1.0)
        a_mdd = float(compute_drawdown_series(s_ret).min())
        a_vol = float(s_ret.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
        weighted_pnl = float(weights[i] * a_cum * initial_capital)
        asset_impacts.append(
            {
                "symbol": sym,
                "weight": round(float(weights[i]), 4),
                "cumulative_return_pct": round(a_cum, 6),
                "max_drawdown_pct": round(a_mdd, 6),
                "realized_vol_annualized": round(a_vol, 6),
                "weighted_pnl_inr": round(weighted_pnl, 2),
            }
        )

    equity_curve = (initial_capital * (1.0 + port_event).cumprod())
    vol_ratio = realized_vol_event / max(realized_vol_pre, 1e-8)

    explanation = (
        f"During {event.title} ({len(event_simple)} trading days), the portfolio experienced a "
        f"cumulative return of {cum_ret*100:.2f}% with a peak-to-trough drawdown of {observed_mdd*100:.2f}% "
        f"(worst single session {worst_day_ret*100:.2f}% on {worst_day_date}). "
        f"Annualized realized volatility rose from {realized_vol_pre*100:.2f}% pre-crisis to "
        f"{realized_vol_event*100:.2f}% ({vol_ratio:.2f}x), while average pairwise asset correlation "
        f"shifted from {avg_corr_pre:.2f} to {avg_corr_event:.2f}."
    )

    return {
        "scenario_type": "HISTORICAL_OBSERVED",
        "coverage_status": "COMPLETE",
        "event_id": event.event_id,
        "title": event.title,
        "description": event.description,
        "event_window": {
            "start_date": event_simple.index.min().strftime("%Y-%m-%d"),
            "end_date": event_simple.index.max().strftime("%Y-%m-%d"),
            "sessions": int(len(event_simple)),
        },
        "pre_window": {
            "start_date": pre_simple.index.min().strftime("%Y-%m-%d"),
            "end_date": pre_simple.index.max().strftime("%Y-%m-%d"),
            "sessions": int(len(pre_simple)),
        },
        "portfolio_metrics": {
            "initial_capital": round(float(initial_capital), 2),
            "terminal_capital": round(crisis_value_end, 2),
            "cumulative_return_pct": round(cum_ret, 6),
            "observed_max_drawdown_pct": round(observed_mdd, 6),
            "peak_to_trough_loss_inr": round(crisis_max_loss_amt, 2),
            "worst_day_return_pct": round(worst_day_ret, 6),
            "worst_day_date": worst_day_date,
            "realized_vol_pre_annualized": round(realized_vol_pre, 6),
            "realized_vol_crisis_annualized": round(realized_vol_event, 6),
            "volatility_expansion_ratio": round(vol_ratio, 3),
            "avg_pairwise_corr_pre": round(avg_corr_pre, 4),
            "avg_pairwise_corr_crisis": round(avg_corr_event, 4),
        },
        "downside_risk_comparison": {
            "horizon_days": horizon,
            "pre_crisis_var_95_inr": var_pre["var_amount"],
            "pre_crisis_cvar_95_inr": cvar_pre["cvar_amount"],
            "crisis_var_95_inr": var_during["var_amount"],
            "crisis_cvar_95_inr": cvar_during["cvar_amount"],
        },
        "pre_correlation_matrix": {
            "symbols": list(pre_corr.columns),
            "values": pre_corr.round(4).to_numpy().tolist(),
        },
        "crisis_correlation_matrix": {
            "symbols": list(event_corr.columns),
            "values": event_corr.round(4).to_numpy().tolist(),
        },
        "asset_impacts": asset_impacts,
        "crisis_equity_curve": [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
            for idx, v in equity_curve.items()
        ],
        "crisis_drawdown_curve": [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(v), 6)}
            for idx, v in dd_event.items()
        ],
        "narrative_analysis": explanation,
    }
