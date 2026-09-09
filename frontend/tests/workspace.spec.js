import { test, expect } from '@playwright/test';

async function signIn(page, role = 'admin') {
  await page.goto('/signin');
  await page.getByLabel('Email or username').fill(role);
  await page.getByLabel('Password', { exact: true }).fill('BrowserTest!234');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Festival overview.' })).toBeVisible();
}
test('fresh visitor and malformed storage reach sign in without crashing', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.addInitScript(() => sessionStorage.setItem('gy_session', '{invalid'));
  await page.goto('/home');
  await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
  expect(errors).toEqual([]);
});
test('dashboard, account screen and logout have no runtime errors', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await signIn(page);
  await expect(page.getByText('₹35,000.00').first()).toBeVisible();
  await page.getByRole('link', { name: 'Access management', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Access management.' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'admin@example.test', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
  expect(errors).toEqual([]);
});
test('expense submission, independent review, audit snapshot and export', async ({ page }) => {
  await signIn(page);
  await page.getByRole('link', { name: 'Expense ledger', exact: true }).click();
  await page.getByRole('button', { name: 'Add expense', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('What was the expense for?').fill('Browser tested flower expense');
  await dialog.getByLabel('Amount (₹)').fill('235.50');
  await dialog.getByLabel('Vendor / paid to').fill('Flower vendor');
  await dialog.getByLabel('Receipt / voucher number').fill('BROWSER-BILL-01');
  await dialog.getByRole('button', { name: 'Submit for review' }).click();
  await expect(
    page.getByRole('cell', { name: 'Browser tested flower expense', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('row')
    .filter({ hasText: 'Browser tested flower expense' })
    .getByRole('button', { name: 'View / review' })
    .click();
  await expect(
    page.getByText('Another administrator or treasurer must review your entry.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await signIn(page, 'treasurer');
  await page.getByRole('link', { name: 'Expense ledger', exact: true }).click();
  await page
    .getByRole('row')
    .filter({ hasText: 'Browser tested flower expense' })
    .getByRole('button', { name: 'View / review' })
    .click();
  await page.getByLabel('Review reason').fill('Receipt matched by browser regression test');
  await page.getByRole('button', { name: 'Save review decision' }).click();
  await expect(
    page
      .getByRole('row')
      .filter({ hasText: 'Browser tested flower expense' })
      .getByText('approved', { exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'CSV', exact: true }).click();
  expect((await download).suggestedFilename()).toContain('ganesh-expenses');
  await page.getByRole('link', { name: 'Audit trail', exact: true }).click();
  await expect(
    page
      .getByRole('cell', { name: 'Receipt matched by browser regression test', exact: false })
      .first(),
  ).toBeVisible();
});
test('failed collection submission stays open and never claims success', async ({ page }) => {
  await signIn(page);
  await page.getByRole('link', { name: 'Collections', exact: true }).click();
  await page.getByRole('button', { name: 'Add collection', exact: true }).click();
  await page.getByLabel('Contributor name').fill('Network failure test');
  await page.getByLabel('Amount (₹)').fill('100');
  await page.route('**/api/payments/', (route) =>
    route.request().method() === 'POST' ? route.abort() : route.continue(),
  );
  await page.getByRole('button', { name: 'Submit for review' }).click();
  await expect(page.getByRole('alert')).toContainText('Cannot reach the server');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('Record saved successfully.')).toHaveCount(0);
});
test('expired access token refreshes and page reload restores session', async ({ page }) => {
  await signIn(page);
  await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('gy_session'));
    session.access = 'expired-token';
    sessionStorage.setItem('gy_session', JSON.stringify(session));
  });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Festival overview.' })).toBeVisible();
  await expect(page.getByText('₹35,000.00').first()).toBeVisible();
});
test('mobile navigation works and all financial content fits the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await expect(page.getByText('₹35,000.00').first()).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy();
  await page.screenshot({ path: 'test-results/mobile-overview.png', fullPage: true });
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Collections', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Collections.' })).toBeVisible();
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
});
test('member cannot navigate to committee-only records', async ({ page }) => {
  await signIn(page, 'member');
  await page.goto('/users');
  await expect(page.getByRole('heading', { name: 'Festival overview.' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Access management' })).toHaveCount(0);
});
test('desktop review screenshot and year filter show genuine empty states', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1050 });
  await signIn(page);
  await expect(page.getByText('₹35,000.00').first()).toBeVisible();
  await page.screenshot({ path: 'test-results/desktop-overview.png', fullPage: true });
  await page
    .getByLabel('Festival year', { exact: true })
    .selectOption(String(new Date().getFullYear() - 1));
  await expect(page.getByText('No approved spending', { exact: true })).toBeVisible();
  await expect(page.getByText('Your ledger starts here')).toBeVisible();
});
