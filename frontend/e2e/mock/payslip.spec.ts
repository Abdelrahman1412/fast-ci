import { expect, test } from '../fixtures/mock-api';

test.beforeEach(async ({ page }) => {
  await page.goto('/#/payslip');
});

test('shows an estimate for the default salary', async ({ page }) => {
  await expect(page.getByTestId('gross')).toHaveText('AED 16,000.00');
  await expect(page.getByTestId('net')).toHaveText('AED 14,424.00');
});

test('recalculates when the basic changes', async ({ page }) => {
  await page.getByLabel('Basic').fill('30000');
  await expect(page.getByTestId('gross')).toHaveText('AED 34,000.00');
});

test('a zero salary gives a zero payslip', async ({ page }) => {
  for (const field of ['Basic', 'Housing', 'Transport']) await page.getByLabel(field).fill('0');
  await expect(page.getByTestId('net')).toHaveText('AED 0.00');
});

test('makes no API calls', async ({ page, mockApi }) => {
  await page.getByLabel('Basic').fill('15000');
  await expect(page.getByTestId('gross')).toHaveText('AED 19,000.00');
  expect(mockApi.calls).toEqual([]);
});
