from __future__ import annotations

import numpy as np
from fastapi import APIRouter

from backend.data.preprocessing import align_and_clean_universe
from backend.research.analytics import compute_portfolio_historical_analytics
from backend.research.covariance import estimate_and_validate_covariance
from backend.risk.attribution import compute_euler_risk_attribution
from backend.schemas.api_models import PortfolioBaseRequest

router = APIRouter(prefix="/portfolio", tags=["Portfolio Analytics"])


@router.post("/analyze")
def analyze_portfolio(req: PortfolioBaseRequest) -> dict:
    symbols = [a.symbol.upper() for a in req.allocations]
    weights = np.array([a.weight for a in req.allocations], dtype=float)
    weights = weights / np.sum(weights)

    _, simple_rets, _, quality_report = align_and_clean_universe(
        symbols=symbols,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    simple_rets = simple_rets[symbols]

    analytics = compute_portfolio_historical_analytics(
        simple_returns=simple_rets,
        weights=weights,
        risk_free_rate=req.risk_free_rate,
        initial_capital=req.initial_capital,
    )
    cov_diag = estimate_and_validate_covariance(simple_rets, method="sample")
    attribution = compute_euler_risk_attribution(
        symbols=symbols,
        weights=weights,
        daily_cov_matrix=cov_diag.matrix,
    )

    return {
        "portfolio_composition": [
            {"symbol": s, "weight": round(float(w), 6)} for s, w in zip(symbols, weights)
        ],
        "historical_analytics": analytics,
        "covariance_diagnostics": cov_diag.to_dict(),
        "euler_risk_attribution": attribution,
        "data_provenance": quality_report.model_dump(mode="json"),
    }
