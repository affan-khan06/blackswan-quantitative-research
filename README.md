# BLACKSWAN — Quantifying the Uncertain

> **Regime-aware Monte Carlo portfolio risk intelligence using historical Indian market data, stochastic simulation, GARCH volatility modelling, and quantitative stress testing.**

BLACKSWAN is an institutional-grade quantitative portfolio risk research platform focused on Indian NSE markets. Rather than attempting directional stock price prediction, BLACKSWAN estimates forward loss distributions, latent volatility regimes, Euler risk contributions, crisis vulnerabilities, and out-of-sample Value at Risk calibration.

---

## Core Capabilities

- **NSE Data Engineering Pipeline**: Automated acquisition (`yfinance` + Yahoo Finance v8 Chart API), NSE market calendar holiday filtering, strict common-date inner alignment without return forward-filling, corporate-action adjusted close preservation, and per-asset `DataQualityReport` manifests.
- **Four Stochastic Simulation Engines**:
  - **Gaussian Monte Carlo**: Cholesky factorization ($\Sigma = LL^T$) with explicit PSD eigenvalue adjustment reporting.
  - **Historical Bootstrap**: Cross-sectional multivariate resampling preserving empirical fat tails and co-movement.
  - **Circular Block Bootstrap**: Contiguous block resampling ($b$-day blocks) preserving short-horizon volatility clustering.
  - **Regime-Switching Monte Carlo**: Markov-chain regime transitions coupled with regime-conditioned return distributions and a **Crisis Correlation Sensitivity Mode** ($\rho_{\text{HIGH\_VOL}} \to 0.85$).
- **Econometric Volatility & Regime Modelling**:
  - **GARCH(1,1)** via `arch` with stationarity validation ($\alpha + \beta < 1$), convergence diagnostics, and multi-step variance forecasts.
  - **3-State Gaussian HMM** via `hmmlearn` on causal features ($r_{m,t}, \sigma^{(21)}_{m,t}, |r_{m,t}|$) with strict post-fit volatility ordering into `LOW_VOL`, `NORMAL`, and `HIGH_VOL`.
- **Portfolio Risk & Euler Attribution**: Consistent positive-loss VaR & CVaR (95% and 99%), pathwise maximum drawdown distribution, downside deviation, and exact Euler volatility decomposition ($\sum_i \text{CCR}_i = \sigma_p$).
- **Stress Testing & Out-of-Sample Backtesting**: Observed historical replays (2008 GFC, 2020 COVID-19, 2022 Tightening, 2024 Election Volatility), clearly separated hypothetical shocks, and chronological walk-forward rolling VaR backtesting with **Kupiec POF** and **Christoffersen Conditional Coverage** tests.
- **Reproducible Experiment Registry & PDF Reports**: Seeded PCG64 RNGs, SQLAlchemy persistence (SQLite / PostgreSQL), experiment comparison, and downloadable ReportLab + Matplotlib PDF research reports.

---

## System Architecture

```
+---------------------------------------------------------------------------+
|           React + TypeScript + Tailwind CSS + Plotly.js Terminal          |
|  Command Center | Simulation Lab | Distribution | Regimes | Stress Lab    |
|  Model Validation | Research Reports (PDF Export)                         |
+-------------------------------------+-------------------------------------+
                                      | /api/* (Express Gateway / Nginx)
+-------------------------------------v-------------------------------------+
|                       FastAPI Quantitative Backend                        |
|  Data Pipeline   -> Research Engine -> Simulation      -> Risk & Reports  |
|  - acquisition      - analytics        - gaussian         - var / cvar    |
|  - validation       - covariance       - hist_bootstrap   - attribution   |
|  - market_calendar  - volatility       - block_bootstrap  - backtesting   |
|  - preprocessing    - regime_hmm       - regime_switching - stress tests  |
+-------------------------------------+-------------------------------------+
                                      |
                    SQLAlchemy ORM (SQLite / PostgreSQL)
```

---

## Quickstart (Local Development)

### 1. Python Backend Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend & Gateway Dependencies
```bash
npm install
```

### 3. Run Full Stack (Single Command)
```bash
npm run dev
```
This launches the FastAPI quantitative engine on port `8787` and the Vite/Express Quant Terminal on `http://localhost:3000`.

### 4. Run Backend Directly (Optional)
```bash
uvicorn backend.app.main:app --reload --port 8787
```

---

## Docker & PostgreSQL Deployment

```bash
cp .env.example .env
docker compose up --build
```
Services started:
- `postgres` (PostgreSQL 16 on port `5432`)
- `backend` (FastAPI on port `8000`)
- `frontend` (Nginx serving built React/Vite bundle on port `3000`)

---

## Testing & Verification

```bash
# Python unit & FastAPI integration suite (pytest)
.venv/bin/pytest -v

# Frontend TypeScript check & formatter unit tests
npm run lint
npx --yes tsx --test src/utils/formatters.test.ts
```

---

## Key Assumptions & Limitations

1. **No Directional Price Prediction**: Simulations quantify dispersion and tail risk under historical and econometric assumptions; they are not buy/sell signals or guaranteed forecasts.
2. **Survivorship & Structural Break Risk**: Evaluating current NSE constituents backward introduces survivorship bias; unprecedented structural shocks may exceed historical crisis magnitudes.
3. **Zero Look-Ahead Policy**: Out-of-sample HMM evaluations and rolling VaR backtests standardize features and fit parameters strictly on observations $\le t-1$.

See [`docs/RESEARCH_SPEC.md`](docs/RESEARCH_SPEC.md), [`docs/DATASET_PROVENANCE.md`](docs/DATASET_PROVENANCE.md), and [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) for full mathematical and operational details.
