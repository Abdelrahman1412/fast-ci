import { expect, test } from '@playwright/test';

// Runs against a real HTTP API (server/demo-api.mjs here; your backend in a real repo).
test.beforeEach(async ({ request }) => {
  await request.post('/api/__reset');
});

test('a request travels from the form to approval', async ({ page }) => {
  await page.goto('/#/leave/new');
  await page.getByLabel('Employee').selectOption({ label: 'Lina Saeed' });
  await page.getByLabel('Type').selectOption('annual');
  await page.getByLabel('From').fill('2026-12-07');
  await page.getByLabel('To').fill('2026-12-11');
  await page.getByRole('button', { name: 'Submit request' }).click();
  await expect(page.getByText(/Request #\d+ submitted for 5 day\(s\)\./)).toBeVisible();

  await page.goto('/#/leave');
  const row = page.locator('tbody tr', { hasText: 'Lina Saeed' });
  await row.getByRole('button', { name: 'Approve' }).click();
  await expect(row.locator('.status')).toHaveText('approved');
});

test('the server refuses an overlapping request', async ({ page }) => {
  await page.goto('/#/leave/new');
  await page.getByLabel('Employee').selectOption({ label: 'Ravi Menon' });
  await page.getByLabel('Type').selectOption('annual');
  await page.getByLabel('From').fill('2026-11-10');
  await page.getByLabel('To').fill('2026-11-12');
  await page.getByRole('button', { name: 'Submit request' }).click();
  await expect(page.getByRole('alert')).toHaveText('overlaps an existing request');
});

test('the employee list comes from the server', async ({ page }) => {
  await page.goto('/#/employees');
  await expect(page.getByRole('row')).toHaveCount(5);
});
