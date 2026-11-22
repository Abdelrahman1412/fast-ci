import { describe, expect, it } from 'vitest';
import { estimateNet, progressiveTax, prorate, socialInsurance } from './payroll';

describe('progressiveTax', () => {
  it.each([
    [0, 0], [4999.99, 0], [5000, 0], [6000, 50], [15000, 500], [16000, 600], [40000, 3000], [50000, 4500],
    [100000, 12000],
  ])('tax on %d is %d', (taxable, expected) => {
    expect(progressiveTax(taxable)).toBe(expected);
  });

  it.each(Array.from({ length: 30 }, (_, i) => i * 4000))('never exceeds the top rate at %d', (taxable) => {
    const tax = progressiveTax(taxable);
    expect(tax).toBeGreaterThanOrEqual(0);
    expect(tax).toBeLessThanOrEqual(taxable * 0.15);
  });

  it.each(Array.from({ length: 12 }, (_, i) => i * 5000))('is monotonic from %d', (low) => {
    expect(progressiveTax(low)).toBeLessThanOrEqual(progressiveTax(low + 2500));
  });

  it('rejects negative income', () => {
    expect(() => progressiveTax(-1)).toThrow();
  });

  it('accepts custom brackets in any order', () => {
    expect(progressiveTax(1000, [[500, 0.5], [0, 0]])).toBe(250);
  });
});

describe('prorate', () => {
  it.each(Array.from({ length: 31 }, (_, i) => i))('%i of 31 days', (days) => {
    expect(prorate(9300, days, 2026, 1)).toBe(Math.round(((9300 * days) / 31) * 100) / 100);
  });
  it.each([-1, 32])('rejects %i days', (days) => {
    expect(() => prorate(1000, days, 2026, 1)).toThrow();
  });
});

describe('socialInsurance', () => {
  it.each([[0, 0], [10000, 900], [45000, 4050], [90000, 4050]])('on %d basic is %d', (basic, expected) => {
    expect(socialInsurance(basic)).toBe(expected);
  });
});

describe('estimateNet', () => {
  it('matches the backend for a full month', () => {
    expect(estimateNet({ basic: 12000, housing: 3000, transport: 1000, year: 2026, month: 4 })).toEqual({
      gross: 16000,
      deductions: 1080 + 496,
      net: 16000 - 1080 - 496,
    });
  });

  it.each([0, 1, 10, 15, 29, 30])('net identity holds with %i days worked', (daysWorked) => {
    const r = estimateNet({ basic: 20000, housing: 5000, year: 2026, month: 4, daysWorked });
    expect(r.net).toBeCloseTo(r.gross - r.deductions, 2);
    expect(r.net).toBeGreaterThanOrEqual(0);
  });
});
