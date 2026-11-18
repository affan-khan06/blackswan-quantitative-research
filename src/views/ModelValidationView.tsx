import React, { useEffect, useState } from 'react';
import { PlotlyChart } from '../components/PlotlyChart';
import { api } from '../services/api';
import type { BacktestResponse, ExperimentDetail, PortfolioAllocation } from '../types/quant';
import { formatMethodLabel, formatNum, formatPct } from '../utils/formatters';

interface ModelValidationViewProps {
  experiment: ExperimentDetail | null;
}

const DEFAULT_ALLOCATIONS: PortfolioAllocation[] = [
  { symbol: 'NIFTY50', weight: 0.40 },
  { symbol: 'RELIANCE', weight: 0.25 },
  { symbol: 'HDFCBANK', weight: 0.20 },
  { symbol: 'INFY', weight: 0.15 },
];

export function ModelValidationView({ experiment }: ModelValidationViewProps) {
  const [confidence, setConfidence] = useState(0.95);
  const [windowSize, setWindowSize] = useState(252);
  const [oosSessions, setOosSessions] = useState(200);
  const [selectedModelChart, setSelectedModelChart] = useState('regime_switching_mc');
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const allocations = experiment?.portfolio_composition.allocations ?? DEFAULT_ALLOCATIONS;

  useEffect(() => {
    api
      .listBacktests()
      .then((res) => {
        if (res.backtests.length > 0) {
          setBacktest(res.backtests[0].results);
        }
      })
      .catch(() => {});
  }, []);

  const handleRunBacktest = async () => {
    setRunning(true);
    setErrorMsg(null);
    try {
      const res = await api.runBacktest({
        allocations,
        start_date: '2017-01-01',
        confidence_level: confidence,
        window_size: windowSize,
        oos_sessions: oosSessions,
        mc_draws_per_step: 800,
        random_seed: experiment?.random_seed ?? 42,
      });
      setBacktest(res);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Backtest execution failed.');
    } finally {
      setRunning(false);
    }
  };

  const selectedModel = backtest?.models[selectedModelChart];

  return (
    <div className="space-y-6">
      {/* Configuration Header */}
      <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-[#F4F4F5]">
              Chronological Out-of-Sample Rolling VaR Backtesting
            </h2>
            <p className="text-xs text-[#71717A] mt-0.5 max-w-3xl">
              Evaluates 1-day VaR forecasts against unseen NSE sessions using strictly causal estimation windows
              (observations ≤ t−1). Reports Kupiec unconditional coverage and Christoffersen conditional coverage tests honestly.
            </p>
          </div>
          <button
            type="button"
            onClick={handleRunBacktest}
            disabled={running}
            className="px-4 py-2 text-xs font-semibold bg-[#F4F4F5] text-[#050506] rounded-md hover:bg-[#E4E4E7] transition-colors disabled:opacity-50 whitespace-nowrap"
          >
            {running ? 'Running Walk-Forward Backtest...' : 'Run Out-of-Sample Backtest'}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <label htmlFor="bt-conf" className="block text-[#71717A] mb-1">
              VaR Confidence Level
            </label>
            <select
              id="bt-conf"
              value={confidence}
              onChange={(e) => setConfidence(Number(e.target.value))}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-3 py-2 font-mono text-[#F4F4F5]"
            >
              <option value={0.95}>95% (Expected violation rate: 5.0%)</option>
              <option value={0.99}>99% (Expected violation rate: 1.0%)</option>
            </select>
          </div>
          <div>
            <label htmlFor="bt-win" className="block text-[#71717A] mb-1">
              Trailing Estimation Window (Days)
            </label>
            <input
              id="bt-win"
              type="number"
              min={126}
              max={504}
              value={windowSize}
              onChange={(e) => setWindowSize(Number(e.target.value))}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-3 py-2 font-mono text-[#F4F4F5]"
            />
          </div>
          <div>
            <label htmlFor="bt-oos" className="block text-[#71717A] mb-1">
              Out-of-Sample Test Sessions
            </label>
            <input
              id="bt-oos"
              type="number"
              min={60}
              max={500}
              value={oosSessions}
              onChange={(e) => setOosSessions(Number(e.target.value))}
              className="w-full bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-3 py-2 font-mono text-[#F4F4F5]"
            />
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-md bg-[#C75B64]/10 border border-[#C75B64]/40 text-xs text-[#E28A91]">
            {errorMsg}
          </div>
        )}
      </section>

      {backtest && (
        <>
          {/* Rolling VaR & Violations Chart */}
          <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-[#F4F4F5]">
                  Out-of-Sample 1-Day VaR Threshold vs Realized Daily Loss
                </h3>
                <p className="text-xs font-mono text-[#71717A] mt-0.5 tabular-nums">
                  OOS Period: {backtest.backtest_start_date} to {backtest.backtest_end_date} ·{' '}
                  {backtest.observations} sessions
                </p>
              </div>
              <select
                aria-label="Select model for rolling VaR chart"
                value={selectedModelChart}
                onChange={(e) => setSelectedModelChart(e.target.value)}
                className="bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-3 py-1.5 text-xs text-[#F4F4F5]"
              >
                {Object.keys(backtest.models).map((k) => (
                  <option key={k} value={k}>
                    {formatMethodLabel(k)}
                  </option>
                ))}
              </select>
            </div>

            {selectedModel && (
              <PlotlyChart
                testId="rolling-var-backtest-chart"
                height={330}
                data={[
                  {
                    x: backtest.dates,
                    y: backtest.realized_loss_pct.map((v) => v * 100),
                    type: 'scatter',
                    mode: 'lines',
                    name: 'Realized 1d Loss (%)',
                    line: { color: '#71717A', width: 1.1 },
                  },
                  {
                    x: backtest.dates,
                    y: selectedModel.predicted_var_pct.map((v) => v * 100),
                    type: 'scatter',
                    mode: 'lines',
                    name: `${formatMethodLabel(selectedModelChart)} ${(backtest.confidence_level * 100).toFixed(0)}% VaR (%)`,
                    line: { color: '#E4E4E7', width: 2 },
                  },
                  {
                    x: backtest.dates.filter((_, idx) => backtest.realized_loss_pct[idx] > selectedModel.predicted_var_pct[idx]),
                    y: backtest.realized_loss_pct
                      .filter((loss, idx) => loss > selectedModel.predicted_var_pct[idx])
                      .map((v) => v * 100),
                    type: 'scatter',
                    mode: 'markers',
                    name: 'VaR Breach / Exception',
                    marker: { color: '#C75B64', size: 7, symbol: 'circle' },
                  },
                ]}
                layout={{
                  xaxis: { title: { text: 'Out-of-Sample Trading Session' } },
                  yaxis: { title: { text: '1-Day Loss / VaR (%)' } },
                }}
              />
            )}
          </section>

          {/* Statistical Coverage Comparison Table */}
          <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-3">
            <h3 className="text-sm font-semibold text-[#F4F4F5]">
              Kupiec Unconditional Coverage & Christoffersen Independence Diagnostics
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                    <th className="text-left py-2.5 px-2 font-medium">Methodology</th>
                    <th className="text-right py-2.5 px-2 font-medium">OOS Days</th>
                    <th className="text-right py-2.5 px-2 font-medium">Expected</th>
                    <th className="text-right py-2.5 px-2 font-medium">Actual</th>
                    <th className="text-right py-2.5 px-2 font-medium">Actual Rate</th>
                    <th className="text-right py-2.5 px-2 font-medium">Kupiec p-val</th>
                    <th className="text-right py-2.5 px-2 font-medium">Christoffersen p-val</th>
                    <th className="text-right py-2.5 px-2 font-medium">Calibration Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                  {Object.values(backtest.models).map((m) => {
                    const isCalibrated = m.calibration_verdict === 'CALIBRATED';
                    return (
                      <tr key={m.method} className="hover:bg-[#141418]/70">
                        <td className="py-2.5 px-2 font-sans font-medium text-[#F4F4F5]">
                          {formatMethodLabel(m.method)}
                        </td>
                        <td className="py-2.5 px-2 text-right text-[#71717A]">{m.observations}</td>
                        <td className="py-2.5 px-2 text-right text-[#71717A]">{m.expected_violations}</td>
                        <td className="py-2.5 px-2 text-right text-[#F4F4F5]">{m.actual_violations}</td>
                        <td className="py-2.5 px-2 text-right text-[#F4F4F5]">
                          {formatPct(m.actual_violation_rate)}
                        </td>
                        <td
                          className={`py-2.5 px-2 text-right ${
                            m.kupiec_passed ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
                          }`}
                        >
                          {formatNum(m.kupiec_p_value, 4)}
                        </td>
                        <td
                          className={`py-2.5 px-2 text-right ${
                            m.christoffersen_passed ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
                          }`}
                        >
                          {formatNum(m.christoffersen_p_value, 4)}
                        </td>
                        <td
                          className={`py-2.5 px-2 text-right font-semibold ${
                            isCalibrated ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
                          }`}
                        >
                          {m.calibration_verdict}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-[#71717A] pt-2 border-t border-[#1A1A1E] leading-relaxed">
              {backtest.methodology_note}
            </p>
          </section>
        </>
      )}
    </div>
  );
}
