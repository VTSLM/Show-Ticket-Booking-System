import { test, expect, Page } from "@playwright/test";
import { FIREBASE_API_KEY } from "../helpers/fakeLogin";

// #208: email/password accounts verify their email before using TicketFlow.
// Firebase's sign-in endpoints and the TicketFlow API are mocked, so no real accounts are used.

test.skip(!FIREBASE_API_KEY, "Set NEXT_PUBLIC_FIREBASE_API_KEY to the value the frontend was built with");

const EMAIL = "new.user@example.com";
const UID = "uid-new-user";
const jwt = (verified: boolean) =>
  ["e30", Buffer.from(JSON.stringify({ exp: 4102444800, iat: 1700000000, sub: UID, user_id: UID, email: EMAIL, email_verified: verified })).toString("base64url"), "sig"].join(".");

type Firebase = { verified: boolean; emailsSent: number; tokenRefreshes: number; loginChecks: number; registered: number };

async function mockFirebaseAndApi(page: Page, verified: boolean): Promise<Firebase> {
  const fb: Firebase = { verified, emailsSent: 0, tokenRefreshes: 0, loginChecks: 0, registered: 0 };
  const json = (body: unknown) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  const account = () => ({ localId: UID, email: EMAIL, emailVerified: fb.verified, passwordHash: "x", providerUserInfo: [{ providerId: "password", email: EMAIL }] });

  await page.route("**/identitytoolkit.googleapis.com/**", (route) => {
    const url = route.request().url();
    if (url.includes("accounts:signInWithPassword") || url.includes("accounts:signUp")) {
      return route.fulfill(json({ localId: UID, email: EMAIL, idToken: jwt(fb.verified), refreshToken: "refresh", expiresIn: "3600", registered: true }));
    }
    if (url.includes("accounts:lookup")) return route.fulfill(json({ users: [account()] }));
    if (url.includes("accounts:sendOobCode")) {
      expect(route.request().postDataJSON().requestType).toBe("VERIFY_EMAIL");
      fb.emailsSent += 1;
      return route.fulfill(json({ email: EMAIL }));
    }
    return route.fulfill(json({}));
  });
  await page.route("**/securetoken.googleapis.com/**", (route) => {
    fb.tokenRefreshes += 1;
    return route.fulfill(json({ access_token: jwt(fb.verified), id_token: jwt(fb.verified), expires_in: "3600", token_type: "Bearer", refresh_token: "refresh", user_id: UID }));
  });
  await page.route("**/auth/verify-token", (route) => {
    fb.loginChecks += 1;
    return route.fulfill(json({ user: { id: "user-1", name: "New User", email: EMAIL, roles: ["customer"], status: "active" }, session: null }));
  });
  await page.route("**/auth/register", (route) => {
    if (route.request().method() !== "POST") return route.continue(); // the sign-up page itself
    fb.registered += 1;
    return route.fulfill(json({ message: "Registration successful", user_id: "user-1", status: "active" }));
  });
  await page.route("**/auth/me", (route) => route.fulfill(json({ id: "user-1", name: "New User", email: EMAIL, roles: ["customer"], status: "active" })));
  await page.route("**/api/**", (route) => route.fulfill(json([])));
  return fb;
}

async function logIn(page: Page) {
  await page.goto("/auth/login?redirect=%2Fbrowse");
  await page.getByLabel("Email").fill(EMAIL);
  await page.locator("#password").fill("Passw0rd!x");
  await page.locator("form").getByRole("button", { name: /^log in$/i }).click();
}

test("an unverified account is sent a link and taken to the verify page, not into the app", async ({ page }) => {
  const fb = await mockFirebaseAndApi(page, false);
  await logIn(page);

  await expect(page).toHaveURL(/\/auth\/verify-email\?redirect=%2Fbrowse&sent=1/);
  await expect(page.getByTestId("verify-email-address")).toHaveText(EMAIL);
  expect(fb.emailsSent).toBe(1);
  expect(fb.loginChecks).toBe(0); // the backend login was never attempted
  // Just sent, so resending waits
  await expect(page.getByRole("button", { name: /Resend email \(\d+s\)/ })).toBeDisabled();
});

test("once the link is clicked, continuing logs the user in", async ({ page }) => {
  const fb = await mockFirebaseAndApi(page, false);
  await logIn(page);
  await expect(page.getByTestId("verify-email")).toBeVisible();

  // Not verified yet: stays put
  await page.getByRole("button", { name: "I've verified, continue" }).click();
  await expect(page.getByText("Your email isn't verified yet", { exact: false })).toBeVisible();

  fb.verified = true; // the user clicks the link in the email
  await page.getByRole("button", { name: "I've verified, continue" }).click();

  await expect(page).toHaveURL(/\/browse/);
  expect(fb.tokenRefreshes).toBeGreaterThan(0); // fresh token that says "verified"
  await expect.poll(() => fb.loginChecks).toBeGreaterThan(0);
  await expect(page.getByText("New User").first()).toBeVisible();
});

test("an older unverified account can resend the email from the verify page", async ({ page }) => {
  const fb = await mockFirebaseAndApi(page, false);
  await logIn(page);
  await expect(page.getByTestId("verify-email")).toBeVisible();
  // Arrive later without the "just sent" wait
  await page.goto("/auth/verify-email?redirect=%2Fbrowse");
  const resend = page.getByRole("button", { name: "Resend email" });
  await expect(resend).toBeEnabled();
  await resend.click();
  await expect.poll(() => fb.emailsSent).toBe(2);
  await expect(page.getByRole("button", { name: /Resend email \(\d+s\)/ })).toBeDisabled();
});

test("a verified account logs in straight away", async ({ page }) => {
  const fb = await mockFirebaseAndApi(page, true);
  await logIn(page);
  await expect(page).toHaveURL(/\/browse/);
  expect(fb.emailsSent).toBe(0);
  expect(fb.loginChecks).toBeGreaterThan(0);
});

test("signing up sends a verification email and opens the verify page", async ({ page }) => {
  const fb = await mockFirebaseAndApi(page, false);
  await page.goto("/auth/register");
  await page.locator("#name").fill("New User");
  await page.locator("#email").fill(EMAIL);
  await page.locator("#birthdate").fill("2000-01-01");
  await page.locator("#password").fill("Passw0rd!x");
  await page.locator("#confirmPassword").fill("Passw0rd!x");
  await page.locator("form").locator('button[type="submit"]').click();

  await expect(page).toHaveURL(/\/auth\/verify-email\?redirect=%2Fbrowse&sent=1/);
  expect(fb.registered).toBe(1); // the profile is saved before verification
  expect(fb.emailsSent).toBe(1);
  expect(fb.loginChecks).toBe(0);
});
