import { expect, test } from '../fixtures/mock-api';

test.beforeEach(async ({ page }) => {
  await page.goto('/#/leave');
});

test('shows pending requests', async ({ page }) => {
  await expect(page.locator('tbody tr')).toHaveCount(2);
});

test('approving updates the row in place', async ({ page }) => {
  const row = page.locator('tr[data-id="11"]');
  await row.getByRole('button', { name: 'Approve' }).click();
  await expect(row.locator('.status')).toHaveText('approved');
  await expect(page.getByText('Request approved.')).toBeVisible();
  await expect(row.getByRole('button')).toHaveCount(0);
});

test('rejecting updates the row in place', async ({ page }) => {
  const row = page.locator('tr[data-id="12"]');
  await row.getByRole('button', { name: 'Reject' }).click();
  await expect(row.locator('.status')).toHaveText('rejected');
});

test('a conflict from the server is shown', async ({ page, mockApi }) => {
  mockApi.on('POST /leave-requests/11/approve', (route) =>
    route.fulfill({ status: 409, contentType: 'application/json', body: '{"detail":"cannot move from approved to approved"}' }),
  );
  await page.locator('tr[data-id="11"]').getByRole('button', { name: 'Approve' }).click();
  await expect(page.getByRole('alert')).toHaveText('cannot move from approved to approved');
});

test('an empty queue says so', async ({ page, mockApi }) => {
  mockApi.leave.length = 0;
  await page.reload();
  await expect(page.getByText('Nothing to review')).toBeVisible();
});
