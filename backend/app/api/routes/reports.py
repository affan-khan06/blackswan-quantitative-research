from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.database.repositories import (
    BacktestRepository,
    ExperimentRepository,
    StressTestRepository,
)
from backend.database.session import get_db
from backend.services.report_service import generate_experiment_pdf_report

router = APIRouter(prefix="/reports", tags=["Research Reports"])


@router.get("/{experiment_id}/pdf")
def download_pdf_report(experiment_id: str, db: Session = Depends(get_db)) -> Response:
    exp = ExperimentRepository(db).get(experiment_id)
    if not exp or exp.status != "COMPLETED":
        raise HTTPException(
            status_code=404,
            detail=f"Completed experiment '{experiment_id}' not found for report generation.",
        )

    recent_bt = BacktestRepository(db).list_recent(limit=1)
    recent_st = StressTestRepository(db).list_recent(limit=4)

    pdf_bytes = generate_experiment_pdf_report(
        experiment=exp,
        recent_backtest=recent_bt[0] if recent_bt else None,
        recent_stress_tests=recent_st,
    )

    headers = {
        "Content-Disposition": f'attachment; filename="BLACKSWAN_Report_{experiment_id}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
