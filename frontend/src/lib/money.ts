export function round2(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function formatMoney(value: number, currency = 'AED', locale = 'en-US'): string {
  return new Intl.NumberFormat(locale, { style: 'currency', currency, minimumFractionDigits: 2 }).format(value);
}

export function parseMoney(input: string): number {
  const cleaned = input.replace(/[,\s]/g, '');
  if (!/^-?\d+(\.\d{1,2})?$/.test(cleaned)) throw new Error(`not an amount: ${input}`);
  return Number(cleaned);
}
