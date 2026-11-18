import React from 'react';
import { PlotlyChart } from '../components/PlotlyChart';
import { EmptyExperimentPrompt } from '../components/TerminalShell';
import type { ExperimentDetail, ViewId } from '../types/quant';
import { formatINR, formatNum, formatPct } from '../utils/formatters';

interface RegimeIntelligenceViewProps {
  experiment: ExperimentDetail | null;
  onNavigate: (view: ViewId) => void;
}

export function RegimeIntelligenceView({ experiment, onNavigate }: RegimeIntelligenceViewProps) {
  if (!experiment) {
    return (
      <EmptyExperimentPrompt
        title="No Regime or GARCH Analysis Available"
        description="Run a portfolio simulation to estimate the 3-state Gaussian Hidden Markov Model (LOW_VOL, NORMAL, HIGH_VOL), GARCH(1,1) conditional volatility, and crisis correlation sensitivity."
        actionLabel="Open Simulation Lab"
        onAction={() => onNavigate('simulation-lab')}
      />
    );
  }

  const regimes = experiment.results.regimes;
  const garch = experiment.results.garch;
  const timeline = regimes.timeline;
  const labels = regimes.labels;
  const sensitivity = regimes.crisis_correlation_sensitivity;

  const dates = timeline.map((t) => t.date);

  return (
    <div className="space-y-6">
      {/* Regime Posterior Probability Timeline */}
      <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
          <div>
            <h2 className="text-base font-semibold text-[#F4F4F5]">
              3-State Gaussian HMM Regime Posterior Timeline (NIFTY 50 Benchmark)
            </h2>
            <p className="text-xs text-[#71717A] mt-0.5">{regimes.oos_note}</p>
          </div>
          <div className="text-xs font-mono tabular-nums text-[#A1A1AA]">
            Current Regime:{' '}
            <span
              className={
                regimes.current_regime === 'HIGH_VOL'
                  ? 'text-[#C75B64]'
                  : regimes.current_regime === 'NORMAL'
                    ? 'text-[#C89D5C]'
                    : 'text-[#F4F4F5]'
              }
            >
              {regimes.current_regime}
            </span>
          </div>
        </div>

        <PlotlyChart
          testId="regime-timeline-chart"
          height={320}
          data={[
            {
              x: dates,
              y: timeline.map((t) => t.p_high_vol * 100),
              type: 'scatter',
              mode: 'lines',
              stackgroup: 'one',
              name: 'P(HIGH_VOL)',
              line: { color: '#C75B64', width: 0.7 },
              fillcolor: 'rgba(199, 91, 100, 0.58)',
            },
            {
              x: dates,
              y: timeline.map((t) => t.p_normal * 100),
              type: 'scatter',
              mode: 'lines',
              stackgroup: 'one',
              name: 'P(NORMAL)',
              line: { color: '#C89D5C', width: 0.7 },
              fillcolor: 'rgba(200, 157, 92, 0.36)',
            },
            {
              x: dates,
              y: timeline.map((t) => t.p_low_vol * 100),
              type: 'scatter',
              mode: 'lines',
              stackgroup: 'one',
              name: 'P(LOW_VOL)',
              line: { color: '#D4D4D8', width: 0.7 },
              fillcolor: 'rgba(212, 212, 216, 0.22)',
            },
          ]}
          layout={{
            yaxis: { title: { text: 'Regime Posterior Probability (%)' }, range: [0, 100] },
            xaxis: { title: { text: 'NSE Trading Date' } },
          }}
        />
      </section>

      {/* Transition Matrix Heatmap + Regime Statistics */}
      <section className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-5 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
          <h3 className="text-sm font-semibold text-[#F4F4F5]">Markov State Transition Matrix P(i → j)</h3>
          <p className="text-xs text-[#71717A] mt-0.5">
            Post-fit volatility ordering guarantees LOW_VOL ≤ NORMAL ≤ HIGH_VOL.
          </p>
          <PlotlyChart
            testId="transition-matrix-heatmap"
            height={280}
            data={[
              {
                z: regimes.transition_matrix,
                x: labels,
                y: labels,
                type: 'heatmap',
                colorscale: [
                  [0, '#09090B'],
                  [0.5, '#1D1D22'],
                  [1, '#52525B'],
                ],
                text: regimes.transition_matrix.map((row) =>
                  row.map((v) => `${(v * 100).toFixed(1)}%`)
                ) as unknown as string[],
                texttemplate: '%{text}',
                textfont: { family: '"JetBrains Mono", monospace', size: 12, color: '#F4F4F5' },
                showscale: false,
              },
            ]}
            layout={{
              margin: { t: 20, r: 20, b: 56, l: 122 },
              xaxis: { title: { text: 'Next Regime (t+1)', standoff: 12 } },
              yaxis: { title: { text: 'Current Regime (t)', standoff: 14 }, autorange: 'reversed' },
            }}
          />
        </div>

        <div className="xl:col-span-7 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-4">
          <h3 className="text-sm font-semibold text-[#F4F4F5]">Regime-Conditioned Distributions & Durations</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                  <th className="text-left py-2 font-medium">Regime</th>
                  <th className="text-right py-2 font-medium">Occupancy</th>
                  <th className="text-right py-2 font-medium">Ann. Return</th>
                  <th className="text-right py-2 font-medium">Ann. Vol</th>
                  <th className="text-right py-2 font-medium">Expected Dur.</th>
                  <th className="text-right py-2 font-medium">Empirical Dur.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                {labels.map((lbl) => {
                  const st = regimes.regime_stats[lbl];
                  return (
                    <tr key={lbl}>
                      <td className="py-2.5 font-semibold text-[#F4F4F5]">{lbl}</td>
                      <td className="py-2.5 text-right text-[#71717A]">{st.frequency_pct.toFixed(1)}%</td>
                      <td
                        className={`py-2.5 text-right ${
                          st.annualized_mean_return >= 0 ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
                        }`}
                      >
                        {formatPct(st.annualized_mean_return)}
                      </td>
                      <td className="py-2.5 text-right text-[#D4D4D8]">{formatPct(st.annualized_volatility)}</td>
                      <td className="py-2.5 text-right text-[#71717A]">{st.expected_duration_days}d</td>
                      <td className="py-2.5 text-right text-[#71717A]">{st.empirical_avg_duration_days}d</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="border-t border-[#1A1A1E] pt-3">
            <h4 className="text-xs font-semibold text-[#F4F4F5] mb-2">
              Crisis Correlation Sensitivity Experiment (HIGH_VOL ρ → 0.85)
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono tabular-nums">
              <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-2.5">
                <div className="text-[#71717A] font-sans">Baseline 95% VaR</div>
                <div className="mt-1 text-[#F4F4F5]">{formatINR(sensitivity.baseline.var_95_inr)}</div>
              </div>
              <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-2.5">
                <div className="text-[#71717A] font-sans">Stressed 95% VaR</div>
                <div className="mt-1 text-[#C75B64]">
                  {formatINR(sensitivity.crisis_corr_stressed.var_95_inr)}
                </div>
              </div>
              <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-2.5">
                <div className="text-[#71717A] font-sans">Baseline 99% CVaR</div>
                <div className="mt-1 text-[#F4F4F5]">{formatINR(sensitivity.baseline.cvar_99_inr)}</div>
              </div>
              <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-2.5">
                <div className="text-[#71717A] font-sans">Stressed 99% CVaR</div>
                <div className="mt-1 text-[#C75B64]">
                  {formatINR(sensitivity.crisis_corr_stressed.cvar_99_inr)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* GARCH(1,1) Conditional Volatility */}
      <section className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-8 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
            <div>
              <h3 className="text-sm font-semibold text-[#F4F4F5]">
                GARCH(1,1) Conditional Volatility vs 21-Day Rolling Volatility
              </h3>
              <p className="text-xs text-[#71717A] mt-0.5">{garch.limitations}</p>
            </div>
          </div>
          <PlotlyChart
            testId="garch-volatility-chart"
            height={300}
            data={[
              {
                x: garch.series.map((s) => s.date),
                y: garch.series.map((s) => s.garch_vol * 100),
                type: 'scatter',
                mode: 'lines',
                name: 'GARCH(1,1) Conditional Vol (%)',
                line: { color: '#E4E4E7', width: 1.7 },
              },
              {
                x: garch.series.map((s) => s.date),
                y: garch.series.map((s) => s.rolling_vol_21d * 100),
                type: 'scatter',
                mode: 'lines',
                name: '21d Rolling Historical Vol (%)',
                line: { color: '#71717A', width: 1.2, dash: 'dot' },
              },
            ]}
            layout={{
              yaxis: { title: { text: 'Annualized Volatility (%)' } },
              xaxis: { title: { text: 'NSE Trading Session' } },
            }}
          />
        </div>

        <div className="xl:col-span-4 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-4">
          <h3 className="text-sm font-semibold text-[#F4F4F5]">GARCH(1,1) Diagnostics & Forecast</h3>
          <div className="space-y-2 text-xs font-mono tabular-nums">
            <div className="flex justify-between py-1 border-b border-[#1A1A1E]">
              <span className="text-[#71717A]">omega (ω)</span>
              <span>{formatNum(garch.parameters.omega_pct2, 5)}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#1A1A1E]">
              <span className="text-[#71717A]">alpha (α₁)</span>
              <span>{formatNum(garch.parameters.alpha, 4)}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#1A1A1E]">
              <span className="text-[#71717A]">beta (β₁)</span>
              <span>{formatNum(garch.parameters.beta, 4)}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#1A1A1E]">
              <span className="text-[#71717A]">Persistence (α + β)</span>
              <span className={garch.is_stationary ? 'text-[#E4E4E7]' : 'text-[#C75B64]'}>
                {formatNum(garch.parameters.persistence, 4)} ({garch.is_stationary ? 'Stationary' : 'Non-Stationary'})
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#1A1A1E]">
              <span className="text-[#71717A]">Unconditional Vol</span>
              <span>{formatPct(garch.unconditional_vol_annualized)}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-[#71717A]">Optimizer Status</span>
              <span>{garch.converged ? 'Converged' : 'Warning'}</span>
            </div>
          </div>

          <PlotlyChart
            testId="garch-forecast-chart"
            height={160}
            data={[
              {
                x: garch.forecast_vol_annualized.map((f) => f.horizon_day),
                y: garch.forecast_vol_annualized.map((f) => f.annualized_vol * 100),
                type: 'scatter',
                mode: 'lines',
                name: 'Forecast Vol (%)',
                line: { color: '#C89D5C', width: 1.9 },
              },
            ]}
            layout={{
              margin: { t: 16, r: 12, b: 36, l: 48 },
              xaxis: { title: { text: 'Forecast Horizon (Days)' } },
              yaxis: { title: { text: 'Vol (%)' } },
              showlegend: false,
            }}
          />
        </div>
      </section>
    </div>
  );
}
