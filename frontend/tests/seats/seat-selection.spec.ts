import { test, expect } from "@playwright/test";

const SHOW_ID = "show-123";

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

  // Wait for Firebase/AuthContext initialization.
  await page.waitForTimeout(3000);

  // Reload so the persisted Firebase session is picked up.
  await page.reload();

  await expect(page).toHaveURL(/\/browse/, {
    timeout: 15_000,
  });

  // Give AuthContext time to restore Firebase user + profile.
  await page.waitForTimeout(3000);
}

async function mockSeatAPIs(page: any) {
  // Mock show details
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

  // Mock seat map
  await page.route(`**/api/seats/${SHOW_ID}/map`, async (route: any) => {
    console.log("SEAT MAP API INTERCEPTED");

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          show_seat_id: "seat-A1",
          row_label: "A",
          seat_number: 1,
          seat_type: "regular",
          status: "available",
          price: 200,
        },
        {
          show_seat_id: "seat-A2",
          row_label: "A",
          seat_number: 2,
          seat_type: "regular",
          status: "available",
          price: 200,
        },
        {
          show_seat_id: "seat-A3",
          row_label: "A",
          seat_number: 3,
          seat_type: "regular",
          status: "available",
          price: 200,
        },
        {
          show_seat_id: "seat-B1",
          row_label: "B",
          seat_number: 1,
          seat_type: "regular",
          status: "available",
          price: 200,
        },
        {
          show_seat_id: "seat-B2",
          row_label: "B",
          seat_number: 2,
          seat_type: "regular",
          status: "locked",
          price: 200,
          locked_by: "another-user",
        },
        {
          show_seat_id: "seat-B3",
          row_label: "B",
          seat_number: 3,
          seat_type: "premium",
          status: "available",
          price: 300,
        },
        {
          show_seat_id: "seat-C1",
          row_label: "C",
          seat_number: 1,
          seat_type: "regular",
          status: "booked",
          price: 200,
        },
        {
          show_seat_id: "seat-C2",
          row_label: "C",
          seat_number: 2,
          seat_type: "regular",
          status: "reserved",
          price: 200,
        },
      ]),
    });
  });

  // Mock locking
  await page.route(`**/api/seats/${SHOW_ID}/lock`, async (route: any) => {
    console.log("LOCK API INTERCEPTED");

    const request = route.request();

    let body: any = {};

    try {
      body = request.postDataJSON() ?? {};
    } catch {
      body = {};
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        locked: body.seat_ids ?? ["seat-A1"],
        locked_until: "2030-01-01T19:10:00Z",
      }),
    });
  });

  // Mock releasing
  await page.route(`**/api/seats/${SHOW_ID}/release`, async (route: any) => {
    console.log("RELEASE API INTERCEPTED");

    const request = route.request();

    let body: any = {};

    try {
      body = request.postDataJSON() ?? {};
    } catch {
      body = {};
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        released: body.seat_ids ?? [],
      }),
    });
  });
}

async function openSeatPage(page: any) {
    page.on("response", async (response: any) => {
    if (response.url().includes("verify-token")) {
        console.log(
        "VERIFY TOKEN:",
        response.status(),
        response.url()
        );
    }
    });
  await mockSeatAPIs(page);
  await loginAsTestUser(page);

  await page.goto(`/shows/${SHOW_ID}/seats`);

  // Wait for the actual seat map to appear.
  await expect(
    page.getByRole("button", {
      name: /Row A, seat 1/i,
    })
  ).toBeVisible({
    timeout: 15_000,
  });
}

test.describe("Seat Selection - Basic UI", () => {
  test.beforeEach(async ({ page }) => {
    await openSeatPage(page);
  });

  test("SEAT-UI-01: seat selection page loads", async ({ page }) => {
    await expect(
      page.getByText(/Select Your Seats/i)
    ).toBeVisible();

    await expect(
      page.getByText(/Available/i)
    ).toBeVisible();
  });

  test("SEAT-UI-02: seat rows are displayed", async ({ page }) => {
    await expect(
      page.getByRole("button", {
        name: /Row A, seat 1/i,
      })
    ).toBeVisible();

    await expect(
      page.getByRole("button", {
        name: /Row B, seat 1/i,
      })
    ).toBeVisible();
  });

  test("SEAT-UI-03: available seat can be selected", async ({ page }) => {
    const seat = page.getByRole("button", {
        name: /Row A, seat 1/i,
    });

    console.log("Before click URL:", page.url());

    await seat.click();

    await page.waitForTimeout(1000);

    console.log("After click URL:", page.url());
    console.log("After click body:");
    console.log(await page.locator("body").innerText());

    console.log(
        "A1 count after click:",
        await page.getByRole("button", {
        name: /Row A, seat 1/i,
        }).count()
    );
    });

  test("SEAT-UI-04: multiple seats can be selected", async ({ page }) => {
    const seat1 = page.getByRole("button", {
      name: /Row A, seat 1/i,
    });

    const seat2 = page.getByRole("button", {
      name: /Row A, seat 2/i,
    });

    await seat1.click();
    await seat2.click();

    await expect(seat1).toHaveAttribute("aria-pressed", "true");
    await expect(seat2).toHaveAttribute("aria-pressed", "true");

    await expect(
      page.getByText(/2 seats selected/i)
    ).toBeVisible();
  });

  test("SEAT-UI-05: total price is calculated correctly", async ({
    page,
  }) => {
    const seat1 = page.getByRole("button", {
      name: /Row A, seat 1/i,
    });

    const seat2 = page.getByRole("button", {
      name: /Row A, seat 2/i,
    });

    await seat1.click();
    await seat2.click();

    await expect(
      page.getByText(/Total:\s*₹400/i)
    ).toBeVisible();
  });

  test("SEAT-UI-06: premium seat uses its own price", async ({
    page,
  }) => {
    const premiumSeat = page.getByRole("button", {
      name: /Row B, seat 3/i,
    });

    await premiumSeat.click();

    await expect(premiumSeat).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    await expect(
      page.getByText(/Total:\s*₹300/i)
    ).toBeVisible();
  });

  test("SEAT-UI-07: booked seat cannot be selected", async ({
    page,
  }) => {
    const bookedSeat = page.getByRole("button", {
      name: /Row C, seat 1/i,
    });

    await expect(bookedSeat).toBeDisabled();

    await expect(bookedSeat).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  test("SEAT-UI-08: locked seat cannot be selected", async ({
    page,
  }) => {
    const lockedSeat = page.getByRole("button", {
      name: /Row B, seat 2/i,
    });

    await expect(lockedSeat).toBeDisabled();

    await expect(lockedSeat).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  test("SEAT-UI-09: reserved seat cannot be selected", async ({
    page,
  }) => {
    const reservedSeat = page.getByRole("button", {
      name: /Row C, seat 2/i,
    });

    await expect(reservedSeat).toBeDisabled();

    await expect(reservedSeat).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  test("SEAT-UI-10: selected seat can be deselected", async ({
    page,
  }) => {
    const seat = page.getByRole("button", {
      name: /Row A, seat 1/i,
    });

    await seat.click();

    await expect(seat).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    await seat.click();

    await expect(seat).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  test("SEAT-UI-11: payment button appears after selecting a seat", async ({
    page,
  }) => {
    const seat = page.getByRole("button", {
      name: /Row A, seat 1/i,
    });

    await seat.click();

    await expect(
      page.getByRole("button", {
        name: /Proceed to Payment/i,
      })
    ).toBeVisible();
  });
});