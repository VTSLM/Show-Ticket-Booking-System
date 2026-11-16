import { test, expect } from "@playwright/test";

const SHOW_ID = "show-edge-123";

const availableSeat = {
  show_seat_id: "seat-A1",
  row_label: "A",
  seat_number: 1,
  seat_type: "regular",
  status: "available",
  price: 200,
};

async function mockShow(page: any) {
  await page.route(`**/api/browse/shows/${SHOW_ID}`, async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: SHOW_ID,
        title: "Test Movie",
        event_type: "movie",
        language: "English",
        venue_name: "Test Cinema",
        city: "Ahmedabad",
        start_time: "2030-01-01T19:00:00",
        base_price: 200,
      }),
    });
  });

  await page.route(`**/api/seats/${SHOW_ID}/ws`, async (route: any) => {
    await route.abort();
  });
}

test.describe("Seat Selection - Edge Cases", () => {
  test("SEAT-EDGE-01: empty seat map displays appropriate message", async ({
    page,
  }) => {
    await mockShow(page);

    await page.route(`**/api/seats/${SHOW_ID}/map`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto(`/shows/${SHOW_ID}/seats`);

    await expect(
      page.getByText(
        "No seats are currently available for this show.",
        { exact: true }
      )
    ).toBeVisible();
  });

  test("SEAT-EDGE-02: seat map API failure is handled", async ({ page }) => {
  // Mock the show details API
  await page.route(`**/api/browse/shows/${SHOW_ID}`, async route => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: SHOW_ID,
        title: "Test Movie",
        venue_name: "Test Cinema",
        start_time: "2030-01-01T19:00:00",
      }),
    });
  });

  // Mock seat map API failure
  await page.route(`**/api/seats/${SHOW_ID}/map`, async route => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Internal server error",
      }),
    });
  });

  await page.goto(`/shows/${SHOW_ID}/seats`);

  // The application should fall back to the empty-seat state
  await expect(
    page.getByText("No seats are currently available for this show.")
  ).toBeVisible();
});

  test("SEAT-EDGE-03: locking a seat is handled", async ({ page }) => {
    await mockShow(page);

    await page.route(`**/api/seats/${SHOW_ID}/map`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([availableSeat]),
      });
    });

    await page.route(`**/api/seats/${SHOW_ID}/lock`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          locked: ["seat-A1"],
          locked_until: "2030-01-01T19:10:00",
        }),
      });
    });

    await page.goto(`/shows/${SHOW_ID}/seats`);

    const seat = page.getByRole("button", {
      name: /Row A, seat 1/i,
    });

    await seat.click();

    await expect(seat).toHaveAttribute("aria-pressed", "true");
  });

  test("SEAT-EDGE-04: lock failure shows an error", async ({ page }) => {
    await mockShow(page);

    await page.route(`**/api/seats/${SHOW_ID}/map`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([availableSeat]),
      });
    });

    await page.route(`**/api/seats/${SHOW_ID}/lock`, async (route: any) => {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Seats unavailable: ['seat-A1']",
        }),
      });
    });

    await page.goto(`/shows/${SHOW_ID}/seats`);

    await page.getByRole("button", {
      name: /Row A, seat 1/i,
    }).click();

    await expect(
      page.getByText(/Seats unavailable/i)
    ).toBeVisible();
  });

  test("SEAT-EDGE-05: booking failure shows an error", async ({ page }) => {
    await mockShow(page);

    await page.route(`**/api/seats/${SHOW_ID}/map`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([availableSeat]),
      });
    });

    await page.route(`**/api/seats/${SHOW_ID}/lock`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          locked: ["seat-A1"],
          locked_until: "2030-01-01T19:10:00",
        }),
      });
    });

    await page.route(`**/api/bookings`, async (route: any) => {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Seat is no longer available",
        }),
      });
    });

    await page.goto(`/shows/${SHOW_ID}/seats`);

    await page.getByRole("button", {
      name: /Row A, seat 1/i,
    }).click();

    await page.getByRole("button", {
      name: /Proceed to Payment/i,
    }).click();

    await expect(
      page.getByText(/Seat is no longer available/i)
    ).toBeVisible();
  });

  test("SEAT-EDGE-06: user with no selected seats cannot proceed", async ({
    page,
  }) => {
    await mockShow(page);

    await page.route(`**/api/seats/${SHOW_ID}/map`, async (route: any) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([availableSeat]),
      });
    });

    await page.goto(`/shows/${SHOW_ID}/seats`);

    await expect(
      page.getByRole("button", {
        name: /Proceed to Payment/i,
      })
    ).not.toBeVisible();
  });
});