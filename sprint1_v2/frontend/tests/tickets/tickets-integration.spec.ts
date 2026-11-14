import { test, expect } from "@playwright/test";

const CUSTOMER_EMAIL = process.env.TEST_LOGIN_EMAIL;
const CUSTOMER_PASSWORD = process.env.TEST_LOGIN_PASSWORD;
const CONFIRMED_BOOKING_ID = process.env.TEST_CONFIRMED_BOOKING_ID;

test.describe("Ticket Generation - Integration Tests", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!CUSTOMER_EMAIL || !CUSTOMER_PASSWORD, "TEST_LOGIN_EMAIL and TEST_LOGIN_PASSWORD must be set");

    await page.goto("/auth/login");
    await page.getByLabel("Email").fill(CUSTOMER_EMAIL!);
    await page.getByLabel("Password").fill(CUSTOMER_PASSWORD!);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/browse$/, { timeout: 15_000 });
  });

  test("TICKET-INT-01: My Bookings fetches real bookings from backend", async ({ page }) => {
    const bookingsResPromise = page.waitForResponse(
      (r) => r.url().endsWith("/api/bookings") && r.request().method() === "GET"
    );

    await page.getByRole("link", { name: "My Bookings" }).click();
    const res = await bookingsResPromise;
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
  });

  test("TICKET-INT-02: Download Ticket PDF streams real application/pdf from backend", async ({ page }) => {
    test.skip(!CONFIRMED_BOOKING_ID, "TEST_CONFIRMED_BOOKING_ID must be set");

    await page.goto(`/bookings/${CONFIRMED_BOOKING_ID}`);
    const pdfResPromise = page.waitForResponse(
      (r) => r.url().includes(`/api/tickets/bookings/${CONFIRMED_BOOKING_ID}/pdf`) && r.request().method() === "GET"
    );
    await page.getByRole("button", { name: "Download Ticket PDF" }).click();
    const pdfRes = await pdfResPromise;

    expect(pdfRes.status()).toBe(200);
    expect(pdfRes.headers()["content-type"]).toContain("application/pdf");
  });
});

