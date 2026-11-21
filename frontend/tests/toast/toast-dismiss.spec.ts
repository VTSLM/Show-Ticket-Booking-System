import { test, expect } from '@playwright/test';

const baseUrl = process.env.BASE_URL ?? 'http://localhost:3000';

test.describe('Notifications can be dismissed', () => {
  test('TOAST-01: the close button removes an error notification', async ({ page }) => {
    await page.goto(`${baseUrl}/auth/login`);

    // "Forgot password?" with no email shows an error toast without any network call.
    await page.getByRole('button', { name: 'Forgot password?' }).click();
    const message = page.getByText('Enter your email address first.');
    await expect(message).toBeVisible();

    await page.getByRole('button', { name: 'Dismiss notification' }).click();
    await expect(message).toBeHidden();
  });

  test('TOAST-02: the close button can be reached with the keyboard', async ({ page }) => {
    await page.goto(`${baseUrl}/auth/login`);

    await page.getByRole('button', { name: 'Forgot password?' }).click();
    const message = page.getByText('Enter your email address first.');
    await expect(message).toBeVisible();

    const dismiss = page.getByRole('button', { name: 'Dismiss notification' });
    await dismiss.focus();
    await page.keyboard.press('Enter');
    await expect(message).toBeHidden();
  });
});
