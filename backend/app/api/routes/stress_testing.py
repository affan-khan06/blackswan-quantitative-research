from __future__ import annotations

import uuid
import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.data.preprocessing import align_and_clean_universe
from backend.database.models import StressTestRecord
from backend.database.repositories import StressTestRepository
from backend.database.session import get_db
from backend.schemas.api_models import HistoricalStressRequest, HypotheticalStressRequest
from backend.stress.historical_events import HISTORICAL_CRISIS_CATALOG, run_historical_crisis_replay
from backend.stress.hypothetical import run_hypothetical_stress_test

router = APIRouter(prefix="/stress-testing", tags=["Stress Testing"])


@router.get("/events")
def list_historical_events() -> dict:
    return {
        "events": [
            {
                "event_id": ev.event_id,
                "title": ev.title,
                "start_date": ev.start_date.isoformat(),
                "end_date": ev.end_date.isoformat(),
                "description": ev.description,
            }
            for ev in HISTORICAL_CRISIS_CATALOG.values()
        ]
    }


@router.post("/historical")
def run_historical_stress(req: HistoricalStressRequest, db: Session = Depends(get_db)) -> dict:
    symbols = [a.symbol.upper() for a in req.allocations]
    weights = np.array([a.weight for a in req.allocations], dtype=float)
    weights = weights / np.sum(weights)

    result = run_historical_crisis_replay(
        event_id=req.event_id,
        symbols=symbols,
        weights=weights,
        initial_capital=req.initial_capital,
        random_seed=req.random_seed,
    )

    st_id = f"st_{uuid.uuid4().hex[:12]}"
    comp = {"allocations": [{"symbol": s, "weight": round(float(w), 6)} for s, w in zip(symbols, weights)]}
    rec = StressTestRecord(
        id=st_id,
        scenario_type="HISTORICAL_OBSERVED",
        scenario_name=req.event_id,
        portfolio_composition=comp,
        results=result,
    )
    StressTestRepository(db).create(rec)
    return {"id": st_id, "created_at": rec.created_at.isoformat(), **result}


@router.post("/hypothetical")
def run_hypothetical_stress(req: HypotheticalStressRequest, db: Session = Depends(get_db)) -> dict:
    symbols = [a.symbol.upper() for a in req.allocations]
    weights = np.array([a.weight for a in req.allocations], dtype=float)
    weights = weights / np.sum(weights)

    _, _, log_rets, _ = align_and_clean_universe(
        symbols=symbols,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    result = run_hypothetical_stress_test(
        scenario_type=req.scenario_type,
        symbols=symbols,
        weights=weights,
        asset_log_returns=log_rets[symbols],
        initial_capital=req.initial_capital,
        shock_magnitude_pct=req.shock_magnitude_pct,
        target_sector=req.target_sector,
        volatility_multiplier=req.volatility_multiplier,
        target_crisis_corr=req.target_crisis_corr,
        horizon_days=req.horizon_days,
        n_paths=req.n_paths,
        random_seed=req.random_seed,
    )

    st_id = f"st_{uuid.uuid4().hex[:12]}"
    comp = {"allocations": [{"symbol": s, "weight": round(float(w), 6)} for s, w in zip(symbols, weights)]}
    rec = StressTestRecord(
        id=st_id,
        scenario_type="HYPOTHETICAL",
        scenario_name=req.scenario_type.value,
        portfolio_composition=comp,
        results=result,
    )
    StressTestRepository(db).create(rec)
    return {"id": st_id, "created_at": rec.created_at.isoformat(), **result}


@router.get("/history")
def list_stress_tests(db: Session = Depends(get_db)) -> dict:
    records = StressTestRepository(db).list_recent(limit=20)
    return {
        "stress_tests": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "scenario_type": r.scenario_type,
                "scenario_name": r.scenario_name,
                "portfolio_composition": r.portfolio_composition,
                "results": r.results,
            }
            for r in records
        ]
    }
