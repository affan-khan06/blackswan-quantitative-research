from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import uuid

import numpy as np
import pandas as pd

from backend.app.core.config import get_settings
from backend.app.core.logging import logger
from backend.data.preprocessing import align_and_clean_universe
from backend.database.models import ExperimentRecord
from backend.database.repositories import ExperimentRepository
from backend.database.session import SessionLocal
from backend.research.analytics import (
    compute_portfolio_historical_analytics,
    compute_portfolio_log_returns,
)
from backend.research.covariance import estimate_and_validate_covariance
from backend.research.distributions import analyze_return_distribution
from backend.research.regime_detection import REGIME_LABELS, fit_market_regime_hmm
from backend.research.volatility import fit_garch_1_1
from backend.risk.attribution import compute_euler_risk_attribution
from backend.risk.cvar import (
    compute_cvar_from_losses,
    compute_historical_cvar,
    compute_parametric_cvar,
)
from backend.risk.drawdown import compute_simulated_risk_summary
from backend.risk.var import (
    compute_historical_var,
    compute_mc_var,
    compute_parametric_var,
)
from backend.schemas.api_models import SimulationRequest
from backend.simulation.base import SimulationConfig, SimulationMethod, SimulationOutput
from backend.simulation.block_bootstrap import run_block_bootstrap
from backend.simulation.gaussian import run_gaussian_monte_carlo
from backend.simulation.historical_bootstrap import run_historical_bootstrap
from backend.simulation.regime_switching import run_regime_switching_monte_carlo

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="blackswan-sim")
_jobs_lock = threading.Lock()
_job_states: dict[str, dict] = {}


def _build_fan_chart_payload(paths: np.ndarray, initial_capital: float) -> dict:
    """
    Compute daily cross-sectional percentile bands (5, 25, 50, 75, 95)
    and extract 20 deterministic representative sample paths for visualization.
    """
    n_paths, n_steps = paths.shape
    days = list(range(n_steps))
    p05 = np.percentile(paths, 5, axis=0)
    p25 = np.percentile(paths, 25, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p75 = np.percentile(paths, 75, axis=0)
    p95 = np.percentile(paths, 95, axis=0)
    mean_path = np.mean(paths, axis=0)

    sample_count = min(20, n_paths)
    sample_indices = np.linspace(0, n_paths - 1, sample_count, dtype=int)
    sample_paths = [
        [round(float(v), 2) for v in paths[idx]]
        for idx in sample_indices
    ]

    return {
        "days": days,
        "initial_capital": round(float(initial_capital), 2),
        "p05": [round(float(x), 2) for x in p05],
        "p25": [round(float(x), 2) for x in p25],
        "p50": [round(float(x), 2) for x in p50],
        "p75": [round(float(x), 2) for x in p75],
        "p95": [round(float(x), 2) for x in p95],
        "mean": [round(float(x), 2) for x in mean_path],
        "sample_paths": sample_paths,
    }


def _build_histogram_payload(values: np.ndarray, n_bins: int = 45) -> dict:
    counts, edges = np.histogram(values, bins=n_bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return {
        "bin_centers": [round(float(c), 2) for c in centers],
        "bin_edges": [round(float(e), 2) for e in edges],
        "counts": [int(c) for c in counts],
    }


def _execute_simulation_pipeline(req: SimulationRequest, exp_id: str) -> dict:
    settings = get_settings()
    symbols = [a.symbol.upper() for a in req.allocations]
    weights = np.array([a.weight for a in req.allocations], dtype=float)
    weights = weights / np.sum(weights)  # Exact floating-point normalization

    # Include NIFTY50 as market benchmark anchor for HMM regime detection if not already in portfolio
    fetch_syms = list(dict.fromkeys([*symbols, "NIFTY50"]))
    _, simple_all, log_all, quality_report = align_and_clean_universe(
        symbols=fetch_syms,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    simple_port_assets = simple_all[symbols]
    log_port_assets = log_all[symbols]
    benchmark_log = log_all["NIFTY50"]

    # 1. Historical Portfolio Analytics
    historical_analytics = compute_portfolio_historical_analytics(
        simple_returns=simple_port_assets,
        weights=weights,
        risk_free_rate=req.risk_free_rate,
        initial_capital=req.initial_capital,
    )

    # 2. GARCH(1,1) Conditional Volatility on Portfolio Daily Log Returns
    port_log_series = compute_portfolio_log_returns(simple_port_assets, weights)
    garch_result = fit_garch_1_1(
        port_log_series,
        forecast_horizon=min(req.horizon_days, 63),
    )

    # 3. 3-State Gaussian HMM Regime Detection on Market Benchmark
    hmm_result = fit_market_regime_hmm(
        asset_log_returns=log_port_assets,
        benchmark_returns=benchmark_log,
        random_seed=req.random_seed,
    )

    # 4. Run Selected Simulation Methodology
    sim_cfg = SimulationConfig(
        symbols=symbols,
        weights=weights,
        initial_capital=req.initial_capital,
        horizon_days=req.horizon_days,
        n_paths=req.n_paths,
        random_seed=req.random_seed,
        rebalancing=req.rebalancing,
        transaction_cost_bps=req.transaction_cost_bps,
        block_length=req.block_length,
        crisis_correlation_stress=req.crisis_correlation_stress,
        crisis_stress_blend=req.crisis_stress_blend,
        crisis_target_corr=req.crisis_target_corr,
    )

    def _run_method(method: SimulationMethod, cfg: SimulationConfig) -> SimulationOutput:
        if method == SimulationMethod.GAUSSIAN_MC:
            return run_gaussian_monte_carlo(log_port_assets, cfg)
        if method == SimulationMethod.HISTORICAL_BOOTSTRAP:
            return run_historical_bootstrap(log_port_assets, cfg)
        if method == SimulationMethod.BLOCK_BOOTSTRAP:
            return run_block_bootstrap(log_port_assets, cfg)
        return run_regime_switching_monte_carlo(hmm_result, cfg)

    primary_sim = _run_method(req.simulation_method, sim_cfg)

    # 5. Risk Measures (Consistent positive-loss convention: L = V0 - VT)
    mc_var_95 = compute_mc_var(primary_sim.terminal_losses, req.initial_capital, 0.95)
    mc_var_99 = compute_mc_var(primary_sim.terminal_losses, req.initial_capital, 0.99)
    mc_var_selected = compute_mc_var(primary_sim.terminal_losses, req.initial_capital, req.confidence_level)

    mc_cvar_95 = compute_cvar_from_losses(primary_sim.terminal_losses, req.initial_capital, 0.95)
    mc_cvar_99 = compute_cvar_from_losses(primary_sim.terminal_losses, req.initial_capital, 0.99)
    mc_cvar_selected = compute_cvar_from_losses(primary_sim.terminal_losses, req.initial_capital, req.confidence_level)

    hist_var_95 = compute_historical_var(simple_port_assets, weights, req.initial_capital, req.horizon_days, 0.95)
    hist_var_99 = compute_historical_var(simple_port_assets, weights, req.initial_capital, req.horizon_days, 0.99)
    hist_cvar_95 = compute_historical_cvar(simple_port_assets, weights, req.initial_capital, req.horizon_days, 0.95)

    param_var_95 = compute_parametric_var(simple_port_assets, weights, req.initial_capital, req.horizon_days, 0.95)
    param_var_99 = compute_parametric_var(simple_port_assets, weights, req.initial_capital, req.horizon_days, 0.99)
    param_cvar_95 = compute_parametric_cvar(simple_port_assets, weights, req.initial_capital, req.horizon_days, 0.95)

    sim_risk_summary = compute_simulated_risk_summary(
        primary_sim.portfolio_paths,
        primary_sim.portfolio_daily_returns,
        req.initial_capital,
        loss_threshold_pct=req.loss_threshold_pct,
    )

    # 6. Euler Volatility Risk Attribution
    cov_diag = estimate_and_validate_covariance(simple_port_assets, method="sample")
    risk_attribution = compute_euler_risk_attribution(
        symbols=symbols,
        weights=weights,
        daily_cov_matrix=cov_diag.matrix,
    )

    # 7. Distribution Diagnostics
    terminal_val_dist = analyze_return_distribution(primary_sim.terminal_values)
    terminal_loss_dist = analyze_return_distribution(primary_sim.terminal_losses)

    # 8. Method Comparison & Crisis Correlation Sensitivity Experiment
    method_comparison: list[dict] = []
    if req.run_method_comparison:
        comp_n_paths = min(req.n_paths, 1500)
        for m in SimulationMethod:
            comp_cfg = SimulationConfig(
                symbols=symbols,
                weights=weights,
                initial_capital=req.initial_capital,
                horizon_days=req.horizon_days,
                n_paths=comp_n_paths,
                random_seed=req.random_seed,
                rebalancing=req.rebalancing,
                transaction_cost_bps=req.transaction_cost_bps,
                block_length=req.block_length,
                crisis_correlation_stress=False,
            )
            out_m = _run_method(m, comp_cfg)
            v95 = compute_mc_var(out_m.terminal_losses, req.initial_capital, 0.95)
            v99 = compute_mc_var(out_m.terminal_losses, req.initial_capital, 0.99)
            c95 = compute_cvar_from_losses(out_m.terminal_losses, req.initial_capital, 0.95)
            c99 = compute_cvar_from_losses(out_m.terminal_losses, req.initial_capital, 0.99)
            r_sum = compute_simulated_risk_summary(
                out_m.portfolio_paths, out_m.portfolio_daily_returns, req.initial_capital, req.loss_threshold_pct
            )
            method_comparison.append(
                {
                    "method": m.value,
                    "n_paths": comp_n_paths,
                    "expected_terminal_value": r_sum["expected_terminal_value"],
                    "var_95_inr": v95["var_amount"],
                    "cvar_95_inr": c95["cvar_amount"],
                    "var_99_inr": v99["var_amount"],
                    "cvar_99_inr": c99["cvar_amount"],
                    "p95_worst_max_drawdown": r_sum["p95_worst_max_drawdown"],
                    "prob_negative_return": r_sum["probability_negative_return"],
                }
            )

    # Regime crisis correlation sensitivity comparison (baseline vs stressed HIGH_VOL correlation)
    base_rs_cfg = SimulationConfig(
        symbols=symbols,
        weights=weights,
        initial_capital=req.initial_capital,
        horizon_days=req.horizon_days,
        n_paths=min(req.n_paths, 1500),
        random_seed=req.random_seed,
        rebalancing=req.rebalancing,
        crisis_correlation_stress=False,
    )
    stress_rs_cfg = SimulationConfig(
        symbols=symbols,
        weights=weights,
        initial_capital=req.initial_capital,
        horizon_days=req.horizon_days,
        n_paths=min(req.n_paths, 1500),
        random_seed=req.random_seed,
        rebalancing=req.rebalancing,
        crisis_correlation_stress=True,
        crisis_stress_blend=req.crisis_stress_blend,
        crisis_target_corr=req.crisis_target_corr,
    )
    rs_base_out = run_regime_switching_monte_carlo(hmm_result, base_rs_cfg)
    rs_stress_out = run_regime_switching_monte_carlo(hmm_result, stress_rs_cfg)

    crisis_sensitivity = {
        "baseline": {
            "var_95_inr": compute_mc_var(rs_base_out.terminal_losses, req.initial_capital, 0.95)["var_amount"],
            "cvar_95_inr": compute_cvar_from_losses(rs_base_out.terminal_losses, req.initial_capital, 0.95)["cvar_amount"],
            "var_99_inr": compute_mc_var(rs_base_out.terminal_losses, req.initial_capital, 0.99)["var_amount"],
            "cvar_99_inr": compute_cvar_from_losses(rs_base_out.terminal_losses, req.initial_capital, 0.99)["cvar_amount"],
        },
        "crisis_corr_stressed": {
            "var_95_inr": compute_mc_var(rs_stress_out.terminal_losses, req.initial_capital, 0.95)["var_amount"],
            "cvar_95_inr": compute_cvar_from_losses(rs_stress_out.terminal_losses, req.initial_capital, 0.95)["cvar_amount"],
            "var_99_inr": compute_mc_var(rs_stress_out.terminal_losses, req.initial_capital, 0.99)["var_amount"],
            "cvar_99_inr": compute_cvar_from_losses(rs_stress_out.terminal_losses, req.initial_capital, 0.99)["cvar_amount"],
            "diagnostics": rs_stress_out.diagnostics,
        },
    }

    # Build Regime timeline payload
    regime_timeline = [
        {
            "date": d,
            "regime": s,
            "p_low_vol": round(float(hmm_result.state_probabilities[i, 0]), 4),
            "p_normal": round(float(hmm_result.state_probabilities[i, 1]), 4),
            "p_high_vol": round(float(hmm_result.state_probabilities[i, 2]), 4),
            "benchmark_cum_return": round(float(np.exp(benchmark_log.loc[pd.Timestamp(d)]) - 1.0), 6)
            if pd.Timestamp(d) in benchmark_log.index
            else 0.0,
        }
        for i, (d, s) in enumerate(zip(hmm_result.state_dates, hmm_result.state_sequence))
    ]

    results_payload = {
        "historical_analytics": historical_analytics,
        "garch": garch_result,
        "regimes": {
            "labels": REGIME_LABELS,
            "current_regime": hmm_result.current_regime,
            "current_state_probabilities": hmm_result.current_state_probs,
            "transition_matrix": hmm_result.transition_matrix.round(4).tolist(),
            "regime_stats": hmm_result.regime_stats,
            "oos_note": hmm_result.oos_regime_accuracy_note,
            "diagnostics": hmm_result.diagnostics,
            "timeline": regime_timeline,
            "crisis_correlation_sensitivity": crisis_sensitivity,
        },
        "simulation": {
            "method": primary_sim.method.value,
            "return_convention": primary_sim.return_convention,
            "assumptions": primary_sim.assumptions,
            "diagnostics": primary_sim.diagnostics,
            "fan_chart": _build_fan_chart_payload(primary_sim.portfolio_paths, req.initial_capital),
            "terminal_value_histogram": _build_histogram_payload(primary_sim.terminal_values),
            "terminal_loss_histogram": _build_histogram_payload(primary_sim.terminal_losses),
            "terminal_value_stats": terminal_val_dist,
            "terminal_loss_stats": terminal_loss_dist,
        },
        "risk_metrics": {
            "loss_convention": "Positive loss values represent capital drawdown L = V0 - VT.",
            "selected_confidence_level": req.confidence_level,
            "monte_carlo": {
                "var_selected": mc_var_selected,
                "cvar_selected": mc_cvar_selected,
                "var_95": mc_var_95,
                "cvar_95": mc_cvar_95,
                "var_99": mc_var_99,
                "cvar_99": mc_cvar_99,
            },
            "historical": {
                "var_95": hist_var_95,
                "cvar_95": hist_cvar_95,
                "var_99": hist_var_99,
            },
            "parametric": {
                "var_95": param_var_95,
                "cvar_95": param_cvar_95,
                "var_99": param_var_99,
            },
            "summary": sim_risk_summary,
            "euler_risk_attribution": risk_attribution,
        },
        "method_comparison": method_comparison,
    }

    portfolio_comp = {
        "allocations": [{"symbol": sym, "weight": round(float(w), 6)} for sym, w in zip(symbols, weights)],
        "initial_capital": float(req.initial_capital),
        "risk_free_rate": float(req.risk_free_rate),
    }
    model_cfg = {
        "simulation_method": req.simulation_method.value,
        "n_paths": req.n_paths,
        "horizon_days": req.horizon_days,
        "confidence_level": req.confidence_level,
        "random_seed": req.random_seed,
        "rebalancing": req.rebalancing.value,
        "transaction_cost_bps": req.transaction_cost_bps,
        "block_length": req.block_length,
        "crisis_correlation_stress": req.crisis_correlation_stress,
        "crisis_stress_blend": req.crisis_stress_blend,
        "crisis_target_corr": req.crisis_target_corr,
        "loss_threshold_pct": req.loss_threshold_pct,
    }

    return {
        "id": exp_id,
        "name": req.name,
        "data_start_date": str(quality_report.common_start_date),
        "data_end_date": str(quality_report.common_end_date),
        "model_version": settings.model_version,
        "portfolio_composition": portfolio_comp,
        "model_configuration": model_cfg,
        "data_provenance": quality_report.model_dump(mode="json"),
        "results": results_payload,
    }


def _background_job_runner(job_id: str, exp_id: str, req: SimulationRequest) -> None:
    with _jobs_lock:
        _job_states[job_id] = {
            "job_id": job_id,
            "experiment_id": exp_id,
            "status": "RUNNING",
            "progress_stage": "Acquiring & validating NSE market data, fitting GARCH/HMM, and simulating paths...",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "error": None,
        }
    db = SessionLocal()
    repo = ExperimentRepository(db)
    try:
        output = _execute_simulation_pipeline(req, exp_id)
        rec = repo.get(exp_id)
        if rec:
            rec.status = "COMPLETED"
            rec.data_start_date = output["data_start_date"]
            rec.data_end_date = output["data_end_date"]
            rec.data_provenance = output["data_provenance"]
            rec.results = output["results"]
            repo.update(rec)
        with _jobs_lock:
            _job_states[job_id]["status"] = "COMPLETED"
            _job_states[job_id]["progress_stage"] = "Completed"
            _job_states[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"Completed simulation experiment {exp_id}",
            extra={"extra_data": {"experiment_id": exp_id, "method": req.simulation_method.value}},
        )
    except Exception as exc:
        logger.exception(f"Simulation experiment {exp_id} failed: {exc}")
        rec = repo.get(exp_id)
        if rec:
            rec.status = "FAILED"
            rec.error_message = str(exc)
            repo.update(rec)
        with _jobs_lock:
            _job_states[job_id]["status"] = "FAILED"
            _job_states[job_id]["error"] = str(exc)
            _job_states[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        db.close()


def submit_simulation_job(req: SimulationRequest) -> dict:
    settings = get_settings()
    exp_id = f"exp_{uuid.uuid4().hex[:12]}"
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    symbols = [a.symbol.upper() for a in req.allocations]
    weights = np.array([a.weight for a in req.allocations], dtype=float)
    weights = weights / np.sum(weights)

    db = SessionLocal()
    try:
        repo = ExperimentRepository(db)
        pending_record = ExperimentRecord(
            id=exp_id,
            name=req.name,
            status="RUNNING",
            simulation_method=req.simulation_method.value,
            n_paths=req.n_paths,
            horizon_days=req.horizon_days,
            confidence_level=req.confidence_level,
            initial_capital=req.initial_capital,
            random_seed=req.random_seed,
            data_start_date=req.start_date.isoformat(),
            data_end_date=(req.end_date or datetime.now(timezone.utc).date()).isoformat(),
            model_version=settings.model_version,
            portfolio_composition={
                "allocations": [{"symbol": s, "weight": round(float(w), 6)} for s, w in zip(symbols, weights)],
                "initial_capital": float(req.initial_capital),
                "risk_free_rate": float(req.risk_free_rate),
            },
            model_configuration=req.model_dump(mode="json", exclude={"allocations", "name"}),
            data_provenance={},
            results={},
        )
        repo.create(pending_record)
    finally:
        db.close()

    with _jobs_lock:
        _job_states[job_id] = {
            "job_id": job_id,
            "experiment_id": exp_id,
            "status": "QUEUED",
            "progress_stage": "Queued for execution",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "error": None,
        }

    _executor.submit(_background_job_runner, job_id, exp_id, req)
    return _job_states[job_id]


def run_simulation_sync(req: SimulationRequest) -> ExperimentRecord:
    """Synchronous helper used in integration tests and direct script execution."""
    exp_id = f"exp_{uuid.uuid4().hex[:12]}"
    output = _execute_simulation_pipeline(req, exp_id)
    db = SessionLocal()
    try:
        repo = ExperimentRepository(db)
        rec = ExperimentRecord(
            id=exp_id,
            name=req.name,
            status="COMPLETED",
            simulation_method=req.simulation_method.value,
            n_paths=req.n_paths,
            horizon_days=req.horizon_days,
            confidence_level=req.confidence_level,
            initial_capital=req.initial_capital,
            random_seed=req.random_seed,
            data_start_date=output["data_start_date"],
            data_end_date=output["data_end_date"],
            model_version=output["model_version"],
            portfolio_composition=output["portfolio_composition"],
            model_configuration=output["model_configuration"],
            data_provenance=output["data_provenance"],
            results=output["results"],
        )
        return repo.create(rec)
    finally:
        db.close()


def get_job_status(job_id: str) -> dict | None:
    with _jobs_lock:
        return _job_states.get(job_id)
