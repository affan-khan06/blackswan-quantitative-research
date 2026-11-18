import type {
  AssetMetadata,
  BacktestResponse,
  ExperimentDetail,
  ExperimentSummary,
  MarketOverviewResponse,
  PortfolioAllocation,
  RebalanceMode,
  SimulationMethod,
} from '../types/quant';

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const isGet = !init?.method || init.method.toUpperCase() === 'GET';
  const maxAttempts = isGet ? 12 : 3;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
      ...init,
    });

    const contentType = res.headers.get('content-type') || '';
    if (res.status === 503 && attempt < maxAttempts - 1) {
      await new Promise((r) => setTimeout(r, 1500));
      continue;
    }

    if (!res.ok) {
      let message = `Request failed with status ${res.status}`;
      if (contentType.includes('application/json')) {
        try {
          const errBody = await res.json();
          if (typeof errBody.detail === 'string') {
            message = errBody.detail;
          } else if (Array.isArray(errBody.detail)) {
            message = errBody.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join('; ');
          }
        } catch {
          // ignore
        }
      }
      throw new Error(message);
    }

    if (!contentType.includes('application/json')) {
      throw new Error(`Expected JSON response from ${url}, received '${contentType || 'unknown'}'.`);
    }
    return res.json() as Promise<T>;
  }
  throw new Error(`Backend unavailable after ${maxAttempts} attempts.`);
}

export const api = {
  getUniverse(): Promise<{ assets: AssetMetadata[]; default_portfolio_symbols: string[] }> {
    return requestJson('/api/market-data/universe');
  },

  getMarketOverview(forceRefresh = false): Promise<MarketOverviewResponse> {
    const qs = forceRefresh ? '?force_refresh=true' : '';
    return requestJson(`/api/market-data/overview${qs}`);
  },

  getLatestExperiment(): Promise<{ experiment: ExperimentDetail | null }> {
    return requestJson('/api/experiments/latest');
  },

  listExperiments(): Promise<{ experiments: ExperimentSummary[] }> {
    return requestJson('/api/experiments');
  },

  getExperiment(id: string): Promise<ExperimentDetail> {
    return requestJson(`/api/experiments/${encodeURIComponent(id)}`);
  },

  deleteExperiment(id: string): Promise<{ deleted: boolean; id: string }> {
    return requestJson(`/api/experiments/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },

  compareExperiments(leftId: string, rightId: string): Promise<{ left: ExperimentSummary; right: ExperimentSummary }> {
    return requestJson(
      `/api/experiments/compare?left_id=${encodeURIComponent(leftId)}&right_id=${encodeURIComponent(rightId)}`
    );
  },

  launchSimulation(payload: {
    name: string;
    allocations: PortfolioAllocation[];
    start_date: string;
    initial_capital: number;
    risk_free_rate: number;
    simulation_method: SimulationMethod;
    n_paths: number;
    horizon_days: number;
    confidence_level: number;
    random_seed: number;
    rebalancing: RebalanceMode;
    transaction_cost_bps: number;
    block_length: number;
    crisis_correlation_stress: boolean;
    run_method_comparison: boolean;
  }): Promise<{
    job_id: string;
    experiment_id: string;
    status: string;
    progress_stage: string;
  }> {
    return requestJson('/api/simulations/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  pollJob(jobId: string): Promise<{
    job_id: string;
    experiment_id: string;
    status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
    progress_stage: string;
    error: string | null;
  }> {
    return requestJson(`/api/simulations/jobs/${encodeURIComponent(jobId)}`);
  },

  getStressEvents(): Promise<{
    events: Array<{
      event_id: string;
      title: string;
      start_date: string;
      end_date: string;
      description: string;
    }>;
  }> {
    return requestJson('/api/stress-testing/events');
  },

  runHistoricalStress(payload: {
    event_id: string;
    allocations: PortfolioAllocation[];
    initial_capital: number;
    random_seed?: number;
  }): Promise<Record<string, unknown>> {
    return requestJson('/api/stress-testing/historical', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  runHypotheticalStress(payload: {
    scenario_type: string;
    allocations: PortfolioAllocation[];
    start_date: string;
    initial_capital: number;
    shock_magnitude_pct: number;
    target_sector: string;
    volatility_multiplier: number;
    target_crisis_corr: number;
    horizon_days: number;
    n_paths: number;
    random_seed: number;
  }): Promise<Record<string, unknown>> {
    return requestJson('/api/stress-testing/hypothetical', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  runBacktest(payload: {
    allocations: PortfolioAllocation[];
    start_date: string;
    confidence_level: number;
    window_size: number;
    oos_sessions: number;
    mc_draws_per_step: number;
    random_seed: number;
  }): Promise<BacktestResponse> {
    return requestJson('/api/risk/backtest', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  listBacktests(): Promise<{ backtests: Array<{ id: string; created_at: string; results: BacktestResponse }> }> {
    return requestJson('/api/risk/backtests');
  },

  getReportDownloadUrl(experimentId: string): string {
    return `/api/reports/${encodeURIComponent(experimentId)}/pdf`;
  },
};
