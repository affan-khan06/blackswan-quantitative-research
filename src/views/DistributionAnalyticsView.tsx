import React from 'react';
import { PlotlyChart } from '../components/PlotlyChart';
import { EmptyExperimentPrompt } from '../components/TerminalShell';
import type { ExperimentDetail, ViewId } from '../types/quant';
import { formatINR, formatMethodLabel, formatNum, formatPct } from '../utils/formatters';

interface DistributionAnalyticsViewProps {
  experiment: ExperimentDetail | null;
  onNavigate: (view: ViewId) => void;
}

export function DistributionAnalyticsView({ experiment, onNavigate }: DistributionAnalyticsViewProps) {
  if (!experiment) {
    return (
      <EmptyExperimentPrompt
        title="No Distribution Data Available"
        description="Run a portfolio Monte Carlo simulation in the Simulation Lab to inspect terminal wealth fan charts, loss distributions, and percentile tail statistics."
        actionLabel="Go to Simulation Lab"
        onAction={() => onNavigate('simulation-lab')}
      />
    );
  }

  const sim = experiment.results.simulation;
  const fan = sim.fan_chart;
  const risk = experiment.results.risk_metrics;
  const mc = risk.monte_carlo;
  const histVar = risk.historical;
  const paramVar = risk.parametric;
  const valStats = sim.terminal_value_stats;
  const lossHist = sim.terminal_loss_histogram;
  const valHist = sim.terminal_value_histogram;

  const var95 = mc.var_95.var_amount;
  const cvar95 = mc.cvar_95.cvar_amount;
  const var99 = mc.var_99.var_amount;

  const fanTraces: Partial<Plotly.Data>[] = [
    {
      x: fan.days,
      y: fan.p95,
      type: 'scatter',
      mode: 'lines',
      line: { width: 0 },
      showlegend: false,
      hoverinfo: 'skip',
    },
    {
      x: fan.days,
      y: fan.p05,
      type: 'scatter',
      mode: 'lines',
      fill: 'tonexty',
      fillcolor: 'rgba(228, 228, 231, 0.06)',
      line: { width: 0 },
      name: '5th–95th Percentile Band',
    },
    {
      x: fan.days,
      y: fan.p75,
      type: 'scatter',
      mode: 'lines',
      line: { width: 0 },
      showlegend: false,
      hoverinfo: 'skip',
    },
    {
      x: fan.days,
      y: fan.p25,
      type: 'scatter',
      mode: 'lines',
      fill: 'tonexty',
      fillcolor: 'rgba(228, 228, 231, 0.14)',
      line: { width: 0 },
      name: '25th–75th Interquartile Band',
    },
    ...fan.sample_paths.slice(0, 10).map((path, idx) => ({
      x: fan.days,
      y: path,
      type: 'scatter' as const,
      mode: 'lines' as const,
      line: { color: 'rgba(161, 161, 170, 0.16)', width: 1 },
      showlegend: idx === 0,
      name: idx === 0 ? 'Sample Paths' : undefined,
      hoverinfo: 'skip' as const,
    })),
    {
      x: fan.days,
      y: fan.p50,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#F4F4F5', width: 2.1 },
      name: 'Median Path (P50)',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Fan Chart */}
      <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
          <div>
            <h2 className="text-base font-semibold text-[#F4F4F5]">
              Simulated Portfolio Trajectory Fan Chart — {formatMethodLabel(sim.method)}
            </h2>
            <p className="text-xs text-[#71717A] mt-0.5">{sim.return_convention}</p>
          </div>
          <span className="text-xs font-mono text-[#71717A] tabular-nums">
            N = {experiment.n_paths.toLocaleString()} paths · H = {experiment.horizon_days}d
          </span>
        </div>

        <PlotlyChart
          testId="simulation-fan-chart"
          height={360}
          data={fanTraces}
          layout={{
            xaxis: { title: { text: 'Simulation Horizon (Trading Days)' } },
            yaxis: { title: { text: 'Portfolio Value (INR)' } },
            shapes: [
              {
                type: 'line',
                x0: 0,
                x1: experiment.horizon_days,
                y0: experiment.initial_capital,
                y1: experiment.initial_capital,
                line: { color: '#71717A', width: 1, dash: 'dash' },
              },
            ],
          }}
        />
      </section>

      {/* Terminal Value & Loss Distributions */}
      <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
          <h3 className="text-sm font-semibold text-[#F4F4F5]">Terminal Portfolio Value Distribution</h3>
          <p className="text-xs text-[#71717A] font-mono tabular-nums mt-0.5">
            P05: {formatINR(valStats.p05 as number)} · Median: {formatINR(valStats.median as number)} · P95:{' '}
            {formatINR(valStats.p95 as number)}
          </p>
          <PlotlyChart
            testId="terminal-value-histogram"
            height={300}
            data={[
              {
                x: valHist.bin_centers,
                y: valHist.counts,
                type: 'bar',
                name: 'Path Count',
                marker: {
                  color: valHist.bin_centers.map((c) =>
                    c < experiment.initial_capital ? 'rgba(199, 91, 100, 0.65)' : 'rgba(228, 228, 231, 0.62)'
                  ),
                },
              },
            ]}
            layout={{
              xaxis: { title: { text: 'Terminal Wealth (INR)' } },
              yaxis: { title: { text: 'Path Frequency' } },
              shapes: [
                {
                  type: 'line',
                  x0: experiment.initial_capital,
                  x1: experiment.initial_capital,
                  y0: 0,
                  y1: 1,
                  yref: 'paper',
                  line: { color: '#F4F4F5', width: 1.3, dash: 'dash' },
                },
              ],
            }}
          />
        </div>

        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
          <h3 className="text-sm font-semibold text-[#F4F4F5]">
            Terminal Loss Distribution (VaR & CVaR Tail Markers)
          </h3>
          <p className="text-xs text-[#71717A] font-mono tabular-nums mt-0.5">
            95% VaR: {formatINR(var95)} · 95% CVaR: {formatINR(cvar95)} · 99% VaR: {formatINR(var99)}
          </p>
          <PlotlyChart
            testId="terminal-loss-histogram"
            height={300}
            data={[
              {
                x: lossHist.bin_centers,
                y: lossHist.counts,
                type: 'bar',
                name: 'Loss Frequency',
                marker: {
                  color: lossHist.bin_centers.map((c) =>
                    c >= var95 ? 'rgba(199, 91, 100, 0.78)' : 'rgba(113, 113, 122, 0.48)'
                  ),
                },
              },
            ]}
            layout={{
              xaxis: { title: { text: 'Terminal Loss L = V0 - VT (INR, Positive = Loss)' } },
              yaxis: { title: { text: 'Path Frequency' } },
              shapes: [
                {
                  type: 'line',
                  x0: var95,
                  x1: var95,
                  y0: 0,
                  y1: 1,
                  yref: 'paper',
                  line: { color: '#C89D5C', width: 1.8, dash: 'dash' },
                },
                {
                  type: 'line',
                  x0: cvar95,
                  x1: cvar95,
                  y0: 0,
                  y1: 1,
                  yref: 'paper',
                  line: { color: '#C75B64', width: 2.0 },
                },
              ],
              annotations: [
                {
                  x: var95,
                  y: 0.96,
                  yref: 'paper',
                  text: '95% VaR',
                  showarrow: false,
                  font: { color: '#C89D5C', size: 10, family: '"JetBrains Mono", monospace' },
                  xanchor: 'left',
                },
                {
                  x: cvar95,
                  y: 0.84,
                  yref: 'paper',
                  text: '95% CVaR',
                  showarrow: false,
                  font: { color: '#C75B64', size: 10, family: '"JetBrains Mono", monospace' },
                  xanchor: 'left',
                },
              ],
            }}
          />
        </div>
      </section>

      {/* VaR / CVaR Cross-Estimator & Normality Diagnostics */}
      <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
          <h3 className="text-sm font-semibold text-[#F4F4F5] mb-3">
            VaR & Expected Shortfall Across Risk Estimators
          </h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                <th className="text-left py-2 font-medium">Estimator</th>
                <th className="text-right py-2 font-medium">95% VaR</th>
                <th className="text-right py-2 font-medium">95% CVaR</th>
                <th className="text-right py-2 font-medium">99% VaR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
              <tr>
                <td className="py-2.5 font-sans text-[#F4F4F5]">Monte Carlo ({formatMethodLabel(sim.method)})</td>
                <td className="py-2.5 text-right text-[#C89D5C]">{formatINR(mc.var_95.var_amount)}</td>
                <td className="py-2.5 text-right text-[#C75B64]">{formatINR(mc.cvar_95.cvar_amount)}</td>
                <td className="py-2.5 text-right text-[#C75B64]">{formatINR(mc.var_99.var_amount)}</td>
              </tr>
              <tr>
                <td className="py-2.5 font-sans text-[#F4F4F5]">Historical Rolling Horizon</td>
                <td className="py-2.5 text-right text-[#C89D5C]">{formatINR(histVar.var_95.var_amount)}</td>
                <td className="py-2.5 text-right text-[#C75B64]">{formatINR(histVar.cvar_95.cvar_amount)}</td>
                <td className="py-2.5 text-right text-[#C75B64]">{formatINR(histVar.var_99.var_amount)}</td>
              </tr>
              <tr>
                <td className="py-2.5 font-sans text-[#F4F4F5]">Parametric Variance-Covariance</td>
                <td className="py-2.5 text-right text-[#C89D5C]">{formatINR(paramVar.var_95.var_amount)}</td>
                <td className="py-2.5 text-right text-[#C75B64]">{formatINR(paramVar.cvar_95.cvar_amount)}</td>
                <td className="py-2.5 text-right text-[#C75B64]">{formatINR(paramVar.var_99.var_amount)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-[#F4F4F5]">Distribution Diagnostics & Model Assumptions</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono tabular-nums">
            <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-2.5">
              <div className="text-[#71717A] font-sans">Skewness</div>
              <div className="mt-1 text-sm text-[#F4F4F5]">{formatNum(valStats.skewness as number, 3)}</div>
            </div>
            <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-2.5">
              <div className="text-[#71717A] font-sans">Excess Kurtosis</div>
              <div className="mt-1 text-sm text-[#F4F4F5]">
                {formatNum(valStats.excess_kurtosis as number, 3)}
              </div>
            </div>
            <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-2.5">
              <div className="text-[#71717A] font-sans">JB Normality Test</div>
              <div className="mt-1 text-sm text-[#F4F4F5]">
                p = {formatNum(valStats.jarque_bera_pvalue as number, 4)}
              </div>
            </div>
          </div>
          <ul className="space-y-1.5 text-xs text-[#A1A1AA] list-disc pl-4">
            {sim.assumptions.map((a, idx) => (
              <li key={idx}>{a}</li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
