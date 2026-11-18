from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.api_models import SimulationRequest
from backend.services.experiment_service import (
    get_job_status,
    run_simulation_sync,
    submit_simulation_job,
)

router = APIRouter(prefix="/simulations", tags=["Simulations"])


@router.post("/run", status_code=202)
def launch_simulation(req: SimulationRequest) -> dict:
    """
    Enqueue a Monte Carlo / GARCH / HMM simulation job in the worker pool
    and return job_id and experiment_id immediately.
    """
    return submit_simulation_job(req)


@router.post("/run-sync")
def launch_simulation_sync(req: SimulationRequest) -> dict:
    """
    Execute simulation synchronously and return full persisted experiment payload.
    """
    rec = run_simulation_sync(req)
    return {
        "id": rec.id,
        "name": rec.name,
        "status": rec.status,
        "created_at": rec.created_at.isoformat(),
        "simulation_method": rec.simulation_method,
        "n_paths": rec.n_paths,
        "horizon_days": rec.horizon_days,
        "confidence_level": rec.confidence_level,
        "initial_capital": rec.initial_capital,
        "random_seed": rec.random_seed,
        "data_start_date": rec.data_start_date,
        "data_end_date": rec.data_end_date,
        "model_version": rec.model_version,
        "portfolio_composition": rec.portfolio_composition,
        "model_configuration": rec.model_configuration,
        "data_provenance": rec.data_provenance,
        "results": rec.results,
    }


@router.get("/jobs/{job_id}")
def poll_simulation_job(job_id: str) -> dict:
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Simulation job '{job_id}' not found.")
    return job
