import React, { useState } from 'react';
import { api } from '../services/api';
import type { ExperimentDetail, ExperimentSummary } from '../types/quant';
import { formatINR, formatMethodLabel, formatPct } from '../utils/formatters';

interface ResearchReportsViewProps {
  experiments: ExperimentSummary[];
  activeExperiment: ExperimentDetail | null;
  onSelectExperiment: (id: string) => void;
  onDeleteExperiment: (id: string) => void;
}

export function ResearchReportsView({
  experiments,
  activeExperiment,
  onSelectExperiment,
  onDeleteExperiment,
}: ResearchReportsViewProps) {
  const [compareLeftId, setCompareLeftId] = useState<string>('');
  const [compareRightId, setCompareRightId] = useState<string>('');
  const [comparison, setComparison] = useState<{ left: ExperimentSummary; right: ExperimentSummary } | null>(null);

  const handleCompare = async () => {
    if (!compareLeftId || !compareRightId) return;
    const res = await api.compareExperiments(compareLeftId, compareRightId);
    setComparison(res);
  };

  return (
    <div className="space-y-6">
      {/* Persisted Experiment Registry */}
      <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[#F4F4F5]">Experiment History & Reproducibility Registry</h2>
            <p className="text-xs text-[#71717A] mt-0.5">
              Every simulation run is persisted with seed, data window, model configuration, and exportable PDF research report.
            </p>
          </div>
          {activeExperiment && (
            <a
              href={api.getReportDownloadUrl(activeExperiment.id)}
              download={`BLACKSWAN_Report_${activeExperiment.id}.pdf`}
              className="px-4 py-2 text-xs font-semibold bg-[#F4F4F5] text-[#050506] rounded-md hover:bg-[#E4E4E7] transition-colors"
            >
              Download Active PDF Report
            </a>
          )}
        </div>

        {experiments.length === 0 ? (
          <div className="py-8 text-center text-xs text-[#71717A]">
            No experiments recorded yet. Launch a simulation from the Simulation Lab to generate your first audit record.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                  <th className="text-left py-2.5 px-2 font-medium">Experiment</th>
                  <th className="text-left py-2.5 px-2 font-medium">Method</th>
                  <th className="text-right py-2.5 px-2 font-medium">Paths / Days</th>
                  <th className="text-right py-2.5 px-2 font-medium">Seed</th>
                  <th className="text-right py-2.5 px-2 font-medium">95% VaR</th>
                  <th className="text-right py-2.5 px-2 font-medium">95% CVaR</th>
                  <th className="text-right py-2.5 px-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                {experiments.map((exp) => {
                  const isActive = activeExperiment?.id === exp.id;
                  return (
                    <tr key={exp.id} className={isActive ? 'bg-[#141418]' : 'hover:bg-[#141418]/60'}>
                      <td className="py-2.5 px-2 font-sans">
                        <div className="font-medium text-[#F4F4F5]">{exp.name}</div>
                        <div className="font-mono text-[11px] text-[#71717A]">
                          {exp.id} · {exp.data_start_date} / {exp.data_end_date}
                        </div>
                      </td>
                      <td className="py-2.5 px-2 font-sans text-[#F4F4F5]">
                        {formatMethodLabel(exp.simulation_method)}
                      </td>
                      <td className="py-2.5 px-2 text-right text-[#71717A]">
                        {exp.n_paths.toLocaleString()} / {exp.horizon_days}d
                      </td>
                      <td className="py-2.5 px-2 text-right text-[#71717A]">{exp.random_seed}</td>
                      <td className="py-2.5 px-2 text-right text-[#C89D5C]">
                        {formatINR(exp.headline_metrics.var_95_inr)}
                      </td>
                      <td className="py-2.5 px-2 text-right text-[#C75B64]">
                        {formatINR(exp.headline_metrics.cvar_95_inr)}
                      </td>
                      <td className="py-2.5 px-2 text-right font-sans space-x-2 whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => onSelectExperiment(exp.id)}
                          className="text-xs font-medium text-[#E4E4E7] hover:underline"
                        >
                          {isActive ? 'Loaded' : 'Load'}
                        </button>
                        <a
                          href={api.getReportDownloadUrl(exp.id)}
                          download={`BLACKSWAN_Report_${exp.id}.pdf`}
                          className="text-xs font-medium text-[#A1A1AA] hover:text-[#F4F4F5] hover:underline"
                        >
                          PDF
                        </a>
                        <button
                          type="button"
                          aria-label={`Delete ${exp.name}`}
                          onClick={() => onDeleteExperiment(exp.id)}
                          className="text-xs font-medium text-[#C75B64] hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Side-by-Side Experiment Comparison */}
      {experiments.length >= 2 && (
        <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-[#F4F4F5]">Side-by-Side Experiment Comparison</h3>
              <p className="text-xs text-[#71717A] mt-0.5">
                Compare portfolio risk metrics across methodologies, seeds, or horizon configurations.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <select
                aria-label="Left comparison experiment"
                value={compareLeftId}
                onChange={(e) => setCompareLeftId(e.target.value)}
                className="bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-2.5 py-1.5 text-[#F4F4F5]"
              >
                <option value="">Select Experiment A</option>
                {experiments.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} ({e.id})
                  </option>
                ))}
              </select>
              <select
                aria-label="Right comparison experiment"
                value={compareRightId}
                onChange={(e) => setCompareRightId(e.target.value)}
                className="bg-[#08080A] border border-[#222228] focus:border-[#71717A] focus:outline-none rounded-md px-2.5 py-1.5 text-[#F4F4F5]"
              >
                <option value="">Select Experiment B</option>
                {experiments.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} ({e.id})
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleCompare}
                disabled={!compareLeftId || !compareRightId}
                className="px-3 py-1.5 font-semibold bg-[#141418] border border-[#222228] text-[#F4F4F5] rounded-md hover:border-[#E4E4E7] transition-colors disabled:opacity-40"
              >
                Compare
              </button>
            </div>
          </div>

          {comparison && (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                  <th className="text-left py-2 font-medium">Metric</th>
                  <th className="text-right py-2 font-medium">{comparison.left.name}</th>
                  <th className="text-right py-2 font-medium">{comparison.right.name}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                <tr>
                  <td className="py-2 font-sans text-[#71717A]">Methodology</td>
                  <td className="py-2 text-right font-sans text-[#F4F4F5]">{formatMethodLabel(comparison.left.simulation_method)}</td>
                  <td className="py-2 text-right font-sans text-[#F4F4F5]">{formatMethodLabel(comparison.right.simulation_method)}</td>
                </tr>
                <tr>
                  <td className="py-2 font-sans text-[#71717A]">Expected Terminal Value</td>
                  <td className="py-2 text-right text-[#F4F4F5]">{formatINR(comparison.left.headline_metrics.expected_terminal_value)}</td>
                  <td className="py-2 text-right text-[#F4F4F5]">{formatINR(comparison.right.headline_metrics.expected_terminal_value)}</td>
                </tr>
                <tr>
                  <td className="py-2 font-sans text-[#71717A]">95% VaR</td>
                  <td className="py-2 text-right text-[#C89D5C]">{formatINR(comparison.left.headline_metrics.var_95_inr)}</td>
                  <td className="py-2 text-right text-[#C89D5C]">{formatINR(comparison.right.headline_metrics.var_95_inr)}</td>
                </tr>
                <tr>
                  <td className="py-2 font-sans text-[#71717A]">95% CVaR</td>
                  <td className="py-2 text-right text-[#C75B64]">{formatINR(comparison.left.headline_metrics.cvar_95_inr)}</td>
                  <td className="py-2 text-right text-[#C75B64]">{formatINR(comparison.right.headline_metrics.cvar_95_inr)}</td>
                </tr>
                <tr>
                  <td className="py-2 font-sans text-[#71717A]">GARCH Cond. Vol (Ann.)</td>
                  <td className="py-2 text-right text-[#F4F4F5]">{formatPct(comparison.left.headline_metrics.garch_vol_ann)}</td>
                  <td className="py-2 text-right text-[#F4F4F5]">{formatPct(comparison.right.headline_metrics.garch_vol_ann)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </section>
      )}

      {/* Data Provenance & Quality Report for Active Experiment */}
      {activeExperiment && activeExperiment.data_provenance && (
        <section className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-[#F4F4F5]">Data Provenance & Manifest Audit</h3>
          <p className="text-xs text-[#71717A]">{activeExperiment.data_provenance.alignment_policy}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#1A1A1E] text-[#71717A]">
                  <th className="text-left py-2 font-medium">Symbol</th>
                  <th className="text-left py-2 font-medium">Source</th>
                  <th className="text-right py-2 font-medium">Coverage</th>
                  <th className="text-right py-2 font-medium">Observations</th>
                  <th className="text-right py-2 font-medium">Missing %</th>
                  <th className="text-right py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1A1A1E] font-mono tabular-nums">
                {activeExperiment.data_provenance.assets.map((a) => (
                  <tr key={a.symbol}>
                    <td className="py-2 font-semibold text-[#F4F4F5]">{a.symbol}</td>
                    <td className="py-2 font-sans text-[#71717A]">{a.data_source}</td>
                    <td className="py-2 text-right text-[#71717A]">
                      {a.start_date} → {a.end_date}
                    </td>
                    <td className="py-2 text-right text-[#F4F4F5]">{a.observation_count}</td>
                    <td className="py-2 text-right text-[#71717A]">{a.missing_observation_pct.toFixed(2)}%</td>
                    <td className="py-2 text-right text-[#E4E4E7]">{a.validation_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
