import { test, expect } from '@playwright/test';

const loginUrl =
  process.env.LOGIN_URL ?? 'http://localhost:3000/auth/login';

const testEmail = process.env.TEST_LOGIN_EMAIL;
const testPassword = process.env.TEST_LOGIN_PASSWORD;

test.describe('Login - edge cases and session behavior', () => {
  test.beforeEach(() => {
    if (!testEmail || !testPassword) {
      throw new Error(
        'TEST_LOGIN_EMAIL and TEST_LOGIN_PASSWORD must be set'
      );
    }
  });

  async function login(page: any) {
    await page.goto(loginUrl);

    await page.getByLabel('Email').fill(testEmail!);
    await page.getByLabel('Password').fill(testPassword!);

    await page.getByRole('button', { name: 'Log in' }).click();

    await page.waitForURL('**/browse', {
      timeout: 15_000,
    });
  }

  test('LOGIN-EDGE-01: authenticated session survives page refresh', async ({
    page,
  }) => {
    await login(page);

    expect(page.url()).toContain('/browse');

    await page.reload();

    await expect(page).toHaveURL(/\/browse/);
  });

  test('LOGIN-EDGE-02: failed token verification does not redirect to browse', async ({
    page,
  }) => {
    await page.route('**/auth/verify-token', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Authentication service unavailable',
        }),
      });
    });

    await page.goto(loginUrl);

    await page.getByLabel('Email').fill(testEmail!);
    await page.getByLabel('Password').fill(testPassword!);

    await page.getByRole('button', { name: 'Log in' }).click();

    await expect(page).not.toHaveURL(/\/browse/, {
      timeout: 10_000,
    });

    await expect(
      page.getByRole('button', { name: 'Log in' })
    ).toBeVisible();
  });

  test('LOGIN-EDGE-03: login button returns to normal after authentication failure', async ({
    page,
  }) => {
    await page.route('**/auth/verify-token', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Authentication service unavailable',
        }),
      });
    });

    await page.goto(loginUrl);

    const loginButton = page.getByRole('button', { name: 'Log in' });

    await page.getByLabel('Email').fill(testEmail!);
    await page.getByLabel('Password').fill(testPassword!);

    await loginButton.click();

    /*
     * While the request is being processed, the application should
     * enter its loading state.
     */
    await expect(
      page.getByRole('button', { name: /Logging in/i })
    ).toBeVisible();

    /*
     * After the authentication request fails, the button should
     * return to its normal state instead of remaining stuck.
     */
    await expect(
      page.getByRole('button', { name: 'Log in' })
    ).toBeVisible({
      timeout: 10_000,
    });

    await expect(page).not.toHaveURL(/\/browse/);
  });

  test('LOGIN-EDGE-04: login button prevents repeated submission while loading', async ({
    page,
  }) => {
    await page.goto(loginUrl);

    const loginButton = page.getByRole('button', { name: 'Log in' });

    await page.getByLabel('Email').fill(testEmail!);
    await page.getByLabel('Password').fill(testPassword!);

    await loginButton.click();

    /*
     * The Login page uses a loading state while authentication
     * is in progress. The button should therefore become disabled
     * rather than allowing repeated submissions.
     */
    await expect(
      page.getByRole('button', { name: /Logging in/i })
    ).toBeDisabled({
      timeout: 5_000,
    });
  });
});