import { test, expect } from '@playwright/test';

const loginUrl =
  process.env.LOGIN_URL ?? 'http://localhost:3000/auth/login';

const firebaseOnlyEmail = process.env.TEST_FIREBASE_ONLY_EMAIL;
const firebaseOnlyPassword = process.env.TEST_FIREBASE_ONLY_PASSWORD;

const inactiveManagerEmail =
  process.env.TEST_INACTIVE_MANAGER_EMAIL;
const inactiveManagerPassword =
  process.env.TEST_INACTIVE_MANAGER_PASSWORD;

const blockedEmail = process.env.TEST_BLOCKED_EMAIL;
const blockedPassword = process.env.TEST_BLOCKED_PASSWORD;

async function attemptLogin(
  page: any,
  email: string | undefined,
  password: string | undefined
) {
  await page.goto(loginUrl);

  await page.getByLabel('Email').fill(email!);
  await page.getByLabel('Password').fill(password!);

  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(
    page.getByRole('button', { name: /Log in|Logging in/i })
  ).toBeVisible({
    timeout: 10_000,
  });
}

test.describe('Firebase authentication integration', () => {
  test('FIREBASE-01: Firebase user not registered in Supabase is rejected', async ({
    page,
  }) => {
    test.skip(
      !firebaseOnlyEmail || !firebaseOnlyPassword,
      'Firebase-only test credentials are not configured'
    );

    await attemptLogin(
      page,
      firebaseOnlyEmail,
      firebaseOnlyPassword
    );

    await expect(page).not.toHaveURL(/\/browse/);

    await expect(
      page.getByText(/User not found\. Please register/i)
    ).toBeVisible({
      timeout: 10_000,
    });
  });

  test('FIREBASE-02: inactive manager is rejected after Firebase authentication', async ({
    page,
  }) => {
    test.skip(
      !inactiveManagerEmail || !inactiveManagerPassword,
      'Inactive manager test credentials are not configured'
    );

    await attemptLogin(
      page,
      inactiveManagerEmail,
      inactiveManagerPassword
    );

    await expect(page).not.toHaveURL(/\/browse/);

    await expect(
        page.getByText(/Account pending admin approval/i)
        ).toBeVisible({
        timeout: 10_000,
        });
  });

  test('FIREBASE-03: blocked user is rejected after Firebase authentication', async ({
    page,
  }) => {
    test.skip(
      !blockedEmail || !blockedPassword,
      'Blocked-user test credentials are not configured'
    );

    await attemptLogin(
      page,
      blockedEmail,
      blockedPassword
    );

    await expect(page).not.toHaveURL(/\/browse/);

    await expect(
        page.getByText(/Account blocked/i)
        ).toBeVisible({
        timeout: 10_000,
        });
  });
});