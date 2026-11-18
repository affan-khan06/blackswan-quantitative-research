import React from 'react';
import { PlotlyChart } from '../components/PlotlyChart';
import { EmptyExperimentPrompt, LoadingPanel } from '../components/TerminalShell';
import type { ExperimentDetail, MarketOverviewResponse, ViewId } from '../types/quant';
import { formatINR, formatMethodLabel, formatNum, formatPct } from '../utils/formatters';

interface CommandCenterViewProps {
  experiment: ExperimentDetail | null;
  marketOverview: MarketOverviewResponse | null;
  loadingMarket: boolean;
  loadingExperiment: boolean;
  onNavigate: (view: ViewId) => void;
}

export function CommandCenterView({
  experiment,
  marketOverview,
  loadingMarket,
  loadingExperiment,
  onNavigate,
}: CommandCenterViewProps) {
  if (loadingExperiment || (loadingMarket && !marketOverview)) {
    return <LoadingPanel label="Loading real NSE market data and experiment telemetry..." />;
  }

  if (!experiment) {
    return (
      <div className="space-y-6">
        <EmptyExperimentPrompt
          title="No Portfolio Simulation Executed Yet"
          description="BLACKSWAN enforces strict empirical provenance and never displays simulated placeholder risk metrics. Inspect the live NSE historical universe below, then configure your portfolio weights and stochastic methodology in the Simulation Lab."
          actionLabel="Open Simulation Lab"
          onAction={() => onNavigate('simulation-lab')}
        />

        {marketOverview && (
          <div className="space-y-6">
            <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
                <div>
                  <h2 className="text-base font-semibold text-[#F4F4F5]">
                    NIFTY 50 Historical Benchmark Index (Normalized Base = 100)
                  </h2>
                  <p className="text-xs text-[#71717A] font-mono mt-0.5 tabular-nums">
                    Real NSE Sessions: {marketOverview.data_quality_report.aligned_trading_days.toLocaleString()} ·{' '}
                    {marketOverview.data_quality_report.common_start_date} to{' '}
                    {marketOverview.data_quality_report.common_end_date}
                  </p>
                </div>
                <span className="text-xs font-mono text-[#E4E4E7] tabular-nums">
                  Latest NIFTY 50: {formatNum(marketOverview.latest_prices['NIFTY50'], 2)}
                </span>
              </div>

              <PlotlyChart
                testId="benchmark-overview-chart"
                height={320}
                data={[
                  {
                    x: marketOverview.benchmark_series.map((d) => d.date),
                    y: marketOverview.benchmark_series.map((d) => d.normalized),
                    type: 'scatter',
                    mode: 'lines',
                    name: 'NIFTY 50 (Base 100)',
                    line: { color: '#E4E4E7', width: 1.6 },
                  },
                ]}
                layout={{
                  yaxis: { title: { text: 'Normalized Index Level' } },
                  xaxis: { title: { text: 'NSE Trading Session' } },
                }}
              />
            </section>

            <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
              <h3 className="text-sm font-semibold text-[#F4F4F5] mb-3">
                Verified NSE Universe — Historical Return & Volatility Audit
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                      <th className="text-left py-2.5 px-2 font-medium">Asset</th>
                      <th className="text-right py-2.5 px-2 font-medium">Last Close</th>
                      <th className="text-right py-2.5 px-2 font-medium">CAGR</th>
                      <th className="text-right py-2.5 px-2 font-medium">Ann. Vol</th>
                      <th className="text-right py-2.5 px-2 font-medium">Sharpe</th>
                      <th className="text-right py-2.5 px-2 font-medium">Max Drawdown</th>
                      <th className="text-right py-2.5 px-2 font-medium">Kurtosis</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                    {marketOverview.asset_metrics.map((m) => (
                      <tr key={m.symbol} className="hover:bg-[#141418]/70 transition-colors">
                        <td className="py-2 px-2 font-semibold text-[#F4F4F5]">{m.symbol}</td>
                        <td className="py-2 px-2 text-right text-[#D4D4D8]">
                          {formatNum(marketOverview.latest_prices[m.symbol], 2)}
                        </td>
                        <td
                          className={`py-2 px-2 text-right ${
                            m.annualized_return_cagr >= 0 ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
                          }`}
                        >
                          {formatPct(m.annualized_return_cagr)}
                        </td>
                        <td className="py-2 px-2 text-right text-[#D4D4D8]">
                          {formatPct(m.annualized_volatility)}
                        </td>
                        <td className="py-2 px-2 text-right text-[#D4D4D8]">
                          {formatNum(m.sharpe_ratio, 2)}
                        </td>
                        <td className="py-2 px-2 text-right text-[#C75B64]">
                          {formatPct(m.max_drawdown)}
                        </td>
                        <td className="py-2 px-2 text-right text-[#71717A]">
                          {formatNum(m.excess_kurtosis, 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </div>
    );
  }

  const res = experiment.results;
  const risk = res.risk_metrics;
  const mc = risk.monte_carlo;
  const summary = risk.summary;
  const hist = res.historical_analytics;
  const garch = res.garch;
  const regimes = res.regimes;
  const attr = risk.euler_risk_attribution;

  const regimeColor =
    regimes.current_regime === 'HIGH_VOL'
      ? 'text-[#C75B64]'
      : regimes.current_regime === 'NORMAL'
        ? 'text-[#C89D5C]'
        : 'text-[#F4F4F5]';

  return (
    <div className="space-y-6">
      {/* Experiment Context Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg px-4 py-3 text-xs">
        <div className="flex flex-wrap items-center gap-2 font-mono text-[#71717A] tabular-nums">
          <span className="font-sans font-semibold text-[#F4F4F5]">{experiment.name}</span>
          <span aria-hidden="true">·</span>
          <span>{formatMethodLabel(experiment.simulation_method)}</span>
          <span aria-hidden="true">·</span>
          <span>{experiment.n_paths.toLocaleString()} paths</span>
          <span aria-hidden="true">·</span>
          <span>{experiment.horizon_days} trading days</span>
          <span aria-hidden="true">·</span>
          <span>Seed {experiment.random_seed}</span>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => onNavigate('distribution-analytics')}
            className="text-xs font-medium text-[#D4D4D8] hover:text-[#F4F4F5] transition-colors"
          >
            Inspect Distributions
          </button>
          <a
            href={`/api/reports/${encodeURIComponent(experiment.id)}/pdf`}
            download={`BLACKSWAN_Report_${experiment.id}.pdf`}
            className="px-3 py-1.5 text-xs font-medium bg-[#141418] border border-[#222228] text-[#F4F4F5] rounded-md hover:border-[#52525B] transition-colors"
          >
            Export PDF
          </a>
        </div>
      </div>

      {/* Headline Risk KPI Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-4">
          <div className="text-xs text-[#71717A]">Expected Terminal Value ({experiment.horizon_days}d)</div>
          <div className="mt-1.5 text-2xl font-semibold font-mono tabular-nums text-[#F4F4F5]">
            {formatINR(summary.expected_terminal_value)}
          </div>
          <div className="mt-1 text-[11px] font-mono tabular-nums text-[#71717A]">
            Initial {formatINR(experiment.initial_capital)} · P(Loss){' '}
            {formatPct(summary.probability_negative_return, 1)}
          </div>
        </div>

        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-4">
          <div className="text-xs text-[#71717A]">95% Value at Risk / CVaR ({experiment.horizon_days}d)</div>
          <div className="mt-1.5 text-2xl font-semibold font-mono tabular-nums text-[#C75B64]">
            {formatINR(mc.var_95.var_amount)}
          </div>
          <div className="mt-1 text-[11px] font-mono tabular-nums text-[#71717A]">
            CVaR (ES): <span className="text-[#C75B64]">{formatINR(mc.cvar_95.cvar_amount)}</span> (
            {formatPct(mc.cvar_95.cvar_pct)})
          </div>
        </div>

        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-4">
          <div className="text-xs text-[#71717A]">GARCH(1,1) Conditional Volatility</div>
          <div className="mt-1.5 text-2xl font-semibold font-mono tabular-nums text-[#F4F4F5]">
            {formatPct(garch.current_conditional_vol_annualized)}
          </div>
          <div className="mt-1 text-[11px] font-mono tabular-nums text-[#71717A]">
            21d Rolling: {formatPct(garch.current_rolling_vol_21d_annualized)} · α+β{' '}
            {formatNum(garch.parameters.persistence, 3)}
          </div>
        </div>

        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-4">
          <div className="text-xs text-[#71717A]">Current HMM Market Regime</div>
          <div className={`mt-1.5 text-2xl font-semibold font-mono ${regimeColor}`}>
            {regimes.current_regime}
          </div>
          <div className="mt-1 text-[11px] font-mono tabular-nums text-[#71717A]">
            Posterior P({regimes.current_regime}):{' '}
            {formatPct(regimes.current_state_probabilities[regimes.current_regime], 1)}
          </div>
        </div>
      </section>

      {/* Historical Equity Curve & Drawdown */}
      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F4F4F5]">
                Historical Rebalanced Portfolio Equity & Drawdown
              </h2>
              <p className="text-xs text-[#71717A] font-mono tabular-nums mt-0.5">
                CAGR {formatPct(hist.annualized_return_cagr)} · Sharpe {formatNum(hist.sharpe_ratio, 2)} · Sortino{' '}
                {formatNum(hist.sortino_ratio, 2)} · Max DD {formatPct(hist.max_drawdown)}
              </p>
            </div>
          </div>

          <PlotlyChart
            testId="command-equity-chart"
            height={320}
            data={[
              {
                x: hist.equity_curve.map((p) => p.date),
                y: hist.equity_curve.map((p) => p.value),
                type: 'scatter',
                mode: 'lines',
                name: 'Portfolio Wealth (INR)',
                line: { color: '#E4E4E7', width: 1.7 },
              },
              {
                x: hist.drawdown_curve.map((p) => p.date),
                y: hist.drawdown_curve.map((p) => p.value * 100),
                type: 'scatter',
                mode: 'lines',
                name: 'Drawdown (%)',
                yaxis: 'y2',
                fill: 'tozeroy',
                fillcolor: 'rgba(199, 91, 100, 0.12)',
                line: { color: '#C75B64', width: 1.1 },
              },
            ]}
            layout={{
              yaxis: { title: { text: 'Portfolio Value (INR)' } },
              yaxis2: {
                title: { text: 'Drawdown (%)', standoff: 14 },
                overlaying: 'y',
                side: 'right',
                showgrid: false,
                ticksuffix: '%',
                tickformat: '.0f',
                tickfont: { family: '"JetBrains Mono", monospace', size: 10, color: '#C75B64' },
              },
            }}
          />
        </div>

        {/* Euler Risk Attribution */}
        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[#F4F4F5]">Euler Volatility Attribution</h2>
            <p className="text-xs text-[#71717A] mt-1">
              Asset share of total annualized portfolio volatility ({formatPct(attr.portfolio_annualized_volatility)}).
            </p>

            <div className="mt-5 space-y-3.5">
              {attr.assets.map((a) => (
                <div key={a.symbol} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono tabular-nums">
                    <span className="font-semibold text-[#F4F4F5]">
                      {a.symbol} <span className="text-[#71717A]">({(a.weight * 100).toFixed(1)}%)</span>
                    </span>
                    <span className="text-[#D4D4D8]">{a.pct_risk_contribution.toFixed(1)}% risk</span>
                  </div>
                  <div className="h-1 w-full bg-[#18181D] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#D4D4D8]"
                      style={{ width: `${Math.max(0, Math.min(100, a.pct_risk_contribution))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 pt-3 border-t border-[#1A1A1E] text-[11px] font-mono text-[#71717A] tabular-nums space-y-1">
            <div>
              Euler Sum: {formatPct(attr.sum_component_contributions, 4)} · Error:{' '}
              {attr.reconciliation_error.toExponential(1)}
            </div>
            <div>Diversification Benefit: {formatPct(attr.diversification_benefit_vol)}</div>
          </div>
        </div>
      </section>

      {/* Methodology Comparison Table */}
      {res.method_comparison && res.method_comparison.length > 0 && (
        <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F4F4F5]">
                Stochastic Methodology Comparison ({experiment.horizon_days}-Day Horizon)
              </h2>
              <p className="text-xs text-[#71717A] mt-0.5">
                Identical portfolio, horizon, and random seed evaluated across all four simulation engines.
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                  <th className="text-left py-2.5 px-2 font-medium">Methodology</th>
                  <th className="text-right py-2.5 px-2 font-medium">Expected Terminal</th>
                  <th className="text-right py-2.5 px-2 font-medium">95% VaR</th>
                  <th className="text-right py-2.5 px-2 font-medium">95% CVaR</th>
                  <th className="text-right py-2.5 px-2 font-medium">99% VaR</th>
                  <th className="text-right py-2.5 px-2 font-medium">99% CVaR</th>
                  <th className="text-right py-2.5 px-2 font-medium">P95 Max DD</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                {res.method_comparison.map((row) => {
                  const isActive = row.method === experiment.simulation_method;
                  return (
                    <tr
                      key={row.method}
                      className={isActive ? 'bg-[#141418]' : 'hover:bg-[#111115]'}
                    >
                      <td className="py-2.5 px-2 font-sans font-medium text-[#F4F4F5]">
                        {formatMethodLabel(row.method)}
                        {isActive && <span className="ml-2 text-xs font-mono text-[#A1A1AA]">(Active)</span>}
                      </td>
                      <td className="py-2.5 px-2 text-right text-[#E4E4E7]">
                        {formatINR(row.expected_terminal_value)}
                      </td>
                      <td className="py-2.5 px-2 text-right text-[#C89D5C]">{formatINR(row.var_95_inr)}</td>
                      <td className="py-2.5 px-2 text-right text-[#C75B64]">{formatINR(row.cvar_95_inr)}</td>
                      <td className="py-2.5 px-2 text-right text-[#C89D5C]">{formatINR(row.var_99_inr)}</td>
                      <td className="py-2.5 px-2 text-right text-[#C75B64]">{formatINR(row.cvar_99_inr)}</td>
                      <td className="py-2.5 px-2 text-right text-[#C75B64]">
                        {formatPct(row.p95_worst_max_drawdown)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
