import { test, expect } from '@playwright/test';

const loginUrl = process.env.LOGIN_URL ?? 'http://localhost:3000/auth/login';
const testEmail = process.env.TEST_LOGIN_EMAIL;
const testPassword = process.env.TEST_LOGIN_PASSWORD;

test.describe('Login page - validation and UI', () => {
  test('LOGIN-UI-01: login page renders the required controls', async ({ page }) => {
    await page.goto(loginUrl);

    await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign up' })).toHaveAttribute('href', '/auth/register');
  });

  test('LOGIN-UI-02: empty required fields are rejected by browser validation', async ({ page }) => {
    await page.goto(loginUrl);

    const email = page.getByLabel('Email');
    const password = page.getByLabel('Password');

    await expect(email).toHaveAttribute('required', '');
    await expect(password).toHaveAttribute('required', '');

    await page.getByRole('button', { name: 'Log in' }).click();

    // The required inputs should still be present because the browser blocks submission.
    await expect(email).toBeVisible();
    await expect(password).toBeVisible();
  });

  test('LOGIN-UI-03: invalid email format is rejected by the email input', async ({ page }) => {
    await page.goto(loginUrl);

    const email = page.getByLabel('Email');
    await email.fill('not-an-email');
    await page.getByLabel('Password').fill('SomePassword123');

    expect(await email.evaluate((el: HTMLInputElement) => el.validity.typeMismatch)).toBe(true);
  });

  test('LOGIN-UI-04: password input masks the password', async ({ page }) => {
    await page.goto(loginUrl);

    await expect(page.getByLabel('Password')).toHaveAttribute('type', 'password');
  });

  test('LOGIN-UI-05: forgot-password control is currently non-functional', async ({ page }) => {
    await page.goto(loginUrl);

    const forgot = page.getByRole('button', { name: 'Forgot password?' });
    await expect(forgot).toBeVisible();
    await expect(forgot).toHaveAttribute('type', 'button');

    // There is currently no click handler/navigation attached in the supplied page.tsx.
    // This test intentionally documents the existing behavior rather than expecting
    // a password-reset flow that is not implemented.
  });
});

test.describe('Login page - real Firebase account', () => {
  test.skip(!testEmail || !testPassword, 'Set TEST_LOGIN_EMAIL and TEST_LOGIN_PASSWORD to run real-login tests.');

  test('LOGIN-01: valid credentials redirect to /browse', async ({ page }) => {
    await page.goto(loginUrl);
    await page.getByLabel('Email').fill(testEmail!);
    await page.getByLabel('Password').fill(testPassword!);
    await page.getByRole('button', { name: 'Log in' }).click();

    await expect(page).toHaveURL(/\/browse(?:$|\/)/, { timeout: 15000 });
  });

  test('LOGIN-02: wrong password does not redirect to /browse', async ({ page }) => {
    await page.goto(loginUrl);
    await page.getByLabel('Email').fill(testEmail!);
    await page.getByLabel('Password').fill(`${testPassword!}-wrong`);
    await page.getByRole('button', { name: 'Log in' }).click();

    await page.waitForTimeout(1500);
    await expect(page).toHaveURL(/\/auth\/login(?:$|\/)/);
  });
});
