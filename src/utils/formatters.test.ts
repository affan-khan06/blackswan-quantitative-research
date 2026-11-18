import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatMethodLabel,
  formatPct,
  normalizeWeightsEqual,
  validatePortfolioWeights,
} from './formatters';

test('validatePortfolioWeights accepts exact 100% sum and rejects mismatched sums', () => {
  const valid = validatePortfolioWeights([
    { symbol: 'NIFTY50', weight: 0.4 },
    { symbol: 'RELIANCE', weight: 0.35 },
    { symbol: 'HDFCBANK', weight: 0.25 },
  ]);
  assert.equal(valid.valid, true);
  assert.equal(valid.error, null);

  const invalidSum = validatePortfolioWeights([
    { symbol: 'NIFTY50', weight: 0.5 },
    { symbol: 'RELIANCE', weight: 0.3 },
  ]);
  assert.equal(invalidSum.valid, false);
  assert.match(invalidSum.error ?? '', /100\.00%/);

  const empty = validatePortfolioWeights([]);
  assert.equal(empty.valid, false);
});

test('normalizeWeightsEqual distributes weights summing exactly to 1.0', () => {
  const eq = normalizeWeightsEqual(['NIFTY50', 'RELIANCE', 'HDFCBANK']);
  const total = eq.reduce((acc, item) => acc + item.weight, 0);
  assert.ok(Math.abs(total - 1.0) < 1e-9);
});

test('formatPct and formatMethodLabel render deterministic outputs', () => {
  assert.equal(formatPct(0.12345, 2), '12.35%');
  assert.equal(formatPct(null), '—');
  assert.equal(formatMethodLabel('regime_switching_mc'), 'Regime-Switching MC');
});
