import { Page, expect } from "@playwright/test";

export interface MockProfile {
  id: string;
  name: string;
  email: string;
  roles: string[];
  status: string;
}

function toBase64Url(obj: object): string {
  return Buffer.from(JSON.stringify(obj))
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

export function buildFakeFirebaseJwt(uid: string, email: string): string {
  const nowSec = Math.floor(Date.now() / 1000);
  const header = toBase64Url({ alg: "RS256", typ: "JWT" });
  const payload = toBase64Url({
    iss: "https://securetoken.google.com/ticketflow-test",
    aud: "ticketflow-test",
    auth_time: nowSec,
    user_id: uid,
    sub: uid,
    iat: nowSec,
    exp: nowSec + 3600,
    email,
    email_verified: true,
    firebase: { identities: { email: [email] }, sign_in_provider: "password" },
  });
  return `${header}.${payload}.fakesignature`;
}

/**
 * Intercepts Firebase Auth REST calls and backend auth endpoints so Playwright UI
 * and edge tests can authenticate deterministically without external Firebase access.
 */
export async function loginWithMockFirebase(page: Page, profile: MockProfile) {
  const uid = `uid-${profile.id}`;
  const fakeToken = buildFakeFirebaseJwt(uid, profile.email);

  await page.route("**/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        kind: "identitytoolkit#VerifyPasswordResponse",
        localId: uid,
        email: profile.email,
        displayName: profile.name,
        idToken: fakeToken,
        registered: true,
        refreshToken: "fake-refresh-token",
        expiresIn: "3600",
      }),
    });
  });

  await page.route("**/identitytoolkit.googleapis.com/v1/accounts:lookup*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        kind: "identitytoolkit#GetAccountInfoResponse",
        users: [
          {
            localId: uid,
            email: profile.email,
            displayName: profile.name,
            emailVerified: true,
            passwordHash: "FAKE",
            lastLoginAt: String(Date.now()),
            createdAt: String(Date.now() - 10000),
          },
        ],
      }),
    });
  });

  await page.route("**/securetoken.googleapis.com/v1/token*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: fakeToken,
        expires_in: "3600",
        token_type: "Bearer",
        refresh_token: "fake-refresh-token",
        id_token: fakeToken,
        user_id: uid,
        project_id: "ticketflow-test",
      }),
    });
  });

  await page.route("**/auth/verify-token", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user: profile, firebase_uid: uid }),
    });
  });

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...profile, firebase_uid: uid }),
    });
  });

  await page.route("**/api/browse/cities", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/browse/shows*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.goto("/auth/login");
  await page.getByLabel("Email").fill(profile.email);
  await page.getByLabel("Password").fill("TestPassword@123");
  await page.getByRole("button", { name: "Log in" }).click();

  await expect(page).toHaveURL(/\/browse$/, { timeout: 15_000 });
  await expect(page.getByText(profile.name)).toBeVisible({ timeout: 10_000 });
}

