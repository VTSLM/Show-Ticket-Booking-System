import { test, expect } from "@playwright/test";

const shows = [
  {
    show_id: "movie-1",
    start_time: "2026-12-15T18:30:00",
    base_price: 250,
    title: "Interstellar",
    event_type: "movie",
    language: "English",
    poster_url: null,
    venue_name: "PVR Ahmedabad",
    city: "Ahmedabad",
    available_seats: 72,
  },
  {
    show_id: "concert-1",
    start_time: "2026-12-16T19:00:00",
    base_price: 350,
    title: "Coldplay Live",
    event_type: "concert",
    language: "English",
    poster_url: null,
    venue_name: "Narendra Modi Stadium",
    city: "Ahmedabad",
    available_seats: 250,
  },
];

async function setup(page: any) {
  await page.route("**/api/browse/cities", async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(["Ahmedabad", "Mumbai", "Delhi"]),
    });
  });

  await page.route("**/api/browse/shows**", async (route: any) => {
    const url = new URL(route.request().url());

    const search = url.searchParams.get("search")?.toLowerCase();
    const city = url.searchParams.get("city")?.toLowerCase();
    const eventType = url.searchParams.get("event_type")?.toLowerCase();

    let result = [...shows];

    if (search) {
      result = result.filter(
        (show) =>
          show.title.toLowerCase().includes(search) ||
          show.venue_name.toLowerCase().includes(search)
      );
    }

    if (city) {
      result = result.filter(
        (show) => show.city.toLowerCase() === city
      );
    }

    if (eventType) {
      result = result.filter(
        (show) => show.event_type.toLowerCase() === eventType
      );
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(result),
    });
  });

  await page.goto("/browse");
}

test.describe("Browsing - Filters", () => {
  test.beforeEach(async ({ page }) => {
    await setup(page);
  });

  test("BROWSE-FILTER-01 search by show title", async ({ page }) => {
    const search = page.getByRole("textbox", {
      name: "Search shows or venues",
    });

    await search.fill("Interstellar");
    await page.getByRole("button", { name: "Search" }).click();

    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).toBeVisible();

    await expect(
      page.getByRole("heading", { name: "Coldplay Live" })
    ).not.toBeVisible();
  });

  test("BROWSE-FILTER-02 search by venue", async ({ page }) => {
    const search = page.getByRole("textbox", {
      name: "Search shows or venues",
    });

    await search.fill("Narendra Modi Stadium");
    await page.getByRole("button", { name: "Search" }).click();

    await expect(
      page.getByRole("heading", { name: "Coldplay Live" })
    ).toBeVisible();

    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).not.toBeVisible();
  });

  test("BROWSE-FILTER-03 search is case insensitive", async ({ page }) => {
    const search = page.getByRole("textbox", {
      name: "Search shows or venues",
    });

    await search.fill("INTERSTELLAR");
    await page.getByRole("button", { name: "Search" }).click();

    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).toBeVisible();
  });

  test("BROWSE-FILTER-04 filter by city", async ({ page }) => {
    await page
      .getByRole("combobox", { name: "Filter by city" })
      .selectOption("Ahmedabad");

    await page.getByRole("button", { name: "Search" }).click();

    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).toBeVisible();

    await expect(
      page.getByRole("heading", { name: "Coldplay Live" })
    ).toBeVisible();
  });

  test("BROWSE-FILTER-05 filter by event type", async ({ page }) => {
    await page
      .getByRole("combobox", { name: "Filter by show type" })
      .selectOption("movie");

    await page.getByRole("button", { name: "Search" }).click();

    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).toBeVisible();

    await expect(
      page.getByRole("heading", { name: "Coldplay Live" })
    ).not.toBeVisible();
  });

  test("BROWSE-FILTER-06 combine search and event type", async ({ page }) => {
    await page
      .getByRole("textbox", { name: "Search shows or venues" })
      .fill("Interstellar");

    await page
      .getByRole("combobox", { name: "Filter by show type" })
      .selectOption("movie");

    await page.getByRole("button", { name: "Search" }).click();

    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).toBeVisible();

    await expect(
      page.getByRole("heading", { name: "Coldplay Live" })
    ).not.toBeVisible();
  });

  test("BROWSE-FILTER-07 pressing Enter performs search", async ({ page }) => {
    const search = page.getByRole("textbox", {
      name: "Search shows or venues",
    });

    await search.fill("Interstellar");
    await search.press("Enter");

    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).toBeVisible();
  });
});