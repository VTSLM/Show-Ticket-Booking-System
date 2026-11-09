import { test, expect } from "@playwright/test";

const shows = [
  {
    show_id: "show-101",
    start_time: "2026-12-15T18:30:00",
    base_price: 250,
    show_status: "scheduled",
    event_id: "event-101",
    title: "Interstellar",
    event_type: "movie",
    language: "English",
    genre: "Sci-Fi",
    duration_minutes: 169,
    poster_url: null,
    description: "A science-fiction movie.",
    venue_id: "venue-101",
    venue_name: "PVR Ahmedabad",
    city: "Ahmedabad",
    address: "SG Highway",
    screen_name: "Audi 1",
    capacity: 100,
    available_seats: 72,
    total_seats: 100,
  },
  {
    show_id: "show-102",
    start_time: "2026-12-16T19:00:00",
    base_price: 350,
    show_status: "scheduled",
    event_id: "event-102",
    title: "Coldplay Live",
    event_type: "concert",
    language: "English",
    genre: "Music",
    duration_minutes: 120,
    poster_url: null,
    description: "Live concert.",
    venue_id: "venue-102",
    venue_name: "Narendra Modi Stadium",
    city: "Ahmedabad",
    screen_name: "Main",
    capacity: 500,
    available_seats: 250,
    total_seats: 500,
  },
];

const cities = ["Ahmedabad", "Mumbai", "Delhi"];

test.describe("Browsing - Edge Cases", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/browse/cities**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(cities),
      });
    });

    await page.route("**/api/browse/shows**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(shows),
      });
    });
  });

  test("BROWSE-EDGE-01 no results displays empty state", async ({ page }) => {
    await page.route("**/api/browse/shows**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/browse");

    await expect(page.getByText("No shows found")).toBeVisible();
    await expect(
      page.getByText("Try a different search or filter.")
    ).toBeVisible();
  });

  test("BROWSE-EDGE-02 missing poster displays fallback", async ({ page }) => {
    await page.route("**/api/browse/shows**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            ...shows[0],
            poster_url: null,
          },
        ]),
      });
    });

    await page.goto("/browse");

    const showCard = page.getByRole("link", {
      name: /Interstellar movie English/i,
    });

    await expect(showCard).toBeVisible();
    await expect(showCard.getByText("🎥")).toBeVisible();
  });

  test("BROWSE-EDGE-03 missing language displays fallback", async ({
    page,
  }) => {
    await page.route("**/api/browse/shows**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            ...shows[0],
            language: null,
          },
        ]),
      });
    });

    await page.goto("/browse");

    const showCard = page.getByRole("link", {
      name: /Interstellar movie/i,
    });

    await expect(showCard).toBeVisible();
    await expect(showCard).toContainText("Language not listed");
  });

  test("BROWSE-EDGE-04 missing available seats displays fallback", async ({
    page,
  }) => {
    await page.route("**/api/browse/shows**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            ...shows[0],
            available_seats: null,
          },
        ]),
      });
    });

    await page.goto("/browse");

    const showCard = page.getByRole("link", {
      name: /Interstellar movie English/i,
    });

    await expect(showCard).toBeVisible();
    await expect(showCard).toContainText("— seats");
  });

  test("BROWSE-EDGE-05 backend failure displays error", async ({ page }) => {
  let intercepted = false;

  await page.route("**/api/browse/shows**", async (route) => {
    intercepted = true;

    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Internal server error",
      }),
    });
  });

  await page.goto("/browse");

  await page.waitForTimeout(1000);

  console.log("API request intercepted:", intercepted);

  console.log(
    "Page text:",
    await page.locator("body").innerText()
  );

  await expect(
    page.getByText("Internal server error").first()
  ).toBeVisible();
});
  test("BROWSE-EDGE-06 empty search returns all shows", async ({ page }) => {
    await page.goto("/browse");

    const searchInput = page.getByRole("textbox", {
      name: "Search shows or venues",
    });

    await expect(searchInput).toBeVisible();

    await searchInput.fill("");

    await page.getByRole("button", {
      name: "Search",
    }).click();

    await expect(
      page.getByRole("link", {
        name: /Interstellar movie English/i,
      })
    ).toBeVisible();

    await expect(
      page.getByRole("link", {
        name: /Coldplay Live concert English/i,
      })
    ).toBeVisible();
  });
});