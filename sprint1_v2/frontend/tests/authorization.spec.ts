import { test, expect, Page } from '@playwright/test';

const loginUrl = '/auth/login';

const customerEmail = process.env.TEST_CUSTOMER_EMAIL;
const customerPassword = process.env.TEST_CUSTOMER_PASSWORD;

const managerEmail = process.env.TEST_MANAGER_EMAIL;
const managerPassword = process.env.TEST_MANAGER_PASSWORD;

const adminEmail = process.env.TEST_ADMIN_EMAIL;
const adminPassword = process.env.TEST_ADMIN_PASSWORD;

async function login(page: Page, email: string | undefined, password: string | undefined) {
  test.skip(!email || !password, 'Required role test credentials are not configured');

  await page.goto(loginUrl);
  await page.getByLabel('Email').fill(email!);
  await page.getByLabel('Password').fill(password!);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL(/\/browse(?:\/)?$/, { timeout: 15_000 });
}

test.describe('Login - authentication and authorization', () => {
  test('LOGIN-AUTH-01: unauthenticated user is redirected from bookings to login', async ({ page }) => {
    await page.goto('/bookings');
    await expect(page).toHaveURL(/\/auth\/login(?:\/)?$/, { timeout: 10_000 });
  });

  test('LOGIN-AUTH-02: active customer can access bookings', async ({ page }) => {
    await login(page, customerEmail, customerPassword);

    await page.goto('/bookings');
    await expect(page).toHaveURL(/\/bookings(?:\/)?$/, { timeout: 10_000 });
  });

  test('LOGIN-AUTH-03: customer cannot access manager page', async ({ page }) => {
    await login(page, customerEmail, customerPassword);

    await page.goto('/manager');
    await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
  });

  test('LOGIN-AUTH-04: customer cannot access admin page', async ({ page }) => {
    await login(page, customerEmail, customerPassword);

    await page.goto('/admin');
    await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
  });

  test('LOGIN-AUTH-05: active manager can access manager page', async ({ page }) => {
    await login(page, managerEmail, managerPassword);

    await page.goto('/manager');
    await expect(page).toHaveURL(/\/manager(?:\/)?$/, { timeout: 10_000 });
  });

  test('LOGIN-AUTH-06: manager cannot access admin page', async ({ page }) => {
    await login(page, managerEmail, managerPassword);

    await page.goto('/admin');
    await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
  });

  test('LOGIN-AUTH-07: active admin can access admin page', async ({ page }) => {
    await login(page, adminEmail, adminPassword);

    await page.goto('/admin');
    await expect(page).toHaveURL(/\/admin(?:\/)?$/, { timeout: 10_000 });
  });
});
