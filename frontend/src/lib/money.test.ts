import { describe, expect, it } from 'vitest';
import { formatMoney, parseMoney, round2 } from './money';

describe('round2', () => {
  it.each([
    [1.005, 1.01], [2.675, 2.68], [0.125, 0.13], [10, 10], [3.333, 3.33], [-1.005, -1], [0, 0], [99.999, 100],
  ])('round2(%d) = %d', (input, expected) => {
    expect(round2(input)).toBe(expected);
  });
});

describe('formatMoney', () => {
  it.each([
    [0, 'AED', 'AED 0.00'], [1234.5, 'AED', 'AED 1,234.50'], [1234.5, 'USD', '$1,234.50'], [1e6, 'EUR', '€1,000,000.00'],
  ])('%d in %s', (value, currency, expected) => {
    expect(formatMoney(value, currency).replace(/ /g, ' ')).toBe(expected);
  });
});

describe('parseMoney', () => {
  it.each([['12000', 12000], ['12,000.50', 12000.5], [' 7 500 ', 7500], ['-3.2', -3.2], ['0.01', 0.01]])(
    'parses %j',
    (input, expected) => {
      expect(parseMoney(input)).toBe(expected);
    },
  );
  it.each(['', 'abc', '1.234', '12.3.4', '$12', '1e5'])('rejects %j', (input) => {
    expect(() => parseMoney(input)).toThrow();
  });
});
