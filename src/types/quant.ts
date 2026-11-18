export type SimulationMethod =
  | 'gaussian_mc'
  | 'historical_bootstrap'
  | 'block_bootstrap'
  | 'regime_switching_mc';

export type RebalanceMode = 'daily' | 'buy_and_hold';

export type ViewId =
  | 'command-center'
  | 'simulation-lab'
  | 'distribution-analytics'
  | 'regime-intelligence'
  | 'stress-testing'
  | 'model-validation'
  | 'research-reports';

export interface AssetMetadata {
  symbol: string;
  yahoo_ticker: string;
  name: string;
  exchange: string;
  currency: string;
  category: 'INDEX' | 'SECTOR_INDEX' | 'VOLATILITY_INDEX' | 'EQUITY';
  sector: string;
  description: string;
}

export interface PortfolioAllocation {
  symbol: string;
  weight: number;
}

export interface AssetMetricSummary {
  symbol: string;
  observations: number;
  annualized_return_arithmetic: number;
  annualized_return_cagr: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  skewness: number;
  excess_kurtosis: number;
}

export interface DatasetManifestEntry {
  symbol: string;
  yahoo_ticker: string;
  name: string;
  exchange: string;
  category: string;
  sector: string;
  start_date: string | null;
  end_date: string | null;
  observation_count: number;
  expected_trading_days: number;
  missing_observations: number;
  missing_observation_pct: number;
  duplicate_timestamps: number;
  non_positive_prices: number;
  negative_volumes: number;
  extreme_jump_flags: number;
  data_source: string;
  retrieved_at: string;
  validation_status: string;
  notes: string[];
}

export interface DataQualityReport {
  generated_at: string;
  common_start_date: string | null;
  common_end_date: string | null;
  aligned_trading_days: number;
  assets: DatasetManifestEntry[];
  alignment_policy: string;
  warnings: string[];
}

export interface MarketOverviewResponse {
  latest_trading_date: string;
  latest_prices: Record<string, number>;
  asset_metrics: AssetMetricSummary[];
  benchmark_series: Array<{ date: string; price: number; normalized: number }>;
  data_quality_report: DataQualityReport;
}

export interface ExperimentSummary {
  id: string;
  name: string;
  status: string;
  created_at: string;
  simulation_method: SimulationMethod;
  n_paths: number;
  horizon_days: number;
  confidence_level: number;
  initial_capital: number;
  random_seed: number;
  data_start_date: string;
  data_end_date: string;
  model_version: string;
  portfolio_composition: {
    allocations: PortfolioAllocation[];
    initial_capital: number;
    risk_free_rate: number;
  };
  model_configuration: Record<string, unknown>;
  error_message?: string | null;
  headline_metrics: {
    var_95_inr: number | null;
    cvar_95_inr: number | null;
    var_99_inr: number | null;
    cvar_99_inr: number | null;
    expected_terminal_value: number | null;
    current_regime: string | null;
    garch_vol_ann: number | null;
  };
}

export interface ExperimentDetail extends ExperimentSummary {
  data_provenance: DataQualityReport;
  results: {
    historical_analytics: {
      observations: number;
      start_date: string;
      end_date: string;
      annualized_return_arithmetic: number;
      annualized_return_cagr: number;
      annualized_volatility: number;
      sharpe_ratio: number;
      sortino_ratio: number;
      max_drawdown: number;
      skewness: number;
      excess_kurtosis: number;
      current_rolling_vol_21d: number | null;
      current_rolling_vol_63d: number | null;
      equity_curve: Array<{ date: string; value: number }>;
      drawdown_curve: Array<{ date: string; value: number }>;
      rolling_vol_21d: Array<{ date: string; value: number }>;
      rolling_vol_63d: Array<{ date: string; value: number }>;
      correlation_matrix: { symbols: string[]; values: number[][] };
      asset_metrics: AssetMetricSummary[];
    };
    garch: {
      model: string;
      observations: number;
      converged: boolean;
      log_likelihood: number;
      aic: number;
      bic: number;
      parameters: {
        mu_daily_pct: number;
        omega_pct2: number;
        alpha: number;
        beta: number;
        persistence: number;
      };
      is_stationary: boolean;
      unconditional_vol_annualized: number | null;
      current_conditional_vol_annualized: number;
      current_rolling_vol_21d_annualized: number | null;
      forecast_horizon_days: number;
      forecast_vol_annualized: Array<{ horizon_day: number; annualized_vol: number }>;
      series: Array<{ date: string; garch_vol: number; rolling_vol_21d: number }>;
      warnings: string[];
      limitations: string;
    };
    regimes: {
      labels: string[];
      current_regime: string;
      current_state_probabilities: Record<string, number>;
      transition_matrix: number[][];
      regime_stats: Record<
        string,
        {
          observation_count: number;
          frequency_pct: number;
          annualized_mean_return: number;
          annualized_volatility: number;
          expected_duration_days: number;
          empirical_avg_duration_days: number;
          persistence_probability: number;
        }
      >;
      oos_note: string;
      diagnostics: {
        converged: boolean;
        n_observations: number;
        oos_evaluation_observations: number;
        oos_regime_distribution: Record<string, number>;
        warnings: string[];
        assumptions: string;
      };
      timeline: Array<{
        date: string;
        regime: string;
        p_low_vol: number;
        p_normal: number;
        p_high_vol: number;
        benchmark_cum_return: number;
      }>;
      crisis_correlation_sensitivity: {
        baseline: { var_95_inr: number; cvar_95_inr: number; var_99_inr: number; cvar_99_inr: number };
        crisis_corr_stressed: {
          var_95_inr: number;
          cvar_95_inr: number;
          var_99_inr: number;
          cvar_99_inr: number;
          diagnostics: Record<string, unknown>;
        };
      };
    };
    simulation: {
      method: SimulationMethod;
      return_convention: string;
      assumptions: string[];
      diagnostics: Record<string, unknown>;
      fan_chart: {
        days: number[];
        initial_capital: number;
        p05: number[];
        p25: number[];
        p50: number[];
        p75: number[];
        p95: number[];
        mean: number[];
        sample_paths: number[][];
      };
      terminal_value_histogram: { bin_centers: number[]; counts: number[] };
      terminal_loss_histogram: { bin_centers: number[]; counts: number[] };
      terminal_value_stats: Record<string, number | boolean | null>;
      terminal_loss_stats: Record<string, number | boolean | null>;
    };
    risk_metrics: {
      loss_convention: string;
      selected_confidence_level: number;
      monte_carlo: {
        var_selected: { confidence_level: number; var_amount: number; var_pct: number };
        cvar_selected: { confidence_level: number; cvar_amount: number; cvar_pct: number };
        var_95: { confidence_level: number; var_amount: number; var_pct: number };
        cvar_95: { confidence_level: number; cvar_amount: number; cvar_pct: number };
        var_99: { confidence_level: number; var_amount: number; var_pct: number };
        cvar_99: { confidence_level: number; cvar_amount: number; cvar_pct: number };
      };
      historical: {
        var_95: { var_amount: number; var_pct: number };
        cvar_95: { cvar_amount: number; cvar_pct: number };
        var_99: { var_amount: number; var_pct: number };
      };
      parametric: {
        var_95: { var_amount: number; var_pct: number };
        cvar_95: { cvar_amount: number; cvar_pct: number };
        var_99: { var_amount: number; var_pct: number };
      };
      summary: {
        initial_capital: number;
        expected_terminal_value: number;
        median_terminal_value: number;
        std_terminal_value: number;
        min_terminal_value: number;
        max_terminal_value: number;
        expected_terminal_return_pct: number;
        median_terminal_return_pct: number;
        probability_negative_return: number;
        loss_threshold_pct: number;
        probability_exceeding_loss_threshold: number;
        mean_max_drawdown: number;
        median_max_drawdown: number;
        p95_worst_max_drawdown: number;
        simulated_annualized_volatility: number;
        downside_deviation_annualized: number;
      };
      euler_risk_attribution: {
        methodology: string;
        note: string;
        portfolio_annualized_volatility: number;
        sum_component_contributions: number;
        reconciliation_error: number;
        reconciled: boolean;
        diversification_benefit_vol: number;
        assets: Array<{
          symbol: string;
          weight: number;
          standalone_annualized_vol: number;
          marginal_contribution_to_vol: number;
          component_contribution_to_vol: number;
          pct_risk_contribution: number;
        }>;
      };
    };
    method_comparison: Array<{
      method: SimulationMethod;
      n_paths: number;
      expected_terminal_value: number;
      var_95_inr: number;
      cvar_95_inr: number;
      var_99_inr: number;
      cvar_99_inr: number;
      p95_worst_max_drawdown: number;
      prob_negative_return: number;
    }>;
  };
}

export interface BacktestModelResult {
  method: SimulationMethod;
  observations: number;
  confidence_level: number;
  expected_violations: number;
  actual_violations: number;
  expected_violation_rate: number;
  actual_violation_rate: number;
  kupiec_lr_pof: number;
  kupiec_p_value: number;
  kupiec_passed: boolean;
  christoffersen_lr_ind: number;
  christoffersen_lr_cc: number;
  christoffersen_p_value: number;
  christoffersen_passed: boolean;
  calibration_verdict: string;
  violation_dates: string[];
  predicted_var_pct: number[];
}

export interface BacktestResponse {
  id: string;
  created_at: string;
  backtest_start_date: string;
  backtest_end_date: string;
  observations: number;
  rolling_window_days: number;
  confidence_level: number;
  dates: string[];
  realized_loss_pct: number[];
  models: Record<string, BacktestModelResult>;
  methodology_note: string;
}
