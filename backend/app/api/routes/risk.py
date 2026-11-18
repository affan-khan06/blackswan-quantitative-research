from __future__ import annotations

import uuid
import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.data.preprocessing import align_and_clean_universe
from backend.database.models import BacktestRecord
from backend.database.repositories import BacktestRepository
from backend.database.session import get_db
from backend.risk.backtesting import run_rolling_var_backtest
from backend.schemas.api_models import BacktestRequest

router = APIRouter(prefix="/risk", tags=["Risk & Backtesting"])


@router.post("/backtest")
def execute_var_backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> dict:
    symbols = [a.symbol.upper() for a in req.allocations]
    weights = np.array([a.weight for a in req.allocations], dtype=float)
    weights = weights / np.sum(weights)

    fetch_syms = list(dict.fromkeys([*symbols, "NIFTY50"]))
    _, simple_all, log_all, _ = align_and_clean_universe(
        symbols=fetch_syms,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    result = run_rolling_var_backtest(
        asset_log_returns=log_all[symbols],
        asset_simple_returns=simple_all[symbols],
        benchmark_log_returns=log_all["NIFTY50"],
        weights=weights,
        confidence_level=req.confidence_level,
        window_size=req.window_size,
        oos_sessions=req.oos_sessions,
        mc_draws_per_step=req.mc_draws_per_step,
        random_seed=req.random_seed,
    )

    bt_id = f"bt_{uuid.uuid4().hex[:12]}"
    comp = {
        "allocations": [{"symbol": s, "weight": round(float(w), 6)} for s, w in zip(symbols, weights)],
    }
    rec = BacktestRecord(
        id=bt_id,
        confidence_level=req.confidence_level,
        oos_sessions=result["observations"],
        portfolio_composition=comp,
        results=result,
    )
    BacktestRepository(db).create(rec)

    return {
        "id": bt_id,
        "created_at": rec.created_at.isoformat(),
        "portfolio_composition": comp,
        **result,
    }


@router.get("/backtests")
def list_backtests(db: Session = Depends(get_db)) -> dict:
    records = BacktestRepository(db).list_recent(limit=10)
    return {
        "backtests": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "confidence_level": r.confidence_level,
                "oos_sessions": r.oos_sessions,
                "portfolio_composition": r.portfolio_composition,
                "results": r.results,
            }
            for r in records
        ]
    }
