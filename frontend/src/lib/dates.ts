export type Weekend = 'sat-sun' | 'fri-sat' | 'fri';

// JavaScript getUTCDay: Sunday = 0 ... Saturday = 6.
const WEEKENDS: Record<Weekend, ReadonlySet<number>> = {
  'sat-sun': new Set([6, 0]),
  'fri-sat': new Set([5, 6]),
  fri: new Set([5]),
};

export function parseIsoDate(value: string): Date {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error(`not an ISO date: ${value}`);
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
    throw new Error(`not a real date: ${value}`);
  }
  return date;
}

export function toIso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(date: Date, days: number): Date {
  return new Date(date.getTime() + days * 86_400_000);
}

export function workingDays(start: string, end: string, weekend: Weekend = 'sat-sun', holidays: string[] = []): number {
  const from = parseIsoDate(start);
  const to = parseIsoDate(end);
  if (to < from) throw new Error('end date is before start date');
  const off = WEEKENDS[weekend];
  const skip = new Set(holidays);
  let count = 0;
  for (let day = from; day <= to; day = addDays(day, 1)) {
    if (!off.has(day.getUTCDay()) && !skip.has(toIso(day))) count += 1;
  }
  return count;
}

export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}
