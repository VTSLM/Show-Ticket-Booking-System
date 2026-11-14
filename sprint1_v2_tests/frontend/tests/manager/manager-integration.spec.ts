import { test, expect } from "@playwright/test";

const MANAGER_EMAIL = process.env.TEST_MANAGER_EMAIL;
const MANAGER_PASSWORD = process.env.TEST_MANAGER_PASSWORD;

test.describe("Manager Listing - Integration Tests", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!MANAGER_EMAIL || !MANAGER_PASSWORD, "TEST_MANAGER_EMAIL and TEST_MANAGER_PASSWORD must be set");

    await page.goto("/auth/login");
    await page.getByLabel("Email").fill(MANAGER_EMAIL!);
    await page.getByLabel("Password").fill(MANAGER_PASSWORD!);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/browse$/, { timeout: 15_000 });
  });

  test("MGR-INT-01: manager dashboard loads real venues, events, and shows from backend", async ({ page }) => {
    const showsRes = page.waitForResponse((r) => r.url().includes("/api/manager/shows") && r.request().method() === "GET");
    const eventsRes = page.waitForResponse((r) => r.url().includes("/api/manager/events") && r.request().method() === "GET");
    const venuesRes = page.waitForResponse((r) => r.url().includes("/api/manager/venues") && r.request().method() === "GET");

    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await expect(page).toHaveURL(/\/manager$/);

    expect((await showsRes).status()).toBe(200);
    expect((await eventsRes).status()).toBe(200);
    expect((await venuesRes).status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Manager Dashboard" })).toBeVisible();
  });

  test("MGR-INT-02: creating event persists in real backend and appears in Events list", async ({ page }) => {
    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await page.getByRole("button", { name: "Events" }).click();

    const uniqueTitle = `E2E Test Movie ${Date.now()}`;
    await page.locator("label", { hasText: /^Title$/ }).locator("..").locator("input").fill(uniqueTitle);
    await page.locator("label", { hasText: /^Duration \(min\)$/ }).locator("..").locator("input").fill("120");

    const createResPromise = page.waitForResponse(
      (r) => r.url().includes("/api/manager/events") && r.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Create Event" }).click();
    const createRes = await createResPromise;
    expect(createRes.status()).toBe(200);

    await expect(page.getByText(uniqueTitle)).toBeVisible();
  });
});

