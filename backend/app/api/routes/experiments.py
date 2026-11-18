from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.repositories import ExperimentRepository
from backend.database.session import get_db

router = APIRouter(prefix="/experiments", tags=["Experiments"])


def _serialize_summary(r) -> dict:
    risk = (r.results or {}).get("risk_metrics", {})
    mc = risk.get("monte_carlo", {})
    summary = risk.get("summary", {})
    regimes = (r.results or {}).get("regimes", {})
    garch = (r.results or {}).get("garch", {})
    return {
        "id": r.id,
        "name": r.name,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
        "simulation_method": r.simulation_method,
        "n_paths": r.n_paths,
        "horizon_days": r.horizon_days,
        "confidence_level": r.confidence_level,
        "initial_capital": r.initial_capital,
        "random_seed": r.random_seed,
        "data_start_date": r.data_start_date,
        "data_end_date": r.data_end_date,
        "model_version": r.model_version,
        "portfolio_composition": r.portfolio_composition,
        "model_configuration": r.model_configuration,
        "error_message": r.error_message,
        "headline_metrics": {
            "var_95_inr": mc.get("var_95", {}).get("var_amount"),
            "cvar_95_inr": mc.get("cvar_95", {}).get("cvar_amount"),
            "var_99_inr": mc.get("var_99", {}).get("var_amount"),
            "cvar_99_inr": mc.get("cvar_99", {}).get("cvar_amount"),
            "expected_terminal_value": summary.get("expected_terminal_value"),
            "current_regime": regimes.get("current_regime"),
            "garch_vol_ann": garch.get("current_conditional_vol_annualized"),
        },
    }


@router.get("")
def list_experiments(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> dict:
    records = ExperimentRepository(db).list_all(limit=limit)
    return {"experiments": [_serialize_summary(r) for r in records]}


@router.get("/latest")
def get_latest_experiment(db: Session = Depends(get_db)) -> dict:
    rec = ExperimentRepository(db).get_latest_completed()
    if not rec:
        return {"experiment": None}
    return {
        "experiment": {
            **_serialize_summary(rec),
            "data_provenance": rec.data_provenance,
            "results": rec.results,
        }
    }


@router.get("/compare")
def compare_experiments(
    left_id: str = Query(...),
    right_id: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    repo = ExperimentRepository(db)
    left = repo.get(left_id)
    right = repo.get(right_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="One or both experiment IDs were not found.")
    return {
        "left": _serialize_summary(left),
        "right": _serialize_summary(right),
    }


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    rec = ExperimentRepository(db).get(experiment_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return {
        **_serialize_summary(rec),
        "data_provenance": rec.data_provenance,
        "results": rec.results,
    }


@router.delete("/{experiment_id}")
def delete_experiment(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    deleted = ExperimentRepository(db).delete(experiment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return {"deleted": True, "id": experiment_id}
