# BLACKSWAN — REST API Reference

Base URL: `/api` (proxied on `:3000` in unified dev/gateway mode; FastAPI runs on `:8787` locally or `:8000` inside Docker).

## Endpoints

- `GET /api/health` — Returns service health, model version, and database connectivity status.
- `GET /api/market-data/universe` — Lists all supported NSE indices and equities with metadata.
- `GET /api/market-data/overview?symbols=...&start_date=2016-01-01&force_refresh=false` — Acquires, validates, and summarizes NSE asset metrics plus the full `DataQualityReport`.
- `POST /api/portfolio/analyze` — Computes historical portfolio returns, Sharpe/Sortino, max drawdown, covariance diagnostics, and Euler volatility risk attribution.
- `POST /api/simulations/run` — Submits a background Monte Carlo / GARCH / HMM simulation job (`202 Accepted` with `job_id` and `experiment_id`).
- `POST /api/simulations/run-sync` — Executes the full simulation pipeline synchronously and returns the persisted experiment payload.
- `GET /api/simulations/jobs/{job_id}` — Polls background simulation execution status (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`).
- `POST /api/risk/backtest` — Executes a chronological out-of-sample rolling 1-day VaR backtest comparing Gaussian MC, Historical Bootstrap, Block Bootstrap, and Regime-Switching MC with Kupiec POF and Christoffersen CC tests.
- `GET /api/risk/backtests` — Retrieves recent persisted backtest runs.
- `GET /api/stress-testing/events` — Lists supported historical NSE crisis windows (`GFC_2008`, `COVID_2020`, `TIGHTENING_2022`, `ELECTION_2024`).
- `POST /api/stress-testing/historical` — Replays an observed historical crisis on the specified portfolio.
- `POST /api/stress-testing/hypothetical` — Evaluates a user-parameterized hypothetical shock (`broad_market_decline`, `sector_decline`, `volatility_spike`, `correlation_shock`, `combined_crisis`).
- `GET /api/experiments` / `GET /api/experiments/latest` / `GET /api/experiments/{id}` / `DELETE /api/experiments/{id}` — Experiment persistence and lifecycle management.
- `GET /api/experiments/compare?left_id=...&right_id=...` — Side-by-side experiment comparison.
- `GET /api/reports/{experiment_id}/pdf` — Streams a downloadable ReportLab + Matplotlib institutional PDF research report.
