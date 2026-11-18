from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import (
    experiments,
    health,
    market_data,
    portfolio,
    reports,
    risk,
    simulations,
    stress_testing,
)
from backend.app.core.config import get_settings
from backend.app.core.exceptions import BlackswanError
from backend.app.core.logging import logger
from backend.database.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info("BLACKSWAN database initialized and FastAPI server starting.")
    yield
    logger.info("BLACKSWAN FastAPI server shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BLACKSWAN Quantitative Risk Intelligence API",
        description=(
            "Institutional portfolio risk analytics engine for Indian NSE markets: "
            "stochastic Monte Carlo simulation, GARCH(1,1) volatility, Gaussian HMM regimes, "
            "crisis stress testing, Euler attribution, and out-of-sample VaR backtesting."
        ),
        version=settings.model_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(BlackswanError)
    async def blackswan_exception_handler(_: Request, exc: BlackswanError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "details": exc.details},
        )

    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(market_data.router, prefix=api_prefix)
    app.include_router(portfolio.router, prefix=api_prefix)
    app.include_router(simulations.router, prefix=api_prefix)
    app.include_router(risk.router, prefix=api_prefix)
    app.include_router(stress_testing.router, prefix=api_prefix)
    app.include_router(experiments.router, prefix=api_prefix)
    app.include_router(reports.router, prefix=api_prefix)

    return app


app = create_app()
