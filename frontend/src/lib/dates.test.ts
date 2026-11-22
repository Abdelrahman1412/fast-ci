import { describe, expect, it } from 'vitest';
import { addDays, daysInMonth, parseIsoDate, toIso, workingDays } from './dates';

const MON = '2026-11-02';

describe('parseIsoDate', () => {
  it.each(['2026-01-01', '2024-02-29', '1999-12-31', '2026-11-30'])('accepts %s', (value) => {
    expect(toIso(parseIsoDate(value))).toBe(value);
  });
  it.each(['', '2026-1-1', '2026/01/01', '2026-02-30', '2025-02-29', '2026-13-01', 'yesterday', '20260101'])(
    'rejects %j',
    (value) => {
      expect(() => parseIsoDate(value)).toThrow();
    },
  );
});

describe('workingDays', () => {
  it.each([
    ['sat-sun', 1, 1], ['sat-sun', 5, 5], ['sat-sun', 7, 5], ['sat-sun', 14, 10], ['sat-sun', 28, 20],
    ['fri-sat', 1, 1], ['fri-sat', 5, 4], ['fri-sat', 7, 5], ['fri-sat', 14, 10],
    ['fri', 7, 6], ['fri', 14, 12],
  ] as const)('%s weekend over %i days is %i', (weekend, length, expected) => {
    const end = toIso(addDays(parseIsoDate(MON), length - 1));
    expect(workingDays(MON, end, weekend)).toBe(expected);
  });

  it.each(Array.from({ length: 12 }, (_, i) => i + 1))('%i whole weeks are 5 days each', (weeks) => {
    const end = toIso(addDays(parseIsoDate(MON), weeks * 7 - 1));
    expect(workingDays(MON, end)).toBe(weeks * 5);
  });

  it.each(Array.from({ length: 7 }, (_, i) => i))('single day at offset %i counts once or not at all', (offset) => {
    const day = toIso(addDays(parseIsoDate(MON), offset));
    expect(workingDays(day, day)).toBe(offset >= 5 ? 0 : 1);
  });

  it('skips holidays', () => {
    expect(workingDays(MON, '2026-11-06', 'sat-sun', ['2026-11-04'])).toBe(4);
  });

  it('does not double count a holiday on a weekend', () => {
    expect(workingDays(MON, '2026-11-08', 'sat-sun', ['2026-11-07'])).toBe(5);
  });

  it('rejects a reversed range', () => {
    expect(() => workingDays('2026-11-06', MON)).toThrow('before');
  });
});

describe('daysInMonth', () => {
  it.each([
    [2026, 1, 31], [2026, 2, 28], [2026, 3, 31], [2026, 4, 30], [2026, 5, 31], [2026, 6, 30],
    [2026, 7, 31], [2026, 8, 31], [2026, 9, 30], [2026, 10, 31], [2026, 11, 30], [2026, 12, 31],
    [2024, 2, 29], [2000, 2, 29], [1900, 2, 28],
  ])('%i-%i has %i days', (year, month, days) => {
    expect(daysInMonth(year, month)).toBe(days);
  });
});
