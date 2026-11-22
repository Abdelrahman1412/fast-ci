import { expect, test } from '../fixtures/mock-api';

test.beforeEach(async ({ page }) => {
  await page.goto('/#/leave/new');
});

test('an empty submit lists every problem', async ({ page, mockApi }) => {
  await page.getByRole('button', { name: 'Submit request' }).click();
  await expect(page.getByTestId('errors').locator('li')).toHaveText([
    'Choose an employee',
    'Choose a leave type',
    'Enter a valid start date',
    'Enter a valid end date',
  ]);
  expect(mockApi.calls).not.toContain('POST /leave-requests');
});

test('previews working days as dates are entered', async ({ page }) => {
  await page.getByLabel('From').fill('2026-11-02');
  await page.getByLabel('To').fill('2026-11-13');
  await expect(page.getByTestId('days-preview')).toHaveText('10 working day(s)');
});

test('rejects a reversed range', async ({ page }) => {
  await page.getByLabel('Employee').selectOption({ label: 'Lina Saeed' });
  await page.getByLabel('Type').selectOption('annual');
  await page.getByLabel('From').fill('2026-11-13');
  await page.getByLabel('To').fill('2026-11-02');
  await page.getByRole('button', { name: 'Submit request' }).click();
  await expect(page.getByTestId('errors')).toHaveText('End date is before start date');
});

test('submits a valid request', async ({ page, mockApi }) => {
  await page.getByLabel('Employee').selectOption({ label: 'Omar Haddad' });
  await page.getByLabel('Type').selectOption('sick');
  await page.getByLabel('From').fill('2026-11-02');
  await page.getByLabel('To').fill('2026-11-04');
  await page.getByRole('button', { name: 'Submit request' }).click();
  await expect(page.getByText('Request #99 submitted for 3 day(s).')).toBeVisible();
  expect(mockApi.leave.at(-1)?.employee_name).toBe('Omar Haddad');
});

test('shows the server reason when a request is refused', async ({ page, mockApi }) => {
  mockApi.on('POST /leave-requests', (route) =>
    route.fulfill({ status: 422, contentType: 'application/json', body: '{"detail":"insufficient balance"}' }),
  );
  await page.getByLabel('Employee').selectOption({ label: 'Lina Saeed' });
  await page.getByLabel('Type').selectOption('annual');
  await page.getByLabel('From').fill('2026-11-02');
  await page.getByLabel('To').fill('2026-11-27');
  await page.getByRole('button', { name: 'Submit request' }).click();
  await expect(page.getByRole('alert')).toHaveText('insufficient balance');
});

test('terminated employees are not offered', async ({ page }) => {
  const options = page.getByLabel('Employee').locator('option');
  await expect(options).toHaveText(['Choose…', 'Lina Saeed', 'Ravi Menon', 'Omar Haddad']);
});
