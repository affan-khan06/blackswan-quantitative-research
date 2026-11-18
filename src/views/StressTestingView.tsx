import React, { useEffect, useState } from 'react';
import { PlotlyChart } from '../components/PlotlyChart';
import { api } from '../services/api';
import type { ExperimentDetail, PortfolioAllocation } from '../types/quant';
import { formatINR, formatNum, formatPct } from '../utils/formatters';

interface StressTestingViewProps {
  experiment: ExperimentDetail | null;
}

const DEFAULT_ALLOCATIONS: PortfolioAllocation[] = [
  { symbol: 'NIFTY50', weight: 0.25 },
  { symbol: 'RELIANCE', weight: 0.20 },
  { symbol: 'HDFCBANK', weight: 0.20 },
  { symbol: 'INFY', weight: 0.15 },
  { symbol: 'LT', weight: 0.10 },
  { symbol: 'ITC', weight: 0.10 },
];

export function StressTestingView({ experiment }: StressTestingViewProps) {
  const [events, setEvents] = useState<
    Array<{ event_id: string; title: string; start_date: string; end_date: string; description: string }>
  >([]);
  const [selectedEvent, setSelectedEvent] = useState('COVID_2020');
  const [historicalResult, setHistoricalResult] = useState<Record<string, unknown> | null>(null);
  const [loadingHist, setLoadingHist] = useState(false);

  const [hypScenario, setHypScenario] = useState('combined_crisis');
  const [shockPct, setShockPct] = useState(-15);
  const [volMultiplier, setVolMultiplier] = useState(2.2);
  const [targetSector, setTargetSector] = useState('Financials');
  const [targetCorr, setTargetCorr] = useState(0.88);
  const [hypResult, setHypResult] = useState<Record<string, unknown> | null>(null);
  const [loadingHyp, setLoadingHyp] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const activeAllocations = experiment?.portfolio_composition.allocations ?? DEFAULT_ALLOCATIONS;
  const activeCapital = experiment?.initial_capital ?? 1000000;

  useEffect(() => {
    api.getStressEvents().then((res) => setEvents(res.events)).catch(() => {});
  }, []);

  const handleRunHistorical = async () => {
    setLoadingHist(true);
    setErrorMsg(null);
    try {
      const res = await api.runHistoricalStress({
        event_id: selectedEvent,
        allocations: activeAllocations,
        initial_capital: activeCapital,
        random_seed: experiment?.random_seed ?? 42,
      });
      setHistoricalResult(res);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Historical stress test failed.');
    } finally {
      setLoadingHist(false);
    }
  };

  const handleRunHypothetical = async () => {
    setLoadingHyp(true);
    setErrorMsg(null);
    try {
      const res = await api.runHypotheticalStress({
        scenario_type: hypScenario,
        allocations: activeAllocations,
        start_date: '2018-01-01',
        initial_capital: activeCapital,
        shock_magnitude_pct: shockPct / 100,
        target_sector: targetSector,
        volatility_multiplier: volMultiplier,
        target_crisis_corr: targetCorr,
        horizon_days: 21,
        n_paths: 2000,
        random_seed: experiment?.random_seed ?? 42,
      });
      setHypResult(res);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Hypothetical stress test failed.');
    } finally {
      setLoadingHyp(false);
    }
  };

  const histMetrics = historicalResult?.portfolio_metrics as Record<string, number | string> | undefined;
  const histDownside = historicalResult?.downside_risk_comparison as Record<string, number> | undefined;
  const histCurve = historicalResult?.crisis_equity_curve as Array<{ date: string; value: number }> | undefined;
  const histAssets = historicalResult?.asset_impacts as
    | Array<{
        symbol: string;
        weight: number;
        cumulative_return_pct: number;
        max_drawdown_pct: number;
        realized_vol_annualized: number;
        weighted_pnl_inr: number;
      }>
    | undefined;
  const preCorr = historicalResult?.pre_correlation_matrix as { symbols: string[]; values: number[][] } | undefined;
  const crisisCorr = historicalResult?.crisis_correlation_matrix as { symbols: string[]; values: number[][] } | undefined;

  const hypBase = hypResult?.baseline_distribution as Record<string, number> | undefined;
  const hypStress = hypResult?.stressed_distribution as Record<string, number> | undefined;
  const hypInstant = hypResult?.instantaneous_shock as Record<string, number> | undefined;

  return (
    <div className="space-y-6">
      <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg px-4 py-3 text-xs text-[#71717A] flex flex-wrap items-center justify-between gap-2">
        <span>
          Active Stress Portfolio:{' '}
          <span className="font-mono text-[#F4F4F5]">
            {activeAllocations.map((a) => `${a.symbol} ${(a.weight * 100).toFixed(1)}%`).join(' · ')}
          </span>
        </span>
        <span className="font-mono text-[#F4F4F5] tabular-nums">Capital: {formatINR(activeCapital)}</span>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-md bg-[#C75B64]/10 border border-[#C75B64]/40 text-xs text-[#E28A91]">
          {errorMsg}
        </div>
      )}

      {/* SECTION A: HISTORICAL OBSERVED CRISIS REPLAY */}
      <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-[11px] font-mono tracking-wide text-[#A1A1AA]">Observed Historical Episode</div>
            <h2 className="text-base font-semibold text-[#F4F4F5] mt-0.5">Historical Crisis Replay</h2>
            <p className="text-xs text-[#71717A] mt-0.5">
              Evaluates realized portfolio drawdown, volatility expansion, and correlation breakdown using actual NSE market data.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select
              aria-label="Select historical crisis event"
              value={selectedEvent}
              onChange={(e) => setSelectedEvent(e.target.value)}
              className="bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-3 py-2 text-xs text-[#F4F4F5]"
            >
              {(events.length > 0
                ? events
                : [
                    { event_id: 'COVID_2020', title: '2020 COVID-19 Pandemic Crash' },
                    { event_id: 'TIGHTENING_2022', title: '2022 Rate Tightening Cycle' },
                    { event_id: 'ELECTION_2024', title: '2024 Indian Election Volatility' },
                    { event_id: 'GFC_2008', title: '2008 Global Financial Crisis' },
                  ]
              ).map((ev) => (
                <option key={ev.event_id} value={ev.event_id}>
                  {ev.title}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleRunHistorical}
              disabled={loadingHist}
              className="px-4 py-2 text-xs font-semibold bg-[#F4F4F5] text-[#050506] rounded-md hover:bg-[#E4E4E7] transition-colors disabled:opacity-50"
            >
              {loadingHist ? 'Replaying...' : 'Run Historical Replay'}
            </button>
          </div>
        </div>

        {historicalResult && historicalResult.coverage_status === 'INSUFFICIENT_COVERAGE' && (
          <div className="p-4 rounded-md bg-[#C89D5C]/10 border border-[#C89D5C]/40 text-xs text-[#C89D5C]">
            {String(historicalResult.message)}
          </div>
        )}

        {historicalResult && histMetrics && histCurve && (
          <div className="space-y-5">
            <p className="text-xs text-[#E4E4E7] bg-[#08080A] border border-[#1A1A1E] rounded-md p-3.5 leading-relaxed">
              {String(historicalResult.narrative_analysis)}
            </p>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 font-mono tabular-nums">
              <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-3">
                <div className="text-xs font-sans text-[#71717A]">Observed Max Drawdown</div>
                <div className="mt-1 text-lg font-semibold text-[#C75B64]">
                  {formatPct(histMetrics.observed_max_drawdown_pct as number)}
                </div>
                <div className="text-[11px] text-[#71717A]">
                  Worst Day: {formatPct(histMetrics.worst_day_return_pct as number)}
                </div>
              </div>
              <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-3">
                <div className="text-xs font-sans text-[#71717A]">Crisis Realized Vol</div>
                <div className="mt-1 text-lg font-semibold text-[#C89D5C]">
                  {formatPct(histMetrics.realized_vol_crisis_annualized as number)}
                </div>
                <div className="text-[11px] text-[#71717A]">
                  Pre-Crisis: {formatPct(histMetrics.realized_vol_pre_annualized as number)} (
                  {formatNum(histMetrics.volatility_expansion_ratio as number, 2)}x)
                </div>
              </div>
              <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-3">
                <div className="text-xs font-sans text-[#71717A]">Avg Pairwise Correlation</div>
                <div className="mt-1 text-lg font-semibold text-[#F4F4F5]">
                  {formatNum(histMetrics.avg_pairwise_corr_crisis as number, 2)}
                </div>
                <div className="text-[11px] text-[#71717A]">
                  Pre-Crisis: {formatNum(histMetrics.avg_pairwise_corr_pre as number, 2)}
                </div>
              </div>
              {histDownside && (
                <div className="bg-[#08080A] border border-[#1A1A1E] rounded-md p-3">
                  <div className="text-xs font-sans text-[#71717A]">Simulated 21d 95% VaR Shift</div>
                  <div className="mt-1 text-lg font-semibold text-[#C75B64]">
                    {formatINR(histDownside.crisis_var_95_inr)}
                  </div>
                  <div className="text-[11px] text-[#71717A]">
                    Pre-Crisis: {formatINR(histDownside.pre_crisis_var_95_inr)}
                  </div>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <PlotlyChart
                testId="crisis-equity-chart"
                height={280}
                data={[
                  {
                    x: histCurve.map((p) => p.date),
                    y: histCurve.map((p) => p.value),
                    type: 'scatter',
                    mode: 'lines',
                    name: 'Crisis Portfolio Value (INR)',
                    line: { color: '#C75B64', width: 2 },
                  },
                ]}
                layout={{
                  xaxis: { title: { text: 'Crisis Session Date' } },
                  yaxis: { title: { text: 'Portfolio Value (INR)' } },
                }}
              />

              {preCorr && crisisCorr && (
                <PlotlyChart
                  testId="crisis-correlation-heatmap"
                  height={280}
                  data={[
                    {
                      z: crisisCorr.values,
                      x: crisisCorr.symbols,
                      y: crisisCorr.symbols,
                      type: 'heatmap',
                      zmin: -1,
                      zmax: 1,
                      colorscale: [
                        [0, '#334155'],
                        [0.5, '#111114'],
                        [1, '#A94952'],
                      ],
                      text: crisisCorr.values.map((r) => r.map((v) => v.toFixed(2))) as unknown as string[],
                      texttemplate: '%{text}',
                      textfont: { color: '#F4F4F5' },
                    },
                  ]}
                  layout={{
                    title: { text: 'In-Crisis Asset Correlation Matrix', font: { size: 12, color: '#F4F4F5' } },
                    margin: { t: 36, r: 20, b: 44, l: 72 },
                    yaxis: { autorange: 'reversed' },
                  }}
                />
              )}
            </div>

            {histAssets && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                      <th className="text-left py-2 font-medium">Asset</th>
                      <th className="text-right py-2 font-medium">Weight</th>
                      <th className="text-right py-2 font-medium">Crisis Return</th>
                      <th className="text-right py-2 font-medium">Asset Max DD</th>
                      <th className="text-right py-2 font-medium">Crisis Vol</th>
                      <th className="text-right py-2 font-medium">Weighted P&L</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                    {histAssets.map((a) => (
                      <tr key={a.symbol}>
                        <td className="py-2 font-semibold text-[#F4F4F5]">{a.symbol}</td>
                        <td className="py-2 text-right text-[#71717A]">{formatPct(a.weight, 1)}</td>
                        <td
                          className={`py-2 text-right ${
                            a.cumulative_return_pct >= 0 ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
                          }`}
                        >
                          {formatPct(a.cumulative_return_pct)}
                        </td>
                        <td className="py-2 text-right text-[#C75B64]">{formatPct(a.max_drawdown_pct)}</td>
                        <td className="py-2 text-right text-[#F4F4F5]">{formatPct(a.realized_vol_annualized)}</td>
                        <td
                          className={`py-2 text-right ${
                            a.weighted_pnl_inr >= 0 ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
                          }`}
                        >
                          {formatINR(a.weighted_pnl_inr)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>

      {/* SECTION B: HYPOTHETICAL SHOCK BUILDER */}
      <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-[11px] font-mono tracking-wide text-[#C89D5C]">Hypothetical Sensitivity Scenario</div>
            <h2 className="text-base font-semibold text-[#F4F4F5] mt-0.5">Hypothetical Stress Builder</h2>
            <p className="text-xs text-[#71717A] mt-0.5">
              Construct forward sensitivity shocks (not observed historical data) and compare baseline vs stressed VaR/CVaR.
            </p>
          </div>
          <button
            type="button"
            onClick={handleRunHypothetical}
            disabled={loadingHyp}
            className="px-4 py-2 text-xs font-semibold bg-[#141418] border border-[#52525B] text-[#F4F4F5] rounded-md hover:border-[#F4F4F5] hover:bg-[#1B1B20] transition-colors disabled:opacity-50"
          >
            {loadingHyp ? 'Computing...' : 'Run Hypothetical Shock'}
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
          <div>
            <label htmlFor="hyp-type" className="block text-[#71717A] mb-1">
              Scenario Type
            </label>
            <select
              id="hyp-type"
              value={hypScenario}
              onChange={(e) => setHypScenario(e.target.value)}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-2.5 py-2 text-[#F4F4F5]"
            >
              <option value="combined_crisis">Combined Black Swan</option>
              <option value="broad_market_decline">Broad Market Decline</option>
              <option value="sector_decline">Sector-Specific Decline</option>
              <option value="volatility_spike">Volatility Spike</option>
              <option value="correlation_shock">Correlation Shock</option>
            </select>
          </div>
          <div>
            <label htmlFor="hyp-shock" className="block text-[#71717A] mb-1">
              Price Shock (%)
            </label>
            <input
              id="hyp-shock"
              type="number"
              min={-75}
              max={30}
              value={shockPct}
              onChange={(e) => setShockPct(Number(e.target.value))}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-2.5 py-2 font-mono text-[#F4F4F5]"
            />
          </div>
          <div>
            <label htmlFor="hyp-vol" className="block text-[#71717A] mb-1">
              Vol Multiplier (x)
            </label>
            <input
              id="hyp-vol"
              type="number"
              step={0.1}
              min={0.5}
              max={5.0}
              value={volMultiplier}
              onChange={(e) => setVolMultiplier(Number(e.target.value))}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-2.5 py-2 font-mono text-[#F4F4F5]"
            />
          </div>
          <div>
            <label htmlFor="hyp-corr" className="block text-[#71717A] mb-1">
              Crisis Correlation
            </label>
            <input
              id="hyp-corr"
              type="number"
              step={0.05}
              min={0.2}
              max={0.98}
              value={targetCorr}
              onChange={(e) => setTargetCorr(Number(e.target.value))}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-2.5 py-2 font-mono text-[#F4F4F5]"
            />
          </div>
          <div>
            <label htmlFor="hyp-sector" className="block text-[#71717A] mb-1">
              Target Sector
            </label>
            <select
              id="hyp-sector"
              value={targetSector}
              onChange={(e) => setTargetSector(e.target.value)}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-2.5 py-2 text-[#F4F4F5]"
            >
              <option value="Financials">Financials</option>
              <option value="Information Technology">Information Technology</option>
              <option value="Energy & Telecom">Energy & Telecom</option>
              <option value="Automobiles">Automobiles</option>
            </select>
          </div>
        </div>

        {hypResult && hypBase && hypStress && hypInstant && (
          <div className="space-y-4">
            <div className="text-xs text-[#C89D5C] bg-[#08080A] border border-[#1A1A1E] rounded-md p-3">
              {String(hypResult.description)} — {String(hypResult.disclaimer)}
            </div>
            <PlotlyChart
              testId="hypothetical-comparison-chart"
              height={260}
              data={[
                {
                  x: ['95% VaR', '95% CVaR', '99% VaR'],
                  y: [hypBase.var_95_inr, hypBase.cvar_95_inr, hypBase.var_99_inr],
                  type: 'bar',
                  name: 'Baseline (21d)',
                  marker: { color: '#52525B' },
                },
                {
                  x: ['95% VaR', '95% CVaR', '99% VaR'],
                  y: [hypStress.var_95_inr, hypStress.cvar_95_inr, hypStress.var_99_inr],
                  type: 'bar',
                  name: 'Hypothetical Stressed (21d)',
                  marker: { color: '#C75B64' },
                },
              ]}
              layout={{
                barmode: 'group',
                yaxis: { title: { text: 'Tail Loss Amount (INR)' } },
              }}
            />
          </div>
        )}
      </section>
    </div>
  );
}
