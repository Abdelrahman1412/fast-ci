import { daysInMonth } from './dates';
import { round2 } from './money';

export type Bracket = readonly [lowerBound: number, rate: number];

export const DEFAULT_BRACKETS: readonly Bracket[] = [
  [0, 0],
  [5000, 0.05],
  [15000, 0.1],
  [40000, 0.15],
];

export function progressiveTax(taxable: number, brackets: readonly Bracket[] = DEFAULT_BRACKETS): number {
  if (taxable < 0) throw new Error('taxable income cannot be negative');
  const ordered = [...brackets].sort((a, b) => a[0] - b[0]);
  let tax = 0;
  ordered.forEach(([lower, rate], i) => {
    const upper = ordered[i + 1]?.[0];
    if (taxable <= lower) return;
    const top = upper === undefined ? taxable : Math.min(taxable, upper);
    tax += (top - lower) * rate;
  });
  return round2(tax);
}

export function prorate(amount: number, days: number, year: number, month: number): number {
  const total = daysInMonth(year, month);
  if (days < 0 || days > total) throw new Error(`days must be between 0 and ${total}`);
  return round2((amount * days) / total);
}

export function socialInsurance(basic: number, rate = 0.09, cap = 45000): number {
  return round2(Math.min(basic, cap) * rate);
}

export interface PayslipInput {
  basic: number;
  housing?: number;
  transport?: number;
  year: number;
  month: number;
  daysWorked?: number;
}

export function estimateNet(input: PayslipInput): { gross: number; deductions: number; net: number } {
  const days = input.daysWorked ?? daysInMonth(input.year, input.month);
  const monthly = input.basic + (input.housing ?? 0) + (input.transport ?? 0);
  const gross = prorate(monthly, days, input.year, input.month);
  const si = socialInsurance(prorate(input.basic, days, input.year, input.month));
  const tax = progressiveTax(Math.max(gross - si, 0));
  const deductions = round2(si + tax);
  return { gross, deductions, net: round2(gross - deductions) };
}
