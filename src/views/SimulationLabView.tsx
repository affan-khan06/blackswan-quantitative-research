import React, { useMemo, useState } from 'react';
import { api } from '../services/api';
import type {
  AssetMetadata,
  ExperimentDetail,
  PortfolioAllocation,
  RebalanceMode,
  SimulationMethod,
} from '../types/quant';
import { formatINR, normalizeWeightsEqual, validatePortfolioWeights } from '../utils/formatters';

interface SimulationLabViewProps {
  universe: AssetMetadata[];
  defaultSymbols: string[];
  onExperimentCompleted: (exp: ExperimentDetail) => void;
}

export function SimulationLabView({
  universe,
  defaultSymbols,
  onExperimentCompleted,
}: SimulationLabViewProps) {
  const investableAssets = useMemo(
    () => universe.filter((a) => a.category !== 'VOLATILITY_INDEX'),
    [universe]
  );

  const [experimentName, setExperimentName] = useState('NSE Multi-Asset Tail Risk Study');
  const [allocations, setAllocations] = useState<PortfolioAllocation[]>(() =>
    normalizeWeightsEqual(
      defaultSymbols.length > 0 ? defaultSymbols : ['NIFTY50', 'RELIANCE', 'HDFCBANK', 'INFY', 'LT', 'ITC']
    )
  );
  const [startDate, setStartDate] = useState('2017-01-01');
  const [initialCapital, setInitialCapital] = useState(1000000);
  const [riskFreeRate, setRiskFreeRate] = useState(0.065);
  const [method, setMethod] = useState<SimulationMethod>('regime_switching_mc');
  const [nPaths, setNPaths] = useState(2000);
  const [horizonDays, setHorizonDays] = useState(63);
  const [confidenceLevel, setConfidenceLevel] = useState(0.95);
  const [randomSeed, setRandomSeed] = useState(42);
  const [rebalancing, setRebalancing] = useState<RebalanceMode>('daily');
  const [txCostBps, setTxCostBps] = useState(5);
  const [blockLength, setBlockLength] = useState(10);
  const [crisisCorrStress, setCrisisCorrStress] = useState(false);
  const [runComparison, setRunComparison] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const validation = useMemo(() => validatePortfolioWeights(allocations), [allocations]);

  const toggleAsset = (symbol: string) => {
    const exists = allocations.some((a) => a.symbol === symbol);
    if (exists) {
      if (allocations.length <= 1) return;
      setAllocations(allocations.filter((a) => a.symbol !== symbol));
    } else {
      setAllocations([...allocations, { symbol, weight: 0.1 }]);
    }
  };

  const updateWeightPct = (symbol: string, pctValue: number) => {
    setAllocations((prev) =>
      prev.map((a) => (a.symbol === symbol ? { ...a, weight: pctValue / 100 } : a))
    );
  };

  const handleEqualize = () => {
    setAllocations(normalizeWeightsEqual(allocations.map((a) => a.symbol)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!validation.valid) {
      setErrorMsg(validation.error);
      return;
    }

    setSubmitting(true);
    setJobMessage('Submitting simulation job to FastAPI quant engine...');
    try {
      const job = await api.launchSimulation({
        name: experimentName.trim() || 'NSE Risk Simulation',
        allocations,
        start_date: startDate,
        initial_capital: Number(initialCapital),
        risk_free_rate: Number(riskFreeRate),
        simulation_method: method,
        n_paths: Number(nPaths),
        horizon_days: Number(horizonDays),
        confidence_level: Number(confidenceLevel),
        random_seed: Number(randomSeed),
        rebalancing,
        transaction_cost_bps: Number(txCostBps),
        block_length: Number(blockLength),
        crisis_correlation_stress: crisisCorrStress,
        run_method_comparison: runComparison,
      });

      setJobMessage(`Job ${job.job_id} running (acquiring NSE data, fitting GARCH/HMM, simulating paths)...`);

      // Poll real backend job status until COMPLETED or FAILED
      for (let attempt = 0; attempt < 180; attempt++) {
        await new Promise((r) => setTimeout(r, 600));
        const status = await api.pollJob(job.job_id);
        if (status.status === 'COMPLETED') {
          const detail = await api.getExperiment(status.experiment_id);
          onExperimentCompleted(detail);
          setJobMessage(null);
          setSubmitting(false);
          return;
        }
        if (status.status === 'FAILED') {
          throw new Error(status.error || 'Simulation job failed on backend.');
        }
      }
      throw new Error('Simulation polling timed out.');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Simulation failed.');
      setJobMessage(null);
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 xl:grid-cols-12 gap-6">
      {/* Left: Asset Selector & Weight Editor */}
      <section className="xl:col-span-7 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[#F4F4F5]">1. Portfolio Universe & Weights</h2>
            <p className="text-xs text-[#71717A] mt-0.5">
              Select NSE instruments and assign target allocation weights summing strictly to 100.00%.
            </p>
          </div>
          <button
            type="button"
            onClick={handleEqualize}
            className="px-3 py-1.5 text-xs font-medium bg-[#141418] border border-[#222228] text-[#E4E4E7] rounded-md hover:border-[#52525B] transition-colors"
          >
            Equal Weight ({allocations.length})
          </button>
        </div>

        {/* Asset Toggle Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {investableAssets.map((asset) => {
            const selected = allocations.some((a) => a.symbol === asset.symbol);
            return (
              <button
                key={asset.symbol}
                type="button"
                onClick={() => toggleAsset(asset.symbol)}
                aria-pressed={selected}
                className={`px-3 py-2 rounded-md border text-left transition-colors ${
                  selected
                    ? 'bg-[#16161B] border-[#E4E4E7] text-[#F4F4F5]'
                    : 'bg-[#08080A] border-[#1A1A1E] text-[#71717A] hover:text-[#D4D4D8] hover:border-[#27272D]'
                }`}
              >
                <div className="text-xs font-mono font-semibold">{asset.symbol}</div>
                <div className="text-[11px] text-[#71717A] truncate">{asset.sector}</div>
              </button>
            );
          })}
        </div>

        {/* Weight Editor Table */}
        <div className="border-t border-[#1A1A1E] pt-4 space-y-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-[#E4E4E7]">Allocation Weights</span>
            <span
              className={`font-mono tabular-nums font-semibold ${
                validation.valid ? 'text-[#E4E4E7]' : 'text-[#C75B64]'
              }`}
            >
              Total: {(validation.totalWeight * 100).toFixed(2)}%
            </span>
          </div>

          <div className="space-y-2">
            {allocations.map((alloc) => {
              const meta = universe.find((u) => u.symbol === alloc.symbol);
              const pctVal = Number((alloc.weight * 100).toFixed(2));
              return (
                <div
                  key={alloc.symbol}
                  className="grid grid-cols-12 items-center gap-3 bg-[#08080A] border border-[#1A1A1E] rounded-md px-3 py-2"
                >
                  <div className="col-span-5 sm:col-span-4 min-w-0">
                    <div className="text-xs font-mono font-semibold text-[#F4F4F5]">{alloc.symbol}</div>
                    <div className="text-[11px] text-[#71717A] truncate">{meta?.name}</div>
                  </div>
                  <div className="col-span-4 sm:col-span-5">
                    <input
                      type="range"
                      aria-label={`${alloc.symbol} weight slider`}
                      min={1}
                      max={100}
                      step={0.5}
                      value={pctVal}
                      onChange={(e) => updateWeightPct(alloc.symbol, Number(e.target.value))}
                      className="w-full accent-[#E4E4E7]"
                    />
                  </div>
                  <div className="col-span-3 flex items-center justify-end gap-1.5">
                    <input
                      type="number"
                      aria-label={`${alloc.symbol} weight percent`}
                      min={0.01}
                      max={100}
                      step="any"
                      value={pctVal}
                      onChange={(e) => updateWeightPct(alloc.symbol, Number(e.target.value))}
                      className="w-20 bg-[#0F0F12] border border-[#222228] rounded px-2 py-1 text-right text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
                    />
                    <span className="text-xs font-mono text-[#71717A]">%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Right: Stochastic Model Configuration */}
      <section className="xl:col-span-5 bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-5 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-[#F4F4F5]">2. Simulation & Model Parameters</h2>
          <p className="text-xs text-[#71717A] mt-0.5">
            Configure stochastic generator, horizon, seed reproducibility, and crisis correlation stress.
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <label htmlFor="exp-name" className="block text-xs text-[#A1A1AA] mb-1">
              Experiment Title
            </label>
            <input
              id="exp-name"
              type="text"
              value={experimentName}
              onChange={(e) => setExperimentName(e.target.value)}
              className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-sm text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="sim-method" className="block text-xs text-[#A1A1AA] mb-1">
                Simulation Methodology
              </label>
              <select
                id="sim-method"
                value={method}
                onChange={(e) => setMethod(e.target.value as SimulationMethod)}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-2 py-2 text-xs font-medium text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              >
                <option value="regime_switching_mc">Regime-Switching MC</option>
                <option value="gaussian_mc">Gaussian Monte Carlo</option>
                <option value="historical_bootstrap">Historical Bootstrap</option>
                <option value="block_bootstrap">Circular Block Bootstrap</option>
              </select>
            </div>

            <div>
              <label htmlFor="sim-capital" className="block text-xs text-[#A1A1AA] mb-1">
                Initial Capital (INR)
              </label>
              <input
                id="sim-capital"
                type="number"
                min={10000}
                step={10000}
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="sim-paths" className="block text-xs text-[#A1A1AA] mb-1">
                Paths (N)
              </label>
              <input
                id="sim-paths"
                type="number"
                min={200}
                max={10000}
                step={50}
                value={nPaths}
                onChange={(e) => setNPaths(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="sim-horizon" className="block text-xs text-[#A1A1AA] mb-1">
                Horizon (Days)
              </label>
              <input
                id="sim-horizon"
                type="number"
                min={5}
                max={252}
                value={horizonDays}
                onChange={(e) => setHorizonDays(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="sim-seed" className="block text-xs text-[#A1A1AA] mb-1">
                Random Seed
              </label>
              <input
                id="sim-seed"
                type="number"
                min={0}
                value={randomSeed}
                onChange={(e) => setRandomSeed(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="sim-conf" className="block text-xs text-[#A1A1AA] mb-1">
                Confidence
              </label>
              <select
                id="sim-conf"
                value={confidenceLevel}
                onChange={(e) => setConfidenceLevel(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-xs font-mono text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              >
                <option value={0.95}>95%</option>
                <option value={0.99}>99%</option>
                <option value={0.90}>90%</option>
              </select>
            </div>
            <div>
              <label htmlFor="sim-rebal" className="block text-xs text-[#A1A1AA] mb-1">
                Rebalancing
              </label>
              <select
                id="sim-rebal"
                value={rebalancing}
                onChange={(e) => setRebalancing(e.target.value as RebalanceMode)}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-2 py-2 text-xs text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              >
                <option value="daily">Daily Rebal</option>
                <option value="buy_and_hold">Buy & Hold</option>
              </select>
            </div>
            <div>
              <label htmlFor="sim-start" className="block text-xs text-[#A1A1AA] mb-1">
                History Start
              </label>
              <input
                id="sim-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-2 py-2 text-xs font-mono text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="sim-rf" className="block text-xs text-[#A1A1AA] mb-1">
                Risk-Free Rate
              </label>
              <input
                id="sim-rf"
                type="number"
                step={0.001}
                min={0}
                max={0.2}
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-2.5 py-2 text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="sim-tx" className="block text-xs text-[#A1A1AA] mb-1">
                Tx Cost (bps)
              </label>
              <input
                id="sim-tx"
                type="number"
                min={0}
                max={100}
                value={txCostBps}
                onChange={(e) => setTxCostBps(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="sim-blk" className="block text-xs text-[#A1A1AA] mb-1">
                Block Len (d)
              </label>
              <input
                id="sim-blk"
                type="number"
                min={2}
                max={63}
                value={blockLength}
                onChange={(e) => setBlockLength(Number(e.target.value))}
                className="w-full bg-[#08080A] border border-[#222228] rounded-md px-3 py-2 text-xs font-mono tabular-nums text-[#F4F4F5] focus:border-[#71717A] focus:outline-none"
              />
            </div>
          </div>

          <div className="pt-2 space-y-2">
            <label className="flex items-center gap-2.5 text-xs text-[#D4D4D8] cursor-pointer">
              <input
                type="checkbox"
                checked={crisisCorrStress}
                onChange={(e) => setCrisisCorrStress(e.target.checked)}
                className="accent-[#E4E4E7]"
              />
              <span>Enable Crisis Correlation Stress in HIGH_VOL Regime (ρ → 0.85)</span>
            </label>
            <label className="flex items-center gap-2.5 text-xs text-[#D4D4D8] cursor-pointer">
              <input
                type="checkbox"
                checked={runComparison}
                onChange={(e) => setRunComparison(e.target.checked)}
                className="accent-[#E4E4E7]"
              />
              <span>Benchmark all 4 simulation methodologies side-by-side</span>
            </label>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-md bg-[#C75B64]/10 border border-[#C75B64]/35 text-xs text-[#E28A91]">
            {errorMsg}
          </div>
        )}

        {jobMessage && (
          <div className="p-3 rounded-md bg-[#141418] border border-[#27272D] text-xs font-mono text-[#E4E4E7]">
            {jobMessage}
          </div>
        )}

        <div className="pt-2 flex items-center justify-between gap-3">
          <div className="text-xs font-mono text-[#71717A] tabular-nums">
            Capital: {formatINR(initialCapital)}
          </div>
          <button
            type="submit"
            disabled={submitting || !validation.valid}
            className="px-5 py-2 text-xs font-semibold bg-[#F4F4F5] text-[#050506] rounded-md hover:bg-[#E4E4E7] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? 'Running Simulation...' : 'Start Simulation'}
          </button>
        </div>
      </section>
    </form>
  );
}
