import { test, expect } from "@playwright/test";

const CUSTOMER_EMAIL = process.env.TEST_LOGIN_EMAIL;
const CUSTOMER_PASSWORD = process.env.TEST_LOGIN_PASSWORD;
const PENDING_BOOKING_ID = process.env.TEST_PENDING_BOOKING_ID;

test.describe("Payment Gateway - Integration Tests", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(
      !CUSTOMER_EMAIL || !CUSTOMER_PASSWORD || !PENDING_BOOKING_ID,
      "TEST_LOGIN_EMAIL, TEST_LOGIN_PASSWORD, and TEST_PENDING_BOOKING_ID must be set"
    );

    await page.goto("/auth/login");
    await page.getByLabel("Email").fill(CUSTOMER_EMAIL!);
    await page.getByLabel("Password").fill(CUSTOMER_PASSWORD!);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/browse$/, { timeout: 15_000 });
  });

  test("PAY-INT-01: loads real pending booking details from backend", async ({ page }) => {
    const bookingResPromise = page.waitForResponse(
      (r) => r.url().includes(`/api/bookings/${PENDING_BOOKING_ID}`) && r.request().method() === "GET"
    );

    await page.goto(`/payment?booking_id=${PENDING_BOOKING_ID}`);
    const res = await bookingResPromise;
    expect(res.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Complete Payment" })).toBeVisible();
  });

  test("PAY-INT-02: clicking Pay invokes real POST /api/payments/orders", async ({ page }) => {
    await page.goto(`/payment?booking_id=${PENDING_BOOKING_ID}`);

    const orderResPromise = page.waitForResponse(
      (r) => r.url().includes("/api/payments/orders") && r.request().method() === "POST"
    );
    await page.getByRole("button", { name: /Pay ₹/i }).click();
    const orderRes = await orderResPromise;

    expect(orderRes.status()).toBe(200);
    const data = await orderRes.json();
    expect(data).toHaveProperty("razorpay_order_id");
    expect(data.amount).toBeGreaterThan(0);
  });
});

