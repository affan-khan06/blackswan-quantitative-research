import type { PortfolioAllocation } from '../types/quant';

export function formatINR(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value);
}

export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNum(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return value.toFixed(decimals);
}

export function formatMethodLabel(method: string): string {
  switch (method) {
    case 'gaussian_mc':
      return 'Gaussian Monte Carlo';
    case 'historical_bootstrap':
      return 'Historical Bootstrap';
    case 'block_bootstrap':
      return 'Block Bootstrap';
    case 'regime_switching_mc':
      return 'Regime-Switching MC';
    default:
      return method;
  }
}

export function validatePortfolioWeights(allocations: PortfolioAllocation[]): {
  valid: boolean;
  totalWeight: number;
  error: string | null;
} {
  if (allocations.length === 0) {
    return { valid: false, totalWeight: 0, error: 'Select at least one NSE asset.' };
  }
  for (const a of allocations) {
    if (!Number.isFinite(a.weight) || a.weight <= 0 || a.weight > 1) {
      return {
        valid: false,
        totalWeight: allocations.reduce((acc, item) => acc + (Number.isFinite(item.weight) ? item.weight : 0), 0),
        error: `Asset ${a.symbol} weight must be between 0% and 100%.`,
      };
    }
  }
  const total = allocations.reduce((acc, a) => acc + a.weight, 0);
  if (Math.abs(total - 1.0) > 1e-3) {
    return {
      valid: false,
      totalWeight: total,
      error: `Portfolio weights sum to ${(total * 100).toFixed(2)}%; must equal 100.00%.`,
    };
  }
  return { valid: true, totalWeight: total, error: null };
}

export function normalizeWeightsEqual(symbols: string[]): PortfolioAllocation[] {
  if (symbols.length === 0) return [];
  const base = Math.floor((10000 / symbols.length)) / 10000;
  const result = symbols.map((symbol, idx) => ({
    symbol,
    weight: idx === symbols.length - 1 ? Number((1 - base * (symbols.length - 1)).toFixed(4)) : base,
  }));
  return result;
}
