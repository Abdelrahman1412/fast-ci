import { expect, test } from '../fixtures/mock-api';

test.beforeEach(async ({ page }) => {
  await page.goto('/#/employees');
});

test('lists every employee', async ({ page }) => {
  await expect(page.getByRole('row')).toHaveCount(5);
  await expect(page.getByRole('cell', { name: 'Lina Saeed' })).toBeVisible();
});

test('search narrows the table', async ({ page }) => {
  await page.getByLabel('Search').fill('finance');
  await expect(page.getByRole('row')).toHaveCount(2);
  await expect(page.getByRole('cell', { name: 'Omar Haddad' })).toBeVisible();
});

test('search with no match says so', async ({ page }) => {
  await page.getByLabel('Search').fill('nobody here');
  await expect(page.getByText('No employees match')).toBeVisible();
});

test('sorting by salary puts the lowest first', async ({ page }) => {
  await page.getByLabel('Sort by').selectOption('salary');
  await expect(page.getByRole('row').nth(1)).toContainText('Maya Costa');
});

test('headcount leaves out terminated staff', async ({ page }) => {
  await expect(page.getByTestId('headcount')).toHaveText(['Engineering: 2', 'Finance: 1']);
});

test('a server error is shown, not swallowed', async ({ page, mockApi }) => {
  mockApi.on('GET /employees', (route) => route.fulfill({ status: 500, body: '{"detail":"database unavailable"}' }));
  await page.reload();
  await expect(page.getByRole('alert')).toHaveText('The server said: database unavailable');
});
