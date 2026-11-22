import { expect, test } from '../fixtures/mock-api';

test('the default page is the employee list', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Employees');
  await expect(page).toHaveTitle('Employees · Acme HR');
});

test('an unknown address falls back to the employee list', async ({ page }) => {
  await page.goto('/#/does-not-exist');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Employees');
});

for (const [link, heading] of [
  ['Leave requests', 'Leave requests'],
  ['New request', 'New leave request'],
  ['Payslip estimate', 'Payslip estimate'],
]) {
  test(`the "${link}" link opens its page`, async ({ page }) => {
    await page.goto('/');
    await page.getByRole('navigation').getByRole('link', { name: link }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(heading);
    await expect(page.getByRole('navigation').getByRole('link', { name: link })).toHaveAttribute('aria-current', 'page');
  });
}
