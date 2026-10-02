import { describe, it, expect } from 'vitest';
import { formatPrice, formatCurrency, formatPercent } from '@/shared/lib/formatters';

describe('Shared Formatters (FSD Primitives)', () => {
  it('formats high-value asset prices with 2 decimals (e.g., BTC, Gold)', () => {
    expect(formatPrice(65432.1)).toBe('65,432.10');
    expect(formatCurrency(4183.43)).toBe('$4,183.43');
  });

  it('formats mid-value assets with dynamic precision (e.g., SOL, NEAR)', () => {
    expect(formatPrice(4.8842)).toBe('4.8842');
    expect(formatCurrency(4.8842)).toBe('$4.8842');
  });

  it('formats micro-value tokens with up to 6 or 8 decimals', () => {
    expect(formatPrice(0.00045678)).toBe('0.00045678');
    expect(formatCurrency(0.00045678)).toBe('$0.00045678');
  });

  it('handles null, undefined and NaN gracefully with institutional dash', () => {
    expect(formatPrice(null)).toBe('—');
    expect(formatPrice(undefined)).toBe('—');
    expect(formatPrice(NaN)).toBe('—');
    expect(formatCurrency(null)).toBe('—');
  });

  it('formats percentage values with explicit sign', () => {
    expect(formatPercent(4.55)).toBe('+4.55%');
    expect(formatPercent(-2.1)).toBe('-2.10%');
    expect(formatPercent(0)).toBe('0.00%');
    expect(formatPercent(null)).toBe('0.00%');
  });
});
