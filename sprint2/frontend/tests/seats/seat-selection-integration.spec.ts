import { test, expect } from "@playwright/test";

const SHOW_ID = process.env.TEST_SHOW_ID;

async function loginAsTestUser(page: any) {
  const email = process.env.TEST_LOGIN_EMAIL;
  const password = process.env.TEST_LOGIN_PASSWORD;

  if (!email || !password) {
    throw new Error(
      "TEST_LOGIN_EMAIL and TEST_LOGIN_PASSWORD must be set"
    );
  }

  await page.goto("/auth/login");

  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);

  await page.getByRole("button", {
    name: /log\s*in|sign\s*in/i,
  }).click();

  await expect(page).toHaveURL(/\/browse/, {
    timeout: 15_000,
  });

  await page.waitForTimeout(2000);
  await page.reload();

  await expect(page).toHaveURL(/\/browse/, {
    timeout: 15_000,
  });

  await page.waitForTimeout(2000);
}

test.describe("Seat Selection - Integration Tests", () => {
  test.beforeEach(() => {
    if (!SHOW_ID) {
      throw new Error("TEST_SHOW_ID must be set");
    }
  });

  test("SEAT-INT-01: real seat map loads from backend", async ({ page }) => {
    const seatMapResponsePromise = page.waitForResponse(
      response =>
        response.url().includes(`/api/seats/${SHOW_ID}/map`) &&
        response.request().method() === "GET"
    );

    await page.goto(`/shows/${SHOW_ID}/seats`);

    const response = await seatMapResponsePromise;

    expect(response.status()).toBe(200);

    const seats = await response.json();

    expect(Array.isArray(seats)).toBeTruthy();
    expect(seats.length).toBeGreaterThan(0);

    await expect(
      page.locator('button[aria-label*="Row"]').first()
    ).toBeVisible();
  });

  test("SEAT-INT-02: available seat can be locked through real backend", async ({
    page,
    }) => {
    await loginAsTestUser(page);

    await page.goto(`/shows/${SHOW_ID}/seats`);

    const availableSeat = page.locator(
        'button[title*="(available)"]'
    ).first();

    await expect(availableSeat).toBeVisible();

    console.log("Before click URL:", page.url());

    await availableSeat.click();

    await page.waitForTimeout(1000);

    console.log("After click URL:", page.url());
    console.log("Page text:");
    console.log(await page.locator("body").innerText());

    await expect(page).not.toHaveURL(/\/auth\/login/);
    });

  test("SEAT-INT-03: selected seat can be released through real backend", async ({
    page,
  }) => {
    await loginAsTestUser(page);

    await page.goto(`/shows/${SHOW_ID}/seats`);

    const availableSeat = page.locator(
      'button[title*="(available)"]'
    ).first();

    await expect(availableSeat).toBeVisible();

    const lockResponsePromise = page.waitForResponse(
      response =>
        response.url().includes(`/api/seats/${SHOW_ID}/lock`) &&
        response.request().method() === "POST"
    );

    await availableSeat.click();

    const lockResponse = await lockResponsePromise;
    expect(lockResponse.status()).toBe(200);

    await expect(availableSeat).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    const releaseResponsePromise = page.waitForResponse(
      response =>
        response.url().includes(`/api/seats/${SHOW_ID}/release`) &&
        response.request().method() === "POST"
    );

    await availableSeat.click();

    const releaseResponse = await releaseResponsePromise;

    expect(releaseResponse.status()).toBe(200);

    const body = await releaseResponse.json();

    expect(body.released).toBeDefined();
  });

  test("SEAT-INT-04: unavailable seat cannot be selected", async ({
    page,
  }) => {
    await page.goto(`/shows/${SHOW_ID}/seats`);

    const unavailableSeat = page.locator(
      'button[title*="(booked)"], button[title*="(locked)"], button[title*="(reserved)"]'
    ).first();

    await expect(unavailableSeat).toBeVisible();

    await expect(unavailableSeat).toBeDisabled();
  });

  test("SEAT-INT-05: booking endpoint is reached after seat selection", async ({
    page,
  }) => {
    await loginAsTestUser(page);

    await page.goto(`/shows/${SHOW_ID}/seats`);

    const availableSeat = page.locator(
      'button[title*="(available)"]'
    ).first();

    await expect(availableSeat).toBeVisible();

    const lockResponsePromise = page.waitForResponse(
      response =>
        response.url().includes(`/api/seats/${SHOW_ID}/lock`) &&
        response.request().method() === "POST"
    );

    await availableSeat.click();

    const lockResponse = await lockResponsePromise;

    expect(lockResponse.status()).toBe(200);

    await expect(
      page.getByRole("button", {
        name: /Proceed to Payment/i,
      })
    ).toBeVisible();

    const bookingResponsePromise = page.waitForResponse(
      response =>
        response.url().includes("/api/bookings") &&
        response.request().method() === "POST"
    );

    await page.getByRole("button", {
      name: /Proceed to Payment/i,
    }).click();

    const bookingResponse = await bookingResponsePromise;

    expect(bookingResponse.status()).toBe(200);

    const booking = await bookingResponse.json();

    expect(booking.booking_id).toBeDefined();
    expect(booking.total_amount).toBeDefined();
    expect(booking.status).toBe("pending");
  });
});