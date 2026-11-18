# BLACKSWAN — Research Specification & Mathematical Architecture

## 1. Product Vision & Scope
BLACKSWAN is an institutional-grade quantitative portfolio risk intelligence system designed primarily for Indian financial markets (NSE indices and liquid equities). It integrates historical market data engineering, econometric volatility modelling (GARCH), latent state detection (Gaussian HMM), correlated stochastic simulation, Euler risk attribution, historical & hypothetical stress testing, and chronological out-of-sample VaR backtesting.

BLACKSWAN does **not** forecast directional asset prices. It estimates the distribution of potential portfolio outcomes, tail losses, and regime vulnerabilities under explicitly documented statistical assumptions.

## 2. System Architecture

```
+-------------------------------------------------------------------------+
|                   React + TypeScript + Vite + Plotly.js                 |
|  Command Center | Simulation Lab | Distribution | Regimes | Stress |    |
|  Model Validation | Research Reports (PDF Export)                       |
+------------------------------------+------------------------------------+
                                     | REST JSON / PDF Stream (/api/*)
+------------------------------------v------------------------------------+
|                         FastAPI Backend (Python)                        |
|  API Routes -> Services -> Background Simulation Executor               |
|  +--------------+  +--------------+  +--------------+  +--------------+ |
|  | Data Pipeline|  | Quant Engine |  | Simulation   |  | Risk & Back- | |
|  | acquisition  |  | analytics    |  | gaussian     |  | testing      | |
|  | validation   |  | covariance   |  | hist_boot    |  | var / cvar   | |
|  | preprocessing|  | volatility   |  | block_boot   |  | attribution  | |
|  | calendar     |  | hmm regimes  |  | regime_mc    |  | stress tests | |
|  +--------------+  +--------------+  +--------------+  +--------------+ |
|                                    |                                    |
|                 SQLAlchemy ORM (SQLite / PostgreSQL)                    |
|              Raw Cache (data/raw/) & Cleaned (data/processed/)          |
+-------------------------------------------------------------------------+
```

## 3. Dataset Acquisition & Leakage-Free Preprocessing
- **Primary Universe (NSE via Yahoo Finance Chart/yfinance)**:
  - Indices: `^NSEI` (NIFTY 50), `^NSEBANK` (NIFTY BANK), `^CNXIT` (NIFTY IT), `^CNXAUTO` (NIFTY AUTO), `^INDIAVIX` (INDIA VIX)
  - Liquid Equities: `RELIANCE.NS`, `HDFCBANK.NS`, `ICICIBANK.NS`, `INFY.NS`, `TCS.NS`, `LT.NS`, `ITC.NS`, `BHARTIARTL.NS`, `SBIN.NS`, `M&M.NS`
- **Separation of Raw and Cleaned Storage**: Raw OHLCV snapshots are cached under `data/raw/` with retrieval timestamp and provenance. Cleaned, date-aligned price and return matrices are stored under `data/processed/` alongside `data/manifest.json`.
- **Integrity Rules**:
  1. Never forward-fill returns across missing dates.
  2. Distinguish NSE trading holidays from genuine missing asset observations using `market_calendar.py` and benchmark session presence.
  3. Preserve adjusted close (`adj_close`) for split/dividend continuity; validate `price > 0`, `volume >= 0`, and flag duplicate timestamps or >40% single-day jumps for audit.
  4. Chronological splits only: all rolling windows, GARCH fits, HMM fits, and out-of-sample backtests strictly prohibit future data leakage.

## 4. Mathematical Definitions

### 4.1 Return & Summary Conventions
- **Simple Return**: $R_t = \frac{P_t - P_{t-1}}{P_{t-1}}$
- **Logarithmic Return**: $r_t = \ln\left(\frac{P_t}{P_{t-1}}\right)$
- **Annualization**: $T_y = 252$ NSE trading days/year; $\mu_{\text{ann}} = \bar{R} \cdot 252$ (arithmetic) or $(1+\bar{R})^{252}-1$ (compounded, explicitly labelled); $\sigma_{\text{ann}} = \sigma_{\text{daily}} \sqrt{252}$.
- **Sharpe Ratio**: $\text{SR} = \frac{\mu_{\text{ann}} - r_f}{\sigma_{\text{ann}}}$, default $r_f = 6.5\%$ (India 91-day T-bill proxy).
- **Sortino Ratio**: $\text{SoR} = \frac{\mu_{\text{ann}} - r_f}{\sigma_{\text{down, ann}}}$, where $\sigma_{\text{down, daily}} = \sqrt{\frac{1}{N}\sum_{t=1}^N \min(0, R_t - r_{f,\text{daily}})^2}$.
- **Maximum Drawdown**: $\text{MDD} = \min_{t} \left(\frac{V_t}{\max_{s \le t} V_s} - 1\right)$.

### 4.2 Covariance & Positive Semi-Definite (PSD) Handling
Given sample covariance $\Sigma$, if $\lambda_{\min}(\Sigma) < 10^{-10}$, BLACKSWAN applies eigenvalue clipping $\tilde{\lambda}_i = \max(\lambda_i, \epsilon)$ with $\epsilon = 10^{-8}$, reconstructs $\tilde{\Sigma} = Q \operatorname{diag}(\tilde{\lambda}) Q^T$, and **explicitly reports** the minimum original eigenvalue and adjustment magnitude in model diagnostics.

### 4.3 Stochastic Simulation Methodologies
All return generators use reproducible `PCG64(seed)` RNGs and explicitly document log-return compounding $V_t = V_{t-1} \exp(w^T r_t)$ (or daily rebalanced arithmetic return $V_t = V_{t-1}(1 + w^T R_t)$ with optional transaction cost deduction on rebalance).
1. **Gaussian Monte Carlo**: $\tilde{\Sigma} = L L^T$, $Z \sim \mathcal{N}(0, I)$, $r_t = \mu + L Z$.
2. **Historical Bootstrap**: IID resampling of observed historical multivariate return rows $r_{\tau_t}$ preserving cross-sectional dependence.
3. **Circular Block Bootstrap**: Resampling contiguous blocks of length $b$ (default $b = 10$ days) to preserve short-horizon volatility clustering and autocorrelation.
4. **Regime-Switching Monte Carlo**: At each step $t$, draw $s_t \sim P(s_{t-1}, \cdot)$ from the fitted 3-state HMM transition matrix, then sample $r_t \sim \mathcal{N}(\mu_{s_t}, \Sigma_{s_t})$. Includes a **Crisis Correlation Sensitivity Mode** that stresses off-diagonal correlations in `HIGH_VOL` toward $\rho_{\text{stress}}$.

### 4.4 GARCH(1,1) Volatility Modelling
$$\sigma_t^2 = \omega + \alpha \varepsilon_{t-1}^2 + \beta \sigma_{t-1}^2, \quad \omega > 0,\ \alpha \ge 0,\ \beta \ge 0,\ \alpha + \beta < 1$$
Estimated via MLE (`arch`), reporting convergence status, persistence $\alpha + \beta$, unconditional variance $\frac{\omega}{1 - \alpha - \beta}$, and $h$-step-ahead conditional volatility forecasts.

### 4.5 Gaussian Hidden Markov Model (3-State)
Observations $x_t = [r_{m,t},\ \sigma^{(21)}_{m,t},\ |r_{m,t}|]$ standardized strictly on the training sample. States are **ordered post-fit** by estimated return-volatility $\hat{\sigma}_s$ into `LOW_VOL`, `NORMAL`, and `HIGH_VOL`.

### 4.6 Risk Metrics & Euler Attribution
- **Loss Convention**: $L = V_0 - V_T$ (positive values indicate capital loss).
- **Value at Risk ($\text{VaR}_\alpha$)**: $(1-\alpha)$ quantile of portfolio loss distribution ($\alpha \in \{0.95, 0.99\}$).
- **Conditional Value at Risk ($\text{CVaR}_\alpha$)**: $\mathbb{E}[L \mid L \ge \text{VaR}_\alpha]$.
- **Euler Volatility Attribution**:
  $$\sigma_p = \sqrt{w^T \Sigma w}, \quad \text{MCR}_i = \frac{(\Sigma w)_i}{\sigma_p}, \quad \text{CCR}_i = w_i \cdot \text{MCR}_i, \quad \sum_{i=1}^n \text{CCR}_i = \sigma_p$$

### 4.7 Out-of-Sample VaR Backtesting
Chronological expanding/rolling window estimation (minimum 252 trading days warmup). For each out-of-sample day $t$, 1-day VaR is estimated using **only observations $\le t-1$** and compared against realized loss $L_t$:
- **Kupiec POF Test**: $LR_{\text{POF}} = -2 \ln \left[\frac{(1-p)^{T-x} p^x}{(1-\hat{p})^{T-x} \hat{p}^x}\right] \sim \chi^2_1$
- **Christoffersen Conditional Coverage Test**: $LR_{\text{CC}} = LR_{\text{POF}} + LR_{\text{IND}} \sim \chi^2_2$ testing both unconditional frequency and independence of consecutive violations.

## 5. Limitations & Assumptions
- Equity return distributions exhibit fat tails, skewness, and volatility clustering; Gaussian MC systematically underestimates tail risk during market crises.
- Historical crisis replays (e.g., 2020 COVID-19) reflect past market microstructure and may not bound future tail shocks.
- Yahoo Finance adjusted close prices rely on upstream corporate action adjustments; survivorship bias exists when analysing currently listed NIFTY constituents backward in time.
